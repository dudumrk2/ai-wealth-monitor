"""
find_resources2.py - outputs only IDs + numbers (no Hebrew) to avoid encoding issues
"""
import httpx
import json

PACKAGE_SEARCH_URL = "https://data.gov.il/api/3/action/package_search"
DATASTORE_URL = "https://data.gov.il/api/3/action/datastore_search"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

resp = httpx.get(PACKAGE_SEARCH_URL, params={"q": "gemel net"}, headers=headers, timeout=20)
resp2 = httpx.get(PACKAGE_SEARCH_URL, params={"q": "\u05d2\u05de\u05dc \u05e0\u05d8"}, headers=headers, timeout=20)

# Try both queries
data = resp2.json() if resp2.status_code == 200 else resp.json()
resources = data["result"]["results"][0]["resources"]
print(f"FOUND {len(resources)} resources total")
print()

results = []
for r in resources:
    rid = r.get("id", "?")
    name_raw = r.get("name", "?")
    created = r.get("created", "?")[:10]
    # Store name as-is but we'll print IDs only
    results.append({"id": rid, "name": name_raw, "created": created})
    print(f"RESOURCE: id={rid} created={created}")

print()
print("=== Checking latest REPORT_PERIOD for each ===")
for r in results:
    rid = r["id"]
    try:
        p = {
            "resource_id": rid,
            "limit": 1,
            "sort": "REPORT_PERIOD desc",
            "fields": "REPORT_PERIOD,YIELD_TRAILING_3_YRS,YIELD_TRAILING_5_YRS,SHARPE_RATIO,AVG_ANNUAL_YIELD_TRAILING_3YRS,YEAR_TO_DATE_YIELD"
        }
        r2 = httpx.get(DATASTORE_URL, params=p, headers=headers, timeout=15)
        code = r2.status_code
        if code == 200:
            d2 = r2.json()
            if d2.get("success") and d2["result"]["records"]:
                rec = d2["result"]["records"][0]
                period = rec.get("REPORT_PERIOD", "?")
                y3 = rec.get("YIELD_TRAILING_3_YRS", "N/A")
                y5 = rec.get("YIELD_TRAILING_5_YRS", "N/A")
                sharpe = rec.get("SHARPE_RATIO", "N/A")
                ytd = rec.get("YEAR_TO_DATE_YIELD", "N/A")
                avg3 = rec.get("AVG_ANNUAL_YIELD_TRAILING_3YRS", "N/A")
                total = d2["result"]["total"]
                print(f"  OK  id={rid} period={period} total_records={total} 3Y={y3} 5Y={y5} Sharpe={sharpe} YTD={ytd} AvgAnn3Y={avg3}")
            else:
                err = d2.get("error", "?")
                print(f"  EMPTY id={rid} err={err}")
        else:
            print(f"  HTTP_{code} id={rid}")
    except Exception as e:
        print(f"  EXCEPT id={rid} err={e}")

print()
print("Done.")
