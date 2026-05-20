# Stock Agent — Sprint 4 Design Spec
**Date**: 2026-05-20  
**Status**: Approved for implementation  
**Scope**: Sprint 4 (Cron & Deduplication) + minor fixes from Sprints 1–3 review  

---

## 1. Context

The Wealth Monitor app has an autonomous Financial Analyst Agent (`stock_agent.py` + `stock_agent_tools.py`) that runs a Sense→Think→Act loop over the family stock portfolio. Sprints 1–3 are complete. This spec covers:

- **Sprint 4**: FastAPI cron endpoint + 13F alert deduplication via Firestore
- **Pre-existing fixes**: two bugs found during review that must be fixed before Sprint 4 runs

---

## 2. Fixes from Review (before Sprint 4)

### Fix A — Missing `langgraph` dependency
**File**: `backend/requirements.txt`  
**Change**: Add `langgraph>=0.2.0`  
**Why**: `stock_agent.py` imports `from langgraph.prebuilt import create_react_agent` but the package is not declared. Production deploy will fail with `ModuleNotFoundError`.

### Fix B — Telegram parse_mode
**File**: `backend/stock_agent_tools.py`, `send_telegram_alert` tool  
**Change**: `"parse_mode": "Markdown"` → `"parse_mode": "HTML"`  
**Why**: Telegram's legacy Markdown mode breaks on common characters (`-`, `.`, `(`, `)`) present in all agent-generated messages. HTML mode is stable and widely supported.  
**Impact**: Alert messages formatted with `*bold*` must change to `<b>bold</b>`. Update the System Prompt alert format strings in `stock_agent.py` accordingly.

---

## 3. Sprint 4 Architecture

### 3.1 Deduplication Strategy (Approach A — Pre-filter)

The orchestration layer fetches and filters 13F data **before** invoking the agent. The agent receives only unseen alerts as pre-computed context and never calls `scan_guru_portfolio` itself during a cron run. After the agent completes, the orchestration layer marks the processed alerts as sent in Firestore.

```
Orchestration (_analyze_stocks_for_family)
  │
  ├─ 1. get_family_holdings(uid) → tickers list
  ├─ 2. scan_guru_portfolio() × 3  (direct call, outside agent)
  ├─ 3. get_sent_13f_alert_keys()  (Firestore read)
  ├─ 4. compute new_alerts = all_alerts − sent_alerts
  ├─ 5. analyze_portfolio_and_gurus(tickers, pre_analyzed_guru_data=new_alerts)
  │       └── Agent does: price fetching + send_telegram_alert only
  └─ 6. mark_13f_alert_sent(key) for each key in new_alerts
```

**Why not alternatives:**
- Wrapping `send_telegram_alert` with dedup (Option B) requires parsing free-form message text to extract a fingerprint — fragile and breaks when alert wording changes.
- A 5th "check_alert_sent" tool (Option C) relies on the LLM calling it correctly every time — not reliable enough for a financial alerting system.

### 3.2 Firestore Data Structure

```
Collection: settings
  Document: agent_state
    {
      "sent_alerts": {
        "Berkshire Hathaway:AAPL:Q4 2024": true,
        "Pershing Square:NVDA:Q1 2025": true
      }
    }
```

**Alert key format**: `"{guru_name}:{ticker}:{quarter}"` — e.g. `"Berkshire Hathaway:AAPL:Q4 2024"`  
The quarter value comes directly from the string returned by `scan_guru_portfolio` (e.g. `"Q4 2024"`), making it naturally self-expiring quarter-by-quarter.

---

## 4. Components

### 4.1 `db_manager.py` — Two new functions

```python
def get_sent_13f_alert_keys() -> set[str]:
    """Read settings/agent_state and return the set of already-sent alert keys."""

def mark_13f_alert_sent(alert_key: str) -> bool:
    """Add alert_key to settings/agent_state.sent_alerts in Firestore (merge=True)."""
```

Follow the existing `save_prime_rate` / `get_prime_rate` pattern: read/write `settings/agent_state` with `merge=True`.

### 4.2 `stock_agent.py` — One parameter change

**Function**: `analyze_portfolio_and_gurus`  
**Change**: Add optional parameter `pre_analyzed_guru_data: dict[str, str] | None = None`

When `pre_analyzed_guru_data` is provided, the human input message includes the pre-computed 13F summary and explicitly instructs the agent to **skip Step 2** (guru scanning) and proceed directly to Step 3 (ACT). When `None`, the agent runs its full loop unchanged (useful for manual/testing invocations).

```python
# pre_analyzed_guru_data shape:
{
  "Berkshire Hathaway": "<string from scan_guru_portfolio>",
  "Pershing Square":    "<string from scan_guru_portfolio>",
  "Scion Asset Management": "<string from scan_guru_portfolio>"
}
```

### 4.3 `app.py` — Three additions

#### Helper: `_analyze_stocks_for_family(uid: str) -> dict`
Internal async function. Full flow:

1. `get_family_holdings(uid)` → extract ticker list
2. Skip family if no holdings
3. Call `scan_guru_portfolio.invoke({"guru_name": name})` for each guru in `TRACKED_GURUS`
4. `get_sent_13f_alert_keys()` → `sent_keys: set[str]`
5. Parse each guru result to extract `(ticker, quarter)` pairs for new + liquidated positions
6. Build `new_alert_keys` = keys not in `sent_keys`
7. Call `analyze_portfolio_and_gurus(tickers, pre_analyzed_guru_data=guru_results)`
8. On success: call `mark_13f_alert_sent(key)` for every key in `new_alert_keys`
9. Return result dict

#### Endpoint: `POST /api/cron/analyze-stocks`
```python
@app.post("/api/cron/analyze-stocks")
async def analyze_stocks_cron(request: Request):
    """Daily cron to run the autonomous stock agent for all families. Secured via X-Cron-Secret."""
```
- Validates `X-Cron-Secret` header (same pattern as all other cron endpoints)
- Reads all UIDs via `db_manager.get_all_family_uids_for_holdings()`
- Checks per-family opt-out flag `cron_agent_enabled` (default `True` — read via `profile.get("cron_agent_enabled", True)`, no Firestore migration needed)
- Calls `_analyze_stocks_for_family(uid)` for each eligible family
- Returns `{"status": "success", "families_processed": N, "results": [...]}`

#### Endpoint: `POST /api/settings/cron/analyze-stocks/run`
```python
@app.post("/api/settings/cron/analyze-stocks/run")
async def trigger_manual_analyze_stocks(user: dict = Depends(verify_token)):
    """Manual trigger for the stock agent — for testing from the app UI."""
```
- Authenticated via `verify_token` (same pattern as other `/api/settings/cron/*/run` endpoints)
- Calls `_analyze_stocks_for_family(uid)` for the requesting user's family only
- Returns the agent result directly

---

## 5. Parsing 13F Results for Alert Keys

The `scan_guru_portfolio` tool returns strings in this format:
```
Berkshire Hathaway — Q4 2024 13F Activity (Dataroma):
  🆕 New positions (initiated this quarter): NYT, ULTA
  🚪 Liquidated positions (sold 100%): HPQ, PARA
```

The orchestration helper must parse this string to extract `(quarter, tickers)` and build alert keys. A simple regex or string split on `"—"` and `":"` is sufficient — no need for a dedicated parser class.

---

## 6. Files Changed

| File | Change type |
|------|-------------|
| `backend/requirements.txt` | Add `langgraph>=0.2.0` |
| `backend/stock_agent_tools.py` | Fix `parse_mode` → HTML |
| `backend/stock_agent.py` | Add `pre_analyzed_guru_data` param; update alert message format to HTML |
| `backend/db_manager.py` | Add `get_sent_13f_alert_keys`, `mark_13f_alert_sent` |
| `backend/app.py` | Add `_analyze_stocks_for_family`, two new endpoints |

---

## 7. Out of Scope

- Frontend UI for the agent (no changes to `frontend/`)
- Adding new gurus to `TRACKED_GURUS` — this is a future config change
- Unit tests for the new endpoints (can be added in a follow-up sprint)
- Dataroma HTML parser hardening — known future fragility, not addressed here
