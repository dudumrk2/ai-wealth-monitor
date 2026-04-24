"""
Migration Script: Add ownerName to root portfolio objects
==========================================================
For each family in Firestore, this script:
1. Reads member names from families/{uid}.pii_data.member1/member2
2. Reads the portfolios/{uid} document
3. Sets portfolios.user.ownerName  = member1.name
   Sets portfolios.spouse.ownerName = member2.name
4. Saves back to Firestore with merge=True

Run from the backend directory:
    cd backend
    python scripts/migrate_owner_names.py

Safe to run multiple times (idempotent).
"""

import sys
import os

# Force UTF-8 output on Windows to avoid encoding errors
if hasattr(sys.stdout, 'buffer'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'serviceAccountKey.json')
if not os.path.exists(key_path):
    print(f"[ERROR] serviceAccountKey.json not found at: {key_path}")
    sys.exit(1)

cred = credentials.Certificate(key_path)
firebase_admin.initialize_app(cred)
db = firestore.client()
print("[OK] Firebase connected.\n")


def run_migration():
    families_ref = db.collection("families")
    families = list(families_ref.stream())
    print(f"[INFO] Found {len(families)} family document(s) to process.\n")

    updated = 0
    skipped = 0
    errors = 0

    for family_doc in families:
        uid = family_doc.id
        family_data = family_doc.to_dict() or {}

        # Skip demo user
        if uid == "demo":
            print(f"[SKIP] [{uid}] demo user")
            skipped += 1
            continue

        # Get member names from pii_data (primary path) or top-level fallback
        pii = family_data.get("pii_data") or family_data
        m1_name = (pii.get("member1") or {}).get("name", "").strip()
        m2_name = (pii.get("member2") or {}).get("name", "").strip()

        if not m1_name:
            print(f"[WARN] [{uid}] No member1 name found -- skipping.")
            skipped += 1
            continue

        print(f"[INFO] [{uid}] member1='{m1_name}', member2='{m2_name or '(none)'}'")

        # Read portfolio document
        portfolio_ref = db.collection("portfolios").document(uid)
        portfolio_snap = portfolio_ref.get()

        if not portfolio_snap.exists:
            print(f"       [WARN] No portfolios document -- skipping.")
            skipped += 1
            continue

        portfolios = (portfolio_snap.to_dict() or {}).get("portfolios", {})
        changes = {}

        # user slot
        user_slot = portfolios.get("user") or {}
        current_user_name = user_slot.get("ownerName", "")
        if current_user_name != m1_name:
            changes["portfolios.user.ownerName"] = m1_name
            print(f"       [EDIT] user.ownerName: '{current_user_name}' -> '{m1_name}'")
        else:
            print(f"       [OK]   user.ownerName already '{m1_name}'")

        # spouse slot (only if member2 name exists)
        if m2_name:
            spouse_slot = portfolios.get("spouse") or {}
            current_spouse_name = spouse_slot.get("ownerName", "")
            if current_spouse_name != m2_name:
                changes["portfolios.spouse.ownerName"] = m2_name
                print(f"       [EDIT] spouse.ownerName: '{current_spouse_name}' -> '{m2_name}'")
            else:
                print(f"       [OK]   spouse.ownerName already '{m2_name}'")

        # Apply
        if changes:
            try:
                portfolio_ref.update(changes)
                print(f"       [SAVE] {len(changes)} field(s) saved.")
                updated += 1
            except Exception as e:
                print(f"       [ERROR] {e}")
                errors += 1
        else:
            print(f"       [--]   No changes needed.")
            skipped += 1

        print()

    print("=" * 50)
    print(f"Migration complete.")
    print(f"  Updated : {updated}")
    print(f"  Skipped : {skipped}")
    print(f"  Errors  : {errors}")


if __name__ == "__main__":
    run_migration()
