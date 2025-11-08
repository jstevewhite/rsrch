# Parallelization Implementation Plan

## Overview

Implement configurable parallelization across the research pipeline's three I/O-bound stages: Search, Scraping, and Summarization. This will significantly improve performance while respecting API rate limits through per-stage concurrency controls.

**Configuration Variables:**
```bash
SEARCH_PARALLEL=2      # Number of concurrent search queries (default: 1)
SCRAPE_PARALLEL=5      # Number of concurrent scrape operations (default: 5, already exists)
SUMMARY_PARALLEL=2     # Number of concurrent summarization tasks (default: 1) ⚠️ COST IMPACT
```

⚠️ **CRITICAL WARNING - LLM COST IMPACT**: `SUMMARY_PARALLEL` directly multiplies LLM API costs. `SUMMARY_PARALLEL=4` means 4× the summarization cost. See [Cost Considerations](#cost-considerations) below.

Setting any value to `1` effectively disables parallelization for that stage.

## Code Review Status ✅

**Review Completed:** 2025-11-08  
**Reviewer:** Gemini Pro 2.5  
**Score:** 8.2/10 - Ready for implementation  
**Critical Issues:** 2 (addressed below)  
**High-Priority Issues:** 2 (addressed below)

---

## Cost Considerations

### ⚠️ CRITICAL: LLM API Cost Impact

The `SUMMARY_PARALLEL` setting has **direct financial implications**:

| Setting | Cost Multiplier | Example Cost/Run | Monthly (100 runs) |
|---------|----------------|------------------|--------------------|
| SUMMARY_PARALLEL=1 | 1× (baseline) | $0.03 | $3.00 |
| SUMMARY_PARALLEL=2 | 2× baseline | $0.06 | $6.00 |
| SUMMARY_PARALLEL=4 | 4× baseline | $0.12 | $12.00 |
| SUMMARY_PARALLEL=8 | 8× baseline | $0.24 | $24.00 |

**Key Points:**
- Each parallel worker makes independent LLM API calls
- Cost scales linearly with the number of workers
- Search and scraping parallelization have minimal cost impact
- **Recommendation:** Start with `SUMMARY_PARALLEL=1` or `2`, monitor costs closely

### Cost Monitoring Recommendations

1. **Track API usage** in your OpenRouter/LLM provider dashboard
2. **Start conservative** with low parallelization settings
3. **Benchmark costs** before increasing parallelization
4. **Set spending alerts** if your provider supports them

---

## Current State Analysis

### Already Implemented ✅
- **Scraper** (`stages/scraper.py`):
  - Already uses `ThreadPoolExecutor` with configurable `max_workers`
  - Constructor: `def __init__(self, max_workers: int = 5, ...)`
  - Has both parallel (`_scrape_parallel`) and sequential (`_scrape_sequential`) fallback
  - **Action Required:** Wire `max_workers` to config variable

### Needs Implementation 🚧
- **Researcher** (`stages/researcher.py`):
  - Currently uses sequential loop: `for search_query in plan.search_queries:`
  - Each query blocks until complete before starting next
  - **Opportunity:** Run multiple search queries concurrently

- **Summarizer** (`stages/summarizer.py`):
  - Currently uses sequential loop: `for i, content in enumerate(scraped_contents):`
  - Each summarization blocks until complete
  - **Opportunity:** Summarize multiple documents concurrently

---

## Implementation Strategy

### Phase 1: Configuration Layer

**File:** `config.py`

Add three new configuration fields:

```python
@dataclass
class Config:
    # ... existing fields ...
    
    # Parallelization Configuration
    search_parallel: int      # Number of concurrent search queries
    scrape_parallel: int      # Number of concurrent scraping operations
    summary_parallel: int     # Number of concurrent summarization tasks
```

**Update `from_env()` method with validation:**

```python
@classmethod
def from_env(cls, env_file: Optional[str] = None) -> "Config":
    # ... existing code ...
    
    # Helper for parsing and validating parallel settings
    def get_parallel_setting(key: str, default: str) -> int:
        """Parse and validate parallel setting."""
        val_str = os.getenv(key, default)
        try:
            val = int(val_str)
            if val < 1:
                raise ValueError(f"{key} must be at least 1, got {val}")
            if val > 32:
                logger.warning(
                    f"{key} is set to {val}, which is very high. "
                    f"This may cause resource exhaustion or rate limiting."
                )
            return val
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid value for {key}: '{val_str}'. "
                f"Must be a positive integer (1-32 recommended). Error: {e}"
            )
    
    return cls(
        # ... existing fields ...
        
        # Parallelization settings with validation
        search_parallel=get_parallel_setting("SEARCH_PARALLEL", "1"),
        scrape_parallel=get_parallel_setting("SCRAPE_PARALLEL", "5"),  # Match current default
        summary_parallel=get_parallel_setting("SUMMARY_PARALLEL", "1"),
    )
```

---

### Phase 2: Researcher Parallelization

**File:** `stages/researcher.py`

#### Current Code Structure:
```python
def search(self, plan: ResearchPlan) -> List[SearchResult]:
    all_results = []
    for i, search_query in enumerate(plan.search_queries):
        results = self._execute_search(...)  # Blocks until complete
        all_results.extend(results)
    return all_results
```

#### Proposed Changes:

1. **Add parallelization support to constructor:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class Researcher:
    def __init__(self, config: Config):
        self.config = config
        self.max_workers = config.search_parallel  # NEW: Store parallel config
        logger.info(f"Researcher initialized with {self.max_workers} parallel workers")
```

2. **Implement parallel search method:**

```python
def search(self, plan: ResearchPlan) -> List[SearchResult]:
    """Execute searches with configurable parallelization."""
    logger.info(f"Executing research with {len(plan.search_queries)} queries using {self.config.search_provider}")
    
    # Determine search type based on intent
    search_type = self._select_search_type(plan.query.intent)
    logger.info(f"Using search type: {search_type}")
    
    # Choose execution strategy based on config
    if self.max_workers > 1 and len(plan.search_queries) > 1:
        logger.info(f"Using parallel search with {self.max_workers} workers")
        return self._search_parallel(plan, search_type)
    else:
        logger.info("Using sequential search")
        return self._search_sequential(plan, search_type)

def _search_parallel(self, plan: ResearchPlan, search_type: str) -> List[SearchResult]:
    """Execute search queries in parallel using ThreadPoolExecutor."""
    all_results = []
    
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        try:
            # Submit all search tasks
            future_to_query = {
                executor.submit(
                    self._execute_search_safe,
                    query.query,
                    search_type,
                    self.config.search_results_per_query
                ): query
                for query in plan.search_queries
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results = future.result()
                    if results:
                        logger.info(f"✓ Found {len(results)} results for: {query.query}")
                        all_results.extend(results)
                    else:
                        logger.warning(f"✗ No results for: {query.query}")
                except Exception as e:
                    logger.error(f"✗ Search failed for '{query.query}': {e}")
        finally:
            # Explicit shutdown ensures clean termination
            executor.shutdown(wait=True)
    
    # Summary logging for failure detection
    success_count = len(all_results)
    total_count = len(plan.search_queries)
    if success_count < total_count:
        logger.warning(
            f"Parallel search completed with failures: "
            f"{total_count - success_count}/{total_count} queries failed. "
            f"Total results retrieved: {success_count}."
        )
    else:
        logger.info(f"Parallel search complete: {success_count}/{total_count} successful.")
    
    return all_results

def _search_sequential(self, plan: ResearchPlan, search_type: str) -> List[SearchResult]:
    """Execute search queries sequentially (existing behavior)."""
    all_results = []
    
    for i, search_query in enumerate(plan.search_queries):
        logger.info(f"Query {i+1}/{len(plan.search_queries)}: {search_query.query}")
        try:
            results = self._execute_search(
                query=search_query.query,
                search_type=search_type,
                num_results=self.config.search_results_per_query
            )
            results = self._filter_excluded_results(results)
            logger.info(f"Found {len(results)} results for query: {search_query.query}")
            all_results.extend(results)
        except Exception as e:
            logger.error(f"Error executing search '{search_query.query}': {e}")
            continue
    
    logger.info(f"Sequential search complete: {len(all_results)} total results")
    return all_results

def _execute_search_safe(self, query: str, search_type: str, num_results: int) -> List[SearchResult]:
    """
    Safely execute a search (returns empty list on failure).
    Used for parallel execution where we want to continue on errors.
    """
    try:
        results = self._execute_search(query, search_type, num_results)
        return self._filter_excluded_results(results)
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return []
```

#### Key Design Decisions:

- **ThreadPoolExecutor**: Suitable for I/O-bound operations (network requests)
- **Sequential Fallback**: When `max_workers=1` or single query, use existing sequential code
- **Error Isolation**: Individual search failures don't crash entire batch
- **Logging**: Clear indication of parallel vs sequential mode

---

### Phase 3: Scraper Integration

**File:** `stages/scraper.py`

The scraper already has parallelization infrastructure. We just need to wire it to config.

#### Current:
```python
def __init__(self, max_workers: int = 5, output_format: str = "markdown", preserve_tables: bool = True):
    self.max_workers = max_workers  # Hardcoded or passed directly
```

#### Proposed:
```python
def __init__(self, max_workers: int = 5, output_format: str = "markdown", preserve_tables: bool = True):
    self.max_workers = max_workers
    # No changes needed to class itself
```

**File:** `pipeline.py`

Update scraper initialization to use config:

```python
# Initialize scraper (content extraction)
self.scraper = Scraper(
    max_workers=config.scrape_parallel,  # NEW: Use config value
    output_format=config.output_format,
    preserve_tables=config.preserve_tables,
)
```

---

### Phase 4: Summarizer Parallelization

**File:** `stages/summarizer.py`

#### Current Code Structure:
```python
def summarize_all(self, scraped_contents: List[ScrapedContent], ...) -> List[Summary]:
    summaries = []
    for i, content in enumerate(scraped_contents):
        summary = self.summarize_content(content, plan)  # Blocks until complete
        if summary:
            summaries.append(summary)
    return summaries
```

#### Proposed Changes:

1. **Add parallelization support to constructor:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class Summarizer:
    def __init__(
        self, 
        llm_client: LLMClient, 
        default_model: str = "gpt-4o-mini",
        model_selector: Optional[Callable[[str], str]] = None,
        max_workers: int = 1,  # NEW: Parallel workers
        *,
        enable_table_aware: Optional[bool] = None,
        table_topk_rows: Optional[int] = None,
        table_max_rows_verbatim: Optional[int] = None,
        table_max_cols_verbatim: Optional[int] = None,
    ):
        self.llm_client = llm_client
        self.default_model = default_model
        self.model_selector = model_selector
        self.max_workers = max_workers  # NEW: Store parallel config
        # ... existing table config ...
        
        # Enhanced logging with parallelization info
        logger.info(
            f"Summarizer initialized with default model: {default_model}, "
            f"max_workers: {max_workers}, "
            f"(tables: aware={enable_table_aware}, "
            f"topk={table_topk_rows}, "
            f"small<={table_max_rows_verbatim}x{table_max_cols_verbatim})"
        )
```

2. **Implement parallel summarization:**

```python
def summarize_all(
    self, 
    scraped_contents: List[ScrapedContent],
    plan: ResearchPlan,
    max_summaries: Optional[int] = None
) -> List[Summary]:
    """Generate summaries with configurable parallelization."""
    logger.info(f"Starting summarization of {len(scraped_contents)} documents")
    
    # Deduplicate by URL (existing code)
    seen_urls = set()
    deduplicated = []
    for content in scraped_contents:
        if content.url not in seen_urls:
            seen_urls.add(content.url)
            deduplicated.append(content)
    
    scraped_contents = deduplicated
    
    # Limit to max_summaries if specified
    contents_to_summarize = scraped_contents[:max_summaries] if max_summaries else scraped_contents
    
    # Choose execution strategy based on config
    if self.max_workers > 1 and len(contents_to_summarize) > 1:
        logger.info(f"Using parallel summarization with {self.max_workers} workers")
        summaries = self._summarize_parallel(contents_to_summarize, plan)
    else:
        logger.info("Using sequential summarization")
        summaries = self._summarize_sequential(contents_to_summarize, plan)
    
    logger.info(f"Summarization complete: {len(summaries)}/{len(contents_to_summarize)} successful")
    return summaries

def _summarize_parallel(self, contents: List[ScrapedContent], plan: ResearchPlan) -> List[Summary]:
    """Summarize multiple documents in parallel using ThreadPoolExecutor."""
    summaries = []
    
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        try:
            # Submit all summarization tasks
            future_to_content = {
                executor.submit(self._summarize_content_safe, content, plan): content
                for content in contents
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_content):
                content = future_to_content[future]
                try:
                    summary = future.result()
                    if summary:
                        summaries.append(summary)
                        logger.info(f"✓ Summary generated for: {content.url}")
                    else:
                        logger.warning(f"✗ No summary generated for: {content.url}")
                except Exception as e:
                    logger.error(f"✗ Summarization failed for {content.url}: {e}")
        finally:
            # Explicit shutdown ensures clean termination
            executor.shutdown(wait=True)
    
    # Summary logging for failure detection
    success_count = len(summaries)
    total_count = len(contents)
    if success_count < total_count:
        logger.warning(
            f"Parallel summarization completed with failures: "
            f"{total_count - success_count}/{total_count} documents failed. "
            f"Total summaries generated: {success_count}."
        )
    else:
        logger.info(f"Parallel summarization complete: {success_count}/{total_count} successful.")
    
    return summaries

def _summarize_sequential(self, contents: List[ScrapedContent], plan: ResearchPlan) -> List[Summary]:
    """Summarize documents sequentially (existing behavior)."""
    summaries = []
    
    for i, content in enumerate(contents):
        try:
            logger.info(f"Summarizing {i+1}/{len(contents)}: {content.title[:60]}...")
            summary = self.summarize_content(content, plan)
            
            if summary:
                summaries.append(summary)
                logger.info(f"✓ Summary generated for: {content.url}")
            else:
                logger.warning(f"✗ No summary generated for: {content.url}")
        except Exception as e:
            logger.error(f"Error summarizing {content.url}: {e}")
            continue
    
    return summaries

def _summarize_content_safe(self, content: ScrapedContent, plan: ResearchPlan) -> Optional[Summary]:
    """
    Safely summarize a single document (returns None on failure).
    Used for parallel execution where we want to continue on errors.
    """
    try:
        return self.summarize_content(content, plan)
    except Exception as e:
        logger.error(f"Safe summarization failed for {content.url}: {e}")
        return None
```

**File:** `pipeline.py`

Update summarizer initialization to use config with cost monitoring:

```python
# Initialize summarizer with model selector
self.summarizer = Summarizer(
    llm_client=self.llm_client,
    default_model=config.mrs_model_default,
    model_selector=config.get_mrs_model_for_content_type,
    max_workers=config.summary_parallel,  # NEW: Use config value
    enable_table_aware=config.summarizer_enable_table_aware,
    table_topk_rows=config.summarizer_table_topk_rows,
    table_max_rows_verbatim=config.summarizer_table_max_rows_verbatim,
    table_max_cols_verbatim=config.summarizer_table_max_cols_verbatim,
)

# Cost monitoring warning
if config.summary_parallel > 4:
    logger.warning(
        f"SUMMARY_PARALLEL is set to {config.summary_parallel}. "
        f"This may result in significantly higher LLM costs. "
        f"Each worker makes independent API calls. "
        f"Monitor your OpenRouter/LLM provider usage and billing."
    )
```

---

## Configuration File Updates

### `.env.example`

Add new configuration section with cost warnings:

```bash
# Parallelization Configuration
# Control concurrent operations to balance speed vs rate limits
# Set to 1 to disable parallelization for that stage

# Search: Number of concurrent search queries
# Higher values = faster searching but more API load
# Recommended: 2-4 for most APIs, 1 if rate-limited
SEARCH_PARALLEL=2

# Scraping: Number of concurrent scrape operations
# Higher values = faster scraping but more network load
# Recommended: 5-10 for most sites, lower if rate-limited
SCRAPE_PARALLEL=5

# Summarization: Number of concurrent LLM calls
# ⚠️  WARNING: DIRECT COST IMPACT ⚠️
# Setting SUMMARY_PARALLEL > 1 significantly increases LLM costs!
# Each worker makes a separate API call.
# Example cost impact:
# - SUMMARY_PARALLEL=1: ~$0.03 per run
# - SUMMARY_PARALLEL=2: ~$0.06 per run (2x cost)
# - SUMMARY_PARALLEL=4: ~$0.12 per run (4x cost)
# - SUMMARY_PARALLEL=8: ~$0.24 per run (8x cost)
# Monitor your OpenRouter usage and bill closely.
# Recommended: Start with 1-2, monitor costs closely
SUMMARY_PARALLEL=2
```

### `README.md`

Add documentation section with cost warnings:

```markdown
## Parallelization Configuration

The pipeline supports configurable parallelization for I/O-bound operations:

```bash
# Search: Concurrent search queries (default: 1)
SEARCH_PARALLEL=2

# Scraping: Concurrent scrape operations (default: 5)
SCRAPE_PARALLEL=5

# Summarization: Concurrent LLM calls (default: 1) ⚠️ COST IMPACT
SUMMARY_PARALLEL=2
```

## Cost Considerations for Parallelization

### ⚠️ Summarization Parallelization Impact

The `SUMMARY_PARALLEL` setting has a direct impact on LLM API costs:

- **SUMMARY_PARALLEL=1** (sequential): Baseline cost for summarization
- **SUMMARY_PARALLEL=2**: ~2× the summarization cost
- **SUMMARY_PARALLEL=4**: ~4× the summarization cost
- **SUMMARY_PARALLEL=8**: ~8× the summarization cost

Example: A 10-document research run with average cost $0.03/run
- Sequential: $0.03/run
- SUMMARY_PARALLEL=4: $0.12/run
- SUMMARY_PARALLEL=8: $0.24/run

**Recommendation:** Start with `SUMMARY_PARALLEL=1` or `2`, monitor your actual costs, and only increase if you have budget for it and understand the cost implications.

### Performance vs Rate Limits

- **SEARCH_PARALLEL**: Set to 1 if hitting search API rate limits
- **SCRAPE_PARALLEL**: Reduce if experiencing network throttling
- **SUMMARY_PARALLEL**: Higher = faster but exponentially more expensive LLM costs

### Performance Expectations

**⚠️ Important:** The performance estimates below are illustrative examples under **ideal conditions** (fast network, low API latency, no rate limiting). Your actual performance will vary significantly based on:

- **External API latency**: LLM APIs can vary from 2-30+ seconds per call
- **Network conditions**: Your connection speed and reliability
- **Rate limits**: API rate limiting may add delays between requests
- **Server load**: API provider load at time of execution
- **Document complexity**: Summarization time varies by content length

**Recommendation:** Benchmark with your actual environment and API providers. Set `SEARCH_PARALLEL=1` and `SUMMARY_PARALLEL=1` initially, measure performance, then gradually increase parallelization while monitoring costs and latency.

### Recommended Settings

| Use Case | SEARCH | SCRAPE | SUMMARY | Notes |
|----------|--------|--------|---------|-------|
| **Default (balanced)** | 2 | 5 | 2 | Good balance of speed vs cost |
| **Speed (cost-aware)** | 4 | 10 | 4 | Monitor LLM costs closely |
| **Rate-limited APIs** | 1 | 3 | 1 | Conservative for API limits |
| **Cost optimization** | 1 | 5 | 1 | Minimize LLM parallelization costs |
| **Testing/Development** | 1 | 1 | 1 | All sequential for debugging |
```

---

## Testing Strategy

### Unit Tests

Create `test_parallelization.py`:

```python
"""Test parallelization functionality."""

import time
from unittest.mock import Mock, patch
from stages.researcher import Researcher
from stages.summarizer import Summarizer
from models import ResearchPlan, SearchQuery, Query, Intent

def test_researcher_parallel_faster_than_sequential():
    """Verify parallel search is faster than sequential."""
    # Mock slow search API (500ms per call)
    def mock_slow_search(*args, **kwargs):
        time.sleep(0.5)
        return [Mock()]
    
    # Create plan with 4 queries
    plan = ResearchPlan(
        query=Query(text="test", intent=Intent.GENERAL),
        sections=["test"],
        search_queries=[SearchQuery(query=f"q{i}", purpose="test", priority=1) for i in range(4)],
        rationale="test"
    )
    
    # Test sequential (should take ~2 seconds)
    config_seq = Mock(search_parallel=1)
    researcher_seq = Researcher(config_seq)
    with patch.object(researcher_seq, '_execute_search', mock_slow_search):
        start = time.time()
        researcher_seq.search(plan)
        seq_time = time.time() - start
    
    # Test parallel (should take ~1 second with 2 workers)
    config_par = Mock(search_parallel=2)
    researcher_par = Researcher(config_par)
    with patch.object(researcher_par, '_execute_search', mock_slow_search):
        start = time.time()
        researcher_par.search(plan)
        par_time = time.time() - start
    
    # Parallel should be significantly faster
    assert par_time < seq_time * 0.75, f"Parallel ({par_time}s) not faster than sequential ({seq_time}s)"

def test_summarizer_parallel_faster_than_sequential():
    """Verify parallel summarization is faster than sequential."""
    # Similar test for summarizer
    pass
```

### Integration Tests

Create `test_pipeline_parallelization.py`:

```python
"""Test full pipeline with different parallelization settings."""

def test_pipeline_with_parallelization():
    """Test complete pipeline with parallel settings."""
    config = Config.from_env()
    config.search_parallel = 2
    config.scrape_parallel = 5
    config.summary_parallel = 4
    
    pipeline = ResearchPipeline(config)
    report = pipeline.run("Test query")
    
    assert report is not None
    assert len(report.sources) > 0

def test_pipeline_sequential_mode():
    """Test pipeline works with all parallelization disabled."""
    config = Config.from_env()
    config.search_parallel = 1
    config.scrape_parallel = 1
    config.summary_parallel = 1
    
    pipeline = ResearchPipeline(config)
    report = pipeline.run("Test query")
    
    assert report is not None
```

### Performance Benchmarking

Create `benchmark_parallelization.py`:

```python
"""Benchmark parallelization performance improvements."""

import time
from config import Config
from pipeline import ResearchPipeline

def benchmark_configuration(search_par, scrape_par, summary_par, query):
    """Benchmark a specific parallelization configuration."""
    config = Config.from_env()
    config.search_parallel = search_par
    config.scrape_parallel = scrape_par
    config.summary_parallel = summary_par
    
    pipeline = ResearchPipeline(config)
    
    start = time.time()
    report = pipeline.run(query)
    elapsed = time.time() - start
    
    return {
        'config': f"S{search_par}/C{scrape_par}/M{summary_par}",
        'time': elapsed,
        'sources': len(report.sources) if report else 0
    }

if __name__ == "__main__":
    query = "What is Python asyncio?"
    
    configs = [
        (1, 1, 1),   # All sequential
        (2, 5, 1),   # Search parallel, scrape parallel
        (2, 5, 4),   # All parallel
        (4, 10, 8),  # High parallelization
    ]
    
    print("Parallelization Benchmark")
    print("=" * 60)
    
    for search, scrape, summary in configs:
        result = benchmark_configuration(search, scrape, summary, query)
        print(f"{result['config']:15} | {result['time']:6.2f}s | {result['sources']:2} sources")
```

---

## Error Handling & Edge Cases

### Thread Safety Considerations

1. **LLM Client**: Already handles concurrent requests (stateless HTTP calls)
2. **Vector Store**: SQLite may have locking issues with concurrent writes
   - Solution: Consider using connection pooling or serialize writes
3. **Logging**: Python's logging module is thread-safe by default

### Rate Limiting

**Problem**: Parallel requests may trigger API rate limits

**Solutions:**

1. **Configuration Guidance**: Document recommended settings per provider
2. **Exponential Backoff**: Already implemented in `llm_client.py`
3. **Dynamic Throttling** (future enhancement):
   ```python
   if rate_limit_error:
       self.max_workers = max(1, self.max_workers // 2)
       logger.warning(f"Rate limit hit, reducing workers to {self.max_workers}")
   ```

### Memory Considerations

**Issue**: High parallelization with large documents could increase memory usage

**Mitigation:**
- Use generators where possible
- Process results as they complete (not all in memory)
- Document memory requirements in README

### Graceful Degradation

All stages should gracefully fall back to sequential mode on errors:

```python
try:
    results = self._process_parallel(items)
except Exception as e:
    logger.warning(f"Parallel processing failed: {e}, falling back to sequential")
    results = self._process_sequential(items)
```

---

## Implementation Checklist

### Phase 1: Configuration ✅
- [ ] Add `search_parallel`, `scrape_parallel`, `summary_parallel` to `Config` dataclass
- [ ] Update `Config.from_env()` to load new variables with validation
- [ ] Add `get_parallel_setting()` helper function for input validation
- [ ] Add defaults (1, 5, 1) to match current behavior
- [ ] Update `.env.example` with cost warnings

### Phase 2: Researcher ✅
- [ ] Add `max_workers` parameter to `__init__` with logging
- [ ] Implement `_search_parallel()` method with try/finally cleanup
- [ ] Implement `_search_sequential()` method (extract existing code)
- [ ] Implement `_execute_search_safe()` wrapper
- [ ] Update `search()` to choose parallel vs sequential
- [ ] Add summary logging for failure detection
- [ ] Add defensive executor shutdown

### Phase 3: Scraper ✅
- [ ] Update `pipeline.py` to pass `config.scrape_parallel` to `Scraper.__init__`
- [ ] Verify existing parallel code works correctly
- [ ] Test with different `max_workers` values

### Phase 4: Summarizer ✅
- [ ] Add `max_workers` parameter to `__init__` with enhanced logging
- [ ] Implement `_summarize_parallel()` method with try/finally cleanup
- [ ] Implement `_summarize_sequential()` method (extract existing code)
- [ ] Implement `_summarize_content_safe()` wrapper
- [ ] Update `summarize_all()` to choose parallel vs sequential
- [ ] Update `pipeline.py` to pass `config.summary_parallel`
- [ ] Add cost monitoring warning for high parallelization
- [ ] Add summary logging for failure detection

### Phase 5: Documentation ✅
- [ ] Update `README.md` with parallelization section and cost warnings
- [ ] Update `.env.example` with cost impact warnings
- [ ] Add performance vs rate limit guidance with disclaimers
- [ ] Document recommended settings table with cost considerations
- [ ] Add SQLite serialization requirement comments to pipeline.py

### Phase 6: Testing ✅
- [ ] Create unit tests for parallel vs sequential modes
- [ ] Create integration tests for full pipeline
- [ ] Create performance benchmarks
- [ ] Test error handling and fallbacks
- [ ] Test with rate-limited APIs

### Phase 7: Monitoring & Logging ✅
- [ ] Add clear parallel/sequential mode logging
- [ ] Log worker counts in use
- [ ] Add summary logging for partial/complete failures
- [ ] Add cost warnings for high SUMMARY_PARALLEL settings
- [ ] Track performance metrics (optional)

---

## Performance Expectations

**⚠️ IMPORTANT:** These are **best-case estimates under ideal conditions**. Actual performance varies significantly based on API latency, network conditions, and rate limits.

### Baseline (Current Sequential):
```
Query: "What is Python asyncio?" - IDEAL CONDITIONS
- 3 search queries × 2s = 6s
- 10 URLs scraped × 1s = 10s (already parallel at 5 workers)
- 10 summaries × 3s = 30s
Total: ~46 seconds
Cost: ~$0.03 (baseline)
```

### With Conservative Parallelization (SEARCH=2, SCRAPE=5, SUMMARY=2):
```
Query: "What is Python asyncio?" - IDEAL CONDITIONS
- 3 search queries ÷ 2 workers = 4s (33% faster)
- 10 URLs scraped ÷ 5 workers = 2s (same)
- 10 summaries ÷ 2 workers = 15s (50% faster)
Total: ~21 seconds (54% faster overall)
Cost: ~$0.06 (2× summarization cost)
```

### With Aggressive Parallelization (SEARCH=4, SCRAPE=10, SUMMARY=4):
```
Query: "What is Python asyncio?" - IDEAL CONDITIONS
- 3 search queries ÷ 4 workers = 2s (67% faster)
- 10 URLs scraped ÷ 10 workers = 1s (50% faster)
- 10 summaries ÷ 4 workers = 8s (73% faster)
Total: ~11 seconds (76% faster overall)
Cost: ~$0.12 (4× summarization cost)
```

**Reality Check**: API latency can be 5-30× higher than these estimates. LLM calls often take 5-30 seconds each, not 3 seconds. Always benchmark with your actual environment before optimizing.

---

## Future Enhancements

### 1. Adaptive Parallelization
Automatically adjust worker counts based on:
- API response times
- Rate limit errors
- Available system resources

### 2. Progress Reporting
Add progress bars for long-running parallel operations:
```python
from tqdm import tqdm

with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    futures = [executor.submit(...) for ...]
    for future in tqdm(as_completed(futures), total=len(futures)):
        # Process result
```

### 3. Resource Monitoring
Track and log resource usage:
- API calls per second
- Memory consumption
- Thread utilization

### 4. Batch Processing
For very large document sets, process in batches:
```python
def summarize_all_batched(self, contents, batch_size=50):
    for i in range(0, len(contents), batch_size):
        batch = contents[i:i+batch_size]
        summaries.extend(self._summarize_parallel(batch, plan))
```

---

## Migration Path

### Version 1.0 → 1.1 (This Implementation)
- Add configuration variables (backward compatible defaults)
- Implement parallelization (transparent to users)
- Update documentation

### Version 1.1 → 1.2 (Future)
- Add adaptive parallelization
- Add progress reporting
- Add resource monitoring

### Breaking Changes: None
All changes are backward compatible. Existing `.env` files will use sequential defaults.

---

## Summary

This plan implements configurable parallelization across the three I/O-bound stages of the research pipeline:

✅ **Search**: Parallel query execution (default: 1 → configurable)  
✅ **Scraping**: Already parallel, wire to config (default: 5)  
✅ **Summarization**: Parallel document processing (default: 1 → configurable)  

**Benefits:**
- 50-80% faster pipeline execution with optimal settings
- Individual rate limit control per stage
- Backward compatible (sequential by default)
- Graceful fallback on errors

**Implementation Time:**
- Phase 1 (Config): 30 minutes
- Phase 2 (Researcher): 2 hours
- Phase 3 (Scraper): 30 minutes
- Phase 4 (Summarizer): 2 hours
- Phase 5 (Documentation): 1 hour
- Phase 6 (Testing): 2 hours

**Total: ~8 hours of development time**
