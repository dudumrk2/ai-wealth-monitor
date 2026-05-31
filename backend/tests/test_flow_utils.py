"""Unit tests for flow_utils helpers."""
import json
from unittest.mock import MagicMock, patch
import pytest
import fitz

import flow_utils


# ── prepare_pdf_for_vision ────────────────────────────────────────────────────

def _make_unencrypted_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_prepare_pdf_for_vision_extracts_pii_from_both_members():
    pdf_bytes = _make_unencrypted_pdf()
    f_profile = {
        "pii_data": {
            "member1": {"name": "Alice", "lastName": "Smith", "idNumber": "012345678", "email": "a@b.com"},
            "member2": {"name": "Bob", "lastName": "Jones", "idNumber": "987654321", "email": "b@b.com"},
        }
    }

    doc, targets, authenticated_id = flow_utils.prepare_pdf_for_vision(pdf_bytes, f_profile)
    doc.close()

    assert "Alice" in targets
    assert "Smith" in targets
    assert "012345678" in targets
    assert "Bob" in targets
    assert "987654321" in targets
    assert authenticated_id is None


def test_prepare_pdf_for_vision_strips_leading_zero_from_id():
    pdf_bytes = _make_unencrypted_pdf()
    f_profile = {
        "pii_data": {
            "member1": {"name": "Dan", "idNumber": "012345678"},
        }
    }

    _, targets, _ = flow_utils.prepare_pdf_for_vision(pdf_bytes, f_profile)

    assert "012345678" in targets
    assert "12345678" in targets


def test_prepare_pdf_for_vision_empty_profile_returns_empty_targets():
    pdf_bytes = _make_unencrypted_pdf()
    doc, targets, authenticated_id = flow_utils.prepare_pdf_for_vision(pdf_bytes, {})
    doc.close()

    assert targets == []
    assert authenticated_id is None


# ── call_claude_vision ────────────────────────────────────────────────────────

def test_call_claude_vision_raises_on_empty_images():
    with pytest.raises(ValueError, match="No images"):
        flow_utils.call_claude_vision("fake-key", [], "any prompt")


def test_call_claude_vision_strips_json_fence_and_parses(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='```json\n{"key": "value"}\n```')]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr(flow_utils, "Anthropic", lambda api_key: mock_client)

    result = flow_utils.call_claude_vision("fake-key", ["b64data"], "prompt")

    assert result == {"key": "value"}


def test_call_claude_vision_raises_on_invalid_json(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="This is not JSON at all")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr(flow_utils, "Anthropic", lambda api_key: mock_client)

    with pytest.raises(ValueError, match="Invalid JSON"):
        flow_utils.call_claude_vision("fake-key", ["b64data"], "prompt")


# ── call_gemini_json ──────────────────────────────────────────────────────────

def test_call_gemini_json_returns_parsed_json_on_first_attempt(monkeypatch):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text='{"result": true}')
    monkeypatch.setattr(flow_utils.genai, "Client", lambda api_key: mock_client)
    monkeypatch.setattr(flow_utils.time, "sleep", MagicMock())

    result = flow_utils.call_gemini_json("key", "sys", "user", max_retries=3)

    assert result == {"result": True}
    assert mock_client.models.generate_content.call_count == 1


def test_call_gemini_json_retries_on_transient_error_and_succeeds(monkeypatch):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        RuntimeError("transient error"),
        MagicMock(text='{"ok": 1}'),
    ]
    monkeypatch.setattr(flow_utils.genai, "Client", lambda api_key: mock_client)
    monkeypatch.setattr(flow_utils.time, "sleep", MagicMock())

    result = flow_utils.call_gemini_json("key", "sys", "user", max_retries=3, retry_delay=0.0)

    assert result == {"ok": 1}
    assert mock_client.models.generate_content.call_count == 2


def test_call_gemini_json_raises_runtime_error_after_max_retries(monkeypatch):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("always fails")
    monkeypatch.setattr(flow_utils.genai, "Client", lambda api_key: mock_client)
    monkeypatch.setattr(flow_utils.time, "sleep", MagicMock())

    with pytest.raises(RuntimeError):
        flow_utils.call_gemini_json("key", "sys", "user", max_retries=2, retry_delay=0.0)

    assert mock_client.models.generate_content.call_count == 2
