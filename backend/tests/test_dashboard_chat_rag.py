"""Unit tests for RAG-powered query_insurance_policy tool (Site 2)."""
from unittest.mock import MagicMock, patch
import pytest

import routers.dashboard_chat as chat_module


# ---------------------------------------------------------------------------
# Tests for the module-level helper _query_insurance_policy
# ---------------------------------------------------------------------------


def test_query_insurance_policy_returns_top_excerpts(monkeypatch):
    """Should embed query, retrieve chunks, rank via cosine, return formatted excerpts."""
    chunks = [
        {"text": "כיסוי נכות", "anchor": "כיסוי נכות", "source_doc": "life.pdf", "embedding": [1.0, 0.0]},
        {"text": "פרמיה חודשית", "anchor": "פרמיה חודשית", "source_doc": "life.pdf", "embedding": [0.0, 1.0]},
        {"text": "ביטוח רכב", "anchor": "ביטוח רכב", "source_doc": "car.pdf", "embedding": [0.7, 0.7]},
    ]

    monkeypatch.setattr(chat_module, "embed_query", MagicMock(return_value=[1.0, 0.0]))
    monkeypatch.setattr(chat_module, "get_insurance_chunks", MagicMock(return_value=chunks))
    monkeypatch.setattr(chat_module, "cosine_top_k", MagicMock(return_value=[(0, 1.0), (2, 0.7071)]))

    result = chat_module._query_insurance_policy("מה הכיסוי לנכות?", "uid_abc")

    assert "כיסוי נכות" in result
    assert "life.pdf" in result
    # Should not include second result's text (ranked 3rd)
    assert "פרמיה חודשית" not in result


def test_query_insurance_policy_passes_uid_to_get_chunks(monkeypatch):
    """get_insurance_chunks must be called with the correct uid."""
    monkeypatch.setattr(chat_module, "embed_query", MagicMock(return_value=[0.5]))
    mock_get = MagicMock(return_value=[])
    monkeypatch.setattr(chat_module, "get_insurance_chunks", mock_get)
    monkeypatch.setattr(chat_module, "cosine_top_k", MagicMock(return_value=[]))

    chat_module._query_insurance_policy("any question", "uid_xyz")

    mock_get.assert_called_once_with("uid_xyz")


def test_query_insurance_policy_returns_no_results_message_when_chunks_empty(monkeypatch):
    """When no chunks are indexed, return a helpful 'no policies indexed' message."""
    monkeypatch.setattr(chat_module, "embed_query", MagicMock(return_value=[0.5]))
    monkeypatch.setattr(chat_module, "get_insurance_chunks", MagicMock(return_value=[]))
    monkeypatch.setattr(chat_module, "cosine_top_k", MagicMock(return_value=[]))

    result = chat_module._query_insurance_policy("מה הכיסוי?", "uid_no_chunks")

    assert isinstance(result, str) and len(result) > 0
    # Should signal that no indexed content was found
    assert "no" in result.lower() or "לא" in result or "indexed" in result.lower() or "פוליסה" in result


def test_query_insurance_policy_passes_embeddings_to_cosine_top_k(monkeypatch):
    """cosine_top_k must receive the query vector and the chunk embedding matrix."""
    chunks = [
        {"text": "t1", "anchor": "a1", "source_doc": "x.pdf", "embedding": [0.1, 0.2]},
        {"text": "t2", "anchor": "a2", "source_doc": "x.pdf", "embedding": [0.3, 0.4]},
    ]
    query_vec = [0.9, 0.1]
    monkeypatch.setattr(chat_module, "embed_query", MagicMock(return_value=query_vec))
    monkeypatch.setattr(chat_module, "get_insurance_chunks", MagicMock(return_value=chunks))
    mock_cosine = MagicMock(return_value=[(0, 0.9)])
    monkeypatch.setattr(chat_module, "cosine_top_k", mock_cosine)

    chat_module._query_insurance_policy("q", "uid")

    call_args = mock_cosine.call_args
    assert call_args.args[0] == query_vec
    assert call_args.args[1] == [[0.1, 0.2], [0.3, 0.4]]
    assert call_args.args[2] == 5  # k=5


def test_system_prompt_references_query_insurance_policy():
    """The system_prompt template must instruct Gemini to use query_insurance_policy, not read_full_policy."""
    # The instruction string is built inside copilot_chat_ask — check the source
    import inspect
    source = inspect.getsource(chat_module.copilot_chat_ask)
    assert "query_insurance_policy" in source
    assert "read_full_policy" not in source


def test_query_result_includes_source_and_heading(monkeypatch):
    """Retrieval output must include מקור (source_doc) and סעיף (section heading)."""
    fake_chunks = [{
        "embedding": [0.1] * 768,
        "text": "## \u05db\u05d9\u05e1\u05d5\u05d9 \u05d2\u05e0\u05d9\u05d1\u05d4\n\u05de\u05db\u05e1\u05d4 \u05d2\u05e0\u05d9\u05d1\u05d4 \u05de\u05dc\u05d0\u05d4.",
        "anchor": "## \u05db\u05d9\u05e1\u05d5\u05d9 \u05d2\u05e0\u05d9\u05d1\u05d4",
        "source_doc": "car_policy.pdf",
    }]
    monkeypatch.setattr(chat_module, "get_insurance_chunks", lambda uid: fake_chunks)
    monkeypatch.setattr(chat_module, "embed_query", lambda q: [0.1] * 768)
    monkeypatch.setattr(chat_module, "cosine_top_k", lambda qv, embs, k: [(0, 0.95)])
    result = chat_module._query_insurance_policy("\u05db\u05d9\u05e1\u05d5\u05d9 \u05d2\u05e0\u05d9\u05d1\u05d4", "uid123")
    assert "\u05de\u05e7\u05d5\u05e8: car_policy.pdf" in result
    assert "\u05e1\u05e2\u05d9\u05e3: ## \u05db\u05d9\u05e1\u05d5\u05d9 \u05d2\u05e0\u05d9\u05d1\u05d4" in result


def test_system_prompt_includes_refusal_instruction():
    """System prompt must instruct the model to refuse when excerpts don't answer."""
    import inspect
    source = inspect.getsource(chat_module.copilot_chat_ask)
    assert "לא מצאתי מידע מפורש בפוליסה על כך" in source

