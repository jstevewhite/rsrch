# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered research pipeline that generates comprehensive reports by searching the web, scraping content, and synthesizing information using LLMs. The codebase follows a modular, stage-based architecture where each stage transforms data through a sequential pipeline with iterative refinement.

**Key Characteristics**:
- 10-stage pipeline with iterative research loop (stages 4-8 can repeat)
- Multi-provider support (SERP, Tavily, Perplexity for search; BeautifulSoup, Jina, Serper for scraping)
- Configurable parallelization for search, scraping, and summarization
- Vector-based semantic search using SQLite+VSS
- Optional claim verification with confidence scoring
- Flat package layout (unusual - see Critical Gotchas below)

## Quick Start

### Installation
```bash
# Install as editable package (required for imports to work)
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (API_KEY and SERPER_API_KEY are required)
```

### First Run
```bash
# Using console script (after pip install -e .)
rsrch "What is the latest research on quantum computing?"

# Direct execution (from project root)
python cli.py "What is the latest research on quantum computing?"

# Check the output
ls reports/
cat reports/report_*.md
cat research_pipeline.log  # Detailed execution logs
```

### Example Queries by Intent Type
```bash
# Informational - general knowledge query
rsrch "What is tirzepatide and how does it work?"

# News - current events
rsrch "Latest developments in AI safety regulation"

# Code - programming tutorials
rsrch "How to use async/await in Python with examples"

# Research - academic/technical analysis
rsrch "Comparative analysis of transformer architectures for NLP"

# Comparative - comparing options
rsrch "PostgreSQL vs MySQL for high-traffic applications"
```

### Common Options
```bash
rsrch "query" --log-level DEBUG          # Verbose logging
rsrch "query" --output ./custom_reports  # Custom output directory
rsrch "query" --show-plan                # Display research plan before execution
```

## Architecture

### Pipeline Flow (10 Stages + Iteration)

The pipeline is orchestrated by `pipeline.py` (`ResearchPipeline` class):

1. **Query Parsing** - Accept user query → `Query` model
2. **Intent Classification** (`stages/intent_classifier.py`) - Classify query intent (informational, news, code, research, comparative, tutorial, general) → `Intent` enum
3. **Planning** (`stages/planner.py`) - Generate research plan with sections and search queries → `ResearchPlan` model
4. **Research** (`stages/researcher.py`) - Execute web searches via SERP/Tavily/Perplexity APIs → `SearchResult[]`
5. **Search Reranking** (`stages/reranker.py` - optional) - Rerank search results by relevance, filter to top `RERANK_TOP_K_URL` ratio → Filtered `SearchResult[]`
6. **Scraping** (`stages/scraper.py`) - Extract content with 3-tier fallback (BeautifulSoup → Jina.ai → Serper) → `ScrapedContent[]`
7. **Summarization** (`stages/summarizer.py`) - Generate summaries with citations using map-reduce pattern → `Summary[]`
8. **Reflection** (`stages/reflector.py`) - Validate completeness, identify gaps → `ReflectionResult`
   - If incomplete and iterations remain: generate additional queries, loop back to stage 4
   - If complete or max iterations reached: proceed to stage 9
9. **Context Assembly** (`stages/context_assembler.py`) - Rank all accumulated summaries using vector similarity, filter to top `RERANK_TOP_K_SUM` ratio → `ContextPackage`
10. **Report Generation** (in `pipeline.py`) - Synthesize final report with citations → `Report`
11. **Claim Verification** (`stages/verifier.py` - optional) - Fact-check report claims against sources → `VerificationSummary`

**Iterative Research Loop**: Stages 4-8 repeat up to `MAX_ITERATIONS` times (default: 2) if reflection identifies gaps. All summaries accumulate across iterations. Example:
- Iteration 1: 5 queries → 10 summaries
- Reflection: identifies 2 gaps, generates 2 additional queries
- Iteration 2: 2 queries → 4 summaries
- Total: 14 summaries → ranked/filtered in stage 9 → report generated

**Reranking Cascade Example** (with `RERANK_TOP_K_URL=0.3`, `RERANK_TOP_K_SUM=0.5`):
- Stage 4: 10 search results per query × 5 queries = 50 results
- Stage 5: Rerank → scrape top 30% = 15 URLs
- Stage 6-7: Scrape + summarize 15 URLs = 15 summaries
- Stage 9: Rerank summaries → use top 50% = 7-8 summaries in final report

### Critical Gotchas

#### 1. Flat Package Layout - Import Implications
The project uses an **unusual flat layout** where the root directory IS the `rsrch` package (via `setup.py` `package_dir={"rsrch": "."}`).

**What this means**:
- Files like `config.py`, `pipeline.py`, `models.py` at root are imported as `rsrch.config`, `rsrch.pipeline`, `rsrch.models`
- The `stages/` subdirectory is `rsrch.stages`
- **You must run `pip install -e .` for imports to work** (even for local development)
- When editing root-level files, use absolute imports: `from rsrch.config import Config` (not `from config import Config`)
- When editing within stages/, you can use relative imports: `from ..models import Query` or absolute: `from rsrch.models import Query`

**If imports fail**: Ensure you ran `pip install -e .` and are using the same Python interpreter (`which python` should match `which pip`).

#### 2. Prompts Are Embedded in Python Code
Unlike many projects, prompts are **hardcoded in Python files, not config files**. The README mentions plans to move them to config, but currently:

**Critical prompt locations**:
- **Intent classification**: `stages/intent_classifier.py` (~line 20-40)
- **Research planning**: `stages/planner.py` (~line 30-60)
- **Source grounding policy**: `pipeline.py` lines 355-388 (critical for preventing outdated "corrections")
- **Report generation**: `pipeline.py` `_generate_report()` method (~line 390-427)
- **Global LLM policy**: `llm_client.py` line 17 (`GLOBAL_POLICY` - prevents knowledge cutoff refusals)

**To modify behavior**: Edit the prompt strings in these Python files, not `.env`.

#### 3. Verification Stage Produces False Positives
The verification stage (`VERIFY_CLAIMS=true`) is experimental. It often flags **composite claims** where a single sentence combines multiple facts from different sources.

**Example issue**: "The study included 500 participants and found 23% improvement [Source 3]" - if Source 3 only mentions the improvement percentage but not the participant count, verification will flag this even if another source mentioned 500 participants.

**Best practice**: Use multiple citations for composite claims: "The study included 500 participants [Source 2] and found 23% improvement [Source 3]" or split into separate sentences.

#### 4. Tests Require API Keys
Tests are **not mocked** - they make real API calls. You need valid API keys in `.env` to run most tests. Some tests will fail or skip if keys are missing.

### Key Architectural Patterns

**Data Models** (`models.py`): All data structures are dataclasses with clear types. Key models: `Query`, `Intent`, `ResearchPlan`, `SearchResult`, `ScrapedContent`, `Summary`, `ContextPackage`, `Report`, `ReflectionResult`, `VerificationResult`.

**Configuration** (`config.py`): Single `Config` dataclass loaded from `.env` via `Config.from_env()`. Loaded once at pipeline initialization. Each stage can use a different LLM model. Content-type-specific models supported via `MRS_MODEL_CODE`, `MRS_MODEL_RESEARCH`, `MRS_MODEL_NEWS`, `MRS_MODEL_DOCUMENTATION`, `MRS_MODEL_GENERAL`.

**LLM Client** (`llm_client.py`): OpenAI-compatible wrapper with:
- Retry logic for empty/invalid JSON responses (up to `LLM_MAX_RETRIES`, default 3)
- Global prompt policy to prevent knowledge cutoff refusals (`PROMPT_POLICY_INCLUDE`, default true)
- Multi-strategy JSON parsing (handles markdown code blocks, inline JSON, prose-embedded JSON)
- Automatic refusal detection and retry with stricter reminders

**Parallelization**: Three independent parallelization settings:
- `SEARCH_PARALLEL` (default 1): Concurrent search query execution
- `SCRAPE_PARALLEL` (default 5): Concurrent URL scraping operations
- `SUMMARY_PARALLEL` (default 1): Concurrent LLM summarization calls (⚠️ high values trigger rate limits)

**Vector Storage** (`stages/context_assembler.py`): SQLite with VSS extension for semantic search. Stores embeddings and content chunks. Uses DB-based cosine similarity via registered SQL function when embeddings exist; falls back to in-memory similarity for empty database.

**Table Handling**:
- Scraper preserves HTML tables as Markdown pipe tables when `OUTPUT_FORMAT=markdown` and `PRESERVE_TABLES=true`
- Summarizer intelligently handles tables: small tables (≤15 rows, ≤8 cols) preserved verbatim; large tables compacted to top-K salient rows + Python-computed aggregates (mean/max) in note line
- Report generator includes tables inline or in appendix section

**Domain Exclusions**: `EXCLUDE_DOMAINS` (comma-separated) applies across all providers (SERP/Perplexity via `-site:domain`, Tavily via exclude payload) with additional post-filtering. Default example excludes YouTube.

### Stage Implementation Details

**Scraper** (`stages/scraper.py`):
- 3-tier fallback: BeautifulSoup (free, fast) → Jina.ai (paid, JavaScript-capable) → Serper (paid, professional)
- Tracks fallback usage stats and estimated costs (logged at end)
- Chunks content for summarization (configurable chunk size)
- Configurable via `max_workers`, `output_format`, `preserve_tables` constructor parameters

**Summarizer** (`stages/summarizer.py`):
- Map-reduce pattern: chunks → individual chunk summaries → reduced final summary per URL
- Content-type detection (`stages/content_detector.py`) routes to appropriate model (code vs research vs news vs documentation)
- Table-aware preprocessing controlled by `ENABLE_TABLE_AWARE`, `TABLE_TOPK_ROWS`, `TABLE_MAX_ROWS_VERBATIM`, `TABLE_MAX_COLS_VERBATIM`
- Parallelized via `ThreadPoolExecutor` with `max_workers=SUMMARY_PARALLEL`

**Context Assembler** (`stages/context_assembler.py`):
- Generates embeddings for all summaries and the query
- Computes cosine similarity (in SQLite if DB has embeddings, else in-memory numpy)
- Optional Jina reranking if `USE_RERANKER=true` and credentials configured
- Filters to top `RERANK_TOP_K_SUM` ratio (e.g., 0.5 = keep top 50% of summaries)
- Returns `ContextPackage` with relevance scores in `additional_context`

**Reflector** (`stages/reflector.py`):
- Evaluates whether summaries adequately answer the query
- Identifies missing information gaps
- Generates new `SearchQuery` objects for additional research
- Returns `ReflectionResult` with `is_complete` boolean and `additional_queries` list

**Verifier** (`stages/verifier.py`):
- Extracts factual claims from report using `ClaimExtractor`
- Groups claims by source citation
- Verifies each claim against scraped source content using `ClaimVerifier`
- Produces `VerificationSummary` with confidence scores
- Flags claims below `VERIFY_CONFIDENCE_THRESHOLD` (default 0.7)
- **Known issue**: Flags composite claims with single citations as unsupported

## Development Guide

### Project Structure
```
rsrch/
├── cli.py                      # CLI entry point (console script: rsrch)
├── config.py                   # Config dataclass, env loading
├── models.py                   # All data models (Query, Report, etc.)
├── llm_client.py               # LLM wrapper with retry/policy
├── pipeline.py                 # Main ResearchPipeline orchestrator
├── stages/
│   ├── __init__.py            # Exports all stage classes
│   ├── intent_classifier.py   # Intent detection
│   ├── planner.py             # Research planning
│   ├── researcher.py          # Web search (multi-provider)
│   ├── scraper.py             # Content extraction (3-tier fallback)
│   ├── summarizer.py          # Map-reduce summarization
│   ├── context_assembler.py   # Vector ranking, reranking
│   ├── reflector.py           # Completeness validation
│   ├── reranker.py            # Search result reranking
│   ├── verifier.py            # Claim verification (optional)
│   ├── content_detector.py    # Content type detection
│   └── embedding_client.py    # Embedding generation
├── .env.example               # Config template with extensive comments
├── setup.py / pyproject.toml  # Package definition (flat layout)
├── reports/                   # Generated reports (gitignored)
├── research_db.sqlite         # Vector database (gitignored)
├── research_pipeline.log      # Execution logs
└── test_*.py                  # Standalone test scripts
```

### Running Tests
```bash
# Tests are standalone Python files - run directly (no pytest)
python test_scraper.py              # Scraper batch test
python test_scraper_url.py          # Single URL scraping
python test_scraper_tables.py       # HTML→Markdown table conversion
python test_summarizer.py           # Summarization with citations
python test_tables.py               # Table-aware summarization
python test_context_assembly.py    # Vector similarity ranking
python test_detector.py             # Content type detection
python test_llm_retry.py            # JSON retry logic
python test_model_routing.py        # Content-specific model selection
python test_researcher.py           # Web search
python test_temporal_verification.py # Verification stage

# Most tests require API keys in .env
# Tests make real API calls (not mocked)
```

### Adding a New Stage

1. **Create stage file**: `stages/your_stage.py`
```python
from rsrch.llm_client import LLMClient
from rsrch.models import YourInputModel, YourOutputModel

class YourStage:
    def __init__(self, llm_client: LLMClient, model: str):
        self.llm_client = llm_client
        self.model = model

    def process(self, input_data: YourInputModel) -> YourOutputModel:
        prompt = "Your prompt here..."
        result = self.llm_client.complete_json(
            prompt=prompt,
            model=self.model,
            temperature=0.3,
        )
        return YourOutputModel(**result)
```

2. **Export from stages/__init__.py**:
```python
from .your_stage import YourStage
```

3. **Add config parameter** (if needed) in `config.py`:
```python
@dataclass
class Config:
    # ... existing fields ...
    your_stage_model: str
```

4. **Initialize in pipeline.py** (`ResearchPipeline.__init__`):
```python
self.your_stage = YourStage(
    llm_client=self.llm_client,
    model=config.your_stage_model,
)
```

5. **Call in pipeline.py** (`ResearchPipeline.run()`):
```python
# Stage N: Your stage
logger.info("Stage N: Processing...")
result = self.your_stage.process(input_data)
logger.info(f"Your stage complete: {result.summary}")
```

### Modifying Prompts

**All prompts are in Python code.** To change behavior:

1. **Find the prompt** (see locations in Critical Gotchas section)
2. **Edit the string** directly in the Python file
3. **Test thoroughly** - prompt changes affect output quality
4. **Consider temperature** - most stages use 0.2-0.4 for factual tasks

**Example - Modify report generation prompt**:
```python
# In pipeline.py, _generate_report() method (~line 390)
prompt = f"""Generate a comprehensive research report...

Your instructions here...

Query: "{query.text}"
...
```

**Important prompts to preserve**:
- **Source grounding instructions** (pipeline.py:355-388) - prevents LLM from "correcting" sources with outdated knowledge
- **Global policy** (llm_client.py:17) - prevents knowledge cutoff refusals
- **Citation requirements** - all prompts should emphasize citations

### Model Selection Strategy

**Fast/cheap models** for simple classification/extraction:
- Intent classification: `gpt-4o-mini` or `gpt-oss-120b`
- Context assembly: `gpt-4o-mini`
- Verification: `gpt-4o-mini`

**Capable models** for complex reasoning:
- Planning: `gpt-4o` or `claude-sonnet-4.5`
- Reflection: `gpt-4o` or `claude-sonnet-4.5`
- Report generation: `gpt-4o`, `claude-sonnet-4.5`, or `gemini-2.5-pro`

**Content-specific models** for domain expertise:
- Code: `MRS_MODEL_CODE` (e.g., `gpt-oss-120b` or specialized code model)
- Research: `MRS_MODEL_RESEARCH` (e.g., `gpt-4o` for academic content)
- News: `MRS_MODEL_NEWS` (e.g., `gpt-4o-mini` for fast processing)

## Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'rsrch'
```
**Solution**: Run `pip install -e .` from the project root. Verify with `pip show rsrch`.

**Still failing?** Check:
- `which python` matches `which pip`
- You're in the correct directory (`ls setup.py` should succeed)
- Reinstall: `pip uninstall -y rsrch || true && pip install -e .`

### API Key Issues
```
ValueError: Required environment variable API_KEY is not set
```
**Solution**:
1. Ensure `.env` exists in project root: `ls .env`
2. Check API_KEY is set: `grep API_KEY .env`
3. No quotes needed: `API_KEY=sk-your-key` (not `API_KEY="sk-your-key"`)

### No Search Results
```
Found 0 search results
```
**Solution**:
1. Check search provider API key:
   - `SEARCH_PROVIDER=SERP` requires `SERPER_API_KEY`
   - `SEARCH_PROVIDER=TAVILY` requires `TAVILY_API_KEY`
   - `SEARCH_PROVIDER=PERPLEXITY` requires `PERPLEXITY_API_KEY`
2. Check logs: `grep -i "search" research_pipeline.log`
3. Verify provider is responding: test with simple query

### Scraping Failures
```
Scraped 0 URLs
```
**Solution**:
1. Check logs for fallback usage: `grep -i "fallback" research_pipeline.log`
2. BeautifulSoup fails on JavaScript-heavy sites → Jina/Serper fallback should activate
3. Check fallback API keys if needed: `JINA_API_KEY`, `SERPER_API_KEY`
4. Review scraper stats in logs: "Fallback scraping used: N times"

### JSON Parsing Errors
```
Failed to get valid JSON response after 3 attempts
```
**Solution**:
1. Increase retries: `LLM_MAX_RETRIES=5` in `.env`
2. Check model compatibility - some models don't support JSON mode well
3. Review logs for raw response: set `--log-level DEBUG`
4. Try a different model for that stage

### Rate Limiting (HTTP 429)
```
Error 429: Too Many Requests
```
**Solution**:
1. Reduce parallelization:
   - `SUMMARY_PARALLEL=1` (most common cause)
   - `SEARCH_PARALLEL=1`
   - `SCRAPE_PARALLEL=3`
2. Add delays between requests (modify stage code)
3. Upgrade API tier if available
4. Pipeline warns if `SUMMARY_PARALLEL > 4`

### Verification False Positives
```
⚠️ Flagged 10 claims for review
```
**Solution**:
1. Review flagged claims manually - many are false positives
2. Common causes:
   - Composite claims with single citation
   - Paraphrasing that changes wording
   - Math errors (LLM miscounts, verification catches it)
3. Solutions:
   - Use multiple citations: `[Source 2][Source 3]`
   - Split composite sentences
   - Disable verification: `VERIFY_CLAIMS=false`
   - Adjust threshold: `VERIFY_CONFIDENCE_THRESHOLD=0.6` (lower = more lenient)

### Empty or Incomplete Reports
```
Report has no content sections
```
**Solution**:
1. Check reflection stage: `grep -i "reflection" research_pipeline.log`
2. Increase iterations: `MAX_ITERATIONS=3`
3. Review search results quality
4. Check prompt in `pipeline._generate_report()` - may need tuning
5. Try a more capable model: `REPORT_MODEL=gpt-4o`

## Reference

### Critical Environment Variables

**Required for basic operation**:
```bash
API_KEY=sk-your-key                    # OpenAI-compatible LLM API key
API_ENDPOINT=https://api.openai.com/v1 # LLM endpoint (default: OpenAI)
SERPER_API_KEY=your-key                # SERP search API key (if SEARCH_PROVIDER=SERP)
```

**Search provider selection** (choose one):
```bash
SEARCH_PROVIDER=SERP              # Default: SERP API (Serper.dev)
# OR
SEARCH_PROVIDER=TAVILY            # Tavily API (1000 free/month)
TAVILY_API_KEY=your-key           # Required for Tavily
# OR
SEARCH_PROVIDER=PERPLEXITY        # Perplexity Search API
PERPLEXITY_API_KEY=your-key       # Required for Perplexity
```

**Model configuration** (all optional, fall back to DEFAULT_MODEL):
```bash
DEFAULT_MODEL=gpt-4o-mini         # Fallback for all stages
INTENT_MODEL=gpt-4o-mini          # Intent classification
PLANNER_MODEL=gpt-4o              # Research planning
MRS_MODEL_DEFAULT=gpt-4o-mini     # Summarization default
CONTEXT_MODEL=gpt-4o-mini         # Context assembly
REFLECTION_MODEL=gpt-4o           # Completeness validation
REPORT_MODEL=gpt-4o               # Final report generation
VERIFY_MODEL=gpt-4o-mini          # Claim verification (if enabled)
```

**Content-specific summarization models** (optional):
```bash
MRS_MODEL_CODE=gpt-4o-mini        # For code/Stack Overflow content
MRS_MODEL_RESEARCH=gpt-4o         # For academic papers/arXiv
MRS_MODEL_NEWS=gpt-4o-mini        # For news articles
MRS_MODEL_DOCUMENTATION=gpt-4o    # For technical docs
MRS_MODEL_GENERAL=gpt-4o-mini     # General content fallback
```

**Behavior control**:
```bash
PROMPT_POLICY_INCLUDE=true        # Prevent knowledge cutoff refusals (recommended)
MAX_ITERATIONS=2                  # Research iterations (1=no iteration, 2=one retry)
VERIFY_CLAIMS=false               # Enable claim verification (adds ~30-60s, ~$0.04-0.05)
VERIFY_CONFIDENCE_THRESHOLD=0.7   # Flag claims below this confidence
```

**Performance tuning**:
```bash
SEARCH_PARALLEL=1                 # Concurrent search queries (increase cautiously)
SCRAPE_PARALLEL=5                 # Concurrent scraping (5 is safe default)
SUMMARY_PARALLEL=1                # Concurrent LLM calls (⚠️ >4 triggers rate limits)
SEARCH_RESULTS_PER_QUERY=10       # Results per query (5-20 recommended)
RERANK_TOP_K_URL=0.3              # Ratio of results to scrape (0.0-1.0)
RERANK_TOP_K_SUM=0.5              # Ratio of summaries in report (0.0-1.0)
```

**Output configuration**:
```bash
OUTPUT_DIR=./reports              # Report output directory
LOG_LEVEL=INFO                    # Logging: DEBUG, INFO, WARNING, ERROR
REPORT_MAX_TOKENS=4000            # Max report length (~3000 words)
```

**Table handling**:
```bash
OUTPUT_FORMAT=markdown            # Scraper output format
PRESERVE_TABLES=true              # Convert HTML tables to Markdown
ENABLE_TABLE_AWARE=true           # Smart table summarization
TABLE_TOPK_ROWS=10                # Rows to keep in large tables
TABLE_MAX_ROWS_VERBATIM=15        # Max rows for verbatim preservation
TABLE_MAX_COLS_VERBATIM=8         # Max columns for verbatim preservation
```

**Domain exclusions**:
```bash
EXCLUDE_DOMAINS=youtube.com,youtu.be  # Comma-separated domains to exclude
```

**Vector database**:
```bash
VECTOR_DB_PATH=./research_db.sqlite   # SQLite database path
EMBEDDING_MODEL=text-embedding-3-small # Embedding model
EMBEDDING_URL=https://api.openai.com/v1 # Embedding endpoint (default: same as LLM)
```

**Reranking** (optional):
```bash
USE_RERANKER=true                        # Enable Jina reranking
RERANKER_URL=https://api.jina.ai/v1/rerank
RERANKER_MODEL=jina-reranker-v2-base-multilingual
RERANKER_API_KEY=your-key
```

### API Requirements

**Required**:
- OpenAI-compatible LLM endpoint (`API_KEY`, `API_ENDPOINT`)
- Search provider (one of):
  - SERP API (`SERPER_API_KEY`) - default, professional-grade
  - Tavily API (`TAVILY_API_KEY`) - 1000 free requests/month
  - Perplexity API (`PERPLEXITY_API_KEY`)

**Optional**:
- Jina.ai (`RERANKER_API_KEY`) - for search result reranking
- Jina.ai (`JINA_API_KEY`) - for scraping fallback on JavaScript-heavy sites
- Serper.dev - for scraping fallback (uses same `SERPER_API_KEY` as search)
- Custom embedding endpoint (`EMBEDDING_URL`, `EMBEDDING_API_KEY`)

### File Outputs

**Generated during execution**:
```
reports/report_YYYYMMDD_HHMMSS.md  # Final research report (Markdown)
research_pipeline.log               # Detailed execution logs (rotating)
research_db.sqlite                  # Vector database (embeddings + chunks)
research_db.sqlite-shm              # SQLite shared memory (temporary)
research_db.sqlite-wal              # SQLite write-ahead log (temporary)
```

**Report structure** (example: `report_20250206_143022.md`):
```markdown
# Research Report

**Query:** Your query here
**Intent:** informational
**Generated:** 2025-02-06 14:30:22

---

[Executive summary, main content sections, key findings, conclusion]

---

## Sources

**[Source 1]** Title
- URL: https://...
- Chunk: 0

**[Source 2]** Title
- URL: https://...

---

## ⚠️ Research Limitations (if incomplete)

[Gaps identified by reflection stage]

---

**Metadata:**
- intent: informational
- status: complete
- num_sources: 5
```

## Common Patterns

### Stage Class Pattern
```python
from rsrch.llm_client import LLMClient
from rsrch.models import InputModel, OutputModel

class MyStage:
    def __init__(self, llm_client: LLMClient, model: str):
        self.llm_client = llm_client
        self.model = model

    def process(self, input_data: InputModel) -> OutputModel:
        # Build prompt
        prompt = f"Process this: {input_data.text}"

        # Get LLM response
        result = self.llm_client.complete_json(
            prompt=prompt,
            model=self.model,
            temperature=0.3,
        )

        # Return typed model
        return OutputModel(**result)
```

### JSON Completion with Retry
```python
# Automatically retries up to LLM_MAX_RETRIES times on:
# - Empty responses
# - Invalid JSON
# - Network errors
result = self.llm_client.complete_json(
    prompt=prompt,
    model=self.model,
    temperature=0.3,
    max_tokens=2000,  # Optional
)
# result is a dict - parse into your model
```

### Text Completion
```python
# For non-JSON responses (e.g., final report generation)
content = self.llm_client.complete(
    prompt=prompt,
    model=self.model,
    temperature=0.2,  # Lower for factual content
    max_tokens=4000,
)
# content is a string
```

### Parallel Execution Pattern
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_item(item):
    # Your processing logic
    return result

items = [...]  # Your list of items
results = []

with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    # Submit all tasks
    futures = {executor.submit(process_item, item): item for item in items}

    # Collect results as they complete
    for future in as_completed(futures):
        try:
            result = future.result()
            results.append(result)
        except Exception as e:
            logger.error(f"Task failed: {e}")
            # Continue processing other items

return results
```

### Configuration Access Pattern
```python
# In pipeline.py or stage files
config = Config.from_env()  # Loads from .env

# Access stage-specific models
model = config.planner_model  # Falls back to config.default_model if not set

# Access content-specific models
model = config.get_mrs_model_for_content_type('code')  # Returns MRS_MODEL_CODE or fallback
```

### Logging Pattern
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed info for debugging")
logger.info("Progress updates")
logger.warning("Recoverable issues")
logger.error("Errors that don't stop execution")

# Include context
logger.info(f"Processing {len(items)} items")
logger.error(f"Failed to process {item.url}: {error}")
```
