# Insurance Policy RAG — Architecture & Implementation

> Technical reference for the insurance-policy Retrieval-Augmented Generation
> feature inside **ai-wealth-monitor**. Describes what was built, how each
> component works, the data model, the retrieval algorithm, and the evaluation
> results that justify the design choices.

---

## 1. What it does

The family-wealth app lets users upload their real insurance policy PDFs
(car, home, health, life). The RAG feature makes those policies *queryable in
natural language* from the chat copilot:

- **At upload time** the PDF is stripped of PII, converted to clean Markdown by
  Gemini, split into semantically-meaningful chunks, embedded, and stored in
  Firestore under the family.
- **At query time**, when the user asks a contractual question (coverage,
  exclusions, premiums, conditions), Gemini autonomously calls a
  `query_insurance_policy` tool that runs hybrid retrieval over the indexed
  chunks and feeds the most relevant excerpts back into the answer.

The user never sees the machinery — they just ask *"מה הכיסוי לגרירה?"* and get
a grounded answer citing the right section of their own policy.

---

## 2. End-to-end architecture

```
┌─────────────────────────── INDEXING (on PDF upload) ───────────────────────────┐
│                                                                                 │
│  PDF bytes                                                                      │
│     │                                                                           │
│     ▼                                                                           │
│  redact_pdf_bytes()      ── PyMuPDF apply_redactions: physically removes PII    │
│     │                       text from the PDF layer (not a visual blackout)     │
│     ▼                                                                           │
│  extract_markdown_via_gemini()  ── Gemini native-PDF → Markdown (## headings,   │
│     │                              Hebrew preserved, tables kept as Markdown)   │
│     ▼                                                                           │
│  chunk_section_aware()   ── split on `## ` headings; tables split row-by-row    │
│     │                                                                           │
│     ▼                                                                           │
│  embed_documents()       ── gemini-embedding-001, RETRIEVAL_DOCUMENT, 768-d     │
│     │                                                                           │
│     ▼                                                                           │
│  save_policy_chunks()    ── Firestore: families/{uid}/insurance_chunks/{id}     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── QUERY (on chat question) ───────────────────────────┐
│                                                                                 │
│  User question  ──►  Gemini (copilot_chat_ask) decides to call the tool         │
│                          │                                                      │
│                          ▼                                                      │
│              _query_insurance_policy(query, uid)                                │
│                          │                                                      │
│        ┌─────────────────┼─────────────────┐                                    │
│        ▼                 ▼                                                       │
│  get_insurance_chunks()  embed_query()  ── gemini-embedding-001,                │
│   (load all chunks)        │                RETRIEVAL_QUERY, 768-d              │
│        │                   ▼                                                     │
│        │            cosine_top_k() ─┐                                            │
│        │            bm25_top_k()  ──┤── rrf_merge()  ── Reciprocal Rank Fusion   │
│        │                            │                                            │
│        ▼                            ▼                                            │
│  top-k excerpts (formatted with מקור/סעיף labels)                               │
│        │                                                                        │
│        ▼                                                                        │
│  Gemini composes the final grounded Hebrew answer                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component reference

All RAG helpers live in `backend/rag_utils.py`. Every network-calling function
accepts an optional `client=` kwarg so tests can inject a fake Gemini client.

### 3.1 PII redaction — `redact_pdf_bytes(pdf_bytes, pii_targets) -> bytes`

Uses PyMuPDF (`fitz`). For each PII target string, finds its rectangles on every
page, adds a redaction annotation, then calls `apply_redactions()` which
**physically deletes the underlying text**, not just paints over it. Targets
shorter than 2 characters are skipped to avoid catastrophic over-redaction
(e.g. redacting every "א").

> The `pii_targets` come from the existing extraction flow — the same PII the
> app already detects for the structured-data pipeline is reused here.

### 3.2 Markdown extraction — `extract_markdown_via_gemini(pdf_bytes) -> str`

Sends the redacted PDF inline to Gemini (`Part.from_bytes(..., mime_type="application/pdf")`)
with a prompt instructing it to:

- preserve the original language exactly (Hebrew — no translation/transliteration),
- use `## ` level-2 Markdown headings per section,
- keep tables as Markdown tables,
- output Markdown only (no preamble or code fences).

**Why Gemini and not PyMuPDF text extraction?** PyMuPDF mangles right-to-left
Hebrew text order. Gemini's native-PDF understanding reconstructs the reading
order and the table structure correctly.

### 3.3 Chunking — `chunk_section_aware(text, source_doc, policy_id) -> list[dict]`

Two-level strategy:

1. **Section split** — `re.split(r"\n(?=## )", text)` breaks the document on
   each `## ` heading, so each chunk corresponds to one logical policy section.
2. **Table-aware split** — within each section, `_split_table_rows()` detects
   Markdown tables and emits **one chunk per data row**, with the header row
   prepended for context. Non-table prose is kept together (and fixed-split with
   10 % overlap if it exceeds `SECTION_MAX_CHARS = 2800`, ≈ 700 tokens).

Each chunk is a dict:

```python
{
    "chunk_id":   "{policy_id}_{idx}",   # valid Firestore document id
    "text":       "<raw chunk text>",    # no embedding prefixes
    "anchor":     "## Section heading",  # the heading line, or text[:80] fallback
    "source_doc": "car_policy.pdf",
    "policy_id":  "car_policy",
}
```

**Why table-aware?** Policies pack the answers users actually ask about
(premiums, coverage sums, phone numbers, dates) into tables. If a whole tariff
table is one chunk, a query like *"מהי הפרמיה לגרירה?"* retrieves the entire
table and the model often picks the wrong row. Splitting each row into its own
chunk — `header + row` — makes the exact row directly retrievable. This was the
single largest source of wrong answers in evaluation (see §7).

**Robustness (hardened in PR #17 review):**

- `_is_table_start(lines, i)` — a table begins only where a `|`-row is followed
  by another `|`-row. The non-table collector uses the *same* predicate, which
  guarantees forward progress: a lone `|`-prefixed line (a malformed one-row
  table, or a table immediately followed by prose) is consumed as text rather
  than triggering an infinite loop.
- `_is_separator_row(line)` — only a genuine separator (`|---|`, `|:--:|`, every
  cell matching `:?-+:?`) is skipped. A real data row such as `| 1 | 2 |` is
  **never** mistaken for a separator, so a table that lacks a separator line no
  longer silently drops its first data row.

### 3.4 Embeddings — `embed_documents()` / `embed_query()`

Both call `gemini-embedding-001` with `output_dimensionality=768`.

- Documents use `task_type="RETRIEVAL_DOCUMENT"`.
- Queries use `task_type="RETRIEVAL_QUERY"`.

No `passage:` / `query:` text prefixes are used — the Gemini embedding API
distinguishes document vs. query intent through `task_type`, unlike the e5
family which needs literal text prefixes.

### 3.5 Retrieval — hybrid dense + lexical, fused with RRF

`_query_insurance_policy(query, uid, k=5)` in `backend/routers/dashboard_chat.py`
orchestrates three steps:

```python
query_vec      = embed_query(query)
embeddings     = [c["embedding"] for c in chunks]
cosine_results = cosine_top_k(query_vec, embeddings, len(chunks))   # dense / semantic
bm25_results   = bm25_top_k(query, chunks, len(chunks))            # lexical / exact
top            = rrf_merge(cosine_results, bm25_results, k=k)       # fusion
```

**`cosine_top_k(query, vectors, k)`** — numpy cosine similarity over all chunk
vectors, returns `[(index, similarity), ...]` sorted descending. In-process, no
vector DB.

**`bm25_top_k(query, chunks, k)`** — BM25Okapi (`rank-bm25`) over chunk text.
Strong for *exact* matches the dense model blurs — specific numbers, policy
numbers, phone numbers, named coverages. Tokenization is via `_tokenize()`,
which splits on whitespace **and Markdown pipes** so `|` delimiters don't
pollute term frequencies.

**`rrf_merge(cosine_results, bm25_results, k, rrf_k=60)`** — Reciprocal Rank
Fusion. Each chunk's fused score is the sum over both rankers of
`1 / (rrf_k + rank)`. RRF combines the two signals without needing to calibrate
cosine scores against BM25 scores (which live on totally different scales) — it
only uses *ranks*. A chunk that ranks highly in *both* lists wins. `rrf_k = 60`
is the canonical constant from the original RRF paper.

> **Why hybrid?** Dense retrieval understands paraphrase and synonymy
> (*"נזק לרכב"* ≈ *"תאונה"*); lexical BM25 nails verbatim tokens (an exact ₪
> figure or a coverage name). Each covers the other's blind spot.

### 3.6 Answer generation & prompt design

The retrieved excerpts are formatted with explicit Hebrew labels so the model
understands provenance and hierarchy:

```
[1] מקור: car_policy.pdf | סעיף: ## פרק ב — כיסוי גניבה
<chunk text…>

---

[2] מקור: car_policy.pdf | סעיף: ## תעריפים
| שירות | מחיר |
| גרירה | 1,200 |
```

The copilot system prompt instructs Gemini to use the tool for contractual
questions, and includes a **refusal instruction**:

> *"אם הפרגמנטים שהחזיר הכלי לא עונים במפורש על השאלה — ענה 'לא מצאתי מידע מפורש
> בפוליסה על כך' במקום לנחש."*

This converts would-be hallucinations into honest "not found" answers.

---

## 4. Data model (Firestore)

```
families/{uid}/insurance_chunks/{chunk_id}
    text:        string        # raw chunk text
    anchor:      string        # section heading (citation key)
    embedding:   [768 floats]  # gemini-embedding-001
    policy_id:   string        # groups chunks of one policy
    source_doc:  string        # original filename
```

- **`save_policy_chunks(uid, policy_id, chunks)`** — first deletes existing docs
  with the same `policy_id` (idempotent re-upload), then writes each chunk.
- **`get_insurance_chunks(uid)`** — streams every chunk for the family. Returns
  `[]` when Firestore is unavailable (graceful degradation).

No separate vector database: at the few-policies-per-family scale, loading the
chunks and running numpy cosine + BM25 in-process is simpler and adds no infra.

---

## 5. Upload-flow integration

In `backend/document_flows.py`, after the existing Claude-based structured
extraction, a **best-effort** block runs the RAG indexing pipeline:

```python
try:
    policy_id = self.target_policy_id or slug_from_filename(filename)
    redacted_bytes = redact_pdf_bytes(file_bytes, pii_targets)
    markdown = extract_markdown_via_gemini(redacted_bytes)
    chunks = chunk_section_aware(markdown, source_doc=filename, policy_id=policy_id)
    if chunks:
        embeddings = embed_documents([c["text"] for c in chunks])
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb
        save_policy_chunks(uid, policy_id, chunks)
except Exception as rag_err:
    print(f"⚠️ [INSURANCE-FLOW] RAG indexing skipped (non-fatal): {rag_err}")
```

The `try/except` ensures a RAG failure **never breaks** the primary extraction
flow that the rest of the app depends on. `policy_id` is the explicit
`target_policy_id` when present, otherwise a slug of the filename stem
(`"my policy 2024.pdf"` → `"my_policy_2024"`).

---

## 6. Architecture decisions

| Decision            | Choice                          | Reason |
|---------------------|---------------------------------|--------|
| Vector storage      | Firestore subcollection         | Already in stack; no new infra |
| Embeddings          | `gemini-embedding-001` @ 768-d  | Lab ablation: comparable to e5, 0 hallucinations |
| Embedding prefixes  | None (`task_type` instead)      | Gemini API uses task_type, not text prefixes |
| Similarity          | numpy cosine in-process         | No ChromaDB/Pinecone needed at this scale |
| Lexical retrieval   | BM25 (`rank-bm25`)              | Pure-Python, zero per-query API cost |
| Fusion              | Reciprocal Rank Fusion (k=60)   | Scale-free; no score calibration needed |
| Chunking            | Section-aware + table-row split | Tables hold the facts users ask about |
| Hebrew extraction   | Gemini native-PDF               | PyMuPDF mangles RTL text |
| PII removal         | PyMuPDF `apply_redactions`      | Physically strips text, not visual blackout |
| RAG error handling  | Non-fatal `try/except`          | Never break the existing extraction flow |

---

## 7. Evaluation

Measured in the companion lab project (`insurance-rag`) on a 75-question gold
set across the four policy types, using an LLM-as-judge
(Correct / Partially / Incorrect / Hallucinated). The production app uses the
**Gemini-embedding** configuration:

| Label         | Count | %   |
|---------------|-------|-----|
| Correct       | 45    | 60% |
| Partially     | 15    | 20% |
| Incorrect     | 15    | 20% |
| Hallucinated  | 0     | 0%  |
| **Correct + Partially** | **60 / 75** | **80%** |

By source document:

| Document       | Questions | Correct + Partially |
|----------------|-----------|---------------------|
| car_policy     | 15        | 67% |
| car_policy1    | 20        | 95% |
| health_policy  | 25        | 88% |
| home_policy    | 15        | 60% |

**Failure analysis.** Almost every wrong answer was a *table row lookup* — a
specific premium, coverage sum, date, or phone number. This finding directly
motivated table-aware chunking (§3.3) and BM25 hybrid retrieval (§3.5), which
target exactly that failure class. The prompt/labeling and refusal changes
(§3.6) additionally drove hallucinations to zero.

> The 60% / 80% numbers are the **pre-improvement baseline**. Table-aware
> chunking, BM25 hybrid retrieval, and the prompt changes were introduced
> afterward (PR #17) and are expected to lift Correct toward ~75–80%; a fresh
> end-to-end re-measure on the production app is the natural next validation
> step.

---

## 8. Testing

RAG tests run from `backend/`:

```
python -m pytest tests/ -q
```

| File                                   | Covers |
|----------------------------------------|--------|
| `tests/test_rag_utils.py`              | chunking, table-row split, separator validation, infinite-loop guards, `cosine_top_k`, `bm25_top_k`, `rrf_merge`, `_tokenize`, redaction, Gemini PDF extraction |
| `tests/test_db_chunks.py`              | save/get chunks, dedup on re-upload, `db=None` degradation |
| `tests/test_insurance_flow_rag.py`     | pipeline called in correct order, filename slug, non-fatal failure |
| `tests/test_dashboard_chat_rag.py`     | hybrid retrieval output, uid passed correctly, empty state, source/heading labels, refusal instruction in prompt |

Notable regression tests added during the PR #17 review:

- `test_lone_pipe_line_does_not_hang_and_is_kept_as_text` — proves the table
  parser cannot infinite-loop on a malformed single-row table.
- `test_table_without_separator_keeps_first_data_row` — proves a separator-less
  table does not lose its first data row.
- `test_is_separator_row_distinguishes_separator_from_data` — validates the
  separator predicate.
- `test_bm25_top_k_*` / `test_rrf_merge_*` — unit-cover the hybrid retrieval math.

---

## 9. Known limitations & future work

- **Scale.** All chunks are loaded into memory per query, and BM25 rebuilds its
  index on every call. Fine for a handful of policies per family; a family with
  many large policies would need server-side filtering (e.g. by `policy_id`) or
  a persistent index.
- **Hebrew lexical matching.** `_tokenize` strips table pipes but does not strip
  Hebrew prefixes (ב/ה/ל/מ/ו). *"לגרירה"* will not BM25-match *"גרירה"*. A
  light stemmer or prefix-stripping would tighten exact-match recall.
- **Re-indexing.** Indexing only happens on upload; there is no UI trigger to
  re-index an existing policy.
- **policy_id on rename.** If `target_policy_id` is absent and the user renames
  the file, the filename-slug differs and a duplicate set of chunks is created.
- **Indexing feedback.** The user is not told how many chunks were indexed or
  whether indexing failed (it is silent and non-fatal by design).
- **Demo user.** `DEMO_UID` returns canned chat responses before the RAG tool is
  registered — intentional for the showcase, but it means RAG cannot be
  exercised through the demo account.

---

## 10. File map

| File | Role |
|------|------|
| `backend/rag_utils.py` | Chunking, embeddings, cosine/BM25/RRF retrieval, PII redaction, Gemini PDF extraction |
| `backend/db_manager.py` | `save_policy_chunks`, `get_insurance_chunks` (Firestore) |
| `backend/document_flows.py` | Wires RAG indexing into the PDF upload flow (non-fatal) |
| `backend/routers/dashboard_chat.py` | `_query_insurance_policy` tool + copilot system prompt |
| `backend/requirements.txt` | Adds `numpy`, `rank-bm25` |
| `backend/tests/test_rag_*.py`, `test_dashboard_chat_rag.py`, `test_db_chunks.py` | Test suite |
