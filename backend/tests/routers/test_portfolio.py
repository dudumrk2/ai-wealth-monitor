"""Route tests for routers/portfolio.py using FastAPI TestClient."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.portfolio import router
from auth import verify_token

TEST_UID = "test_uid_portfolio"


def _make_client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[verify_token] = lambda: {"uid": TEST_UID}
    app.include_router(router)
    return TestClient(app)


client = _make_client()


# ── DELETE /api/portfolio/fund/{fund_id} ──────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_delete_fund_removes_fund_and_saves(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {
            "user": {"funds": [{"id": "fund-1", "track_name": "Test Fund"}, {"id": "fund-2"}]},
            "spouse": {"funds": []},
        }
    }
    mock_db.save_processed_portfolio.return_value = None

    resp = client.delete("/api/portfolio/fund/fund-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    saved_doc = mock_db.save_processed_portfolio.call_args.args[1]
    fund_ids = [f["id"] for f in saved_doc["portfolios"]["user"]["funds"]]
    assert "fund-1" not in fund_ids
    assert "fund-2" in fund_ids


@patch("routers.portfolio.db_manager")
def test_delete_fund_returns_404_when_portfolio_missing(mock_db):
    mock_db.get_processed_portfolio.return_value = None

    resp = client.delete("/api/portfolio/fund/any-id")

    assert resp.status_code == 404


@patch("routers.portfolio.db_manager")
def test_delete_fund_returns_404_when_fund_not_found(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {
            "user": {"funds": [{"id": "fund-other"}]},
            "spouse": {"funds": []},
        }
    }

    resp = client.delete("/api/portfolio/fund/non-existent-id")

    assert resp.status_code == 404


# ── GET /api/portfolio/fx-rate ────────────────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_get_fx_rate_returns_cached_rate(mock_db):
    mock_db.get_fx_rate.return_value = {"rate": 3.72, "date": "2024-01-15"}

    resp = client.get("/api/portfolio/fx-rate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rate"] == 3.72
    assert data["cached"] is True


@patch("routers.portfolio.db_manager")
def test_get_fx_rate_returns_fallback_on_api_failure(mock_db):
    mock_db.get_fx_rate.return_value = None  # cache miss
    # aiohttp is imported inside the function; patching via sys.modules path
    with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
        resp = client.get("/api/portfolio/fx-rate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rate"] == 3.70
    assert data["is_fallback"] is True
