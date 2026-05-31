"""Route tests for routers/alternatives.py."""
from unittest.mock import patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.alternatives import router
from auth import verify_token

TEST_UID = "test_uid_alt"


def _make_client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[verify_token] = lambda: {"uid": TEST_UID}
    app.include_router(router)
    return TestClient(app)


client = _make_client()


# ── GET /api/alternatives/projects ───────────────────────────────────────────

@patch("routers.alternatives.db_manager")
def test_get_projects_returns_list(mock_db):
    mock_db.get_alt_projects.return_value = [
        {"id": "p1", "name": "Project A", "developer": "Dev",
         "originalAmount": 100000, "currency": "ILS", "startDate": "2023-01-01",
         "durationMonths": 12, "expectedReturn": 8.0, "status": "Active"},
    ]

    resp = client.get("/api/alternatives/projects")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Project A"
    mock_db.get_alt_projects.assert_called_once_with(TEST_UID)


# ── POST /api/alternatives/projects ──────────────────────────────────────────

@patch("routers.alternatives.db_manager")
def test_add_project_returns_doc_id(mock_db):
    mock_db.add_alt_project.return_value = "new-doc-id"

    payload = {
        "name": "New Project", "developer": "Dev B",
        "originalAmount": 50000, "currency": "ILS",
        "startDate": "2024-06-01", "durationMonths": 24,
        "expectedReturn": 10.0, "status": "Active",
    }
    resp = client.post("/api/alternatives/projects", json=payload)

    assert resp.status_code == 200
    assert resp.json()["id"] == "new-doc-id"
    assert mock_db.add_alt_project.call_args.args[0] == TEST_UID


@patch("routers.alternatives.db_manager")
def test_add_project_returns_500_when_db_fails(mock_db):
    mock_db.add_alt_project.return_value = None

    payload = {
        "name": "Bad Project", "developer": "Dev", "originalAmount": 1000,
        "currency": "ILS", "startDate": "2024-01-01", "durationMonths": 6,
        "expectedReturn": 5.0,
    }
    resp = client.post("/api/alternatives/projects", json=payload)

    assert resp.status_code == 500


# ── GET /api/alternatives/leveraged-policies ─────────────────────────────────

@patch("routers.alternatives.db_manager")
def test_get_leveraged_policies_returns_list(mock_db):
    mock_db.get_leveraged_policies.return_value = [
        {"id": "pol-1", "policyNumber": "123", "name": "Policy A",
         "funderLink": "https://example.com", "currentBalance": 200000,
         "baseMonth": "2024-01", "balloonLoanAmount": 100000,
         "interestRate": 5.0, "initialDepositAmount": 150000,
         "initialRepaymentDate": "2030-01-01"},
    ]

    resp = client.get("/api/alternatives/leveraged-policies")

    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Policy A"
    mock_db.get_leveraged_policies.assert_called_once_with(TEST_UID)


# ── POST /api/alternatives/leveraged-policies ────────────────────────────────

@patch("routers.alternatives.db_manager")
def test_add_leveraged_policy_stores_and_returns_id(mock_db):
    mock_db.add_leveraged_policy.return_value = "pol-new"

    payload = {
        "policyNumber": "POL-007", "name": "New Policy",
        "funderLink": "https://funder.com/p", "currentBalance": 100000,
        "baseMonth": "2024-01", "balloonLoanAmount": 50000,
        "interestRate": 4.5, "initialDepositAmount": 80000,
        "initialRepaymentDate": "2029-01-01",
    }
    resp = client.post("/api/alternatives/leveraged-policies", json=payload)

    assert resp.status_code == 200
    assert resp.json()["id"] == "pol-new"
    call_data = mock_db.add_leveraged_policy.call_args.args[1]
    assert call_data["id"] == "POL-007"
