"""
routers/agent.py
================
FastAPI router for the autonomous LangGraph Financial Analyst Agent.

Exposes three endpoints:
  POST /api/cron/analyze-stocks                — cron-secured daily trigger (all families)
  POST /api/settings/cron/analyze-stocks/run  — authenticated manual trigger (own family)
  POST /api/demo/run-scenario                  — presentation demo with mock tools (cron-secret secured)
"""

import asyncio
import base64
import os
import re
import time
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Request

import db_manager
from auth import verify_token

# NOTE: stock_agent / stock_agent_tools / langchain are intentionally NOT imported
# at module level — they pull in langchain_google_genai + langgraph + yfinance
# (~20s of import time). They are exposed lazily (PEP 562 __getattr__ below) so
# merely registering this router (on every app startup / cold start) stays cheap,
# while `agent_module.scan_guru_portfolio` etc. remain patchable test seams.

router = APIRouter(tags=["Agent"])

# stock_agent / stock_agent_tools pull in langchain + langgraph + yfinance (heavy).
# They are bound lazily on first use (keeping cold start fast) and kept as module
# globals so tests can patch `agent.scan_guru_portfolio` / `agent.TRACKED_GURUS` /
# `agent.analyze_portfolio_and_gurus`.
analyze_portfolio_and_gurus = None
TRACKED_GURUS = None
scan_guru_portfolio = None


def _load_agent_deps():
    global analyze_portfolio_and_gurus, TRACKED_GURUS, scan_guru_portfolio
    if scan_guru_portfolio is None:
        from stock_agent import analyze_portfolio_and_gurus as _analyze
        from stock_agent_tools import TRACKED_GURUS as _gurus, scan_guru_portfolio as _scan
        analyze_portfolio_and_gurus, TRACKED_GURUS, scan_guru_portfolio = _analyze, _gurus, _scan


# ---------------------------------------------------------------------------
# Email fallback helper
# ---------------------------------------------------------------------------

def _send_agent_summary_email(uid: str, profile: dict, agent_output: str) -> None:
    """Send the agent's findings via email when Telegram is not configured.

    Mirrors the Gmail-send pattern used by _weekly_stock_summary_for_family.
    Silently swallows errors so a missing Gmail setup never breaks the agent run.

    Args:
        uid: Family UID (used only for log messages).
        profile: Firestore family profile dict — must contain gmail_refresh_token
                 and pii_data.member1.email for the send to succeed.
        agent_output: The agent's final summary text (plain text or light HTML).
    """
    import markdown

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        refresh_token = profile.get("gmail_refresh_token")
        if not refresh_token:
            print(f"⚠️  [AGENT] No Gmail refresh_token for {uid} — skipping email fallback.")
            return

        email_addr = profile.get("pii_data", {}).get("member1", {}).get("email")
        if not email_addr:
            print(f"⚠️  [AGENT] No email address for {uid} — skipping email fallback.")
            return

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        html_body = markdown.markdown(agent_output)
        email_html = (
            "<html><head><style>"
            "body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }"
            "h2 { color: #2c3e50; } b { color: #1abc9c; }"
            "</style></head>"
            f"<body dir='ltr'>{html_body}</body></html>"
        )

        message = MIMEText(email_html, "html", "utf-8")
        message["To"] = email_addr
        message["Subject"] = "Stock Agent Alert — Portfolio Analysis"
        raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw_msg}).execute()
        print(f"📧 [AGENT] Email fallback sent to {email_addr} for {uid}.")

    except Exception as e:
        print(f"⚠️  [AGENT] Email fallback failed for {uid}: {e}")


# ---------------------------------------------------------------------------
# Internal orchestration helper
# ---------------------------------------------------------------------------

def _analyze_stocks_for_family(uid: str) -> dict:
    """Run the autonomous stock agent for a single family with 13F deduplication.

    Flow:
      1. Fetch family holdings from Firestore.
      2. Run scan_guru_portfolio for each tracked guru (outside the agent).
      3. Compute which 13F alerts are new (not yet sent).
      4. Invoke the LangGraph agent with pre-computed guru data.
      5. Mark new alerts as sent in Firestore on success.

    Returns a result dict with uid, success flag, and agent output.
    """
    _load_agent_deps()  # lazy: import langchain/langgraph/yfinance only when the agent runs

    print(f"\n🤖 [AGENT] Starting analysis for family: {uid}")

    # Step 1 — Profile & holdings
    profile = db_manager.get_family_profile(uid)
    if not profile:
        print(f"⚠️  [AGENT] No profile found for {uid}")
        return {"uid": uid, "status": "error", "reason": "no_profile"}

    holdings = db_manager.get_family_holdings(uid)
    if not holdings:
        print(f"⚠️  [AGENT] No holdings found for {uid}")
        return {"uid": uid, "status": "error", "reason": "no_holdings"}

    tickers = [h["id"] for h in holdings]
    print(f"📊 [AGENT] Holdings for {uid}: {tickers}")

    # Notification channel — prefer per-family Telegram chat_id, fall back to email.
    telegram_chat_id: str = profile.get("telegram_chat_id", "") or ""
    print(
        f"🔔 [AGENT] Notification channel for {uid}: "
        f"{'Telegram chat_id=' + telegram_chat_id if telegram_chat_id else 'email fallback'}"
    )

    # Step 2 — Pre-fetch 13F data outside the agent
    guru_results: dict[str, str] = {}
    for guru_name in TRACKED_GURUS.keys():
        print(f"🔍 [AGENT] Scanning guru: {guru_name}")
        guru_results[guru_name] = scan_guru_portfolio.invoke({"guru_name": guru_name})

    # Step 3 — Compute new alert keys
    sent_keys = db_manager.get_sent_13f_alert_keys()
    all_alert_keys: set[str] = set()

    for guru_name, result_str in guru_results.items():
        quarter_match = re.search(r'(Q\d \d{4})', result_str)
        if not quarter_match:
            continue
        quarter = quarter_match.group(1)

        for line in result_str.splitlines():
            if "New positions" in line or "Liquidated positions" in line:
                # Tickers appear after the colon on the same line
                colon_idx = line.rfind(":")
                if colon_idx == -1:
                    continue
                tickers_str = line[colon_idx + 1:].strip()
                if tickers_str.lower() == "none" or not tickers_str:
                    continue
                for ticker in [t.strip() for t in tickers_str.split(",")]:
                    if ticker:
                        all_alert_keys.add(f"{guru_name}:{ticker}:{quarter}")

    new_alert_keys = all_alert_keys - sent_keys
    print(f"🆕 [AGENT] New alert keys to process for {uid}: {len(new_alert_keys)}")

    # Step 4 — Run agent with pre-computed data
    result = analyze_portfolio_and_gurus(
        tickers,
        pre_analyzed_guru_data=guru_results,
        telegram_chat_id=telegram_chat_id,
    )

    # Step 5 — Mark new alerts as sent on success
    if result.get("success"):
        for key in new_alert_keys:
            db_manager.mark_13f_alert_sent(key)
        print(f"✅ [AGENT] Analysis complete for {uid}. "
              f"Marked {len(new_alert_keys)} new alerts as sent.")

        # Step 6 — Email fallback when Telegram is not configured
        if not telegram_chat_id:
            _send_agent_summary_email(uid, profile, result.get("output", ""))
    else:
        print(f"❌ [AGENT] Analysis failed for {uid}: {result.get('error', 'unknown')}")

    return {
        "uid": uid,
        "success": result.get("success", False),
        "new_alerts_marked": len(new_alert_keys) if result.get("success") else 0,
        "notification_channel": "telegram" if telegram_chat_id else "email",
        "output_snippet": result.get("output", "")[:200],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/cron/analyze-stocks")
async def analyze_stocks_cron(request: Request):
    """
    Daily cron endpoint to run the autonomous LangGraph stock agent for all families.
    Fetches live prices, scans Superinvestor 13F filings, and sends Telegram alerts.
    Deduplication prevents repeat 13F alerts across runs.
    Secured via X-Cron-Secret header.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: invalid or missing X-Cron-Secret"
        )

    uids = db_manager.get_all_family_uids_for_holdings()
    print(f"\n🤖 [CRON] analyze-stocks — targeting {len(uids)} family/families")

    results = []
    for uid in uids:
        profile = db_manager.get_family_profile(uid)
        if profile and profile.get("cron_agent_enabled", True) is False:
            print(f"⏭️  [CRON] Skipping analyze-stocks for {uid} (disabled in settings)")
            continue
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(_analyze_stocks_for_family, uid),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
            print(f"⏰ [CRON] Agent run timed out (180s) for family: {uid}")
            res = {
                "uid": uid,
                "success": False,
                "error": "agent_timeout_180s",
                "new_alerts_marked": 0,
            }
        results.append(res)

    return {
        "status": "success",
        "families_processed": len(results),
        "results": results,
    }


@router.post("/api/demo/run-scenario")
async def run_demo_scenario(request: Request):
    """Presentation demo endpoint — runs the real LangGraph agent with mock tools.

    Secured via X-Cron-Secret header (same secret as the cron endpoint).
    Accepts body: {"scenario": "price" | "risk" | "alpha" | "clear"}

    Returns the agent's actual tool calls and final output so the presentation
    page can display what the real agent decided to do.
    """
    # Fail closed: reject if the secret is unset OR does not match (mirrors
    # analyze_stocks_cron). This endpoint triggers paid Gemini calls, so it must
    # never be reachable without a configured secret.
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    body = await request.json()
    scenario_name = body.get("scenario", "clear")

    # Lazy imports — keep langchain/langgraph/agent modules out of the cold-start path.
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.prebuilt import create_react_agent
    from stock_agent import AGENT_RECURSION_LIMIT, SYSTEM_PROMPT
    from stock_agent_tools import DEMO_SCENARIOS, build_demo_tools

    if scenario_name not in DEMO_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario_name}'. Choose: {list(DEMO_SCENARIOS)}")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")

    mock_tools = build_demo_tools(scenario_name)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0)
    agent = create_react_agent(model=llm, tools=mock_tools, prompt=SYSTEM_PROMPT)

    tickers = ["AAPL", "ICL.TA", "5131054"]
    human_input = (
        f"Run a full portfolio analysis now.\n\n"
        f"Current Holdings: {', '.join(tickers)}\n\n"
        f"Superinvestors to scan: \"Berkshire Hathaway\", \"Pershing Square\", \"Scion Asset Management\"\n\n"
        f"Notification config:\n"
        f"  Telegram chat_id: demo-presentation\n"
        f"  IMPORTANT: When calling send_telegram_alert, always pass chat_id=\"demo-presentation\".\n\n"
        f"Follow all three steps exactly. After all tool calls, provide a brief summary."
    )

    def _run():
        start = time.time()
        result = agent.invoke(
            {"messages": [HumanMessage(content=human_input)]},
            config={"recursion_limit": AGENT_RECURSION_LIMIT},
        )
        logs = []
        for msg in result["messages"]:
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    logs.append({"type": "tool_call", "name": tc["name"], "args": tc.get("args", {})})
            if isinstance(msg, ToolMessage):
                logs.append({"type": "tool_result", "name": msg.name, "content": msg.content})
            if isinstance(msg, AIMessage) and not tool_calls:
                content = msg.content
                if isinstance(content, list):
                    content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
                if content:
                    logs.append({"type": "final_output", "content": content})
        return {"logs": logs, "duration_seconds": round(time.time() - start, 1)}

    try:
        result = await asyncio.wait_for(asyncio.to_thread(_run), timeout=120.0)
        return {"scenario": scenario_name, **result}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Agent run timed out (120s)")


@router.post("/api/settings/cron/analyze-stocks/run")
async def trigger_manual_analyze_stocks(user: dict = Depends(verify_token)):
    """Manual trigger for the stock agent — for testing from the app UI."""
    uid = user["uid"]
    print(f"\n⚡ User {uid} triggered stock agent analysis")
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_analyze_stocks_for_family, uid),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        print(f"⏰ [AGENT] Manual trigger timed out (180s) for: {uid}")
        return {
            "uid": uid,
            "success": False,
            "error": "agent_timeout_180s",
            "new_alerts_marked": 0,
        }
