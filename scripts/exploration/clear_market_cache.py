import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

# Add the current directory to sys.path so we can import our modules if needed
sys.path.append(os.getcwd())

def initialize_firebase():
    # Try multiple possible paths for the service account key
    possible_paths = [
        "serviceAccountKey.json",
        os.path.join("backend", "serviceAccountKey.json"),
        os.path.join("..", "backend", "serviceAccountKey.json")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"🔑 Using service account key from: {path}")
            cred = credentials.Certificate(path)
            firebase_admin.initialize_app(cred)
            return True
            
    print("⚠️ No service account key found. Attempting Application Default Credentials...")
    try:
        firebase_admin.initialize_app()
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        return False

if __name__ == "__main__":
    if not initialize_firebase():
        sys.exit(1)

    db = firestore.client()
    collection_ref = db.collection("market_cache")

    print("🔍 [CACHE] Clearing market_cache...")
    docs = collection_ref.stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1

    print(f"✅ Successfully deleted {count} document(s) from 'market_cache'.")
    print("🚀 The next dashboard refresh will now use the new classification filters (2026 data).")
