# Remediation Plan: Remaining Issues

## Issue 5: EmbeddingClient makes N sequential API calls instead of batching

**File:** `stages/context_assembler.py:69-92`

**Problem:** `generate_embeddings_batch()` loops over texts one at a time, making a separate HTTP request per text. The OpenAI embeddings API accepts a list of inputs natively. For 20 summaries this means 20 round-trips instead of 1.

Additionally, the fallback zero vector at line 90 hardcodes 1536 dimensions, which silently produces wrong similarity scores if a different embedding model is used.

**Fix:**

1. Rewrite `generate_embeddings_batch()` to send all texts in a single API call:

```python
def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
    url = f"{self.api_url}/embeddings"
    headers = {"Content-Type": "application/json"}
    if self.api_key:
        headers["Authorization"] = f"Bearer {self.api_key}"

    payload = {"input": texts, "model": self.model}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        # Sort by index to guarantee order matches input
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        raise
```

2. Remove the hardcoded 1536-dimension fallback. If embedding fails, let the error propagate -- a zero vector silently corrupts ranking.

3. If there's a concern about batch size limits, add chunking at a safe batch size (e.g., 2048 texts per call) inside this method.

**Files changed:** `stages/context_assembler.py`

---

## Issue 6: VectorStore connection leaks on exceptions

**File:** `stages/context_assembler.py:127-157, 159-200, 230-253`

**Problem:** Every `VectorStore` method manually calls `conn = self._connect()` and `conn.close()`. If an exception occurs between these calls, the connection is never closed. This leaks file descriptors over time and can cause "too many open files" errors on long runs.

**Fix:**

1. Make `_connect()` return a context manager (sqlite3 connections already support `with`). Update every method to use `with self._connect() as conn:` instead of manual open/close.

2. Specific changes in each method:

**`_init_db()`** (lines 127-157):
```python
def _init_db(self):
    with self._connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS summaries (...)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS embeddings (...)""")
        conn.commit()
    logger.info(f"Vector store initialized at: {self.db_path}")
```

**`store_summaries()`** (lines 159-200):
```python
def store_summaries(self, summaries, embeddings):
    with self._connect() as conn:
        cursor = conn.cursor()
        summary_ids = []
        for summary, embedding in zip(summaries, embeddings):
            cursor.execute(...)
            summary_id = cursor.lastrowid
            summary_ids.append(summary_id)
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            cursor.execute(...)
        conn.commit()
    return summary_ids
```

**`get_embedding()`** (lines 202-227):
```python
def get_embedding(self, summary_id):
    with self._connect() as conn:
        cursor = conn.cursor()
        cursor.execute(...)
        row = cursor.fetchone()
    # process row outside the with block
```

**`search_similar_in_ids()`** (lines 230-253):
Same pattern -- wrap in `with self._connect() as conn:`.

Note: `sqlite3.connect()` used as a context manager handles commit/rollback but does NOT close the connection. We need a small wrapper:

```python
from contextlib import contextmanager

@contextmanager
def _connect(self):
    conn = sqlite3.connect(str(self.db_path))
    # register cosine_sim function
    conn.create_function("cosine_sim", 3, _cosine_sim_sql)
    try:
        yield conn
    finally:
        conn.close()
```

Move the `_cosine_sim_sql` function to module level or a static method so it can be referenced cleanly.

**Files changed:** `stages/context_assembler.py`

---

## Issue 7: Verifier re-scrapes URLs already scraped in stage 5

**File:** `stages/verifier.py:313-322`, `pipeline.py:308-320`

**Problem:** `ClaimVerifier.verify_source_claims()` re-scrapes each source URL (line 316: `self.scraper.scrape_url(source_url)`). The pipeline already scraped these URLs in stage 5 and has the content in `scraped_content`. This doubles HTTP requests and slows down verification.

**Fix:**

1. In `pipeline.py`, accumulate all scraped content across iterations (similar to `all_summaries`). Build a `dict[url, ScrapedContent]` cache:

```python
# Before the iteration loop (after line 175):
all_scraped: Dict[str, ScrapedContent] = {}

# Inside the loop, after scraping (after line 213):
for sc in scraped_content:
    all_scraped[sc.url] = sc
```

2. Pass the cache to `verify_all_sources()`:

```python
results_by_source = self.claim_verifier.verify_all_sources(
    claims_by_source, scraped_cache=all_scraped
)
```

3. In `ClaimVerifier`, add `scraped_cache` parameter to `verify_all_sources()` and `verify_source_claims()`. Look up the cache first; only re-scrape on cache miss:

```python
def verify_source_claims(self, source_url, claims, scraped_cache=None):
    # Try cache first
    if scraped_cache and source_url in scraped_cache:
        scraped = scraped_cache[source_url]
        logger.debug(f"Using cached content for {source_url}")
    else:
        logger.debug(f"Re-scraping {source_url}...")
        scraped = self.scraper.scrape_url(source_url)

    if not scraped or not scraped.content:
        return self._mark_unverifiable(claims, "Source unavailable or empty")
    # ... rest unchanged
```

4. Add `from ..models import ScrapedContent` import and `Dict` to verifier imports.

**Files changed:** `pipeline.py`, `stages/verifier.py`

---

## Issue 8: Pipeline continues silently on zero search results

**File:** `pipeline.py:186-193`

**Problem:** If the search stage fails or returns zero results (line 193: `search_results = []`), the pipeline continues through scraping, summarization, and report generation with no data. The report generation fallback prompt (line 438-458) has no source material and will produce a hallucinated report based purely on LLM training data.

**Fix:**

After the search stage, check for empty results on the first iteration. If we have zero search results AND zero accumulated summaries, raise or return early with a clear error:

```python
# After Stage 4 (line 193), add:
if not search_results and not all_summaries:
    if iteration == 1:
        logger.error("No search results found on initial research iteration")
        raise RuntimeError(
            "Search returned no results. Check your search provider "
            "configuration and API key. Query: " + query_text[:100]
        )
```

On subsequent iterations (iteration > 1), empty results are acceptable since we already have summaries from prior iterations -- no change needed there.

**Files changed:** `pipeline.py`

---

## Issue 9: Planner retry wraps LLMClient retry (up to 12 API calls)

**File:** `stages/planner.py:15-16, 65-120`

**Problem:** `Planner.plan()` has its own retry loop (`MAX_RETRIES = 2`, so 3 total attempts at lines 66-112). Inside each attempt, it calls `self.llm_client.complete_json()` which has its own retry loop (default `max_retries=3`). A transient failure can produce 3 x 3 = 9 API calls, or up to 12 with the planner's extra attempt.

The planner's retry exists to handle the case where the LLM returns valid JSON but with empty `sections` or `search_queries`. But the retry-on-network-error case is already covered by `complete_json`.

**Fix:**

Remove the outer retry loop and let `complete_json`'s retries handle transient errors. Keep only the validation logic:

```python
def plan(self, query: Query) -> ResearchPlan:
    logger.info(f"Planning research for query: {query.text[:100]}...")
    # ... build prompt ...

    response = self.llm_client.complete_json(
        prompt=prompt,
        model=self.model,
        temperature=0.3,
        max_tokens=2000,
    )

    sections = response.get("sections", [])
    search_queries_data = response.get("search_queries", [])
    rationale = response.get("rationale", "")

    if not sections or not search_queries_data:
        raise RuntimeError(
            "Research planning failed: LLM returned empty sections or queries. "
            "Try a different planner model or rephrase the query."
        )

    search_queries = [
        SearchQuery(query=sq["query"], purpose=sq["purpose"], priority=sq.get("priority", 3))
        for sq in search_queries_data
    ]

    plan = ResearchPlan(query=query, sections=sections,
                        search_queries=search_queries, rationale=rationale)
    logger.info(f"Created plan with {len(sections)} sections and {len(search_queries)} queries")
    return plan
```

Also remove the now-unused `MAX_RETRIES`, `RETRY_DELAY` class attributes and `import time`.

**Files changed:** `stages/planner.py`

---

## Issue 10: `any` (lowercase) used as type annotation

**File:** `stages/reranker.py:16, 303`

**Problem:** `original_item: any` (line 16) and `search_results: List[any]` (line 303) use Python's builtin `any` function as a type annotation instead of `typing.Any`. This doesn't cause a runtime error (dataclass field annotations aren't enforced), but it's incorrect and confuses type checkers.

**Fix:**

1. Add `Any` to the existing `typing` import at line 5:

```python
from typing import List, Optional, Tuple, Any
```

2. Change line 16:
```python
original_item: Any
```

3. Change line 303:
```python
def rerank_search_results(self, query: str, search_results: List[Any]) -> List[Any]:
```

**Files changed:** `stages/reranker.py`
