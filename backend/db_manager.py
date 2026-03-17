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
