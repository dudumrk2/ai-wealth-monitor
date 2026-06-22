"""Unit tests for _analyze_stocks_for_family in routers/agent.py."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.agent as agent_module
from stock_agent_tools import DEMO_SCENARIOS, build_demo_tools


# Patch TRACKED_GURUS to a single controlled guru so tests are deterministic
_TEST_GURUS = {"Test Guru": "TG"}


def _run(uid: str, holdings, sent_keys: set, guru_output: str, agent_success: bool = True):
    """Helper: run _analyze_stocks_for_family with mocked dependencies."""
    profile = {"telegram_chat_id": "", "pii_data": {"member1": {"email": "t@t.com"}}}

    with patch.object(agent_module.db_manager, "get_family_profile", return_value=profile), \
         patch.object(agent_module.db_manager, "get_family_holdings", return_value=holdings), \
         patch.object(agent_module.db_manager, "get_sent_13f_alert_keys", return_value=sent_keys), \
         patch.object(agent_module.db_manager, "mark_13f_alert_sent") as mock_mark, \
         patch.object(agent_module, "scan_guru_portfolio") as mock_scan, \
         patch.object(agent_module, "analyze_portfolio_and_gurus",
                      return_value={"success": agent_success, "output": "analysis text"}), \
         patch.object(agent_module, "_send_agent_summary_email"), \
         patch.object(agent_module, "TRACKED_GURUS", _TEST_GURUS):

        mock_scan.invoke.return_value = guru_output
        result = agent_module._analyze_stocks_for_family(uid)
        return result, mock_mark


# ── Error paths ───────────────────────────────────────────────────────────────

def test_analyze_stocks_returns_error_when_no_profile():
    with patch.object(agent_module.db_manager, "get_family_profile", return_value=None):
        result = agent_module._analyze_stocks_for_family("uid_x")
    assert result["status"] == "error"
    assert result["reason"] == "no_profile"


def test_analyze_stocks_returns_error_when_no_holdings():
    profile = {"telegram_chat_id": ""}
    with patch.object(agent_module.db_manager, "get_family_profile", return_value=profile), \
         patch.object(agent_module.db_manager, "get_family_holdings", return_value=[]):
        result = agent_module._analyze_stocks_for_family("uid_x")
    assert result["status"] == "error"
    assert result["reason"] == "no_holdings"


# ── Deduplication: new alerts ─────────────────────────────────────────────────

def test_analyze_stocks_marks_new_alert_keys_as_sent():
    guru_output = (
        "Guru Report Q1 2024\n"
        "New positions: AAPL, MSFT\n"
        "Liquidated positions: TSLA\n"
    )
    result, mock_mark = _run("uid_x", [{"id": "AAPL"}], set(), guru_output, agent_success=True)
    assert result["new_alerts_marked"] > 0
    assert mock_mark.call_count == result["new_alerts_marked"]


def test_analyze_stocks_does_not_remark_already_sent_keys():
    guru_output = (
        "Guru Report Q1 2024\n"
        "New positions: AAPL\n"
    )
    # Pre-populate all keys that would be generated
    sent_keys = {
        "Test Guru:AAPL:Q1 2024",
    }
    result, mock_mark = _run("uid_x", [{"id": "AAPL"}], sent_keys, guru_output, agent_success=True)
    assert result["new_alerts_marked"] == 0
    assert mock_mark.call_count == 0


def test_analyze_stocks_does_not_mark_keys_on_agent_failure():
    guru_output = (
        "Guru Report Q1 2024\n"
        "New positions: AAPL\n"
    )
    result, mock_mark = _run("uid_x", [{"id": "AAPL"}], set(), guru_output, agent_success=False)
    assert result["new_alerts_marked"] == 0
    mock_mark.assert_not_called()


# ── Demo scenario tools ───────────────────────────────────────────────────────

def test_build_demo_tools_returns_five_tools_with_mock_data():
    tools = build_demo_tools("price")
    assert len(tools) == 5

    by_name = {t.name: t for t in tools}
    # The price scenario defines AAPL up +6.10% — the mock must return it verbatim.
    assert "+6.10%" in by_name["get_us_stock_data"].invoke({"ticker": "AAPL"})
    # search_financial_news mock includes the seeded headline + URL.
    assert "OpenAI" in by_name["search_financial_news"].invoke({"ticker": "AAPL"})
    # send_telegram_alert is a no-op stub in demo mode (never hits the network).
    assert "successfully" in by_name["send_telegram_alert"].invoke({"message": "hi"})


def test_build_demo_tools_unknown_ticker_falls_back():
    tools = {t.name: t for t in build_demo_tools("clear")}
    # An unseeded ticker should not raise — it returns a generic fallback string.
    out = tools["get_us_stock_data"].invoke({"ticker": "ZZZZ"})
    assert "ZZZZ" in out


# ── Demo endpoint auth (fail-closed) ──────────────────────────────────────────

@pytest.fixture
def demo_client():
    app = FastAPI()
    app.include_router(agent_module.router)
    return TestClient(app)


def test_demo_endpoint_rejects_when_secret_unset(demo_client, monkeypatch):
    """Fail closed: no CRON_SECRET configured → 403 even with a header."""
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = demo_client.post(
        "/api/demo/run-scenario",
        json={"scenario": "price"},
        headers={"X-Cron-Secret": "anything"},
    )
    assert resp.status_code == 403


def test_demo_endpoint_rejects_wrong_secret(demo_client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "right-secret")
    resp = demo_client.post(
        "/api/demo/run-scenario",
        json={"scenario": "price"},
        headers={"X-Cron-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


def test_demo_endpoint_rejects_unknown_scenario(demo_client, monkeypatch):
    """Valid secret but bad scenario → 400, before any Gemini call."""
    monkeypatch.setenv("CRON_SECRET", "right-secret")
    resp = demo_client.post(
        "/api/demo/run-scenario",
        json={"scenario": "does-not-exist"},
        headers={"X-Cron-Secret": "right-secret"},
    )
    assert resp.status_code == 400
