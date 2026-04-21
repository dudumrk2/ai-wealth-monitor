from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File, Form
import firebase_admin
import datetime
import yfinance as yf
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
import requests
from bs4 import BeautifulSoup

import sys
import time

# --- LOG REDIRECTION TO FILE ---
# This ensures that all 'print' statements and errors are written to app.log
# which I can read here, while still showing in your terminal.
class Logger(object):
    def __init__(self, file_path, original_stream):
        self.terminal = original_stream
        self.log = open(file_path, "a", encoding="utf-8")

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

from report_utils import (
    _redact_and_render_pdf,
    _extract_funds_via_ai,
    _collect_market_data,
    _collect_market_data_async,
    _attach_competitors_to_funds
)



# --- STOCK SCRAPING HELPERS ---
import re
import json

def fetch_bizportal_fund_data(ticker: str) -> Optional[dict]:
    """
    Fetches the latest price for an Israeli mutual fund or ETF from Bizportal.
    Target URL: https://www.bizportal.co.il/mutualfunds/quote/generalview/{ticker}
    Returns a dict with 'current_price' and 'previous_close'.
    """
    url = f"https://www.bizportal.co.il/mutualfunds/quote/generalview/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ [BIZPORTAL] HTTP {response.status_code} for fund {ticker}")
            return None
            
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract Current Price
        # Bizportal stores prices inside `<div class="num">`
        num_divs = soup.find_all('div', class_='num')
        if not num_divs:
            print(f"❌ [BIZPORTAL] Could not find price container (.num) for fund {ticker}")
            return None
        
        current_price_str = num_divs[0].get_text().strip().replace(",", "")
        current_price_agorot = float(current_price_str)
        
        # Bizportal prices are in AGOROT (1/100 of NIS), convert to NIS
        current_price = current_price_agorot / 100.0
        
        # Extract Daily PCT Change
        # Bizportal stores pct change in `<span class="num percent rise">` or `<span class="num percent drop">`
        pct_change = 0.0
        rise_span = soup.select_one('.num.percent.rise')
        drop_span = soup.select_one('.num.percent.drop')
        
        if rise_span:
            pct_str = rise_span.get_text().strip().replace("%", "").replace(",", "")
            pct_change = float(pct_str)
        elif drop_span:
            pct_str = drop_span.get_text().strip().replace("%", "").replace(",", "")
            # Bizportal includes the minus sign in the string, so we just convert it
            pct_change = float(pct_str)
            
        # Calculate Previous Close
        # formula: current_price = previous_close * (1 + pct_change/100) -> previous_close = current_price / (1 + pct_change/100)
        if pct_change != -100.0:
            previous_close = current_price / (1 + (pct_change / 100))
        else:
            previous_close = current_price # Fallback to prevent division by zero edge-cases
            
        print(f"🔍 [BIZPORTAL] Scraped {ticker}: Price={current_price}, Pct={pct_change}%, CalculatedPrev={previous_close}")
        return {
            "current_price": current_price,
            "previous_close": previous_close,
            "pct_change": pct_change
        }

    except Exception as e:
        print(f"❌ [BIZPORTAL] Failed to scrape Bizportal for fund {ticker}: {e}")
        return None

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

app.include_router(dashboard_chat.router)
app.include_router(documents.router)
app.include_router(insurance.router)

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

from auth import verify_token, security

@app.delete("/api/portfolio/fund/{fund_id}")
async def delete_fund(fund_id: str, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        raise HTTPException(status_code=404, detail="תיק נתונים לא נמצא")
        
    portfolios = portfolio_doc.get("portfolios", {})
    deleted = False
    
    for owner_key in ["user", "spouse"]:
        owner_data = portfolios.get(owner_key, {})
        funds = owner_data.get("funds", [])
        if not funds: continue
        
        new_funds = [f for f in funds if f.get("id") != fund_id]
        if len(new_funds) < len(funds):
            owner_data["funds"] = new_funds
            deleted = True
            
    if not deleted:
        raise HTTPException(status_code=404, detail="הפוליסה לא נמצאה או שכבר נמחקה")
        
    db_manager.save_processed_portfolio(uid, portfolio_doc)
    return {"status": "ok", "message": "הפוליסה הוסרה בהצלחה"}

@app.get("/api/portfolio/fx-rate")
async def get_fx_rate(user: dict = Depends(verify_token)):
    """
    Get the global USD/ILS exchange rate. Uses Firestore cache (config/fx_rates) with 12 hour TTL.
    """
    import aiohttp
    import datetime
    
    # 1. Check cache first
    cached = db_manager.get_fx_rate()
    if cached:
        print(f"💰 [APP] Returning cached FX rate: {cached['rate']} from {cached['date']}")
        return {"rate": cached["rate"], "date": cached["date"], "is_fallback": False, "cached": True}
        
    # 2. Fetch fresh if no cache or stale
    print(f"💰 [APP] Fetching fresh FX rate from API...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.frankfurter.app/latest?from=USD&to=ILS', timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    rate = data['rates']['ILS']
                    date_str = data['date']
                    
                    # Ensure it is a float
                    rate = float(rate)
                    
                    # Save to cache
                    db_manager.save_fx_rate(rate, date_str)
                    
                    return {"rate": rate, "date": date_str, "is_fallback": False, "cached": False}
                else:
                    print(f"⚠️ [APP] frankfurter.app returned status {response.status}")
    except Exception as e:
        print(f"💥 [APP] Error fetching FX rate: {e}")
        
    # 3. Fallback
    fallback_rate = 3.70
    fallback_date = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"💰 [APP] Using fallback FX rate: {fallback_rate}")
    return {"rate": fallback_rate, "date": fallback_date, "is_fallback": True, "cached": False}

def _calculate_stock_summary_data(stocks: list, fx_rate: float) -> dict:
    """Calculate aggregate totals for the stock portfolio in ILS."""
    if not stocks:
        return {"total_value": 0, "daily_return": 0, "total_return": 0}
        
    total_value_ils = 0.0
    total_daily_pnl_ils = 0.0
    total_pnl_ils = 0.0
    total_invested_ils = 0.0

    for stock in stocks:
        symbol = stock.get("symbol")
        if not symbol: continue
        
        currency = stock.get("currency", "USD")
        r = fx_rate if currency == "USD" else 1.0
        
        # Prefer new naming from scraper, fallback to Excel naming
        v_orig = stock.get("totalValueOriginal", stock.get("value", 0.0))
        dp_orig = stock.get("dailyPnlOriginal", stock.get("dailyPnl", 0.0))
        tp_orig = stock.get("totalPnlOriginal", stock.get("totalPnl", 0.0))
        
        val_ils = v_orig * r
        total_value_ils += val_ils
        total_daily_pnl_ils += dp_orig * r
        total_pnl_ils += tp_orig * r
        total_invested_ils += (val_ils - (tp_orig * r))

    daily_base = total_value_ils - total_daily_pnl_ils
    daily_return_pct = (total_daily_pnl_ils / daily_base * 100) if daily_base > 0 else 0.0
    total_return_pct = (total_pnl_ils / total_invested_ils * 100) if total_invested_ils > 0 else 0.0
    
    return {
        "total_value": total_value_ils,
        "daily_return": daily_return_pct,
        "total_return": total_return_pct
    }

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
            
            # Generate action items using the unified Gemini-based advisor
            try:
                action_items = ai_advisor.generate_action_items(portfolios, live_market_data, f_profile)
                print(f"✅ [APP] Advisory refresh complete: generated {len(action_items)} action items.")
            except Exception as ai_e:
                print(f"⚠️ [APP] Advisory failed during refresh: {ai_e}. Keeping existing items.")
                action_items = portfolio_doc.get("action_items", [])

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

        # Get FX rate
        fx_rate_data = db_manager.get_fx_rate()
        fx_rate = fx_rate_data.get("rate", 3.70) if fx_rate_data else 3.70

        # ALWAYS calculate fresh summary for the dashboard
        stocks_list = portfolio_doc.get("stocks", [])
        stock_summary = _calculate_stock_summary_data(stocks_list, fx_rate)

        return {
            "last_updated": last_updated,
            "portfolios": portfolios,
            "action_items": action_items,
            "stocks": stocks_list,
            "stock_portfolio_summary": stock_summary,
            "fx_rate": fx_rate
        }
    
    print(f"⚠️ [APP] Portfolio not found in Firestore for {uid}. Falling back to mock data.")
    return {
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"],
        "action_items": MOCK_DATA["action_items"],
        "stocks": []
    }


async def _perform_stock_prices_update(uid: str, source_label: str = "REFRESH") -> dict:
    """
    Unified logic to refresh stock prices and FX rates for a specific user.
    Called both by manual refresh and automated cron jobs.
    """
    # 1. Refresh USD/ILS FX Rate first
    fx_prev_close = 1.0
    new_rate = 1.0
    try:
        fx_ticker = yf.Ticker("USDILS=X")
        fx_data = fx_ticker.history(period="5d")
        if not fx_data.empty:
            new_rate = float(fx_data['Close'].iloc[-1])
            fx_prev_close = float(fx_data['Close'].iloc[-2]) if len(fx_data) > 1 else new_rate
            db_manager.save_fx_rate(new_rate, datetime.datetime.now().strftime("%Y-%m-%d"))
            print(f"💰 [{source_label}] Updated FX Rate: {new_rate} (Prev: {fx_prev_close})")
    except Exception as e:
        print(f"⚠️ [{source_label}] Failed to update FX rate: {e}")

    # 2. Identify stocks to update
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        return {"updated": 0, "message": "No portfolio found"}
        
    stocks = portfolio_doc.get("stocks", [])
    if not stocks:
        return {"updated": 0, "message": "No holdings found"}
        
    total_value = 0.0
    total_daily_return_value = 0.0
    total_invested = 0.0
    updated_count = 0
    
    print(f"🔄 [{source_label}] Starting refresh for UID: {uid} ({len(stocks)} symbols)")
    
    for holding in stocks:
        symbol = holding.get("symbol")
        if not symbol: continue
        
        is_cash = holding.get("is_cash", False)
        
        try:
            current_price = None
            previous_close = None
            method_label = "yfinance"

            if is_cash:
                current_price = 1.0
                currency = holding.get("currency", "USD")
                if currency == "USD" and fx_prev_close > 0:
                    # To reflect FX change in Daily P&L, previous native price should be:
                    # previous_native = 1.0 / (new_rate / fx_prev_close)
                    previous_close = 1.0 * (fx_prev_close / new_rate)
                else:
                    previous_close = 1.0
                method_label = "cash"
            else:
                # Normalize: if numeric, append .TA for Yahoo Finance
                ticker = str(symbol).strip()
        
                if ticker.isdigit():
                    # Israeli Mutual Fund / ETF - Use Bizportal
                    method_label = "Bizportal"
                    fund_data = fetch_bizportal_fund_data(ticker)
                    if fund_data:
                        current_price = fund_data["current_price"]
                        previous_close = fund_data["previous_close"]
                    else:
                        print(f"⚠️ [{source_label}] Bizportal fetch failed for {ticker}, skipping price update.")
                else:
                    # US/Other Stock - Use yfinance
                    try:
                        t = yf.Ticker(ticker)
                        hist = t.history(period="5d")
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                            previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                        else:
                            print(f"⚠️ [{source_label}] No yfinance history found for ticker {ticker}")
                    except Exception as yf_e:
                        print(f"⚠️ [{source_label}] yfinance error for {ticker}: {yf_e}")
        
            old_price = holding.get("lastPrice", holding.get("current_price", 0.0))
            
            if current_price is None:
                # Fallback to existing calculations if fetch failed
                shares = float(holding.get("qty", holding.get("shares", 0.0)))
                holding_value = shares * float(old_price)
                avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", old_price)))
                total_value += holding_value
                total_invested += shares * avg_cost
                total_daily_return_value += float(holding.get("dailyPnlOriginal", 0.0))
                continue
                
            # Extract shares for log
            shares_for_log = float(holding.get("qty", holding.get("shares", 0.0)))
    
            # Compute aggregations for THIS stock
            shares = float(holding.get("qty", holding.get("shares", 0.0)))
            avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", current_price)))
            
            holding_value = shares * current_price
            holding_invested = shares * avg_cost
            
            # Daily delta
            daily_delta = current_price - previous_close
            daily_pnl = shares * daily_delta
            total_pnl = holding_value - holding_invested
                
            # 1. Update the stock object for `portfolios` doc (the UI view)
            calc_daily_pct = (daily_delta / previous_close * 100) if previous_close > 0 else 0.0
            
            # Print the correct stats to matches what is saved
            print(f"📊 [{source_label}] {symbol} ({shares_for_log:,.2f} units) via {method_label}: Prev={previous_close:.2f} -> Curr={current_price:.2f} (Daily Δ: {daily_delta:+.2f}, {calc_daily_pct:+.2f}%)")
            
            holding["lastPrice"] = current_price
            holding["qty"] = shares  # Ensure qty is saved for the frontend
            
            holding["dailyChangePercent"] = calc_daily_pct
            holding["dailyPnlOriginal"] = daily_pnl
            holding["totalPnlOriginal"] = total_pnl
            holding["totalValueOriginal"] = holding_value
            holding["totalReturnPercent"] = (total_pnl / holding_invested * 100) if holding_invested > 0 else 0.0
            holding["last_updated"] = datetime.datetime.now().isoformat()
            
            if method_label == "Bizportal":
                print(f"🎯 [DEBUG-IL] {ticker} -> Price: {current_price}, Prev: {previous_close}, DailyDelta: {daily_delta:+.2f}, DailyChange%: {calc_daily_pct:+.2f}%")
    
            # 2. Update the `families/{uid}/holdings` subcollection for cron job sync
            updates_for_subcol = {
                "current_price": current_price,
                "shares": shares,
                "average_cost": avg_cost,
                "last_updated": datetime.datetime.now().isoformat(),
                "name": holding.get("name", ""),
                "currency": holding.get("currency", "USD")
            }
            db_manager.update_family_holding(uid, symbol, updates_for_subcol)
            
            updated_count += 1
            total_value += holding_value
            total_invested += holding_invested
            total_daily_return_value += daily_pnl
                    
        except Exception as e:
            print(f"⚠️ [{source_label}] Error updating {symbol}: {e}")
            shares = float(holding.get("qty", 0.0))
            total_value += shares * float(old_price)
            avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", old_price)))
            total_invested += shares * avg_cost
            total_daily_return_value += float(holding.get("dailyPnlOriginal", 0.0))
    
    if updated_count > 0:
        # Recalculate summary using the clean helper
        fx_rate_data = db_manager.get_fx_rate()
        fx_rate = fx_rate_data.get("rate", 3.70) if fx_rate_data else 3.70
        summary = _calculate_stock_summary_data(stocks, fx_rate)
        
        # Save back the whole portfolio doc to update the UI
        db_manager.save_processed_portfolio(uid, portfolio_doc)

        # Update the summary too
        db_manager.update_portfolio_summary(uid, summary["total_value"], summary["daily_return"], summary["total_return"])
        print(f"✅ [{source_label}] Completed. {updated_count} stocks updated. Total Value: {summary['total_value']:,.0f}")

    return {"updated": updated_count}

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
    cron_fetch_emails_enabled: Optional[bool] = None
    cron_stock_prices_enabled: Optional[bool] = None
    cron_weekly_summary_enabled: Optional[bool] = None


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
        "cron_fetch_emails_enabled": profile.get("cron_fetch_emails_enabled", True),
        "cron_stock_prices_enabled": profile.get("cron_stock_prices_enabled", True),
        "cron_weekly_summary_enabled": profile.get("cron_weekly_summary_enabled", True),
    }

@app.post("/api/settings/cron/update-stock-prices/run")
async def trigger_manual_update_stock_prices(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    print(f"\n🚀 [APP] Manual stock price update triggered by user {uid}")
    res = await _perform_stock_prices_update(uid, source_label="USER-MANUAL-CRON")
    return {"status": "success", "result": res}

@app.post("/api/settings/cron/weekly-stock-summary/run")
async def trigger_manual_weekly_summary(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    print(f"\n🚀 [APP] Manual weekly summary triggered by user {uid}")
    res = await _weekly_stock_summary_for_family(uid)
    return {"status": "success", "result": res}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
