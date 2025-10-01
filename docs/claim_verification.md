# Claim Verification Stage

## Overview

The claim verification stage (Stage 10) is an **optional quality control mechanism** that extracts claims from generated reports and verifies them against the original source material. This ensures factual accuracy and catches potential hallucinations or misattributions.

## How It Works

### High-Level Flow

```
Generated Report
    ↓
Extract all claims with [Source N] citations
    ↓
Group claims by source URL
    ↓
For each source:
    - Re-scrape the URL (fresh content)
    - Submit full page + all claims to LLM
    - Get verification results for all claims at once
    ↓
Aggregate results across all sources
    ↓
Annotate report with verification appendix
```

### Key Design Decisions

1. **Batch Verification**: All claims from one source are verified together in a single LLM call
2. **Fresh Content**: Re-scrapes sources to verify against current data
3. **Full Context**: LLM sees the complete source page, not just snippets
4. **Optional**: Adds ~30-60s and ~$0.04-0.05 per report, so it's disabled by default

## Configuration

### Enable Verification

In `.env`:

```env
# Verification Configuration (Optional - adds ~30-60s and ~$0.04-0.05 per report)
VERIFY_CLAIMS=true  # Enable claim verification stage
VERIFY_MODEL=gpt-4o-mini  # Model for verification (cheap is fine)
VERIFY_CONFIDENCE_THRESHOLD=0.7  # Flag claims below this confidence
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `VERIFY_CLAIMS` | `false` | Enable/disable verification stage |
| `VERIFY_MODEL` | `gpt-4o-mini` | Model to use (cheap models work well) |
| `VERIFY_CONFIDENCE_THRESHOLD` | `0.7` | Flag claims with confidence below this |

## Implementation

### Stage 1: Claim Extraction

**Class**: `ClaimExtractor`

Extracts factual claims from the report that have source citations:

```python
claims_by_source = claim_extractor.extract_and_group(
    report_text=report.content,
    summaries=final_summaries
)
# Returns: {
#   "https://example.com/article1": [claim1, claim2, claim3],
#   "https://arxiv.org/paper": [claim4, claim5],
# }
```

**What it extracts**:
- Factual statements with [Source N] citations
- Statistics and numbers
- Quotes from sources
- Dates and temporal claims

**What it skips**:
- Opinions and analysis
- Unsourced statements
- The model's own commentary

### Stage 2: Claim Verification

**Class**: `ClaimVerifier`

For each source URL:
1. Re-scrapes the source (fresh content)
2. Submits full page + all claims to LLM
3. Gets verification results for all claims

```python
results_by_source = claim_verifier.verify_all_sources(claims_by_source)
```

**Verdict Types**:
- `supported`: Explicitly stated or strongly implied
- `partial`: Approximately correct but imprecise
- `unsupported`: Not mentioned in source
- `contradicted`: Source says the opposite

**Confidence Scores**:
- `0.9-1.0`: Very confident in verdict
- `0.7-0.9`: Confident
- `0.5-0.7`: Uncertain
- `<0.5`: Very uncertain

### Stage 3: Report Annotation

**Class**: `VerificationReporter`

Creates verification summary and adds appendix to report:

```python
verification_summary = verification_reporter.create_summary(results_by_source)
report = verification_reporter.annotate_report(report, verification_summary)
```

## Output

### Metadata

Verification results are added to report metadata:

```python
report.metadata["verification"] = {
    "total_claims": 50,
    "supported": 47,
    "partial": 2,
    "unsupported": 1,
    "contradicted": 0,
    "avg_confidence": 0.89,
    "flagged_count": 3,
    "verification_pass": False,  # True if no flagged claims
}
```

### Verification Appendix

A detailed appendix is added to the report:

```markdown
# Verification Report

## Summary
- **Total Claims**: 50
- **Fully Supported**: 47 (94%)
- **Partially Supported**: 2 (4%)
- **Unsupported**: 1 (2%)
- **Average Confidence**: 0.89

## Flagged Claims

The following 3 claims require attention:

### ⚠️ Claim 1: PARTIAL

**Claim**: "The plan demands Hamas release all remaining hostages within 48 hours"

- **Source**: https://example.com/article1
- **Confidence**: 0.65
- **Reasoning**: Source mentions hostage release demand but does not specify "48 hours"
- **Evidence**: "The plan includes demands for the immediate release of all hostages held by Hamas"

### ❌ Claim 2: UNSUPPORTED

**Claim**: "The plan has been endorsed by 15 Arab nations"

- **Source**: https://example.com/article2
- **Confidence**: 0.92
- **Reasoning**: Source does not mention any endorsements
- **Evidence**: No mention found in source content

## By-Source Analysis

**Source**: https://example.com/article1
- Claims verified: 25
- Supported: 24 (96%)
- Flagged: 1
- Avg confidence: 0.91

**Source**: https://example.com/article2
- Claims verified: 15
- Supported: 13 (87%)
- Flagged: 2
- Avg confidence: 0.85
```

## Cost & Performance

### Cost Estimate (per report)

Assuming typical report with:
- 10 sources
- 50 claims total
- Using `gpt-4o-mini` (~$0.15/1M input, $0.60/1M output)

**Breakdown**:
1. Claim extraction: ~$0.001 (5K tokens in, 1K out)
2. Verification (10 sources × 20K tokens each): ~$0.04 (220K tokens total)

**Total**: ~$0.04-0.05 per report

### Time Estimate

- Claim extraction: 2-3 seconds
- Re-scraping 10 sources: 10-20 seconds (parallel)
- Verification LLM calls: 10-30 seconds (depends on content size)

**Total overhead**: ~30-60 seconds

## When to Use Verification

### ✅ Use verification when:
- Accuracy is critical (e.g., medical, legal, financial research)
- Reports will be used for decision-making
- High-stakes situations where errors are costly
- Debugging report quality issues
- Building trust with users

### ⚠️ Consider skipping when:
- Cost/time budget is tight
- Exploratory research (initial drafts)
- Low-stakes queries
- Sources are highly trusted (e.g., official docs)
- Report is clearly marked as preliminary

## Troubleshooting

### High Number of Flagged Claims

**Possible causes**:
1. **Source-grounding not working**: Check that source-grounding instructions are enabled
2. **Model hallucinating**: Try using a different model for report generation
3. **Sources changed**: Re-scraping may show different content than during summarization
4. **Threshold too high**: Lower `VERIFY_CONFIDENCE_THRESHOLD` to reduce false flags

**Solutions**:
- Review flagged claims manually
- Adjust confidence threshold
- Improve source-grounding instructions
- Use more capable models

### Verification Takes Too Long

**Possible causes**:
1. **Many sources**: Each source requires re-scraping + LLM call
2. **Large sources**: Big pages take longer to process
3. **Slow model**: Some models are slower than others

**Solutions**:
- Use `gpt-4o-mini` (fast and cheap)
- Implement parallel verification (future enhancement)
- Skip verification for low-stakes reports

### Sources Unavailable

If a source can't be re-scraped (404, paywall, etc.):
- Claims from that source are marked as "unsupported"
- Reasoning indicates "Cannot verify: Source unavailable"
- Consider using cached scraped content (future enhancement)

## Future Enhancements

### 1. Parallel Verification
Process multiple sources simultaneously:
```python
# Instead of sequential
for url in sources:
    verify(url)

# Use parallel
with ThreadPoolExecutor() as executor:
    results = executor.map(verify, sources)
```

### 2. Use Cached Content
Option to verify against originally scraped content instead of re-scraping:
```python
VERIFY_USE_CACHED=true  # Use original scraped content
```

**Pros**: Faster, no re-scraping failures
**Cons**: Doesn't catch if source changed

### 3. Selective Verification
Only verify high-risk claim types:
```python
VERIFY_CLAIM_TYPES=statistic,quote,date  # Skip general factual claims
```

### 4. Confidence-Based Retry
Automatically retry low-confidence claims with a better model:
```python
if result.confidence < 0.5:
    result = verify_with_better_model(claim, source)
```

### 5. Human-in-the-Loop
Interactive mode for reviewing flagged claims:
```python
for flagged_claim in flagged_claims:
    action = ask_user(flagged_claim)  # keep, edit, remove
    apply_action(report, flagged_claim, action)
```

## Example Usage

### Python API

```python
from config import Config
from pipeline import ResearchPipeline

# Enable verification
config = Config.from_env()
config.verify_claims = True
config.verify_model = "gpt-4o-mini"

# Run pipeline
pipeline = ResearchPipeline(config)
report = pipeline.run("What is the latest on the Israel-Hamas peace negotiations?")

# Check verification results
if "verification" in report.metadata:
    v = report.metadata["verification"]
    print(f"Verification: {v['supported']}/{v['total_claims']} claims supported")
    print(f"Flagged: {v['flagged_count']} claims")
```

### Command Line

```bash
# Enable in .env
export VERIFY_CLAIMS=true

# Run research
python main.py "What is the latest on climate change?"

# Report will include verification appendix
```

## Comparison with Other Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **Per-claim verification** | Fine-grained | Expensive (N LLM calls) |
| **Batch by source** ✓ | Efficient, contextual | May miss cross-source issues |
| **RAG verification** | Very accurate | Requires vector DB setup |
| **Rule-based** | Fast, cheap | Brittle, limited |
| **Human review** | Most accurate | Slow, expensive |

Our batch-by-source approach balances accuracy, cost, and speed.

## Data Models

### ExtractedClaim

```python
@dataclass
class ExtractedClaim:
    text: str              # The claim text
    source_number: int     # Which [Source N] cited
    source_url: str        # Actual URL
    claim_type: str        # factual|statistic|quote|date
    context: str           # Surrounding text
```

### VerificationResult

```python
@dataclass
class VerificationResult:
    claim: ExtractedClaim
    verdict: str           # supported|partial|unsupported|contradicted
    confidence: float      # 0.0 to 1.0
    evidence: Optional[str]  # Supporting quote
    reasoning: str         # Brief explanation
```

### VerificationSummary

```python
@dataclass
class VerificationSummary:
    total_claims: int
    supported_claims: int
    partial_claims: int
    unsupported_claims: int
    contradicted_claims: int
    flagged_claims: List[VerificationResult]
    avg_confidence: float
    by_source: Dict[str, List[VerificationResult]]
```

## Architecture

```
Pipeline
    └── Stage 10: Verification (optional)
            ├── ClaimExtractor
            │   └── Extracts claims from report
            │       └── Groups by source URL
            ├── ClaimVerifier
            │   └── For each source:
            │       ├── Re-scrape URL
            │       ├── Verify all claims at once
            │       └── Return results
            └── VerificationReporter
                ├── Create summary statistics
                ├── Generate appendix
                └── Annotate report
```

---

**Status**: ✅ Implemented (October 1, 2025)  
**Default**: Disabled (set `VERIFY_CLAIMS=true` to enable)  
**Cost**: ~$0.04-0.05 per report  
**Time**: ~30-60 seconds overhead
