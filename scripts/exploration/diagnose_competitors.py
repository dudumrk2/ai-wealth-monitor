"""
diagnose_competitors.py
=======================
Fetches live competitor data from the government API for every track found
in the Firestore portfolio, then compares it to the cached data stored
in the `market_cache` collection and the data embedded in each fund.

Run from the backend directory:
    py diagnose_competitors.py [uid]

If uid is not provided, the script lists all available portfolio UIDs.
"""
import sys
import json
import asyncio

# ── Bootstrap: load env and init Firebase ────────────────────────────────────
import os
from dotenv import load_dotenv
load_dotenv()

# Add backend folder to sys.path so db_manager and market_data can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import db_manager
import market_data as md

# ── Helpers ───────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"

def fmt_pct(val):
    return f"{val:.2f}%" if val is not None else "—"

def fmt_float(val):
    return f"{val:.2f}" if val is not None else "—"

def print_competitor(c, prefix="  "):
    print(f"{prefix}{BOLD}{c.get('provider_name', '?')}{RESET}")
    print(f"{prefix}  1Y: {fmt_pct(c.get('yield_1yr'))}  |  "
          f"3Y: {fmt_pct(c.get('yield_3yr'))}  |  "
          f"5Y: {fmt_pct(c.get('yield_5yr'))}  |  "
          f"Sharpe: {fmt_float(c.get('sharpe_ratio'))}  |  "
          f"Fee: {fmt_pct(c.get('management_fee_accumulation'))}")


def print_live_competitor(c, prefix="│  "):
    horizon = c.get('_horizon_label', '??')
    manager = c.get('provider_name', '?')
    fund = c.get('fund_name', 'Fund')
    
    y1 = c.get('yield_1yr')
    y3 = c.get('yield_3yr')
    y5 = c.get('yield_5yr')
    fee = c.get('management_fee_accumulation')
    
    # Validation Check: Highlight missing yield data
    warnings = []
    if y1 in (None, 0.0, "", "—"): warnings.append("1Y missing")
    if y3 in (None, 0.0, "", "—"): warnings.append("3Y missing")
    if y5 in (None, 0.0, "", "—"): warnings.append("5Y missing")
    
    warn_str = f" {YELLOW}(⚠ {', '.join(warnings)}){RESET}" if warnings else f" {GREEN}(✓ Yields Valid){RESET}"
    
    print(f"{prefix}🏆 Top {horizon}: {manager} - {fund}{warn_str}")
    print(f"{prefix}    1Y: {fmt_pct(y1)} | 3Y: {fmt_pct(y3)} | 5Y: {fmt_pct(y5)} | Sharpe: {fmt_float(c.get('sharpe_ratio'))} | Fee: {fmt_pct(fee)}")

async def diagnose(uid: str):
    print(f"\n{BOLD}{CYAN}══ Diagnosing portfolio for UID: {uid} ══{RESET}\n")

    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        print(f"{RED}✗ No portfolio found in Firestore for {uid}{RESET}")
        return

    portfolios = portfolio_doc.get("portfolios", {})

    # Collect all unique (product_type, track_name) combos
    tracks = {}  # track_name -> (product_type, stored_competitors)
    for owner in ["user", "spouse"]:
        for fund in portfolios.get(owner, {}).get("funds", []):
            track = fund.get("track_name", "")
            category = fund.get("category", "")
            prod_type = "פנסיה" if category == "pension" else "גמל"
            stored_comps = fund.get("top_competitors", [])
            if track and track not in tracks:
                tracks[track] = (prod_type, stored_comps)

    if not tracks:
        print(f"{YELLOW}⚠ No tracks found in portfolio.{RESET}")
        return

    print(f"Found {len(tracks)} unique track(s):\n")

    for track_name, (prod_type, stored_comps) in tracks.items():
        print(f"{BOLD}┌─ Track: {track_name} ({prod_type}){RESET}")

        # ── Firestore cache ─────────────────────────────────────────────────
        cached = db_manager.get_market_cache(track_name)
        print(f"│  {CYAN}[market_cache Firestore]{RESET} {'HIT' if cached else 'MISS'}")
        if cached:
            for c in cached[:3]:
                print_competitor(c, prefix="│    ")

        # ── Embedded in fund ───────────────────────────────────────────────
        print(f"│  {CYAN}[top_competitors in fund]{RESET} {len(stored_comps)} stored")
        if stored_comps:
            for c in stored_comps:
                print_competitor(c, prefix="│    ")
        else:
            print(f"│    {RED}✗ No competitors embedded in fund!{RESET}")

        # ── Live from government API ────────────────────────────────────────
        print(f"│  {CYAN}[Live Gov API fetch]{RESET}")
        try:
            dataset_query = md._select_dataset_query(prod_type)
            resource_id = await md.get_latest_resource_id(dataset_query)
            
            if not resource_id:
                print(f"│    {RED}✗ Failed to discover resource_id for {dataset_query}{RESET}")
                live = []
            else:
                live = await md.fetch_top_competitors_by_horizon(
                    track_name=track_name, 
                    resource_id=resource_id, 
                    product_type=prod_type
                )
                
            if live:
                print(f"│  ✅ Live fetch SUCCESS — {len(live)} unique competitors found:")
                for c in live:
                    print_live_competitor(c, prefix="│  ")
            else:
                print(f"│    {RED}✗ Returned empty list{RESET}")
        except Exception as e:
            print(f"│    {RED}✗ Error: {e}{RESET}")
            live = []

        # ── Comparison ─────────────────────────────────────────────────────
        if stored_comps and live:
            stored_names = {c.get("provider_name") for c in stored_comps}
            live_names   = {c.get("provider_name") for c in live}
            matching = stored_names & live_names
            if matching == live_names:
                print(f"│  {GREEN}✓ Stored competitors match live data{RESET}")
            else:
                print(f"│  {YELLOW}△ Differences: stored={stored_names} live={live_names}{RESET}")
        elif not stored_comps:
            print(f"│  {RED}✗ No stored data to compare — need to run Reprocess{RESET}")

        print("└" + "─" * 60)
        print()


def clear_market_cache():
    """Delete all documents in the market_cache Firestore collection."""
    if db_manager.db is None:
        print(f"{RED}Firestore not initialized. Check serviceAccountKey.json.{RESET}")
        return

    coll = db_manager.db.collection("market_cache")
    docs = list(coll.stream())
    if not docs:
        print(f"{YELLOW}market_cache is already empty — nothing to delete.{RESET}")
        return

    print(f"{CYAN}Deleting {len(docs)} documents from market_cache...{RESET}")
    for doc in docs:
        doc.reference.delete()
        print(f"  {RED}✗ Deleted:{RESET} {doc.id}")

    print(f"\n{GREEN}✓ market_cache cleared ({len(docs)} docs removed).{RESET}")
    print("  Next call to get_top_competitors will rebuild fresh data from the curated source.")


def list_uids():
    if db_manager.db is None:
        print(f"{RED}Firestore not initialized. Check serviceAccountKey.json.{RESET}")
        return
    docs = db_manager.db.collection("portfolios").stream()
    uids = [d.id for d in docs]
    if not uids:
        print("No portfolios found in Firestore.")
    else:
        print("Available portfolio UIDs:")
        for u in uids:
            print(f"  {u}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  py diagnose_competitors.py [uid]            — run full diagnosis")
        print("  py diagnose_competitors.py --clear-cache    — wipe Firestore market_cache")
        print()
        list_uids()
    elif sys.argv[1] == "--clear-cache":
        clear_market_cache()
    else:
        uid = sys.argv[1]
        asyncio.run(diagnose(uid))
