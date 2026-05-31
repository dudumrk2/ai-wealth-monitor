"""Route tests for routers/insurance.py."""
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.insurance import router
from auth import verify_token
import config

TEST_UID = "test_uid_insurance"
DEMO_UID = config.DEMO_UID


def _make_client(uid: str) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[verify_token] = lambda: {"uid": uid}
    app.include_router(router)
    return TestClient(app)


client = _make_client(TEST_UID)
demo_client = _make_client(DEMO_UID)


# ── Demo bypass ───────────────────────────────────────────────────────────────

def test_compare_insurance_demo_returns_hardcoded_draft():
    resp = demo_client.post("/api/insurance/compare", json={"policy_id": "any"})
    assert resp.status_code == 200
    data = resp.json()
    assert "draft" in data
    assert len(data["draft"]) > 0


# ── 404 cases ─────────────────────────────────────────────────────────────────

@patch("routers.insurance.db_manager")
def test_compare_insurance_returns_404_when_portfolio_missing(mock_db):
    mock_db.get_processed_portfolio.return_value = None
    resp = client.post("/api/insurance/compare", json={"policy_id": "p1"})
    assert resp.status_code == 404


@patch("routers.insurance.db_manager")
def test_compare_insurance_returns_404_when_policy_not_found(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}
    }
    resp = client.post("/api/insurance/compare", json={"policy_id": "non-existent"})
    assert resp.status_code == 404


# ── No competitors → short-circuit message ────────────────────────────────────

@patch("routers.insurance.db_manager")
def test_compare_insurance_returns_no_competitors_message_when_empty(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {
            "user": {
                "funds": [
                    {"id": "pol-1", "provider_name": "Harel",
                     "category": "insurance", "top_competitors": []}
                ]
            },
            "spouse": {"funds": []},
        }
    }
    resp = client.post("/api/insurance/compare", json={"policy_id": "pol-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "draft" in data
    assert len(data["draft"]) > 0
