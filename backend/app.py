from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
import firebase_admin
import datetime
import yfinance as yf
from fastapi.middleware.cors import CORSMiddleware
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
import re
from services.prime_rate import fetch_israeli_prime_rate
from services.stock_updater import _perform_stock_prices_update, _calculate_stock_summary_data

import sys
import time

# --- LOG REDIRECTION WITH ROTATION ---
import logging
from logging.handlers import RotatingFileHandler

log_file_path = os.path.join(os.path.dirname(__file__), "app.log")
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

class StreamToLogger(object):
    def __init__(self, original_stream, logger_func):
        self.terminal = original_stream
        self.logger_func = logger_func

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()
        if message.rstrip():
            self.logger_func(message.rstrip())

    def flush(self):
        self.terminal.flush()

sys.stdout = StreamToLogger(sys.stdout, logging.info)
sys.stderr = StreamToLogger(sys.stderr, logging.error)
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

from report_utils import (
    _redact_and_render_pdf,
    _extract_funds_via_ai,
    _collect_market_data,
    _collect_market_data_async,
    _attach_competitors_to_funds
)



# --- DATABASE HELPERS ---

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
from routers import documents
from routers import insurance
from routers import alternatives
from routers import portfolio
app.include_router(dashboard_chat.router)
app.include_router(documents.router)
app.include_router(insurance.router)
app.include_router(alternatives.router)
app.include_router(portfolio.router)

@app.on_event("startup")
async def startup_event():
    print("✅ [APP] Backend service started and ready for requests.")
    sys.stdout.flush()

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

@app.post("/api/auth/demo")
async def login_demo():
    """Seed demo data and return a demo token for the frontend."""
    from services.demo_seeder import seed_demo_data
    import config
    seed_demo_data()
    
    # Get the seeded profile to return to frontend
    profile = db_manager.get_family_profile(config.DEMO_UID)
    
    return {
        "token": config.DEMO_TOKEN, 
        "uid": config.DEMO_UID,
        "family_config": profile
    }

from auth import verify_token

@app.post("/api/portfolio/update-prices")
async def user_update_stock_prices(user: dict = Depends(verify_token)):
    """
    User-triggered endpoint to update their family stock holdings with the latest price.
    """
    uid = user.get("uid")
    res = await _perform_stock_prices_update(uid, source_label="USER-REFRESH")
    return {"status": "success", "updated": res["updated"]}


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

# ── MANUAL STOCK ENTRY ────────────────────────────────────────────────────────

class ManualStockRequest(BaseModel):
    symbol: str
    name: str
    qty: float
    avgCostPrice: float
    currency: str = "USD"
    is_cash: Optional[bool] = False

@app.post("/api/portfolio/stock/manual")
async def add_manual_stock(stock_req: ManualStockRequest, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    print(f"📥 [APP] Manual stock/cash entry for {uid}: {stock_req.symbol}")
    
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        # Create a skeleton doc if none exists
        portfolio_doc = {
            "uid": uid,
            "last_updated": datetime.datetime.now().isoformat(),
            "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}},
            "stocks": [],
            "action_items": []
        }
    
    stocks = portfolio_doc.get("stocks", [])
    
    # 1. Create the stock object
    import uuid
    new_stock = {
        "id": str(uuid.uuid4()),
        "symbol": stock_req.symbol.strip().upper() if not (stock_req.is_cash and stock_req.symbol.strip().upper() == "CASH") else f"CASH_{uuid.uuid4().hex[:6].upper()}",
        "name": stock_req.name.strip(),
        "qty": stock_req.qty,
        "avgCostPrice": stock_req.avgCostPrice if not stock_req.is_cash else 1.0,
        "currency": stock_req.currency.strip().upper(),
        "source": "manual",
        "is_manual": True,
        "is_cash": stock_req.is_cash,
        "last_updated": datetime.datetime.now().isoformat(),
        "lastPrice": stock_req.avgCostPrice if not stock_req.is_cash else 1.0, # Initial fallback
        "totalValueOriginal": stock_req.qty * (stock_req.avgCostPrice if not stock_req.is_cash else 1.0),
        "totalPnlOriginal": 0.0,
        "totalReturnPercent": 0.0,
        "dailyPnlOriginal": 0.0,
        "dailyChangePercent": 0.0,
        "sector": "cash" if stock_req.is_cash else "Other"
    }

    # Use existing symbol or append? Let's check for duplicates.
    existing_idx = next((i for i, s in enumerate(stocks) if s.get("symbol") == new_stock["symbol"]), -1)
    if existing_idx >= 0:
        # Update existing
        stocks[existing_idx].update(new_stock)
        print(f"🔄 [APP] Updated existing manual stock: {new_stock['symbol']}")
    else:
        stocks.append(new_stock)
        print(f"✨ [APP] Added new manual stock: {new_stock['symbol']}")

    # 2. Update processed_portfolio
    portfolio_doc["stocks"] = stocks
    db_manager.save_processed_portfolio(uid, portfolio_doc)
    
    # 3. Sync to holdings subcollection for price updater
    updates_for_subcol = {
        "current_price": new_stock["lastPrice"],
        "shares": new_stock["qty"],
        "average_cost": new_stock["avgCostPrice"],
        "last_updated": new_stock["last_updated"],
        "name": new_stock["name"],
        "currency": new_stock["currency"],
        "is_manual": True
    }
    db_manager.update_family_holding(uid, new_stock["symbol"], updates_for_subcol)
    
    # 4. Trigger price update immediately for this one stock? (Maybe not needed yet, user can hit refresh)
    
    return {"status": "success", "stock": new_stock}

@app.delete("/api/portfolio/stock/{symbol}")
async def delete_stock(symbol: str, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    print(f"🗑️ [APP] Deleting stock {symbol} for {uid}")
    
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
         raise HTTPException(status_code=404, detail="Portfolio not found")
         
    stocks = portfolio_doc.get("stocks", [])
    new_stocks = [s for s in stocks if s.get("symbol") != symbol]
    
    if len(new_stocks) == len(stocks):
        raise HTTPException(status_code=404, detail="Stock not found in portfolio")
        
    portfolio_doc["stocks"] = new_stocks
    db_manager.save_processed_portfolio(uid, portfolio_doc)
    
    # Also delete from holdings subcollection
    from firebase_admin import firestore
    try:
        db_manager.db.collection("families").document(uid).collection("holdings").document(symbol).delete()
    except:
        pass # Best effort
        
    return {"status": "success", "message": f"Stock {symbol} removed"}



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
async def get_gmail_auth_url(uid: str = None, member: str = "member1", user: dict = Depends(verify_token)):
    """
    Return the Google OAuth URL for Gmail authorization.
    Requires Firebase auth token in Authorization header.
    Query param: ?uid=<firebase-uid>  (defaults to the authenticated user's uid)
                 ?member=<member_id>  (defaults to member1)
    """
    import httpx as _httpx
    requester_uid = user["uid"]

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
    cron_fetch_emails_enabled: Optional[bool] = None
    cron_stock_prices_enabled: Optional[bool] = None
    cron_weekly_summary_enabled: Optional[bool] = None


@app.put("/api/settings/gmail")
async def save_gmail_settings(
    payload: GmailSettingsPayload,
    user: dict = Depends(verify_token),
):
    """Save Gmail search settings and cron schedule for the authenticated family."""
    uid = user["uid"]

    updates: dict = {}
    if payload.gmail_sender_email is not None:
        updates["gmail_sender_email"] = payload.gmail_sender_email.strip()
    if payload.gmail_subject is not None:
        updates["gmail_subject"] = payload.gmail_subject.strip()
    if payload.cron_day is not None:
        updates["cron_day"] = max(1, min(30, payload.cron_day))
    if payload.cron_frequency_months is not None:
        updates["cron_frequency_months"] = max(1, min(12, payload.cron_frequency_months))
    if payload.cron_fetch_emails_enabled is not None:
        updates["cron_fetch_emails_enabled"] = payload.cron_fetch_emails_enabled
    if payload.cron_stock_prices_enabled is not None:
        updates["cron_stock_prices_enabled"] = payload.cron_stock_prices_enabled
    if payload.cron_weekly_summary_enabled is not None:
        updates["cron_weekly_summary_enabled"] = payload.cron_weekly_summary_enabled

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    for field, value in updates.items():
        db_manager.update_family_field(uid, field, value)

    return {"status": "success", "updated": list(updates.keys())}


@app.get("/api/settings/gmail")
async def get_gmail_settings(user: dict = Depends(verify_token)):
    """Return the current Gmail settings + connection status for the authenticated family."""
    uid = user["uid"]

    profile = db_manager.get_family_profile(uid) or {}
    return {
        "gmail_connected": bool(profile.get("gmail_refresh_token")),
        "gmail_connected_member": profile.get("gmail_connected_member", "member1"),
        "gmail_sender_email": profile.get("gmail_sender_email", "no-reply@surense.com"),
        "gmail_subject": profile.get("gmail_subject", "דוח מצב ביטוח ופנסיה"),
        "cron_day": profile.get("cron_day", 1),
        "cron_frequency_months": profile.get("cron_frequency_months", 3),
        "last_fetched_at": profile.get("last_fetched_at"),
        "cron_fetch_emails_enabled": profile.get("cron_fetch_emails_enabled", True),
        "cron_stock_prices_enabled": profile.get("cron_stock_prices_enabled", True),
        "cron_weekly_summary_enabled": profile.get("cron_weekly_summary_enabled", True),
    }

@app.post("/api/settings/cron/update-stock-prices/run")
async def trigger_manual_update_stock_prices(user: dict = Depends(verify_token)):
    uid = user["uid"]

    print(f"\n🚀 [APP] Manual stock price update triggered by user {uid}")
    res = await _perform_stock_prices_update(uid, source_label="USER-MANUAL-CRON")
    return {"status": "success", "result": res}

@app.post("/api/settings/cron/weekly-stock-summary/run")
async def trigger_manual_weekly_summary(user: dict = Depends(verify_token)):
    uid = user["uid"]

    print(f"\n🚀 [APP] Manual weekly summary triggered by user {uid}")
    res = await _weekly_stock_summary_for_family(uid)
    return {"status": "success", "result": res}

@app.delete("/api/settings/gmail")
async def disconnect_gmail(user: dict = Depends(verify_token)):
    """Removes the Gmail refresh token and associated member linkage."""
    from firebase_admin import firestore
    uid = user["uid"]

    try:
        db_manager.update_family_field(uid, "gmail_refresh_token", firestore.DELETE_FIELD)
        db_manager.update_family_field(uid, "gmail_connected_member", firestore.DELETE_FIELD)
        return {"status": "success", "message": "Gmail disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/gmail/scan")
async def trigger_manual_gmail_scan(user: dict = Depends(verify_token)):
    """Manually trigger the Gmail scan for the authenticated user and process new reports."""
    uid = user["uid"]

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
    
    if family_profile.get("cron_fetch_emails_enabled", True) is False and not bypass_schedule:
        print(f"⏭️  [CRON] Skipping fetch_emails for {uid} (disabled in settings)")
        return {"processed": 0, "skipped": "disabled_in_settings"}

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

            # Identify owner by trying to decrypt the PDF
            from flow_utils import prepare_pdf_for_vision
            doc, _, authenticated_id = prepare_pdf_for_vision(pdf_bytes, family_profile)
            
            # Guess owner (first ID in member_id_numbers -> user, otherwise spouse)
            detected_owner = "user"
            if authenticated_id and len(member_id_numbers) > 1:
                if authenticated_id == member_id_numbers[1]:
                    detected_owner = "spouse"
            
            # Close the doc used for identification (PensionFlow will open its own)
            doc.close()

            # ── Check if we already processed a newer email for this owner ────
            if detected_owner in owners_processed:
                print(f"⏭️ [CRON] Skipping message {msg_id} — already processed a newer email for owner '{detected_owner}'")
                results.append({"msg_id": msg_id, "status": "skipped_older", "reason": f"newer_email_already_processed_for_{detected_owner}"})
                continue

            # Mark this owner as processed
            owners_processed.add(detected_owner)
            
            # --- Use PensionFlow to process the report ---
            from document_flows import PensionFlow
            flow = PensionFlow(f_profile=family_profile)
            flow_result = await flow.process(pdf_bytes, f"{detected_owner}_gmail_report.pdf", uid)
            
            results.append({
                "msg_id": msg_id, 
                "status": "success", 
                "owner": detected_owner,
                "extracted_count": flow_result.get("extracted_count", 0),
                "validation_warnings": flow_result.get("validation_warnings", [])
            })

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

    # All relevant processing is now handled inside the PensionFlow per report.
    # We update the last_fetched_at if at least one report was successful.
    processed_count = len([r for r in results if r.get("status") == "success"])
    if processed_count > 0:
        db_manager.update_family_field(uid, "last_fetched_at", datetime.datetime.now().isoformat())
    
    print(f"\n🏁 [CRON] fetch-emails COMPLETE — {processed_count}/{len(messages)} processed.")
    return {
        "status": "success",
        "processed": processed_count,
        "total_found": len(messages),
        "results": results,
    }


@app.post("/api/cron/update-stock-prices")
async def update_stock_prices_cron(request: Request):
    """
    Daily cron endpoint to update all family stock holdings with the latest price.
    Also calculates total daily and all-time returns for the stock portfolio.
    Secured via X-Cron-Secret header.
    """
    import yfinance as yf
    
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    uids = db_manager.get_all_family_uids_for_holdings()
    print(f"\n📈 [CRON] update-stock-prices — targeting {len(uids)} family/families")
    
    results = []
    for uid in uids:
        profile = db_manager.get_family_profile(uid)
        if profile and profile.get("cron_stock_prices_enabled", True) is False:
            print(f"⏭️  [CRON] Skipping update_stock_prices for {uid} (disabled in settings)")
            continue

        res = await _perform_stock_prices_update(uid, source_label="CRON")
        if res.get("updated", 0) > 0:
            results.append({"uid": uid, "updated": res["updated"]})

    return {"status": "success", "families_processed": len(results), "results": results}


async def _weekly_stock_summary_for_family(uid: str) -> dict:
    import base64
    from email.mime.text import MIMEText
    import markdown
    from google import genai
    from google.genai import types
    import config
    import prompts

    try:
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            return {"status": "error", "reason": "GEMINI_API_KEY not configured."}
        client = genai.Client(api_key=gemini_api_key)
        
        family_profile = db_manager.get_family_profile(uid)
        if not family_profile: 
            return {"status": "error", "reason": "no_family_profile"}
        
        refresh_token = family_profile.get("gmail_refresh_token")
        if not refresh_token: 
            return {"status": "error", "reason": "no_gmail_refresh_token"}
        
        email_addr = family_profile.get("pii_data", {}).get("member1", {}).get("email")
        if not email_addr:
            print(f"⚠️ [CRON] No email found for {uid}")
            return {"status": "error", "reason": "no_email_found"}

        holdings = db_manager.get_family_holdings(uid)
        if not holdings:
            return {"status": "error", "reason": "no_stock_holdings_found"}
            
        # Build portfolio data string
        portfolio_strings = []
        for h in holdings:
            ticker = h.get("id")
            shares = float(h.get("shares", 0.0))
            current_price = float(h.get("current_price", 0.0))
            average_cost = float(h.get("average_cost", 0.0))
            previous_week_price = float(h.get("previous_week_price", current_price))
            
            weekly_delta_pct = ((current_price - previous_week_price) / previous_week_price * 100) if previous_week_price else 0.0
            all_time_delta_pct = ((current_price - average_cost) / average_cost * 100) if average_cost > 0 else 0.0
            
            if h.get("is_manual", False) and h.get("name") and str(ticker).startswith("CASH_"): 
                name = h.get("name")
                portfolio_strings.append(
                    f"- 💰 מזומן ({name}): {shares:,.2f} {h.get('currency', 'ILS')}"
                )
            else:
                name = h.get("name", ticker)
                # If name is just the ticker, try to keep it clean
                display_name = f"{name} ({ticker})" if name != ticker else ticker
                
                # Check why return might be 0%
                has_prev = "previous_week_price" in h
                
                portfolio_strings.append(
                    f"- 📈 {display_name}: {shares:,.2f} יחידות | מחיר נוכחי: {current_price:.2f} | "
                    f"תשואה שבועית: {weekly_delta_pct:.2f}% (יש היסטוריה: {has_prev}) | תשואה כוללת: {all_time_delta_pct:.2f}%"
                )
        
        portfolio_data_string = "\n".join(portfolio_strings)
        
        final_prompt = prompts.WEEKLY_STOCK_SUMMARY_PROMPT.format(portfolio_data_string=portfolio_data_string)
        
        # Call Gemini
        print(f"\n{'='*20} FULL AI PROMPT (WEEKLY SUMMARY) {'='*20}")
        print(final_prompt)
        print(f"{'='*60}\n")
        
        print(f"🤖 [CRON-AI] Calling Gemini {config.GEMINI_PRO_MODEL_NAME} for weekly summary...")
        response = client.models.generate_content(
            model=config.GEMINI_PRO_MODEL_NAME,
            contents=final_prompt,
            config=types.GenerateContentConfig(
                temperature=0.5
            )
        )
        
        ai_text = response.text
        
        # Convert to HTML
        html_content = markdown.markdown(ai_text)
        email_html = f"<html><head><style>body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }} h2 {{ color: #2c3e50; }} strong {{ color: #1abc9c; }}</style></head><body dir='rtl'>{html_content}</body></html>"
        
        # Send Email
        service = _get_gmail_service(refresh_token)
        message = MIMEText(email_html, 'html', 'utf-8')
        message['To'] = email_addr
        message['Subject'] = "סיכום תיק מניות שבועי והמלצות"
        raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        service.users().messages().send(userId="me", body={'raw': raw_msg}).execute()
        print(f"✅ [CRON] Email sent successfully to {email_addr}")
        
        # Reset previous_week_price
        for h in holdings:
            ticker = h.get("id")
            current_price = h.get("current_price")
            if ticker and current_price:
                db_manager.update_family_holding(uid, ticker, {"previous_week_price": current_price})
                
        return {"status": "success", "email": email_addr}
        
    except Exception as e:
        print(f"💥 [CRON] Error weekly summary for {uid}: {e}")
        return {"status": "error", "reason": str(e)}


@app.post("/api/cron/weekly-stock-summary")
async def weekly_stock_summary_cron(request: Request):
    """
    Weekly cron endpoint to analyze stock portfolios using Gemini 2.5 Pro and email the results.
    Secured via X-Cron-Secret header.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    # Get families with gmail
    uids = db_manager.get_all_family_uids()
    print(f"\n📧 [CRON] weekly-stock-summary — targeting {len(uids)} family/families")
    
    results = []
    
    for uid in uids:
        profile = db_manager.get_family_profile(uid)
        if profile and profile.get("cron_weekly_summary_enabled", True) is False:
            print(f"⏭️  [CRON] Skipping weekly_summary for {uid} (disabled in settings)")
            continue
            
        res = await _weekly_stock_summary_for_family(uid)
        results.append({"uid": uid, **res})

    return {"status": "success", "families_processed": len(uids), "results": results}


@app.post("/api/cron/update-funder-yields")
async def cron_update_funder_yields(request: Request):
    """
    Monthly Cron to update leveraged policy balances based on Funder.
    Secured via X-Cron-Secret header.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    print("\n⏰ [CRON] Starting Funder Yields updater...")
    return await _run_funder_yields_update()

@app.post("/api/settings/cron/update-funder-yields/run")
async def trigger_manual_funder_yields(user: dict = Depends(verify_token)):
    uid = user["uid"]

    print(f"\n⚡ User {uid} triggered Funder Yields updater")
    return await _run_funder_yields_update()

async def _run_funder_yields_update():
    uids = db_manager.get_all_family_uids_for_holdings()
    from funder_scraper import fetch_funder_yields
    
    total_updated = 0
    for uid in uids:
        policies = db_manager.get_leveraged_policies(uid)
        for p in policies:
            link = p.get("funderLink")
            if not link:
                continue
                
            base_month = p.get("baseMonth", "")
            if not base_month:
                continue
                
            yields = await fetch_funder_yields(link)
            if not yields:
                continue
                
            missing = []
            for y_data in yields:
                if y_data["period"] > base_month:
                    missing.append(y_data)
                else:
                    break
                    
            if not missing:
                continue
                
            missing.reverse()
            
            current_balance = float(p.get("currentBalance", 0.0))
            for m in missing:
                y_pct = float(m["yield"])
                current_balance = current_balance * (1 + (y_pct / 100))
                
            p["currentBalance"] = round(current_balance, 2)
            p["baseMonth"] = missing[-1]["period"]
            
            db_manager.add_leveraged_policy(uid, p)
            print(f"✅ Updated policy {p.get('name')} for family {uid} to {p['baseMonth']} balance {p['currentBalance']}")
            total_updated += 1

    # --- Update Israeli Prime Rate as part of this monthly cron ---
    print("\n📊 [CRON] Fetching latest Israeli Prime Rate...")
    prime_rate = fetch_israeli_prime_rate()
    db_manager.save_prime_rate(prime_rate)
    print(f"✅ [CRON] Prime rate updated: {prime_rate}%")
            
    return {"status": "success", "updatedPolices": total_updated, "prime_rate": prime_rate}


@app.get("/api/settings/prime-rate")
async def get_prime_rate_endpoint(user: dict = Depends(verify_token)):
    """
    Get the current Israeli Prime Rate stored in Firestore.
    Frontend can call this as an alternative to a direct Firestore read.
    """
    stored_rate = db_manager.get_prime_rate()
    if stored_rate is not None:
        return {"current_prime_rate": stored_rate, "source": "firestore"}
    # Fallback: fetch live
    live_rate = fetch_israeli_prime_rate()
    return {"current_prime_rate": live_rate, "source": "live"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
