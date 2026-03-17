
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Setup Firebase
current_dir = os.path.dirname(os.path.abspath(__file__))
# Note: In the real env, it might be in root or backend
service_account_path = os.path.join(current_dir, "serviceAccountKey.json")
if not os.path.exists(service_account_path):
    service_account_path = os.path.join(os.path.dirname(current_dir), "serviceAccountKey.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def inspect_firestore():
    print("--- FIRESTORE INSPECTION ---")
    collections = ["families", "portfolios"]
    for coll_name in collections:
        print(f"\nCollection: {coll_name}")
        docs = db.collection(coll_name).stream()
        found = False
        for doc in docs:
            found = True
            print(f"  - Document ID: {doc.id}")
            # print(f"    Data: {json.dumps(doc.to_dict(), indent=2, ensure_ascii=False)[:200]}...")
        if not found:
            print("  (Empty)")

if __name__ == "__main__":
    inspect_firestore()
