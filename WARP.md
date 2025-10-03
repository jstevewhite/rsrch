# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Research Pipeline** - A modular, configurable CLI tool for automated research report generation using LLMs. This is a Python-based system designed to accept natural language queries and produce comprehensive Markdown reports through a multi-stage pipeline.

**Current Status:** v0.1 - Foundation complete (30% functional). Core infrastructure working, research stages need implementation.

## Common Development Commands

### Setup and Configuration
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API_KEY
```

### Running the Pipeline
```bash
# Basic usage
python cli.py "What is the latest research on tirzepatide?"

# With debug logging
python cli.py "Your query here" --log-level DEBUG

# Custom output directory
python cli.py "Your query" --output ./my_reports

# Show research plan
python cli.py "Your query" --show-plan
```

### Testing Different Query Types
```bash
# Informational query
python cli.py "What is machine learning?"

# Code/tutorial query
python cli.py "How do I use asyncio in Python?"

# News query
python cli.py "Latest quantum computing news"

# Research query
python cli.py "Comparative analysis of transformer architectures"
```

### Development
```bash
# Check logs
tail -f research_pipeline.log

# View generated reports
ls -lh reports/
cat reports/report_*.md

# Test specific stage (when implementing)
python -m pytest tests/test_intent_classifier.py -v
```

## High-Level Architecture

### Pipeline Flow
The system processes queries through 9 stages (stages 1-3 and 9 currently implemented):

```
Query → Intent Classification → Research Planning → [Research] → [Scraping] 
  → [Summarization] → [Context Assembly] → [Reflection] → Report Generation
```

**Implemented (✅):**
- Stage 1: Query parsing (`models.Query`)
- Stage 2: Intent classification (`stages/intent_classifier.py`)
- Stage 3: Research planning (`stages/planner.py`)
- Stage 9: Report generation (`pipeline.py`)

**TODO (🚧):**
- Stage 4: Web search (needs `stages/researcher.py`)
- Stage 5: Content scraping (needs `stages/scraper.py`)
- Stage 6: Summarization with citations (needs `stages/summarizer.py`)
- Stage 7: Context assembly (needs `stages/context_assembler.py`)
- Stage 8: Reflection/validation (needs `stages/reflector.py`)

### Core Components

**Orchestration:**
- `pipeline.py`: Main orchestrator that chains all stages together
- `cli.py`: Command-line interface and entry point

**Configuration:**
- `config.py`: Environment-based configuration management
- `.env`: Configuration file with API keys and model settings

**Data Models:**
- `models.py`: Type-safe dataclasses for all pipeline data structures
  - `Query`, `Intent`, `ResearchPlan`, `SearchQuery`
  - `SearchResult`, `ScrapedContent`, `Citation`, `Summary`
  - `ContextPackage`, `ReflectionResult`, `Report`

**LLM Integration:**
- `llm_client.py`: OpenAI-compatible API wrapper
  - Supports both text and JSON mode completions
  - Compatible with litellm for multi-provider support

**Stages:** (`stages/` directory)
- Each stage is a separate module with clear input/output contracts
- Stages use dependency injection (receive `LLMClient` and model name)
- Currently implemented: `intent_classifier.py`, `planner.py`

### Design Patterns

**Modular Stage Architecture:**
Each pipeline stage follows this pattern:
```python
class StageClass:
    def __init__(self, llm_client: LLMClient, model: str):
        self.llm_client = llm_client
        self.model = model
    
    def process(self, input_data: InputModel) -> OutputModel:
        # Stage logic here
        return output_data
```

**Configuration-Driven:**
- Different LLM models can be configured per stage
- Fast/cheap models for classification (e.g., gpt-4o-mini)
- Powerful models for planning and final report (e.g., gpt-4o)
- Example: `INTENT_MODEL=gpt-4o-mini`, `REPORT_MODEL=gpt-4o`

**Intent-Aware Processing:**
The system adapts behavior based on detected query intent:
- `CODE`: Focus on documentation, examples, best practices
- `NEWS`: Prioritize recent sources, multiple perspectives
- `RESEARCH`: Academic sources, in-depth analysis
- `INFORMATIONAL`: Factual information, definitions
- Others: `COMPARATIVE`, `TUTORIAL`, `GENERAL`

## Implementation Priorities

### Phase 1: Web Search & Scraping (Highest Priority)
**Goal:** Enable actual web research instead of relying solely on LLM knowledge

**MCP Tools Available (via Warp/Claude, not directly in Python):**

*Search (via serper-api-mcp):*
- `search`: General web search (returns URLs, titles, snippets)
- `search_news`: News-specific search (for NEWS intent queries)
- `search_scholar`: Academic/scholarly search (for RESEARCH intent queries)
- `get_url`: Web scraper (paid per request, for fallback use)

**Scraping Strategy (Python Implementation):**
- **Primary**: BeautifulSoup + requests (free, works for 95%+ of sites)
- **Fallback 1**: Jina.ai r.jina.ai API (paid, handles JS-heavy sites)
- **Fallback 2**: Serper scrape API (paid, final fallback)

**Files to Create:**
1. `stages/researcher.py`: Web search using serper-api-mcp tools
2. `stages/scraper.py`: ✅ Created - Multi-tier scraper with automatic fallbacks

**Integration:**
- Update `pipeline.py` stages 4-5 to use new implementations
- Handle rate limiting and errors gracefully
- Store results in appropriate data models

### Phase 2: Vector Storage
**Goal:** Store and efficiently retrieve scraped content

**Requirements:**
- SQLite + VSS extension for vector search
- Embedding generation using `EMBEDDING_MODEL`
- Metadata tracking (URL, timestamp, chunk position)

### Phase 3: Smart Summarization
**Goal:** Extract key information with proper citations

**Requirements:**
- Map-reduce summarization strategy
- Citation extraction and tracking
- Context package assembly for report generation

### Phase 4: Reflection & Refinement
**Goal:** Validate completeness and fill gaps

**Requirements:**
- Gap analysis ("Do we have enough to answer the query?")
- Generate additional queries if needed
- Iterative research loops until satisfied

## Key Implementation Notes

### Adding a New Stage

1. Create stage file in `stages/` directory
2. Follow the standard stage interface pattern
3. Import and register in `stages/__init__.py`
4. Update `pipeline.py` to integrate the stage
5. Add configuration in `.env` if stage needs a specific model
6. Update data models in `models.py` if needed

Example:
```python
# stages/new_stage.py
import logging
from ..models import InputModel, OutputModel
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

class NewStage:
    def __init__(self, llm_client: LLMClient, model: str):
        self.llm_client = llm_client
        self.model = model
    
    def process(self, input_data: InputModel) -> OutputModel:
        logger.info("Processing new stage...")
        # Implementation here
        return output_data
```

### Using MCP Tools for Search

The serper-api-mcp server provides intent-aware search capabilities:

```python
# Example: Using serper-api-mcp tools
from call_mcp_tool import call_mcp_tool

# General web search
results = call_mcp_tool(
    name="search",
    input={
        "query": "search terms",
        "num_results": 10,
        "country_code": "us",
        "language": "en"
    }
)

# News-specific search (for NEWS intent)
news_results = call_mcp_tool(
    name="search_news",
    input={
        "query": "latest developments",
        "num_results": 10
    }
)

# Academic/scholarly search (for RESEARCH intent)
scholar_results = call_mcp_tool(
    name="search_scholar",
    input={
        "query": "academic research topic",
        "num_results": 10
    }
)
```

### Scraping Implementation

The scraper uses a three-tier approach automatically:

```python
from stages.scraper import Scraper

scraper = Scraper()
scraped_content = scraper.scrape_results(search_results)

# Automatically tries:
# 1. BeautifulSoup (free) - works for 95%+ sites
# 2. Jina.ai API (paid) - if BeautifulSoup fails
# 3. Serper API (paid) - if Jina fails

# Check fallback usage:
stats = scraper.get_fallback_usage_stats()
print(f"Paid scrapes used: {stats['fallback_used']}")
print(f"Estimated cost: ${stats['estimated_cost']:.2f}")
```

**API Setup:**
- Jina.ai: `https://r.jina.ai/{url}` (optional: add API key for higher rate limit)
- Serper: `https://scrape.serper.dev` (requires `SERPER_API_KEY` in `.env`)
### Working with LLM Client

The `LLMClient` supports two completion modes:

```python
# Standard text completion
response = llm_client.complete(
    prompt="Your prompt here",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=2000
)

# JSON mode (for structured responses)
response = llm_client.complete_json(
    prompt="Your prompt here requesting JSON",
    model="gpt-4o-mini",
    temperature=0.3
)
```

### Error Handling Pattern

Stages should handle errors gracefully and provide fallbacks:

```python
try:
    # Main processing logic
    result = self.process_data(input_data)
    logger.info("Stage completed successfully")
    return result
except Exception as e:
    logger.error(f"Error in stage: {e}")
    # Return minimal/fallback result
    return fallback_result
```

## MCP Tools Configuration

This project uses the **serper-api-mcp** server for web searches:

```json
"serper-api-mcp": {
  "command": "node",
  "args": ["/Volumes/SAM2/CODE/MCP/serper-api-mcp/serper-api-mcp/build/index.js"],
  "env": {
    "SERPER_API_KEY": "your_serper_key"
  }
}
```

**Available Tools:**
- `search`: General web search
- `search_news`: News articles (use for NEWS intent)
- `search_scholar`: Academic papers (use for RESEARCH intent)

**Tool Selection Strategy:**
The `researcher.py` stage should select the appropriate search tool based on query intent:
- `Intent.NEWS` → use `search_news`
- `Intent.RESEARCH` → use `search_scholar`
- All others → use `search`

## Configuration

All configuration is managed through `.env` file:

**API Configuration:**
- `API_KEY`: Your OpenAI (or compatible) API key **(required)**
- `API_ENDPOINT`: API endpoint URL (default: OpenAI)
- `DEFAULT_MODEL`: Default model if stage-specific not set

**Stage-Specific Models:**
- `INTENT_MODEL`: For intent classification (default: gpt-4o-mini)
- `PLANNER_MODEL`: For research planning (default: gpt-4o)
- `MRS_MODEL`: For map-reduce summarization
- `CONTEXT_MODEL`: For context assembly
- `REFLECTION_MODEL`: For reflection/validation
- `REPORT_MODEL`: For final report generation (default: gpt-4o)

**Search Configuration:**
- `SERP_API_KEY`: SERP API key (optional, for future use)
- `RERANK_TOP_K`: Top-K percentage for re-ranking (default: 0.25)

**Database & Storage:**
- `VECTOR_DB_PATH`: Path to SQLite vector database (default: ./research_db.sqlite)
- `EMBEDDING_MODEL`: Model for generating embeddings (default: text-embedding-3-small)

**Output:**
- `OUTPUT_DIR`: Directory for generated reports (default: ./reports)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Troubleshooting

**Import Errors:**
Always run commands from the repository root (`/Users/stwhite/CODE/rsrch`)

**API Key Issues:**
```bash
# Verify .env file exists and contains API_KEY
cat .env | grep API_KEY
```

**Logging:**
```bash
# Check detailed logs
tail -f research_pipeline.log

# Enable debug mode
python cli.py "query" --log-level DEBUG
```

**Model Compatibility:**
The LLM client is OpenAI-compatible. To use other providers:
- Set appropriate `API_ENDPOINT` in `.env`
- Or modify `llm_client.py` to use litellm for automatic provider handling

## Documentation Files

- `README.md`: Comprehensive project documentation
- `QUICKSTART.md`: 5-minute setup guide
- `PROJECT_SUMMARY.md`: Current status and next steps
- `IMPLEMENTATION_GUIDE.md`: Detailed technical implementation guide
- `pipeline.md`: Original design document

## Development Philosophy

This codebase emphasizes:

- **Incremental Development**: Build foundation first, add features progressively
- **Separation of Concerns**: Each stage has one clear responsibility
- **Configuration Over Code**: Change behavior through `.env` instead of code modifications
- **Type Safety**: Use dataclasses for all data structures
- **Graceful Degradation**: Log errors and continue when possible
- **Comprehensive Logging**: Track all operations for debugging
