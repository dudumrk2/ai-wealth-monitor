# Startup Environment Validation & Telegram Alert Implementation Plan (Revised)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent broken Cloud Run deployments caused by missing environment variables, inject any recovered secrets from Secret Manager into `os.environ`, send a deduplicated fail-fast alert to Telegram with `K_REVISION` context, and abort container startup via FastAPI lifespan so Cloud Run never shifts production traffic to the broken revision.

**Architecture:** A dedicated `backend/env_validator.py` module defines mandatory production variables. During FastAPI `lifespan` startup (before port 8080 opens), it validates each variable (treating empty strings and whitespace as missing). If missing from `os.environ`, it queries Google Secret Manager; if found, it writes it back into `os.environ` so the rest of the application can use it. If mandatory variables remain missing, it sends an HTML-escaped Telegram alert (deduplicated by `K_REVISION` via Firestore to prevent restart storm alerts, 2-3s timeout) and raises `RuntimeError`. Cloud Run's startup probe fails, and traffic routing to the candidate revision is aborted.

**Tech Stack:** Python 3.11+, FastAPI (Lifespan), Google Cloud Secret Manager (`google-cloud-secret-manager>=2.18.0`), Google Cloud Firestore, Requests, Pytest.

---

### Key Design Decisions & Clarifications

1. **Secret Manager Fallback & Injection into `os.environ`:**
   - Service account `408755725045-compute@developer.gserviceaccount.com` has `roles/editor` on `finance-family-management`, which includes `secretmanager.versions.access`.
   - When a variable is retrieved from Secret Manager, it is explicitly injected: `os.environ[key] = secret_value`.
2. **Timing & Test Isolation:**
   - Validation runs inside FastAPI's `lifespan` hook in `app.py`, NEVER at import time.
   - Bypassed in tests via explicit `os.environ["SKIP_ENV_VALIDATION"] = "1"` set in `backend/tests/conftest.py`.
3. **Alert Deduplication & Cloud Run Crash Loop Protection:**
   - Cloud Run retries failed container startups up to several times.
   - Deduplication uses Firestore (`system_alerts/startup_fail_{K_REVISION}`) to ensure at most one Telegram message per failed revision deployment.
   - Telegram HTTP call uses a 2.5s timeout so it does not delay container failure.
   - Alert message includes `K_SERVICE` and `K_REVISION`.
4. **Telegram Credentials: Warn Loudly:**
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are not in the mandatory crash list. If missing from both `os.environ` and Secret Manager, log at `CRITICAL` level that the Telegram alert could not be dispatched, and continue with raising `RuntimeError` for the missing mandatory app variables.
5. **Verified Mandatory List:**
   - `CRON_SECRET` (Required by cron endpoints `/api/cron/*`)
   - `GEMINI_API_KEY` (Required by AI log monitor & RAG)
   - `ANTHROPIC_API_KEY` (Required by `document_flows.py` Claude Vision OCR & stock summary)
   - `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET` (Required for Gmail OAuth token refresh)
   - `FIREBASE_STORAGE_BUCKET` (Required for document upload/storage)
   - *(Note: `FRONTEND_URL` and `BACKEND_URL` have safe local defaults and are omitted from mandatory blocking list).*
6. **Input Hygiene:**
   - Any value where `val is None or not str(val).strip()` is treated as missing.
   - Variable names only are logged/alerted (never secret values).
   - `html.escape()` used for all dynamic strings in Telegram HTML payload.

---

### File Structure & Responsibilities

- **`backend/requirements.txt`** (Modify):
  - Add `google-cloud-secret-manager>=2.18.0`.
- **`backend/env_validator.py`** (New):
  - Defines `MANDATORY_ENV_VARS`.
  - Implements `get_secret_with_fallback(key, project_id)` -> fetches and injects into `os.environ`.
  - Implements `send_startup_failure_alert(missing_vars, service, revision)` with Firestore deduplication and 2.5s timeout.
  - Implements `validate_environment(fail_fast=True)`.
- **`backend/app.py`** (Modify):
  - Register `lifespan` handler calling `validate_environment()`.
- **`backend/tests/conftest.py`** (Modify):
  - Add `os.environ["SKIP_ENV_VALIDATION"] = "1"`.
- **`backend/tests/test_env_validator.py`** (New):
  - Unit tests covering validation, injection, deduplication, HTML escaping, and lifespan integration.
- **`scripts/verify_env.py`** (New):
  - Standalone pre-deploy CLI check to run before `gcloud run deploy`.
- **`PROGRESS.md`** (Modify):
  - Document the startup validation architecture and fail-fast deployment protection.

---

### Task 1: Update Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add `google-cloud-secret-manager` to `backend/requirements.txt`**
- [ ] **Step 2: Commit dependency update**

---

### Task 2: Create Unit Tests for Environment Validator

**Files:**
- Create: `backend/tests/test_env_validator.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Update `backend/tests/conftest.py` to set `SKIP_ENV_VALIDATION=1`**
- [ ] **Step 2: Write unit tests in `backend/tests/test_env_validator.py`**
  - Test 1: All mandatory vars present -> passes.
  - Test 2: Missing var retrieved from Secret Manager -> injected into `os.environ`, validation passes.
  - Test 3: Missing var not in Secret Manager -> triggers alert, raises `RuntimeError`.
  - Test 4: Deduplication -> second call for same `K_REVISION` skips sending Telegram alert.
  - Test 5: Empty/whitespace string -> correctly treated as missing.
  - Test 6: HTML escaping -> special characters in service/revision/var names are properly escaped.
  - Test 7: Missing Telegram token -> logs CRITICAL loudly, still raises `RuntimeError` for app vars.
- [ ] **Step 3: Run pytest to verify tests fail initially**

---

### Task 3: Implement `env_validator.py`

**Files:**
- Create: `backend/env_validator.py`

- [ ] **Step 1: Implement `env_validator.py`**
  - `MANDATORY_ENV_VARS` list.
  - `get_secret_from_sm(key, project_id)`.
  - `send_startup_failure_alert(missing_vars)` with Firestore dedup, `html.escape()`, and 2.5s timeout.
  - `validate_environment(fail_fast=True)` checking `SKIP_ENV_VALIDATION` and whitespace.
- [ ] **Step 2: Run pytest to verify all `test_env_validator.py` tests pass**
- [ ] **Step 3: Commit Task 3**

---

### Task 4: Integrate into FastAPI `lifespan` in `backend/app.py`

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: Wire `validate_environment()` into FastAPI `lifespan`**
  - Define `async def lifespan(app: FastAPI)` (or modify existing lifespan/startup).
  - Execute `validate_environment()` inside lifespan startup.
- [ ] **Step 2: Run complete backend test suite (`pytest backend/tests/ -v`)**
  - Verify 0 regressions across all existing tests.
- [ ] **Step 3: Commit Task 4**

---

### Task 5: Pre-deploy Script & Documentation

**Files:**
- Create: `scripts/verify_env.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Create `scripts/verify_env.py` for pre-deployment CLI checks**
- [ ] **Step 2: Update `PROGRESS.md` with architectural notes and local dev guidelines**
- [ ] **Step 3: Commit Task 5**
