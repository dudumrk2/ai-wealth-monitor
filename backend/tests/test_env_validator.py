import os
import sys
import html
from unittest.mock import patch, MagicMock
import pytest

from env_validator import (
    MANDATORY_ENV_VARS,
    validate_environment,
    send_startup_failure_alert,
    get_secret_with_fallback,
    TELEGRAM_HTTP_TIMEOUT,
)


@pytest.fixture(autouse=True)
def reset_skip_flag():
    # Allow tests in this module to explicitly test validation behavior
    old_skip = os.environ.get("SKIP_ENV_VALIDATION")
    if "SKIP_ENV_VALIDATION" in os.environ:
        del os.environ["SKIP_ENV_VALIDATION"]
    yield
    if old_skip is not None:
        os.environ["SKIP_ENV_VALIDATION"] = old_skip


def test_validate_environment_all_present():
    fake_env = {var: "mock_value_123" for var in MANDATORY_ENV_VARS}
    with patch.dict(os.environ, fake_env, clear=True):
        missing = validate_environment(fail_fast=True)
        assert missing == []


def test_validate_environment_missing_raises_and_alerts():
    fake_env = {"GEMINI_API_KEY": "mock_gemini"}
    with patch.dict(os.environ, fake_env, clear=True):
        with patch("env_validator.get_secret_from_sm", return_value=None):
            with patch("env_validator.send_startup_failure_alert") as mock_alert:
                with pytest.raises(RuntimeError) as exc_info:
                    validate_environment(fail_fast=True)
                
                err_msg = str(exc_info.value)
                assert "Missing mandatory environment variables" in err_msg
                assert "CRON_SECRET" in err_msg
                mock_alert.assert_called_once()
                # Verify secrets are NOT logged in error message, only variable names
                assert "mock_gemini" not in err_msg


def test_validate_environment_secret_manager_injection():
    # Suppose CRON_SECRET is missing from os.environ, but available in Secret Manager
    fake_env = {var: "mock_val" for var in MANDATORY_ENV_VARS if var != "CRON_SECRET"}
    
    def fake_sm(key, project_id=None):
        if key == "CRON_SECRET":
            return "recovered_secret_from_sm"
        return None

    with patch.dict(os.environ, fake_env, clear=True):
        with patch("env_validator.get_secret_from_sm", side_effect=fake_sm):
            with patch("env_validator.send_startup_failure_alert") as mock_alert:
                missing = validate_environment(fail_fast=True)
                assert missing == []
                # CRITICAL: Verify it was injected into os.environ for the rest of the app!
                assert os.environ.get("CRON_SECRET") == "recovered_secret_from_sm"
                mock_alert.assert_not_called()


def test_whitespace_and_empty_treated_as_missing():
    fake_env = {var: "mock_val" for var in MANDATORY_ENV_VARS}
    fake_env["CRON_SECRET"] = "   "  # whitespace only
    fake_env["GEMINI_API_KEY"] = ""  # empty string

    with patch.dict(os.environ, fake_env, clear=True):
        with patch("env_validator.get_secret_from_sm", return_value=None):
            with patch("env_validator.send_startup_failure_alert"):
                with pytest.raises(RuntimeError) as exc_info:
                    validate_environment(fail_fast=True)
                err = str(exc_info.value)
                assert "CRON_SECRET" in err
                assert "GEMINI_API_KEY" in err


def test_skip_env_validation_flag():
    with patch.dict(os.environ, {"SKIP_ENV_VALIDATION": "1"}, clear=True):
        # Even with empty env, must not raise
        missing = validate_environment(fail_fast=True)
        assert missing == []


def test_send_startup_failure_alert_success_and_deduplication():
    with patch.dict(os.environ, {
        "K_SERVICE": "test-service",
        "K_REVISION": "test-service-00001",
        "TELEGRAM_BOT_TOKEN": "mock_bot_token",
        "TELEGRAM_CHAT_ID": "12345678",
    }):
        # Mock Firestore to simulate deduplication
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = False  # first run: not yet alerted
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc

        with patch("env_validator.get_firestore_client", return_value=mock_db):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                
                # 1. First execution: should send alert and record to Firestore
                sent = send_startup_failure_alert(["CRON_SECRET", "GEMINI_API_KEY"])
                assert sent is True
                assert mock_post.called
                assert mock_post.call_args[1]["timeout"] <= 3.0
                mock_doc.set.assert_called_once()
                
                # 2. Second execution (same revision retry in Cloud Run):
                mock_doc.get.return_value.exists = True  # now exists!
                mock_post.reset_mock()
                
                sent_again = send_startup_failure_alert(["CRON_SECRET", "GEMINI_API_KEY"])
                assert sent_again is False  # deduplicated!
                mock_post.assert_not_called()


def test_send_startup_failure_alert_html_escaping():
    with patch.dict(os.environ, {
        "K_SERVICE": "service<test>&corp",
        "K_REVISION": "rev<123>",
        "TELEGRAM_BOT_TOKEN": "mock_tok",
        "TELEGRAM_CHAT_ID": "123",
    }):
        with patch("env_validator.get_firestore_client", return_value=None):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                send_startup_failure_alert(["MALFORMED<VAR>"])
                
                payload = mock_post.call_args[1]["json"]
                text = payload["text"]
                assert "service&lt;test&gt;&amp;corp" in text
                assert "rev&lt;123&gt;" in text
                assert "MALFORMED&lt;VAR&gt;" in text


def test_missing_telegram_credentials_logs_critical_without_crashing():
    with patch.dict(os.environ, {}, clear=True):
        with patch("env_validator.get_secret_from_sm", return_value=None):
            with patch("env_validator.logger.critical") as mock_log_crit:
                sent = send_startup_failure_alert(["CRON_SECRET"])
                assert sent is False
                mock_log_crit.assert_called()
                log_text = mock_log_crit.call_args[0][0]
                assert "TELEGRAM" in log_text


@pytest.mark.asyncio
async def test_app_lifespan_invokes_validate_environment():
    import app as backend_app
    with patch("app.validate_environment") as mock_validate:
        async with backend_app.lifespan(backend_app.app):
            mock_validate.assert_called_once_with(fail_fast=True)
