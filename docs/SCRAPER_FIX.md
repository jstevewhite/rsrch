# Scraper scrape_url() Method Fix

## Problem Identified

The claim verification stage was failing with this error:

```
Claim: "With famine declared and over 66,000 dead, trust in international guarantees is low among Gazans."
Source: https://www.reuters.com/world/middle-east/hamas-weighs-its-response-trumps-gaza-peace-proposal-2025-09-30/
Confidence: 0.00
Reasoning: Cannot verify: Scraping error: 'Scraper' object has no attribute 'scrape_url'
```

**Root Cause**: The `ClaimVerifier` class was calling `scraper.scrape_url()` to re-scrape sources during verification, but the `Scraper` class only had a `scrape_results()` method that expected a list of `SearchResult` objects, not individual URLs.

## Solution Implemented

Added a public `scrape_url()` method to the `Scraper` class that wraps the internal `_scrape_single_url()` method.

### Code Changes

**File**: `rsrch/stages/scraper.py`

```python
def scrape_url(self, url: str, use_fallback: bool = True) -> Optional[ScrapedContent]:
    """
    Scrape a single URL.
    
    Public method for scraping individual URLs, useful for re-scraping
    sources during claim verification.
    
    Args:
        url: URL to scrape
        use_fallback: Whether to use paid API fallbacks on failure (default: True)
        
    Returns:
        ScrapedContent object, or None if scraping failed
    """
    try:
        return self._scrape_single_url(url, use_fallback=use_fallback)
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None
```

### How It Works

The new `scrape_url()` method:

1. **Takes a single URL** - No need to wrap it in a SearchResult object
2. **Uses existing scraping logic** - Calls the internal `_scrape_single_url()` method
3. **Handles fallbacks** - Supports BeautifulSoup → Jina.ai → Serper fallback chain
4. **Returns None on failure** - Gracefully handles errors instead of raising

### Usage

**Before** (didn't work):
```python
# ClaimVerifier trying to call non-existent method
scraped = self.scraper.scrape_url(source_url)  # AttributeError!
```

**After** (works):
```python
# ClaimVerifier can now call the public method
scraped = self.scraper.scrape_url(source_url)  # ✓ Works!
if scraped and scraped.content:
    # Use the content for verification
    ...
```

## Testing

### Unit Tests

Run the scraper URL method tests:

```bash
cd /Users/stwhite/CODE
python -m rsrch.test_scraper_url
```

**Expected output:**

```
✅ Scraper has scrape_url() method
✅ Method signature: scrape_url(url, use_fallback)
✅ Method has required 'url' parameter
✅ Successfully scraped example.com
✅ ClaimVerifier initialized successfully with Scraper
✅ ClaimVerifier can access scraper.scrape_url() method

Test Summary
Scraper.scrape_url() test: ✅ PASSED
ClaimVerifier integration test: ✅ PASSED
```

### Integration Testing

The fix is automatically used by the claim verification stage (Stage 10):

1. **Claim Extraction** - Extracts claims from report
2. **Source Grouping** - Groups claims by source URL
3. **Re-scraping** - Calls `scraper.scrape_url()` for each source ✓ Now works!
4. **Verification** - Verifies claims against fresh content
5. **Report Annotation** - Appends verification results

## Impact

### Before Fix

```
Verifying claims from source: https://reuters.com/...
ERROR - Scraping error: 'Scraper' object has no attribute 'scrape_url'
Confidence: 0.00
Reasoning: Cannot verify: Scraping error
```

**Result**: All claims marked as unverifiable with 0.00 confidence

### After Fix

```
Verifying claims from source: https://reuters.com/...
✓ Primary scraper succeeded for: https://reuters.com/...
INFO - Verified 3 claims from source
Confidence: 0.85
Verdict: supported
Evidence: "exact quote from source..."
```

**Result**: Claims are properly verified with evidence and confidence scores

## Files Modified

1. **`rsrch/stages/scraper.py`** - Added public `scrape_url()` method

## Files Created

1. **`test_scraper_url.py`** - Unit tests for scrape_url() method
2. **`docs/SCRAPER_FIX.md`** - This documentation

## Behavior Comparison

### Scraping Methods Available

| Method | Input | Use Case | Status |
|--------|-------|----------|--------|
| `scrape_results()` | `List[SearchResult]` | Batch scraping during research | ✓ Existing |
| `scrape_url()` | `str` (single URL) | Individual URL scraping for verification | ✓ New |
| `_scrape_single_url()` | `str` | Internal method | ✓ Private |

### Fallback Strategy (Both Methods)

Both methods use the same fallback chain:

1. **Primary**: BeautifulSoup (free, works for most sites)
2. **Fallback 1**: Jina.ai r.jina.ai (handles JavaScript)
3. **Fallback 2**: Serper scrape API (final fallback)

## Future Enhancements

Potential improvements:

1. **Caching** - Cache scraped content to avoid re-scraping during verification
2. **Batch re-scraping** - Scrape multiple sources in parallel during verification
3. **Freshness check** - Only re-scrape if cached content is stale
4. **Rate limiting** - Respect site rate limits when re-scraping

## Related Components

- **ClaimVerifier** (`rsrch/stages/verifier.py`) - Uses `scrape_url()` for re-scraping
- **Scraper** (`rsrch/stages/scraper.py`) - Provides scraping functionality
- **Pipeline** (`rsrch/pipeline.py`) - Orchestrates verification stage

## Verification

To verify the fix is working in your pipeline:

1. **Enable verification** in `.env`:
   ```bash
   VERIFY_CLAIMS=true
   ```

2. **Run a query** that generates a report with sources

3. **Check logs** for successful scraping:
   ```
   INFO - Verifying 3 claims from source 1/2: https://...
   DEBUG - Re-scraping https://...
   INFO - ✓ Primary scraper succeeded for: https://...
   ```

4. **Check report** for verification appendix with confidence scores > 0.00

If you see confidence scores > 0.00 and actual evidence quotes, the fix is working correctly!
