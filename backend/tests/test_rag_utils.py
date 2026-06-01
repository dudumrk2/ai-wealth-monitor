"""Unit tests for rag_utils — insurance policy RAG helpers."""
from unittest.mock import MagicMock

import fitz
import pytest

from rag_utils import (
    EMBED_MODEL,
    EMBED_OUTPUT_DIM,
    SECTION_MAX_CHARS,
    _is_separator_row,
    _tokenize,
    bm25_top_k,
    chunk_section_aware,
    cosine_top_k,
    embed_documents,
    embed_query,
    extract_markdown_via_gemini,
    redact_pdf_bytes,
    rrf_merge,
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


# ---------------------------------------------------------------------------
# Regression: table parser must never hang or drop data (PR #17 review fixes)
# ---------------------------------------------------------------------------


def test_lone_pipe_line_does_not_hang_and_is_kept_as_text():
    """A ``|``-line not followed by another ``|``-row must be treated as text.

    Before the fix this caused an infinite loop (i never advanced). The chunk
    must still be produced so no content is lost.
    """
    # Single pseudo-table line at the very end of the section.
    md = "## \u05d4\u05e2\u05e8\u05d4\n| \u05e9\u05d9\u05e8\u05d5\u05ea: \u05d2\u05e8\u05d9\u05e8\u05d4 - 500"
    chunks = chunk_section_aware(md, "p.pdf", "p1")
    assert len(chunks) == 1
    assert "\u05d2\u05e8\u05d9\u05e8\u05d4" in chunks[0]["text"]


def test_pipe_line_followed_by_prose_does_not_hang():
    """A ``|``-line followed by a non-table line must not loop forever."""
    md = "| \u05dc\u05d0 \u05d8\u05d1\u05dc\u05d4\n\u05e4\u05e1\u05e7\u05d4 \u05e8\u05d2\u05d9\u05dc\u05d4 \u05db\u05d0\u05df"
    chunks = chunk_section_aware(md, "p.pdf", "p1")
    # Both lines collapse into one text chunk; importantly the call returns.
    assert len(chunks) == 1
    assert "\u05e4\u05e1\u05e7\u05d4 \u05e8\u05d2\u05d9\u05dc\u05d4" in chunks[0]["text"]


def test_table_without_separator_keeps_first_data_row():
    """A table lacking a ``|---|`` separator must not drop its first data row."""
    md = "## \u05ea\u05e2\u05e8\u05d9\u05e4\u05d9\u05dd\n| \u05e9\u05d9\u05e8\u05d5\u05ea | \u05de\u05d7\u05d9\u05e8 |\n| \u05d2\u05e8\u05d9\u05e8\u05d4 | 500 |\n| \u05d6\u05db\u05d5\u05db\u05d9\u05ea | 300 |"
    chunks = chunk_section_aware(md, "p.pdf", "p1")
    # heading + two data rows (no separator row to skip)
    assert len(chunks) == 3
    assert "\u05d2\u05e8\u05d9\u05e8\u05d4" in chunks[1]["text"]  # first data row preserved
    assert "\u05d6\u05db\u05d5\u05db\u05d9\u05ea" in chunks[2]["text"]


def test_is_separator_row_distinguishes_separator_from_data():
    assert _is_separator_row("|---|---|")
    assert _is_separator_row("| :--- | ---: |")
    assert _is_separator_row("|:-:|:-:|")
    assert not _is_separator_row("| 1 | 2 |")
    assert not _is_separator_row("| \u05d2\u05e8\u05d9\u05e8\u05d4 | 500 |")
    assert not _is_separator_row("")


# ---------------------------------------------------------------------------
# BM25 + RRF hybrid retrieval helpers
# ---------------------------------------------------------------------------


def test_tokenize_strips_table_pipes():
    assert _tokenize("| \u05d2\u05e8\u05d9\u05e8\u05d4 | 500 |") == ["\u05d2\u05e8\u05d9\u05e8\u05d4", "500"]
    assert _tokenize("plain text here") == ["plain", "text", "here"]


def test_bm25_top_k_ranks_exact_match_first():
    chunks = [
        {"text": "\u05db\u05d9\u05e1\u05d5\u05d9 \u05e0\u05d6\u05e7\u05d9 \u05e6\u05d3 \u05e9\u05dc\u05d9\u05e9\u05d9"},
        {"text": "\u05e4\u05e8\u05de\u05d9\u05d4 \u05e9\u05e0\u05ea\u05d9\u05ea \u05d2\u05e8\u05d9\u05e8\u05d4 1200"},
        {"text": "\u05ea\u05e0\u05d0\u05d9\u05dd \u05db\u05dc\u05dc\u05d9\u05d9\u05dd"},
    ]
    results = bm25_top_k("\u05d2\u05e8\u05d9\u05e8\u05d4", chunks, k=3)
    assert len(results) == 3
    # The chunk literally containing the query term ranks first.
    assert results[0][0] == 1


def test_bm25_top_k_empty_chunks_returns_empty():
    assert bm25_top_k("anything", [], k=5) == []


def test_rrf_merge_rewards_agreement_between_rankers():
    # Index 2 is top of both lists -> should win after fusion.
    cosine = [(2, 0.9), (0, 0.8), (1, 0.1)]
    bm25 = [(2, 5.0), (1, 4.0), (0, 0.2)]
    merged = rrf_merge(cosine, bm25, k=3)
    assert merged[0][0] == 2
    assert {idx for idx, _ in merged} == {0, 1, 2}


def test_rrf_merge_respects_k_limit():
    cosine = [(0, 0.9), (1, 0.8), (2, 0.7), (3, 0.6)]
    bm25 = [(3, 5.0), (2, 4.0), (1, 3.0), (0, 2.0)]
    merged = rrf_merge(cosine, bm25, k=2)
    assert len(merged) == 2
