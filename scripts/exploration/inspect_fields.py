"""
inspect_fields.py
-----------------
Fetches 3 raw records from the Gemel Net API for 'מניות השתלמות'
and prints ALL field names + values so we can verify the correct column mapping.
Run from root: py inspect_fields.py
"""
import httpx
import json

RESOURCE_ID = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
URL = "https://data.gov.il/api/3/action/datastore_search"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

params = {
    "resource_id": RESOURCE_ID,
    "filters": '{"SPECIALIZATION":"מניות", "FUND_CLASSIFICATION":"קרנות השתלמות"}',
    "limit": 3,
}

print("Fetching from API...")
try:
    resp = httpx.get(URL, params=params, headers=headers, timeout=20)
    print(f"HTTP Status: {resp.status_code}")
    data = resp.json()

    if not data.get("success"):
        print("API returned error:")
        print(json.dumps(data.get("error"), ensure_ascii=False, indent=2))
    else:
        records = data["result"]["records"]
        print(f"\nTotal records returned: {data['result']['total']}")
        print(f"Records in this batch: {len(records)}")

        if records:
            print("\n========== FIRST RECORD - ALL FIELDS ==========")
            rec = records[0]
            for k, v in sorted(rec.items()):
                print(f"  {k:45s} = {repr(v)}")

            print("\n========== SECOND RECORD (for comparison) ==========")
            if len(records) > 1:
                rec2 = records[1]
                for k, v in sorted(rec2.items()):
                    print(f"  {k:45s} = {repr(v)}")
        else:
            print("No records returned!")

except Exception as e:
    print(f"Error: {e}")
    # Try without filters as fallback
    print("\nRetrying without filters...")
    params2 = {"resource_id": RESOURCE_ID, "limit": 2}
    resp2 = httpx.get(URL, params=params2, headers=headers, timeout=20)
    print(f"HTTP Status: {resp2.status_code}")
    data2 = resp2.json()
    if data2.get("success") and data2["result"]["records"]:
        rec = data2["result"]["records"][0]
        print("\n========== FIRST RECORD (no filter) - ALL FIELDS ==========")
        for k, v in sorted(rec.items()):
            print(f"  {k:45s} = {repr(v)}")
