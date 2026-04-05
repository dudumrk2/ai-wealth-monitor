"""
find_resources.py - Unicode-safe version
"""
import httpx
import sys
import io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PACKAGE_SEARCH_URL = "https://data.gov.il/api/3/action/package_search"
DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print("=== Step 1: Fetching Gemel Net package resources ===")
resp = httpx.get(PACKAGE_SEARCH_URL, params={"q": "גמל נט"}, headers=headers, timeout=20)
print(f"Status: {resp.status_code}")
data = resp.json()

resources = data["result"]["results"][0]["resources"]
print(f"\nFound {len(resources)} resources:\n")

for r in resources:
    print(f"  NAME='{r.get('name', '?')}'  ID={r.get('id')}  Created={r.get('created','?')[:10]}")

print("\n=== Step 2: Checking latest REPORT_PERIOD for each resource ===\n")

for r in resources:
    rid = r.get("id")
    name = r.get("name", "?")
    try:
        p = {
            "resource_id": rid,
            "limit": 1,
            "sort": "REPORT_PERIOD desc",
            "fields": "REPORT_PERIOD,FUND_NAME,MANAGING_CORPORATION,YIELD_TRAILING_3_YRS,YIELD_TRAILING_5_YRS,SHARPE_RATIO,AVG_ANNUAL_YIELD_TRAILING_3YRS"
        }
        r2 = httpx.get(DATASTORE_URL, params=p, headers=headers, timeout=15)
        if r2.status_code == 200:
            d2 = r2.json()
            if d2.get("success") and d2["result"]["records"]:
                rec = d2["result"]["records"][0]
                period = rec.get("REPORT_PERIOD", "?")
                corp = rec.get("MANAGING_CORPORATION", "?")
                y3 = rec.get("YIELD_TRAILING_3_YRS", "?")
                y5 = rec.get("YIELD_TRAILING_5_YRS", "?")
                sharpe = rec.get("SHARPE_RATIO", "?")
                avg3 = rec.get("AVG_ANNUAL_YIELD_TRAILING_3YRS", "?")
                print(f"  [{period}] ID={rid}  Corp={corp}  3Y={y3}  5Y={y5}  Sharpe={sharpe}  AvgAnnual3Y={avg3}")
            else:
                print(f"  [NO RECORDS] ID={rid}  Name={name}  err={d2.get('error')}")
        else:
            print(f"  [HTTP {r2.status_code}] ID={rid}  Name={name}")
    except Exception as e:
        print(f"  [EXCEPTION] ID={rid} | {e}")
