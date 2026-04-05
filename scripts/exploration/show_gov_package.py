import urllib.request
import json

package_ids = ['gemelnet', 'pensyanet']
for pid in package_ids:
    url = f'https://data.gov.il/api/3/action/package_show?id={pid}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            result = data.get('result', {})
            print(f"\n--- Package: {result.get('title')} ({pid}) ---")
            for r in result.get('resources', []):
                print(f"  Resource ID: {r.get('id')} | Name: {r.get('name')} | Created: {r.get('created')}")
    except Exception as e:
        print(f'Error showing package {pid}: {e}')
