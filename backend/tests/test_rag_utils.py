"""Unit tests for rag_utils — insurance policy RAG helpers."""
from unittest.mock import MagicMock

import fitz
import pytest

from rag_utils import (
    EMBED_MODEL,
    EMBED_OUTPUT_DIM,
    SECTION_MAX_CHARS,
    chunk_section_aware,
    cosine_top_k,
    embed_documents,
    embed_query,
    extract_markdown_via_gemini,
    redact_pdf_bytes,
)


def test_chunk_section_aware_splits_on_headings_no_e5_prefix():
    md = (
        "## Section A\n"
        "content A line 1\n"
        "content A line 2\n"
        "\n"
        "## Section B\n"
        "content B\n"
    )
    chunks = chunk_section_aware(md, source_doc="policy1.pdf", policy_id="p_42")

    assert len(chunks) == 2

    # text is raw — NO "passage: " e5 prefix
    assert chunks[0]["text"].startswith("## Section A")
    assert chunks[1]["text"].startswith("## Section B")
    assert "passage:" not in chunks[0]["text"]
    assert "passage:" not in chunks[1]["text"]

    # anchor = heading line for heading-prefixed chunks
    assert chunks[0]["anchor"] == "## Section A"
    assert chunks[1]["anchor"] == "## Section B"

    # chunk_id = "{policy_id}_{idx}" (valid Firestore doc id)
    assert chunks[0]["chunk_id"] == "p_42_0"
    assert chunks[1]["chunk_id"] == "p_42_1"

    # source_doc preserved
    assert chunks[0]["source_doc"] == "policy1.pdf"
    assert chunks[1]["source_doc"] == "policy1.pdf"


def test_chunk_section_aware_oversized_section_splits_into_subchunks():
    """A section longer than SECTION_MAX_CHARS falls back to fixed-size sub-chunking."""
    long_body = "x" * (SECTION_MAX_CHARS * 2)  # well over the cap
    md = f"## Big Section\n{long_body}\n"

    chunks = chunk_section_aware(md, source_doc="big.pdf", policy_id="p")

    # Must produce more than one chunk for the oversized section
    assert len(chunks) > 1
    # Every chunk respects the size cap
    assert all(len(c["text"]) <= SECTION_MAX_CHARS for c in chunks)
    # chunk_id indices are sequential starting at 0
    assert [c["chunk_id"] for c in chunks] == [f"p_{i}" for i in range(len(chunks))]
    # Metadata preserved on every sub-chunk
    assert all(c["source_doc"] == "big.pdf" for c in chunks)
    assert all(c["policy_id"] == "p" for c in chunks)


def test_cosine_top_k_returns_indices_sorted_by_descending_similarity():
    query = [1.0, 0.0]
    chunk_vectors = [
        [0.0, 1.0],   # idx 0 — orthogonal       (sim 0.0)
        [1.0, 0.0],   # idx 1 — identical        (sim 1.0)
        [0.7071, 0.7071],  # idx 2 — 45 deg     (sim ~0.707)
    ]

    top = cosine_top_k(query, chunk_vectors, k=2)

    assert len(top) == 2
    # ordered by descending similarity
    assert top[0][0] == 1
    assert top[1][0] == 2
    assert top[0][1] > top[1][1]
    assert top[0][1] == pytest.approx(1.0, abs=1e-3)
    assert top[1][1] == pytest.approx(0.7071, abs=1e-3)


def test_cosine_top_k_clamps_to_available_chunks_when_k_exceeds():
    query = [1.0, 0.0]
    chunk_vectors = [[1.0, 0.0], [0.0, 1.0]]

    top = cosine_top_k(query, chunk_vectors, k=10)

    assert len(top) == 2  # only as many results as available chunks


def _make_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_redact_pdf_bytes_physically_removes_pii_from_text_layer():
    """apply_redactions must remove the underlying text, not just cover it."""
    pdf_bytes = _make_pdf_with_text("Hello SECRET world")

    redacted = redact_pdf_bytes(pdf_bytes, ["SECRET"])

    doc = fitz.open(stream=redacted, filetype="pdf")
    extracted = doc[0].get_text()
    doc.close()

    assert "SECRET" not in extracted
    assert "Hello" in extracted
    assert "world" in extracted


def test_redact_pdf_bytes_ignores_short_or_empty_targets():
    """Targets shorter than 2 chars must be ignored to avoid catastrophic over-redaction."""
    pdf_bytes = _make_pdf_with_text("Hello a world")

    redacted = redact_pdf_bytes(pdf_bytes, ["", "a", "  "])

    doc = fitz.open(stream=redacted, filetype="pdf")
    extracted = doc[0].get_text()
    doc.close()
    assert "Hello" in extracted
    assert "world" in extracted


def _mock_embed_response(vectors: list[list[float]]) -> MagicMock:
    resp = MagicMock()
    resp.embeddings = [MagicMock(values=v) for v in vectors]
    return resp


def test_embed_documents_uses_retrieval_document_task_type_and_returns_lists():
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _mock_embed_response(
        [[0.1, 0.2], [0.3, 0.4]]
    )

    result = embed_documents(["chunk a", "chunk b"], client=mock_client)

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    call = mock_client.models.embed_content.call_args
    assert call.kwargs["model"] == EMBED_MODEL
    assert call.kwargs["contents"] == ["chunk a", "chunk b"]
    cfg = call.kwargs["config"]
    assert cfg.task_type == "RETRIEVAL_DOCUMENT"
    assert cfg.output_dimensionality == EMBED_OUTPUT_DIM


def test_embed_query_uses_retrieval_query_task_type_and_returns_one_vector():
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _mock_embed_response([[0.5, 0.6]])

    result = embed_query("what is the deductible?", client=mock_client)

    assert result == [0.5, 0.6]
    call = mock_client.models.embed_content.call_args
    assert call.kwargs["model"] == EMBED_MODEL
    assert call.kwargs["contents"] == ["what is the deductible?"]
    cfg = call.kwargs["config"]
    assert cfg.task_type == "RETRIEVAL_QUERY"
    assert cfg.output_dimensionality == EMBED_OUTPUT_DIM


def test_extract_markdown_via_gemini_sends_pdf_inline_and_returns_markdown_text():
    import config

    pdf_bytes = b"%PDF-1.4 fake bytes"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(
        text="## Section\nbody content"
    )

    result = extract_markdown_via_gemini(pdf_bytes, client=mock_client)

    assert result == "## Section\nbody content"

    call = mock_client.models.generate_content.call_args
    assert call.kwargs["model"] == config.GEMINI_MODEL_NAME

    contents = call.kwargs["contents"]
    assert len(contents) == 2
    pdf_part = contents[0]
    assert pdf_part.inline_data.mime_type == "application/pdf"
    assert pdf_part.inline_data.data == pdf_bytes
    prompt = contents[1]
    assert isinstance(prompt, str) and len(prompt) > 0


def test_anchor_uses_section_heading():
    md = "## \u05db\u05d9\u05e1\u05d5\u05d9\u05d9\u05dd \u05de\u05d9\u05d5\u05d7\u05d3\u05d9\u05dd\n\u05ea\u05d5\u05db\u05df \u05d4\u05e1\u05e2\u05d9\u05e3 \u05db\u05d0\u05df."
    chunks = chunk_section_aware(md, "policy.pdf", "pol1")
    assert chunks[0]["anchor"] == "## \u05db\u05d9\u05e1\u05d5\u05d9\u05d9\u05dd \u05de\u05d9\u05d5\u05d7\u05d3\u05d9\u05dd"


def test_anchor_falls_back_to_first_80_chars_without_heading():
    md = "Some text without a heading prefix, just raw content here."
    chunks = chunk_section_aware(md, "policy.pdf", "pol1")
    assert chunks[0]["anchor"] == md[:80]


def test_table_rows_split_into_separate_chunks():
    md = "## \u05ea\u05e2\u05e8\u05d9\u05e4\u05d9\u05dd\n| \u05e9\u05d9\u05e8\u05d5\u05ea | \u05de\u05d7\u05d9\u05e8 |\n|---|---|\n| \u05d2\u05e8\u05d9\u05e8\u05d4 | 500 |\n| \u05d6\u05db\u05d5\u05db\u05d9\u05ea | 300 |"
    chunks = chunk_section_aware(md, "policy.pdf", "pol1")
    assert len(chunks) == 3  # heading chunk + two data row chunks
    assert "\u05d2\u05e8\u05d9\u05e8\u05d4" in chunks[1]["text"]
    assert "\u05d6\u05db\u05d5\u05db\u05d9\u05ea" in chunks[2]["text"]
    # Each chunk includes the header row
    assert "\u05e9\u05d9\u05e8\u05d5\u05ea" in chunks[1]["text"]
    assert "\u05e9\u05d9\u05e8\u05d5\u05ea" in chunks[2]["text"]


def test_table_with_preceding_text_creates_text_plus_row_chunks():
    md = "## \u05e1\u05e7\u05d9\u05e8\u05d4\n\u05ea\u05d5\u05db\u05df \u05db\u05dc\u05dc\u05d9 \u05e2\u05dc \u05d4\u05e4\u05d5\u05dc\u05d9\u05e1\u05d4\n| \u05e1\u05d5\u05d2 | \u05e2\u05e8\u05da |\n|---|---|\n| \u05d7\u05d9\u05d9\u05dd | 100 |"
    chunks = chunk_section_aware(md, "p.pdf", "p1")
    # non-table text chunk + 1 data row chunk = 2 chunks
    assert len(chunks) == 2
    assert "\u05ea\u05d5\u05db\u05df \u05db\u05dc\u05dc\u05d9" in chunks[0]["text"]
    assert "\u05d7\u05d9\u05d9\u05dd" in chunks[1]["text"]
    assert "\u05e1\u05d5\u05d2" in chunks[1]["text"]  # header row included
