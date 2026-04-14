import os
import json
import re
import time
import fitz
from anthropic import Anthropic
from google import genai
from google.genai import types, errors

import config

def prepare_pdf_for_vision(file_bytes: bytes, f_profile: dict) -> tuple[fitz.Document, list[str], str | None]:
    """
    Opens a PDF, extracts PII targets from the family profile for redaction,
    and authenticates the document if it is encrypted using the family IDs.
    Returns a 3-tuple:
      - The opened PyMuPDF Document
      - A list of PII strings to redact
      - The ID number that was used to authenticate (None if doc was not encrypted)
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Extract PII targets for redaction and IDs for authentication
    f_pii = f_profile.get("pii_data", {})
    pii_targets = []
    id_numbers = []
    
    for m_key in ["member1", "member2"]:
        m_data = f_pii.get(m_key)
        if m_data:
            id_num = m_data.get("idNumber", "")
            if id_num:
                id_numbers.append(id_num)
            
            pii_targets.extend([
                m_data.get("name", ""),
                m_data.get("lastName", ""),
                id_num,
                m_data.get("email", "")
            ])
            if id_num and id_num.startswith("0"):
                pii_targets.append(id_num.lstrip("0"))
                
    pii_targets = [t for t in pii_targets if t and len(t) > 2]
    
    # Authenticate if encrypted
    authenticated_id: str | None = None
    if doc.is_encrypted:
        print(f"🔒 [FLOW_UTILS] Document is encrypted. Trying password authentication...")
        for doc_id in id_numbers:
            if doc.authenticate(doc_id):
                authenticated_id = doc_id
                print(f"✅ [FLOW_UTILS] Authenticated successfully with ID {doc_id}")
                break
        if authenticated_id is None:
            raise ValueError("Could not decrypt the PDF. Please ensure the family ID numbers are correct in the profile.")
            
    return doc, pii_targets, authenticated_id

def call_claude_vision(api_key: str, images_b64: list[str], prompt: str) -> dict:
    """
    Sends base64 images and a prompt to Claude Vision and returns parsed JSON.
    """
    if not images_b64:
        raise ValueError("No images provided to Claude Vision.")

    client = Anthropic(api_key=api_key)
    content_blocks = []
    
    # Send up to 20 pages — pension reports can be long (multiple product sections)
    for b64 in images_b64[:20]:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
        
    content_blocks.append({"type": "text", "text": prompt})

    print(f"🧠 [FLOW_UTILS] Sending {min(len(images_b64), 20)} images to Claude...")
    start_time = time.time()
    response = client.messages.create(
        model=config.CLAUDE_MODEL_NAME,
        max_tokens=4096,
        messages=[{"role": "user", "content": content_blocks}],
    )
    duration = time.time() - start_time
    print(f"✅ [FLOW_UTILS] Claude responded successfully in {duration:.2f}s")

    response_text = response.content[0].text.strip()
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
    response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE)
    
    try:
        return json.loads(response_text)
    except Exception as e:
        print(f"💥 [FLOW_UTILS] Failed to parse Claude JSON: {e}\nRaw Response:\n{response_text[:300]}")
        raise ValueError("Invalid JSON returned by Claude Vision")


def call_claude_text(api_key: str, sys_prompt: str, user_prompt: str) -> list | dict:
    """
    Sends pure text to Claude (for advisory) and returns parsed JSON.
    """
    client = Anthropic(api_key=api_key)
    
    print("🧠 [FLOW_UTILS] Sending text prompt to Claude...")
    start_time = time.time()
    response = client.messages.create(
        model=config.CLAUDE_MODEL_NAME,
        max_tokens=8192,
        system=sys_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    duration = time.time() - start_time
    print(f"✅ [FLOW_UTILS] Claude responded successfully in {duration:.2f}s")
    
    response_text = response.content[0].text.strip()
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
    response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE)
    
    try:
        return json.loads(response_text)
    except Exception as e:
        print(f"💥 [FLOW_UTILS] Failed to parse Claude JSON: {e}")
        raise ValueError("Invalid JSON returned by Claude")


def call_gemini_json(api_key: str, sys_prompt: str, user_prompt: str, max_retries: int = 10, retry_delay: float = 2.0) -> list | dict:
    """
    Sends text to Gemini Flash configured for strict JSON output.
    Retries up to max_retries times with retry_delay seconds between each attempt.
    Raises a descriptive RuntimeError if all attempts fail.
    """
    client = genai.Client(api_key=api_key)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🤖 [FLOW_UTILS] Calling Gemini 2.5 Flash... (attempt {attempt}/{max_retries})")
            start_time = time.time()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL_NAME,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )
            duration = time.time() - start_time
            print(f"✅ [FLOW_UTILS] Gemini responded successfully in {duration:.2f}s")

            res_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(res_text)

        except Exception as e:
            last_error = e
            
            # Check for quota exhaustion (429 / RESOURCE_EXHAUSTED)
            is_quota_error = (
                (isinstance(e, errors.APIError) and e.code == 429) or 
                "429" in str(e) or 
                "RESOURCE_EXHAUSTED" in str(e)
            )
            
            if is_quota_error:
                print(f"🛑 [FLOW_UTILS] Quota exhausted (429). Stopping retries.")
                raise RuntimeError("המכסה היומית של ה-AI הסתיימה. נא לנסות שוב מחר או לשדרג את החשבון (בוצע ניסיון להפסיק ריטריים מיותרים).")

            if attempt < max_retries:
                wait_time = retry_delay + attempt
                print(f"⚠️ [FLOW_UTILS] Gemini attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"💥 [FLOW_UTILS] All {max_retries} Gemini attempts failed. Last error: {e}")

    raise RuntimeError(
        f"שירות ה-AI (Gemini) אינו זמין כרגע לאחר {max_retries} ניסיונות. "
        f"נא לנסות שוב מאוחר יותר. (שגיאה: {last_error})"
    )
