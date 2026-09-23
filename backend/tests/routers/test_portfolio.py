"""Route tests for routers/portfolio.py using FastAPI TestClient."""
from unittest.mock import patch, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.portfolio import router, _compute_return_points, _group_into_quarters, _detect_deposit_suggestion
from auth import verify_token

TEST_UID = "test_uid_portfolio"


def _make_client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[verify_token] = lambda: {"uid": TEST_UID}
    app.include_router(router)
    return TestClient(app)


client = _make_client()


# ── DELETE /api/portfolio/fund/{fund_id} ──────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_delete_fund_removes_fund_and_saves(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {
            "user": {"funds": [{"id": "fund-1", "track_name": "Test Fund"}, {"id": "fund-2"}]},
            "spouse": {"funds": []},
        }
    }
    mock_db.save_processed_portfolio.return_value = None

    resp = client.delete("/api/portfolio/fund/fund-1")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    saved_doc = mock_db.save_processed_portfolio.call_args.args[1]
    fund_ids = [f["id"] for f in saved_doc["portfolios"]["user"]["funds"]]
    assert "fund-1" not in fund_ids
    assert "fund-2" in fund_ids


@patch("routers.portfolio.db_manager")
def test_delete_fund_returns_404_when_portfolio_missing(mock_db):
    mock_db.get_processed_portfolio.return_value = None

    resp = client.delete("/api/portfolio/fund/any-id")

    assert resp.status_code == 404


@patch("routers.portfolio.db_manager")
def test_delete_fund_returns_404_when_fund_not_found(mock_db):
    mock_db.get_processed_portfolio.return_value = {
        "portfolios": {
            "user": {"funds": [{"id": "fund-other"}]},
            "spouse": {"funds": []},
        }
    }

    resp = client.delete("/api/portfolio/fund/non-existent-id")

    assert resp.status_code == 404


# ── GET /api/portfolio/fx-rate ────────────────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_get_fx_rate_returns_cached_rate(mock_db):
    mock_db.get_fx_rate.return_value = {"rate": 3.72, "date": "2024-01-15"}

    resp = client.get("/api/portfolio/fx-rate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rate"] == 3.72
    assert data["cached"] is True


@patch("routers.portfolio.db_manager")
def test_get_fx_rate_returns_fallback_on_api_failure(mock_db):
    mock_db.get_fx_rate.return_value = None  # cache miss
    # aiohttp is imported inside the function; patching via sys.modules path
    with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
        resp = client.get("/api/portfolio/fx-rate")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rate"] == 3.70
    assert data["is_fallback"] is True


# ── _compute_return_points unit tests ─────────────────────────────────────────

def test_compute_return_points_empty():
    assert _compute_return_points([], []) == []


def test_compute_return_points_single_snapshot_is_baseline():
    snaps = [{"month": "2026-01", "total_value_ils": 100_000}]
    pts = _compute_return_points(snaps, [])
    assert len(pts) == 1
    assert pts[0]["return_pct"] == 0.0
    assert pts[0]["label"] == "2026-01"


def test_compute_return_points_growth_no_deposits():
    snaps = [
        {"month": "2026-01", "total_value_ils": 100_000},
        {"month": "2026-02", "total_value_ils": 110_000},
    ]
    pts = _compute_return_points(snaps, [])
    # (110k - 100k - 0) / 100k * 100 = 10.0
    assert pts[1]["return_pct"] == 10.0


def test_compute_return_points_deposit_adjusted():
    """A deposit in February should NOT inflate the return."""
    snaps = [
        {"month": "2026-01", "total_value_ils": 100_000},
        {"month": "2026-02", "total_value_ils": 140_000},
    ]
    deps = [{"month": "2026-02", "amount_ils": 30_000}]
    pts = _compute_return_points(snaps, deps)
    # (140k - 100k - 30k) / 100k * 100 = 10.0
    assert pts[1]["return_pct"] == 10.0


def test_compute_return_points_zero_start_value_returns_none():
    snaps = [
        {"month": "2026-01", "total_value_ils": 0},
        {"month": "2026-02", "total_value_ils": 50_000},
    ]
    pts = _compute_return_points(snaps, [])
    # Can't divide by zero → return_pct should be None for all points
    assert pts[0]["return_pct"] is None
    assert pts[1]["return_pct"] is None


def test_compute_return_points_deposit_missing_month_field_ignored():
    """Deposits without a 'month' field fall back to '9999' and are never accumulated."""
    snaps = [
        {"month": "2026-01", "total_value_ils": 100_000},
        {"month": "2026-02", "total_value_ils": 110_000},
    ]
    deps = [{"amount_ils": 50_000}]  # no 'month' key
    pts = _compute_return_points(snaps, deps)
    # Deposit should be ignored — same result as no deposits
    assert pts[1]["return_pct"] == 10.0


# ── _group_into_quarters unit tests ──────────────────────────────────────────

def test_group_into_quarters_single_quarter():
    monthly = [
        {"label": "2026-01", "total_value_ils": 100_000, "return_pct": 0.0},
        {"label": "2026-02", "total_value_ils": 105_000, "return_pct": 5.0},
        {"label": "2026-03", "total_value_ils": 108_000, "return_pct": 8.0},
    ]
    q = _group_into_quarters(monthly)
    assert len(q) == 1
    assert q[0]["label"] == "Q1 2026"
    assert q[0]["return_pct"] == 8.0  # last month of quarter wins


def test_group_into_quarters_multi_year_sorted():
    """Q4 2025 must appear before Q1 2026 (not reversed by string sort)."""
    monthly = [
        {"label": "2025-10", "total_value_ils": 90_000, "return_pct": -2.0},
        {"label": "2025-11", "total_value_ils": 91_000, "return_pct": -1.0},
        {"label": "2025-12", "total_value_ils": 92_000, "return_pct": 0.0},
        {"label": "2026-01", "total_value_ils": 95_000, "return_pct": 3.0},
        {"label": "2026-02", "total_value_ils": 97_000, "return_pct": 5.0},
        {"label": "2026-03", "total_value_ils": 100_000, "return_pct": 8.0},
    ]
    q = _group_into_quarters(monthly)
    labels = [pt["label"] for pt in q]
    assert labels == ["Q4 2025", "Q1 2026"]


# ── _detect_deposit_suggestion unit tests ────────────────────────────────────

def _make_snap(month: str, value: float) -> dict:
    return {"month": month, "total_value_ils": value}


@patch("routers.portfolio.db_manager")
def test_detect_deposit_suggestion_below_threshold(mock_db):
    """Small growth — no suggestion."""
    mock_db.get_portfolio_deposits.return_value = []
    snaps = [_make_snap("2026-08", 100_000), _make_snap("2026-09", 103_000)]
    result = _detect_deposit_suggestion(TEST_UID, snaps)
    assert result is None


@patch("routers.portfolio.db_manager")
def test_detect_deposit_suggestion_above_threshold(mock_db):
    """Large unexplained jump — suggestion returned with correct default_date."""
    mock_db.get_portfolio_deposits.return_value = []
    snaps = [_make_snap("2026-08", 100_000), _make_snap("2026-09", 135_000)]
    result = _detect_deposit_suggestion(TEST_UID, snaps)
    assert result is not None
    assert result["detected"] is True
    assert result["suggested_amount"] == 35_000.0
    assert result["current_month"] == "2026-09"
    # default_date must be first day of detected month — not today
    assert result["default_date"] == "2026-09-01"


@patch("routers.portfolio.db_manager")
def test_detect_deposit_suggestion_suppressed_after_deposit_recorded(mock_db):
    """If the deposit is already registered, unexplained growth drops below threshold."""
    mock_db.get_portfolio_deposits.return_value = [
        {"month": "2026-09", "amount_ils": 30_000}
    ]
    snaps = [_make_snap("2026-08", 100_000), _make_snap("2026-09", 135_000)]
    result = _detect_deposit_suggestion(TEST_UID, snaps)
    # Unexplained = 35k - 30k = 5k, pct = 5%. 5k >= 5k AND 5% >= 4% → still triggers
    # Change values so the remaining unexplained is below threshold
    mock_db.get_portfolio_deposits.return_value = [
        {"month": "2026-09", "amount_ils": 35_000}
    ]
    result = _detect_deposit_suggestion(TEST_UID, snaps)
    assert result is None  # fully explained — no suggestion


@patch("routers.portfolio.db_manager")
def test_detect_deposit_suggestion_no_previous_snapshot(mock_db):
    """Only one snapshot — cannot compare, returns None."""
    mock_db.get_portfolio_deposits.return_value = []
    snaps = [_make_snap("2026-09", 100_000)]
    result = _detect_deposit_suggestion(TEST_UID, snaps)
    assert result is None


# ── GET /api/portfolio/performance ────────────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_get_performance_no_data(mock_db):
    mock_db.get_portfolio_snapshots.return_value = []
    mock_db.get_portfolio_deposits.return_value = []

    resp = client.get("/api/portfolio/performance?view=monthly")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is False
    assert data["points"] == []


@patch("routers.portfolio.db_manager")
def test_get_performance_monthly_returns_points(mock_db):
    snaps = [
        {"month": "2026-01", "total_value_ils": 100_000},
        {"month": "2026-02", "total_value_ils": 110_000},
    ]
    mock_db.get_portfolio_snapshots.return_value = snaps
    mock_db.get_portfolio_deposits.return_value = []

    resp = client.get("/api/portfolio/performance?view=monthly")

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is True
    assert len(data["points"]) == 2
    assert data["total_return_pct"] == 10.0
    assert "deposit_suggestion" in data


@patch("routers.portfolio.db_manager")
def test_get_performance_deposit_suggestion_included_in_response(mock_db):
    """deposit_suggestion key must always be present in the response."""
    snaps = [{"month": "2026-01", "total_value_ils": 100_000}]
    mock_db.get_portfolio_snapshots.return_value = snaps
    mock_db.get_portfolio_deposits.return_value = []

    resp = client.get("/api/portfolio/performance?view=monthly")

    assert resp.status_code == 200
    assert "deposit_suggestion" in resp.json()


# ── POST /api/portfolio/deposit ───────────────────────────────────────────────

@patch("routers.portfolio.db_manager")
def test_record_deposit_happy_path(mock_db):
    mock_db.save_portfolio_deposit.return_value = True

    resp = client.post("/api/portfolio/deposit", json={"amount_ils": 30000, "date": "2026-01-15"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch("routers.portfolio.db_manager")
def test_record_deposit_negative_amount_rejected(mock_db):
    resp = client.post("/api/portfolio/deposit", json={"amount_ils": -100, "date": "2026-01-15"})
    assert resp.status_code == 400


@patch("routers.portfolio.db_manager")
def test_record_deposit_invalid_date_format_rejected(mock_db):
    resp = client.post("/api/portfolio/deposit", json={"amount_ils": 5000, "date": "15-01-2026"})
    assert resp.status_code == 400


@patch("routers.portfolio.db_manager")
def test_record_deposit_future_date_rejected(mock_db):
    resp = client.post("/api/portfolio/deposit", json={"amount_ils": 5000, "date": "2099-01-01"})
    assert resp.status_code == 400
    assert "עתיד" in resp.json()["detail"]

