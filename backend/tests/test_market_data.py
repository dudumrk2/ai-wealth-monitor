"""Unit tests for market_data — curated selection, query routing, parsing, and
the CKAN resource-id discovery with its Stale-While-Revalidate fallback."""
import pytest

import market_data


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

def test_safe_float_parses_numeric_string():
    assert market_data._safe_float("12.5") == 12.5


def test_safe_float_parses_int():
    assert market_data._safe_float(5) == 5.0


def test_safe_float_returns_zero_on_none():
    assert market_data._safe_float(None) == 0.0


def test_safe_float_returns_zero_on_garbage():
    assert market_data._safe_float("abc") == 0.0


# ---------------------------------------------------------------------------
# _select_dataset_query
# ---------------------------------------------------------------------------

def test_select_dataset_query_pension_hebrew():
    assert market_data._select_dataset_query("פנסיה") == market_data._PENSION_QUERY


def test_select_dataset_query_pension_english():
    assert market_data._select_dataset_query("pension") == market_data._PENSION_QUERY


def test_select_dataset_query_insurance_managers():
    assert market_data._select_dataset_query("ביטוח מנהלים") == market_data._BITUACH_QUERY


def test_select_dataset_query_defaults_to_gemel():
    assert market_data._select_dataset_query("קרן השתלמות") == market_data._GEMEL_QUERY


def test_select_dataset_query_handles_none():
    assert market_data._select_dataset_query(None) == market_data._GEMEL_QUERY


# ---------------------------------------------------------------------------
# _extract_search_term
# ---------------------------------------------------------------------------

def test_extract_search_term_gemel_stocks():
    assert market_data._extract_search_term("1181 אנליסט גמל מניות", "גמל") == "מניות"


def test_extract_search_term_pension_age_bracket():
    assert market_data._extract_search_term("הפניקס לבני 50 ומטה", "פנסיה") == "50 ומטה"


def test_extract_search_term_gemel_ignores_age_uses_style():
    # For גמל, age brackets are ignored and a style keyword is used instead
    assert market_data._extract_search_term("הפניקס לבני 50 ומטה", "גמל") == "כללי"


def test_extract_search_term_defaults_to_general():
    assert market_data._extract_search_term("שם בלי מאפיינים", "גמל") == "כללי"


def test_extract_search_term_handles_none_track():
    assert market_data._extract_search_term(None, "גמל") == "כללי"


# ---------------------------------------------------------------------------
# _get_curated_competitors
# ---------------------------------------------------------------------------

def test_curated_pension_60_plus():
    assert market_data._get_curated_competitors("פנסיה", "מסלול לבני 60 ומטה") is market_data._TOP_PENSION_60_PLUS


def test_curated_pension_50_plus():
    assert market_data._get_curated_competitors("פנסיה", "מסלול לבני 50 ומטה") is market_data._TOP_PENSION_50_PLUS


def test_curated_pension_stocks():
    assert market_data._get_curated_competitors("פנסיה", "מסלול מניות") is market_data._TOP_PENSION_STOCKS


def test_curated_pension_general_default():
    assert market_data._get_curated_competitors("פנסיה", "מסלול כללי") is market_data._TOP_PENSION_GENERAL


def test_curated_gemel_stocks():
    assert market_data._get_curated_competitors("גמל", "מסלול מניות") is market_data._TOP_GEMEL_STOCKS


def test_curated_gemel_conservative():
    assert market_data._get_curated_competitors("גמל", 'מסלול אג"ח') is market_data._TOP_GEMEL_CONSERVATIVE


def test_curated_gemel_general_default():
    assert market_data._get_curated_competitors("גמל", "מסלול רגיל") is market_data._TOP_GEMEL_GENERAL


# ---------------------------------------------------------------------------
# _parse_records
# ---------------------------------------------------------------------------

def test_parse_records_maps_basic_fields():
    records = [{
        "MANAGING_CORPORATION": "  הראל  ",
        "FUND_NAME": "קרן א",
        "FUND_ID": "512",
        "YEAR_TO_DATE_YIELD": "10.5",
        "YIELD_TRAILING_3_YRS": "30",
        "YIELD_TRAILING_5_YRS": "55",
        "AVG_ANNUAL_MANAGEMENT_FEE": "0.5",
    }]
    parsed = market_data._parse_records(records)
    assert len(parsed) == 1
    row = parsed[0]
    assert row["provider_name"] == "הראל"  # stripped
    assert row["fund_id"] == "512"
    assert row["yield_1yr"] == 10.5
    assert row["yield_3yr"] == 30.0
    assert row["yield_5yr"] == 55.0
    assert row["management_fee_accumulation"] == 0.5


def test_parse_records_falls_back_to_annual_times_period():
    # When cumulative trailing yields are missing, use annual × period
    records = [{
        "MANAGING_CORPORATION": "מיטב",
        "AVG_ANNUAL_YIELD_TRAILING_3YRS": "4",   # → 4 * 3 = 12
        "AVG_ANNUAL_YIELD_TRAILING_5YRS": "3",   # → 3 * 5 = 15
    }]
    parsed = market_data._parse_records(records)
    assert parsed[0]["yield_3yr"] == 12.0
    assert parsed[0]["yield_5yr"] == 15.0


def test_parse_records_skips_malformed_record_but_keeps_valid():
    # A record that raises inside the loop is skipped, others survive
    records = [
        None,  # .get on None raises → skipped
        {"MANAGING_CORPORATION": "כלל"},
    ]
    parsed = market_data._parse_records(records)
    assert len(parsed) == 1
    assert parsed[0]["provider_name"] == "כלל"


# ---------------------------------------------------------------------------
# get_latest_resource_id  (async, httpx + module cache)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        return self._response


@pytest.fixture(autouse=True)
def _clear_resource_cache():
    market_data.CACHED_RESOURCE_IDS.clear()
    yield
    market_data.CACHED_RESOURCE_IDS.clear()


@pytest.mark.asyncio
async def test_get_latest_resource_id_cache_hit_skips_http(monkeypatch):
    market_data.CACHED_RESOURCE_IDS["גמל נט"] = "cached-rid"

    def _boom(*a, **k):
        raise AssertionError("HTTP should not be called on cache hit")

    monkeypatch.setattr(market_data.httpx, "AsyncClient", _boom)
    rid = await market_data.get_latest_resource_id("גמל נט")
    assert rid == "cached-rid"


@pytest.mark.asyncio
async def test_get_latest_resource_id_prefers_year_keyword_and_caches(monkeypatch):
    payload = {"result": {"results": [
        {"resources": [
            {"id": "old", "name": "2019 archive", "created": "2019-01-01"},
            {"id": "new", "name": "Yields 2025", "created": "2020-01-01"},
        ]}
    ]}}
    monkeypatch.setattr(
        market_data.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(_FakeResponse(payload))
    )
    rid = await market_data.get_latest_resource_id("גמל נט")
    assert rid == "new"
    # cached for subsequent calls
    assert market_data.CACHED_RESOURCE_IDS["גמל נט"] == "new"


@pytest.mark.asyncio
async def test_get_latest_resource_id_returns_none_on_empty_results(monkeypatch):
    payload = {"result": {"results": []}}
    monkeypatch.setattr(
        market_data.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(_FakeResponse(payload))
    )
    assert await market_data.get_latest_resource_id("פנסיה נט") is None


@pytest.mark.asyncio
async def test_get_latest_resource_id_returns_none_on_http_error(monkeypatch):
    def _raise(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(market_data.httpx, "AsyncClient", _raise)
    assert await market_data.get_latest_resource_id("גמל נט") is None


# ---------------------------------------------------------------------------
# get_top_competitors  (Firestore cache short-circuit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_top_competitors_returns_firestore_cache_without_external_call(monkeypatch):
    import db_manager
    cached = [{"provider_name": "הראל", "yield_1yr": 10.0}]
    monkeypatch.setattr(db_manager, "get_market_cache", lambda track: cached)

    async def _should_not_run(*a, **k):
        raise AssertionError("external fetch should be skipped on cache hit")

    monkeypatch.setattr(market_data, "_get_top_competitors_myfunds", _should_not_run)
    result = await market_data.get_top_competitors("פנסיה", "מסלול כללי")
    assert result == cached
