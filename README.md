# Research Pipeline

A modular, configurable CLI tool for automated research report generation using LLMs.

## Features

✅ **Intent Classification**: Automatically identifies query type (informational, news, code, research, etc.)
✅ **Research Planning**: Creates structured plans with sections and search queries
✅ **Configurable Models**: Use different LLMs for each stage via configuration
✅ **Report Generation**: Produces comprehensive Markdown reports

🚧 **In Development**:
- Web search and SERP integration
- Content scraping and chunking
- Vector database storage (SQLite + VSS)
- Content-aware map-reduce summarization
- Citation extraction
- Reflection stage for completeness validation

## Architecture

The pipeline consists of 9 stages:

1. **Query Parsing**: Accept and parse user query
2. **Intent Classification**: Identify query intent
3. **Planning**: Design research approach and queries
4. **Research**: Execute searches and gather URLs (TODO)
5. **Scraping**: Extract and chunk content (TODO)
6. **Summarization**: Generate summaries with citations (TODO)
7. **Context Assembly**: Build context package (TODO)
8. **Reflection**: Validate completeness (TODO)
9. **Report Generation**: Create final report

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

# Search Configuration (for future implementation)
SERP_API_KEY=your_serp_api_key
RERANK_TOP_K=0.25

# Vector Database Configuration
VECTOR_DB_PATH=./research_db.sqlite
EMBEDDING_MODEL=text-embedding-3-small

# Output Configuration
OUTPUT_DIR=./reports
LOG_LEVEL=INFO
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

# Show research plan
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

```
rsrch/
├── cli.py                 # Main CLI entry point
├── config.py             # Configuration management
├── models.py             # Data models
├── llm_client.py         # LLM client wrapper
├── pipeline.py           # Pipeline orchestrator
├── stages/
│   ├── __init__.py
│   ├── intent_classifier.py
│   └── planner.py
├── .env.example          # Example configuration
├── requirements.txt      # Python dependencies
├── pipeline.md           # Original pipeline design
└── README.md            # This file
```

## Output

Reports are saved as Markdown files in the configured output directory (default: `./reports/`).

Example output file: `report_20250130_143022.md`

Each report includes:
- Query and intent
- Generation timestamp
- Structured content with sections
- Metadata

## Development Status

### Current Status (v0.1)

- ✅ Configuration system
- ✅ LLM client (OpenAI compatible)
- ✅ Intent classification
- ✅ Research planning
- ✅ Basic report generation
- ✅ CLI interface

### Roadmap

#### Phase 1 (Next)
- [ ] Web search integration (SERP API)
- [ ] URL scraping with BeautifulSoup
- [ ] Content chunking

#### Phase 2
- [ ] Vector database (SQLite + VSS)
- [ ] Embedding generation
- [ ] Semantic search and re-ranking

#### Phase 3
- [ ] Map-reduce summarization
- [ ] Citation extraction and tracking
- [ ] Context assembly

#### Phase 4
- [ ] Reflection stage
- [ ] Iterative research refinement
- [ ] Final report construction with citations

## litellm Usage

The pipeline uses OpenAI client which is compatible with litellm. To use litellm:

```python
from litellm import completion

# Initialize
response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
    api_key=os.getenv("API_KEY")
)

# Access response
print(response.choices[0].message.content)
```

The current implementation uses OpenAI client directly but can be easily adapted to use litellm for multi-provider support.

## Troubleshooting

### API Key Issues
- Ensure `API_KEY` is set in your `.env` file
- Check that the `.env` file is in the same directory as `cli.py`

### Module Import Errors
- Make sure you're running from the `rsrch` directory
- Install all requirements: `pip install -r requirements.txt`

### Logging
- Check `research_pipeline.log` for detailed error messages
- Use `--log-level DEBUG` for verbose output

## Contributing

This is an active development project. Key areas for contribution:

1. **Search Integration**: Implement web search and SERP parsing
2. **Scraping**: Robust content extraction from various sources
3. **Vector DB**: SQLite + VSS implementation
4. **Summarization**: Map-reduce with citation tracking
5. **Testing**: Unit and integration tests

## License

MIT

## Credits

Based on the research pipeline design documented in `pipeline.md`.
