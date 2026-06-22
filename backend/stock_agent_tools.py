"""
stock_agent_tools.py
====================
LangChain @tool definitions for the Autonomous Financial Analyst Agent.

These tools equip the LLM agent with the ability to:
  1. Fetch live US stock prices via yfinance.
  2. Fetch live Israeli (TASE) stock/fund prices via the existing Bizportal scraper.
  3. Send real-time push notifications to a Telegram chat.
  4. Scan Superinvestor 13F filings for new and liquidated positions (alpha signals).
  5. Search recent financial news headlines for any US ticker via yfinance.

Security: Only yfinance, requests, python-telegram-bot, httpx, and
beautifulsoup4 are used for external integrations — no other outbound
HTTP libraries are introduced.

Environment variables required (loaded from .env by the calling process):
  TELEGRAM_BOT_TOKEN  — The token issued by BotFather for the Telegram bot.
  TELEGRAM_CHAT_ID    — The numeric chat / channel ID to send alerts to.
"""

import logging
import os

import requests
from bs4 import BeautifulSoup
import yfinance as yf
from langchain_core.tools import tool

# Import the existing TASE web-scraping function to avoid duplicating logic.
# fetch_bizportal_fund_data scrapes Bizportal.co.il for Israeli mutual funds /
# ETFs identified by a numeric fund code.
from services.scraper import fetch_bizportal_fund_data

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo / Presentation mock data
# ---------------------------------------------------------------------------

DEMO_SCENARIOS: dict[str, dict[str, str]] = {
    "price": {
        "get_us_stock_data:AAPL":
            "AAPL last price: $213.40 USD  ▲ +6.10% vs previous close ($201.13)",
        "get_us_stock_data:ICL.TA":
            "ICL.TA last price: $15.90 USD  ▼ -0.60% vs previous close ($16.00)",
        "get_il_stock_data:5131054":
            "Israeli fund/ETF 5131054 last price: ₪12.34 NIS  ▲ +0.20% (daily change)",
        "search_financial_news:AAPL": (
            "Recent news for AAPL:\n"
            "1. Apple surges after surprise AI partnership with OpenAI — https://finance.yahoo.com/news/apple-ai-openai\n"
            "2. iPhone 17 demand data beats Wall Street estimates — https://finance.yahoo.com/news/iphone17-demand\n"
            "3. AAPL breaks above $210 resistance for first time in 2025 — https://finance.yahoo.com/news/aapl-210"
        ),
        "scan_guru_portfolio:Berkshire Hathaway":
            "Berkshire Hathaway — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): OXY\n  🚪 Liquidated positions (sold 100%): PARA",
        "scan_guru_portfolio:Pershing Square":
            "Pershing Square — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Scion Asset Management":
            "Scion Asset Management — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
    },
    "risk": {
        "get_us_stock_data:AAPL":
            "AAPL last price: $192.10 USD  ▲ +0.80% vs previous close ($190.58)",
        "get_us_stock_data:ICL.TA":
            "ICL.TA last price: $15.90 USD  ▼ -0.40% vs previous close ($16.00)",
        "get_il_stock_data:5131054":
            "Israeli fund/ETF 5131054 last price: ₪12.34 NIS  ▲ +0.10% (daily change)",
        "scan_guru_portfolio:Berkshire Hathaway":
            "Berkshire Hathaway — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): AAPL",
        "scan_guru_portfolio:Pershing Square":
            "Pershing Square — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Scion Asset Management":
            "Scion Asset Management — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
    },
    "alpha": {
        "get_us_stock_data:AAPL":
            "AAPL last price: $193.20 USD  ▲ +1.20% vs previous close ($190.90)",
        "get_us_stock_data:ICL.TA":
            "ICL.TA last price: $16.10 USD  ▲ +0.60% vs previous close ($16.00)",
        "get_il_stock_data:5131054":
            "Israeli fund/ETF 5131054 last price: ₪12.34 NIS  ▲ +0.05% (daily change)",
        "scan_guru_portfolio:Berkshire Hathaway":
            "Berkshire Hathaway — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): GOOGL, TSM\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Pershing Square":
            "Pershing Square — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Scion Asset Management":
            "Scion Asset Management — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): NVO\n  🚪 Liquidated positions (sold 100%): BABA",
    },
    "clear": {
        "get_us_stock_data:AAPL":
            "AAPL last price: $191.50 USD  ▲ +0.30% vs previous close ($190.93)",
        "get_us_stock_data:ICL.TA":
            "ICL.TA last price: $16.20 USD  ▲ +0.10% vs previous close ($16.18)",
        "get_il_stock_data:5131054":
            "Israeli fund/ETF 5131054 last price: ₪12.34 NIS  ▲ +0.05% (daily change)",
        "scan_guru_portfolio:Berkshire Hathaway":
            "Berkshire Hathaway — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Pershing Square":
            "Pershing Square — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
        "scan_guru_portfolio:Scion Asset Management":
            "Scion Asset Management — Q1 2025 13F Activity (Dataroma):\n  🆕 New positions (initiated this quarter): None\n  🚪 Liquidated positions (sold 100%): None",
    },
}


def build_demo_tools(scenario_name: str) -> list:
    """Return mock LangChain tools for a named demo scenario.

    The returned tools have identical signatures to the real AGENT_TOOLS so the
    agent's system prompt and tool-calling logic work without any changes.
    Only the return values are replaced with controlled mock strings.
    """
    mock = DEMO_SCENARIOS.get(scenario_name, DEMO_SCENARIOS["clear"])

    def _get(key: str, fallback: str) -> str:
        return mock.get(key, fallback)

    @tool
    def get_us_stock_data(ticker: str) -> str:  # noqa: F811
        """Fetch the latest closing price for a US-listed stock or ETF from Yahoo Finance."""
        ticker = ticker.strip().upper()
        return _get(f"get_us_stock_data:{ticker}", f"{ticker} last price: $150.00 USD  ▲ +0.50%")

    @tool
    def get_il_stock_data(ticker: str) -> str:  # noqa: F811
        """Fetch the latest price for an Israeli security (TASE mutual fund or ETF) from Bizportal."""
        return _get(f"get_il_stock_data:{ticker.strip()}", f"Israeli fund/ETF {ticker} last price: ₪12.00 NIS  ▲ +0.10%")

    @tool
    def scan_guru_portfolio(guru_name: str) -> str:  # noqa: F811
        """Scan the latest 13F filing activity for a tracked Superinvestor.

        Supported: "Berkshire Hathaway", "Pershing Square", "Scion Asset Management".
        """
        return _get(
            f"scan_guru_portfolio:{guru_name.strip()}",
            f"{guru_name} — Q1 2025 13F Activity:\n  🆕 New positions: None\n  🚪 Liquidated positions: None",
        )

    @tool
    def search_financial_news(ticker: str) -> str:  # noqa: F811
        """Fetch the 3 most recent financial news headlines for a US-listed stock via Yahoo Finance."""
        ticker = ticker.strip().upper()
        return _get(f"search_financial_news:{ticker}", f"No recent news found for {ticker}.")

    @tool
    def send_telegram_alert(message: str, chat_id: str = "") -> str:  # noqa: F811
        """Send a push notification message to the family Telegram chat via the configured bot."""
        logger.info(f"[DEMO send_telegram_alert] {message[:120]}")
        return "✅ Telegram alert sent successfully."

    return [get_us_stock_data, get_il_stock_data, scan_guru_portfolio, search_financial_news, send_telegram_alert]


# ---------------------------------------------------------------------------
# Tool 1 — US Stock Data
# ---------------------------------------------------------------------------

@tool
def get_us_stock_data(ticker: str) -> str:
    """Fetch the latest closing price for a US-listed stock or ETF from Yahoo Finance.

    Use this tool when the user or the monitoring workflow asks for the current
    price of any stock traded on a US exchange (NYSE, NASDAQ, CBOE, etc.),
    including US-listed ETFs and ADRs.  Examples of valid tickers: "AAPL",
    "MSFT", "NVDA", "SPY", "QQQ", "TSLA".

    Do NOT use this tool for Israeli securities — use get_il_stock_data instead.

    Args:
        ticker: The uppercase US ticker symbol (e.g. "AAPL", "MSFT").
                Must match the symbol as listed on Yahoo Finance.

    Returns:
        A human-readable string reporting the latest price in USD, or an error
        message if the data could not be retrieved.  Examples:
          "AAPL last price: $182.63 USD"
          "ERROR [get_us_stock_data]: No price data returned for ticker 'XYZ'"
    """
    ticker = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")

        if hist.empty:
            msg = f"ERROR [get_us_stock_data]: No price data returned for ticker '{ticker}'. " \
                  f"Verify the symbol is correct and that US markets are not closed."
            logger.warning(msg)
            return msg

        last_price = float(hist["Close"].iloc[-1])
        prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_price
        daily_change_pct = ((last_price - prev_price) / prev_price * 100) if prev_price > 0 else 0.0
        direction = "▲" if daily_change_pct >= 0 else "▼"

        result = (
            f"{ticker} last price: ${last_price:,.4f} USD  "
            f"{direction} {daily_change_pct:+.2f}% vs previous close (${prev_price:,.4f})"
        )
        logger.info(f"[get_us_stock_data] {result}")
        return result

    except Exception as e:
        msg = f"ERROR [get_us_stock_data]: Failed to fetch data for '{ticker}'. Reason: {e}"
        logger.error(msg)
        return msg


# ---------------------------------------------------------------------------
# Tool 2 — Israeli (TASE) Stock / Fund Data
# ---------------------------------------------------------------------------

@tool
def get_il_stock_data(ticker: str) -> str:
    """Fetch the latest price for an Israeli security (TASE mutual fund or ETF) from Bizportal.

    Use this tool when the user or the monitoring workflow asks for the current
    price of an Israeli-market security.  Israeli mutual funds and ETFs traded
    on the Tel Aviv Stock Exchange (TASE) are identified by a numeric fund code
    (typically 6–7 digits), NOT by a letter-based symbol.

    Examples of valid Israeli fund codes: "5131054", "5122947", "1159014".

    Do NOT use this tool for US-listed securities — use get_us_stock_data instead.

    This tool delegates to the project's existing fetch_bizportal_fund_data()
    scraper (services/scraper.py), which parses the Bizportal.co.il website for
    live price information.  Prices returned by Bizportal are originally in
    Agorot (1 NIS = 100 Agorot); the scraper converts them to NIS automatically.

    Args:
        ticker: The numeric Israeli fund / security code as a string
                (e.g. "5131054"). Must be the Bizportal-compatible numeric code.

    Returns:
        A human-readable string with the price in NIS (converted from Agorot),
        or an error message if the scraper could not retrieve data.  Examples:
          "Israeli fund 5131054 last price: ₪12.34 NIS (daily change: +0.45%)"
          "ERROR [get_il_stock_data]: Could not fetch data for IL fund '9999999'"
    """
    ticker = ticker.strip()
    try:
        fund_data = fetch_bizportal_fund_data(ticker)

        if fund_data is None:
            msg = (
                f"ERROR [get_il_stock_data]: Could not fetch data for IL fund '{ticker}'. "
                f"The Bizportal scraper returned no data — verify the numeric fund code is correct."
            )
            logger.warning(msg)
            return msg

        current_price: float = fund_data["current_price"]     # already in NIS
        pct_change: float = fund_data.get("pct_change", 0.0)
        direction = "▲" if pct_change >= 0 else "▼"

        result = (
            f"Israeli fund/ETF {ticker} last price: ₪{current_price:,.4f} NIS  "
            f"{direction} {pct_change:+.2f}% (daily change)"
        )
        logger.info(f"[get_il_stock_data] {result}")
        return result

    except Exception as e:
        msg = f"ERROR [get_il_stock_data]: Unexpected failure for IL ticker '{ticker}'. Reason: {e}"
        logger.error(msg)
        return msg


# ---------------------------------------------------------------------------
# Tool 3 — Financial News Search
# ---------------------------------------------------------------------------

@tool
def search_financial_news(ticker: str) -> str:
    """Fetch the 3 most recent financial news headlines for a US-listed stock via Yahoo Finance.

    Use this tool when a stock has moved significantly (e.g. ≥ 5% in a session)
    and you want to understand WHY — to enrich an alert with context.

    Do NOT use this tool for Israeli numeric fund codes — it is designed for
    US ticker symbols only (e.g. "AAPL", "NVDA", "TSLA").

    Args:
        ticker: The uppercase US ticker symbol (e.g. "AAPL").

    Returns:
        Up to 3 recent headlines, each on its own line, with a short URL.
        Example:
          "1. Apple hits all-time high ahead of earnings — https://finance.yahoo.com/..."
          "2. iPhone demand surge drives AAPL rally — https://..."
        Returns an error message if no news is found or the request fails.
    """
    ticker = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker)
        news = t.news or []

        if not news:
            return f"No recent news found for {ticker}."

        lines = []
        for i, item in enumerate(news[:3], start=1):
            content = item.get("content", {})
            title = content.get("title", "").strip()
            # Yahoo Finance news items nest the URL inside content.canonicalUrl or clickThroughUrl
            url = (
                content.get("canonicalUrl", {}).get("url", "")
                or content.get("clickThroughUrl", {}).get("url", "")
                or ""
            )
            if title:
                lines.append(f"{i}. {title}" + (f" — {url}" if url else ""))

        if not lines:
            return f"No readable headlines found for {ticker}."

        result = f"Recent news for {ticker}:\n" + "\n".join(lines)
        logger.info(f"[search_financial_news] {ticker}: {len(lines)} headline(s) retrieved")
        return result

    except Exception as e:
        msg = f"ERROR [search_financial_news]: Failed to fetch news for '{ticker}'. Reason: {e}"
        logger.error(msg)
        return msg


# ---------------------------------------------------------------------------
# Tool 4 — Telegram Alert
# ---------------------------------------------------------------------------

@tool
def send_telegram_alert(message: str, chat_id: str = "") -> str:
    """Send a push notification message to the family Telegram chat via the configured bot.

    Use this tool whenever the agent needs to notify the user about a significant
    financial event, such as:
      - A monitored stock crossing a price threshold.
      - A Superinvestor 13F filing detecting a new position or a full exit.
      - A portfolio alert (e.g. large daily drawdown, currency spike).
      - Any other time-sensitive insight that warrants an immediate human notification.

    Do NOT use this tool for routine status updates or informational summaries
    that the user did not explicitly request to be notified about — prefer
    returning a text response from the agent instead.

    The bot token is read from the TELEGRAM_BOT_TOKEN environment variable.
    The destination chat ID comes from the `chat_id` argument (preferred) and
    falls back to the TELEGRAM_CHAT_ID environment variable when not supplied.

    Args:
        message: The notification text to send. Supports HTML formatting
                 (e.g. <b>bold</b>, <i>italic</i>).  Keep messages
                 concise and actionable — ideally one to three sentences.
        chat_id: The numeric Telegram chat / channel ID to send the alert to.
                 Pass the value provided in the run context.  Leave empty to
                 fall back to the TELEGRAM_CHAT_ID environment variable.

    Returns:
        A confirmation string on success, or a descriptive error message if the
        Telegram API call failed.  Examples:
          "✅ Telegram alert sent successfully."
          "ERROR [send_telegram_alert]: TELEGRAM_BOT_TOKEN is not set in environment."
          "ERROR [send_telegram_alert]: Telegram API returned HTTP 400 — Bad Request."
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    # Prefer the per-call chat_id argument; fall back to the global env var.
    resolved_chat_id = chat_id.strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        msg = "ERROR [send_telegram_alert]: TELEGRAM_BOT_TOKEN is not set in environment variables."
        logger.error(msg)
        return msg

    if not resolved_chat_id:
        msg = "ERROR [send_telegram_alert]: No chat_id provided and TELEGRAM_CHAT_ID is not set in environment variables."
        logger.error(msg)
        return msg

    chat_id = resolved_chat_id

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",   # HTML — stable across special chars (-, ., parens) in alert text
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info(f"[send_telegram_alert] Alert sent to chat {chat_id}: {message[:80]}...")
            return "✅ Telegram alert sent successfully."

        # Provide actionable feedback on known HTTP error codes
        error_detail = response.json().get("description", "No details returned.")
        msg = (
            f"ERROR [send_telegram_alert]: Telegram API returned HTTP {response.status_code}. "
            f"Details: {error_detail}"
        )
        logger.error(msg)
        return msg

    except requests.exceptions.Timeout:
        msg = "ERROR [send_telegram_alert]: Request timed out while contacting the Telegram API."
        logger.error(msg)
        return msg

    except Exception as e:
        msg = f"ERROR [send_telegram_alert]: Unexpected failure. Reason: {e}"
        logger.error(msg)
        return msg


# ---------------------------------------------------------------------------
# Constant: Tracked Superinvestors
# ---------------------------------------------------------------------------

# Canonical guru names accepted by scan_guru_portfolio, mapped to their
# Dataroma 'm=' URL parameter (verified against dataroma.com/m/managers.php).
TRACKED_GURUS: dict[str, str] = {
    "Berkshire Hathaway": "BRK",
    "Pershing Square":    "psc",
    "Scion Asset Management": "SAM",
}

# ---------------------------------------------------------------------------
# Tool 4 — Superinvestor 13F Scanner (Dataroma)
# ---------------------------------------------------------------------------

_DATAROMA_ACTIVITY_URL = "https://www.dataroma.com/m/m_activity.php"
_DATAROMA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.dataroma.com/",
}


def _extract_ticker(stock_cell_text: str) -> str:
    """Extract the ticker symbol from a Dataroma stock cell string.

    Dataroma renders stock cells as: "AAPL - Apple Inc."
    This helper returns the part before ' - ', uppercased and stripped.
    """
    return stock_cell_text.split(" - ")[0].strip().upper()


@tool
def scan_guru_portfolio(guru_name: str) -> str:
    """Scan the latest 13F filing activity for a tracked Superinvestor and extract alpha signals.

    Use this tool when you need to identify investment ideas or risk warnings derived
    from the most recent quarterly 13F moves of elite institutional investors
    (\"Superinvestors\").  Specifically, this tool extracts:

      - **new_positions**: Stocks the guru initiated for the FIRST TIME this quarter
        (a potential conviction BUY signal worth investigating for the family portfolio).
      - **liquidated_positions**: Stocks the guru sold 100% of their stake in
        (a potential EXIT or RISK WARNING signal — especially if held in the family portfolio).

    When to use this tool:
      - User asks: \"What did Buffett buy / sell this quarter?\"
      - User asks: \"Did Ackman exit any positions recently?\"
      - User asks: \"Generate new stock ideas from Superinvestor moves.\"
      - As part of a weekly monitoring routine to flag any overlap between guru
        liquidations and the family's current holdings.

    Supported guru names (must match exactly, case-insensitive):
      - \"Berkshire Hathaway\"  (Warren Buffett)
      - \"Pershing Square\"     (Bill Ackman)
      - \"Scion Asset Management\" (Michael Burry)

    Data source: Dataroma.com (aggregates SEC 13F filings, updated quarterly,
    typically 45 days after each quarter end).

    Args:
        guru_name: The name of the Superinvestor to query.  Must be one of the
                   values listed in TRACKED_GURUS.  Case-insensitive matching
                   is applied, so \"berkshire hathaway\" also works.

    Returns:
        A structured plain-text summary of the latest quarter's NEW and LIQUIDATED
        positions, e.g.:
            \"Berkshire Hathaway — Q4 2024 13F Activity:\\n\"
            \"  🆕 New positions (initiated this quarter): NYT, ULTA\\n\"
            \"  🚪 Liquidated positions (sold 100%): HPQ, PARA\\n\"
        Returns an error message string if the guru is not supported, the page
        cannot be reached, or the HTML structure has changed.
    """
    # --- Resolve guru name to Dataroma ID ---
    normalised = guru_name.strip()
    guru_id: str | None = None
    for key, val in TRACKED_GURUS.items():
        if key.lower() == normalised.lower():
            guru_id = val
            guru_id_display = key
            break

    if guru_id is None:
        supported = ", ".join(f'"{k}"' for k in TRACKED_GURUS)
        msg = (
            f"ERROR [scan_guru_portfolio]: Unknown guru '{guru_name}'. "
            f"Supported gurus: {supported}"
        )
        logger.warning(msg)
        return msg

    # --- Fetch the activity page from Dataroma ---
    url = _DATAROMA_ACTIVITY_URL
    params = {"m": guru_id, "typ": "a"}  # typ=a → all activity (new + sells + adds)

    try:
        response = requests.get(
            url, params=params, headers=_DATAROMA_HEADERS, timeout=15
        )
        if response.status_code != 200:
            msg = (
                f"ERROR [scan_guru_portfolio]: Dataroma returned HTTP {response.status_code} "
                f"for guru '{guru_id_display}' (m={guru_id}). The site may be temporarily "
                f"unavailable or the guru ID may have changed."
            )
            logger.error(msg)
            return msg

    except requests.exceptions.Timeout:
        msg = f"ERROR [scan_guru_portfolio]: Request timed out fetching Dataroma for '{guru_id_display}'."
        logger.error(msg)
        return msg
    except Exception as e:
        msg = f"ERROR [scan_guru_portfolio]: Network error for '{guru_id_display}': {e}"
        logger.error(msg)
        return msg

    # --- Parse the HTML ---
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"id": "grid"})

        if table is None:
            msg = (
                f"ERROR [scan_guru_portfolio]: Could not find activity table (id='grid') "
                f"on the Dataroma page for '{guru_id_display}'. The site layout may have changed."
            )
            logger.error(msg)
            return msg

        rows = table.find_all("tr")

        new_positions: list[str] = []
        liquidated_positions: list[str] = []
        current_quarter: str = ""
        latest_quarter: str = ""

        for row in rows:
            cells = row.find_all("td")

            # Quarter header row: single cell containing the quarter label (e.g. "Q4 2024")
            if len(cells) == 1:
                text = cells[0].get_text(strip=True)
                if text and not latest_quarter:
                    latest_quarter = text   # capture the FIRST (= most recent) quarter only
                current_quarter = text
                continue

            # Skip header rows (th elements) and rows from older quarters
            if not cells or current_quarter != latest_quarter:
                continue

            # Data rows have 5 cells:
            # [0] history icon | [1] "TICKER - Company Name" | [2] activity label
            # [3] share change  | [4] % portfolio change
            if len(cells) < 3:
                continue

            stock_text = cells[1].get_text(strip=True)
            activity_text = cells[2].get_text(strip=True)

            if not stock_text or not activity_text:
                continue

            ticker = _extract_ticker(stock_text)
            if not ticker:
                continue

            # "Buy" = brand-new position initiated this quarter
            if activity_text == "Buy":
                new_positions.append(ticker)

            # "Sell 100.00%" = full liquidation (may contain different decimal formats)
            elif "sell" in activity_text.lower() and "100" in activity_text:
                liquidated_positions.append(ticker)

        # --- Format the result ---
        if not latest_quarter:
            msg = (
                f"ERROR [scan_guru_portfolio]: No quarterly data found for '{guru_id_display}'. "
                f"The page structure may have changed or the guru has no recorded activity."
            )
            logger.warning(msg)
            return msg

        new_str = ", ".join(new_positions) if new_positions else "None"
        liq_str = ", ".join(liquidated_positions) if liquidated_positions else "None"

        result = (
            f"{guru_id_display} — {latest_quarter} 13F Activity (Dataroma):\n"
            f"  🆕 New positions (initiated this quarter): {new_str}\n"
            f"  🚪 Liquidated positions (sold 100%): {liq_str}"
        )
        logger.info(f"[scan_guru_portfolio] {result}")
        return result

    except Exception as e:
        msg = f"ERROR [scan_guru_portfolio]: Failed to parse Dataroma response for '{guru_id_display}': {e}"
        logger.error(msg)
        return msg
