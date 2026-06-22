"""Unit tests for _analyze_stocks_for_family in routers/agent.py."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from datetime import datetime, timezone, timedelta

import routers.agent as agent_module
import stock_agent_tools
from stock_agent_tools import DEMO_SCENARIOS, build_demo_tools, search_financial_news


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


# ── Financial news recency filter ─────────────────────────────────────────────

def _news_item(title: str, days_ago: int) -> dict:
    """Build a Yahoo-Finance-shaped news item published `days_ago` days back."""
    pub = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    return {"content": {"title": title, "pubDate": pub,
                        "canonicalUrl": {"url": f"https://news/{title}"}}}


def test_search_news_drops_articles_older_than_window(monkeypatch):
    """Headlines older than NEWS_RECENCY_DAYS must be filtered out."""
    fake = MagicMock()
    fake.news = [
        _news_item("FreshStory", days_ago=1),
        _news_item("StaleStory", days_ago=30),
    ]
    monkeypatch.setattr(stock_agent_tools.yf, "Ticker", lambda t: fake)

    out = search_financial_news.invoke({"ticker": "AAPL"})
    assert "FreshStory" in out
    assert "StaleStory" not in out
    # Each retained line is prefixed with its publish date.
    assert "[" in out and "]" in out


def test_search_news_returns_message_when_all_stale(monkeypatch):
    fake = MagicMock()
    fake.news = [_news_item("OldNews", days_ago=99)]
    monkeypatch.setattr(stock_agent_tools.yf, "Ticker", lambda t: fake)

    out = search_financial_news.invoke({"ticker": "AAPL"})
    assert "last 7 days" in out
    assert "OldNews" not in out


# ── Input validation guardrails ───────────────────────────────────────────────

from stock_agent_tools import get_us_stock_data, get_il_stock_data, send_telegram_alert


def test_us_tool_rejects_malformed_ticker():
    out = get_us_stock_data.invoke({"ticker": "not a ticker!!"})
    assert out.startswith("ERROR")
    assert "valid US ticker" in out


def test_il_tool_rejects_non_numeric_code():
    out = get_il_stock_data.invoke({"ticker": "AAPL"})
    assert out.startswith("ERROR")
    assert "valid Israeli fund code" in out


def test_news_tool_rejects_israeli_numeric_code():
    out = search_financial_news.invoke({"ticker": "5131054"})
    assert out.startswith("ERROR")


def test_telegram_rejects_empty_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    out = send_telegram_alert.invoke({"message": "   ", "chat_id": "123"})
    assert out.startswith("ERROR")
    assert "empty" in out


# ── Run summary: price-alert hallucination check ──────────────────────────────

def test_summary_captures_price_alert_ticker():
    """The summary records the ticker named in a PRICE ALERT for hallucination checks."""
    import stock_agent
    from langchain_core.messages import AIMessage

    msg = AIMessage(content="", tool_calls=[{
        "name": "send_telegram_alert",
        "args": {"message": "📊 PRICE ALERT: <b>AAPL</b> moved <b>+6%</b> today."},
        "id": "1",
    }])
    summary = stock_agent._extract_run_summary([msg], start_time=0.0)
    assert summary.price_alert_tickers == ["AAPL"]
    assert summary.price_alerts_sent == 1


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
