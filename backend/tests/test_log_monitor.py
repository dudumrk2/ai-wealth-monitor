"""
tests/test_log_monitor.py
=========================
Unit tests for the log monitor module.
All external calls (GCP Logging, Gemini, Telegram, Gmail) are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Tests for _group_log_entries
# ---------------------------------------------------------------------------

def test_group_log_entries_deduplicates_identical_messages():
    """Identical error messages (after normalisation) should be counted as one group."""
    from routers.log_monitor import _group_log_entries

    entries = [
        {"severity": "ERROR", "message": "Database connection failed: timeout after 30s [req-abc]", "timestamp": "2026-06-01T10:00:00Z"},
        {"severity": "ERROR", "message": "Database connection failed: timeout after 30s [req-xyz]", "timestamp": "2026-06-02T11:00:00Z"},
    ]
    groups = _group_log_entries(entries)
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["severity"] == "ERROR"


def test_group_log_entries_separates_different_messages():
    """Different error messages should produce separate groups."""
    from routers.log_monitor import _group_log_entries

    entries = [
        {"severity": "ERROR", "message": "Database connection failed", "timestamp": "2026-06-01T10:00:00Z"},
        {"severity": "WARNING", "message": "Rate limit hit on Yahoo Finance", "timestamp": "2026-06-01T10:01:00Z"},
    ]
    groups = _group_log_entries(entries)
    assert len(groups) == 2


def test_group_log_entries_empty_returns_empty():
    """Empty input should return empty list."""
    from routers.log_monitor import _group_log_entries

    assert _group_log_entries([]) == []


def test_group_log_entries_sorts_by_count_descending():
    """Groups should be sorted highest count first."""
    from routers.log_monitor import _group_log_entries

    entries = [
        {"severity": "WARNING", "message": "Rate limit warning", "timestamp": "2026-06-01T10:00:00Z"},
        {"severity": "ERROR", "message": "DB timeout", "timestamp": "2026-06-01T10:01:00Z"},
        {"severity": "ERROR", "message": "DB timeout", "timestamp": "2026-06-01T10:02:00Z"},
        {"severity": "ERROR", "message": "DB timeout", "timestamp": "2026-06-01T10:03:00Z"},
    ]
    groups = _group_log_entries(entries)
    assert groups[0]["count"] == 3  # DB timeout group first
    assert groups[1]["count"] == 1  # Rate limit second


# ---------------------------------------------------------------------------
# Tests for _build_grouped_text
# ---------------------------------------------------------------------------

def test_build_grouped_text_formats_correctly():
    """Should produce the structured text block passed to Gemini."""
    from routers.log_monitor import _build_grouped_text

    groups = [
        {
            "severity": "ERROR",
            "signature": "Database connection failed: timeout",
            "count": 23,
            "first_seen": "2026-06-01T09:14:00Z",
            "last_seen": "2026-06-02T14:31:00Z",
            "sample": "ERROR:root:Database connection failed: timeout after 30s [req-abc123]",
        }
    ]
    text = _build_grouped_text(groups)
    assert "[ERROR]" in text
    assert "23 occurrences" in text
    assert "Database connection failed: timeout" in text


# ---------------------------------------------------------------------------
# Tests for _send_log_telegram
# ---------------------------------------------------------------------------

def test_send_log_telegram_calls_requests_post():
    """Should POST to the Telegram API with the bot token and chat_id."""
    from routers.log_monitor import _send_log_telegram

    with patch("routers.log_monitor.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "12345",
        }):
            result = _send_log_telegram("🔍 Test alert")

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "test-token" in call_args[0][0]  # URL contains token
    assert result is True


def test_send_log_telegram_returns_false_when_token_missing():
    """Should return False and not crash when TELEGRAM_BOT_TOKEN is absent."""
    from routers.log_monitor import _send_log_telegram

    with patch.dict("os.environ", {}, clear=True):
        result = _send_log_telegram("Test")

    assert result is False


# ---------------------------------------------------------------------------
# Tests for _send_log_email
# ---------------------------------------------------------------------------

def test_send_log_email_returns_false_when_no_refresh_token():
    """Should return False silently when profile has no gmail_refresh_token."""
    from routers.log_monitor import _send_log_email

    profile = {"pii_data": {"member1": {"email": "test@example.com"}}}
    result = _send_log_email(profile, "Subject", "<html>body</html>")
    assert result is False


def test_send_log_email_returns_false_when_no_email():
    """Should return False silently when profile has no email address."""
    from routers.log_monitor import _send_log_email

    profile = {"gmail_refresh_token": "fake-token", "pii_data": {}}
    result = _send_log_email(profile, "Subject", "<html>body</html>")
    assert result is False


# ---------------------------------------------------------------------------
# Tests for _run_log_scan orchestration (IMP-5)
# ---------------------------------------------------------------------------

def test_run_log_scan_returns_zero_when_no_entries():
    """Should return silence result without sending notifications when no log entries found."""
    from routers.log_monitor import _run_log_scan

    with patch("routers.log_monitor._fetch_gcp_log_entries", return_value=[]):
        result = _run_log_scan()

    assert result["issues_found"] == 0
    assert result["telegram_sent"] is False
    assert result["email_sent"] is False
    assert result["error"] is None


def test_run_log_scan_returns_zero_when_groups_empty():
    """Should return silence result when entries exist but all normalise to empty signatures."""
    from routers.log_monitor import _run_log_scan

    # Entries whose messages normalise to empty (all noise tokens)
    noise_entries = [
        {"severity": "WARNING", "message": "req-abc123", "timestamp": "2026-06-01T10:00:00Z"},
    ]
    with patch("routers.log_monitor._fetch_gcp_log_entries", return_value=noise_entries):
        result = _run_log_scan()

    assert result["issues_found"] == 0
    assert result["telegram_sent"] is False
    assert result["email_sent"] is False


def test_run_log_scan_sends_notifications_when_issues_found():
    """Should call both Telegram and email notifiers when issues are found."""
    from routers.log_monitor import _run_log_scan

    fake_entries = [
        {"severity": "ERROR", "message": "Database connection failed", "timestamp": "2026-06-01T10:00:00Z"},
    ]
    fake_digest = {
        "telegram_message": "🔍 Test alert",
        "email_html": "<html><body>Test</body></html>",
    }

    with patch("routers.log_monitor._fetch_gcp_log_entries", return_value=fake_entries), \
         patch("routers.log_monitor._generate_digest", return_value=fake_digest), \
         patch("routers.log_monitor._send_log_telegram", return_value=True) as mock_tg, \
         patch("routers.log_monitor._send_log_email", return_value=True) as mock_email, \
         patch("routers.log_monitor.db_manager") as mock_db:

        mock_db.get_all_family_uids.return_value = ["uid-owner"]
        mock_db.get_family_profile.return_value = {
            "gmail_refresh_token": "token",
            "pii_data": {"member1": {"email": "owner@example.com"}},
        }

        result = _run_log_scan()

    assert result["issues_found"] == 1
    assert result["telegram_sent"] is True
    assert result["email_sent"] is True
    mock_tg.assert_called_once_with(fake_digest["telegram_message"])
    mock_email.assert_called_once()
