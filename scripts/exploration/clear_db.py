import db_manager

uid = '414PiKcFOWRO0PNRAfuVsD3fqoV2'
print("🧹 Clearing corrupted/duplicate portfolio data...")
db_manager.initialize_firebase()
db_manager.save_processed_portfolio(uid, {
    "uid": uid,
    "last_updated": "2024-03-24T00:00:00Z",
    "portfolios": {
        "user": {"funds": []},
        "spouse": {"funds": []}
    },
    "action_items": []
})
print("✅ Database cleared. Ready for a clean upload!")
