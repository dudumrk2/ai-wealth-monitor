from fastapi import APIRouter, Depends, HTTPException, status
import datetime
import db_manager
from auth import verify_token
import ai_advisor
from services.stock_updater import _perform_stock_prices_update, _calculate_stock_summary_data
from report_utils import _collect_market_data_async, _attach_competitors_to_funds
from mock_data import MOCK_DATA

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])

@router.delete("/fund/{fund_id}")
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

@router.get("/fx-rate")
async def get_fx_rate(user: dict = Depends(verify_token)):
    """
    Get the global USD/ILS exchange rate. Uses Firestore cache (config/fx_rates) with 12 hour TTL.
    """
    import aiohttp
    
    # 1. Check cache first
    cached = db_manager.get_fx_rate()
    if cached:
        print(f"💰 [PORTFOLIO-ROUTER] Returning cached FX rate: {cached['rate']} from {cached['date']}")
        return {"rate": cached["rate"], "date": cached["date"], "is_fallback": False, "cached": True}
        
    # 2. Fetch fresh if no cache or stale
    print(f"💰 [PORTFOLIO-ROUTER] Fetching fresh FX rate from API...")
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
                    print(f"⚠️ [PORTFOLIO-ROUTER] frankfurter.app returned status {response.status}")
    except Exception as e:
        print(f"💥 [PORTFOLIO-ROUTER] Error fetching FX rate: {e}")
        
    # 3. Fallback
    fallback_rate = 3.70
    fallback_date = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"💰 [PORTFOLIO-ROUTER] Using fallback FX rate: {fallback_rate}")
    return {"rate": fallback_rate, "date": fallback_date, "is_fallback": True, "cached": False}

@router.get("")
async def get_portfolio(
    refresh_market: bool = False,
    refresh_ai: bool = False,
    user: dict = Depends(verify_token)
):
    uid = user.get("uid")
    print(f"🔍 [PORTFOLIO-ROUTER] GET /api/portfolio - Fetching for {uid} (refresh_market={refresh_market}, refresh_ai={refresh_ai})")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    
    if portfolio_doc:
        portfolios = portfolio_doc.get("portfolios", {})
        action_items = portfolio_doc.get("action_items", [])
        last_updated = portfolio_doc.get("last_updated")
        
        needs_save = False
        
        # 1. Explicit AI Refresh
        if refresh_ai:
            print(f"🤖 [PORTFOLIO-ROUTER] Explicit AI refresh requested for {uid}")
            family_profile = db_manager.get_family_profile(uid)
            f_profile = family_profile.get("financial_profile", {}) if family_profile else {}
            
            # AI always needs fresh market context to be accurate
            live_market_data = await _collect_market_data_async(portfolios)
            _attach_competitors_to_funds(portfolios, live_market_data)
            
            # Generate action items using the unified Gemini-based advisor
            try:
                action_items = ai_advisor.generate_action_items(portfolios, live_market_data, f_profile)
                print(f"✅ [PORTFOLIO-ROUTER] Advisory refresh complete: generated {len(action_items)} action items.")
            except Exception as ai_e:
                print(f"⚠️ [PORTFOLIO-ROUTER] Advisory failed during refresh: {ai_e}. Keeping existing items.")
                action_items = portfolio_doc.get("action_items", [])

            portfolio_doc["action_items"] = action_items
            last_updated = datetime.datetime.now().isoformat()
            portfolio_doc["last_updated"] = last_updated
            needs_save = True

        # 2. Explicit Market Refresh (if AI refresh wasn't already doing it)
        elif refresh_market:
            print(f"📊 [PORTFOLIO-ROUTER] Explicit market data refresh requested for {uid}")
            live_market_data = await _collect_market_data_async(portfolios)
            _attach_competitors_to_funds(portfolios, live_market_data)
            needs_save = True

        if needs_save:
            print(f"☁️ [PORTFOLIO-ROUTER] Saving updated portfolio after refresh...")
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
    
    print(f"⚠️ [PORTFOLIO-ROUTER] Portfolio not found in Firestore for {uid}. Falling back to mock data.")
    return {
        "last_updated": MOCK_DATA["last_updated"],
        "portfolios": MOCK_DATA["portfolios"],
        "action_items": MOCK_DATA["action_items"],
        "stocks": []
    }
