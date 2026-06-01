# Task: Improve Insurance RAG Accuracy in ai-wealth-monitor

## Project

`D:\AICode\ai-wealth-monitor` — FastAPI backend, React frontend, family wealth app.
Tests run from `backend/` directory: `python -m pytest tests/ -q`
Work on a new feature branch (never commit to main/master).

---

## Background

The app has an insurance RAG pipeline (already implemented and integrated):

1. User uploads a PDF policy → redacted → Gemini PDF extraction → section_aware chunking → gemini-embedding-001 embeddings → stored in Firestore subcollection
2. When the user asks a contractual question in chat → Gemini calls `query_insurance_policy` tool → cosine similarity retrieval → top-5 chunks returned as context

Evaluation on 75 gold questions showed: **60% Correct, 17% Partially, 17% Incorrect, 4% Hallucinated**.
Root-cause analysis identified 3 cheap fixes (prompt-only, zero cost) and 2 medium fixes.

---

## Phase 1 — Prompt Fixes (zero API cost, ~1.5h)

### Fix 1 — Better context format in `_query_insurance_policy`

**File:** `backend/routers/dashboard_chat.py`

Find the `_query_insurance_policy` function. Replace the lines that build `lines` (inside the for loop over `top`) with:

```python
    lines = []
    for rank, (idx, score) in enumerate(top, 1):
        c = chunks[idx]
        # Extract section heading for model context
        text = c["text"]
        heading = text.split("\n")[0] if text.startswith("## ") else c.get("anchor", text[:60])
        lines.append(
            f"[{rank}] מקור: {c['source_doc']} | סעיף: {heading}\n{text}"
        )
```

### Fix 2 — Refusal instruction in system prompt

**File:** `backend/routers/dashboard_chat.py`

Find `system_prompt = f"""You are an expert family wealth advisor...`
Add this sentence at the end of the system prompt (before the closing `"""`):

```
If the `query_insurance_policy` tool returns excerpts that do not explicitly answer the question, respond with "לא מצאתי מידע מפורש בפוליסה על כך" instead of guessing or extrapolating.
```

### Fix 3 — Better anchor in chunk construction

**File:** `backend/rag_utils.py`

Find the `_make_chunk` function. Replace it with:

```python
def _make_chunk(text: str, source_doc: str, policy_id: str, idx: int) -> dict:
    heading_line = text.split("\n")[0] if text.startswith("## ") else ""
    return {
        "chunk_id": f"{policy_id}_{idx}",
        "text": text,
        "anchor": heading_line or text[:80],
        "source_doc": source_doc,
        "policy_id": policy_id,
    }
```

---

## Phase 2 — Table-aware Chunking + BM25 Hybrid (~2 days)

### Fix 4 — Table-aware chunking

**File:** `backend/rag_utils.py`

**Context:** Section-aware chunking keeps entire Markdown tables as one chunk. This breaks retrieval for row-level questions (e.g. "מהי הפרמיה לגרירה?"). Solution: detect Markdown tables within a section and split each data row into its own chunk, prepending the header row as context.

Add a helper and replace `chunk_section_aware`:

```python
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
```

### Fix 5 — BM25 hybrid retrieval with RRF

**Files:** `backend/requirements.txt`, `backend/rag_utils.py`, `backend/routers/dashboard_chat.py`

**Step 1** — Add to `requirements.txt`:

```
rank-bm25>=0.2.2
```

**Step 2** — Add to `rag_utils.py`:

```python
def bm25_top_k(query: str, chunks: list[dict], k: int) -> list[tuple[int, float]]:
    """BM25 retrieval over chunk texts. Good for exact-match (numbers, names)."""
    from rank_bm25 import BM25Okapi  # lazy import — optional dependency
    tokenized = [c["text"].split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.split())
    order = list(reversed(sorted(range(len(scores)), key=lambda i: scores[i])))[:k]
    return [(i, float(scores[i])) for i in order]


def rrf_merge(
    cosine_results: list[tuple[int, float]],
    bm25_results: list[tuple[int, float]],
    k: int = 5,
    rrf_k: int = 60,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion — merges two ranked lists."""
    scores: dict[int, float] = {}
    for rank, (idx, _) in enumerate(cosine_results, 1):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (rrf_k + rank)
    for rank, (idx, _) in enumerate(bm25_results, 1):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (rrf_k + rank)
    top = sorted(scores.items(), key=lambda x: -x[1])[:k]
    return top
```

**Step 3** — Update `_query_insurance_policy` in `dashboard_chat.py` to use hybrid retrieval:

```python
from rag_utils import embed_query, cosine_top_k, bm25_top_k, rrf_merge

def _query_insurance_policy(query: str, uid: str, k: int = 5) -> str:
    chunks = get_insurance_chunks(uid)
    if not chunks:
        return "No insurance policies have been indexed for this family yet."
    chunks = [c for c in chunks if c.get("embedding")]
    if not chunks:
        return "No insurance policies have been indexed for this family yet."

    query_vec = embed_query(query)
    embeddings = [c["embedding"] for c in chunks]

    cosine_results = cosine_top_k(query_vec, embeddings, k * 2)
    bm25_results   = bm25_top_k(query, chunks, k * 2)
    top            = rrf_merge(cosine_results, bm25_results, k=k)

    if not top:
        return "No relevant passages found."
    lines = []
    for rank, (idx, score) in enumerate(top, 1):
        c = chunks[idx]
        text = c["text"]
        heading = text.split("\n")[0] if text.startswith("## ") else c.get("anchor", text[:60])
        lines.append(f"[{rank}] מקור: {c['source_doc']} | סעיף: {heading}\n{text}")
    return "\n\n---\n\n".join(lines)
```

---

## Tests to Write / Update

For each change, update or add tests in:

- `backend/tests/test_rag_utils.py` — add tests for `_split_table_rows`, `bm25_top_k`, `rrf_merge`
- `backend/tests/test_dashboard_chat_rag.py` — verify new context format includes section heading and source

### Example — table chunking test

```python
def test_table_rows_split_into_separate_chunks():
    md = "## תעריפים\n| שירות | מחיר |\n|---|---|\n| גרירה | 500 |\n| זכוכית | 300 |"
    chunks = chunk_section_aware(md, "policy.pdf", "pol1")
    assert len(chunks) == 2  # one chunk per data row
    assert "גרירה" in chunks[0]["text"]
    assert "זכוכית" in chunks[1]["text"]
    # Each chunk includes the header row
    assert "שירות" in chunks[0]["text"]
    assert "שירות" in chunks[1]["text"]
```

### Example — anchor uses heading

```python
def test_anchor_uses_section_heading():
    md = "## כיסויים מיוחדים\nתוכן הסעיף כאן."
    chunks = chunk_section_aware(md, "policy.pdf", "pol1")
    assert chunks[0]["anchor"] == "## כיסויים מיוחדים"
```

### Example — refusal format in retrieval output

```python
def test_query_result_includes_source_and_heading(monkeypatch):
    fake_chunks = [{
        "embedding": [0.1] * 768,
        "text": "## כיסוי גניבה\nמכסה גניבה מלאה.",
        "anchor": "## כיסוי גניבה",
        "source_doc": "car_policy.pdf",
    }]
    monkeypatch.setattr("dashboard_chat.get_insurance_chunks", lambda uid: fake_chunks)
    monkeypatch.setattr("dashboard_chat.embed_query", lambda q, **kw: [0.1] * 768)
    result = _query_insurance_policy("כיסוי גניבה", "uid123")
    assert "מקור: car_policy.pdf" in result
    assert "סעיף: ## כיסוי גניבה" in result
```

After all changes: run `python -m pytest tests/ -q` from `backend/` — all tests must pass.

---

## Expected Impact

| Stage | Correct | Partially | Incorrect | Hallucinated |
|---|---|---|---|---|
| Baseline (current) | 60% | 17% | 17% | 4% |
| After Phase 1 | ~67% | ~15% | ~15% | ~0% |
| After Phase 1+2 | ~75–80% | ~10% | ~10% | ~0% |

---

## Git Workflow

- Branch: `feat/rag-accuracy-improvements`
- Commit Phase 1 separately from Phase 2 (two logical commits)
- Do **NOT** merge to main — open a PR and stop

---

## Security Constraints (never violate)

- Never open `.env` files (any variant)
- Never read `D:\AICode\insurance-rag\data\known_pii.json` or `data\raw\` — real PII
- Never commit or push to `main`/`master`
- Never merge a PR without explicit user approval
