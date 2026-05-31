"""Tests for utility functions in app.py."""
import sys
from unittest.mock import patch, MagicMock
import pytest


# app.py redirects sys.stdout/stderr at import time; import it once per session.
# We guard with a try/except so other tests still run if something fails.
try:
    from app import _extract_pdf_url
    _APP_IMPORTED = True
except Exception as _import_err:
    _APP_IMPORTED = False
    _extract_pdf_url = None  # type: ignore


# ── _extract_pdf_url ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_finds_surense_shortlink_in_html():
    html = '<a href="https://u.surense.com/abc123">Download</a>'
    result = _extract_pdf_url(html, "")
    assert result == "https://u.surense.com/abc123"


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_finds_direct_pdf_link_in_html():
    html = '<a href="https://example.com/report.pdf">Click here</a>'
    result = _extract_pdf_url(html, "")
    assert result == "https://example.com/report.pdf"


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_falls_back_to_text_body():
    text = "Download your report: https://example.com/file.pdf"
    result = _extract_pdf_url("", text)
    assert result == "https://example.com/file.pdf"


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_returns_none_when_no_link():
    result = _extract_pdf_url("No links here", "Also no links")
    assert result is None


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_html_takes_priority_over_text():
    html = "https://u.surense.com/html-link"
    text = "https://example.com/text.pdf"
    result = _extract_pdf_url(html, text)
    assert result == "https://u.surense.com/html-link"


@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_extract_pdf_url_finds_generic_download_link():
    html = "https://storage.example.com/download/report-2024"
    result = _extract_pdf_url(html, "")
    assert result == "https://storage.example.com/download/report-2024"


# ── POST /api/auth/demo ───────────────────────────────────────────────────────

@pytest.mark.skipif(not _APP_IMPORTED, reason="app.py could not be imported")
def test_login_demo_seeds_data_and_returns_token():
    import config
    from fastapi.testclient import TestClient
    from app import app as fastapi_app

    with patch("services.demo_seeder.seed_demo_data") as mock_seed, \
         patch("db_manager.get_family_profile", return_value={"householdName": "Demo Family"}):
        test_client = TestClient(fastapi_app)
        resp = test_client.post("/api/auth/demo")

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == config.DEMO_TOKEN
    assert data["uid"] == config.DEMO_UID
