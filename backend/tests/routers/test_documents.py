"""Unit tests for the pure portfolio-merge helpers in routers/documents.py:
normalize_id, _get_fund_unique_key and _merge_portfolios."""
from routers.documents import normalize_id, _get_fund_unique_key, _merge_portfolios


# ---------------------------------------------------------------------------
# normalize_id
# ---------------------------------------------------------------------------

def test_normalize_id_strips_excel_float_suffix():
    assert normalize_id("123456789.0") == "123456789"


def test_normalize_id_strips_leading_zeros():
    assert normalize_id("000512") == "512"


def test_normalize_id_empty_returns_empty():
    assert normalize_id("") == ""
    assert normalize_id(None) == ""


def test_normalize_id_accepts_numeric_input():
    assert normalize_id(512) == "512"


# ---------------------------------------------------------------------------
# _get_fund_unique_key
# ---------------------------------------------------------------------------

def test_unique_key_insurance_uses_provider_and_policy_number():
    # provider is lower-cased; policy_number is preserved verbatim
    fund = {"category": "insurance", "provider_name": "Harel", "policy_number": "POL-1"}
    assert _get_fund_unique_key(fund) == "ins_harel_POL-1"


def test_unique_key_insurance_falls_back_to_track_when_no_policy_number():
    fund = {"category": "insurance", "provider": "Migdal", "track_name": "Risk"}
    assert _get_fund_unique_key(fund) == "ins_migdal_risk"


def test_unique_key_insurance_ignores_nan_policy_number():
    fund = {"category": "insurance", "provider_name": "Clal", "policy_number": "nan", "track_name": "Life"}
    assert _get_fund_unique_key(fund) == "ins_clal_life"


def test_unique_key_pension_uses_fund_id():
    fund = {"category": "pension", "provider_name": "Meitav", "fund_id": "9988"}
    assert _get_fund_unique_key(fund) == "pen_9988"


def test_unique_key_general_fallback_uses_provider_and_track():
    fund = {"category": "stocks", "provider_name": "IBI", "track_name": "S&P"}
    assert _get_fund_unique_key(fund) == "gen_ibi_s&p"


# ---------------------------------------------------------------------------
# _merge_portfolios
# ---------------------------------------------------------------------------

def test_merge_adds_new_fund():
    existing = [{"category": "pension", "fund_id": "1", "balance": 100}]
    new = [{"category": "pension", "fund_id": "2", "balance": 200}]
    merged = _merge_portfolios(existing, new)
    assert len(merged) == 2
    balances = sorted(f["balance"] for f in merged)
    assert balances == [100, 200]


def test_merge_updates_existing_fund_in_place():
    existing = [{"category": "pension", "fund_id": "1", "balance": 100}]
    new = [{"category": "pension", "fund_id": "1", "balance": 999}]
    merged = _merge_portfolios(existing, new)
    assert len(merged) == 1
    assert merged[0]["balance"] == 999


def test_merge_preserves_existing_firestore_id_when_new_lacks_it():
    existing = [{"category": "pension", "fund_id": "1", "id": "fs-abc", "balance": 100}]
    new = [{"category": "pension", "fund_id": "1", "balance": 250}]
    merged = _merge_portfolios(existing, new)
    assert merged[0]["id"] == "fs-abc"
    assert merged[0]["balance"] == 250


def test_merge_empty_existing_returns_all_new():
    new = [{"category": "pension", "fund_id": "7", "balance": 70}]
    assert _merge_portfolios([], new) == new
