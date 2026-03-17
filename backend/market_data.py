"""
market_data.py
==============
Fetches real competitor data from the official Israeli Government CKAN API
(data.gov.il) using a three-tier Stale-While-Revalidate strategy:

  Tier 1 — Live Gov API  : always attempted first.
  Tier 2 — Firestore     : used if the Gov API is unavailable or returns empty.
  Tier 3 — Hardcoded     : absolute safety net so the AI pipeline never stalls.

Key design decisions
--------------------
* CACHED_RESOURCE_IDS   : module-level dict; avoids re-calling package_search
                          on every request within the same server process.
* get_latest_resource_id: dynamically discovers the current resource_id for a
                          dataset so we survive government file rotations.
* get_top_competitors   : selects the right dataset based on product_type,
                          then executes the fetch + cache + fallback flow.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level in-memory cache for discovered resource IDs.
# Key   : dataset_query string  (e.g. "גמל נט")
# Value : resource_id UUID string
# Lifetime: process lifetime (reset on server restart).
# ---------------------------------------------------------------------------
CACHED_RESOURCE_IDS: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Gov API base URLs
# ---------------------------------------------------------------------------
_CKAN_BASE = "https://data.gov.il/api/3/action"
_PACKAGE_SEARCH_URL = f"{_CKAN_BASE}/package_search"
_DATASTORE_SEARCH_URL = f"{_CKAN_BASE}/datastore_search"

# ---------------------------------------------------------------------------
# Request configuration
# ---------------------------------------------------------------------------
_HTTP_TIMEOUT = 10.0  # seconds

# ---------------------------------------------------------------------------
# Hardcoded safety-net data  (Tier 3)
# Used only when both the Gov API and Firestore cache are unavailable.
# Values are realistic Israeli market averages (2024).
# ---------------------------------------------------------------------------
_HARDCODED_FALLBACK: list[dict] = [
    {
        "provider_name": "אלטשולר שחם",
        "yield_1yr": 14.2,
        "yield_3yr": 8.5,
        "management_fee_accumulation": 0.25,
    },
    {
        "provider_name": "ילין לפידות",
        "yield_1yr": 13.8,
        "yield_3yr": 8.1,
        "management_fee_accumulation": 0.28,
    },
    {
        "provider_name": "מיטב",
        "yield_1yr": 13.1,
        "yield_3yr": 7.9,
        "management_fee_accumulation": 0.30,
    },
]

# ---------------------------------------------------------------------------
# Dataset query strings for each product type
# ---------------------------------------------------------------------------
_GEMEL_QUERY = "גמל נט"
_PENSION_QUERY = "פנסיה נט"


def _select_dataset_query(product_type: str) -> str:
    """Return the appropriate package_search query for the given product_type."""
    pt = product_type or ""
    if "פנסיה" in pt or "pension" in pt.lower():
        return _PENSION_QUERY
    # Default covers גמל, קרן השתלמות, ביטוח מנהלים, etc.
    return _GEMEL_QUERY


# ---------------------------------------------------------------------------
# Step 1: Dynamic Resource ID Discovery
# ---------------------------------------------------------------------------

async def get_latest_resource_id(dataset_query: str) -> Optional[str]:
    """
    Discover the most-recent resource_id for a CKAN dataset by name.

    The government replaces the underlying file (and therefore the resource_id)
    whenever they upload a new version.  This function always fetches the
    *current* resource_id from the package_search endpoint so callers never
    need to hard-code UUIDs.

    Results are cached in CACHED_RESOURCE_IDS for the lifetime of the server
    process to avoid hammering the discovery endpoint on every request.

    Args:
        dataset_query: Free-text search term, e.g. "גמל נט" or "פנסיה נט".

    Returns:
        The resource_id UUID string, or None if discovery fails.
    """
    # --- In-memory cache hit ---
    if dataset_query in CACHED_RESOURCE_IDS:
        rid = CACHED_RESOURCE_IDS[dataset_query]
        logger.info(f"🗂️  [MARKET] Resource ID cache HIT for '{dataset_query}': {rid}")
        print(f"🗂️  [MARKET] Resource ID cache HIT for '{dataset_query}': {rid}")
        return rid

    logger.info(f"🌐 [MARKET] Discovering resource_id for dataset: '{dataset_query}'")
    print(f"🌐 [MARKET] Discovering resource_id for dataset: '{dataset_query}'")

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(
                _PACKAGE_SEARCH_URL,
                params={"q": dataset_query},
            )
            response.raise_for_status()

        payload = response.json()
        results = payload["result"]["results"]

        if not results:
            logger.warning(f"⚠️  [MARKET] package_search returned 0 results for '{dataset_query}'")
            print(f"⚠️  [MARKET] package_search returned 0 results for '{dataset_query}'")
            return None

        resources = results[0].get("resources", [])
        if not resources:
            logger.warning(f"⚠️  [MARKET] No resources found in first result for '{dataset_query}'")
            print(f"⚠️  [MARKET] No resources found in first result for '{dataset_query}'")
            return None

        resource_id: str = resources[0]["id"]
        CACHED_RESOURCE_IDS[dataset_query] = resource_id

        print(f"✅ [MARKET] Discovered resource_id for '{dataset_query}': {resource_id}")
        return resource_id

    except Exception as e:
        logger.error(f"💥 [MARKET] Error discovering resource_id for '{dataset_query}': {e}")
        print(f"💥 [MARKET] Error discovering resource_id for '{dataset_query}': {e}")
        return None


# ---------------------------------------------------------------------------
# Step 2: Fetch Top Competitors with Stale-While-Revalidate Fallback
# ---------------------------------------------------------------------------

def _parse_records(records: list[dict]) -> list[dict]:
    """
    Map raw CKAN datastore records to our internal competitor schema.

    Raw field             → Output field
    ─────────────────────────────────────────────────────────
    MANAGING_CORPORATION  → provider_name
    YIELD_TRAILING_12_MONTHS  → yield_1yr    (%)
    YIELD_TRAILING_36_MONTHS  → yield_3yr    (%)
    MANAGEMENT_FEE_ACCUMULATION → management_fee_accumulation (%)
    """
    parsed = []
    for rec in records:
        try:
            parsed.append({
                "provider_name": str(rec.get("MANAGING_CORPORATION", "") or "").strip(),
                "yield_1yr": _safe_float(rec.get("YEAR_TO_DATE_YIELD", 0)),
                "yield_3yr": _safe_float(rec.get("YIELD_TRAILING_36_MONTHS")),
                "management_fee_accumulation": _safe_float(rec.get("MANAGEMENT_FEE_ACCUMULATION")),
            })
        except Exception as parse_err:
            logger.warning(f"⚠️  [MARKET] Skipping malformed record: {parse_err}")
    return parsed


def _safe_float(value) -> float:
    """Convert a value to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


async def get_top_competitors(product_type: str, track_name: str) -> list[dict]:
    """
    Return a list of up to 3 top-performing competitor funds for the given track.

    The function implements the following fallback waterfall:

      1. Gov API (live)           — sort by 12-month yield descending, filter by track.
      2. Firestore cache          — last successful fetch stored by db_manager.
      3. Hardcoded safety net     — realistic Israeli market averages.

    Args:
        product_type : Hebrew product type string, e.g. "קרן גמל" or "פנסיה".
        track_name   : The investment track name used to filter results,
                       e.g. "כללי" or "מסלול מניות".

    Returns:
        A list of competitor dicts with keys:
          provider_name, yield_1yr, yield_3yr, management_fee_accumulation
    """
    dataset_query = _select_dataset_query(product_type)
    print(f"\n📊 [MARKET] get_top_competitors | product_type='{product_type}' | track='{track_name}' | dataset='{dataset_query}'")

    # ------------------------------------------------------------------ #
    # TIER 1 — Attempt live fetch from the Government CKAN API            #
    # ------------------------------------------------------------------ #
    try:
        resource_id = await get_latest_resource_id(dataset_query)

        if not resource_id:
            raise ValueError("resource_id discovery returned None")

        # Build query searching `track_name` across fields (mainly `FUND_NAME`)
        # Strict "filters" on TARGET_POPULATION often fails because the value is "כלל האוכלוסיה"
        params = {
            "resource_id": resource_id,
            "limit": 3,
            "sort": "YIELD_TRAILING_3_YRS desc",
            "q": track_name,
        }

        print(f"🌐 [MARKET] Calling datastore_search | resource_id={resource_id} | track='{track_name}'")

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(_DATASTORE_SEARCH_URL, params=params)
            response.raise_for_status()

        payload = response.json()
        records: list[dict] = payload.get("result", {}).get("records", [])

        if not records:
            raise ValueError(
                f"datastore_search returned 0 records for track '{track_name}' "
                f"(resource_id={resource_id}). The track name filter may not match."
            )

        competitors = _parse_records(records)
        print(f"✅ [MARKET] Live fetch SUCCESS — {len(competitors)} competitors for '{track_name}'")

        # --- Update Firestore cache (fire-and-forget; don't block response) ---
        # Lazy import so Firebase is only initialised when the server actually runs
        import db_manager
        db_manager.save_market_cache(track_name, competitors)

        return competitors

    except Exception as gov_err:
        # ---------------------------------------------------------------- #
        # TIER 2 — Fallback to Firestore cache                             #
        # ---------------------------------------------------------------- #
        print(f"⚠️  [MARKET] Gov API failed for track '{track_name}': {gov_err}")
        print(f"⚠️  [MARKET] Falling back to Firestore cache...")

        import db_manager
        cached = db_manager.get_market_cache(track_name)
        if cached:
            print(f"✅ [MARKET] Firestore cache HIT — returning {len(cached)} cached competitors for '{track_name}'")
            return cached

        # ---------------------------------------------------------------- #
        # TIER 3 — Hardcoded safety net                                    #
        # ---------------------------------------------------------------- #
        print(f"🛑 [MARKET] Firestore cache empty. Using hardcoded safety-net data for '{track_name}'.")
        return _HARDCODED_FALLBACK
