import httpx
import json

RESOURCE_ID = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
URL = "https://data.gov.il/api/3/action/datastore_search"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

params = {
    "resource_id": RESOURCE_ID,
    "limit": 100,
    "q": "אנליסט השתלמות מניות",
    "sort": "REPORT_PERIOD desc",
}

print("Searching for Analyst...")
resp = httpx.get(URL, params=params, headers=headers, timeout=20)
data = resp.json()

if data.get("success"):
    records = data["result"]["records"]
    for rec in records:
        print(f"\n--- {rec.get('FUND_NAME')} ---")
        print(f"REPORT_PERIOD: {rec.get('REPORT_PERIOD')}")
        print(f"YIELD_TRAILING_3_YRS: {rec.get('YIELD_TRAILING_3_YRS')}")
        print(f"YIELD_TRAILING_5_YRS: {rec.get('YIELD_TRAILING_5_YRS')}")
        print(f"YEAR_TO_DATE_YIELD: {rec.get('YEAR_TO_DATE_YIELD')}")
        print(f"AVG_ANNUAL_YIELD_TRAILING_3YRS: {rec.get('AVG_ANNUAL_YIELD_TRAILING_3YRS')}")
        print(f"SHARPE_RATIO: {rec.get('SHARPE_RATIO')}")
else:
    print("API Error")
