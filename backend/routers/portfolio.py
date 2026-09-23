from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import datetime
import db_manager
from auth import verify_token
import ai_advisor
import config
from services.stock_updater import _perform_stock_prices_update, _calculate_stock_summary_data
from report_utils import _collect_market_data_async, _attach_competitors_to_funds
from mock_data import MOCK_DATA

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])

# ──────────────────────────────────────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────────────────────────────────────

class DepositRequest(BaseModel):
    amount_ils: float
    date: str  # "YYYY-MM-DD"


# ──────────────────────────────────────────────────────────────────────────────
# Performance chart endpoint
# ──────────────────────────────────────────────────────────────────────────────

def _compute_return_points(snapshots: list, deposits: list) -> list:
    """
    Given monthly snapshots and deposit records (all pre-sorted by month),
    return a list of data points with deposit-adjusted return % (Modified Dietz).

    Each point: { "label": str, "total_value_ils": float, "return_pct": float | None }
    The baseline (return_pct = 0) is always the first snapshot.
    """
    if not snapshots:
        return []

    start_value = snapshots[0]["total_value_ils"]
    result = []
    dep_idx = 0
    cumulative_deposit = 0.0

    for snap in snapshots:
        snap_month = snap["month"]

        # Accumulate deposits whose month <= this snapshot month
        while dep_idx < len(deposits) and deposits[dep_idx].get("month", "9999") <= snap_month:
            cumulative_deposit += deposits[dep_idx].get("amount_ils", 0.0)
            dep_idx += 1

        current_value = snap["total_value_ils"]
        return_pct = None
        if start_value > 0:
            return_pct = round(
                (current_value - start_value - cumulative_deposit) / start_value * 100,
                2,
            )

        result.append({
            "label": snap_month,       # e.g. "2026-09"
            "total_value_ils": current_value,
            "return_pct": return_pct,
        })

    return result


def _group_into_quarters(monthly_points: list) -> list:
    """
    Take monthly data points and return quarterly ones.
    Each quarter is represented by its **last** available month.
    Quarter label: "Q1 2026", "Q2 2026", ...
    """
    quarter_map = {}  # "Q1 2026" -> last point in that quarter
    for pt in monthly_points:
        year, month = pt["label"].split("-")
        q = (int(month) - 1) // 3 + 1
        key = f"Q{q} {year}"
        quarter_map[key] = pt  # overwrite → last month of the quarter wins

    def _sort_key(key: str) -> tuple:
        parts = key.split()  # ["Q1", "2026"]
        return (int(parts[1]), int(parts[0][1]))  # (year, quarter_num)

    return [
        {"label": k, **{kk: vv for kk, vv in v.items() if kk != "label"}}
        for k, v in sorted(quarter_map.items(), key=lambda item: _sort_key(item[0]))
    ]


@router.get("/performance")
async def get_performance(
    view: str = "monthly",          # "monthly" | "quarterly" | "yearly"
    user: dict = Depends(verify_token),
):
    """
    Return portfolio performance chart data.

    Query param:
      view — one of "monthly" (default), "quarterly", "yearly"

    Return formula (Modified Dietz):
      return_pct = (current_value - start_value - cumulative_deposits) / start_value * 100

    Granularity:
      monthly  — one point per month in the current year
      quarterly — one point per quarter (Q1-Q4) in the current year
      yearly   — one point per year (all years with data)
    """
    uid = user.get("uid")
    current_year = datetime.datetime.now().year

    if view == "yearly":
        # Fetch everything (no lower bound — we go back as far as data exists)
        # Use a far-past from_month so we get all records
        from_month = None  # fetch all historical data
    else:
        from_month = f"{current_year}-01"

    snapshots = db_manager.get_portfolio_snapshots(uid, from_month=from_month)
    deposits = db_manager.get_portfolio_deposits(uid, from_month=from_month)

    if not snapshots:
        return {"points": [], "total_return_pct": None, "has_data": False, "view": view}

    if view == "quarterly":
        monthly_points = _compute_return_points(snapshots, deposits)
        points = _group_into_quarters(monthly_points)
    elif view == "yearly":
        # Group snapshots by year: keep last snapshot per year
        year_map: dict[str, dict] = {}
        for snap in snapshots:
            year = snap["month"][:4]
            year_map[year] = snap   # overwrite → last month of year wins

        yearly_snapshots = list(year_map.values())
        # Deposits also grouped — keep individual records, _compute_return_points handles accumulation
        # Rewrite labels to year strings after computing monthly
        year_points_raw = _compute_return_points(yearly_snapshots, deposits)
        points = [{"label": pt["label"][:4], **{k: v for k, v in pt.items() if k != "label"}}
                  for pt in year_points_raw]
    else:
        # monthly (default)
        points = _compute_return_points(snapshots, deposits)

    final_return = points[-1].get("return_pct") if points else None
    # For deposit detection we need ALL historical snapshots.
    # If yearly view already fetched all, reuse them; otherwise fetch full history separately.
    all_snapshots = snapshots if view == "yearly" else db_manager.get_portfolio_snapshots(uid, from_month=None)
    deposit_suggestion = _detect_deposit_suggestion(uid, all_snapshots)

    return {
        "points": points,
        "total_return_pct": final_return,
        "has_data": len(points) >= 2,
        "view": view,
        "deposit_suggestion": deposit_suggestion,
    }


def _detect_deposit_suggestion(uid: str, snapshots: list) -> dict | None:
    """
    Check if the latest monthly snapshot shows an unexplained surge compared
    to the previous month (indicating a large cash injection/deposit, e.g. 30,000 ILS to Psagot).

    Returns a deposit suggestion dict if detected, or None.
    """
    try:
        if len(snapshots) < 2:
            return None

        latest_snap = snapshots[-1]
        prev_snap = snapshots[-2]

        current_val = latest_snap.get("total_value_ils", 0.0)
        prev_val = prev_snap.get("total_value_ils", 0.0)

        if prev_val <= 0 or current_val <= prev_val:
            return None

        target_month = latest_snap.get("month", "")
        # Get existing deposits for this target month
        deposits = db_manager.get_portfolio_deposits(uid, from_month=target_month)
        existing_month_deposits = sum(
            d.get("amount_ils", 0.0) for d in deposits if d.get("month") == target_month
        )

        unexplained_growth = (current_val - prev_val) - existing_month_deposits

        # Threshold criteria for suspecting a deposit:
        # 1. Unexplained growth >= 5,000 ILS
        # 2. AND growth >= 4.0% of previous portfolio value, OR unexplained growth >= 20,000 ILS
        pct_growth = (unexplained_growth / prev_val) * 100
        if unexplained_growth >= 5000 and (pct_growth >= 4.0 or unexplained_growth >= 20000):
            return {
                "detected": True,
                "suggested_amount": round(unexplained_growth, 0),
                "diff_amount": round(current_val - prev_val, 0),
                "unexplained_growth": round(unexplained_growth, 0),
                "growth_pct": round(pct_growth, 1),
                "prev_value": prev_val,
                "current_value": current_val,
                "prev_month": prev_snap.get("month"),
                "current_month": target_month,
                "default_date": f"{target_month}-01",
            }
        return None
    except Exception as e:
        print(f"⚠️ [PORTFOLIO] Error detecting deposit suggestion: {e}")
        return None


@router.post("/deposit")
async def record_deposit(body: DepositRequest, user: dict = Depends(verify_token)):
    """Record a new cash deposit into the managed portfolio for return adjustment."""
    uid = user.get("uid")
    if body.amount_ils <= 0:
        raise HTTPException(status_code=400, detail="סכום ההפקדה חייב להיות חיובי")

    # Date validation: format + no future dates
    try:
        deposit_date = datetime.datetime.strptime(body.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="פורמט תאריך לא תקין (YYYY-MM-DD)")
    if deposit_date > datetime.date.today():
        raise HTTPException(status_code=400, detail="תאריך ההפקדה לא יכול להיות בעתיד")

    ok = db_manager.save_portfolio_deposit(uid, body.amount_ils, body.date)
    if not ok:
        raise HTTPException(status_code=500, detail="שגיאה בשמירת ההפקדה")

    return {"status": "ok", "message": f"הפקדה של ₪{body.amount_ils:,.0f} נרשמה בהצלחה"}


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
            
            # AI always needs fresh market context to be accurate
            live_market_data = await _collect_market_data_async(portfolios)
            _attach_competitors_to_funds(portfolios, live_market_data)
            
            # Generate action items using the unified Gemini-based advisor
            try:
                if uid == config.DEMO_UID:
                     print(f"⏭️  [PORTFOLIO-ROUTER] Skipping AI advisor for demo user.")
                else:
                     new_action_items = ai_advisor.generate_action_items(portfolios, live_market_data, family_profile)
                     
                     # Ensure all refreshed items have owner field (default to shared)
                     for item in new_action_items:
                         if "owner" not in item:
                             item["owner"] = "shared"
                             item["owner_name"] = "משותף"
                     
                     # Replace only pension items, preserve insurance/alt items
                     existing_items = portfolio_doc.get("action_items", [])
                     filtered_items = ai_advisor.filter_pension_items(existing_items)
                     action_items = filtered_items + new_action_items
                     portfolio_doc["action_items"] = action_items
                         
                     print(f"✅ [PORTFOLIO-ROUTER] Advisory refresh complete: generated {len(new_action_items)} action items.")
            except Exception as ai_e:
                print(f"⚠️ [PORTFOLIO-ROUTER] Advisory failed during refresh: {ai_e}. Keeping existing items.")
                action_items = portfolio_doc.get("action_items", [])
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
