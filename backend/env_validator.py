"""
Environment Validator & Safe Deployment Guard.

Validates mandatory environment variables during application startup (FastAPI lifespan),
attempts retrieval from Google Secret Manager with active os.environ injection,
dispatches deduplicated fail-fast alerts to Telegram, and raises RuntimeError to prevent
Cloud Run from routing traffic to broken revisions.
"""
import os
import sys
import html
import logging
from datetime import datetime, timezone
import requests

logger = logging.getLogger("env_validator")

MANDATORY_ENV_VARS = [
    "CRON_SECRET",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "FIREBASE_STORAGE_BUCKET",
]

TELEGRAM_HTTP_TIMEOUT = 2.5
DEFAULT_PROJECT_ID = "finance-family-management"

_sm_client = None


def _get_sm_client():
    """Return a cached SecretManagerServiceClient instance."""
    global _sm_client
    if _sm_client is None:
        from google.cloud import secretmanager
        _sm_client = secretmanager.SecretManagerServiceClient()
    return _sm_client


def get_firestore_client():
    """Retrieve Firestore client if firebase-admin is available, or return None."""
    try:
        import firebase_admin
        from firebase_admin import firestore
        if not firebase_admin._apps:
            return None
        return firestore.client()
    except Exception as e:
        logger.debug(f"[ENV_VALIDATOR] Firestore client unavailable for dedup: {e}")
        return None


def get_secret_from_sm(key: str, project_id: str | None = None) -> str | None:
    """Fetch secret value from Google Cloud Secret Manager."""
    try:
        client = _get_sm_client()
        target_project = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or DEFAULT_PROJECT_ID
        name = f"projects/{target_project}/secrets/{key}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        val = response.payload.data.decode("UTF-8").strip()
        return val if val else None
    except Exception as e:
        logger.debug(f"[ENV_VALIDATOR] Secret '{key}' could not be fetched from Secret Manager: {e}")
        return None


def get_secret_with_fallback(key: str, project_id: str | None = None) -> str | None:
    """
    Check os.environ first. If missing or whitespace, fetch from Google Secret Manager.
    If recovered from Secret Manager, immediately inject it into os.environ for the application.
    """
    val = os.getenv(key, "").strip()
    if val:
        return val

    sm_val = get_secret_from_sm(key, project_id)
    if sm_val:
        os.environ[key] = sm_val
        logger.info(f"[ENV_VALIDATOR] Successfully recovered '{key}' from Secret Manager and injected into os.environ.")
        return sm_val

    return None


def send_startup_failure_alert(missing_vars: list[str]) -> bool:
    """
    Send an HTML-escaped Telegram notification to the family chat when startup validation fails.
    Deduplicates across Cloud Run revision retry loops using Firestore.
    """
    bot_token = get_secret_with_fallback("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret_with_fallback("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.critical(
            "[ENV_VALIDATOR] Cannot send Telegram alert: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID "
            "is not set in environment or Secret Manager!"
        )
        return False

    k_service = os.getenv("K_SERVICE", "local-dev")
    k_revision = os.getenv("K_REVISION", "local-dev")

    doc_ref = None
    # Deduplication in Cloud Run crash loops using Firestore
    if k_revision != "local-dev":
        try:
            db = get_firestore_client()
            if db:
                doc_ref = db.collection("system_alerts").document(f"startup_fail_{k_revision}")
                doc_snap = doc_ref.get()
                if doc_snap and getattr(doc_snap, "exists", False):
                    logger.info(
                        f"[ENV_VALIDATOR] Telegram alert already dispatched for revision '{k_revision}'. "
                        "Skipping retry spam."
                    )
                    return False
        except Exception as e:
            logger.warning(f"[ENV_VALIDATOR] Deduplication check error (will send alert anyway): {e}")

    safe_service = html.escape(k_service)
    safe_revision = html.escape(k_revision)
    var_items = "\n".join(f"• <code>{html.escape(v)}</code>" for v in missing_vars)

    text = (
        "🚨 <b>Cloud Run Startup / Deployment Blocked</b>\n\n"
        f"<b>Service:</b> <code>{safe_service}</code>\n"
        f"<b>Revision:</b> <code>{safe_revision}</code>\n\n"
        "<b>Missing Mandatory Environment Variables:</b>\n"
        f"{var_items}\n\n"
        "<i>Container startup aborted. Production traffic remains safely on previous revision.</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=TELEGRAM_HTTP_TIMEOUT)
        if resp.status_code == 200:
            logger.info("[ENV_VALIDATOR] Telegram startup failure alert delivered successfully.")
            if doc_ref is not None:
                try:
                    doc_ref.set({
                        "missing_vars": missing_vars,
                        "service": k_service,
                        "revision": k_revision,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as db_err:
                    logger.warning(f"[ENV_VALIDATOR] Failed to record dedup marker in Firestore: {db_err}")
            return True
        else:
            logger.error(
                f"[ENV_VALIDATOR] Telegram API returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
            return False
    except requests.exceptions.Timeout:
        logger.warning(
            f"[ENV_VALIDATOR] Telegram alert timed out after {TELEGRAM_HTTP_TIMEOUT}s."
        )
        return False
    except Exception as e:
        logger.error(f"[ENV_VALIDATOR] Failed to send Telegram alert: {e}")
        return False


def validate_environment(fail_fast: bool = True) -> list[str]:
    """
    Validate that all mandatory environment variables are present and non-empty.
    Recovers missing variables from Secret Manager if possible.
    If mandatory variables remain missing, triggers Telegram alert and raises RuntimeError.
    """
    if os.getenv("SKIP_ENV_VALIDATION") == "1":
        logger.info("[ENV_VALIDATOR] SKIP_ENV_VALIDATION=1 is set. Skipping environment validation.")
        return []

    missing: list[str] = []

    for var in MANDATORY_ENV_VARS:
        val = get_secret_with_fallback(var)
        if not val:
            missing.append(var)

    if missing:
        err_msg = (
            f"CRITICAL STARTUP ERROR: Missing mandatory environment variables: {', '.join(missing)}"
        )
        logger.critical(f"[ENV_VALIDATOR] {err_msg}")

        try:
            send_startup_failure_alert(missing)
        except Exception as alert_err:
            logger.error(
                f"[ENV_VALIDATOR] Non-fatal error while attempting to send Telegram alert: {alert_err}"
            )

        if fail_fast:
            raise RuntimeError(err_msg)

    return missing
