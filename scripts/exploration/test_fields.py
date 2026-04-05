import urllib.request
import json

resource_id = 'a30dcbea-a1d2-482c-ae29-8f781f5025fb'
fund_id = '1537'

url = f'https://data.gov.il/api/3/action/datastore_search?resource_id={resource_id}&filters=%7B%22FUND_ID%22:%22{fund_id}%22%7D&sort=REPORT_PERIOD%20desc&limit=1'

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        records = data.get('result', {}).get('records', [])
        if records:
            r = records[0]
            for k, v in r.items():
                print(f"{k}: {v}")
except Exception as e:
    print('Error:', e)
