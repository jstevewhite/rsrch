# Research Pipeline

A modular, configurable CLI tool for automated research report generation using LLMs.

**Source Code:** [https://github.com/jstevewhite/rsrch](https://github.com/jstevewhite/rsrch)

## Features

✅ **Intent Classification**: Automatically identifies query type (informational, news, code, research, etc.)
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

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Configure the pipeline via `.env` file:

```bash
# API Configuration
API_KEY=your_openai_api_key
API_ENDPOINT=https://api.openai.com/v1
DEFAULT_MODEL=gpt-4o-mini

# Stage-Specific Models
INTENT_MODEL=gpt-4o-mini
PLANNER_MODEL=gpt-4o
MRS_MODEL=gpt-4o-mini
CONTEXT_MODEL=gpt-4o-mini
REFLECTION_MODEL=gpt-4o
REPORT_MODEL=gpt-4o
VERIFY_MODEL=gpt-4o

# Search Configuration
SERP_API_KEY=your_serp_api_key
RERANK_TOP_K=0.25

# Scraping Fallback (optional - for JS-heavy sites)
SERPER_API_KEY=your_serper_api_key
JINA_API_KEY=your_jina_api_key

# Vector Database Configuration
VECTOR_DB_PATH=./research_db.sqlite
EMBEDDING_MODEL=text-embedding-3-small

# Output Configuration
OUTPUT_DIR=./reports
LOG_LEVEL=INFO

# Research Configuration
MAX_ITERATIONS=3
VERIFY_CLAIMS=false
VERIFY_CONFIDENCE_THRESHOLD=0.7
```

## Usage

### Basic Usage

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

Example output file: `report_20250130_143022.md`

Each report includes:

- Query and intent
- Generation timestamp
- Structured content with sections
- Source citations with URLs and chunk references
- Research limitations (if incomplete)
- Metadata (intent, status, number of sources)

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
PLANNER_MODEL=gpt-4o
REFLECTION_MODEL=gpt-4o
REPORT_MODEL=gpt-4o
```

### Scraping Strategy

The scraper uses a three-tier fallback approach:

1. **BeautifulSoup** (free) - Fast, lightweight HTML parsing
2. **Jina.ai** (paid) - Handles JavaScript and complex layouts
3. **Serper** (paid) - Professional scraping service

### Research Iteration

The pipeline can perform multiple research iterations:

- **Reflection** identifies information gaps
- **Additional queries** are generated to fill gaps
- **Maximum iterations** configurable (default: 3)
- **Stops early** if research is deemed complete

## Troubleshooting

### API Key Issues

- Ensure `API_KEY` is set in your `.env` file
- Check that the `.env` file is in the same directory as `cli.py`
- Verify your API keys are valid and have sufficient credits

### Module Import Errors

- Make sure you're running from the project root directory
- Install all requirements: `pip install -r requirements.txt`

### Search/Scraping Issues

- Verify `SERP_API_KEY` for web search functionality
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
3. **Scraping Strategies**: Improve content extraction for specific site types
4. **Verification**: Enhance claim verification accuracy and coverage
5. **UI/UX**: Create web interface or API endpoints
6. **Testing**: Unit and integration tests
7. **Performance**: Optimize vector operations and caching

## License

MIT

## Credits

Built on the foundation documented in `docs/pipeline.md`.
