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

def _seed_single_demo(uid: str, lang: str):
    """Seed a specific demo user (HE or EN) into Firestore."""
    print(f"🌱 [DEMO_SEEDER] Seeding demo data for {uid} (lang={lang})...")

    # 1. Family Profile
    profile = copy.deepcopy(get_demo_family_profile(lang))
    profile["created_at"] = datetime.datetime.now().isoformat()
    db_manager.save_family_profile(uid, profile)

    # 2. Processed Portfolio
    portfolio = copy.deepcopy(get_demo_portfolio_data(lang))
    portfolio["last_updated"] = datetime.datetime.now().isoformat()
    db_manager.save_processed_portfolio(uid, portfolio)

    # 3. Alternative Investment
    try:
        alt_coll = db_manager.db.collection("families").document(uid).collection("alt_projects")
        docs = alt_coll.list_documents()
        for doc in docs:
            doc.delete()
    except Exception as e:
        print(f"⚠️ [DEMO_SEEDER] Could not clear alt_projects: {e}")

    db_manager.add_alt_project(uid, copy.deepcopy(DEMO_ALT_INVESTMENT))

    # 4. Seed Insurance Policy RAG chunks
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
        except Exception as emb_err:
            pass

        db_manager.save_policy_chunks(uid, "demo-aetna-health", combined_chunks)
    except Exception as e:
        print(f"⚠️ [DEMO_SEEDER] Could not seed insurance chunks: {e}")

    print(f"✅ [DEMO_SEEDER] Seeding complete for {uid} (lang={lang})")

def seed_demo_data(lang: str | None = None):
    """Seed both Hebrew and English demo users in Firestore."""
    # 1. Seed Hebrew demo user (default demo-user-12345)
    _seed_single_demo(config.DEMO_UID, "he")

    # 2. Seed English demo user (demo-user-en)
    _seed_single_demo("demo-user-en", "en")

if __name__ == "__main__":
    seed_demo_data()
