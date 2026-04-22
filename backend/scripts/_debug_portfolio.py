"""Quick diagnostic script to print the raw Firestore portfolio data."""
import sys, os, json

# Find the first argument as UID, or prompt
uid = sys.argv[1] if len(sys.argv) > 1 else input("Enter UID: ").strip()

import db_manager

data = db_manager.get_processed_portfolio(uid)
if not data:
    print("No data found for UID:", uid)
    sys.exit(1)

for owner in ["user", "spouse"]:
    funds = data.get("portfolios", {}).get(owner, {}).get("funds", [])
    total = sum(f.get("balance", 0) for f in funds)
    print(f"\n{'='*60}")
    print(f"  OWNER: {owner.upper()}  |  {len(funds)} funds  |  total balance: {total:,.0f}")
    print(f"{'='*60}")
    for f in funds:
        print(f"  [{f.get('category','?'):22s}] {f.get('provider_name',''):30s} | {f.get('track_name','')[:30]:30s} | balance={f.get('balance',0):>12,.0f} | policy={f.get('policy_number','')}")
