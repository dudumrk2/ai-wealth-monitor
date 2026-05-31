"""Insurance policy RAG helpers — chunking, embedding, retrieval."""
from __future__ import annotations

import os
import re

import fitz
import numpy as np
from google import genai
from google.genai import types

import config


SECTION_MAX_CHARS = 2800  # ~700 tokens at ~4 chars/token (matches insurance-rag baseline)
_SUB_OVERLAP = SECTION_MAX_CHARS // 10

EMBED_MODEL = "gemini-embedding-001"
EMBED_OUTPUT_DIM = 768

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client


def _make_chunk(text: str, source_doc: str, policy_id: str, idx: int) -> dict:
    heading_line = text.split("\n")[0] if text.startswith("## ") else ""
    return {
        "chunk_id": f"{policy_id}_{idx}",
        "text": text,
        "anchor": heading_line or text[:80],
        "source_doc": source_doc,
        "policy_id": policy_id,
    }


def _fixed_split(text: str, size: int, overlap: int) -> list[str]:
    stride = max(1, size - overlap)
    out: list[str] = []
    start = 0
    while start < len(text):
        out.append(text[start : start + size])
        start += stride
    return out


def _split_table_rows(
    section_text: str, source_doc: str, policy_id: str, start_idx: int
) -> tuple[list[dict], int]:
    """Split any Markdown table within section_text into per-row chunks.

    Non-table lines are returned as a single chunk.
    Returns (chunks, next_idx).
    """
    lines = section_text.split("\n")
    chunks: list[dict] = []
    idx = start_idx
    i = 0

    while i < len(lines):
        # Detect table start: line matches | ... |
        if lines[i].startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            header_row = lines[i]
            separator = lines[i + 1] if lines[i + 1].lstrip().startswith("|") else ""
            i += 2 if separator else 1
            # Collect data rows
            while i < len(lines) and lines[i].startswith("|"):
                row = lines[i]
                # One chunk per data row: header + row
                chunk_text = f"{header_row}\n{row}"
                chunks.append(_make_chunk(chunk_text, source_doc, policy_id, idx))
                idx += 1
                i += 1
        else:
            # Collect non-table lines until next table
            non_table: list[str] = []
            while i < len(lines) and not lines[i].startswith("|"):
                non_table.append(lines[i])
                i += 1
            text = "\n".join(non_table).strip()
            if text:
                if len(text) <= SECTION_MAX_CHARS:
                    chunks.append(_make_chunk(text, source_doc, policy_id, idx))
                    idx += 1
                else:
                    for sub in _fixed_split(text, SECTION_MAX_CHARS, _SUB_OVERLAP):
                        chunks.append(_make_chunk(sub, source_doc, policy_id, idx))
                        idx += 1

    return chunks, idx


def chunk_section_aware(text: str, source_doc: str, policy_id: str) -> list[dict]:
    """Split Markdown on ## headings; table rows become individual chunks."""
    if not text:
        return []

    parts = re.split(r"\n(?=## )", text)
    chunks: list[dict] = []
    idx = 0
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        new_chunks, idx = _split_table_rows(stripped, source_doc, policy_id, idx)
        chunks.extend(new_chunks)
    return chunks


def cosine_top_k(
    query: list[float], chunk_vectors: list[list[float]], k: int
) -> list[tuple[int, float]]:
    """Return the top-k chunk indices sorted by descending cosine similarity."""
    if not chunk_vectors:
        return []

    q = np.asarray(query, dtype=np.float32)
    matrix = np.asarray(chunk_vectors, dtype=np.float32)

    q_norm = float(np.linalg.norm(q)) or 1.0
    m_norms = np.linalg.norm(matrix, axis=1)
    m_norms = np.where(m_norms == 0, 1.0, m_norms)
    sims = (matrix @ q) / (m_norms * q_norm)

    order = np.argsort(-sims)[: max(0, k)]
    return [(int(i), float(sims[i])) for i in order]


_EXTRACT_PROMPT = (
    "Convert this PDF policy document to clean Markdown.\n"
    "- Preserve the original language exactly. Most policies are in Hebrew; "
    "do NOT translate or transliterate.\n"
    "- Use `## ` (Markdown level-2 headings) for each section heading.\n"
    "- Preserve tables as Markdown tables.\n"
    "- Output Markdown only. No preamble, no commentary, no code fences."
)


def extract_markdown_via_gemini(pdf_bytes: bytes, *, client=None) -> str:
    """Send the PDF inline to Gemini native-PDF and return structured Markdown."""
    c = client or _get_client()
    pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = c.models.generate_content(
        model=config.GEMINI_MODEL_NAME,
        contents=[pdf_part, _EXTRACT_PROMPT],
    )
    return resp.text


def embed_documents(texts: list[str], *, client=None) -> list[list[float]]:
    """Embed chunk texts with gemini-embedding-001 (RETRIEVAL_DOCUMENT, 768d)."""
    c = client or _get_client()
    resp = c.models.embed_content(
        model=EMBED_MODEL,
        contents=list(texts),
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_OUTPUT_DIM,
        ),
    )
    return [list(e.values) for e in resp.embeddings]


def embed_query(query: str, *, client=None) -> list[float]:
    """Embed a single query with gemini-embedding-001 (RETRIEVAL_QUERY, 768d)."""
    c = client or _get_client()
    resp = c.models.embed_content(
        model=EMBED_MODEL,
        contents=[query],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBED_OUTPUT_DIM,
        ),
    )
    return list(resp.embeddings[0].values)


def redact_pdf_bytes(pdf_bytes: bytes, pii_targets: list[str]) -> bytes:
    """Physically remove PII text from a PDF (apply_redactions strips the text layer).

    Targets shorter than 2 chars are skipped to avoid catastrophic over-redaction.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            for target in pii_targets:
                if not target or len(target.strip()) < 2:
                    continue
                for rect in page.search_for(target):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()
        return doc.tobytes()
    finally:
        doc.close()
