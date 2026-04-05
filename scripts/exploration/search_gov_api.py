import urllib.request
import json

queries = ['%D7%92%D7%9E%D7%9C%20%D7%A0%D7%98', '%D7%A4%D7%A0%D7%A1%D7%99%D7%94%20%D7%A0%D7%98']
for query in queries:
    url = f'https://data.gov.il/api/3/action/package_search?q={query}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            results = data.get('result', {}).get('results', [])
            for p in results:
                print(f"Title: {p.get('title')} | Name/ID: {p.get('name')}")
                for r in p.get('resources', []):
                    print(f"  Resource ID: {r.get('id')} | Name: {r.get('name')}")
    except Exception as e:
        print(f'Error searching {query}: {e}')
