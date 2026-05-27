"""Unit tests for pure helpers in report_utils.py."""
import pytest
import fitz

from report_utils import (
    _parse_float,
    _is_index_mismatch,
    _get_similarity,
    _redact_and_render_pdf,
)


# ── _parse_float ──────────────────────────────────────────────────────────────

def test_parse_float_strips_percent():
    assert _parse_float("5.5%") == pytest.approx(5.5)


def test_parse_float_strips_commas():
    assert _parse_float("1,500.25") == pytest.approx(1500.25)


def test_parse_float_handles_none():
    assert _parse_float(None) == 0.0


def test_parse_float_handles_empty_string():
    assert _parse_float("") == 0.0


def test_parse_float_plain_integer_string():
    assert _parse_float("42") == pytest.approx(42.0)


# ── _is_index_mismatch ────────────────────────────────────────────────────────

def test_is_index_mismatch_api_is_index_pdf_is_not_returns_true():
    assert _is_index_mismatch("מסלול גדילה", "קרן עוקב מדד S&P 500") is True


def test_is_index_mismatch_both_are_index_returns_false():
    assert _is_index_mismatch("עוקב מדד S&P", "קרן עוקב מדד S&P 500") is False


def test_is_index_mismatch_neither_is_index_returns_false():
    assert _is_index_mismatch("מסלול גדילה", "קרן גדילה") is False


def test_is_index_mismatch_pdf_is_index_api_is_not_returns_false():
    assert _is_index_mismatch("עוקב מדד S&P", "מסלול גדילה") is False


# ── _get_similarity ───────────────────────────────────────────────────────────

def test_get_similarity_identical_strings_returns_1():
    assert _get_similarity("hello", "hello") == pytest.approx(1.0)


def test_get_similarity_completely_different_strings_is_low():
    assert _get_similarity("abc", "xyz") < 0.5


def test_get_similarity_empty_strings_returns_1():
    assert _get_similarity("", "") == pytest.approx(1.0)


# ── _redact_and_render_pdf ────────────────────────────────────────────────────

def _make_doc(text: str) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc


def test_redact_and_render_pdf_returns_base64_strings():
    doc = _make_doc("Hello SECRET world")
    result = _redact_and_render_pdf(doc, ["SECRET"])
    assert isinstance(result, list)
    assert len(result) >= 1
    import base64
    for item in result:
        assert isinstance(item, str)
        base64.b64decode(item)


def test_redact_and_render_pdf_skips_first_page_when_long_enough(monkeypatch):
    import config
    monkeypatch.setattr(config, "PDF_SKIP_PAGES", 1)
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()
    result = _redact_and_render_pdf(doc, [])
    assert len(result) == 2
