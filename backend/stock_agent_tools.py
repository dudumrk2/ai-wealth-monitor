"""
stock_agent_tools.py
====================
LangChain @tool definitions for the Autonomous Financial Analyst Agent.

These tools equip the LLM agent with the ability to:
  1. Fetch live US stock prices via yfinance.
  2. Fetch live Israeli (TASE) stock/fund prices via the existing Bizportal scraper.
  3. Send real-time push notifications to a Telegram chat.

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
import yfinance as yf
from langchain_core.tools import tool

# Import the existing TASE web-scraping function to avoid duplicating logic.
# fetch_bizportal_fund_data scrapes Bizportal.co.il for Israeli mutual funds /
# ETFs identified by a numeric fund code.
from services.scraper import fetch_bizportal_fund_data

logger = logging.getLogger(__name__)


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
# Tool 3 — Telegram Alert
# ---------------------------------------------------------------------------

@tool
def send_telegram_alert(message: str) -> str:
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

    The bot token and destination chat are read from environment variables:
      TELEGRAM_BOT_TOKEN  (required) — Telegram bot token from BotFather.
      TELEGRAM_CHAT_ID    (required) — Numeric chat / channel ID.

    Args:
        message: The notification text to send. Supports Telegram MarkdownV2
                 formatting (bold, italic, inline code, etc.).  Keep messages
                 concise and actionable — ideally one to three sentences.

    Returns:
        A confirmation string on success, or a descriptive error message if the
        Telegram API call failed.  Examples:
          "✅ Telegram alert sent successfully."
          "ERROR [send_telegram_alert]: TELEGRAM_BOT_TOKEN is not set in environment."
          "ERROR [send_telegram_alert]: Telegram API returned HTTP 400 — Bad Request."
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        msg = "ERROR [send_telegram_alert]: TELEGRAM_BOT_TOKEN is not set in environment variables."
        logger.error(msg)
        return msg

    if not chat_id:
        msg = "ERROR [send_telegram_alert]: TELEGRAM_CHAT_ID is not set in environment variables."
        logger.error(msg)
        return msg

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",   # Standard Markdown — safe default; switch to MarkdownV2 if needed
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
