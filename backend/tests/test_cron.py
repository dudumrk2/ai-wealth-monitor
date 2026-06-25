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


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
@pytest.mark.asyncio
async def test_weekly_stock_summary_for_family_skips_cash_and_skips_email_on_no_events():
    from app import _weekly_stock_summary_for_family
    with patch("app.db_manager") as mock_db, \
         patch("google.genai.Client") as mock_genai_client, \
         patch("app._get_gmail_service") as mock_gmail:
        
        # Setup mock database
        mock_db.get_family_profile.return_value = {
            "gmail_refresh_token": "some_token",
            "pii_data": {"member1": {"email": "test@example.com"}}
        }
        mock_db.get_family_holdings.return_value = [
            {"id": "CASH_ILS", "shares": 1000, "current_price": 1, "average_cost": 1},
            {"id": "AAPL", "shares": 10, "current_price": 150, "average_cost": 140}
        ]
        
        # Setup mock Gemini response
        mock_client_instance = MagicMock()
        mock_genai_client.return_value = mock_client_instance
        mock_response = MagicMock()
        mock_response.text = "NO_SIGNIFICANT_EVENTS"
        mock_client_instance.models.generate_content.return_value = mock_response
        
        # Run function
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
            res = await _weekly_stock_summary_for_family("family_1")
            
        assert res["status"] == "skipped"
        assert res["reason"] == "no_significant_events"
        
        # Verify CASH_ILS was filtered out and only AAPL was passed to generate_content
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args[1]
        prompt_used = call_args["contents"]
        assert "AAPL" in prompt_used
        assert "CASH_ILS" not in prompt_used
        
        # Verify Gmail service was not called
        mock_gmail.assert_not_called()


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
@pytest.mark.asyncio
async def test_weekly_stock_summary_for_family_sends_email_on_significant_events():
    from app import _weekly_stock_summary_for_family
    with patch("app.db_manager") as mock_db, \
         patch("google.genai.Client") as mock_genai_client, \
         patch("app._get_gmail_service") as mock_gmail_service:
        
        mock_db.get_family_profile.return_value = {
            "gmail_refresh_token": "some_token",
            "pii_data": {"member1": {"email": "test@example.com"}}
        }
        mock_db.get_family_holdings.return_value = [
            {"id": "AAPL", "shares": 10, "current_price": 150, "average_cost": 140}
        ]
        
        mock_client_instance = MagicMock()
        mock_genai_client.return_value = mock_client_instance
        mock_response = MagicMock()
        mock_response.text = "Here is a weekly update about AAPL..."
        mock_client_instance.models.generate_content.return_value = mock_response
        
        mock_service = MagicMock()
        mock_gmail_service.return_value = mock_service
        
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
            res = await _weekly_stock_summary_for_family("family_1")
            
        assert res["status"] == "success"
        assert res["email"] == "test@example.com"
        
        # Verify Gmail service was called
        mock_gmail_service.assert_called_once_with("some_token")
        mock_service.users().messages().send.assert_called_once()
