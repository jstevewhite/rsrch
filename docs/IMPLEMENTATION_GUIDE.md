# Research Pipeline - Implementation Guide

## 🎯 Overview

You now have a **functional research pipeline CLI tool** that accepts queries and generates comprehensive reports. The system is modular, configurable, and designed for incremental enhancement.

## ✅ What's Implemented (v0.1)

### Core Infrastructure
- **Configuration System** (`config.py`): Environment-based configuration with `.env` support
- **LLM Client** (`llm_client.py`): OpenAI-compatible client with JSON mode support
- **Data Models** (`models.py`): Complete type-safe models for all pipeline stages
- **CLI Interface** (`cli.py`): Full command-line tool with logging and error handling

### Implemented Stages
1. ✅ **Query Parsing**: Accepts and structures user queries
2. ✅ **Intent Classification**: Identifies query type (informational, news, code, research, etc.)
3. ✅ **Research Planning**: Generates structured plans with sections and search queries
4. ✅ **Report Generation**: Produces Markdown reports with metadata

## 🚧 What Needs Implementation (Phases 1-4)

### Phase 1: Search & Scraping
**Files to create:**
- `stages/researcher.py` - Web search implementation
- `stages/scraper.py` - Content extraction and chunking

**Key functionality:**
- SERP API integration for web search
- URL validation and filtering
- Content scraping with BeautifulSoup
- Text chunking with overlap
- Rate limiting and error handling

### Phase 2: Vector Database
**Files to create:**
- `vector_db.py` - SQLite + VSS implementation
- `stages/embedder.py` - Embedding generation

**Key functionality:**
- SQLite database with vector search extension
- Embedding generation for chunks
- Metadata storage (URL, timestamp, chunk position)
- Semantic search and retrieval

### Phase 3: Summarization
**Files to create:**
- `stages/summarizer.py` - Map-reduce summarization
- `stages/context_assembler.py` - Context package construction

**Key functionality:**
- Map-reduce summarization strategy
- Citation extraction and tracking
- Relevance scoring and ranking
- Context package assembly for report generation

### Phase 4: Reflection & Refinement
**Files to create:**
- `stages/reflector.py` - Completeness validation

**Key functionality:**
- Gap analysis (what's missing?)
- Additional query generation
- Iterative research loops
- Confidence scoring

## 🏗️ Architecture

```
User Query
    ↓
Intent Classification ← [LLM: intent_model]
    ↓
Research Planning ← [LLM: planner_model]
    ↓
Web Search (TODO) ← [SERP API]
    ↓
Content Scraping (TODO) ← [BeautifulSoup]
    ↓
Chunking & Embedding (TODO) ← [LLM: embedding_model]
    ↓
Vector Storage (TODO) ← [SQLite + VSS]
    ↓
Summarization (TODO) ← [LLM: mrs_model]
    ↓
Context Assembly (TODO) ← [LLM: context_model]
    ↓
Reflection (TODO) ← [LLM: reflection_model]
    ↓
Report Generation ← [LLM: report_model]
    ↓
Markdown Report
```

## 🚀 Getting Started

### 1. Install and Configure
```bash
cd /Users/stwhite/CODE/rsrch
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
```

### 2. Test Current Implementation
```bash
# Basic test
python cli.py "What is machine learning?"

# Code query
python cli.py "How do I use asyncio in Python?"

# News query
python cli.py "Latest developments in quantum computing"

# Research query
python cli.py "Comparative analysis of attention mechanisms in transformers"
```

### 3. Check Output
```bash
ls -lh reports/
cat reports/report_*.md
```

## 📝 Example Usage

### Current Functionality (v0.1)

```bash
# The pipeline will:
# 1. Classify the query intent
# 2. Create a research plan with sections and queries
# 3. Generate a preliminary report based on the plan

python cli.py "What is the latest research on tirzepatide?" --log-level INFO
```

**Output:**
- Report saved to `reports/report_YYYYMMDD_HHMMSS.md`
- Log file: `research_pipeline.log`
- Console output with progress

### With Debug Logging

```bash
python cli.py "Your query" --log-level DEBUG
```

This shows detailed information about:
- LLM API calls and responses
- Model selection for each stage
- Token usage and processing time
- Intermediate results

## 🔧 Configuration Deep Dive

### Model Selection Strategy

The pipeline allows different models for different stages:

```bash
# Fast, cheap models for classification
INTENT_MODEL=gpt-4o-mini

# Powerful models for planning
PLANNER_MODEL=gpt-4o

# Balanced models for summarization
MRS_MODEL=gpt-4o-mini

# Top models for final report
REPORT_MODEL=gpt-4o
```

### Using litellm

To use litellm for multi-provider support, modify `llm_client.py`:

```python
from litellm import completion

class LLMClient:
    def complete(self, prompt, model=None, ...):
        response = completion(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self.api_key,
            base_url=self.api_endpoint,
        )
        return response.choices[0].message.content
```

This allows you to use:
- `gpt-4o-mini` (OpenAI)
- `claude-3-5-sonnet` (Anthropic)
- `gemini-pro` (Google)
- And many more!

## 🛠️ Next Steps for Development

### Immediate Priorities (Recommended Order)

1. **Add Web Search** (Most valuable)
   - Use MCP tool `search_web` or integrate SERP API
   - Implement `stages/researcher.py`
   - Return ranked list of URLs

2. **Add Content Scraping**
   - Use MCP tool `read_url` or BeautifulSoup
   - Implement `stages/scraper.py`
   - Extract clean text from HTML

3. **Add Chunking**
   - Split content into manageable chunks
   - Maintain context with overlap
   - Store metadata (URL, position)

4. **Add Summarization**
   - Implement map-reduce strategy
   - Extract citable quotes
   - Track source URLs

5. **Integrate Everything**
   - Update `pipeline.py` to use new stages
   - Add progress indicators
   - Handle errors gracefully

### Using Available MCP Tools

You have access to powerful MCP tools that can accelerate development:

**For web search:**
```python
# Use the search_web MCP tool
from call_mcp_tool import call_mcp_tool

results = call_mcp_tool(
    name="search_web",
    input={"query": "your search query", "num": 10}
)
```

**For content extraction:**
```python
# Use the read_url MCP tool
content = call_mcp_tool(
    name="read_url",
    input={"url": "https://example.com"}
)
```

**For parallel operations:**
```python
# Use parallel_search_web for multiple queries
results = call_mcp_tool(
    name="parallel_search_web",
    input={
        "searches": [
            {"query": "query 1", "num": 10},
            {"query": "query 2", "num": 10}
        ]
    }
)
```

## 📊 Testing Strategy

### Unit Tests (Future)
```bash
tests/
├── test_intent_classifier.py
├── test_planner.py
├── test_researcher.py
├── test_scraper.py
└── test_summarizer.py
```

### Integration Tests
```bash
# Test full pipeline with known queries
python -m pytest tests/integration/test_pipeline.py
```

### Manual Testing Checklist
- [ ] Different query types (news, code, research, informational)
- [ ] Various model configurations
- [ ] Error handling (API failures, invalid queries)
- [ ] Output quality and formatting
- [ ] Citation accuracy (once implemented)

## 🎓 Learning Resources

### Key Concepts
- **Map-Reduce Summarization**: Split large documents, summarize parts, combine results
- **Semantic Chunking**: Split text while preserving meaning
- **RAG (Retrieval Augmented Generation)**: Enhance LLM responses with retrieved information
- **Vector Search**: Find similar content using embeddings

### Recommended Reading
- LangChain documentation for RAG patterns
- OpenAI embeddings guide
- SQLite VSS extension documentation

## 💡 Tips for Extension

### Adding a New Stage

1. Create stage file: `stages/your_stage.py`
2. Define stage class with clear interface
3. Add to `stages/__init__.py`
4. Update `pipeline.py` to use the stage
5. Add configuration in `config.py` if needed
6. Update models in `models.py` if needed

### Example Stage Template

```python
# stages/your_stage.py
import logging
from ..models import YourInputModel, YourOutputModel
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

class YourStage:
    def __init__(self, llm_client: LLMClient, model: str):
        self.llm_client = llm_client
        self.model = model
    
    def process(self, input_data: YourInputModel) -> YourOutputModel:
        logger.info("Processing in YourStage...")
        # Your logic here
        return output_data
```

## 🐛 Debugging

### Common Issues

**Import Errors:**
```bash
# Make sure you're in the rsrch directory
cd /Users/stwhite/CODE/rsrch
python cli.py "test"
```

**API Key Issues:**
```bash
# Verify .env file
cat .env | grep API_KEY

# Test API key
python -c "from config import Config; c = Config.from_env(); print(c.api_key[:10])"
```

**Logging:**
```bash
# Check logs
tail -f research_pipeline.log

# Increase verbosity
python cli.py "test" --log-level DEBUG
```

## 📈 Performance Optimization (Future)

- Batch embedding generation
- Parallel URL scraping
- Caching of search results
- Incremental summarization
- Resume from checkpoint

## 🎯 Success Metrics

Track these to measure improvement:

- **Coverage**: Does the report address all aspects of the query?
- **Accuracy**: Are facts correct and properly cited?
- **Relevance**: Is content focused on the query?
- **Cost**: Total API costs per report
- **Speed**: Time to generate complete report

## 📞 Support

For issues or questions:
1. Check `research_pipeline.log`
2. Review this guide
3. Check README.md for troubleshooting
4. Examine stage source code for implementation details

---

**Current Version:** 0.1.0  
**Status:** Foundation complete, ready for enhancement  
**Last Updated:** 2025-01-30
