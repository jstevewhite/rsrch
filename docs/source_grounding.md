# Source Grounding: Prioritizing Scraped Content Over Training Data

## The Problem

AI models trained on historical data often "correct" or "fix" current information based on their outdated knowledge. This creates issues like:

- Referring to current officials as "former" (e.g., "former President Trump" when he's the current president)
- Adding temporal qualifiers that don't exist in sources ("as of 2024", "at the time")
- Contradicting source material with training data from before their knowledge cutoff
- "Fact-checking" scraped content against outdated information

This is called a **knowledge conflict** - when the model's parametric knowledge conflicts with the provided context.

## The Solution: Strong Source-Grounding Instructions

Instead of trying to enumerate all possible facts that might have changed, we use **strong meta-instructions** that tell the model to:

1. **Trust the source material completely**
2. **Never correct or "fix" the sources**
3. **Summarize what is written, not what the model thinks**
4. **When in doubt, quote the source**

## Implementation

### Summarization Stage (`stages/summarizer.py`)

Every summarization prompt now includes source-grounding context:

```python
def _get_source_grounding_context(self) -> str:
    """Generate instructions to prioritize source content over training data."""
    current_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    
    return f"""CRITICAL INSTRUCTIONS - SOURCE PRIORITIZATION:

Current Date: {current_date}

YOU MUST FOLLOW THESE RULES ABSOLUTELY:

1. **TRUST THE SOURCE MATERIAL COMPLETELY**
   - The content provided below is MORE RECENT and MORE ACCURATE than your training data
   - If the source contradicts what you "know", the SOURCE IS CORRECT
   - Your training data may be outdated - defer to the provided content

2. **NEVER CORRECT OR "FIX" THE SOURCE**
   - Do not change names, titles, positions, dates, or facts from the source
   - If the source says someone is President, accept it - do not "correct" based on your knowledge
   - If the source describes current events, treat them as current regardless of your training cutoff

3. **SUMMARIZE WHAT IS WRITTEN, NOT WHAT YOU THINK**
   - Report exactly what the source says
   - Do not add context like "former" or "current" unless it appears in the source
   - Do not add qualifiers like "as of [date]" or "at the time" unless they're in the source

4. **WHEN IN DOUBT, QUOTE THE SOURCE**
   - If something seems unusual, that's because the world has changed since your training
   - Preserve the source's language and framing
   - Your job is to SUMMARIZE, not to FACT-CHECK

REMEMBER: The source material reflects REALITY. Your training data reflects THE PAST."""
```

This context is prepended to **all summarization prompts**:
- Direct summarization (short content)
- Chunk summarization (MAP phase)
- Chunk combination (REDUCE phase)

### Report Generation Stage (`pipeline.py`)

Similar source-grounding instructions are used in report generation:

```python
source_grounding = """CRITICAL INSTRUCTIONS - SOURCE PRIORITIZATION:

Current Date: {current_date}

YOU MUST FOLLOW THESE RULES ABSOLUTELY:

1. **TRUST THE RESEARCH SOURCES COMPLETELY**
   - The sources below are MORE RECENT and MORE ACCURATE than your training data
   - If sources contradict what you "know", the SOURCES ARE CORRECT
   - Your training data may be outdated - defer to the provided research

2. **NEVER CORRECT OR "FIX" THE SOURCES**
   - Do not change names, titles, positions, dates, or facts from the sources
   - If sources say someone holds a position, accept it - do not "correct" based on your knowledge
   - If sources describe current events, treat them as current regardless of your training cutoff

3. **WRITE BASED ON SOURCES, NOT YOUR KNOWLEDGE**
   - Report exactly what the sources say
   - Do not add context like "former" or "current" unless it appears in the sources
   - Do not add qualifiers like "as of [date]" or "at the time" unless they're in the sources
   - Do not add background information from your training if it contradicts the sources

4. **WHEN IN DOUBT, STAY CLOSER TO THE SOURCE TEXT**
   - If something seems unusual, that's because the world has changed since your training
   - Preserve the sources' language and framing
   - Your job is to SYNTHESIZE THE RESEARCH, not to FACT-CHECK against outdated knowledge

5. **SOURCE CITATIONS ARE MANDATORY**
   - Use [Source N] citations for EVERY factual claim
   - Base EVERY statement on the provided sources
   - Do not speculate or infer beyond what sources state

REMEMBER: The research sources reflect REALITY. Your training data reflects THE PAST.
"""
```

## Why This Works

### 1. Meta-Instructions Are Powerful
Modern LLMs are highly sensitive to instructions about **how to behave** rather than **what to know**. Telling the model "trust the source over your knowledge" is more effective than listing specific facts.

### 2. Explicit Conflict Resolution
The instructions explicitly address the knowledge conflict: "If the source contradicts what you know, the SOURCE IS CORRECT." This gives the model clear guidance on what to do when it detects a discrepancy.

### 3. Framing as a Role
By framing the task as "SUMMARIZE, not FACT-CHECK" and "SYNTHESIZE THE RESEARCH, not verify against training," we shift the model's mode of operation.

### 4. Current Date Context
Including the current date helps the model understand that time has passed since its training cutoff, priming it to expect changes.

### 5. Emphasis Through Formatting
Using **bold**, CAPS, and structured lists makes the instructions more salient to the model's attention mechanism.

## Best Practices

### DO:
✅ Use strong, direct language ("NEVER", "MUST", "ABSOLUTELY")
✅ Explicitly name the conflict ("your training data may be outdated")
✅ Frame the task appropriately (summarize vs. fact-check)
✅ Include current date for temporal awareness
✅ Emphasize source fidelity over background knowledge
✅ Use formatting to increase salience (bold, caps, lists)

### DON'T:
❌ Try to enumerate all facts that might have changed
❌ Rely on hardcoded "corrections" (brittle and incomplete)
❌ Assume the model will figure it out without explicit instructions
❌ Use weak language ("try to", "prefer", "if possible")
❌ Bury important instructions in long prompts

## Limitations and Edge Cases

### Still Not Perfect
Even with strong instructions, models may occasionally:
- Revert to training data for ambiguous cases
- Add qualifiers out of caution
- Struggle with deeply ingrained facts (e.g., who was president in 2024)

### When It Works Best
Source grounding is most effective when:
- Source content is clear and unambiguous
- Facts in sources directly contradict training data
- The model has strong instruction-following capabilities
- Temperature is low (≤0.3 for summarization)

### When Additional Help Is Needed
For particularly stubborn conflicts:
1. **Few-shot examples**: Show the model examples of correct behavior
2. **Repetition**: Repeat key instructions multiple times
3. **Post-processing**: Use regex or rules to fix known patterns
4. **Model selection**: Some models are better at instruction-following

## Research Background

This approach is informed by research on knowledge conflicts in LLMs:

- **Parametric vs. Contextual Knowledge**: Models store knowledge in parameters (training) and receive context (prompts). Context should win, but doesn't always.
  
- **Instruction Tuning**: Models trained with RLHF/instruction-tuning are more sensitive to meta-instructions about behavior than base models.

- **Attention Bias**: Without explicit instructions, models may weight their parametric knowledge higher than context, especially for "well-known" facts.

- **Chain-of-Thought**: For complex conflicts, asking the model to "think through" the discrepancy can help (though adds latency).

## Future Enhancements

### 1. Adaptive Instructions
Detect knowledge conflicts and strengthen instructions dynamically:

```python
def detect_knowledge_conflict(source_text: str, model_output: str) -> bool:
    # Check if model added qualifiers not in source
    added_qualifiers = ["former", "current", "as of", "at the time"]
    return any(q in model_output and q not in source_text for q in added_qualifiers)

if detect_knowledge_conflict(source, summary):
    # Retry with even stronger instructions
    prompt = f"{stronger_grounding}\n\n{original_prompt}"
```

### 2. Verification Pass
Add a second model call to verify source fidelity:

```python
verification_prompt = f"""
Compare the summary to the source. Did the summary add any information not in the source?
Did it change any names, titles, or positions?

Source: {source_text}
Summary: {summary_text}

Issues found: [list or "none"]
"""
```

### 3. Model-Specific Instructions
Different models respond better to different instruction styles:

```python
GROUNDING_INSTRUCTIONS = {
    "openai/o3": "Focus on logical accuracy to source...",
    "anthropic/claude": "You are a careful research assistant...",
    "deepseek": "Treat source as ground truth for code...",
}
```

### 4. Confidence Signals
Ask models to flag when they're uncertain:

```python
prompt += """
If you encounter information that contradicts your training, 
mark it with [SOURCE] to indicate you're deferring to the provided content.
"""
```

## Monitoring and Metrics

Track source-grounding effectiveness:

```python
# Log potential conflicts
if "former" in summary and "former" not in source:
    logger.warning(f"Possible conflict: added 'former' to {url}")

# Track model behavior
metrics = {
    "qualifiers_added": count_added_qualifiers(source, summary),
    "names_changed": detect_name_changes(source, summary),
    "dates_modified": detect_date_modifications(source, summary),
}
```

## Configuration

Source-grounding is enabled by default in all summarization and report generation stages. No configuration needed.

To disable (not recommended):
```python
# In summarizer.py
def _get_source_grounding_context(self) -> str:
    return ""  # Disable grounding instructions
```

## Testing

Test source-grounding with known conflicts:

```python
# Test case: Known outdated fact
source = "Donald Trump announced his 2025 budget proposal today..."
summary = summarizer.summarize(source, plan)

# Should NOT contain:
assert "former President Trump" not in summary
assert "President Trump" in summary or "Trump" in summary

# Test case: Temporal qualifier
source = "The President signed the bill yesterday..."
summary = summarizer.summarize(source, plan)

# Should NOT add qualifiers not in source:
assert "as of" not in summary
assert "at the time" not in summary
```

## Conclusion

Source-grounding through strong meta-instructions is a robust, scalable solution to knowledge conflicts. It:

- Works across different types of content
- Doesn't require enumerating specific facts
- Scales to future changes without code updates
- Is more maintainable than heuristic corrections

While not perfect, it significantly reduces the frequency of models "correcting" source material with outdated training data.

---

**Last Updated**: October 1, 2025
