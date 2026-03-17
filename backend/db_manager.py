import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

# Global DB client placeholder
db = None

# Initialize Firebase Admin
def initialize_firebase():
    global db
    if firebase_admin._apps:
        if db is None:
            try:
                db = firestore.client()
            except:
                pass
        return

    # Define possible search paths for the key
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    search_paths = [
        os.path.join(current_dir, "serviceAccountKey.json"),
        os.path.join(project_root, "serviceAccountKey.json"),
        os.path.join(os.getcwd(), "serviceAccountKey.json"),
        os.path.join(os.getcwd(), "backend", "serviceAccountKey.json")
    ]
    
    key_path = None
    for path in search_paths:
        exists = os.path.exists(path)
        print(f"🔍 [DB_MANAGER] Checking: {path} -> {'Found' if exists else 'Not Found'}")
        if exists:
            key_path = path
            break
            
    if key_path:
        try:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase Admin initialized using {key_path}")
            db = firestore.client()
        except Exception as e:
            print(f"💥 Error initializing Firebase with credentials at {key_path}: {e}")
    else:
        print(f"❌ WARNING: Firebase serviceAccountKey.json not found in any of: {search_paths}")
        print("Firestore features and real Auth verification will be unavailable.")

initialize_firebase()

import json

def get_family_profile(uid: str):
    """
    Fetch family PII and financial profile from Firestore.
    """
    print(f"\n🔍 [DB_MANAGER] Fetching family profile for UID: {uid}...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized (missing key). Skipping fetch.")
        return None
    try:
        doc_ref = db.collection("families").document(uid)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            # Handle Firestore timestamps (DatetimeWithNanoseconds) for JSON serialization
            for key, value in data.items():
                if hasattr(value, 'isoformat'):
                    data[key] = value.isoformat()
            
            print(f"✅ [DB_MANAGER] Profile found for {uid}:")
            # print(json.dumps(data, indent=2, ensure_ascii=False)) # Commented out to avoid serialization issues in logs
            return {
                "pii_data": data.get("pii_data", {}),
                "financial_profile": data.get("financial_profile", {})
            }
        else:
            print(f"❌ [DB_MANAGER] Family profile for UID {uid} NOT FOUND.")
            return None
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error fetching family profile: {e}")
        return None

def get_processed_portfolio(uid: str):
    """
    Fetch the final processed portfolio from the 'portfolios' collection.
    """
    print(f"\n📂 [DB_MANAGER] Fetching processed portfolio for UID: {uid}...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized (missing key). Skipping fetch.")
        return None
    try:
        doc_ref = db.collection("portfolios").document(uid)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            print(f"✅ [DB_MANAGER] Processed portfolio found for {uid}")
            return data
        else:
            print(f"❌ [DB_MANAGER] Processed portfolio for UID {uid} NOT FOUND.")
            return None
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error fetching processed portfolio: {e}")
        return None

def save_processed_portfolio(uid: str, portfolio_data: dict):
    """
    Save the final processed portfolio JSON to the 'portfolios' collection.
    """
    print(f"\n💾 [DB_MANAGER] Saving processed portfolio for UID: {uid}...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized (missing key). Skipping save.")
        return False
    # print(f"DEBUG DATA: {json.dumps(portfolio_data, indent=2, ensure_ascii=False)}")
    try:
        doc_ref = db.collection("portfolios").document(uid)
        doc_ref.set(portfolio_data)
        print(f"✅ [DB_MANAGER] Successfully saved portfolio for {uid}")
        print("--- SAVED DATA PREVIEW ---")
        # Print a summary or first few items to avoid giant logs in terminal but still show it's working
        print(f"Keys saved: {list(portfolio_data.keys())}")
        print(f"Action items count: {len(portfolio_data.get('action_items', []))}")
        print(f"Funds count (user): {len(portfolio_data.get('portfolios', {}).get('user', {}).get('funds', []))}")
        print("--- END PREVIEW ---")
        return True
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error saving portfolio: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Market Data Cache  (Stale-While-Revalidate pattern)
# Collection: market_cache / Document ID: track_name
# ──────────────────────────────────────────────────────────────────────────────

def save_market_cache(track_name: str, data: list) -> bool:
    """
    Persist a list of top-competitor dicts to Firestore for a given track.

    Document path: market_cache/{track_name}
    Fields stored:
      - competitors  : the raw list of competitor dicts
      - last_updated : Firestore server timestamp

    Returns True on success, False otherwise.
    """
    print(f"\n💾 [DB_MANAGER] Saving market cache for track: '{track_name}'...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized. Skipping market cache save.")
        return False
    try:
        doc_ref = db.collection("market_cache").document(track_name)
        doc_ref.set({
            "competitors": data,
            "last_updated": firestore.SERVER_TIMESTAMP,
        })
        print(f"✅ [DB_MANAGER] Market cache saved for track '{track_name}' ({len(data)} competitors).")
        return True
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error saving market cache for '{track_name}': {e}")
        return False


def get_market_cache(track_name: str):
    """
    Retrieve the cached competitor list from Firestore for a given track.

    Returns:
      list  – the cached competitors list if found.
      None  – if the document does not exist or Firestore is unavailable.
    """
    print(f"\n🔍 [DB_MANAGER] Fetching market cache for track: '{track_name}'...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized. Skipping market cache fetch.")
        return None
    try:
        doc_ref = db.collection("market_cache").document(track_name)
        doc = doc_ref.get()
        if doc.exists:
            cached = doc.to_dict().get("competitors")
            print(f"✅ [DB_MANAGER] Market cache HIT for '{track_name}' ({len(cached or [])} competitors).")
            return cached
        print(f"ℹ️ [DB_MANAGER] Market cache MISS for '{track_name}' – no document found.")
        return None
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error reading market cache for '{track_name}': {e}")
        return None
