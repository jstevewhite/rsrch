# Research Pipeline

A modular, configurable CLI tool for automated research report generation using LLMs.

## What's New
- SQLite vector search in ContextAssembler now uses DB-based top-k cosine similarity via a registered cosine_sim() SQL function; automatically falls back to in-memory similarity when the database has no embeddings.
- EXCLUDE_DOMAINS is applied across providers (SERP/Perplexity via -site:domain, Tavily via request payload) and results are post-filtered by domain. Default example excludes YouTube.
- Tests: added HTML→Markdown table conversion test for the scraper and strengthened large-table summarizer tests to assert computed aggregates.

## Notes

This research pipeline is primarily 'vibe-coded' using Warp and Windsurf. (Some recent articles suggest it's not vibe coding if you actually read and understand the code, so ... I have read and understand the code; make your own call :D) I wrote maybe ... 5-10% of the code. The design is mine, e.g. the pipeline layout, the steps, design decisions, etc. I've been iterating a research agent for some time, mostly for personal learning. The models involved have been primarily GPT5 and Claude Sonnet 4.5 - which produces the fewest errors so far. I use the zen MCP server with Gemini Pro 2.5 for codereview stuff, context7 for api currency, and perplexity for web search. 

Hallucination is low, but not zero. I have been using Gemini Pro to evaluate the reports, and mostly they're "Highly accurate and properly cited". I added my own verification stage; It makes for more searches and more scraping but it's enlightening to get a fact check at the end of the report. 

It still sometimes refers to "Former President Trump" - most models have a cut-off date prior to the inaugeration. I'm thinking about moving each prompt to a config file so they can be tuned.

There are some 'validation heuristics' that offer more significance to trusted sites than untrusted sites; I plan on excerpting that list into a config file so it's easy to update them. I'm considering trying to integrate with Ground News for partisan bias measures as well; maybe some other sites that rate accuracy, to figure into the confidence scoring. 

**RESULTS ARE STOCHASTIC*** Web searches are not deterministic, and neither are LLMs. You can get different reports on different runs, but the facts *should* align. It's like assigning a report to 15 people and comparing them. This can be addressed; I could create report templates, But I like the design here, where a planner makes the outline. 

**VERIFICATION STEP IS ASPIRATIONAL** Thus far it flags things that are ... more or less correct. Sometimes it's because the report writer combined information and cited one source. So read and understand what it's complaining about. Sometimes it's good - they are terrible at math, so it will say "23 items in this table" when there are 21, and then flag it as wrong because there are 19 (a real example where the table had 21 items.) The moral of the story is that when you have validation turned off you'll see a lot of false negatives.

## Models

I like the OSS models, but sometimes you gotta go frontier. I've had very good luck with gpt-oss-120b in most roles, and in the finalizer role I like qwen3-Max or Gemini 2.5 Pro. 

You can actually use e.g. qwen3-30b-a3b-2507 for many tasks - it does a credible job of summarizing, for instance, but the performance I get from the cloud isn't that much different, and the gpt-oss-120b outperforms it in many of these tasks.

Reflection is in development. It will still fail a question every now and then - ones that ChatGTP and Gemini both get right; I have to figure out how they're doing that. 

Claim verification is in ... call it alpha. It has a great sensitivity to model selection; sometimes you'll see a contested claim in the list and click on it and see that it just didn't get the reference. But I like getting the limitations and challenges at the end of the report, particularly since it's AI generated.

## Requirements

You'll need an OpenAI compatible endpoint. I use Openrouter because I get most of the current models to play with. I also use LiteLLM proxy, but again, any openai compatible endpoint should work. I do embedding locally using LMStudio, but you can use OpenAI or Ollama. 

There's a BeautifulSoup scraper; if it fails, it tries Jina.ai, if that fails, it tries Serper's scraper. Jina.ai is the reranker used, but it's not too hard to change. I'm thinking about using a local embedding model and sorting by relevance score, but the Jina reranker is fast and cheap as chips. There's the option of Tavily search, but if you want to do a lot of research, I suggest just buying some credits at both endpoints. 

**Source Code:** [https://github.com/jstevewhite/rsrch](https://github.com/jstevewhite/rsrch)

## Features

✅ **Intent Classification**: Automatically identifies query type (informational, news, code, research, etc.)

✅ **Markdown-first Scraping (new)**: Primary scraper now emits full-page Markdown with preserved tables when `OUTPUT_FORMAT=markdown` and `PRESERVE_TABLES=true`

✅ **Table-aware Summarization (new)**: Small tables are preserved verbatim; large tables are compacted deterministically (header + top-K salient rows + Python-computed aggregates) with configurable thresholds

✅ **Report Table Handling (new)**: Final report includes Markdown tables verbatim and compacted tables as-is with their note lines; will create a short "Tables" subsection or appendix if needed

✅ **Research Planning**: Creates structured plans with sections and search queries

✅ **Web Search Integration**: Searches the web using SERP API for current information

✅ **Content Scraping**: Extracts and processes web content with fallback strategies

✅ **Intelligent Summarization**: Generates summaries with citations using map-reduce

✅ **Context Assembly**: Builds context packages with vector similarity and reranking

✅ **Reflection & Iteration**: Validates completeness and performs additional research if needed

✅ **Claim Verification**: Optional fact-checking of report claims (experimental)

✅ **Configurable Models**: Use different LLMs for each stage via configuration

✅ **Report Generation**: Produces comprehensive Markdown reports with citations

🚧 **Advanced Features**:

- Vector database storage (SQLite + VSS) for semantic search
- Search result reranking for improved relevance
- Iterative research refinement based on reflection
- Multi-source claim verification with confidence scoring

## Architecture

The pipeline consists of 10 stages:

1. **Query Parsing**: Accept and parse user query
2. **Intent Classification**: Identify query intent
3. **Planning**: Design research approach and queries
4. **Research**: Execute web searches and gather results
5. **Scraping**: Extract and chunk content from URLs
6. **Summarization**: Generate summaries with citations
7. **Context Assembly**: Build context package with vector similarity
8. **Reflection**: Validate completeness and identify gaps
9. **Report Generation**: Create final report with citations
10. **Claim Verification**: Optional fact-checking (experimental)

## Installation

Recommended: modern editable install (PEP 660) via pyproject.toml

```bash
pip install -e .
cp .env.example .env
```

Notes:
- Location independent: run from anywhere (no reliance on /Users vs /Volumes paths)
- If you move or clone the repo elsewhere, just run `pip install -e .` again
- Works with Anaconda/conda or venv; make sure `which python` and `which pip` match

Alternative (basic deps only):

```bash
pip install -r requirements.txt
cp .env.example .env
# Then run from project root (no console script installed)
```

## Configuration

Configure the pipeline via `.env` file:

```bash
# API Configuration
API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o-mini

# Stage-Specific Models
INTENT_MODEL=gpt-4o-mini
PLANNER_MODEL=gpt-4o

# Multi-Resource Summarizer (MRS) Model Configuration
# Default model used when no content type is specified
MRS_MODEL_DEFAULT=gpt-4o-mini

# Content-Specific MRS Models (optional)
# Uncomment and configure models for different content types:
# MRS_MODEL_CODE=gpt-4o-mini        # For Stack Overflow, GitHub, code documentation
# MRS_MODEL_RESEARCH=gpt-4o         # For arXiv, research papers, academic content
# MRS_MODEL_NEWS=gpt-4o-mini        # For news articles, blogs, media
# MRS_MODEL_DOCUMENTATION=gpt-4o    # For technical documentation
# MRS_MODEL_GENERAL=gpt-4o-mini     # Fallback for general content

# How content type detection works:
# 1. URL heuristics check domain patterns (arxiv.org -> research, github.com -> code)
# 2. Falls back to MRS_MODEL_DEFAULT if no content-specific model is configured
# 3. Uses MRS_MODEL_GENERAL if configured, otherwise MRS_MODEL_DEFAULT

CONTEXT_MODEL=gpt-4o-mini
REFLECTION_MODEL=gpt-4o
REPORT_MODEL=gpt-4o

# Search Configuration (Serper.dev provides both search and scraping)
SERPER_API_KEY=your_serper_api_key  # Required for web search and scraping fallback
# Exclude domains (comma-separated). Applied as -site:domain for SERP/Perplexity, and 'exclude' payload for Tavily; results are also post-filtered by domain. Example: exclude YouTube
EXCLUDE_DOMAINS=youtube.com,youtu.be
# Perplexity Search API (optional; use if SEARCH_PROVIDER=PERPLEXITY)
PERPLEXITY_API_KEY=your_perplexity_api_key
# Choose provider: SERP (Serper), TAVILY, or PERPLEXITY
SEARCH_PROVIDER=SERP  # Options: SERP, TAVILY, PERPLEXITY
TAVILY_API_KEY=your_tavily_api_key  # Optional: enables higher rate limits
SEARCH_RESULTS_PER_QUERY=10  # Number of search results to request per query (5-20 recommended)
RERANK_TOP_K_URL=0.3   # Ratio of search results to scrape (0.0-1.0)
RERANK_TOP_K_SUM=0.5   # Ratio of summaries to include in report (0.0-1.0)

# Vector Database Configuration
VECTOR_DB_PATH=./research_db.sqlite
EMBEDDING_MODEL=text-embedding-3-small

Vector search notes: ContextAssembler now performs top-k retrieval directly in SQLite using a registered cosine_sim() SQL function when embeddings are present. If the database is empty, it falls back to in-memory similarity.

# Reranker Configuration (optional)
# RERANKER_URL=https://api.jina.ai/v1/rerank
# RERANKER_MODEL=jina-reranker-v2-base-multilingual
# RERANKER_API_KEY=your_reranker_api_key
# USE_RERANKER=true

# Verification Configuration (Optional - adds ~30-60s and ~$0.04-0.05 per report)
# VERIFY_CLAIMS=true  # Enable claim verification stage
# VERIFY_MODEL=gpt-4o-mini  # Model for verification (cheap is fine)
# VERIFY_CONFIDENCE_THRESHOLD=0.7  # Flag claims below this confidence

# Output Configuration
OUTPUT_DIR=./reports
LOG_LEVEL=INFO
REPORT_MAX_TOKENS=4000  # Default: ~3000 words
MAX_ITERATIONS=2  # Maximum research iterations (1=no iteration, 2=one additional iteration)

# Scraper output and table preservation (new)
OUTPUT_FORMAT=markdown      # Emit Markdown from primary scraper
PRESERVE_TABLES=true        # Convert HTML tables to Markdown inline

# Summarizer table handling (new)
ENABLE_TABLE_AWARE=true     # Enable table-aware preprocessing
TABLE_TOPK_ROWS=10          # Rows to keep for large tables (set higher for more)
TABLE_MAX_ROWS_VERBATIM=15  # Preserve small tables at or below this row count
TABLE_MAX_COLS_VERBATIM=8   # Preserve small tables at or below this column count

# Parallelization Configuration
# Control concurrent operations to balance speed vs rate limits
# Set to 1 to disable parallelization for that stage

# Search: Concurrent search queries (default: 1)
SEARCH_PARALLEL=2

# Scraping: Concurrent scrape operations (default: 5)
SCRAPE_PARALLEL=5

# Summarization: Concurrent LLM calls (default: 1)
SUMMARY_PARALLEL=2
```

## Parallelization: Cost vs Speed vs Rate Limits

- Same tokens = same cost, regardless of parallelization level.
- Higher parallelization reduces wall-clock time but may trigger API rate limits (HTTP 429).
- Start conservatively (SEARCH_PARALLEL=2, SCRAPE_PARALLEL=5, SUMMARY_PARALLEL=2); increase gradually.

If you encounter 429 errors, reduce the corresponding parallel setting or upgrade your API tier.

## Usage

### Basic Usage

Preferred (installed console script):

```bash
rsrch "What is the latest research on tirzepatide?"
```

Alternative (direct module):

```bash
python cli.py "What is the latest research on tirzepatide?"
```

### Advanced Options

```bash
# Use custom config file
python cli.py "How do I initialize litellm in Python?" --config ./my_config.env

# Specify output directory
python cli.py "Israel/Gaza conflict latest news" --output ./my_reports

# Enable debug logging
python cli.py "Your query here" --log-level DEBUG

# Show research plan before execution
python cli.py "Your query here" --show-plan
```

### Example Queries

**Informational:**

```bash
python cli.py "What is the latest research on tirzepatide?"
```

**Code/Tutorial:**

```bash
python cli.py "How do you initialize litellm and use it in a python program?"
```

**News:**

```bash
python cli.py "What's the latest news on the Israel/Gaza conflict?"
```

**Research:**

```bash
python cli.py "Comparative analysis of transformer architectures for NLP tasks"
```

## Project Structure

```text
rsrch/
├── cli.py                 # Main CLI entry point
├── config.py             # Configuration management
├── models.py             # Data models
├── llm_client.py         # LLM client wrapper
├── pipeline.py           # Pipeline orchestrator
├── stages/
│   ├── __init__.py
│   ├── intent_classifier.py    # Intent classification
│   ├── planner.py              # Research planning
│   ├── researcher.py           # Web search integration
│   ├── scraper.py              # Content extraction & chunking
│   ├── summarizer.py           # Map-reduce summarization
│   ├── context_assembler.py   # Context building with vector search
│   ├── reflector.py            # Completeness validation
│   ├── reranker.py             # Search result reranking
│   ├── verifier.py             # Claim verification (experimental)
│   ├── content_detector.py     # Content type detection
│   └── embedding_client.py     # Embedding generation
├── .env.example          # Example configuration
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Output

Reports are saved as Markdown files in the configured output directory (default: `./reports/`).

### Table Handling (new)
- Scraper emits Markdown and preserves HTML tables as pipe tables when enabled.
- Summarizer preserves small tables verbatim. For large tables, it compacts deterministically:
  - header retained
  - top-K salient rows (by numeric target column or combined numeric score)
  - aggregates computed outside the LLM (mean/max) and added as a note line
- Report generator is instructed to:
  - include Markdown tables verbatim in relevant sections
  - include compacted tables as-is with their note lines
  - if a table doesn’t fit naturally inline, place it in a short “Tables” subsection or an appendix

Example output file: `report_20250130_143022.md`

Each report includes:

- Query and intent
- Generation timestamp
- Structured content with sections
- Source citations with URLs and chunk references
- Research limitations (if incomplete)
- Metadata (intent, status, number of sources)

## Tests

You can run the included tests directly with Python:

```bash
# Scraper tests (batch + single URL)
python test_scraper.py
python test_scraper_url.py

# Scraper HTML→Markdown table conversion (new)
python test_scraper_tables.py

# Summarizer tests
python test_summarizer.py

# Table-aware summarizer tests (new)
python test_tables.py
```

Notes:
- test_scraper_tables.py validates that a simple HTML <table> becomes a Markdown pipe table in the primary scraper when OUTPUT_FORMAT=markdown and PRESERVE_TABLES=true.
- test_tables.py ensures small tables are preserved verbatim and large tables are compacted with accurate aggregates.

## Development Status

### Current Status (v1.0)

- ✅ Configuration system
- ✅ LLM client (OpenAI compatible)
- ✅ Intent classification (7 intent types)
- ✅ Research planning with structured sections
- ✅ Web search integration (SERP API)
- ✅ Content scraping with fallback strategies
- ✅ Vector database (SQLite + VSS)
- ✅ Map-reduce summarization with citations
- ✅ Context assembly with semantic search
- ✅ Reflection and iterative refinement
- ✅ Report generation with comprehensive citations
- ✅ Optional claim verification
- ✅ CLI interface with logging
- ✅ Comprehensive error handling

### Advanced Features Available

- **Search Reranking**: Improves result relevance using semantic similarity
- **Iterative Research**: Automatically performs additional research if gaps are identified
- **Claim Verification**: Fact-checks report claims against source material
- **Vector Storage**: Stores content chunks for semantic retrieval
- **Multi-Model Configuration**: Different LLMs for different pipeline stages

## Advanced Configuration

### Model Selection Strategy

The pipeline supports different models for different stages to optimize cost and performance:

```bash
# Fast, cost-effective models for simple tasks
INTENT_MODEL=gpt-4o-mini
MRS_MODEL=gpt-4o-mini
CONTEXT_MODEL=gpt-4o-mini

# More capable models for complex reasoning

### Research Iteration

The pipeline can perform multiple research iterations:
- **Additional queries** are generated to fill gaps
- **Maximum iterations** configurable (default: 3)
- **Stops early** if research is deemed complete

## Troubleshooting

### API Key Issues

- Ensure `API_KEY` is set in your `.env` file
- Check that the `.env` file is in the same directory as `cli.py`
- Verify your API keys are valid and have sufficient credits

### Module Import Errors

- If you installed with `pip install -e .`, you can run from anywhere. If imports fail:
  - Ensure you're using the same interpreter you used to install (`which python`, `which pip`)
  - Reinstall: `pip uninstall -y rsrch || true && pip install -e .`
- If you did not use the editable install, run from the project root or switch to the editable install above.

### Search/Scraping Issues

- Verify `SERPER_API_KEY` for web search functionality
- To preserve tables and emit Markdown from the primary scraper, ensure:
  - `OUTPUT_FORMAT=markdown`
  - `PRESERVE_TABLES=true`

### Table Summarization Issues
- If you see only 10 rows in compacted tables, ensure the environment variables are wired and set:
  - `ENABLE_TABLE_AWARE=true`
  - `TABLE_TOPK_ROWS` set to desired number (e.g., 100)
- The pipeline now reads these from `.env` and passes them into the summarizer.

### Verification Notes (composite claims)
- If a sentence combines multiple facts (e.g., classification + counts), attach multiple citations so each part is supported (e.g., [Source 3][Source 7]).
- Prefer splitting into two sentences when possible for easier verification and clearer sourcing.
- The verifier will be stricter if only one citation is provided but both parts are asserted; include the missing source to avoid false negatives.
- Optional: Configure `SERPER_API_KEY` or `JINA_API_KEY` for fallback scraping
- Check `research_pipeline.log` for detailed error messages

### Logging

- Check `research_pipeline.log` for detailed error messages
- Use `--log-level DEBUG` for verbose output
- Monitor scraping fallback usage and costs

## Contributing

This is an active development project. Key areas for contribution:

1. **Model Providers**: Add support for additional LLM providers (Anthropic, etc.)
2. **Search Sources**: Integrate additional search APIs or RSS feeds
3. **Scraping Strategy**

The scraper uses a three-tier fallback approach:
1. **BeautifulSoup** (free) - Fast, lightweight HTML parsing
2. **Jina.ai** (paid) - Handles JavaScript and complex layouts
3. **Serper** (paid) - Professional scraping service

**Search Provider Selection**

Choose your preferred search API provider:

```bash
# Use SERP API (default - requires SERPER_API_KEY)
SEARCH_PROVIDER=SERP

# Use Tavily API (free tier: 1,000 requests/month, no API key needed)
SEARCH_PROVIDER=TAVILY
```

**SERP API (Default):**
- Requires `SERPER_API_KEY` configuration
- Higher quality results, more reliable
- Best for production use

**Tavily API (Free Alternative):**
- 1,000 free requests per month (no API key needed)
- Optional: Provide `TAVILY_API_KEY` for higher rate limits and advanced features
- Good fallback option when SERPER API is unavailable

The pipeline will automatically use your chosen provider for all web searches.
6. **Testing**: Unit and integration tests
7. **Performance**: Optimize vector operations and caching

## License

{{ ... }}

## Credits

Built on the foundation documented in `docs/pipeline.md`.
