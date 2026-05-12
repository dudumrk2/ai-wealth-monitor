"""
stock_agent.py
==============
Orchestrates the Autonomous Financial Analyst Agent using LangGraph
(create_react_agent) backed by Google Gemini Flash.

The agent operates in a "Sense → Think → Act" loop:
  Sense  — fetches live prices for every ticker in the user's portfolio.
  Think  — scans the latest 13F filings for all TRACKED_GURUS.
  Act    — sends Telegram alerts whenever a predefined threshold is crossed.

Alert thresholds (all MUST be respected by the agent at every run):
  A) Any holding moves ≥ 5% in a single session  → price alert.
  B) A tracked guru sold 100% of a stock the user holds → risk/exit alert.
  C) A tracked guru opened a brand-new position    → idea/alpha alert.

Environment variables required:
  GEMINI_API_KEY      — Google AI Studio API key.
  TELEGRAM_BOT_TOKEN  — Telegram bot token from BotFather.
  TELEGRAM_CHAT_ID    — Telegram chat/channel ID to receive alerts.
"""

import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from stock_agent_tools import (
    TRACKED_GURUS,
    get_il_stock_data,
    get_us_stock_data,
    scan_guru_portfolio,
    send_telegram_alert,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent tools registry
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    get_us_stock_data,
    get_il_stock_data,
    scan_guru_portfolio,
    send_telegram_alert,
]

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

_TRACKED_GURUS_LIST = "\n".join(f'  - "{name}"' for name in TRACKED_GURUS)

SYSTEM_PROMPT = f"""You are an Autonomous Financial Analyst managing a private family stock portfolio.
You operate in a strict "Sense → Think → Act" loop every time you run.

═══════════════════════════════════════════════════════════════
STEP 1 — SENSE: Fetch Current Portfolio Prices
═══════════════════════════════════════════════════════════════
For EVERY ticker provided by the user:
  • If the ticker is numeric (e.g. "5131054") → call get_il_stock_data.
  • If the ticker is alphabetical (e.g. "AAPL") → call get_us_stock_data.
Record the current price and daily percentage change for each holding.

═══════════════════════════════════════════════════════════════
STEP 2 — THINK: Scan Superinvestor 13F Filings
═══════════════════════════════════════════════════════════════
ALWAYS call scan_guru_portfolio for EVERY tracked guru — no exceptions:
{_TRACKED_GURUS_LIST}

Collect the "new_positions" and "liquidated_positions" lists returned by each guru scan.

═══════════════════════════════════════════════════════════════
STEP 3 — ACT: Send Telegram Alerts When Required
═══════════════════════════════════════════════════════════════
You MUST call send_telegram_alert in the following scenarios:

  [A] PRICE ALERT
      Trigger: Any holding has a daily change ≥ +5% or ≤ -5%.
      Message format: "📊 PRICE ALERT: [TICKER] moved [±X%] today.
      Current price: [PRICE]. Action recommended: review position."

  [B] RISK ALERT — Guru Exit
      Trigger: A TRACKED_GURU fully liquidated (sold 100%) a stock that
               currently exists in the user's portfolio.
      Message format: "🚨 RISK ALERT: [GURU] exited [TICKER] completely in
      their latest 13F. You currently hold [TICKER]. Consider reviewing your
      conviction thesis."

  [C] ALPHA ALERT — Guru New Position
      Trigger: A TRACKED_GURU initiated a brand-new position.
      Message format: "💡 ALPHA IDEA: [GURU] initiated a NEW position in
      [TICKER] this quarter. Consider researching for potential addition."

If NO alerts are triggered, send a single summary message:
  "✅ Portfolio Check Complete — No significant events detected.
   Prices stable. No guru exits or new entries overlap with your portfolio."

═══════════════════════════════════════════════════════════════
OPERATING RULES
═══════════════════════════════════════════════════════════════
• Call tools sequentially — do not skip any step.
• Do NOT fabricate data. Use ONLY the tool results.
• Every Telegram message must be concise, factual, and actionable.
• After all alerts are sent, provide a brief text summary of this run's findings.
"""

# ---------------------------------------------------------------------------
# LLM + Agent Builder
# ---------------------------------------------------------------------------


def _build_agent_executor():
    """Construct and return a LangGraph ReAct agent (CompiledStateGraph).

    Uses Gemini Flash (matching config.GEMINI_MODEL_NAME across the project)
    with tool-calling enabled via langgraph.prebuilt.create_react_agent.
    The agent is built fresh on each invocation to respect hot-rotated env vars.

    Returns:
        A compiled LangGraph agent ready to be invoked with a message list.

    Raises:
        EnvironmentError: If GEMINI_API_KEY is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Cannot initialise the Financial Analyst Agent."
        )

    # temperature=0: deterministic, rule-following — no creative hallucination.
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0,
    )

    # create_react_agent wires the LLM, tools, and system prompt into a
    # LangGraph CompiledStateGraph that handles the tool-call loop internally.
    return create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
        prompt=SYSTEM_PROMPT,
    )


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------


def analyze_portfolio_and_gurus(user_portfolio_tickers: list[str]) -> dict[str, Any]:
    """Run the full Sense → Think → Act analysis cycle for the provided tickers.

    This is the main entry point called by cron jobs, API routes, or any other
    orchestration layer that needs to trigger an autonomous portfolio review.

    Args:
        user_portfolio_tickers: A flat list of ticker symbols representing the
            family's current stock holdings.  Mix of US (alphabetical, e.g.
            "AAPL") and Israeli (numeric, e.g. "5131054") tickers is supported.
            Example: ["AAPL", "NVDA", "5131054", "5122947"]

    Returns:
        A dict with keys:
          "output"   — The agent's final text summary string.
          "success"  — Boolean indicating whether the run completed without error.
          "error"    — Error message string, only present when success is False.

    Example:
        >>> result = analyze_portfolio_and_gurus(["AAPL", "NVDA", "5131054"])
        >>> print(result["output"])
    """
    if not user_portfolio_tickers:
        logger.warning("[AGENT] analyze_portfolio_and_gurus called with empty ticker list.")
        return {
            "output": "No tickers provided. Agent did not run.",
            "success": False,
            "error": "Empty portfolio list.",
        }

    tickers_formatted = ", ".join(user_portfolio_tickers)
    guru_names_formatted = ", ".join(f'"{g}"' for g in TRACKED_GURUS)

    # The human turn gives the agent its concrete task for this run.
    human_input = (
        f"Run a full portfolio analysis now.\n\n"
        f"Current Holdings: {tickers_formatted}\n\n"
        f"Superinvestors to scan: {guru_names_formatted}\n\n"
        f"Follow all three steps in the system prompt exactly. "
        f"After completing all tool calls, provide a brief summary of what you found."
    )

    logger.info(
        f"[AGENT] Starting analysis for {len(user_portfolio_tickers)} tickers: "
        f"{tickers_formatted}"
    )

    try:
        agent = _build_agent_executor()
        # LangGraph agents accept a list of BaseMessage objects.
        messages = [HumanMessage(content=human_input)]
        result = agent.invoke({"messages": messages})
        # The final answer is the content of the last AI message.
        last_msg = result["messages"][-1]
        output = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        logger.info(f"[AGENT] Run complete. Output snippet: {output[:200]}")
        return {"output": output, "success": True}

    except EnvironmentError as e:
        logger.error(f"[AGENT] Configuration error: {e}")
        return {"output": "", "success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"[AGENT] Unexpected failure during analysis: {e}")
        return {
            "output": "",
            "success": False,
            "error": f"Agent execution failed: {e}",
        }
