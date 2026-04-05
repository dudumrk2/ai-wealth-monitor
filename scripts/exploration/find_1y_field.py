"""
find_1y_field.py
-----------------
Searches for a field that might represent the 1-year yield (20-40 range for stock funds).
"""
import httpx
import json

RESOURCE_ID = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
URL = "https://data.gov.il/api/3/action/datastore_search"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

params = {
    "resource_id": RESOURCE_ID,
    "limit": 100,
    "sort": "REPORT_PERIOD desc",
}

print("Searching for 1Y yield field...")
resp = httpx.get(URL, params=params, headers=headers, timeout=20)
data = resp.json()

if data.get("success"):
    records = data["result"]["records"]
    # Look for records that have 3Y around 70-90% (Stock funds)
    for rec in records:
        y3 = float(rec.get("YIELD_TRAILING_3_YRS") or 0)
        if y3 > 50:
            print(f"\n--- Probable Stock Fund: {rec.get('FUND_NAME')} ---")
            print(f"REPORT_PERIOD: {rec.get('REPORT_PERIOD')}")
            print(f"YIELD_TRAILING_3_YRS: {y3}")
            print("Fields with values between 15 and 45 (Potential 1Y yield):")
            for k, v in rec.items():
                try:
                    vf = float(v)
                    if 15 <= vf <= 45:
                        print(f"  {k}: {v}")
                except:
                    pass
else:
    print("API Error")
