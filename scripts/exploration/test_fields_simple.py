import urllib.request
import json

resource_id = 'a30dcbea-a1d2-482c-ae29-8f781f5025fb'

# No sort, just limit 1 to see fields
url = f'https://data.gov.il/api/3/action/datastore_search?resource_id={resource_id}&limit=1'

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        fields = data.get('result', {}).get('fields', [])
        print("--- Fields in Resource ---")
        for f in fields:
            print(f"{f.get('id')} ({f.get('type')})")
except Exception as e:
    print('Error:', e)
