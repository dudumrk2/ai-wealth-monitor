"""Tests for unified cron endpoints in app.py."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

try:
    from app import app as fastapi_app
    _APP_IMPORTED = True
except Exception:
    _APP_IMPORTED = False
    fastapi_app = None


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_monthly_cron_forbidden_when_secret_invalid(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "super-secret")
    client = TestClient(fastapi_app)
    
    resp = client.post("/api/cron/monthly", headers={"X-Cron-Secret": "wrong"})
    assert resp.status_code == 403

    resp2 = client.post("/api/cron/monthly")  # no header
    assert resp2.status_code == 403


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_weekly_cron_forbidden_when_secret_invalid(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "super-secret")
    client = TestClient(fastapi_app)
    
    resp = client.post("/api/cron/weekly", headers={"X-Cron-Secret": "wrong"})
    assert resp.status_code == 403

    resp2 = client.post("/api/cron/weekly")  # no header
    assert resp2.status_code == 403


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_monthly_cron_success(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "super-secret")
    client = TestClient(fastapi_app)

    with patch("app.db_manager") as mock_db, \
         patch("app._process_family_emails", new_callable=AsyncMock) as mock_emails, \
         patch("app._run_funder_yields_update", new_callable=AsyncMock) as mock_yields:

        mock_db.get_all_family_uids.return_value = ["family_1", "family_2"]
        mock_emails.return_value = {"processed": 3}
        mock_yields.return_value = {"updatedPolices": 2, "prime_rate": 6.25}

        resp = client.post("/api/cron/monthly", headers={"X-Cron-Secret": "super-secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["fetch_emails"]["total_emails_processed"] == 6
        assert data["funder_yields"]["updatedPolices"] == 2
        
        assert mock_emails.call_count == 2
        mock_emails.assert_any_call("family_1")
        mock_emails.assert_any_call("family_2")
        mock_yields.assert_called_once()


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_weekly_cron_success(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "super-secret")
    client = TestClient(fastapi_app)

    with patch("app.db_manager") as mock_db, \
         patch("app._perform_stock_prices_update", new_callable=AsyncMock) as mock_prices, \
         patch("app._weekly_stock_summary_for_family", new_callable=AsyncMock) as mock_summary:

        mock_db.get_all_family_uids_for_holdings.return_value = ["family_1", "family_2"]
        mock_db.get_all_family_uids.return_value = ["family_1", "family_2"]
        
        # Profile mock returns True or False depending on the setting
        def mock_get_profile(uid):
            if uid == "family_1":
                return {
                    "cron_stock_prices_enabled": True,
                    "cron_weekly_summary_enabled": True
                }
            else:
                return {
                    "cron_stock_prices_enabled": False,
                    "cron_weekly_summary_enabled": False
                }
        
        mock_db.get_family_profile.side_effect = mock_get_profile
        mock_prices.return_value = {"updated": 5}
        mock_summary.return_value = {"success": True}

        resp = client.post("/api/cron/weekly", headers={"X-Cron-Secret": "super-secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        
        # family_1 stock updated, family_2 skipped
        assert mock_prices.call_count == 1
        mock_prices.assert_any_call("family_1", source_label="CRON-WEEKLY")
        
        # family_1 summary processed, family_2 summary skipped
        assert mock_summary.call_count == 1
        mock_summary.assert_any_call("family_1")
