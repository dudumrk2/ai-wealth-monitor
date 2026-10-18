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

        mock_scan.return_value = guru_output
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

    by_name = {t.__name__: t for t in tools}
    # The price scenario defines AAPL up +6.10% — the mock must return it verbatim.
    assert "+6.10%" in by_name["get_us_stock_data"](ticker="AAPL")
    # search_financial_news mock includes the seeded headline + URL.
    assert "OpenAI" in by_name["search_financial_news"](ticker="AAPL")
    # send_telegram_alert is a no-op stub in demo mode (never hits the network).
    assert "successfully" in by_name["send_telegram_alert"](message="hi")


def test_build_demo_tools_unknown_ticker_falls_back():
    tools = {t.__name__: t for t in build_demo_tools("clear")}
    # An unseeded ticker should not raise — it returns a generic fallback string.
    out = tools["get_us_stock_data"](ticker="ZZZZ")
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

    out = search_financial_news(ticker="AAPL")
    assert "FreshStory" in out
    assert "StaleStory" not in out
    # Each retained line is prefixed with its publish date.
    assert "[" in out and "]" in out


def test_search_news_returns_message_when_all_stale(monkeypatch):
    fake = MagicMock()
    fake.news = [_news_item("OldNews", days_ago=99)]
    monkeypatch.setattr(stock_agent_tools.yf, "Ticker", lambda t: fake)

    out = search_financial_news(ticker="AAPL")
    assert "last 7 days" in out
    assert "OldNews" not in out


# ── Input validation guardrails ───────────────────────────────────────────────

from stock_agent_tools import get_us_stock_data, get_il_stock_data, send_telegram_alert


def test_us_tool_rejects_malformed_ticker():
    out = get_us_stock_data(ticker="not a ticker!!")
    assert out.startswith("ERROR")
    assert "valid US ticker" in out


def test_il_tool_rejects_non_numeric_code():
    out = get_il_stock_data(ticker="AAPL")
    assert out.startswith("ERROR")
    assert "valid Israeli fund code" in out


def test_news_tool_rejects_israeli_numeric_code():
    out = search_financial_news(ticker="5131054")
    assert out.startswith("ERROR")


def test_telegram_rejects_empty_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    out = send_telegram_alert(message="   ", chat_id="123")
    assert out.startswith("ERROR")
    assert "empty" in out


# ── Run summary: price-alert hallucination check & AFC history ────────────────

def test_summary_captures_price_alert_ticker():
    """The summary records the ticker named in a PRICE ALERT for hallucination checks."""
    import stock_agent
    from google.genai import types

    afc_history = [
        types.Content(
            role="model",
            parts=[
                types.Part.from_function_call(
                    name="get_us_stock_data",
                    args={"ticker": "AAPL"},
                ),
                types.Part.from_function_call(
                    name="get_il_stock_data",
                    args={"ticker": "5131054"},
                ),
                types.Part.from_function_call(
                    name="scan_guru_portfolio",
                    args={"guru_name": "Berkshire Hathaway"},
                ),
                types.Part.from_function_call(
                    name="send_telegram_alert",
                    args={"message": "📊 PRICE ALERT: <b>AAPL</b> moved <b>+6%</b> today."},
                ),
                types.Part.from_function_call(
                    name="send_telegram_alert",
                    args={"message": "🚨 RISK ALERT: <b>Berkshire Hathaway</b> exited <b>AAPL</b>."},
                ),
                types.Part.from_function_call(
                    name="send_telegram_alert",
                    args={"message": "💡 ALPHA IDEA: <b>Berkshire Hathaway</b> initiated <b>OXY</b>."},
                ),
            ],
        ),
        types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name="get_us_stock_data",
                    response={"result": "AAPL last price: $213.40 USD"},
                ),
                types.Part.from_function_response(
                    name="send_telegram_alert",
                    response={"result": "ERROR [send_telegram_alert]: timeout"},
                ),
                types.Part.from_function_response(
                    name="scan_guru_portfolio",
                    response={"error": "Network timeout"},
                ),
            ],
        ),
    ]
    summary = stock_agent._extract_run_summary(afc_history, start_time=0.0)
    assert summary.tickers_checked == ["AAPL", "5131054"]
    assert summary.gurus_scanned == ["Berkshire Hathaway"]
    assert summary.price_alert_tickers == ["AAPL"]
    assert summary.price_alerts_sent == 1
    assert summary.risk_alerts_sent == 1
    assert summary.alpha_alerts_sent == 1
    assert summary.total_alerts_sent == 3
    assert len(summary.tool_errors) == 2
    assert all(err.startswith("ERROR") for err in summary.tool_errors)


def test_analyze_portfolio_and_gurus_invokes_genai_with_afc_limit(monkeypatch):
    """analyze_portfolio_and_gurus calls google.genai with maximum_remote_calls=25 and pre-analyzed data."""
    import stock_agent
    from google.genai import types

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    fake_response = MagicMock()
    fake_response.text = "Portfolio analysis complete."
    fake_response.candidates = []
    fake_response.automatic_function_calling_history = [
        types.Content(
            role="model",
            parts=[types.Part.from_function_call(name="get_us_stock_data", args={"ticker": "AAPL"})],
        ),
    ]

    with patch("stock_agent.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        res = stock_agent.analyze_portfolio_and_gurus(
            user_portfolio_tickers=["AAPL"],
            pre_analyzed_guru_data={"Berkshire Hathaway": "Q1 2025: None"},
            telegram_chat_id="chat-999",
        )

    assert res["success"] is True
    assert res["output"] == "Portfolio analysis complete."
    assert res["summary"]["tickers_checked"] == ["AAPL"]

    call_kwargs = mock_client_cls.return_value.models.generate_content.call_args.kwargs
    assert "PRE-COMPUTED 13F DATA" in call_kwargs["contents"]
    assert 'chat_id="chat-999"' in call_kwargs["contents"]
    assert call_kwargs["config"].automatic_function_calling.maximum_remote_calls == stock_agent.AGENT_RECURSION_LIMIT
    assert call_kwargs["config"].tools == stock_agent.AGENT_TOOLS


def test_analyze_portfolio_and_gurus_fails_when_max_remote_calls_exceeded(monkeypatch):
    """When maximum_remote_calls is reached, response still has a pending function_call -> success=False."""
    import stock_agent
    from google.genai import types

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    fake_candidate = MagicMock()
    fake_candidate.content = types.Content(
        role="model",
        parts=[types.Part.from_function_call(name="get_us_stock_data", args={"ticker": "AAPL"})],
    )
    fake_response = MagicMock()
    fake_response.text = None
    fake_response.candidates = [fake_candidate]
    fake_response.automatic_function_calling_history = []

    with patch("stock_agent.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        res = stock_agent.analyze_portfolio_and_gurus(["AAPL"])

    assert res["success"] is False
    assert "maximum_remote_calls" in res["error"]


def test_analyze_portfolio_and_gurus_fails_when_api_key_missing(monkeypatch):
    """Missing GEMINI_API_KEY returns success=False with configuration error."""
    import stock_agent

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = stock_agent.analyze_portfolio_and_gurus(["AAPL"])
    assert res["success"] is False
    assert "GEMINI_API_KEY" in res["error"]


# ── Demo endpoint auth & execution (fail-closed) ──────────────────────────────

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


def test_demo_endpoint_formats_afc_history_with_name_key(demo_client, monkeypatch):
    """Demo endpoint returns logs with 'name' key (not 'tool') from AFC history."""
    from google.genai import types

    monkeypatch.setenv("CRON_SECRET", "right-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    fake_response = MagicMock()
    fake_response.text = "All checks complete."
    fake_response.automatic_function_calling_history = [
        types.Content(
            role="model",
            parts=[types.Part.from_function_call(name="get_us_stock_data", args={"ticker": "AAPL"})],
        ),
        types.Content(
            role="user",
            parts=[types.Part.from_function_response(name="get_us_stock_data", response={"result": "AAPL $213.40"})],
        ),
    ]

    # Patched at `google.genai.Client` because `run_demo_scenario` lazily imports
    # `from google import genai` inside the endpoint handler to keep cold-start fast.
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        resp = demo_client.post(
            "/api/demo/run-scenario",
            json={"scenario": "price"},
            headers={"X-Cron-Secret": "right-secret"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario"] == "price"
    assert data["logs"] == [
        {"type": "tool_call", "name": "get_us_stock_data", "args": {"ticker": "AAPL"}},
        {"type": "tool_result", "name": "get_us_stock_data", "content": "AAPL $213.40"},
        {"type": "final_output", "content": "All checks complete."},
    ]
