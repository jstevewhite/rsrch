# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

A modular CLI tool for automated research report generation using LLMs. The pipeline consists of 11 stages including intent classification, research planning, web search, content scraping, vector storage, summarization, reflection, and iterative refinement. Features search result reranking, claim verification, and content-aware model routing.

## Development Commands

### Setup & Installation
```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Install package in development mode for running tests from anywhere
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with API keys and configuration
```

### Running the Application
```bash
# Basic usage
python cli.py "What is the latest research on tirzepatide?"

# With custom config file
python cli.py "Your query" --config ./my_config.env

# Enable debug logging
python cli.py "Your query" --log-level DEBUG

# Show research plan before executing
python cli.py "Your query" --show-plan

# Specify custom output directory
python cli.py "Your query" --output ./my_reports
```

### Running Tests
```bash
# Run all tests (requires development installation)
python -m pytest

# Run specific test file
python -m rsrch.test_llm_retry

# Run test script directly
python test_setup.py  # Verifies all imports work

# From parent directory if not installed
cd /Users/stwhite/CODE
python -m rsrch.test_llm_retry
```

## Architecture

### Pipeline Orchestration
The `ResearchPipeline` class (`pipeline.py`) orchestrates the complete research flow with iterative refinement capabilities:

1. **Query Parsing**: Accept and validate user query
2. **Intent Classification**: Identify query type (informational, news, code, research)
3. **Planning**: Generate structured research plan with search queries
4. **Research**: Execute web searches via SERP API
5. **Search Reranking**: Filter results using Jina AI reranker (optional)
6. **Scraping**: Extract content using BeautifulSoup with Jina AI fallback
7. **Summarization**: Map-reduce with content-aware model routing
8. **Context Assembly**: Build context using vector similarity ranking
9. **Reflection**: Validate completeness and identify gaps
10. **Report Generation**: Create final report with iterative refinement
11. **Claim Verification**: Optional fact-checking with confidence scoring

### Stage Components
Each stage in `stages/` implements specific functionality:
- `intent_classifier.py`: Query type detection
- `planner.py`: Research strategy generation
- `researcher.py`: Web search integration
- `scraper.py`: Content extraction with fallback
- `summarizer.py`: Map-reduce summarization
- `context_assembler.py`: Vector similarity and ranking
- `reflector.py`: Completeness validation
- `reranker.py`: Search result filtering
- `verifier.py`: Claim verification system
- `content_detector.py`: Content type detection for model routing

### Configuration System
The `Config` class (`config.py`) manages all settings via environment variables:
- Stage-specific model selection
- Content-aware model routing (code, research, news, documentation)
- API keys and endpoints
- Reranking thresholds
- Iteration limits
- Verification settings

### LLM Client
The `LLMClient` (`llm_client.py`) provides:
- Automatic retry logic for empty/invalid responses
- Configurable retry attempts
- Error handling and logging
- OpenAI-compatible API interface

### Vector Storage
- SQLite database with VSS extension
- Embedding generation via configurable service
- Semantic search capabilities
- Citation tracking

## Key Configuration Variables

Essential settings in `.env`:
- `API_KEY`: OpenAI/OpenRouter API key (required)
- `INTENT_MODEL`: Model for intent classification (default: gpt-4o-mini)
- `PLANNER_MODEL`: Model for research planning (default: gpt-4o)
- `MRS_MODEL_DEFAULT`: Default summarization model (default: gpt-4o-mini)
- `MRS_MODEL_CODE/RESEARCH/NEWS`: Content-specific models (optional)
- `REFLECTION_MODEL`: Model for reflection stage (default: gpt-4o)
- `REPORT_MODEL`: Model for final report (default: gpt-4o)
- `SERP_API_KEY`: For Google search results
- `JINA_API_KEY`: For web scraping and reranking
- `USE_RERANKER`: Enable/disable reranking (default: true)
- `VERIFY_CLAIMS`: Enable claim verification (default: false)
- `MAX_ITERATIONS`: Maximum research iterations (default: 2)
- `RERANK_TOP_K_URL`: Ratio of search results to keep (default: 0.3)
- `RERANK_TOP_K_SUM`: Ratio of summaries to include (default: 0.5)

## Adding New Pipeline Features

To extend functionality:

1. **New Stage**: Create class in `stages/`, inherit from base stage pattern
2. **New Model**: Add to `Config` class and `.env.example`
3. **New Content Type**: Update `content_detector.py` and model routing in `config.py`
4. **New Verification**: Extend `verifier.py` with additional checks

## Troubleshooting

### Module Import Errors
```bash
# Install in development mode
pip install -e .
# Or run from parent directory
cd /Users/stwhite/CODE && python -m rsrch.cli
```

### API Key Issues
- Ensure `.env` file exists with `API_KEY` set
- Check `.env` is in same directory as `cli.py`
- Verify API endpoint matches key type (OpenAI vs OpenRouter)

### Empty LLM Responses
- Check `LLM_MAX_RETRIES` setting (default: 3)
- Review `research_pipeline.log` for retry attempts
- Verify model availability and API limits