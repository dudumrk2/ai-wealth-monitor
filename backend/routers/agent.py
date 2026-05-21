"""
routers/agent.py
================
FastAPI router for the autonomous LangGraph Financial Analyst Agent.

Exposes two endpoints:
  POST /api/cron/analyze-stocks         — cron-secured daily trigger (all families)
  POST /api/settings/cron/analyze-stocks/run — authenticated manual trigger (own family)
"""

import asyncio
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request

import db_manager
from auth import verify_token
from stock_agent import analyze_portfolio_and_gurus
from stock_agent_tools import TRACKED_GURUS, scan_guru_portfolio

router = APIRouter(tags=["Agent"])


# ---------------------------------------------------------------------------
# Internal orchestration helper
# ---------------------------------------------------------------------------

def _analyze_stocks_for_family(uid: str) -> dict:
    """Run the autonomous stock agent for a single family with 13F deduplication.

    Flow:
      1. Fetch family holdings from Firestore.
      2. Run scan_guru_portfolio for each tracked guru (outside the agent).
      3. Compute which 13F alerts are new (not yet sent).
      4. Invoke the LangGraph agent with pre-computed guru data.
      5. Mark new alerts as sent in Firestore on success.

    Returns a result dict with uid, success flag, and agent output.
    """
    print(f"\n🤖 [AGENT] Starting analysis for family: {uid}")

    # Step 1 — Profile & holdings
    profile = db_manager.get_family_profile(uid)
    if not profile:
        print(f"⚠️  [AGENT] No profile found for {uid}")
        return {"uid": uid, "status": "error", "reason": "no_profile"}

    holdings = db_manager.get_family_holdings(uid)
    if not holdings:
        print(f"⚠️  [AGENT] No holdings found for {uid}")
        return {"uid": uid, "status": "error", "reason": "no_holdings"}

    tickers = [h["id"] for h in holdings]
    print(f"📊 [AGENT] Holdings for {uid}: {tickers}")

    # Step 2 — Pre-fetch 13F data outside the agent
    guru_results: dict[str, str] = {}
    for guru_name in TRACKED_GURUS.keys():
        print(f"🔍 [AGENT] Scanning guru: {guru_name}")
        guru_results[guru_name] = scan_guru_portfolio.invoke({"guru_name": guru_name})

    # Step 3 — Compute new alert keys
    sent_keys = db_manager.get_sent_13f_alert_keys()
    all_alert_keys: set[str] = set()

    for guru_name, result_str in guru_results.items():
        quarter_match = re.search(r'(Q\d \d{4})', result_str)
        if not quarter_match:
            continue
        quarter = quarter_match.group(1)

        for line in result_str.splitlines():
            if "New positions" in line or "Liquidated positions" in line:
                # Tickers appear after the colon on the same line
                colon_idx = line.rfind(":")
                if colon_idx == -1:
                    continue
                tickers_str = line[colon_idx + 1:].strip()
                if tickers_str.lower() == "none" or not tickers_str:
                    continue
                for ticker in [t.strip() for t in tickers_str.split(",")]:
                    if ticker:
                        all_alert_keys.add(f"{guru_name}:{ticker}:{quarter}")

    new_alert_keys = all_alert_keys - sent_keys
    print(f"🆕 [AGENT] New alert keys to process for {uid}: {len(new_alert_keys)}")

    # Step 4 — Run agent with pre-computed data
    result = analyze_portfolio_and_gurus(
        tickers,
        pre_analyzed_guru_data=guru_results,
    )

    # Step 5 — Mark new alerts as sent on success
    if result.get("success"):
        for key in new_alert_keys:
            db_manager.mark_13f_alert_sent(key)
        print(f"✅ [AGENT] Analysis complete for {uid}. "
              f"Marked {len(new_alert_keys)} new alerts as sent.")
    else:
        print(f"❌ [AGENT] Analysis failed for {uid}: {result.get('error', 'unknown')}")

    return {
        "uid": uid,
        "success": result.get("success", False),
        "new_alerts_marked": len(new_alert_keys) if result.get("success") else 0,
        "output_snippet": result.get("output", "")[:200],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/cron/analyze-stocks")
async def analyze_stocks_cron(request: Request):
    """
    Daily cron endpoint to run the autonomous LangGraph stock agent for all families.
    Fetches live prices, scans Superinvestor 13F filings, and sends Telegram alerts.
    Deduplication prevents repeat 13F alerts across runs.
    Secured via X-Cron-Secret header.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: invalid or missing X-Cron-Secret"
        )

    uids = db_manager.get_all_family_uids_for_holdings()
    print(f"\n🤖 [CRON] analyze-stocks — targeting {len(uids)} family/families")

    results = []
    for uid in uids:
        profile = db_manager.get_family_profile(uid)
        if profile and profile.get("cron_agent_enabled", True) is False:
            print(f"⏭️  [CRON] Skipping analyze-stocks for {uid} (disabled in settings)")
            continue
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(_analyze_stocks_for_family, uid),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            print(f"⏰ [CRON] Agent run timed out (180s) for family: {uid}")
            res = {
                "uid": uid,
                "success": False,
                "error": "agent_timeout_180s",
                "new_alerts_marked": 0,
            }
        results.append(res)

    return {
        "status": "success",
        "families_processed": len(results),
        "results": results,
    }


@router.post("/api/settings/cron/analyze-stocks/run")
async def trigger_manual_analyze_stocks(user: dict = Depends(verify_token)):
    """Manual trigger for the stock agent — for testing from the app UI."""
    uid = user["uid"]
    print(f"\n⚡ User {uid} triggered stock agent analysis")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_analyze_stocks_for_family, uid),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        print(f"⏰ [AGENT] Manual trigger timed out (180s) for: {uid}")
        return {
            "uid": uid,
            "success": False,
            "error": "agent_timeout_180s",
            "new_alerts_marked": 0,
        }
