# Plan: Table-Preserving Scraper and Content-Aware Summarizer

Owner: rsrch
Status: Proposed (MVP scope)  
Goal: Preserve important tables in scraped content and ensure summaries include small tables verbatim and compress large ones with maintained numeric fidelity.

---

## 1) Objectives
- Ensure HTML tables survive scraping (primary path), emitted as Markdown tables.
- In the summarizer, detect Markdown tables and:
  - Keep small tables verbatim.
  - Compress large tables deterministically: keep headers, top-K salient rows, and precomputed aggregates (outside the LLM).
- Update prompts so the LLM preserves tables and avoids recomputation or reformatting.
- Add tests to guard behavior.

Non-goals (for MVP):
- OCR or image table extraction from scanned PDFs.
- Perfect handling of complex HTML tables with deep nesting/rowspan/colspan (best-effort only).

---

## 2) Current State Summary (as of repo review)
- stages/scraper.py primary path uses BeautifulSoup.get_text(), which strips HTML tables and yields plain text.
- Fallbacks (r.jina.ai, Serper) return Markdown, preserving tables.
- stages/summarizer.py performs map-reduce summarization, table-agnostic today.
- Reports are Markdown, so passing Markdown tables through is compatible.

Implication: Implementing table-aware behavior requires (a) scraper to emit Markdown with tables, (b) summarizer to detect/compact/keep tables and instruct LLM accordingly.

---

## 3) Requirements

Functional
- HTML pages scraped via the primary path should include Markdown tables (not flattened text).
- Summarizer should:
  - Detect Markdown tables reliably.
  - Preserve small tables verbatim.
  - Compress large tables using deterministic, precomputed selections and aggregates.
  - Include compression notes (e.g., rows shown, selection criteria).
- Prompts must ask the LLM to keep tables as-is and avoid recomputing numeric values.

Non-Functional
- Numeric fidelity: all aggregates and selections computed in Python, never by the LLM.
- Configurable thresholds for table size and compression parameters.
- Minimal code churn and backwards compatibility (feature flag to disable new behavior if needed).

---

## 4) Design Overview

Data flow additions
- Scraper (primary path): switch to HTML→Markdown extraction that preserves tables.
- Summarizer: preprocess content/chunks prior to prompting:
  - Identify Markdown tables.
  - Decide keep vs compress.
  - Replace in-text tables with compacted or verbatim Markdown.
  - Optionally append a short "Tables" section or leave inline.
- Prompts: add explicit instructions to preserve tables and not to recompute numbers.

Configuration
- TABLE_MAX_ROWS_VERBATIM (default: 15)
- TABLE_MAX_COLS_VERBATIM (default: 8)
- TABLE_TOPK_ROWS (default: 10)
- TABLE_SALIENCE_STRATEGY: [max-abs, variance, keyword, column_of_interest]
- FEATURE_FLAG_TABLE_AWARE_SUMMARIZATION (default: on)

---

## 5) Detailed Implementation Plan

### 5.1 Scraper: Preserve Tables (HTML→Markdown)
File: stages/scraper.py

Changes
- Modify _scrape_with_beautifulsoup to output Markdown, not flattened plain text.
- Approaches (choose one):
  1) Library-based: markdownify (preferred for speed) with options preserving table structure.
     - Pros: Quick to implement; preserves basic tables.
     - Cons: May struggle with complex colspan/rowspan.
  2) Hybrid: Extract tables with BeautifulSoup, convert each <table> to Markdown (custom function), replace them with Markdown strings in the DOM, then convert remaining HTML to Markdown.
     - Pros: Control over table formatting.
     - Cons: Slightly more code.

Proposed MVP (Hybrid)
- Implement helper: _html_table_to_markdown(table_tag) -> str
  - Parse <thead>, <tbody>, <tr>, <th>, <td>; compute column count from header row; trim whitespace; coerce inline links to Markdown.
  - Ignore nested tables for MVP; treat as text.
- Walk soup.select('table'), replace with a <pre> placeholder string containing Markdown table text.
- Convert remaining HTML to Markdown using a simple converter (library or minimal rules for headings/links/lists) so we preserve overall structure.
- Finally, restore placeholders to inline Markdown tables.

Edge cases to handle (best-effort)
- Empty cells, long cell content (truncate to reasonable length, e.g., 200 chars, adding …).
- Colspan/rowspan: duplicate values or leave as-is in separate columns; document limitation.

Logging/telemetry
- Count tables found and converted per page; include in ScrapedContent.metadata (e.g., tables_found, tables_converted).

### 5.2 Summarizer: Table-Aware Preprocessing
File: stages/summarizer.py

New helpers
- _find_markdown_tables(text: str) -> List[TableSpan]
  - Detect pipe-style Markdown tables via regex (header separator line with --- and pipes; capture start/end offsets).
  - TableSpan includes raw text, row/column counts, header row, body rows.
- _analyze_table(md_table: str) -> TableInfo
  - Parse into headers and rows (split by lines/pipes), produce numeric profile per column (numeric density, min/max/mean).
- _select_salient_rows(info: TableInfo, k: int, strategy: str, keywords: List[str]) -> List[int]
  - Strategies: max-abs by a numeric column; highest variance across numeric columns; keyword matching in any cell.
- _compute_column_aggregates(info: TableInfo) -> Dict[column, aggregates]
  - min/max/mean (rounded but never invented), top categories for categorical columns.
- _compress_markdown_table(info: TableInfo, top_row_indices: List[int]) -> str
  - Output: header + selected rows as Markdown; add a small caption/notes line:
    - e.g., "20 of 240 rows shown; selection=max by Accuracy; aggregates computed externally: Accuracy mean=91.2, max=97.8".
- _preprocess_for_tables(text: str, query: str) -> str
  - For each detected table: if rows<=TABLE_MAX_ROWS_VERBATIM and cols<=TABLE_MAX_COLS_VERBATIM -> keep verbatim; else replace with compressed Markdown from _compress_markdown_table.

Integration points
- _summarize_direct: preprocess text before building prompt.
- _summarize_map_reduce: preprocess each chunk before _summarize_chunk.

Configuration constants
- Add at top of Summarizer:
  - TABLE_MAX_ROWS_VERBATIM = 15
  - TABLE_MAX_COLS_VERBATIM = 8
  - TABLE_TOPK_ROWS = 10
  - ENABLE_TABLE_AWARE = True (feature flag)

Metadata
- Optionally annotate Summary with notes: number of tables preserved/compressed (future enhancement).

### 5.3 Prompt Updates (Summarizer)
Files: stages/summarizer.py (_build_summary_prompt, _summarize_chunk, _combine_chunk_summaries)

Add language (examples):
- "Preserve any Markdown tables verbatim as they appear. Do not reformat tables."
- "For large tables, a compacted version is provided. Use it as-is. Do not recompute totals or statistics."
- "If including a table in the output improves clarity, include it inline; otherwise, reference it briefly." 
- Keep temperature low (already 0.3) to reduce creative reformatting.

### 5.4 Config & Feature Flag
File: config.py (if present) and wiring
- Expose table thresholds and enable flag via environment/Config so we can tune without code changes.
- Thread through ResearchPipeline initialization if needed, but local constants in Summarizer are sufficient for MVP.

### 5.5 Tests
Files: test_summarizer.py (extend) and/or new test_tables.py

Cases
1) Small table flows through
- Input content contains a 5x4 Markdown table.
- Expect summary contains the same table header and pipes (verbatim preservation).

2) Large table compressed
- Input contains a 200x10 table with numeric column "Accuracy".
- Expect compressed table appears with header + top-K rows and a compression notes line.
- Verify notes mention number of rows shown and selection criteria.

3) Scraper preserves tables (integration-ish)
- Feed simple HTML with a <table> through _scrape_with_beautifulsoup.
- Expect Markdown output includes a pipe table.

4) Numeric fidelity
- Ensure aggregates appear exactly as computed in Python and are present in the compacted table notes.

Notes
- Mock LLMClient.complete to avoid API calls; focus on preprocessing and prompt content.

### 5.6 Logging and Metrics
- Summarizer logs: number of tables detected, preserved, compressed per content/chunk.
- Scraper logs: tables found/converted per page.
- Optional counters in metadata for later analysis.

### 5.7 Backward Compatibility & Rollback
- Feature flag ENABLE_TABLE_AWARE in Summarizer; single switch to disable preprocessing.
- If markdownify path causes regressions, allow fallback to plain get_text() via config flag for quick rollback.

---

## 6) Acceptance Criteria
- Scraper (primary path) emits Markdown containing tables for basic HTML pages with <table>.
- Small Markdown tables are preserved verbatim in summary outputs.
- Large tables are compacted deterministically with:
  - Header retained.
  - Top-K rows selected per configured strategy.
  - Aggregates computed outside the LLM and included in notes.
- Prompts explicitly instruct the LLM to keep tables and not recompute numbers.
- Tests cover preservation, compression, and scraper behavior.

---

## 7) Risks & Mitigations
- Complex tables (rowspan/colspan) may render poorly in Markdown.
  - Mitigation: Document limitation; best-effort flattening; allow opt-out via flag.
- Token pressure with many small tables.
  - Mitigation: Pre-trim extremely wide tables; configurable limits; move some large tables to an appendix section (future).
- LLM reformatting tables.
  - Mitigation: Strong prompt guidance + provide tables already in desired format; low temperature.

---

## 8) Timeline (MVP)
- Day 1: Scraper table preservation (HTML→Markdown), basic tests.
- Day 2: Summarizer preprocessing (detect/keep/compress), prompt updates.
- Day 3: Salience/aggregate helpers, tests, tuning thresholds; polish logs/flags.

---

## 9) Rollout Plan
1) Implement behind ENABLE_TABLE_AWARE and SCRAPER_MARKDOWN_MODE flags.
2) Ship to a staging branch; run on a small corpus.
3) Compare before/after reports for table presence and numeric fidelity.
4) Roll out to main; monitor logs/feedback.

---

## 10) File Touchpoints Summary
- stages/scraper.py
  - _scrape_with_beautifulsoup: switch to HTML→Markdown preserving tables.
  - Add: _html_table_to_markdown(table_tag), _replace_tables_with_markdown(soup).
- stages/summarizer.py
  - Add: _find_markdown_tables, _analyze_table, _select_salient_rows, _compute_column_aggregates, _compress_markdown_table, _preprocess_for_tables.
  - Call preprocessing in _summarize_direct and per-chunk in _summarize_map_reduce.
  - Update prompts: _build_summary_prompt, _summarize_chunk, _combine_chunk_summaries.
- tests
  - Extend test_summarizer.py; add test_tables.py (optional).
- config (optional)
  - Table thresholds and flags.

---

## 11) Future Enhancements (Post-MVP)
- Structured outputs: capture tables in Summary.tables for deterministic rendering.
- PDF table extraction pipeline when PDFs are ingested directly.
- Better salience: learning-to-rank for row selection; domain-specific metrics.
- Column typing: more robust detection of numeric vs categorical.
- Appendix management: auto-move large tables and reference them inline.
