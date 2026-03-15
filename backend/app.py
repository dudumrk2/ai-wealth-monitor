from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import shutil
import base64
import json
import fitz # PyMuPDF
from anthropic import Anthropic
from dotenv import load_dotenv

import sys
import time

# Try loading from current dir, then from parent dir (project root)
if not load_dotenv():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

print(f"ANTHROPIC_API_KEY loaded: {'Yes (starts with ' + os.environ.get('ANTHROPIC_API_KEY')[:10] + '...)' if os.environ.get('ANTHROPIC_API_KEY') else 'No'}")
sys.stdout.flush()

from mock_data import MOCK_DATA

app = FastAPI(title="AI Family Pension & Wealth Monitor API")

# Setup directories for local drop-folder processing
# We move these outside the backend folder to prevent uvicorn reloader from restarting
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

INBOX_DIR = os.path.join(DATA_DIR, "local_inbox")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
DEBUG_DIR = os.path.join(DATA_DIR, "debug_redaction")
MOCK_DATA_DIR = os.path.join(DATA_DIR, "mock_analysis")

os.makedirs(INBOX_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(MOCK_DATA_DIR, exist_ok=True)

print(f"Data directories initialized at: {DATA_DIR}")
sys.stdout.flush()

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"\n[HTTP] {request.method} {request.url.path} - Receiving...")
    sys.stdout.flush()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    print(f"[HTTP] {request.method} {request.url.path} - {response.status_code} ({process_time:.2f}ms)")
    sys.stdout.flush()
    return response

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the Firebase token. 
    """
    token = credentials.credentials
    if not token or token == "undefined" or token == "null":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"uid": "mock_user_id"}

@app.get("/api/portfolio")
def get_portfolio(user: dict = Depends(verify_token)):
    return {
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"],
        "action_items": MOCK_DATA["action_items"]
    }

@app.get("/api/action-items")
def get_action_items(user: dict = Depends(verify_token)):
    return MOCK_DATA["action_items"]

class ManualInvestment(BaseModel):
    id: str
    name: str
    description: str
    balance: float
    monthly_deposit: float
    expected_yearly_yield: float
    start_date: str
    end_date: str
    owner: str = "user" 

@app.post("/api/manual-investment", status_code=status.HTTP_201_CREATED)
def add_manual_investment(investment: ManualInvestment, user: dict = Depends(verify_token)):
    return {"status": "success", "data": investment.model_dump()}

class FamilyMemberPII(BaseModel):
    name: str = ""
    lastName: str = ""
    idNumber: str = ""
    email: str = ""

class PIIDataRequest(BaseModel):
    member1: Optional[FamilyMemberPII] = None
    member2: Optional[FamilyMemberPII] = None
    debug: bool = False
    analyze: bool = True

@app.post("/api/process-inbox")
def process_inbox(pii_request: PIIDataRequest, user: dict = Depends(verify_token)):
    """
    Process PDFs from local_inbox, redact PII, send to Anthropic Vision, and archive.
    """
    print("\n" + "="*50)
    print(f"🚀 INCOMING REQUEST: processing inbox for user: {user.get('uid')}")
    print("="*50 + "\n")
    sys.stdout.flush()
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    results = []
    
    # Pre-process PII into targets
    members = []
    if pii_request.member1: members.append(("member_1", pii_request.member1))
    if pii_request.member2: members.append(("member_2", pii_request.member2))
    
    # 0. Cleanup: If we are analyzing, clear previous AI-extracted data to prevent duplication
    if pii_request.analyze:
        print("Clearing previous AI-extracted funds from portfolios...")
        for key in ["user", "spouse"]:
            MOCK_DATA["portfolios"][key]["funds"] = [f for f in MOCK_DATA["portfolios"][key]["funds"] if not f.get("id", "").startswith("ai_")]
    
    all_target_strings = []
    for _, m in members:
        all_target_strings.extend([m.name, m.lastName, m.idNumber, m.email])
        # Special logic: if ID starts with 0, also redact version without 0
        if m.idNumber and m.idNumber.startswith('0'):
            all_target_strings.append(m.idNumber[1:])
    
    all_target_strings = [s for s in all_target_strings if s and len(s.strip()) > 2]
    
    print(f"DEBUG: Data directories initialized at: {DATA_DIR}")
    print(f"DEBUG: Scanning inbox directory: {INBOX_DIR}")
    sys.stdout.flush()
    if not os.path.exists(INBOX_DIR):
        print(f"ERROR: Inbox directory missing at {INBOX_DIR}")
        return {"processed_count": 0, "results": [], "error": f"Inbox directory missing at {INBOX_DIR}"}

    pdf_files = [f for f in os.listdir(INBOX_DIR) if f.lower().endswith('.pdf')]
    print(f"DEBUG: Found {len(pdf_files)} PDF files: {pdf_files}")
    sys.stdout.flush()
    
    if not pdf_files:
        print("No PDF files found to process.")
        return {"processed_count": 0, "results": [], "message": "No PDFs found in local_inbox"}
        
    for filename in pdf_files:
        filepath = os.path.join(INBOX_DIR, filename)
        redacted_images_base64 = []
        
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()
            
            doc = fitz.open("pdf", file_bytes)
            
            detected_owner = "unknown"
            if doc.is_encrypted:
                authenticated = False
                for label, m in members:
                    if m.idNumber and doc.authenticate(m.idNumber):
                        authenticated = True
                        detected_owner = label
                        print(f"Successfully authenticated {filename} using {label}'s ID.")
                        break
                
                if not authenticated:
                    results.append({"filename": filename, "error": "PDF is password protected and none of the provided IDs worked."})
                    doc.close()
                    continue
            else:
                # Fallback: Count matches in text if not encrypted
                match_counts = {"member_1": 0, "member_2": 0}
                for page in doc:
                    text = page.get_text().lower()
                    for label, m in members:
                        if m.name and m.name.lower().strip() in text: match_counts[label] += 1
                        if m.idNumber and m.idNumber.strip() in text: match_counts[label] += 1
                
                if match_counts["member_1"] > match_counts["member_2"]: detected_owner = "member_1"
                elif match_counts["member_2"] > match_counts["member_1"]: detected_owner = "member_2"
                print(f"Document owner identified via text matching: {detected_owner} (Matches: {match_counts})")

            print(f"Processing {filename}: {len(doc)} pages found. Detected Owner: {detected_owner}")
            
            start_page = 3 if len(doc) > 3 else 0
            
            for page_num in range(start_page, len(doc)):
                page = doc[page_num]
                if all_target_strings:
                    for text in all_target_strings:
                        for inst in page.search_for(text):
                            page.draw_rect(inst, color=(0, 0, 0), fill=(0, 0, 0))
                
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                b64_str = base64.b64encode(img_data).decode("utf-8")
                redacted_images_base64.append(b64_str)

                if pii_request.debug:
                    debug_file_path = os.path.join(DEBUG_DIR, f"{filename}_page_{page_num}.png")
                    with open(debug_file_path, "wb") as f:
                        f.write(img_data)
            
            doc.close()
            
            if not redacted_images_base64:
                results.append({"filename": filename, "error": "No pages to process."})
                continue

            print(f"Successfully redacted {len(redacted_images_base64)} pages for {filename}")

            if not api_key or not pii_request.analyze:
                status_msg = "Skipping AI analysis (analyze=False)" if not pii_request.analyze else "Warning: ANTHROPIC_API_KEY missing"
                print(f"{status_msg} for {filename}")
                if pii_request.debug or not pii_request.analyze:
                    results.append({
                        "filename": filename,
                        "data": {"owner_name": "PREVIEW_ONLY", "products": []},
                        "preview_images": redacted_images_base64,
                        "status": "preview_only"
                    })
                    continue
                else:
                    results.append({"filename": filename, "error": "ANTHROPIC_API_KEY missing."})
                    continue

            # Claude Analysis
            print(f"\n🧠 SENDING TO CLAUDE: {filename} ({len(redacted_images_base64)} pages)...")
            sys.stdout.flush()
            anthropic_client = Anthropic(api_key=api_key)
            content_blocks = []
            for b64 in redacted_images_base64[:10]: # Limit to 10 images to avoid payload limits
                content_blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
            
            content_blocks.append({"type": "text", "text": "Extract data from report pages."})

            system_prompt = f"""
You are a financial data extraction expert for the Israeli market.
Extract all pension, insurance, and provident fund products from the provided images.

### EXCLUSION RULES:
- IMPORTANT: DO NOT extract any data from "כלל חיסכון פיננסי" (Clal Financial Savings). 
- If a product is labeled as "חיסכון פיננסי" and the provider is "כלל" (Clal), ignore it entirely.
- Do NOT include these products in the JSON response at all.

### PRODUCT TYPES (STRICT - USE ONLY THESE):
- פנסיה
- מנהלים
- השתלמות
- גמל
- גמל להשקעה

### DATA RULES:
1. NUMBERS: Ensure numbers are NOT reversed. '50' must remain '50'. '1,234' must remain '1,234'.
2. FIELD MAPPING:
   - balance: current accumulation (יתרה צבורה)
   - monthly_deposit: regular monthly contribution (הפקדה חודשית)
   - management_fee_deposit: fee on deposits (דמי ניהול מהפקדה)
   - management_fee_accumulation: fee on accumulation (דמי ניהול מצבירה)
   - yield_1yr/3yr/5yr: percentage yields (תשואה)

Return ONLY a JSON object:
{{
  "products": [
    {{
      "product_type": "...",
      "provider_name": "...",
      "track_name": "...",
      "policy_number": "...",
      "balance": 0,
      "monthly_deposit": 0,
      "management_fee_deposit": 0,
      "management_fee_accumulation": 0,
      "yield_1yr": 0,
      "yield_3yr": 0,
      "yield_5yr": 0
    }}
  ]
}}
"""

            response = anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": content_blocks}]
            )
            
            response_text = response.content[0].text.strip()
            print(f"DEBUG Claude raw response (first 500 chars): {response_text[:500]}")
            sys.stdout.flush()
            # Use raw_decode to parse ONLY the first valid JSON object and ignore anything after it
            start = response_text.find('{')
            if start == -1:
                raise ValueError(f"Claude did not return valid JSON. Response: {response_text[:200]}")
            decoder = json.JSONDecoder()
            pension_data, _ = decoder.raw_decode(response_text, start)
            
            print("\n" + "✨" * 20)
            print("--- CLAUDE ANALYSIS RESULT ---")
            print(json.dumps(pension_data, indent=2, ensure_ascii=False))
            print("--- END OF RESULT ---")
            print("✨" * 20 + "\n")
            sys.stdout.flush()
            
            # Save as mock data for future dev
            with open(os.path.join(MOCK_DATA_DIR, f"{filename}_mock.json"), "w", encoding="utf-8") as f:
                json.dump(pension_data, f, indent=2, ensure_ascii=False)

            result_entry = {"filename": filename, "data": pension_data}
            if pii_request.debug: result_entry["preview_images"] = redacted_images_base64
            results.append(result_entry)
            
            # Archive the file after successful processing to prevent loops
            try:
                shutil.move(filepath, os.path.join(ARCHIVE_DIR, filename))
                print(f"Successfully processed and archived {filename}")
            except Exception as archive_err:
                print(f"WARNING: Could not archive {filename}: {str(archive_err)}")
            
            sys.stdout.flush()
            
            # Map Claude data to MOCK_DATA format and update in memory
            owner_key = "user" if detected_owner == "member_1" else "spouse" if detected_owner == "member_2" else "user"
            
            for p in pension_data.get("products", []):
                # Map Hebrew product types to frontend categories
                raw_type = p.get("product_type", "")
                provider = p.get("provider_name", "").strip()
                track = p.get("track_name", "").strip()
                
                # Double-check exclusion rule (Python-side safety filter)
                if "כלל" in provider and "חיסכון פיננסי" in track:
                    print(f"Skipping excluded product (Filter active): {provider} - {track}")
                    continue
                if "כלל חברה לביטוח" in provider and "חיסכון פיננסי" in track:
                    print(f"Skipping excluded product (Filter active): {provider} - {track}")
                    continue

                category = "provident" # default
                if "פנסיה" in raw_type: category = "pension"
                elif "מנהלים" in raw_type: category = "managers"
                elif "השתלמות" in raw_type: category = "study"
                elif "גמל להשקעה" in raw_type: category = "investment_provident"
                elif "גמל" in raw_type: category = "provident"
                
                MOCK_DATA["portfolios"][owner_key]["funds"].append({
                    "id": f"ai_{filename}_{os.urandom(2).hex()}",
                    "category": category,
                    "provider_name": p.get("provider_name", "Unknown"),
                    "track_name": p.get("track_name", "Unknown"),
                    "status": "active",
                    "balance": p.get("balance", 0),
                    "monthly_deposit": p.get("monthly_deposit", 0),
                    "management_fee_deposit": p.get("management_fee_deposit", 0),
                    "management_fee_accumulation": p.get("management_fee_accumulation", 0),
                    "yield_1yr": p.get("yield_1yr", 0),
                    "yield_3yr": p.get("yield_3yr", 0),
                    "yield_5yr": p.get("yield_5yr", 0),
                    "policy_number": p.get("policy_number", ""),
                })
            
        except Exception as e:
            print(f"ERROR processing {filename}: {str(e)}")
            sys.stdout.flush()
            error_entry = {"filename": filename, "error": str(e)}
            if 'redacted_images_base64' in locals() and pii_request.debug:
                error_entry["preview_images"] = redacted_images_base64
            results.append(error_entry)
            # Archive even failed files to prevent re-triggering the popup in loops
            try:
                shutil.move(filepath, os.path.join(ARCHIVE_DIR, f"FAILED_{filename}"))
                print(f"Archived failed file as FAILED_{filename}")
            except Exception as archive_err:
                print(f"WARNING: Could not archive failed file {filename}: {str(archive_err)}")
            
    return {"status": "success", "processed_count": len(pdf_files), "results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
