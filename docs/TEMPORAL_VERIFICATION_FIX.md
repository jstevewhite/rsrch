# Temporal Context in Claim Verification Fix

## Problem Identified

The claim verification stage was incorrectly marking claims as "UNSUPPORTED" when they contained facts that conflicted with the LLM's training data, even when the source explicitly stated those facts.

### Example Error

```
❌ Claim 1: UNSUPPORTED
Claim: "In September 2025, former U.S. President Donald Trump—now serving as President—unveiled a 20-point peace plan..."
Source: https://6abc.com/post/...
Confidence: 0.00
Reasoning: The claim is entirely unsupported as it incorrectly states that Trump is serving as President in 2025...
Evidence: "The source does not mention Donald Trump serving as President in 2025..."
```

**But the source actually said:**
> "**President Donald Trump** on Monday laid out a 20-point proposal..."

**Root Cause**: The LLM was using its training data (which has Trump not being President in 2025) to override what the source explicitly stated, violating the core principle of source-based verification.

## Solution Implemented

Added explicit temporal context and training data override instructions to the verification prompt.

### Key Changes

**File**: `rsrch/stages/verifier.py`

#### 1. Added Date Context Helper

```python
@staticmethod
def _get_current_date_context() -> str:
    """Get current date context for verification prompt."""
    from datetime import datetime
    now = datetime.now()
    return f"{now.strftime('%B %d, %Y')} ({now.year})"
```

#### 2. Enhanced Verification Prompt

**Before**:
```python
prompt = f"""
TASK: Verify if these claims are supported by the source content.

SOURCE: {source_url}
CLAIMS TO VERIFY: ...
SOURCE CONTENT: ...
```

**After**:
```python
# Get current date context
current_date = self._get_current_date_context()
source_date = scraped.retrieved_at.strftime('%B %d, %Y') if scraped.retrieved_at else "Unknown"

prompt = f"""
TASK: Verify if these claims are supported by the source content.

IMPORTANT VERIFICATION CONTEXT:
- Current date: {current_date}
- Source retrieved: {source_date}
- Your task is to verify claims based ONLY on what the source states
- IGNORE any conflicts with your training data
- If the source explicitly states a fact, accept it as stated in the source
- Example: If source says "President Trump" in 2025, verify based on source text, not your training knowledge
- Focus on: Does the SOURCE support the claim? Not: Does your training data support it?

SOURCE: {source_url}
...
```

### What Changed

The new prompt explicitly instructs the LLM to:

1. **Prioritize source over training data** - "verify claims based ONLY on what the source states"
2. **Ignore training data conflicts** - "IGNORE any conflicts with your training data"
3. **Use concrete examples** - "If source says 'President Trump' in 2025, verify based on source text"
4. **Focus on source-based verification** - "Does the SOURCE support the claim? Not: Does your training data support it?"

## Testing

### Unit Tests

Run the temporal verification tests:

```bash
cd /Users/stwhite/CODE
python -m rsrch.test_temporal_verification
```

**Expected output:**

```
✅ Current date: Present
✅ Source retrieved: Present
✅ Training data warning: Present
✅ Trump example: Present
✅ Source focus: Present
✅ Source-based verdict: Present

✅ SUCCESS! All temporal context elements present
```

### Integration Testing

The fix is automatically used by the claim verification stage (Stage 10).

## Impact

### Before Fix

```
Claim: "President Trump announced a plan in 2025"
Source: "President Donald Trump on Monday laid out a 20-point proposal..."

❌ Verdict: UNSUPPORTED
Confidence: 0.00
Reasoning: Trump is not President in 2025 (based on training data)
```

### After Fix

```
Claim: "President Trump announced a plan in 2025"
Source: "President Donald Trump on Monday laid out a 20-point proposal..."

✅ Verdict: SUPPORTED
Confidence: 0.95
Evidence: "President Donald Trump on Monday laid out a 20-point proposal..."
Reasoning: Source explicitly states Trump is President and made the announcement
```

## Why This Happens

### LLM Training Data Cutoffs

Most LLMs have training data cutoffs:

- **GPT-4**: September 2021
- **GPT-4 Turbo**: April 2023  
- **GPT-4o**: October 2023
- **Claude 3**: August 2023

When verifying claims about events **after** their training cutoff, LLMs may:

1. ❌ Reject facts that contradict training data (e.g., "Trump is President in 2025")
2. ❌ Apply outdated knowledge (e.g., "COVID-19 is a new disease")
3. ❌ Miss recent developments (e.g., new political leaders, company mergers)

### The Fix

By explicitly instructing the model to:
- Prioritize source content over training data
- Ignore temporal conflicts
- Focus only on what the source states

We align the model's behavior with source-based fact-checking principles.

## Files Modified

1. **`rsrch/stages/verifier.py`** - Added temporal context to verification prompt

## Files Created

1. **`test_temporal_verification.py`** - Unit tests for temporal context
2. **`docs/TEMPORAL_VERIFICATION_FIX.md`** - This documentation

## Verification Behavior

### What the Model Should Do

✅ **Source says "President Trump in 2025"** → Verify as supported (ignore training data)
✅ **Source says "Biden won 2020"** → Verify as supported (matches training data)
✅ **Claim about 2026 event** → Verify based only on source, not training data
✅ **Recent CEO appointment** → Verify based on source, not outdated training data

### What the Model Should NOT Do

❌ Use training data to contradict explicit source statements
❌ Apply pre-training cutoff knowledge to post-cutoff claims
❌ Reject claims simply because they differ from training data

## Limitations

### This Fix Does NOT:

1. **Update training data** - The model still has outdated knowledge
2. **Make model omniscient** - It can only verify what sources state
3. **Fix all hallucinations** - Model may still misread sources

### This Fix DOES:

1. ✅ Prevent training data from overriding explicit source statements
2. ✅ Improve verification accuracy for temporal claims
3. ✅ Align behavior with fact-checking best practices

## Alternative Solutions Considered

### 1. Use More Recent Models ❌

**Pro**: Less likely to have conflicts  
**Con**: Still have cutoff dates, expensive, may not be available

### 2. Post-Process Verification Results ❌

**Pro**: Can detect and flag conflicts  
**Con**: Doesn't prevent the issue, adds complexity

### 3. Explicitly Override in Prompt ✅ **(Chosen)**

**Pro**: Simple, effective, no API changes  
**Con**: Relies on prompt following

## Future Enhancements

Potential improvements:

1. **Temporal conflict detection** - Automatically detect when claims involve dates after training cutoff
2. **Confidence adjustment** - Boost confidence when source explicitly supports claim regardless of training data
3. **Training cutoff awareness** - Include model-specific training cutoffs in prompt
4. **Alternative model fallback** - Use more recent model for temporal claims

## Related Issues

This fix addresses a class of problems where LLMs:

- Reject claims about recent events
- Apply outdated political/organizational knowledge
- Contradict sources based on training data
- Fail to verify facts after training cutoff

All of these stem from **training data conflicts** and are mitigated by this fix.

## Monitoring

Watch for verification results with:

- **Low confidence** on factual claims with clear source support
- **"UNSUPPORTED" verdicts** when source explicitly states the fact
- **Reasoning mentioning training data** (e.g., "This contradicts known facts")

If you see these patterns, the temporal context fix may need strengthening or the model may need additional prompt engineering.

## Success Metrics

The fix is working if:

✅ Claims like "President Trump in 2025" are verified as supported when source states it  
✅ Confidence scores reflect source support, not training data  
✅ Reasoning focuses on source content, not external knowledge  
✅ Evidence quotes are from the source, not fabricated

## Example Prompt (Full)

```
TASK: Verify if these claims are supported by the source content.

IMPORTANT VERIFICATION CONTEXT:
- Current date: October 01, 2025 (2025)
- Source retrieved: October 01, 2025
- Your task is to verify claims based ONLY on what the source states
- IGNORE any conflicts with your training data
- If the source explicitly states a fact, accept it as stated in the source
- Example: If source says "President Trump" in 2025, verify based on source text, not your training knowledge
- Focus on: Does the SOURCE support the claim? Not: Does your training data support it?

SOURCE: https://example.com

CLAIMS TO VERIFY:
[
  {
    "id": 0,
    "claim": "President Trump announced a plan in September 2025",
    "type": "factual"
  }
]

SOURCE CONTENT:
President Donald Trump on Monday laid out a 20-point proposal...

---

For EACH claim, analyze:
1. Is it explicitly stated in the source? (direct support)
2. Is it strongly implied by the source? (indirect support)
...

GUIDELINES:
- Be strict: only "supported" if clearly stated or strongly implied IN THE SOURCE
- Use "contradicted" ONLY if the source explicitly contradicts it (not your training data)
- Provide exact quotes from the source as evidence when possible
- Confidence scale: 0.9-1.0 = very confident in verdict based on source
```

This explicit framing helps the model stay grounded in the source rather than its training data.
