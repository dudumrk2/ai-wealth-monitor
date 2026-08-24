import db_manager
import datetime
import config
import copy
from services.demo_constants import (
    get_demo_family_profile,
    get_demo_portfolio_data,
    get_demo_insurance_chunks,
    DEMO_INSURANCE_CHUNKS_EN,
    DEMO_INSURANCE_CHUNKS_HE,
    DEMO_ALT_INVESTMENT,
    is_english_demo_enabled
)

def seed_demo_data(lang: str | None = None):
    """Seed the demo user with realistic data from constants in Firestore."""
    uid = config.DEMO_UID
    target_lang = lang if lang else ("en" if is_english_demo_enabled() else "he")
    print(f"🌱 [DEMO_SEEDER] Seeding demo data for {uid} (lang={target_lang})...")

    # 1. Family Profile
    profile = copy.deepcopy(get_demo_family_profile(target_lang))
    profile["created_at"] = datetime.datetime.now().isoformat()
    db_manager.save_family_profile(uid, profile)

    # 2. Processed Portfolio
    portfolio = copy.deepcopy(get_demo_portfolio_data(target_lang))
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

    # 4. Seed Insurance Policy RAG chunks (Seeds both EN & HE chunks)
    try:
        combined_chunks = copy.deepcopy(DEMO_INSURANCE_CHUNKS_EN + DEMO_INSURANCE_CHUNKS_HE)
        for c in combined_chunks:
            c["chunk_id"] = c.get("chunk_id", c.get("id"))
            c["text"] = c.get("text", c.get("content", ""))
        try:
            from rag_utils import embed_documents
            texts = [c.get("text", "") for c in combined_chunks]
            embeddings = embed_documents(texts)
            for c, emb in zip(combined_chunks, embeddings):
                c["embedding"] = emb
            print(f"✨ [DEMO_SEEDER] Generated live embeddings for {len(combined_chunks)} demo policy chunks")
        except Exception as emb_err:
            print(f"ℹ️ [DEMO_SEEDER] Using predefined chunk embeddings ({emb_err})")

        db_manager.save_policy_chunks(uid, "demo-aetna-health", combined_chunks)
        print(f"✅ [DEMO_SEEDER] Seeded {len(combined_chunks)} insurance RAG chunks for {uid}")
    except Exception as e:
        print(f"⚠️ [DEMO_SEEDER] Could not seed insurance chunks: {e}")

    print(f"✅ [DEMO_SEEDER] Seeding complete for {uid}")

if __name__ == "__main__":
    seed_demo_data()
