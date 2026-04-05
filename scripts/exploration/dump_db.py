import json
import db_manager

db_manager.initialize_firebase()
uid = '414PiKcFOWRO0PNRAfuVsD3fqoV2'
portfolio = db_manager.get_processed_portfolio(uid)

with open("claude_raw_dump.json", "w", encoding="utf-8") as f:
    json.dump(portfolio, f, indent=2, ensure_ascii=False)

print("✅ Dumped portfolio to claude_raw_dump.json")
