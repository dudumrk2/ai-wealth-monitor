import urllib.request
import json

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

output_lines = []

# 1. Broad Search
search_queries = ['גמל נט', 'פנסיה נט', 'גמל-נט', 'פנסיה-נט']
output_lines.append("--- BROAD SEARCH ---")
for q in search_queries:
    encoded_q = urllib.parse.quote(q)
    url = f'https://data.gov.il/api/3/action/package_search?q={encoded_q}'
    try:
        data = get_json(url)
        results = data.get('result', {}).get('results', [])
        for p in results:
            output_lines.append(f"[{q}] Package Title: {p.get('title')} | Name: {p.get('name')}")
    except Exception as e:
        output_lines.append(f"Error searching {q}: {e}")

# 2. Focused Show
potential_ids = ['gemelnet', 'pensia-net', 'pensyanet', 'pension-net', 'gemel-net', 'pensionnet']
output_lines.append("\n--- FOCUSED SHOW ---")
for pid in potential_ids:
    url = f'https://data.gov.il/api/3/action/package_show?id={pid}'
    try:
        data = get_json(url)
        res = data.get('result', {})
        output_lines.append(f"Package: {res.get('title')} ({pid})")
        for r in res.get('resources', []):
             output_lines.append(f"  ID: {r.get('id')} | Name: {r.get('name')} | Format: {r.get('format')} | Created: {r.get('created')}")
    except Exception as e:
        if '404' not in str(e):
             output_lines.append(f"Error checking {pid}: {e}")

with open('gov_api_discovery.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))
