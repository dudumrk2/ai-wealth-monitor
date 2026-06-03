# Log Monitor — Design Spec

**Date:** 2026-06-03  
**Author:** AI + user collaboration  
**Status:** Approved

---

## Overview

Add a weekly automated Google Cloud log scanning workflow to the AI Wealth Monitor backend.
The system fetches the last 7 days of ERROR/WARNING logs from Cloud Run, groups them by error
signature, asks Gemini Flash to write a human-friendly digest, and sends both a Telegram alert
and a Gmail email simultaneously — but only when issues are found. If logs are clean, silence.

---

## Architecture

```
Cloud Scheduler (weekly, Monday 08:00 IL time)
    ↓  POST /api/cron/scan-logs
    ↓  Header: X-Cron-Secret
routers/log_monitor.py
    ├── GCP Cloud Logging API  →  fetch last 7 days, severity >= WARNING
    ├── Group & deduplicate     →  by error signature (first 120 chars of message)
    ├── Gemini Flash            →  generate human-friendly digest (Telegram + email body)
    ├── Telegram                →  send concise alert (if issues found)
    └── Gmail OAuth             →  send full HTML email (if issues found)
```

**Disable mechanism:** Pause the Cloud Scheduler job in GCP console. No code change needed.

---

## Components

### NEW — `backend/routers/log_monitor.py`

Follows the same pattern as `routers/agent.py` — one file contains both the HTTP endpoint
and the orchestration logic.

Responsibilities:
- Authenticate the cron request via `X-Cron-Secret` header (same as existing cron endpoints)
- Query GCP Cloud Logging for `severity >= WARNING` in the last 7 days for the Cloud Run service
- Group entries by error signature (deduplicate repeated identical errors)
- Call Gemini Flash to produce:
  - A short Telegram message (2–4 lines, emoji, top issues)
  - A full HTML email body (Summary, Top Issues with counts, Recommended Actions)
- Send Telegram alert via the existing `send_telegram_alert` tool from `stock_agent_tools.py`
- Send Gmail email via the same OAuth pattern as `_send_agent_summary_email` in `routers/agent.py`
- Return a JSON response with scan summary (issues found, notifications sent, duration)

Also exposes a manual trigger:
- `POST /api/settings/cron/scan-logs/run` — authenticated, for testing from the app

### MODIFY — `backend/app.py`

Register the new `log_monitor` router (same pattern as existing routers).

### MODIFY — `backend/requirements.txt`

Add `google-cloud-logging>=3.9.0` for the GCP Logging client.

---

## GCP Log Query

```python
filter_str = (
    'severity >= "WARNING" '
    'AND resource.type = "cloud_run_revision" '
    'AND timestamp >= "{cutoff_iso}"'
)
```

- Time window: last 7 days
- Max entries fetched: 500 (to keep latency and cost low)
- Fields captured per entry: `severity`, `timestamp`, `textPayload` or `jsonPayload.message`

---

## Error Grouping

Entries are grouped by their **error signature**: the first 120 characters of the log message,
stripped of timestamps, request IDs, and numeric IDs (which vary per request).
This deduplicates noisy repeated errors into a single group with a count.

Output structure passed to Gemini:
```
[ERROR] "Database connection failed: timeout" — 23 occurrences (latest: 2026-06-02 14:31)
[WARNING] "Rate limit hit on Yahoo Finance API" — 7 occurrences (latest: 2026-06-01 09:12)
...
```

---

## Notification Strategy

| Condition | Telegram | Email |
|---|---|---|
| Issues found (any WARNING or ERROR) | ✅ Send concise alert | ✅ Send full digest |
| No issues found | ❌ Silence | ❌ Silence |

**Telegram message format:**
```
🔍 Weekly Log Scan — Issues Found

⚠️ 3 issue types detected in the last 7 days:

1. [ERROR] DB connection timeout — 23x
2. [WARNING] Yahoo Finance rate limit — 7x
3. [ERROR] Agent run failed for family X — 2x

Full details sent to your email.
```

**Email:** Full HTML digest with Summary, grouped error table (type, count, last seen, sample message),
and Recommended Actions section — all written by Gemini Flash.

**Sender:** The first family UID in Firestore that has a `gmail_refresh_token` set is used as the
sender/recipient. This is an operational health alert — it is sent once to the system owner,
not once per family.

---

## Gemini Prompt Design

Input: grouped log entries (text block, max ~2000 tokens)  
Output: JSON with two fields — `telegram_message` and `email_html`  
Model: `gemini-2.5-flash`, `temperature=0` (deterministic)

---

## Security

- Cron endpoint secured by `X-Cron-Secret` header (same mechanism as `/api/cron/analyze-stocks`)
- Manual trigger endpoint secured by Firebase `verify_token` (same as existing manual triggers)
- No log data stored persistently — processed in memory and discarded after notification

---

## Cloud Scheduler Configuration

| Field | Value |
|---|---|
| Schedule | `0 8 * * 1` (every Monday at 08:00) |
| Timezone | `Asia/Jerusalem` |
| Target | `POST https://<cloud-run-url>/api/cron/scan-logs` |
| Header | `X-Cron-Secret: <secret>` |
| Auth | OIDC (same as existing scheduler jobs) |

**Disable:** Pause the job in GCP Console → Cloud Scheduler. No code change required.

---

## Out of Scope

- Settings page toggle (use Cloud Scheduler pause instead)
- Per-family log filtering (this is a system-wide health check)
- Log archiving or persistent storage of scan results
- Slack or other notification channels

---

## Verification Plan

1. Run `POST /api/settings/cron/scan-logs/run` (manual trigger) with a valid auth token
2. Verify the endpoint returns a scan summary JSON
3. Confirm Telegram message received in the configured chat
4. Confirm email received in the admin Gmail inbox
5. Verify Cloud Scheduler job is created and fires on schedule
6. Verify silence when no issues exist (test with empty log window)
