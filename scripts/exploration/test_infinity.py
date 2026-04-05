import urllib.request
import json
for pkg_name in ['%D7%92%D7%9E%D7%9C-%D7%A0%D7%98', '%D7%A4%D7%A0%D7%A1%D7%99%D7%94-%D7%A0%D7%98']:
    url = f'https://data.gov.il/api/3/action/package_search?q={pkg_name}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            for p in data.get('result', {}).get('results', []):
                print(f"\n--- Package: {p.get('title')} ---")
                for r in p.get('resources', []):
                    print(f"{r.get('id')}  |  {r.get('name')}")
    except Exception as e:
        print('Error:', e)
