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
        print("💡 Attempting to initialize Firebase using Application Default Credentials (suitable for Cloud Run/Render)...")
        try:
            firebase_admin.initialize_app()
            print("✅ Firebase Admin initialized using Application Default Credentials.")
            db = firestore.client()
        except Exception as e:
            print(f"💥 Error initializing Firebase with ADC: {e}")
            print("Firestore features and real Auth verification will be unavailable.")

initialize_firebase()

import json

def get_family_profile(uid: str):
    """
    Fetch family PII, financial profile, gmail_refresh_token, and all member
    idNumbers from Firestore.

    Returns a dict with:
      - pii_data            : dict (legacy map, may be empty)
      - financial_profile   : dict
      - gmail_refresh_token : str | None
      - member_id_numbers   : list[str]  — all idNumbers across all family members
    """
    print(f"\n🔍 [DB_MANAGER] Fetching family profile for UID: {uid}...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized (missing key). Skipping fetch.")
        return None
    try:
        doc_ref = db.collection("families").document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            print(f"❌ [DB_MANAGER] Family profile for UID {uid} NOT FOUND.")
            return None

        data = doc.to_dict()
        # Serialise any Firestore timestamps
        for key, value in data.items():
            if hasattr(value, 'isoformat'):
                data[key] = value.isoformat()

        # ── Collect all member ID numbers ─────────────────────────────────────
        member_id_numbers: list = []

        # 1. Try `members` sub-collection first (preferred path)
        try:
            members_ref = doc_ref.collection("members")
            members_docs = members_ref.stream()
            for m_doc in members_docs:
                m_data = m_doc.to_dict() or {}
                id_num = m_data.get("idNumber", "")
                if id_num:
                    member_id_numbers.append(id_num)
                    # Also add version without leading zero
                    if id_num.startswith("0"):
                        member_id_numbers.append(id_num[1:])
            print(f"✅ [DB_MANAGER] Found {len(member_id_numbers)} ID(s) from members sub-collection.")
        except Exception as sub_err:
            print(f"⚠️ [DB_MANAGER] Could not read members sub-collection: {sub_err}")

        # 2. Fallback: legacy `pii_data` map (member1/member2 keys)
        if not member_id_numbers:
            pii_data = data.get("pii_data", {})
            for m_key in ["member1", "member2"]:
                id_num = pii_data.get(m_key, {}).get("idNumber", "")
                if id_num:
                    member_id_numbers.append(id_num)
                    if id_num.startswith("0"):
                        member_id_numbers.append(id_num[1:])
            if member_id_numbers:
                print(f"✅ [DB_MANAGER] Found {len(member_id_numbers)} ID(s) from pii_data map (fallback).")

        print(f"✅ [DB_MANAGER] Profile found for {uid}.")
        return {
            "pii_data": data.get("pii_data", {}),
            "financial_profile": data.get("financial_profile", {}),
            "gmail_refresh_token": data.get("gmail_refresh_token"),
            "member_id_numbers": list(dict.fromkeys(member_id_numbers)),  # deduplicate, preserve order
            # Gmail search & schedule settings
            "gmail_sender_email": data.get("gmail_sender_email"),
            "gmail_subject": data.get("gmail_subject"),
            "cron_day": data.get("cron_day"),
            "cron_frequency_months": data.get("cron_frequency_months"),
            "last_fetched_at": data.get("last_fetched_at"),
        }
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

def get_all_family_uids() -> list:
    """
    Return UIDs of all family documents in Firestore that have a
    `gmail_refresh_token` field set. Used by the cron endpoint to
    automatically find and process every Gmail-enabled family.
    """
    print("\n🔍 [DB_MANAGER] Fetching all Gmail-enabled family UIDs...")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized. Skipping.")
        return []
    try:
        # Filter server-side: only families where gmail_refresh_token exists and is non-empty
        docs = (
            db.collection("families")
            .where("gmail_refresh_token", "!=", "")
            .stream()
        )
        uids = [doc.id for doc in docs]
        print(f"✅ [DB_MANAGER] Found {len(uids)} Gmail-enabled family/families.")
        return uids
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error fetching Gmail-enabled family UIDs: {e}")
        return []

def save_gmail_token(uid: str, refresh_token: str) -> bool:
    """Save (or overwrite) the gmail_refresh_token for a family document."""
    print(f"\n🔐 [DB_MANAGER] Saving Gmail refresh token for UID: {uid}")
    if db is None:
        print("⚠️ [DB_MANAGER] Firestore not initialized.")
        return False
    try:
        db.collection("families").document(uid).update({"gmail_refresh_token": refresh_token})
        print(f"✅ [DB_MANAGER] Gmail token saved for {uid}.")
        return True
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error saving Gmail token: {e}")
        return False

def update_family_field(uid: str, field: str, value) -> bool:
    """Update a single top-level field on a family document."""
    if db is None:
        return False
    try:
        db.collection("families").document(uid).update({field: value})
        return True
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error updating field '{field}' for {uid}: {e}")
        return False

def has_gmail_token(uid: str) -> bool:
    """Return True if the family has a non-empty gmail_refresh_token."""
    if db is None:
        return False
    try:
        doc = db.collection("families").document(uid).get()
        if doc.exists:
            token = doc.to_dict().get("gmail_refresh_token", "")
            return bool(token)
        return False
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error checking Gmail token for {uid}: {e}")
        return False

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


import datetime

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
            data = doc.to_dict()
            last_updated = data.get("last_updated")
            if last_updated:
                # Firestore timestamp comes back as an aware datetime object
                now = datetime.datetime.now(datetime.timezone.utc)
                try:
                    if (now - last_updated).days > 30:
                        print(f"ℹ️ [DB_MANAGER] Market cache STALE (>30 days) for '{track_name}'.")
                        return None
                except Exception as ex:
                    print(f"⚠️ [DB_MANAGER] Error comparing dates: {ex}")
                    
            cached = data.get("competitors")
            print(f"✅ [DB_MANAGER] Market cache HIT for '{track_name}' ({len(cached or [])} competitors).")
            return cached
        print(f"ℹ️ [DB_MANAGER] Market cache MISS for '{track_name}' – no document found.")
        return None
    except Exception as e:
        print(f"💥 [DB_MANAGER] Error reading market cache for '{track_name}': {e}")
        return None
