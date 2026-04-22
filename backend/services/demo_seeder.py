import db_manager
import datetime
import config
import copy
from services.demo_constants import (
    DEMO_FAMILY_PROFILE,
    DEMO_PORTFOLIO_DATA,
    DEMO_ALT_INVESTMENT
)

def seed_demo_data():
    """Seed the demo user with realistic data from constants in Firestore."""
    uid = config.DEMO_UID
    print(f"🌱 [DEMO_SEEDER] Seeding data for {uid}...")

    # 1. Family Profile
    profile = copy.deepcopy(DEMO_FAMILY_PROFILE)
    profile["created_at"] = datetime.datetime.now().isoformat()
    db_manager.save_family_profile(uid, profile)

    # 2. Processed Portfolio
    portfolio = copy.deepcopy(DEMO_PORTFOLIO_DATA)
    portfolio["last_updated"] = datetime.datetime.now().isoformat()
    db_manager.save_processed_portfolio(uid, portfolio)

    # 3. Alternative Investment (Cleanup duplicates first)
    try:
        alt_coll = db_manager.db.collection("families").document(uid).collection("alt_projects")
        docs = alt_coll.list_documents()
        for doc in docs:
            doc.delete()
    except Exception as e:
        print(f"⚠️ [DEMO_SEEDER] Could not clear alt_projects: {e}")

    db_manager.add_alt_project(uid, copy.deepcopy(DEMO_ALT_INVESTMENT))

    print(f"✅ [DEMO_SEEDER] Seeding complete for {uid}")

if __name__ == "__main__":
    seed_demo_data()
