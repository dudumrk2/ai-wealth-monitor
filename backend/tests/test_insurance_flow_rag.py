"""Unit tests for RAG indexing wired into InsuranceFlow.extract_data (Site 1)."""
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

import document_flows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow(target_policy_id=None):
    """Return an InsuranceFlow wired for PDF (not spreadsheet) with minimal profile."""
    return document_flows.InsuranceFlow(
        filename="policy.pdf",
        is_spreadsheet=False,
        f_profile={"pii_data": {}},
        target_policy_id=target_policy_id,
    )


# ---------------------------------------------------------------------------
# Site 1 Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_data_indexes_chunks_after_claude_extraction(monkeypatch):
    """After Claude extraction, the flow must redact, chunk, embed, and save chunks."""
    flow = _make_flow(target_policy_id="pol_abc")
    pdf_bytes = b"%PDF fake"

    # --- Stub infrastructure so the test never touches the network ---
    # Claude Vision succeeds
    monkeypatch.setattr(
        document_flows,
        "call_claude_vision",
        MagicMock(return_value={"policy_type": "life", "premium": 500}),
    )
    # Storage upload succeeds
    with patch("routers.documents.upload_to_firebase_storage", return_value="gs://fake/url"), \
         patch("routers.documents._extract_har_bituach_data"), \
         patch("flow_utils.prepare_pdf_for_vision", return_value=(MagicMock(spec=list, __iter__=lambda s: iter([]), __getitem__=lambda s, k: []), [], [])):

        # fitz is already imported in document_flows — stub page rendering
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=[])
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.__len__ = MagicMock(return_value=0)

        with patch("flow_utils.prepare_pdf_for_vision", return_value=(mock_doc, [], [])):

            # RAG pipeline stubs (all must be called)
            mock_redact = MagicMock(return_value=b"%PDF redacted")
            mock_extract_md = MagicMock(return_value="## Section\nsome text")
            mock_chunk = MagicMock(return_value=[{"chunk_id": "pol_abc_0", "text": "t", "anchor": "t",
                                                   "embedding": [], "policy_id": "pol_abc", "source_doc": "policy.pdf"}])
            mock_embed = MagicMock(return_value=[[0.1] * 768])
            mock_save = MagicMock(return_value=True)

            monkeypatch.setattr(document_flows, "redact_pdf_bytes", mock_redact)
            monkeypatch.setattr(document_flows, "extract_markdown_via_gemini", mock_extract_md)
            monkeypatch.setattr(document_flows, "chunk_section_aware", mock_chunk)
            monkeypatch.setattr(document_flows, "embed_documents", mock_embed)
            monkeypatch.setattr(document_flows, "save_policy_chunks", mock_save)

            result = await flow.extract_data(pdf_bytes, "policy.pdf", "uid_123")

    # Core extraction result preserved
    assert result["policy_type"] == "life"

    # RAG pipeline was called in order with correct args
    mock_redact.assert_called_once()
    mock_extract_md.assert_called_once_with(b"%PDF redacted")
    mock_chunk.assert_called_once_with("## Section\nsome text", source_doc="policy.pdf", policy_id="pol_abc")
    # embed called with the chunk texts
    texts_arg = mock_embed.call_args.args[0]
    assert texts_arg == ["t"]
    # save called with uid, policy_id, and chunks+embeddings merged
    save_args = mock_save.call_args.args
    assert save_args[0] == "uid_123"
    assert save_args[1] == "pol_abc"
    saved_chunks = save_args[2]
    assert saved_chunks[0]["embedding"] == [0.1] * 768


@pytest.mark.asyncio
async def test_extract_data_uses_filename_slug_when_no_target_policy_id(monkeypatch):
    """When target_policy_id is None, derive policy_id from the filename."""
    flow = _make_flow(target_policy_id=None)
    pdf_bytes = b"%PDF fake"

    with patch("routers.documents.upload_to_firebase_storage", return_value=None), \
         patch("flow_utils.prepare_pdf_for_vision", return_value=(MagicMock(__iter__=lambda s: iter([]), __getitem__=lambda s, k: []), [], [])):

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        with patch("flow_utils.prepare_pdf_for_vision", return_value=(mock_doc, [], [])):

            monkeypatch.setattr(document_flows, "call_claude_vision",
                                MagicMock(return_value={"policy_type": "health"}))
            monkeypatch.setattr(document_flows, "redact_pdf_bytes", MagicMock(return_value=b"r"))
            monkeypatch.setattr(document_flows, "extract_markdown_via_gemini", MagicMock(return_value="## S\ntext"))
            mock_chunk = MagicMock(return_value=[])
            mock_embed = MagicMock(return_value=[])
            mock_save = MagicMock(return_value=True)
            monkeypatch.setattr(document_flows, "chunk_section_aware", mock_chunk)
            monkeypatch.setattr(document_flows, "embed_documents", mock_embed)
            monkeypatch.setattr(document_flows, "save_policy_chunks", mock_save)

            await flow.extract_data(pdf_bytes, "my policy 2024.pdf", "uid_x")

    # policy_id must be derived from filename (slug = stem, lowercased, spaces→_)
    chunk_call = mock_chunk.call_args
    assert chunk_call.kwargs["policy_id"] == "my_policy_2024"


@pytest.mark.asyncio
async def test_extract_data_rag_failure_does_not_raise(monkeypatch):
    """RAG indexing errors must be non-fatal — core extraction result still returned."""
    flow = _make_flow(target_policy_id="pol_x")
    pdf_bytes = b"%PDF fake"

    with patch("routers.documents.upload_to_firebase_storage", return_value=None), \
         patch("flow_utils.prepare_pdf_for_vision", return_value=(MagicMock(__iter__=lambda s: iter([]), __getitem__=lambda s, k: []), [], [])):

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        with patch("flow_utils.prepare_pdf_for_vision", return_value=(mock_doc, [], [])):

            monkeypatch.setattr(document_flows, "call_claude_vision",
                                MagicMock(return_value={"policy_type": "car"}))
            # RAG pipeline explodes
            monkeypatch.setattr(document_flows, "redact_pdf_bytes",
                                MagicMock(side_effect=RuntimeError("redaction failed")))
            monkeypatch.setattr(document_flows, "extract_markdown_via_gemini", MagicMock())
            monkeypatch.setattr(document_flows, "chunk_section_aware", MagicMock())
            monkeypatch.setattr(document_flows, "embed_documents", MagicMock())
            monkeypatch.setattr(document_flows, "save_policy_chunks", MagicMock())

            # Must NOT raise
            result = await flow.extract_data(pdf_bytes, "car.pdf", "uid_y")

    assert result["policy_type"] == "car"
