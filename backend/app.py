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

# --- LOG REDIRECTION TO FILE ---
# This ensures that all 'print' statements and errors are written to app.log
# which I can read here, while still showing in your terminal.
class Logger(object):
    def __init__(self, file_path, original_stream):
        self.terminal = original_stream
        self.log = open(file_path, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
        self.terminal.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Define the log path in the backend directory
log_file_path = os.path.join(os.path.dirname(__file__), "app.log")
sys.stdout = Logger(log_file_path, sys.stdout)
sys.stderr = Logger(log_file_path, sys.stderr)
# -------------------------------

# Try loading from current dir, then from parent dir (project root)
if not load_dotenv():
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

print(f"ANTHROPIC_API_KEY loaded: {'Yes (starts with ' + os.environ.get('ANTHROPIC_API_KEY')[:10] + '...)' if os.environ.get('ANTHROPIC_API_KEY') else 'No'}")
sys.stdout.flush()

import asyncio
import difflib

from mock_data import MOCK_DATA
import db_manager
import ai_advisor
import market_data as market_data_module

def _get_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()

def _is_index_mismatch(pdf_name: str, api_name: str) -> bool:
    """Returns True if the API fund is an index tracker but the PDF fund is not."""
    is_api_index = any(word in api_name for word in ["עוקב", "מדד", "S&P", "500", "s&p"])
    is_pdf_index = any(word in pdf_name for word in ["עוקב", "מדד", "S&P", "500", "s&p"])
    return is_api_index and not is_pdf_index

def _parse_float(val) -> float:
    """Convert a value to float, stripping %, commas, and whitespace."""
    try:
        return float(str(val).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return 0.0


PDF_SKIP_PAGES = 1

def _redact_and_render_pdf(doc, target_strings: list[str]) -> list[str]:
    """
    Redact PII (target_strings) from a PDF document and render remaining pages as Base64 PNGs.
    Skips the first PDF_SKIP_PAGES pages if the document is long enough.
    Closes the document before returning.
    """
    import base64 as _base64
    import fitz as _fitz
    
    redacted_images_b64 = []
    start_page = PDF_SKIP_PAGES if len(doc) > PDF_SKIP_PAGES else 0

    for page_num in range(start_page, len(doc)):
        page = doc[page_num]
        if target_strings:
            for text in target_strings:
                if not text or len(text.strip()) < 2:
                    continue
                for inst in page.search_for(text):
                    page.draw_rect(inst, color=(0, 0, 0), fill=(0, 0, 0))
        
        mat = _fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        redacted_images_b64.append(_base64.b64encode(img_data).decode("utf-8"))

    doc.close()
    return redacted_images_b64


def _extract_funds_via_ai(redacted_images_b64: list[str], api_key: str, source_id_prefix: str) -> list[dict]:
    """
    Sends redacted images to Claude Vision, parses the JSON response,
    and maps the products to the expected fund_data schema.
    """
    import json
    import os
    import re

    print("🧠 [APP] Sending redacted images to Claude for extraction...")
    anthropic_client = Anthropic(api_key=api_key)
    
    content_blocks = []
    for b64 in redacted_images_b64[:10]:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

    response_text = response.content[0].text.strip()

    # Robust JSON parsing
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
    response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE).strip()

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

    products = pension_data.get("products", [])
    print(f"✅ [APP] AI Extraction SUCCESS. Found {len(products)} products.")
    
    extracted_funds = []
    
    for p in products:
        raw_type = p.get("product_type", "")
        if "פנסיה" in raw_type:            category = "pension"
        elif "מנהלים" in raw_type:         category = "managers"
        elif "השתלמות" in raw_type:        category = "study"
        elif "גמל להשקעה" in raw_type:     category = "investment_provident"
        elif "גמל" in raw_type:            category = "provident"
        else:                              category = "provident"

        fund_data = {
            "id": f"{source_id_prefix}_{os.urandom(2).hex()}",
            "category": category,
            "provider_name": p.get("provider_name", "Unknown"),
            "track_name": p.get("track_name", "Unknown"),
            "track_id": p.get("track_id", ""),
            "status": "active",
            "balance": p.get("balance", 0),
            "monthly_deposit": p.get("monthly_deposit", 0),
            "management_fee_deposit": p.get("management_fee_deposit", 0),
            "management_fee_accumulation": p.get("management_fee_accumulation", 0),
            "yield_1yr": p.get("yield_1yr", 0),
            "yield_3yr": p.get("yield_3yr_cumulative", p.get("yield_3yr", 0)),
            "yield_5yr": p.get("yield_5yr_cumulative", p.get("yield_5yr", 0)),
            "sharpe_ratio": p.get("sharpe_ratio", 0),
            "policy_number": p.get("policy_number", ""),
        }
        
        # Clean float values and apply anti-hallucination correction
        fund_data["yield_1yr"] = _parse_float(fund_data["yield_1yr"])
        fund_data["yield_3yr"] = _parse_float(fund_data["yield_3yr"])
        fund_data["yield_5yr"] = _parse_float(fund_data["yield_5yr"])
        
        y3 = fund_data["yield_3yr"]
        y5 = fund_data["yield_5yr"]
        y5_ann = _parse_float(p.get("yield_5yr_annualized", 0))
        
        if y5 == 0 and y5_ann > 0:
            fund_data["yield_5yr"] = round(((1 + (y5_ann / 100.0)) ** 5 - 1) * 100, 2)
            print(f"🤖 [APP] Converted 5Y annualized ({y5_ann}%) → cumulative ({fund_data['yield_5yr']}%) for {fund_data['track_name']}")
        elif y3 > 0 and 0 < y5 < y3 * 0.4:
            y5_cumulative = round(((1 + (y5 / 100.0)) ** 5 - 1) * 100, 2)
            print(f"🤖 [APP] Anti-Hallucination: 5Y ({y5}%) << 3Y ({y3}%), likely annualized. Converting → {y5_cumulative}% for {fund_data['track_name']}")
            fund_data["yield_5yr"] = y5_cumulative

        extracted_funds.append(fund_data)

    return extracted_funds

EXTRACTION_SYSTEM_PROMPT = """
אתה מומחה לחילוץ נתונים פיננסיים מדוחות פנסיה ישראליים.
חלץ את כל המוצרים הפיננסיים מהדוח והחזר JSON תקני בלבד.
שים לב: דוח יחיד יכול להכיל מס' מוצרים שונים. למשל, ב"ביטוח מנהלים" תחת אותה פוליסה יכולים להיות מספר מסלולים, או ב"קרן השתלמות" מספר חשבונות נפרדים. חלץ אותם כמוצרים נפרדים במערך "products".

המבנה חייב להיות:
{
  "products": [
    {
      "product_type": "string (סוג המוצר בעברית: פנסיה/ביטוח מנהלים/קרן השתלמות/קופת גמל/גמל להשקעה)",
      "provider_name": "string (שם חברת הביטוח/בית ההשקעות)",
      "track_name": "string (שם המסלול)",
      "track_id": "string (קוד מסלול / מספר אישור משרד האוצר - חלץ במידה וקיים בדוח, אחרת השאר מחרוזת ריקה)",
      "policy_number": "string",
      "balance": number, # סך צבירה (Total Balance)
      "monthly_deposit": number, # הפקדה חודשית (Monthly Deposit)
      "management_fee_deposit": number,
      "management_fee_accumulation": number,
      "yield_1yr": number, # תשואה ל-12 חודשים האחרונים
      "yield_3yr_cumulative": number, # תשואה מצטברת (Cumulative) ל-3 שנים
      "yield_3yr_annualized": number, # תשואה שנתית ממוצעת (Average Annual) ל-3 שנים
      "yield_5yr_cumulative": number, # תשואה מצטברת (Cumulative) ל-5 שנים
      "yield_5yr_annualized": number, # תשואה שנתית ממוצעת (Average Annual) ל-5 שנים
      "sharpe_ratio": number # מדד שארפ (Sharpe Ratio)
    }
  ]
}

הנחיות קריטיות - קרא בעיון:
1. הפקדות (monthly_deposit):
   - חלץ אך ורק *הפקדה חודשית ממוצעת או אחרונה* (למשל 1,500 ₪). 
   - סכנה: דוחות רבים מציגים "סך הפקדות בשנת הדיווח" או "הפקדות שוטפות" שהם בסכומים גבוהים מאוד (למשל 47,000 ₪). לעולם אל תחלץ סכומים שנתיים מצטברים אלו לתוך monthly_deposit! אם לא כתוב במפורש מה ההפקדה החודשית, השאר את field זה כ-0.
2. תשואות (Yields):
   - קיימים שני מונחים: "תשואה מצטברת" (Cumulative, לרוב מספר גבוה כמו 50%+) ו"תשואה שנתית ממוצעת" (Annualized, לרוב מספר נמוך כמו 10%).
   - הקפד לשים כל נתון בשדה המתאים (cumulative מול annualized).
   - חלץ בדיוק את המספר שמופיע בדוח בעמודה המתאימה ל-3 ול-5 שנים. אין להמציא ערכים.
3. מדד שארפ: חלץ את הערך המופיע בדוח. אם לא מופיע, החזר 0.

CRITICAL FORMATTING:
- החזר JSON תקני בלבד ללא בלוקים של markdown (ללא ```json) וללא כל טקסט חופשי.
- אל תכניס פסיקים או פסיק עליון במספרים (החזר 1234.56 במקום 1,234.56).
- אם שדה כלשהו לא מופיע בדוח, יש להחזיר 0 עבור מספרים ו-"" עבור מחרוזות. אל תשמיט שדות ממבנה ה-JSON הנדרש.
"""

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


def _attach_competitors_to_funds(portfolios: dict, market_data: dict) -> None:
    """
    Attach top_competitors list to each fund based on its track_name.
    This ensures that when the frontend opens a product's details,
    the competitor benchmarks are already embedded in the fund object.
    """
    if not market_data:
        return

    print("🔗 [APP] Attaching competitor data to individual funds...")
    for owner_key in ["user", "spouse"]:
        funds = portfolios.get(owner_key, {}).get("funds", [])
        for fund in funds:
            track = fund.get("track_name")
            if track and track in market_data:
                track_data = market_data[track]
                fund["top_competitors"] = track_data.get("top_competitors", [])
                
                user_provider = fund.get("provider_name", "").strip()
                track_id = str(fund.get("track_id", "") or "").strip()
                track_name_for_match = track or user_provider
                match = None
                best_score = 0
                
                for comp in track_data.get("all_competitors", []):
                    comp_provider = comp.get("provider_name", "")
                    comp_name = comp.get("fund_name", "")
                    comp_id = str(comp.get("fund_id", "") or "").strip()
                    
                    # 0. EXACT TRACK ID MATCH (Ultimate Safety)
                    if track_id and comp_id and track_id == comp_id:
                        match = comp
                        break
                    
                    # 1. Broadest check: Must share at least the first significant word of provider_name
                    if user_provider and comp_provider:
                        p1 = user_provider.split(" ")[0].replace('"', '')
                        p2 = comp_provider.split(" ")[0].replace('"', '')
                        p_match = p1 == p2 or user_provider in comp_provider or comp_provider in user_provider
                        if not p_match:
                            continue
                            
                    # 2. Strong filter: Prevent matching active funds with index trackers
                    if _is_index_mismatch(track_name_for_match, comp_name):
                        continue
                        
                    # 3. Calculate sequence similarity between PDF track_name and API fund_name
                    score = _get_similarity(track_name_for_match, comp_name)
                    if score > best_score:
                        best_score = score
                        match = comp
                
                # Minimum acceptable similarity boundary (only applies if we didn't do an exact Track ID match)
                is_exact_match = (match and track_id and str(match.get("fund_id", "")) == track_id)
                if match and not is_exact_match and best_score < 0.3:
                    print(f"⚠️ [APP] Best match for '{user_provider} - {track}' Score {best_score} too low. Discarding.")
                    match = None

                        
                if match:
                    match_method = 'Track ID' if is_exact_match else f'Fuzzy String (Score {best_score:.2f})'
                    print(f"🔄 [APP] Matched '{user_provider} - {track}' via {match_method}. Injecting missing Sharpe Ratio.")
                    # TRUST THE PDF YIELDS: By user request, we DO NOT override the 1Y/3Y/5Y metrics.
                    fund["sharpe_ratio"] = match.get("sharpe_ratio", fund.get("sharpe_ratio"))


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

from routers import dashboard_chat
app.include_router(dashboard_chat.router)

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

from auth import verify_token, security
@app.get("/api/portfolio")
async def get_portfolio(
    refresh_market: bool = False,
    refresh_ai: bool = False,
    user: dict = Depends(verify_token)
):
    uid = user.get("uid")
    print(f"🔍 [APP] GET /api/portfolio - Fetching for {uid} (refresh_market={refresh_market}, refresh_ai={refresh_ai})")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    
    if portfolio_doc:
        portfolios = portfolio_doc.get("portfolios", {})
        action_items = portfolio_doc.get("action_items", [])
        last_updated = portfolio_doc.get("last_updated")
        
        needs_save = False
        
        # 1. Explicit AI Refresh
        if refresh_ai:
            print(f"🤖 [APP] Explicit AI refresh requested for {uid}")
            family_profile = db_manager.get_family_profile(uid)
            f_profile = family_profile.get("financial_profile", {}) if family_profile else {}
            
            # AI always needs fresh market context to be accurate
            live_market_data = await _collect_market_data_async(portfolios)
            _attach_competitors_to_funds(portfolios, live_market_data)
            
            action_items = ai_advisor.generate_action_items(
                family_portfolio=portfolios,
                market_data=live_market_data,
                financial_profile=f_profile
            )
            portfolio_doc["action_items"] = action_items
            last_updated = datetime.datetime.now().isoformat()
            portfolio_doc["last_updated"] = last_updated
            needs_save = True

        # 2. Explicit Market Refresh (if AI refresh wasn't already doing it)
        elif refresh_market:
            print(f"📊 [APP] Explicit market data refresh requested for {uid}")
            live_market_data = await _collect_market_data_async(portfolios)
            _attach_competitors_to_funds(portfolios, live_market_data)
            needs_save = True

        if needs_save:
            print(f"☁️ [APP] Saving updated portfolio after refresh...")
            db_manager.save_processed_portfolio(uid, portfolio_doc)

        return {
            "last_updated": last_updated,
            "portfolios": portfolios,
            "action_items": action_items
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
            redacted_images_base64 = _redact_and_render_pdf(doc, all_target_strings)

            print(f"✅ Redacted {len(redacted_images_base64)} pages for {filename}")

            if not api_key or not pii_request.analyze:
                print(f"DEBUG: Skipping AI analysis (analyze={pii_request.analyze}, api_key={bool(api_key)})")
                # Return a sample of redacted images (first 3 pages) for preview
                preview_sample = redacted_images_base64[:3]
                results.append({"filename": filename, "status": "preview_only", "preview_images": preview_sample})
                continue

            # Step C: Extract portfolio data via Anthropic Vision
                y5 = fund_data["yield_5yr"]
                y5_ann = _parse_float(p.get("yield_5yr_annualized", 0))
                
                # Case 1: cumulative is 0 but annualized exists → convert
                if y5 == 0 and y5_ann > 0:
                    fund_data["yield_5yr"] = round(((1 + (y5_ann / 100.0)) ** 5 - 1) * 100, 2)
                    print(f"🤖 [APP] Converted 5Y annualized ({y5_ann}%) → cumulative ({fund_data['yield_5yr']}%) for {fund_data['track_name']}")
                # Case 2: 5Y is suspiciously low vs 3Y — likely annualized was put in cumulative field
                elif y3 > 0 and 0 < y5 < y3 * 0.4:
                    y5_cumulative = round(((1 + (y5 / 100.0)) ** 5 - 1) * 100, 2)
                    print(f"🤖 [APP] Anti-Hallucination: 5Y ({y5}%) << 3Y ({y3}%), likely annualized. Converting → {y5_cumulative}% for {fund_data['track_name']}")
                    fund_data["yield_5yr"] = y5_cumulative

                MOCK_DATA["portfolios"][owner_key]["funds"].append(fund_data)
            
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
        _attach_competitors_to_funds(MOCK_DATA["portfolios"], live_market_data)
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
            redacted_images_b64 = _redact_and_render_pdf(doc, all_target_strings)
            print(f"✅ Redacted {len(redacted_images_b64)} pages for {filename}")


            if not api_key:
                print("DEBUG: No API key — skipping AI extraction.")
                results.append({"filename": filename, "status": "preview_only"})
                continue

            # ── Anthropic Vision extraction ───────────────────────────────────
            extracted_funds = _extract_funds_via_ai(redacted_images_b64, api_key, f"ai_{filename}")

            owner_key = "user" if detected_owner == "member_1" else "spouse"
            accumulated_portfolios[owner_key]["funds"].extend(extracted_funds)

            results.append({"filename": filename, "status": "success", "products_found": len(extracted_funds)})

        except Exception as e:
            print(f"💥 [APP] Error processing {filename}: {e}")
            results.append({"filename": filename, "error": str(e)})

    # ── Generate action items if any funds were extracted ─────────────────────
    total_funds = sum(len(accumulated_portfolios[k]["funds"]) for k in ["user", "spouse"])

    if total_funds > 0:
        print(f"\n🤖 [APP] Generating action items ({total_funds} funds)…")
        live_market_data = await _collect_market_data_async(accumulated_portfolios)
        _attach_competitors_to_funds(accumulated_portfolios, live_market_data)
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
    _attach_competitors_to_funds(saved_portfolios, live_market_data)
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


# ── Gmail OAuth Endpoints ─────────────────────────────────────────────────────

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
GMAIL_REDIRECT_PATH = "/api/auth/gmail/callback"

def _build_oauth_url(uid: str, member_id: str) -> str:
    """Build the Google OAuth2 authorization URL for Gmail access."""
    from urllib.parse import urlencode
    client_id = os.environ["GOOGLE_CLIENT_ID"]
    base_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    redirect_uri = f"{base_url}{GMAIL_REDIRECT_PATH}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",   # ← gets refresh_token
        "prompt": "consent",        # ← force refresh_token even if previously granted
        "state": f"{uid}::{member_id}", # ← passed back verbatim so we know which family and member
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


@app.get("/api/auth/gmail/url")
async def get_gmail_auth_url(uid: str = None, member: str = "member1", credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Return the Google OAuth URL for Gmail authorization.
    Requires Firebase auth token in Authorization header.
    Query param: ?uid=<firebase-uid>  (defaults to the authenticated user's uid)
                 ?member=<member_id>  (defaults to member1)
    """
    import httpx as _httpx
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        requester_uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    target_uid = uid or requester_uid
    oauth_url = _build_oauth_url(target_uid, member)
    return {"url": oauth_url}


@app.get("/api/auth/gmail/callback")
async def gmail_oauth_callback(code: str = None, state: str = None, error: str = None):
    """
    Google redirects here after the user approves (or denies) Gmail access.
    Exchanges authorization code for refresh_token and saves it to Firestore.
    Then redirects the browser back to the frontend.
    """
    import httpx as _httpx
    from urllib.parse import urlencode
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")

    # User denied access
    if error or not code:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/settings?gmail=denied")

    uid_state = state  # we encoded uid::member_id in the state param
    if not uid_state:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/settings?gmail=error&reason=missing_state")

    parts = uid_state.split("::")
    uid = parts[0]
    member_id = parts[1] if len(parts) > 1 else "member1"

    # Exchange code for tokens
    base_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    redirect_uri = f"{base_url}{GMAIL_REDIRECT_PATH}"
    try:
        async with _httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": os.environ["GOOGLE_CLIENT_ID"],
                    "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_data = resp.json()
    except Exception as e:
        print(f"❌ [OAUTH] Token exchange failed: {e}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/settings?gmail=error&reason=token_exchange")

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        print(f"❌ [OAUTH] No refresh_token in response: {token_data}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{frontend_url}/settings?gmail=error&reason=no_refresh_token")

    # Save to Firestore
    saved = db_manager.save_gmail_token(uid, refresh_token)
    if saved:
        db_manager.update_family_field(uid, "gmail_connected_member", member_id)
    print(f"{'✅' if saved else '❌'} [OAUTH] Token save for uid={uid}: {'OK' if saved else 'FAILED'}")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{frontend_url}/settings?gmail={'connected' if saved else 'error'}")


class GmailSettingsPayload(BaseModel):
    gmail_sender_email: Optional[str] = None
    gmail_subject: Optional[str] = None
    cron_day: Optional[int] = None
    cron_frequency_months: Optional[int] = None


@app.put("/api/settings/gmail")
async def save_gmail_settings(
    payload: GmailSettingsPayload,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Save Gmail search settings and cron schedule for the authenticated family."""
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    updates: dict = {}
    if payload.gmail_sender_email is not None:
        updates["gmail_sender_email"] = payload.gmail_sender_email.strip()
    if payload.gmail_subject is not None:
        updates["gmail_subject"] = payload.gmail_subject.strip()
    if payload.cron_day is not None:
        updates["cron_day"] = max(1, min(30, payload.cron_day))
    if payload.cron_frequency_months is not None:
        updates["cron_frequency_months"] = max(1, min(12, payload.cron_frequency_months))

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    for field, value in updates.items():
        db_manager.update_family_field(uid, field, value)

    return {"status": "success", "updated": list(updates.keys())}


@app.get("/api/settings/gmail")
async def get_gmail_settings(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return the current Gmail settings + connection status for the authenticated family."""
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    profile = db_manager.get_family_profile(uid) or {}
    return {
        "gmail_connected": bool(profile.get("gmail_refresh_token")),
        "gmail_connected_member": profile.get("gmail_connected_member", "member1"),
        "gmail_sender_email": profile.get("gmail_sender_email", "no-reply@surense.com"),
        "gmail_subject": profile.get("gmail_subject", "דוח מצב ביטוח ופנסיה"),
        "cron_day": profile.get("cron_day", 1),
        "cron_frequency_months": profile.get("cron_frequency_months", 3),
        "last_fetched_at": profile.get("last_fetched_at"),
    }

@app.delete("/api/settings/gmail")
async def disconnect_gmail(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Removes the Gmail refresh token and associated member linkage."""
    from firebase_admin import firestore
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        db_manager.update_family_field(uid, "gmail_refresh_token", firestore.DELETE_FIELD)
        db_manager.update_family_field(uid, "gmail_connected_member", firestore.DELETE_FIELD)
        return {"status": "success", "message": "Gmail disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/gmail/scan")
async def trigger_manual_gmail_scan(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Manually trigger the Gmail scan for the authenticated user and process new reports."""
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    print(f"\n🚀 [APP] Manual Gmail scan triggered by user {uid}")
    result = await _process_family_emails(uid, bypass_schedule=True)
    return {"status": "success", "result": result}


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
async def fetch_emails_from_gmail(request: Request, uid: Optional[str] = None):
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

    # ── 2. Resolve target UIDs ────────────────────────────────────────────────
    # uid can come from query param (?uid=xxx). If omitted, process ALL families.
    target_uid = (uid or "").strip()
    if target_uid:
        uids_to_process = [target_uid]
    else:
        uids_to_process = db_manager.get_all_family_uids()
        if not uids_to_process:
            return {"status": "success", "message": "No families found in Firestore", "processed": 0}

    print(f"\n{'='*50}")
    print(f"📧 [CRON] fetch-emails — targeting {len(uids_to_process)} family/families")
    print(f"{'='*50}\n")
    sys.stdout.flush()

    all_results = []
    for current_uid in uids_to_process:
        result = await _process_family_emails(current_uid)
        all_results.append({"uid": current_uid, **result})

    total_processed = sum(r.get("processed", 0) for r in all_results)
    return {
        "status": "success",
        "families_processed": len(all_results),
        "total_emails_processed": total_processed,
        "results": all_results,
    }


async def _process_family_emails(uid: str, bypass_schedule: bool = False) -> dict:
    """Process all unread Gmail reports for a single family UID.
    
    Key behaviours:
    - Only the *latest* (newest) email per owner (user/spouse) is processed.
    - Older emails for the same owner are skipped but still labelled AI_PROCESSED.
    - If no new funds are extracted, existing Firestore data is NOT overwritten.
    """
    import base64 as _base64
    import re as _re
    import httpx as _httpx


    # ── 1. Fetch family profile ───────────────────────────────────────────────
    family_profile = db_manager.get_family_profile(uid)
    if not family_profile:
        print(f"⚠️ [CRON] No family profile for {uid} — skipping.")
        return {"processed": 0, "error": "no_family_profile"}

    refresh_token: str | None = family_profile.get("gmail_refresh_token")
    if not refresh_token:
        print(f"⚠️ [CRON] No gmail_refresh_token for {uid} — skipping.")
        return {"processed": 0, "error": "no_gmail_refresh_token"}

    member_id_numbers: list[str] = family_profile.get("member_id_numbers", [])
    f_profile: dict = family_profile.get("financial_profile", {})

    # Build PII redaction strings from all known members
    all_target_strings: list[str] = list(member_id_numbers)
    pii_data = family_profile.get("pii_data", {})
    for m_key in ["member1", "member2"]:
        m = pii_data.get(m_key, {})
        all_target_strings.extend([m.get("name", ""), m.get("lastName", ""), m.get("email", "")])
    all_target_strings = list(set([s for s in all_target_strings if s and len(s.strip()) > 2]))

    # ── 2. Schedule check ────────────────────────────────────────────────────
    from datetime import date as _date
    cron_day = int(family_profile.get("cron_day") or 1)
    cron_freq = int(family_profile.get("cron_frequency_months") or 3)
    last_fetched = family_profile.get("last_fetched_at")  # ISO string or None
    today = _date.today()

    if not bypass_schedule:
        if today.day != cron_day:
            print(f"⏭️  [CRON] Skipping {uid} — today is day {today.day}, scheduled for day {cron_day}.")
            return {"processed": 0, "skipped": f"not_scheduled_day (today={today.day}, scheduled={cron_day})"}

        if last_fetched:
            try:
                last_dt = _date.fromisoformat(str(last_fetched)[:10])
                months_passed = (today.year - last_dt.year) * 12 + (today.month - last_dt.month)
                if months_passed < cron_freq:
                    print(f"⏭️  [CRON] Skipping {uid} — only {months_passed}/{cron_freq} months since last run.")
                    return {"processed": 0, "skipped": f"too_soon ({months_passed}/{cron_freq} months)"}
            except Exception:
                pass  # bad date format — proceed anyway

    # ── 3. Build Gmail service ────────────────────────────────────────────────
    try:
        service = _get_gmail_service(refresh_token)
    except Exception as e:
        print(f"❌ [CRON] Gmail auth failed for {uid}: {e}")
        return {"processed": 0, "error": f"gmail_auth_failed: {e}"}

    # ── 4. Search for unprocessed emails ──────────────────────────────────────
    sender  = family_profile.get("gmail_sender_email") or "no-reply@surense.com"
    subject = family_profile.get("gmail_subject") or "דוח מצב ביטוח ופנסיה"
    query = f'from:{sender} subject:"{subject}" -label:AI_PROCESSED'
    print(f"🔍 [CRON] Gmail query: {query}")
    print(f"📧 [CRON] Sender filter: {sender} | Subject filter: {subject}")
    try:
        search_result = service.users().messages().list(userId="me", q=query).execute()
    except Exception as e:
        return {"processed": 0, "error": f"gmail_search_failed: {e}"}

    messages = search_result.get("messages", [])
    print(f"📬 [CRON] Found {len(messages)} unprocessed message(s).")
    if not messages:
        return {"status": "success", "processed": 0, "results": [], "message": "No new emails found"}

    # Get or create the AI_PROCESSED label once (used for all messages)
    label_id = _get_or_create_label(service, "AI_PROCESSED")

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    accumulated_portfolios: dict = {
        "user":   {"funds": []},
        "spouse": {"funds": []},
    }
    results = []

    # Track which owners already have a report processed (newest-first).
    # Gmail returns messages newest-first by default.
    owners_processed: set = set()
    # Collect message IDs to label as AI_PROCESSED at the end (even skipped ones)
    all_msg_ids_to_label: list[str] = []

    # ── 5. Process each email (newest first) ──────────────────────────────────
    for msg_stub in messages:
        msg_id = msg_stub["id"]
        all_msg_ids_to_label.append(msg_id)
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
                        print(f"✅ [CRON] PDF decrypted using member ID index {idx} → owner='{detected_owner}'")
                        break
                if not authenticated:
                    print(f"❌ [CRON] Could not decrypt PDF for message {msg_id}")
                    results.append({"msg_id": msg_id, "status": "skipped", "reason": "decryption_failed"})
                    doc.close()
                    continue

            # ── Check if we already processed a newer email for this owner ────
            if detected_owner in owners_processed:
                print(f"⏭️ [CRON] Skipping message {msg_id} — already processed a newer email for owner '{detected_owner}'")
                results.append({"msg_id": msg_id, "status": "skipped_older", "reason": f"newer_email_already_processed_for_{detected_owner}"})
                doc.close()
                continue

            # Redact PII and render pages to base64 PNG
            redacted_images_b64 = _redact_and_render_pdf(doc, all_target_strings)

            print(f"✅ [CRON] Redacted {len(redacted_images_b64)} page(s)")

            if not api_key:
                results.append({"msg_id": msg_id, "status": "preview_only", "reason": "no_anthropic_key"})
                continue

            # ── Anthropic Vision extraction ───────────────────────────────────
            extracted_funds = _extract_funds_via_ai(redacted_images_b64, api_key, f"gmail_{msg_id}")
            accumulated_portfolios[detected_owner]["funds"].extend(extracted_funds)


            # Mark this owner as processed (only newest email per owner)
            owners_processed.add(detected_owner)
            results.append({"msg_id": msg_id, "status": "success", "products_found": len(products), "owner": detected_owner})

        except Exception as e:
            print(f"💥 [CRON] Error processing message {msg_id}: {e}")
            results.append({"msg_id": msg_id, "status": "error", "reason": str(e)})

    # ── 5b. Label ALL found messages as AI_PROCESSED (including skipped) ──────
    for mid in all_msg_ids_to_label:
        try:
            service.users().messages().modify(
                userId="me",
                id=mid,
                body={"addLabelIds": [label_id]},
            ).execute()
            print(f"🏷️ [CRON] Labeled message {mid} as AI_PROCESSED")
        except Exception as e:
            print(f"⚠️ [CRON] Failed to label message {mid}: {e}")

    # ── 6. Generate action items & persist ────────────────────────────────────
    total_funds = sum(len(accumulated_portfolios[k]["funds"]) for k in ["user", "spouse"])

    if total_funds > 0:
        print(f"\n🤖 [CRON] Generating action items ({total_funds} funds)…")
        live_market_data = await _collect_market_data_async(accumulated_portfolios)
        _attach_competitors_to_funds(accumulated_portfolios, live_market_data)
        action_items = ai_advisor.generate_action_items(
            family_portfolio=accumulated_portfolios,
            market_data=live_market_data,
            financial_profile=f_profile,
        )

        now = datetime.datetime.now().isoformat()
        final_json = {
            "uid": uid,
            "last_updated": now,
            "portfolios": accumulated_portfolios,
            "action_items": action_items,
        }

        print("\n☁️ [CRON] Saving to Firestore…")
        db_manager.save_processed_portfolio(uid, final_json)

        # Update last_fetched_at timestamp
        db_manager.update_family_field(uid, "last_fetched_at", now)
    else:
        print("\n⚠️ [CRON] No new funds extracted — preserving existing Firestore data (no overwrite).")

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
