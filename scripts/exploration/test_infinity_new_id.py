import urllib.request
import json

# Target: Gemel Net 2024-Present
resource_id = 'a30dcbea-a1d2-482c-ae29-8f781f5025fb'
# Infinity Fund ID
fund_id = '1537'

url = f'https://data.gov.il/api/3/action/datastore_search?resource_id={resource_id}&filters=%7B%22FUND_ID%22:%22{fund_id}%22%7D&sort=REPORT_PERIOD%20desc&limit=5'

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        records = data.get('result', {}).get('records', [])
        print(f"--- Data for Fund {fund_id} from Resource {resource_id} ---")
        for i, r in enumerate(records):
            print(f"[{i}] PERIOD={r.get('REPORT_PERIOD')} 1Y={r.get('YEAR_TO_DATE_YIELD')} 3Y_CUM={r.get('YIELD_TRAILING_3_YRS')} 5Y_CUM={r.get('YIELD_TRAILING_5_YRS')}")
except Exception as e:
    print('Error:', e)
