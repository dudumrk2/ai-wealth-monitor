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
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

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
# Structured run summary
# ---------------------------------------------------------------------------

class AgentRunSummary(BaseModel):
    """Structured summary of a single agent run, extracted from message history.

    Built by inspecting the actual tool calls made during the run — not by
    parsing the agent's free-text output.  This gives a reliable, programmatic
    view of what the agent actually did regardless of how it phrased its reply.
    """

    tickers_checked: list[str]
    total_alerts_sent: int
    price_alerts_sent: int
    risk_alerts_sent: int
    alpha_alerts_sent: int
    tool_errors: list[str]       # tool responses that start with "ERROR"
    gurus_scanned: list[str]     # populated only in full-loop (non-cron) mode
    run_duration_seconds: float
    success: bool


def _extract_run_summary(
    messages_history: list,
    start_time: float,
) -> AgentRunSummary:
    """Build an AgentRunSummary by inspecting LangGraph's message history.

    LangGraph stores every tool call (AIMessage.tool_calls) and tool response
    (ToolMessage.content) as messages.  Walking those messages gives a ground-
    truth view of what the agent actually invoked, independent of its final
    text summary.

    Args:
        messages_history: Full list of messages from agent.invoke() result.
        start_time: Unix timestamp recorded immediately before agent.invoke().

    Returns:
        AgentRunSummary with per-tool counts and any error strings encountered.
    """
    tickers_checked: list[str] = []
    gurus_scanned: list[str] = []
    tool_errors: list[str] = []
    total_alerts = price_alerts = risk_alerts = alpha_alerts = 0

    for msg in messages_history:
        # AIMessage with tool_calls → what the agent requested
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})

                if name in ("get_us_stock_data", "get_il_stock_data"):
                    ticker = args.get("ticker", "").strip()
                    if ticker:
                        tickers_checked.append(ticker)

                elif name == "send_telegram_alert":
                    total_alerts += 1
                    alert_text = args.get("message", "")
                    if "PRICE ALERT" in alert_text:
                        price_alerts += 1
                    elif "RISK ALERT" in alert_text:
                        risk_alerts += 1
                    elif "ALPHA IDEA" in alert_text:
                        alpha_alerts += 1

                elif name == "scan_guru_portfolio":
                    guru = args.get("guru_name", "").strip()
                    if guru:
                        gurus_scanned.append(guru)

        # ToolMessage → what the tool returned — capture errors
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.startswith("ERROR"):
            tool_errors.append(content[:300])

    return AgentRunSummary(
        tickers_checked=tickers_checked,
        total_alerts_sent=total_alerts,
        price_alerts_sent=price_alerts,
        risk_alerts_sent=risk_alerts,
        alpha_alerts_sent=alpha_alerts,
        tool_errors=tool_errors,
        gurus_scanned=gurus_scanned,
        run_duration_seconds=round(time.time() - start_time, 2),
        success=True,
    )


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
      Message format: "📊 PRICE ALERT: <b>[TICKER]</b> moved <b>[±X%]</b> today.
      Current price: [PRICE]. Action recommended: review position."

  [B] RISK ALERT — Guru Exit
      Trigger: A TRACKED_GURU fully liquidated (sold 100%) a stock that
               currently exists in the user's portfolio.
      Message format: "🚨 RISK ALERT: <b>[GURU]</b> exited <b>[TICKER]</b> completely in
      their latest 13F. You currently hold <b>[TICKER]</b>. Consider reviewing your
      conviction thesis."

  [C] ALPHA ALERT — Guru New Position
      Trigger: A TRACKED_GURU initiated a brand-new position.
      Message format: "💡 ALPHA IDEA: <b>[GURU]</b> initiated a NEW position in
      <b>[TICKER]</b> this quarter. Consider researching for potential addition."

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


def analyze_portfolio_and_gurus(
    user_portfolio_tickers: list[str],
    pre_analyzed_guru_data: dict[str, str] | None = None,
    telegram_chat_id: str = "",
) -> dict[str, Any]:
    """Run the full Sense → Think → Act analysis cycle for the provided tickers.

    This is the main entry point called by cron jobs, API routes, or any other
    orchestration layer that needs to trigger an autonomous portfolio review.

    Args:
        user_portfolio_tickers: A flat list of ticker symbols representing the
            family's current stock holdings.  Mix of US (alphabetical, e.g.
            "AAPL") and Israeli (numeric, e.g. "5131054") tickers is supported.
            Example: ["AAPL", "NVDA", "5131054", "5122947"]
        pre_analyzed_guru_data: Pre-computed 13F data from previous scans.
            If provided, this maps guru names to their pre-computed activity summaries,
            instructing the agent to bypass active scraping and use this data directly.
        telegram_chat_id: Per-family Telegram chat ID.  When provided, the agent
            passes this value to every send_telegram_alert call so alerts reach
            the correct family chat.  Overrides the global TELEGRAM_CHAT_ID env var.

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

    # Notification context injected into every human message so the agent
    # always passes the correct chat_id to send_telegram_alert.
    if telegram_chat_id:
        notification_instruction = (
            f"\nNotification config:\n"
            f"  Telegram chat_id: {telegram_chat_id}\n"
            f"  IMPORTANT: When calling send_telegram_alert, always pass "
            f'chat_id="{telegram_chat_id}" as the chat_id argument.\n'
        )
    else:
        notification_instruction = (
            "\nNotification config:\n"
            "  Telegram: NOT configured for this family.\n"
            "  IMPORTANT: Do NOT call send_telegram_alert. Instead, just "
            "list all triggered alerts clearly in your final summary text — "
            "they will be delivered by another channel.\n"
        )

    if pre_analyzed_guru_data is None:
        guru_names_formatted = ", ".join(f'"{g}"' for g in TRACKED_GURUS)
        # The human turn gives the agent its concrete task for this run.
        human_input = (
            f"Run a full portfolio analysis now.\n\n"
            f"Current Holdings: {tickers_formatted}\n\n"
            f"Superinvestors to scan: {guru_names_formatted}\n"
            f"{notification_instruction}\n"
            f"Follow all three steps in the system prompt exactly. "
            f"After completing all tool calls, provide a brief summary of what you found."
        )
    else:
        human_input = (
            f"Run a full portfolio analysis now.\n\n"
            f"Current Holdings: {tickers_formatted}\n\n"
            f"[PRE-COMPUTED 13F DATA — DO NOT call scan_guru_portfolio. "
            f"Use this data directly for Step 3 (ACT)]\n"
            + "\n".join(
                f"{guru}:\n{data}"
                for guru, data in pre_analyzed_guru_data.items()
            )
            + f"\n{notification_instruction}\n"
            + "Skip Step 2 entirely. Proceed to Step 1 (fetch prices for "
              "the holdings above), then Step 3 (send alerts based on the "
              "pre-computed 13F data provided). Follow all alert rules from "
              "the system prompt exactly."
        )

    logger.info(
        f"[AGENT] Starting analysis for {len(user_portfolio_tickers)} tickers: "
        f"{tickers_formatted}"
    )

    try:
        start_time = time.time()
        agent = _build_agent_executor()
        # LangGraph agents accept a list of BaseMessage objects.
        messages = [HumanMessage(content=human_input)]
        result = agent.invoke({"messages": messages})

        # Build structured summary from message history (ground-truth view).
        summary = _extract_run_summary(result["messages"], start_time)

        # Validate: warn if the agent skipped any tickers.
        skipped = set(user_portfolio_tickers) - set(summary.tickers_checked)
        if skipped:
            logger.warning(
                f"[AGENT] Price check skipped for tickers: {skipped}. "
                f"Agent may have missed these holdings."
            )

        # Validate: warn on any tool errors encountered during the run.
        if summary.tool_errors:
            logger.warning(
                f"[AGENT] {len(summary.tool_errors)} tool error(s) during run: "
                f"{summary.tool_errors}"
            )

        # The final answer is the content of the last AI message.
        last_msg = result["messages"][-1]
        output = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        logger.info(
            f"[AGENT] Run complete in {summary.run_duration_seconds}s — "
            f"checked {len(summary.tickers_checked)} tickers, "
            f"sent {summary.total_alerts_sent} alert(s) "
            f"({summary.price_alerts_sent} price / "
            f"{summary.risk_alerts_sent} risk / "
            f"{summary.alpha_alerts_sent} alpha)"
        )

        return {"output": output, "success": True, "summary": summary.model_dump()}

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
