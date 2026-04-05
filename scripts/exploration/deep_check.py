"""
deep_check.py - Check actual values fetched by market_data logic for a real fund,
and trace the full pipeline to find why 3Y is wrong and Sharpe is missing.
"""
import httpx
import json

DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
RESOURCE_ID = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Query exactly as market_data.py does it
params = {
    "resource_id": RESOURCE_ID,
    "filters": '{"SPECIALIZATION":"\u05de\u05e0\u05d9\u05d5\u05ea", "FUND_CLASSIFICATION":"\u05e7\u05e8\u05e0\u05d5\u05ea \u05d4\u05e9\u05ea\u05dc\u05de\u05d5\u05ea"}',
    "limit": 30000,
}

print("Fetching with same params as market_data.py...")
resp = httpx.get(DATASTORE_URL, params=params, headers=headers, timeout=20)
print(f"HTTP {resp.status_code}")

if resp.status_code != 200:
    print("FAILED. Trying without filters...")
    params2 = {"resource_id": RESOURCE_ID, "limit": 5, "sort": "REPORT_PERIOD desc"}
    resp = httpx.get(DATASTORE_URL, params=params2, headers=headers, timeout=20)
    print(f"Fallback HTTP {resp.status_code}")

data = resp.json()
if not data.get("success"):
    print("API error:", data.get("error"))
    exit(1)

records = data["result"]["records"]
total = data["result"]["total"]
print(f"Total records returned: {total}")

# Replicate the latest_records grouping from market_data.py
latest_records = {}
for r in records:
    fund_id = str(r.get("FUND_ID", r.get("FUND_NAME", ""))).strip()
    period = str(r.get("REPORT_PERIOD", "000000")).strip()
    if fund_id not in latest_records:
        latest_records[fund_id] = r
    else:
        curr_period = str(latest_records[fund_id].get("REPORT_PERIOD", "000000")).strip()
        if period > curr_period:
            latest_records[fund_id] = r

print(f"Unique funds after latest_records grouping: {len(latest_records)}")
print()

# Print each fund's latest record data
print("=== FUND SUMMARY (latest period per fund) ===")
for fund_id, rec in sorted(latest_records.items(), key=lambda x: -(float(x[1].get("YIELD_TRAILING_5_YRS") or 0))):
    period = rec.get("REPORT_PERIOD", "?")
    corp = rec.get("MANAGING_CORPORATION", "?")
    y3   = rec.get("YIELD_TRAILING_3_YRS", "N/A")
    y5   = rec.get("YIELD_TRAILING_5_YRS", "N/A")
    ytd  = rec.get("YEAR_TO_DATE_YIELD", "N/A")
    sharpe = rec.get("SHARPE_RATIO", "N/A")
    avg3 = rec.get("AVG_ANNUAL_YIELD_TRAILING_3YRS", "N/A")
    assets = rec.get("TOTAL_ASSETS", "?")
    fname = str(rec.get("FUND_NAME", "?"))[:8]  # short ID to avoid encoding
    fclass = rec.get("FUND_CLASSIFICATION", "?")[:5]
    print(f"  period={period} 3Y={y3:>7} 5Y={y5:>7} YTD={ytd:>6} Sharpe={sharpe:>5} AvgAnn3Y={avg3:>6} Assets={assets:>8}  corp_len={len(str(corp))} fund={fund_id[:15]}")

print()
print("=== CHECKING SPECIFIC FIELDS IN FIRST RECORD ===")
if latest_records:
    first = list(latest_records.values())[0]
    # Check all yield-related fields
    yield_fields = [k for k in first.keys() if any(x in k.upper() for x in ["YIELD", "SHARPE", "RETURN", "ANNUAL", "TRAILING"])]
    print("All yield/return fields found:")
    for f in sorted(yield_fields):
        print(f"  {f} = {first.get(f)}")
