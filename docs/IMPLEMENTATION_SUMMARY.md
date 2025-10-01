# Implementation Summary: Model Routing + Source Grounding

## What Was Implemented

### 1. Content-Aware Model Routing (October 1, 2025)

**Problem**: Need different models for different content types (research papers vs. code vs. news).

**Solution**: URL-based heuristics + flexible model configuration.

**Files Changed**:
- `stages/content_detector.py` - NEW: Content type detection
- `stages/summarizer.py` - Updated: Model selection by content type
- `config.py` - Updated: MRS model routing configuration
- `pipeline.py` - Updated: Wire up model selector
- `.env` - Updated: Content-specific model configuration

**Details**: See `docs/model_routing.md`

---

### 2. Source-Grounding Instructions (October 1, 2025)

**Problem**: Models "correct" current information based on outdated training data.

**Examples**:
- ❌ "former U.S. President Donald Trump" (when he's the current president)
- ❌ Adding "as of 2024" or "at the time" to current events
- ❌ Contradicting scraped content with training knowledge

**Solution**: Strong meta-instructions to prioritize source content over parametric knowledge.

**Files Changed**:
- `stages/summarizer.py` - Added: `_get_source_grounding_context()` method
- `pipeline.py` - Updated: Report generation with source-grounding

**Key Innovation**: Instead of enumerating facts, we tell the model **HOW to behave**:

```python
"""
CRITICAL INSTRUCTIONS - SOURCE PRIORITIZATION:

YOU MUST FOLLOW THESE RULES ABSOLUTELY:

1. TRUST THE SOURCE MATERIAL COMPLETELY
   - If the source contradicts what you "know", the SOURCE IS CORRECT
   
2. NEVER CORRECT OR "FIX" THE SOURCE
   - Do not change names, titles, positions, dates, or facts
   
3. SUMMARIZE WHAT IS WRITTEN, NOT WHAT YOU THINK
   - Report exactly what the source says
   
4. WHEN IN DOUBT, QUOTE THE SOURCE

REMEMBER: The source material reflects REALITY. Your training data reflects THE PAST.
"""
```

**Details**: See `docs/source_grounding.md`

---

## Quick Start

### Model Routing

1. **Basic setup** (use default for everything):
   ```env
   MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
   ```

2. **Specialized models**:
   ```env
   MRS_MODEL_DEFAULT=qwen/qwen3-30b-a3b-instruct-2507
   MRS_MODEL_RESEARCH=openai/o3-mini        # Better for papers
   MRS_MODEL_CODE=deepseek/deepseek-v3.2-exp  # Better for code
   ```

3. **Test it**:
   ```bash
   python test_detector.py
   ```

### Source Grounding

**It's automatic!** No configuration needed.

Source-grounding instructions are now included in all:
- Summary generation (direct)
- Chunk summarization (MAP)
- Chunk combination (REDUCE)
- Report generation (final synthesis)

---

## Testing & Verification

### Content Detection
```bash
cd /Users/stwhite/CODE/rsrch
python test_detector.py
```

Expected: All 9 tests pass (arxiv→research, github→code, etc.)

### Source Grounding
Monitor logs for conflicts:
```bash
# Look for these patterns in summaries/reports
grep -i "former.*trump" reports/*.md    # Should NOT appear
grep -i "as of 2024" reports/*.md       # Should be rare
grep -i "at the time" reports/*.md      # Should match sources
```

---

## Architecture

### Content-Based Model Flow
```
URL → ContentPatterns.detect_from_url()
    → ContentType (code/research/news/docs/general)
    → Config.get_mrs_model_for_content_type()
    → Model Name
    → Summarizer uses selected model
```

### Source-Grounding Flow
```
Summarizer._summarize_*()
    → _get_source_grounding_context()
    → Prepend to prompt
    → LLM receives strong instructions
    → Output respects source material
```

---

## Benefits

### Model Routing
- **Cost optimization**: Cheap models for simple content, expensive for complex
- **Quality improvement**: Specialized models excel at their domain
- **Flexibility**: Easy to experiment with model combinations
- **Graceful degradation**: Falls back to default if not configured

### Source Grounding
- **Temporal accuracy**: Current events reported correctly
- **Source fidelity**: Preserves source language and framing
- **Scalable**: No need to enumerate facts
- **Future-proof**: Works for any changes, not just known ones

---

## Files Modified

```
/Users/stwhite/CODE/rsrch/
├── .env                              # Updated: MRS model config
├── config.py                          # Updated: Model routing
├── pipeline.py                        # Updated: Source-grounding in reports
├── stages/
│   ├── content_detector.py           # NEW: Content type detection
│   └── summarizer.py                 # Updated: Model routing + source-grounding
├── docs/
│   ├── model_routing.md              # NEW: Model routing docs
│   ├── source_grounding.md           # NEW: Source-grounding docs
│   └── IMPLEMENTATION_SUMMARY.md     # NEW: This file
└── test_detector.py                  # NEW: Content detection tests
```

---

## Next Steps (Optional Enhancements)

### 1. Monitoring
Add logging to track:
- Which models are used for which URLs
- How often conflicts occur (added qualifiers, changed names)
- Model performance by content type

### 2. Adaptive Instructions
Detect knowledge conflicts and strengthen instructions dynamically:
```python
if detect_conflict(source, summary):
    # Retry with even stronger grounding
    summary = summarize_with_stronger_grounding(source)
```

### 3. Verification Pass
Add second LLM call to verify source fidelity:
```python
verification = verify_summary(source, summary)
if verification.has_issues:
    logger.warning(f"Potential conflict: {verification.issues}")
```

### 4. Few-Shot Examples
For stubborn models, add examples of correct behavior:
```python
grounding_context += """
Example:
Source: "President Smith announced..."
Correct: "President Smith announced..."
Wrong: "Former President Smith announced..." ❌
"""
```

---

## Troubleshooting

### Model Not Being Used
Check logs for:
```
DEBUG:stages.summarizer:Selected model 'X' for content type 'Y'
```

If missing:
1. Verify content type detection (`python test_detector.py`)
2. Check `.env` has the model configured
3. Ensure environment variables are loaded

### Still Seeing Knowledge Conflicts
1. Check model has strong instruction-following (o3, Claude, Gemini Pro)
2. Lower temperature (0.2-0.3 for summarization)
3. Consider adding domain-specific examples
4. Some models may need repetition of key rules

### Content Type Wrong
Add domain to pattern lists in `stages/content_detector.py`:
```python
RESEARCH_DOMAINS: Set[str] = {
    'arxiv.org',
    'your-new-domain.org',  # Add here
}
```

---

## References

- **Model Routing**: `docs/model_routing.md`
- **Source Grounding**: `docs/source_grounding.md`
- **Content Detection**: `stages/content_detector.py`
- **Configuration**: `.env` and `config.py`

---

**Implementation Date**: October 1, 2025  
**Author**: Research Pipeline Team  
**Status**: ✅ Production Ready
