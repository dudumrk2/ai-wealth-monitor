"""
deep_check2.py - simplified output, no f-string with len()
"""
import httpx

DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
RESOURCE_ID = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

params = {
    "resource_id": RESOURCE_ID,
    "filters": '{"SPECIALIZATION":"\u05de\u05e0\u05d9\u05d5\u05ea", "FUND_CLASSIFICATION":"\u05e7\u05e8\u05e0\u05d5\u05ea \u05d4\u05e9\u05ea\u05dc\u05de\u05d5\u05ea"}',
    "limit": 30000,
}

resp = httpx.get(DATASTORE_URL, params=params, headers=headers, timeout=20)
print("HTTP", resp.status_code)
data = resp.json()
records = data["result"]["records"]
print("Total records:", data["result"]["total"])

# Replicate latest_records grouping
latest_records = {}
for r in records:
    fund_id = str(r.get("FUND_ID", r.get("FUND_NAME", ""))).strip()
    period = str(r.get("REPORT_PERIOD", "000000")).strip()
    if fund_id not in latest_records:
        latest_records[fund_id] = r
    else:
        curr = str(latest_records[fund_id].get("REPORT_PERIOD", "000000")).strip()
        if period > curr:
            latest_records[fund_id] = r

print("Unique funds:", len(latest_records))
print()

# Print each fund as simple key=value lines
for i, (fid, rec) in enumerate(sorted(latest_records.items(), key=lambda x: -(float(x[1].get("YIELD_TRAILING_5_YRS") or 0)))):
    period = rec.get("REPORT_PERIOD")
    y3     = rec.get("YIELD_TRAILING_3_YRS")
    y5     = rec.get("YIELD_TRAILING_5_YRS")
    ytd    = rec.get("YEAR_TO_DATE_YIELD")
    sharpe = rec.get("SHARPE_RATIO")
    avg3   = rec.get("AVG_ANNUAL_YIELD_TRAILING_3YRS")
    assets = rec.get("TOTAL_ASSETS")
    tpop   = rec.get("TARGET_POPULATION")
    fclass = rec.get("FUND_CLASSIFICATION")
    print(f"FUND_{i+1}: id={fid[:12]} period={period} 3Y={y3} 5Y={y5} YTD={ytd} Sharpe={sharpe} AvgAnn3Y={avg3} Assets={assets} tpop={tpop} class={fclass}")

print()
print("=== ALL YIELD-RELATED FIELDS IN FIRST RECORD ===")
first = list(latest_records.values())[0]
for k in sorted(first.keys()):
    if any(x in k.upper() for x in ["YIELD", "SHARPE", "RETURN", "ANNUAL", "TRAIL", "MONTHLY"]):
        print(f"  {k} = {first.get(k)}")
