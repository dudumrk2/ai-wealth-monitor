from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
import firebase_admin
import datetime
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
from firebase_admin import auth

import sys
import time

# Try loading from current dir, then from parent dir (project root)
if not load_dotenv():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

print(f"ANTHROPIC_API_KEY loaded: {'Yes (starts with ' + os.environ.get('ANTHROPIC_API_KEY')[:10] + '...)' if os.environ.get('ANTHROPIC_API_KEY') else 'No'}")
sys.stdout.flush()

import asyncio

from mock_data import MOCK_DATA
import db_manager
import ai_advisor
import market_data as market_data_module


def _collect_market_data(portfolios: dict) -> dict:
    """
    Fetch top-3 competitors for every unique (product_type, track_name) pair
    found in the user's portfolio, and return a dict keyed by track_name.

    Uses asyncio.run() so it is callable from synchronous FastAPI endpoints.
    For async endpoints, use _collect_market_data_async() instead.
    """
    print("\n📊 [APP] Collecting market competitor data for all tracks...")

    async def _fetch_all(tasks: list[tuple[str, str]]) -> dict:
        results = {}
        for product_type, track_name in tasks:
            if track_name and track_name not in results:
                competitors = await market_data_module.get_top_competitors(
                    product_type=product_type,
                    track_name=track_name,
                )
                results[track_name] = competitors
        return results

    # Gather all (product_type, track_name) pairs from both owners
    tasks: list[tuple[str, str]] = []
    for owner_key in ["user", "spouse"]:
        for fund in portfolios.get(owner_key, {}).get("funds", []):
            tasks.append((
                fund.get("category", ""),
                fund.get("track_name", ""),
            ))

    if not tasks:
        print("ℹ️  [APP] No funds found — skipping market data collection.")
        return {}

    try:
        market_data_result = asyncio.run(_fetch_all(tasks))
        print(f"✅ [APP] Market data collected for {len(market_data_result)} unique track(s).")
        return market_data_result
    except Exception as e:
        print(f"⚠️  [APP] Market data collection failed: {e}. Proceeding with empty market data.")
        return {}

async def _collect_market_data_async(portfolios: dict) -> dict:
    """
    Async-native version of _collect_market_data.
    Use this inside async FastAPI endpoints (e.g. process_reports) so that
    asyncio.run() is never called from within a running event loop.
    """
    print("\n📊 [APP] Collecting market competitor data for all tracks (async)...")

    tasks: list[tuple[str, str]] = []
    for owner_key in ["user", "spouse"]:
        for fund in portfolios.get(owner_key, {}).get("funds", []):
            tasks.append((
                fund.get("category", ""),
                fund.get("track_name", ""),
            ))

    if not tasks:
        print("ℹ️  [APP] No funds found — skipping market data collection.")
        return {}

    results: dict = {}
    try:
        for product_type, track_name in tasks:
            if track_name and track_name not in results:
                competitors = await market_data_module.get_top_competitors(
                    product_type=product_type,
                    track_name=track_name,
                )
                results[track_name] = competitors
        print(f"✅ [APP] Market data collected for {len(results)} unique track(s).")
        return results
    except Exception as e:
        print(f"⚠️  [APP] Market data collection failed: {e}. Proceeding with empty market data.")
        return {}


# Test UID removed - now using dynamic UID from token

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
    try:
        if not firebase_admin._apps:
            # If we're here, initialization failed. Try one last search.
            import db_manager
            db_manager.initialize_firebase()
            
        if not firebase_admin._apps:
            print("⚠️ [AUTH] Firebase not initialized (missing key). Falling back to session-based mock UID for local debug.")
            return {"uid": "414PiKcFOWRO0PNRAfuVsD3fqoV2"}
                
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        # Check if it's the specific SDK initialization error or import error
        err_msg = str(e)
        if "initialize_app()" in err_msg or "firebase_admin" in err_msg:
             print(f"⚠️ [AUTH] Firebase app check failed ({err_msg}). Falling back to session-based mock UID.")
             return {"uid": "414PiKcFOWRO0PNRAfuVsD3fqoV2"}
        print(f"❌ [AUTH] Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/api/portfolio")
def get_portfolio(user: dict = Depends(verify_token)):
    uid = user.get("uid")
    print(f"🔍 [APP] GET /api/portfolio - Fetching for {uid}")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    
    if portfolio_doc:
        print(f"✅ [APP] Returning Firestore portfolio for {uid}")
        return {
            "last_updated": portfolio_doc.get("last_updated"),
            "portfolios": portfolio_doc.get("portfolios"),
            "action_items": portfolio_doc.get("action_items")
        }
    
    print(f"⚠️ [APP] Portfolio not found in Firestore for {uid}. Falling back to mock data.")
    return {
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"],
        "action_items": MOCK_DATA["action_items"]
    }

@app.get("/api/action-items")
def get_action_items(user: dict = Depends(verify_token)):
    uid = user.get("uid")
    print(f"🔍 [APP] GET /api/action-items - Fetching for {uid}")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if portfolio_doc:
        return portfolio_doc.get("action_items", [])
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
    
    # Step A: Call get_family_profile(uid) before processing the PDF
    uid = user.get("uid")
    print(f"\n🚀 [APP] Starting processing flow for UID: {uid}")
    family_profile = db_manager.get_family_profile(uid)
    
    f_profile = {}
    if family_profile:
        print(f"✅ [APP] Family profile found for {uid}")
        # Step B: Pass the fetched pii_data to the local PDF redaction logic
        f_pii = family_profile.get("pii_data", {})
        f_profile = family_profile.get("financial_profile", {})
        
        print(f"DEBUG: Financial Profile keys found: {list(f_profile.keys())}")
        
        for m_key in ["member1", "member2"]:
            m_data = f_pii.get(m_key)
            if m_data:
                name = m_data.get("name", "")
                last = m_data.get("lastName", "")
                id_num = m_data.get("idNumber", "")
                email = m_data.get("email", "")
                print(f"DEBUG: Adding redaction targets for {m_key}: {name} {last}, {id_num}, {email}")
                all_target_strings.extend([name, last, id_num, email])
                if id_num and id_num.startswith('0'):
                    all_target_strings.append(id_num[1:])
    else:
        print(f"⚠️ [APP] No profile found for {uid} in Firestore. Falling back to request data.")

    all_target_strings = list(set([s for s in all_target_strings if s and len(s.strip()) > 2]))
    print(f"DEBUG: Total collective redaction strings: {len(all_target_strings)}")
    
    print(f"DEBUG: Scanning inbox directory: {INBOX_DIR}")
    sys.stdout.flush()
    if not os.path.exists(INBOX_DIR):
        print(f"ERROR: Inbox directory missing at {INBOX_DIR}")
        return {"processed_count": 0, "results": [], "error": f"Inbox directory missing at {INBOX_DIR}"}

    pdf_files = [f for f in os.listdir(INBOX_DIR) if f.lower().endswith('.pdf')]
    print(f"DEBUG: Found {len(pdf_files)} PDF files to process.")
    sys.stdout.flush()
    
    if not pdf_files:
        print("ℹ️ [APP] No PDF files found in local_inbox")
        return {"processed_count": 0, "results": [], "message": "No PDFs found in local_inbox"}
        
    for filename in pdf_files:
        print(f"\n📄 [APP] Processing file: {filename}")
        filepath = os.path.join(INBOX_DIR, filename)
        redacted_images_base64 = []
        
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()
            
            doc = fitz.open("pdf", file_bytes)
            
            detected_owner = "unknown"
            if doc.is_encrypted:
                print(f"DEBUG: Document {filename} is encrypted. Trying password authentication...")
                authenticated = False
                for label, m in members:
                    if m.idNumber and doc.authenticate(m.idNumber):
                        authenticated = True
                        detected_owner = label
                        print(f"✅ Authenticated using request {label}'s ID.")
                        break
                
                if not authenticated and family_profile:
                    for m_key in ["member1", "member2"]:
                        m_id = family_profile.get("pii_data", {}).get(m_key, {}).get("idNumber")
                        if m_id and doc.authenticate(m_id):
                            authenticated = True
                            detected_owner = "member_1" if m_key == "member1" else "member_2"
                            print(f"✅ Authenticated using Firestore {m_key}'s ID.")
                            break

                if not authenticated:
                    print(f"❌ [APP] Could not authenticate {filename}")
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
                    
                    if family_profile:
                        for m_key in ["member1", "member2"]:
                            m_pii = family_profile.get("pii_data", {}).get(m_key, {})
                            label = "member_1" if m_key == "member1" else "member_2"
                            if m_pii.get("name") and m_pii.get("name").lower().strip() in text: match_counts[label] += 1
                            if m_pii.get("idNumber") and m_pii.get("idNumber").strip() in text: match_counts[label] += 1

                if match_counts["member_1"] > match_counts["member_2"]: detected_owner = "member_1"
                elif match_counts["member_2"] > match_counts["member_1"]: detected_owner = "member_2"
                print(f"DEBUG: Identified Owner: {detected_owner} (Matches: {match_counts})")

            print(f"DEBUG: Rendering and redacting {len(doc)} pages...")
            
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

            doc.close()
            print(f"✅ Redacted {len(redacted_images_base64)} pages for {filename}")

            if not api_key or not pii_request.analyze:
                print(f"DEBUG: Skipping AI analysis (analyze={pii_request.analyze}, api_key={bool(api_key)})")
                # Return a sample of redacted images (first 3 pages) for preview
                preview_sample = redacted_images_base64[:3]
                results.append({"filename": filename, "status": "preview_only", "preview_images": preview_sample})
                continue

            # Step C: Extract portfolio data via Anthropic Vision
            print(f"🧠 [APP] Sending redacted images to Claude for extraction...")
            anthropic_client = Anthropic(api_key=api_key)
            
            # System prompt for PDF data extraction
            extraction_system_prompt = """
אתה מומחה לחילוץ נתונים פיננסיים מדוחות פנסיה ישראליים.
חלץ את כל המוצרים הפיננסיים מהדוח והחזר JSON תקני בלבד.
המבנה חייב להיות:
{
  "products": [
    {
      "product_type": "string (סוג המוצר בעברית: פנסיה/ביטוח מנהלים/קרן השתלמות/קופת גמל/גמל להשקעה)",
      "provider_name": "string (שם חברת הביטוח/בית ההשקעות)",
      "track_name": "string (שם המסלול)",
      "policy_number": "string",
      "balance": number,
      "monthly_deposit": number,
      "management_fee_deposit": number,
      "management_fee_accumulation": number,
      "yield_1yr": number,
      "yield_3yr": number,
      "yield_5yr": number
    }
  ]
}

CRITICAL: 
- החזר JSON תקני בלבד ללא markdown, ללא הסברים
- השתמש במרכאות כפולות לכל מחרוזות
- אל תכניס מרכאות לתוך ערכי מחרוזות (השתמש ב-slash או הסר)
- כל הערכים המספריים ללא פסיקים (1234567 ולא 1,234,567)
- אם שדה לא קיים, השתמש ב-0 עבור מספרים ו-"" עבור מחרוזות
"""
            
            content_blocks = []
            for b64 in redacted_images_base64[:10]:
                content_blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
            content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})

            response = anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=extraction_system_prompt,
                messages=[{"role": "user", "content": content_blocks}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Robust JSON extraction - handle Hebrew text with quotes
            import re
            # Strip markdown code blocks if present
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
            response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE)
            response_text = response_text.strip()
            
            start = response_text.find('{')
            if start == -1: raise ValueError(f"No JSON found in response: {response_text[:200]}")
            try:
                decoder = json.JSONDecoder()
                pension_data, _ = decoder.raw_decode(response_text, start)
            except json.JSONDecodeError:
                # Fallback: try to find the outermost JSON object
                brace_count = 0
                end_idx = start
                for i, ch in enumerate(response_text[start:], start):
                    if ch == '{': brace_count += 1
                    elif ch == '}': brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
                pension_data = json.loads(response_text[start:end_idx])
            
            print(f"✅ [APP] AI Extraction for {filename} SUCCESS. Found {len(pension_data.get('products', []))} products.")
            # print(f"DEBUG: Raw extracted: {json.dumps(pension_data, indent=2, ensure_ascii=False)}")

            # Update MOCK_DATA in memory
            owner_key = "user" if detected_owner == "member_1" else "spouse" if detected_owner == "member_2" else "user"
            for p in pension_data.get("products", []):
                # ... mapping logic ...
                category = "provident"
                raw_type = p.get("product_type", "")
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
            
            shutil.move(filepath, os.path.join(ARCHIVE_DIR, filename))

        except Exception as e:
            print(f"💥 [APP] Error processing {filename}: {str(e)}")
            results.append({"filename": filename, "error": str(e)})

    # Step D: Generate action items ONLY if funds were actually extracted
    total_funds_extracted = (
        len(MOCK_DATA["portfolios"].get("user", {}).get("funds", [])) +
        len(MOCK_DATA["portfolios"].get("spouse", {}).get("funds", []))
    )
    
    if total_funds_extracted > 0 and pii_request.analyze:
        print(f"\n🤖 [APP] Orchestrating Action Items generation ({total_funds_extracted} funds found)...")
        # Fetch live competitor benchmarks for every track in the portfolio
        live_market_data = _collect_market_data(MOCK_DATA["portfolios"])
        action_items = ai_advisor.generate_action_items(
            family_portfolio=MOCK_DATA["portfolios"],
            market_data=live_market_data,
            financial_profile=f_profile
        )
    elif not pii_request.analyze:
        # Preview-only scan — don't call Claude for action items, return early
        print("\nℹ️ [APP] Preview scan complete. Skipping action items (analyze=False).")
        return {"status": "preview", "processed_count": len(pdf_files), "results": results}
    else:
        print(f"\n⚠️ [APP] No funds extracted from PDFs. Skipping action items to avoid empty recommendations.")
        action_items = []
    
    # Step E: Combine the extracted portfolio and action items into a single final JSON
    MOCK_DATA["action_items"] = action_items
    MOCK_DATA["last_updated"] = datetime.datetime.now().isoformat()
    
    final_json = {
        "uid": uid,
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"],
        "action_items": MOCK_DATA["action_items"]
    }
    
    print("\n📦 [APP] Final result consolidated. Sample Action Item:")
    if action_items:
        print(json.dumps(action_items[0], indent=2, ensure_ascii=False))
    
    # Step F: Pass the final JSON to save_processed_portfolio(uid, final_json)
    print("\n☁️ [APP] Final step: Persisting to Firestore...")
    db_manager.save_processed_portfolio(uid, final_json)
    
    print(f"\n🏁 [APP] Processing flow for {uid} COMPLETE.")
    return {"status": "success", "processed_count": len(pdf_files), "results": results, "final_data": final_json}

@app.post("/api/process-reports")
async def process_reports(
    files: List[UploadFile] = File(...),
    uid: str = Form(...),
    user: dict = Depends(verify_token),
):
    """
    Stateless, in-memory PDF processing endpoint.
    Accepts up to 2 PDF files via multipart/form-data.
    No files are written to disk — everything is processed from memory.
    """
    print("\n" + "="*50)
    print(f"🚀 INCOMING REQUEST: /api/process-reports for uid={uid}")
    print("="*50 + "\n")
    sys.stdout.flush()

    # ── Validation ───────────────────────────────────────────────────────────
    if len(files) == 0:
        raise HTTPException(status_code=422, detail="נדרש לפחות קובץ PDF אחד.")
    if len(files) > 2:
        raise HTTPException(status_code=422, detail="ניתן להעלות לכל היותר 2 קבצי PDF.")
    for f in files:
        filename_lower = (f.filename or "").lower()
        content_type = (f.content_type or "")
        if not filename_lower.endswith(".pdf") and "pdf" not in content_type:
            raise HTTPException(status_code=422, detail=f"הקובץ '{f.filename}' אינו קובץ PDF.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # ── Fetch family profile from Firestore ───────────────────────────────────
    family_profile = db_manager.get_family_profile(uid)
    f_profile: dict = {}
    all_target_strings: list[str] = []

    if family_profile:
        print(f"✅ [APP] Family profile found for {uid}")
        f_pii = family_profile.get("pii_data", {})
        f_profile = family_profile.get("financial_profile", {})
        for m_key in ["member1", "member2"]:
            m_data = f_pii.get(m_key)
            if m_data:
                name   = m_data.get("name", "")
                last   = m_data.get("lastName", "")
                id_num = m_data.get("idNumber", "")
                email  = m_data.get("email", "")
                all_target_strings.extend([name, last, id_num, email])
                if id_num and id_num.startswith("0"):
                    all_target_strings.append(id_num[1:])
    else:
        print(f"⚠️ [APP] No family profile found for {uid}. PII redaction will be minimal.")

    all_target_strings = list(set([s for s in all_target_strings if s and len(s.strip()) > 2]))
    print(f"DEBUG: Total redaction strings: {len(all_target_strings)}")

    # Initialise a clean portfolio accumulator (user + spouse), so results from
    # multiple uploads merge correctly and don't bleed into MOCK_DATA.
    accumulated_portfolios: dict = {
        "user":   {"funds": []},
        "spouse": {"funds": []},
    }

    results = []

    # ── Process each uploaded file ────────────────────────────────────────────
    for upload_file in files:
        filename = upload_file.filename or "unknown.pdf"
        print(f"\n📄 [APP] Processing uploaded file: {filename}")

        try:
            pdf_bytes = await upload_file.read()

            # Open entirely from memory — zero disk I/O
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # ── Owner detection ───────────────────────────────────────────────
            detected_owner = "unknown"
            if doc.is_encrypted:
                print(f"DEBUG: {filename} is encrypted — trying ID passwords…")
                authenticated = False
                if family_profile:
                    for m_key in ["member1", "member2"]:
                        m_id = family_profile.get("pii_data", {}).get(m_key, {}).get("idNumber")
                        if m_id and doc.authenticate(m_id):
                            authenticated = True
                            detected_owner = "member_1" if m_key == "member1" else "member_2"
                            print(f"✅ Authenticated via Firestore {m_key} ID.")
                            break
                if not authenticated:
                    print(f"❌ [APP] Could not authenticate {filename}")
                    results.append({"filename": filename, "error": "PDF מוגן בסיסמה ואף ת.ז. לא עבדה."})
                    doc.close()
                    continue
            else:
                # Count PII hits per member to guess owner
                match_counts: dict[str, int] = {"member_1": 0, "member_2": 0}
                if family_profile:
                    for page in doc:
                        text = page.get_text().lower()
                        for m_key in ["member1", "member2"]:
                            m_pii  = family_profile.get("pii_data", {}).get(m_key, {})
                            label  = "member_1" if m_key == "member1" else "member_2"
                            if m_pii.get("name") and m_pii["name"].lower().strip() in text:
                                match_counts[label] += 1
                            if m_pii.get("idNumber") and m_pii["idNumber"].strip() in text:
                                match_counts[label] += 1
                if match_counts["member_1"] > match_counts["member_2"]:
                    detected_owner = "member_1"
                elif match_counts["member_2"] > match_counts["member_1"]:
                    detected_owner = "member_2"
                print(f"DEBUG: Detected owner={detected_owner} (matches={match_counts})")

            # ── Redact & render pages to base64 PNG ──────────────────────────
            redacted_images_b64: list[str] = []
            start_page = 3 if len(doc) > 3 else 0

            for page_num in range(start_page, len(doc)):
                page = doc[page_num]
                for text in all_target_strings:
                    for inst in page.search_for(text):
                        page.draw_rect(inst, color=(0, 0, 0), fill=(0, 0, 0))
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                redacted_images_b64.append(base64.b64encode(img_data).decode("utf-8"))

            doc.close()
            print(f"✅ Redacted {len(redacted_images_b64)} pages for {filename}")

            if not api_key:
                print("DEBUG: No API key — skipping AI extraction.")
                results.append({"filename": filename, "status": "preview_only"})
                continue

            # ── Anthropic Vision extraction ───────────────────────────────────
            print(f"🧠 [APP] Sending redacted images to Claude for {filename}…")
            anthropic_client = Anthropic(api_key=api_key)

            extraction_system_prompt = """
אתה מומחה לחילוץ נתונים פיננסיים מדוחות פנסיה ישראליים.
חלץ את כל המוצרים הפיננסיים מהדוח והחזר JSON תקני בלבד.
המבנה חייב להיות:
{
  "products": [
    {
      "product_type": "string (סוג המוצר בעברית: פנסיה/ביטוח מנהלים/קרן השתלמות/קופת גמל/גמל להשקעה)",
      "provider_name": "string (שם חברת הביטוח/בית ההשקעות)",
      "track_name": "string (שם המסלול)",
      "policy_number": "string",
      "balance": number,
      "monthly_deposit": number,
      "management_fee_deposit": number,
      "management_fee_accumulation": number,
      "yield_1yr": number,
      "yield_3yr": number,
      "yield_5yr": number
    }
  ]
}

CRITICAL:
- החזר JSON תקני בלבד ללא markdown, ללא הסברים
- השתמש במרכאות כפולות לכל מחרוזות
- אל תכניס מרכאות לתוך ערכי מחרוזות (השתמש ב-slash או הסר)
- כל הערכים המספריים ללא פסיקים (1234567 ולא 1,234,567)
- אם שדה לא קיים, השתמש ב-0 עבור מספרים ו-"" עבור מחרוזות
"""

            content_blocks: list[dict] = []
            for b64 in redacted_images_b64[:10]:
                content_blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                })
            content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})

            response = anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=extraction_system_prompt,
                messages=[{"role": "user", "content": content_blocks}],
            )

            response_text = response.content[0].text.strip()

            # Robust JSON parsing
            import re as _re
            response_text = _re.sub(r'^```(?:json)?\s*', '', response_text, flags=_re.MULTILINE)
            response_text = _re.sub(r'```\s*$', '', response_text, flags=_re.MULTILINE).strip()

            start_idx = response_text.find('{')
            if start_idx == -1:
                raise ValueError(f"No JSON in Anthropic response: {response_text[:200]}")
            try:
                pension_data, _ = json.JSONDecoder().raw_decode(response_text, start_idx)
            except json.JSONDecodeError:
                brace_count = 0
                end_idx = start_idx
                for i, ch in enumerate(response_text[start_idx:], start_idx):
                    if ch == '{': brace_count += 1
                    elif ch == '}': brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
                pension_data = json.loads(response_text[start_idx:end_idx])

            print(f"✅ [APP] Extracted {len(pension_data.get('products', []))} products from {filename}")

            # ── Map products → fund schema ────────────────────────────────────
            owner_key = "user" if detected_owner == "member_1" else "spouse"
            for p in pension_data.get("products", []):
                raw_type = p.get("product_type", "")
                if "פנסיה" in raw_type:            category = "pension"
                elif "מנהלים" in raw_type:         category = "managers"
                elif "השתלמות" in raw_type:        category = "study"
                elif "גמל להשקעה" in raw_type:     category = "investment_provident"
                elif "גמל" in raw_type:            category = "provident"
                else:                              category = "provident"

                accumulated_portfolios[owner_key]["funds"].append({
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

            results.append({"filename": filename, "status": "success", "products_found": len(pension_data.get("products", []))})

        except Exception as e:
            print(f"💥 [APP] Error processing {filename}: {e}")
            results.append({"filename": filename, "error": str(e)})

    # ── Generate action items if any funds were extracted ─────────────────────
    total_funds = sum(len(accumulated_portfolios[k]["funds"]) for k in ["user", "spouse"])

    if total_funds > 0:
        print(f"\n🤖 [APP] Generating action items ({total_funds} funds)…")
        live_market_data = await _collect_market_data_async(accumulated_portfolios)
        action_items = ai_advisor.generate_action_items(
            family_portfolio=accumulated_portfolios,
            market_data=live_market_data,
            financial_profile=f_profile,
        )
    else:
        print("\n⚠️ [APP] No funds extracted — skipping action items.")
        action_items = []

    # ── Persist to Firestore ──────────────────────────────────────────────────
    now = datetime.datetime.now().isoformat()
    final_json = {
        "uid": uid,
        "last_updated": now,
        "portfolios": accumulated_portfolios,
        "action_items": action_items,
    }

    print("\n☁️ [APP] Saving to Firestore…")
    db_manager.save_processed_portfolio(uid, final_json)

    print(f"\n🏁 [APP] /api/process-reports COMPLETE for {uid}.")
    return {
        "status": "success",
        "processed_count": len([r for r in results if not r.get("error")]),
        "results": results,
        "final_data": final_json,
    }



@app.post("/api/test-reprocess-advisory")
def test_reprocess_advisory(user: dict = Depends(verify_token)):
    """
    Temporary tool: Reprocess AI Advisor using already saved Firestore data.
    Saves costs by skipping Vision extraction.
    """
    uid = user.get("uid")
    print(f"\n🧪 [APP] Testing Advisory Reprocess for {uid}...")
    
    # 1. Fetch existing portfolio (with extracted funds)
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        print(f"❌ [APP] No existing portfolio doc found in Firestore portfolios collection for {uid}.")
        raise HTTPException(status_code=404, detail="No portfolio found in Firestore to reprocess.")
    
    # 2. Fetch family profile (for context/ages)
    family_profile = db_manager.get_family_profile(uid)
    f_profile = family_profile.get("financial_profile", {}) if family_profile else {}
    
    # 3. Fetch live competitor benchmarks, then re-run AI Advisor
    print("📊 [APP] Fetching live market data for reprocess...")
    saved_portfolios = portfolio_doc.get("portfolios", {})
    live_market_data = _collect_market_data(saved_portfolios)
    print("🤖 [APP] Re-generating action items from saved portfolio...")
    action_items = ai_advisor.generate_action_items(
        family_portfolio=saved_portfolios,
        market_data=live_market_data,
        financial_profile=f_profile
    )
    
    # 4. Consolidate and Save
    portfolio_doc["action_items"] = action_items
    portfolio_doc["last_updated"] = datetime.datetime.now().isoformat()
    
    print("☁️ [APP] Saving updated results back to Firestore...")
    db_manager.save_processed_portfolio(uid, portfolio_doc)
    
    # Update in-memory MOCK_DATA for current session consistency
    MOCK_DATA["action_items"] = action_items
    MOCK_DATA["portfolios"] = portfolio_doc.get("portfolios", {})
    
    return {"status": "success", "message": "Advisories reprocessed from Firestore data", "action_items_count": len(action_items)}


# ── Gmail Fetcher Helpers ─────────────────────────────────────────────────────


def _get_gmail_service(refresh_token: str):
    """Build a stateless Gmail API service using a user refresh token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_or_create_label(service, label_name: str) -> str:
    """Return the Gmail label ID for label_name, creating it if it doesn't exist."""
    labels_response = service.users().labels().list(userId="me").execute()
    for label in labels_response.get("labels", []):
        if label.get("name") == label_name:
            return label["id"]
    # Create label
    created = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    print(f"✅ [GMAIL] Created label '{label_name}' (id={created['id']})")
    return created["id"]


def _extract_pdf_url(html_body: str, text_body: str) -> str | None:
    """Extract a surense.com download URL from an email body."""
    import re as _re
    pattern = r"https://(?:u|api)\.surense\.com/[^\s\"'<>]+"
    for body in (html_body, text_body):
        if not body:
            continue
        match = _re.search(pattern, body)
        if match:
            return match.group(0)
    return None


# ── /api/cron/fetch-emails endpoint ──────────────────────────────────────────

@app.post("/api/cron/fetch-emails")
async def fetch_emails_from_gmail(request: Request):
    """
    Stateless cron endpoint.
    Searches Gmail for unprocessed pension reports, downloads + processes each
    PDF, and persists the results to Firestore.
    Secured via X-Cron-Secret header.
    """
    import base64 as _base64
    import re as _re
    import httpx as _httpx

    # ── 1. Auth ───────────────────────────────────────────────────────────────
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    body = await request.json()
    uid: str = body.get("uid", "").strip()
    if not uid:
        raise HTTPException(status_code=422, detail="uid is required in request body")

    print(f"\n{'='*50}")
    print(f"📧 [CRON] fetch-emails for uid={uid}")
    print(f"{'='*50}\n")
    sys.stdout.flush()

    # ── 2. Fetch family profile ───────────────────────────────────────────────
    family_profile = db_manager.get_family_profile(uid)
    if not family_profile:
        raise HTTPException(status_code=404, detail=f"No family profile found for uid={uid}")

    refresh_token: str | None = family_profile.get("gmail_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No gmail_refresh_token in family profile")

    member_id_numbers: list[str] = family_profile.get("member_id_numbers", [])
    f_profile: dict = family_profile.get("financial_profile", {})

    # Build PII redaction strings from all known members
    all_target_strings: list[str] = list(member_id_numbers)
    pii_data = family_profile.get("pii_data", {})
    for m_key in ["member1", "member2"]:
        m = pii_data.get(m_key, {})
        all_target_strings.extend([m.get("name", ""), m.get("lastName", ""), m.get("email", "")])
    all_target_strings = list(set([s for s in all_target_strings if s and len(s.strip()) > 2]))

    # ── 3. Build Gmail service ────────────────────────────────────────────────
    try:
        service = _get_gmail_service(refresh_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Gmail authentication failed: {e}")

    # ── 4. Search for unprocessed emails ──────────────────────────────────────
    query = 'from:no-reply@surense.com subject:"דוח מצב ביטוח ופנסיה" -label:AI_PROCESSED'
    try:
        search_result = service.users().messages().list(userId="me", q=query).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail search failed: {e}")

    messages = search_result.get("messages", [])
    print(f"📬 [CRON] Found {len(messages)} unprocessed message(s).")
    if not messages:
        return {"status": "success", "processed": 0, "results": [], "message": "No new emails found"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    accumulated_portfolios: dict = {
        "user":   {"funds": []},
        "spouse": {"funds": []},
    }
    results = []

    # ── 5. Process each email ─────────────────────────────────────────────────
    for msg_stub in messages:
        msg_id = msg_stub["id"]
        print(f"\n📄 [CRON] Processing message id={msg_id}")
        try:
            # Fetch full message
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            # Decode body parts
            html_body = ""
            text_body = ""
            payload = msg.get("payload", {})

            def _decode_part(part: dict) -> str:
                data = part.get("body", {}).get("data", "")
                if data:
                    return _base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                return ""

            def _walk_parts(payload: dict):
                nonlocal html_body, text_body
                mime = payload.get("mimeType", "")
                if mime == "text/html":
                    html_body += _decode_part(payload)
                elif mime == "text/plain":
                    text_body += _decode_part(payload)
                for sub in payload.get("parts", []):
                    _walk_parts(sub)

            _walk_parts(payload)

            # Extract download URL
            pdf_url = _extract_pdf_url(html_body, text_body)
            if not pdf_url:
                print(f"⚠️ [CRON] No download URL found in message {msg_id} — skipping.")
                results.append({"msg_id": msg_id, "status": "skipped", "reason": "no_url"})
                continue

            print(f"🔗 [CRON] Download URL: {pdf_url}")

            # Download PDF
            async with _httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                response = await client.get(pdf_url)
                if response.status_code != 200:
                    print(f"❌ [CRON] Download failed ({response.status_code}) for {pdf_url}")
                    results.append({"msg_id": msg_id, "status": "skipped", "reason": f"download_http_{response.status_code}"})
                    continue
                pdf_bytes = response.content

            print(f"✅ [CRON] Downloaded {len(pdf_bytes):,} bytes")

            # Open PDF from memory
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Decrypt with any known member ID
            detected_owner = "user"
            if doc.is_encrypted:
                authenticated = False
                for id_num in member_id_numbers:
                    if doc.authenticate(id_num):
                        authenticated = True
                        # Guess owner (first ID → user, second → spouse)
                        idx = member_id_numbers.index(id_num)
                        detected_owner = "user" if idx == 0 else "spouse"
                        print(f"✅ [CRON] PDF decrypted using member ID index {idx}")
                        break
                if not authenticated:
                    print(f"❌ [CRON] Could not decrypt PDF for message {msg_id}")
                    results.append({"msg_id": msg_id, "status": "skipped", "reason": "decryption_failed"})
                    doc.close()
                    continue

            # Redact PII and render pages to base64 PNG
            redacted_images_b64: list[str] = []
            start_page = 3 if len(doc) > 3 else 0
            for page_num in range(start_page, len(doc)):
                page = doc[page_num]
                for txt in all_target_strings:
                    for inst in page.search_for(txt):
                        page.draw_rect(inst, color=(0, 0, 0), fill=(0, 0, 0))
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                redacted_images_b64.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
            doc.close()
            print(f"✅ [CRON] Redacted {len(redacted_images_b64)} page(s)")

            if not api_key:
                results.append({"msg_id": msg_id, "status": "preview_only", "reason": "no_anthropic_key"})
                continue

            # ── Anthropic Vision extraction ───────────────────────────────────
            print(f"🧠 [CRON] Sending to Claude Vision...")
            anthropic_client = Anthropic(api_key=api_key)
            extraction_system_prompt = """
אתה מומחה לחילוץ נתונים פיננסיים מדוחות פנסיה ישראליים.
חלץ את כל המוצרים הפיננסיים מהדוח והחזר JSON תקני בלבד.
המבנה חייב להיות:
{
  "products": [
    {
      "product_type": "string (סוג המוצר בעברית: פנסיה/ביטוח מנהלים/קרן השתלמות/קופת גמל/גמל להשקעה)",
      "provider_name": "string (שם חברת הביטוח/בית ההשקעות)",
      "track_name": "string (שם המסלול)",
      "policy_number": "string",
      "balance": number,
      "monthly_deposit": number,
      "management_fee_deposit": number,
      "management_fee_accumulation": number,
      "yield_1yr": number,
      "yield_3yr": number,
      "yield_5yr": number
    }
  ]
}

CRITICAL:
- החזר JSON תקני בלבד ללא markdown, ללא הסברים
- כל הערכים המספריים ללא פסיקים
- אם שדה לא קיים, השתמש ב-0 עבור מספרים ו-"" עבור מחרוזות
"""
            content_blocks: list[dict] = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}
                for b64 in redacted_images_b64[:10]
            ]
            content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})

            ai_response = anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=extraction_system_prompt,
                messages=[{"role": "user", "content": content_blocks}],
            )
            response_text = ai_response.content[0].text.strip()
            response_text = _re.sub(r'^```(?:json)?\s*', '', response_text, flags=_re.MULTILINE)
            response_text = _re.sub(r'```\s*$', '', response_text, flags=_re.MULTILINE).strip()

            start_idx = response_text.find('{')
            if start_idx == -1:
                raise ValueError(f"No JSON in response: {response_text[:200]}")
            try:
                pension_data, _ = json.JSONDecoder().raw_decode(response_text, start_idx)
            except json.JSONDecodeError:
                brace_count = 0
                end_idx = start_idx
                for i, ch in enumerate(response_text[start_idx:], start_idx):
                    if ch == '{': brace_count += 1
                    elif ch == '}': brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
                pension_data = json.loads(response_text[start_idx:end_idx])

            products = pension_data.get("products", [])
            print(f"✅ [CRON] Extracted {len(products)} product(s)")

            # Map products → fund schema
            for p in products:
                raw_type = p.get("product_type", "")
                if "פנסיה" in raw_type:              category = "pension"
                elif "מנהלים" in raw_type:           category = "managers"
                elif "השתלמות" in raw_type:          category = "study"
                elif "גמל להשקעה" in raw_type:       category = "investment_provident"
                elif "גמל" in raw_type:              category = "provident"
                else:                                category = "provident"

                accumulated_portfolios[detected_owner]["funds"].append({
                    "id": f"gmail_{msg_id}_{os.urandom(2).hex()}",
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

            # ── Apply AI_PROCESSED label ──────────────────────────────────────
            label_id = _get_or_create_label(service, "AI_PROCESSED")
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"addLabelIds": [label_id]},
            ).execute()
            print(f"🏷️ [CRON] Labeled message {msg_id} as AI_PROCESSED")
            results.append({"msg_id": msg_id, "status": "success", "products_found": len(products)})

        except Exception as e:
            print(f"💥 [CRON] Error processing message {msg_id}: {e}")
            results.append({"msg_id": msg_id, "status": "error", "reason": str(e)})

    # ── 6. Generate action items & persist ────────────────────────────────────
    total_funds = sum(len(accumulated_portfolios[k]["funds"]) for k in ["user", "spouse"])

    if total_funds > 0:
        print(f"\n🤖 [CRON] Generating action items ({total_funds} funds)…")
        live_market_data = await _collect_market_data_async(accumulated_portfolios)
        action_items = ai_advisor.generate_action_items(
            family_portfolio=accumulated_portfolios,
            market_data=live_market_data,
            financial_profile=f_profile,
        )
    else:
        print("\n⚠️ [CRON] No funds extracted — skipping action items.")
        action_items = []

    now = datetime.datetime.now().isoformat()
    final_json = {
        "uid": uid,
        "last_updated": now,
        "portfolios": accumulated_portfolios,
        "action_items": action_items,
    }

    print("\n☁️ [CRON] Saving to Firestore…")
    db_manager.save_processed_portfolio(uid, final_json)

    processed_count = len([r for r in results if r.get("status") == "success"])
    print(f"\n🏁 [CRON] fetch-emails COMPLETE — {processed_count}/{len(messages)} processed.")
    return {
        "status": "success",
        "processed": processed_count,
        "total_found": len(messages),
        "results": results,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
