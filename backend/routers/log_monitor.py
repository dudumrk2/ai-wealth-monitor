"""
routers/log_monitor.py
======================
Weekly Google Cloud log scanner — finds WARNING/ERROR entries from the last
7 days, groups them by error signature, and sends:
  - A concise Telegram alert
  - A structured AI investigation brief via Gmail

Both notifications fire simultaneously when issues are found.
Silence when logs are clean.

Endpoints:
  POST /api/cron/scan-logs                  — cron-secured (X-Cron-Secret)
  POST /api/settings/cron/scan-logs/run     — authenticated manual trigger

Disable: Pause the Cloud Scheduler job in GCP Console. No code change needed.
"""

import base64
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, Request

import db_manager
from auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LogMonitor"])

# ---------------------------------------------------------------------------
# Known source files in the repo — used by Gemini to map errors to files
# ---------------------------------------------------------------------------

_REPO_FILE_HINTS = """
Key backend files (for mapping errors to likely source files):
- backend/app.py               — FastAPI app, CORS, startup, Gmail OAuth endpoints
- backend/db_manager.py        — Firestore read/write operations
- backend/market_data.py       — Yahoo Finance / yfinance calls, Israeli market data
- backend/stock_agent.py       — LangGraph ReAct agent orchestration
- backend/stock_agent_tools.py — Telegram alerts, 13F scanner, yfinance tools
- backend/routers/agent.py     — /api/cron/analyze-stocks endpoint
- backend/routers/documents.py — PDF processing endpoints
- backend/routers/portfolio.py — Portfolio CRUD endpoints
- backend/services/stock_updater.py — Scheduled stock price updater
- backend/services/scraper.py  — Bizportal.co.il scraper for Israeli funds
- backend/rag_utils.py         — RAG / embedding utilities
- backend/report_utils.py      — PDF redaction and AI extraction helpers
"""

# ---------------------------------------------------------------------------
# Step 1 — Fetch GCP Cloud Logging entries
# ---------------------------------------------------------------------------

def _fetch_gcp_log_entries(days: int = 7, max_entries: int = 500) -> list[dict]:
    """Fetch WARNING+ severity log entries from GCP Cloud Logging.

    Uses Application Default Credentials (ADC) — the Cloud Run service account
    already has the Logs Viewer role, so no extra credentials are needed.

    Args:
        days: Number of past days to query (default: 7).
        max_entries: Maximum number of entries to fetch (default: 500).

    Returns:
        List of dicts with keys: severity, message, timestamp.
        Returns empty list on any error (non-fatal — caller handles silence).
    """
    try:
        from google.cloud import logging as gcp_logging

        client = gcp_logging.Client()
        project_id = client.project

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        filter_str = (
            f'severity >= "WARNING" '
            f'AND resource.type = "cloud_run_revision" '
            f'AND timestamp >= "{cutoff_iso}"'
        )

        entries = []
        for entry in client.list_entries(filter_=filter_str, max_results=max_entries,
                                         order_by=gcp_logging.DESCENDING):
            payload = entry.payload
            if isinstance(payload, dict):
                message = payload.get("message", str(payload))
            else:
                message = str(payload)

            entries.append({
                "severity": entry.severity or "DEFAULT",
                "message": message,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else "",
            })

        logger.info(f"[LOG_MONITOR] Fetched {len(entries)} log entries from GCP (last {days}d, project={project_id})")
        return entries

    except Exception as e:
        logger.error(f"[LOG_MONITOR] Failed to fetch GCP log entries: {e}")
        return []

# ---------------------------------------------------------------------------
# Step 2 — Group and deduplicate by error signature
# ---------------------------------------------------------------------------

_NOISE_PATTERN = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  # UUID
    r"|req-[a-z0-9]+"                                                       # request IDs
    r"|[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"             # timestamps
    r")\b",
    re.IGNORECASE,
)


def _normalise_message(message: str) -> str:
    """Strip noise tokens so identical errors with different IDs cluster together."""
    cleaned = _NOISE_PATTERN.sub("", message)
    return cleaned[:120].strip()


def _group_log_entries(entries: list[dict]) -> list[dict]:
    """Group log entries by normalised message signature.

    Args:
        entries: List of dicts with keys: severity, message, timestamp.

    Returns:
        List of group dicts sorted by count descending. Each group has:
          severity, signature, count, first_seen, last_seen, sample.
    """
    groups: dict[str, dict] = {}

    for entry in entries:
        sig = _normalise_message(entry.get("message", ""))
        if not sig:
            continue

        if sig not in groups:
            groups[sig] = {
                "severity": entry.get("severity", "DEFAULT"),
                "signature": sig,
                "count": 0,
                "first_seen": entry.get("timestamp", ""),
                "last_seen": entry.get("timestamp", ""),
                "sample": entry.get("message", "")[:300],
            }

        g = groups[sig]
        g["count"] += 1
        ts = entry.get("timestamp", "")
        if ts and ts < g["first_seen"]:
            g["first_seen"] = ts
        if ts and ts > g["last_seen"]:
            g["last_seen"] = ts

    result = sorted(groups.values(), key=lambda x: x["count"], reverse=True)
    return result


def _build_grouped_text(groups: list[dict]) -> str:
    """Render grouped entries as a structured text block for the Gemini prompt."""
    lines = []
    for g in groups:
        lines.append(
            f"[{g['severity']}] \"{g['signature']}\" — "
            f"{g['count']} occurrences "
            f"(first: {g['first_seen']}, last: {g['last_seen']})\n"
            f"  Sample: {g['sample']}"
        )
    return "\n\n".join(lines)

# ---------------------------------------------------------------------------
# Step 3 — Gemini: generate Telegram message + AI investigation brief email
# ---------------------------------------------------------------------------

def _generate_digest(grouped_text: str, scan_from: str, scan_to: str) -> dict[str, str]:
    """Call Gemini Flash to produce the Telegram message and email HTML.

    Args:
        grouped_text: Structured block of grouped log entries.
        scan_from: ISO date string for the start of the scan window.
        scan_to: ISO date string for the end of the scan window.

    Returns:
        Dict with keys 'telegram_message' and 'email_html'.
        Falls back to plain-text defaults on any Gemini error.
    """
    import json as _json
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("[LOG_MONITOR] GEMINI_API_KEY not set — skipping AI digest.")
        return _fallback_digest(grouped_text, scan_from, scan_to)

    system_prompt = f"""You are a backend operations analyst for an AI-powered family wealth management app.
You have received a weekly automated log scan report. Your job is to produce two outputs:

1. A SHORT Telegram message (plain text, 3-6 lines, use emoji) summarising the top issues found.
2. A STRUCTURED AI INVESTIGATION BRIEF (HTML email) designed so the developer can paste it
   directly into an AI coding assistant (like Antigravity/Claude/Gemini) and immediately get
   actionable debugging help.

The AI investigation brief email MUST follow this exact structure:
  - System Context block (app name, stack, repo, scan window)
  - "How to use" instruction: paste into AI assistant
  - Numbered issue sections (one per error group), each with:
      * Occurrences count, first/last seen timestamps
      * Likely source file from the repo (use the file hints below)
      * Sample log entry (verbatim, in a <code> block)
  - Recommended Investigation Steps (concrete, file-specific, not generic)
  - Raw Grouped Log Data section (verbatim copy of the input, inside <pre> block)

Map errors to likely source files using these hints:
{_REPO_FILE_HINTS}

Return ONLY valid JSON with exactly two keys:
  "telegram_message": "...",
  "email_html": "..."

Do not wrap in markdown code fences. Pure JSON only."""

    user_message = f"""Scan window: {scan_from} → {scan_to}

Grouped log entries:
{grouped_text}"""

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        raw = response.content
        if isinstance(raw, list):
            raw = " ".join(
                block.get("text", "") for block in raw
                if isinstance(block, dict) and block.get("type") == "text"
            )
        result = _json.loads(raw.strip())
        if "telegram_message" in result and "email_html" in result:
            return result
        logger.warning("[LOG_MONITOR] Gemini returned unexpected JSON shape — using fallback.")
        return _fallback_digest(grouped_text, scan_from, scan_to)

    except Exception as e:
        logger.error(f"[LOG_MONITOR] Gemini digest generation failed: {e}")
        return _fallback_digest(grouped_text, scan_from, scan_to)


def _fallback_digest(grouped_text: str, scan_from: str, scan_to: str) -> dict[str, str]:
    """Plain-text fallback when Gemini is unavailable."""
    telegram_message = (
        f"🔍 Weekly Log Scan — Issues Found\n\n"
        f"Scan window: {scan_from} → {scan_to}\n\n"
        f"Issues detected (Gemini digest unavailable):\n{grouped_text[:500]}\n\n"
        f"Check your email for the full report."
    )
    email_html = (
        f"<html><body>"
        f"<h2>🔍 Weekly Log Scan — Issues Found</h2>"
        f"<p>Scan window: {scan_from} → {scan_to}</p>"
        f"<p><strong>Note:</strong> Gemini digest was unavailable. Raw grouped data:</p>"
        f"<pre>{grouped_text}</pre>"
        f"</body></html>"
    )
    return {"telegram_message": telegram_message, "email_html": email_html}

# ---------------------------------------------------------------------------
# Step 4 — Send Telegram
# ---------------------------------------------------------------------------

def _send_log_telegram(message: str) -> bool:
    """Send the log monitor alert to the configured Telegram chat.

    Args:
        message: Plain text message (HTML supported).

    Returns:
        True on success, False on any failure (non-fatal).
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token:
        logger.error("[LOG_MONITOR] TELEGRAM_BOT_TOKEN not set — skipping Telegram.")
        return False
    if not chat_id:
        logger.error("[LOG_MONITOR] TELEGRAM_CHAT_ID not set — skipping Telegram.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("[LOG_MONITOR] Telegram alert sent successfully.")
            return True
        logger.error(f"[LOG_MONITOR] Telegram API error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"[LOG_MONITOR] Telegram send failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Step 5 — Send Gmail (AI investigation brief)
# ---------------------------------------------------------------------------

def _send_log_email(profile: dict, subject: str, html_body: str) -> bool:
    """Send the AI investigation brief email via Gmail OAuth.

    Reuses the same OAuth pattern as _send_agent_summary_email in routers/agent.py.
    Uses the first family profile that has a gmail_refresh_token.

    Args:
        profile: Firestore family profile dict.
        subject: Email subject line.
        html_body: Full HTML email body.

    Returns:
        True on success, False if credentials missing or send fails (non-fatal).
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        refresh_token = profile.get("gmail_refresh_token")
        if not refresh_token:
            logger.warning("[LOG_MONITOR] No gmail_refresh_token in profile — skipping email.")
            return False

        email_addr = profile.get("pii_data", {}).get("member1", {}).get("email")
        if not email_addr:
            logger.warning("[LOG_MONITOR] No email address in profile — skipping email.")
            return False

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        message = MIMEText(html_body, "html", "utf-8")
        message["To"] = email_addr
        message["Subject"] = subject
        raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw_msg}).execute()

        logger.info(f"[LOG_MONITOR] AI investigation brief sent to {email_addr}.")
        return True

    except Exception as e:
        logger.error(f"[LOG_MONITOR] Email send failed: {e}")
        return False

# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def _run_log_scan() -> dict[str, Any]:
    """Full log scan pipeline: fetch → group → digest → notify.

    Returns:
        Dict summarising the scan result:
          issues_found (int), telegram_sent (bool), email_sent (bool),
          duration_seconds (float), error (str | None).
    """
    import time
    start = time.time()

    scan_to = datetime.now(timezone.utc)
    scan_from = scan_to - timedelta(days=7)
    scan_from_str = scan_from.strftime("%Y-%m-%d")
    scan_to_str = scan_to.strftime("%Y-%m-%d")

    # 1 — Fetch
    entries = _fetch_gcp_log_entries(days=7, max_entries=500)
    if not entries:
        logger.info("[LOG_MONITOR] No log entries found — scan complete, no notifications sent.")
        return {
            "issues_found": 0,
            "telegram_sent": False,
            "email_sent": False,
            "duration_seconds": round(time.time() - start, 2),
            "error": None,
        }

    # 2 — Group
    groups = _group_log_entries(entries)
    if not groups:
        logger.info("[LOG_MONITOR] Log entries found but no groupable issues — scan complete.")
        return {
            "issues_found": 0,
            "telegram_sent": False,
            "email_sent": False,
            "duration_seconds": round(time.time() - start, 2),
            "error": None,
        }

    logger.info(f"[LOG_MONITOR] {len(groups)} issue type(s) found across {len(entries)} entries.")

    # 3 — AI digest
    grouped_text = _build_grouped_text(groups)
    digest = _generate_digest(grouped_text, scan_from_str, scan_to_str)

    # 4 — Notifications (both channels simultaneously)
    telegram_ok = _send_log_telegram(digest["telegram_message"])

    # Find the first family profile with a gmail_refresh_token
    email_ok = False
    try:
        uids = db_manager.get_all_family_uids()
        for uid in uids:
            profile = db_manager.get_family_profile(uid)
            if profile and profile.get("gmail_refresh_token"):
                subject = f"🔍 Weekly Log Scan — {len(groups)} issue(s) found ({scan_to_str})"
                email_ok = _send_log_email(profile, subject, digest["email_html"])
                break  # Send once to the system owner only
    except Exception as e:
        logger.error(f"[LOG_MONITOR] Could not resolve email recipient: {e}")

    duration = round(time.time() - start, 2)
    logger.info(
        f"[LOG_MONITOR] Scan complete in {duration}s — "
        f"{len(groups)} issues, telegram={'✅' if telegram_ok else '❌'}, "
        f"email={'✅' if email_ok else '❌'}"
    )

    return {
        "issues_found": len(groups),
        "telegram_sent": telegram_ok,
        "email_sent": email_ok,
        "duration_seconds": duration,
        "error": None,
    }

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/cron/scan-logs")
async def scan_logs_cron(request: Request):
    """Weekly cron endpoint to scan GCP Cloud Logging for issues.

    Fetches the last 7 days of WARNING/ERROR entries, groups them, generates
    an AI investigation brief via Gemini, and sends Telegram + Gmail notifications.
    Silence when no issues are found.
    Secured via X-Cron-Secret header.
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    incoming_secret = request.headers.get("X-Cron-Secret", "")
    if not cron_secret or incoming_secret != cron_secret:
        raise HTTPException(status_code=403, detail="Forbidden: invalid or missing X-Cron-Secret")

    import asyncio
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_log_scan),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        logger.error("[LOG_MONITOR] Cron scan timed out after 120s.")
        result = {"issues_found": 0, "telegram_sent": False, "email_sent": False,
                  "duration_seconds": 120.0, "error": "timeout_120s"}

    return {"status": "success", "result": result}


@router.post("/api/settings/cron/scan-logs/run")
async def trigger_manual_scan_logs(user: dict = Depends(verify_token)):
    """Manual trigger for the log scanner — for testing from the app or curl.

    Runs the full scan pipeline and returns the result immediately.
    Requires a valid Firebase auth token.
    """
    uid = user["uid"]
    logger.info(f"[LOG_MONITOR] Manual scan triggered by user {uid}")

    import asyncio
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_log_scan),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        logger.error("[LOG_MONITOR] Manual scan timed out after 120s.")
        result = {"issues_found": 0, "telegram_sent": False, "email_sent": False,
                  "duration_seconds": 120.0, "error": "timeout_120s"}

    return {"status": "success", "uid": uid, "result": result}
