# Project Memory: Research Pipeline (rsrch)

## 🎯 Project Overview

- **Purpose:** Modular CLI pipeline to generate automated research reports using LLMs.
- **Goals:**
  - Classify intent, plan research, gather sources, summarize, reflect, and produce a Markdown report.
  - Make stages configurable per model/provider.
  - Add web search, scraping, chunking, vector DB, and citation tracking.

- **High-Level Architecture:**
  - CLI entry (`cli.py`) orchestrates `pipeline.py`.
  - Config via `.env`/env vars handled by `config.py`.
  - LLM requests via `llm_client.py`.
  - Reports saved to `./reports/`.

## 🚀 Current Focus & Next Steps

- **Active Task:** Phase 2 - Vector Storage Implementation (Configuration ready, implementation pending)
- **Recent Changes:**
  - 2025-10-13 10:34:00 -0500: Updated project memory to reflect completed Phase 1 (Web Search & Scraping stages implemented).
  - 2025-09-30 13:33:55 -0500: Created `.note/project_memory.md` and `.note/session_log.md`.
  - 2025-09-30 13:43:12 -0500: Merged `WARP.md` context into project memory.
- **Next Steps:**
  - **Phase 2:** Implement vector storage (SQLite + VSS, embeddings) for efficient data management.
  - **Phase 3:** Smart summarization with map-reduce and citation tracking.
  - **Phase 4:** Reflection stage for gap analysis and iterative refinement.

## 🏗️ Code Structure & Interfaces

- **Directory Layout:**
  - `cli.py` — CLI entry point and argument parsing.
  - `models.py` — data models and typed structures.
  - `llm_client.py` — LLM client wrapper (OpenAI-compatible).
  - `pipeline.py` — orchestrates pipeline stages and report generation.
  - `stages/` — stage implementations (`intent_classifier.py`, `planner.py`, `researcher.py`, `scraper.py`, `summarizer.py`, `context_assembler.py`, `content_detector.py`, `reranker.py`, `reflector.py`, `verifier.py`).
  - `examples/` — example reports and usage.
  - `tests/` — test files (e.g., `test_researcher.py`, `test_scraper.py`).
  - `.env.example` — example configuration.
  - `requirements.txt` — Python dependencies.
  - `pipeline.md`, `README.md`, `WARP.md` — design and docs.
  - `.note/` — memory system files.

- **Key Components & Interfaces:**
  - `pipeline.run_pipeline(query, options)` coordinates stage calls.
  - `stages.intent_classifier.classify_intent(text)` returns intent label.
  - `stages.planner.plan_research(query, intent)` returns plan with sections and queries.
  - `stages.researcher.research(query, intent)` performs web search using MCP tools.
  - `stages.scraper.scrape(urls)` scrapes and processes content from URLs.
  - `stages.summarizer.summarize(content, context)` generates summaries.
  - `stages.context_assembler.assemble_context(sources)` compiles relevant context.
  - `stages.content_detector.detect_content(content)` identifies content types.
  - `stages.reranker.rerank(results, query)` reranks search results.
  - `stages.reflector.reflect(report, gaps)` performs reflection and gap analysis.
  - `stages.verifier.verify(facts, sources)` verifies information accuracy.
  - `llm_client.complete(prompt, model, **kwargs)` and `llm_client.complete_json(...)` handle LLM completions.
  - **MCP Tools Available:** `search_web`, `parallel_search_web`, `read_url`, `parallel_read_url` for web research.

- **Stage Pattern:**

  ```python
  class StageClass:
      def __init__(self, llm_client: LLMClient, model: str):
          self.llm_client = llm_client
          self.model = model
      
      def process(self, input_data: InputModel) -> OutputModel:
          # Stage logic here
          return output_data
  ```

- **Architecture Diagram (Mermaid):**

```mermaid
flowchart TD
  CLI[cli.py] --> PIPE[pipeline.py]
  PIPE -->|1| PARSE[Query Parsing]
  PIPE -->|2| INTENT[Intent Classification]
  PIPE -->|3| PLAN[Planning]
  PIPE -->|4| RESEARCH[Research (researcher.py)]
  PIPE -->|5| SCRAPE[Scraping (scraper.py)]
  PIPE -->|6| SUM[Summarization (summarizer.py)]
  PIPE -->|7| CTX[Context Assembly (context_assembler.py)]
  PIPE -->|8| REFL[Reflection (reflector.py)]
  PIPE -->|9| REPORT[Report Generation]
```

## ⚖️ Standards & Decisions

- **Coding Conventions:**
  - Python 3.10+, type hints preferred, small focused modules.
  - Config via `.env` with `.env.example` template; logging with levels (INFO/DEBUG).
  - Markdown reports saved to `OUTPUT_DIR` (default `./reports`).
- **Key Decisions Log:**
  - 2025-09-30: Use OpenAI-compatible client with option to adapt to `litellm`.
  - 2025-09-30: Stage-per-model configuration via env vars.
  - 2025-09-30: Adopt `.note/` two-file memory system for active context and historical log.
  - 2025-09-30: Use MCP tools (`search_web`, `read_url`) for web research instead of SERP API.
  - 2025-09-30: Intent-aware processing adapts behavior (CODE, NEWS, RESEARCH, INFORMATIONAL, etc.).
