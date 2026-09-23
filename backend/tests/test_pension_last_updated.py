import pytest
from unittest.mock import MagicMock, patch
import datetime
from document_flows import PensionFlow
import db_manager

@pytest.mark.asyncio
async def test_pension_flow_stamps_last_updated_for_user(monkeypatch):
    mock_doc = {
        "portfolios": {
            "user": {"funds": []},
            "spouse": {"funds": []}
        },
        "action_items": []
    }
    
    saved_docs = []
    def mock_save(uid, doc):
        saved_docs.append(doc)

    monkeypatch.setattr(db_manager, "get_processed_portfolio", lambda uid: mock_doc)
    monkeypatch.setattr(db_manager, "save_processed_portfolio", mock_save)
    monkeypatch.setattr(db_manager, "clear_cache_for_uid", lambda uid: None)

    profile = {
        "pii_data": {
            "member1": {"name": "דוד", "idNumber": "111111111"},
            "member2": {"name": "ענבר", "idNumber": "222222222"}
        }
    }
    flow = PensionFlow(f_profile=profile, owner_key="user")
    
    sample_funds = [
        {"product_type": "פנסיה", "provider_name": "הראל", "track_name": "מסלול כללי", "balance": 50000}
    ]
    
    await flow.save_funds_to_db("test_uid", sample_funds)
    
    assert len(saved_docs) > 0
    saved = saved_docs[-1]
    assert "last_updated" in saved["portfolios"]["user"]
    assert saved["portfolios"]["user"]["last_updated"] is not None
    assert "last_updated" in saved
    # Ensure spouse was not updated
    assert "last_updated" not in saved["portfolios"]["spouse"]


@pytest.mark.asyncio
async def test_pension_flow_stamps_last_updated_for_spouse(monkeypatch):
    mock_doc = {
        "portfolios": {
            "user": {"funds": []},
            "spouse": {"funds": []}
        },
        "action_items": []
    }
    
    saved_docs = []
    def mock_save(uid, doc):
        saved_docs.append(doc)

    monkeypatch.setattr(db_manager, "get_processed_portfolio", lambda uid: mock_doc)
    monkeypatch.setattr(db_manager, "save_processed_portfolio", mock_save)
    monkeypatch.setattr(db_manager, "clear_cache_for_uid", lambda uid: None)

    profile = {
        "pii_data": {
            "member1": {"name": "דוד", "idNumber": "111111111"},
            "member2": {"name": "ענבר", "idNumber": "222222222"}
        }
    }
    flow = PensionFlow(f_profile=profile, owner_key="spouse")
    
    sample_funds = [
        {"product_type": "פנסיה", "provider_name": "הפניקס", "track_name": "מסלול מניות", "balance": 75000}
    ]
    
    await flow.save_funds_to_db("test_uid", sample_funds)
    
    assert len(saved_docs) > 0
    saved = saved_docs[-1]
    assert "last_updated" in saved["portfolios"]["spouse"]
    assert saved["portfolios"]["spouse"]["last_updated"] is not None
    assert "last_updated" in saved
    # Ensure user was not updated
    assert "last_updated" not in saved["portfolios"]["user"]
