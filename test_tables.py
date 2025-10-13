#!/usr/bin/env python3
"""Focused tests for table-aware summarizer preprocessing.

These tests verify that:
- Small Markdown tables are preserved verbatim in the prompt.
- Large Markdown tables are compacted with a note and aggregates (computed in Python),
  and selection criteria reflect the target metric column when available.
"""

import os
from datetime import datetime
from unittest.mock import Mock

from rsrch.stages.summarizer import Summarizer
from rsrch.models import ScrapedContent, ResearchPlan, Query, SearchQuery, Intent


def build_plan():
    query = Query(text="Evaluate model accuracy", intent=Intent.GENERAL)
    plan = ResearchPlan(
        query=query,
        sections=["Overview", "Results"],
        search_queries=[SearchQuery(query="test", purpose="test", priority=1)],
        rationale="test",
    )
    return plan


def test_small_table_preserved():
    # Small 3x3 table should be kept verbatim
    small_table = (
        "Some intro text.\n\n"
        "| Model | Dataset | Score |\n\n"
        "| --- | --- | --- |\n\n"
        "| A | X | 0.91 |\n\n"
        "| B | Y | 0.87 |\n\n"
        "\nConclusion."
    )

    mock_llm = Mock()
    captured_prompt = {}

    def capture_complete(prompt, model, temperature, max_tokens):
        captured_prompt["prompt"] = prompt
        return "dummy-summary"

    mock_llm.complete.side_effect = capture_complete

    summarizer = Summarizer(
        llm_client=mock_llm,
        default_model="gpt-4o-mini",
        model_selector=lambda _: "gpt-4o-mini",
    )

    content = ScrapedContent(
        url="https://example.com/small-table",
        title="Small Table Test",
        content=small_table,
        chunks=[small_table],
        metadata={"scraper_used": "test"},
        retrieved_at=datetime.now(),
    )

    plan = build_plan()

    summary = summarizer.summarize_content(content, plan)

    assert summary is not None
    assert "prompt" in captured_prompt

    prompt = captured_prompt["prompt"]
    # The exact table header and a row should be present
    assert "| Model | Dataset | Score |" in prompt
    assert "| A | X | 0.91 |" in prompt
    # Ensure table-handling instructions are present
    assert "Preserve any Markdown tables verbatim" in prompt


def test_large_table_compacted():
    # Build a large table (25 rows x 4 cols) with an Accuracy column
    header = "| Model | Dataset | Accuracy | Notes |\n| --- | --- | --- | --- |\n"
    rows = []
    # Create ascending accuracy so top values are at the end
    for i in range(25):
        acc = 0.50 + (i * 0.02)  # 0.50, 0.52, ...
        rows.append(f"| M{i} | D{i%3} | {acc:.2f} | row{i} |\n")
    large_table = "Intro text\n\n" + header + "".join(rows) + "\nMore text"

    mock_llm = Mock()
    captured_prompt = {}

    def capture_complete(prompt, model, temperature, max_tokens):
        captured_prompt["prompt"] = prompt
        return "dummy-summary"

    mock_llm.complete.side_effect = capture_complete

    summarizer = Summarizer(
        llm_client=mock_llm,
        default_model="gpt-4o-mini",
        model_selector=lambda _: "gpt-4o-mini",
    )

    content = ScrapedContent(
        url="https://example.com/large-table",
        title="Large Table Test",
        content=large_table,
        chunks=[large_table],
        metadata={"scraper_used": "test"},
        retrieved_at=datetime.now(),
    )

    plan = build_plan()

    summary = summarizer.summarize_content(content, plan)

    assert summary is not None
    assert "prompt" in captured_prompt
    prompt = captured_prompt["prompt"]

    # Header retained
    assert "| Model | Dataset | Accuracy | Notes |" in prompt
    # Debug info
    print("\n--- PROMPT (first 600 chars) ---\n", prompt[:600])
    note_lines = [ln for ln in prompt.splitlines() if ln.strip().startswith("> Note:")]
    print("NOTE LINES:", note_lines)
    # A low-accuracy row (near the start) should likely be missing after compaction
    assert "| M0 | D0 | 0.50 | row0 |" not in prompt
    # A high-accuracy row (near the end) should likely be present
    assert ("| M24 | D0 | 0.98 | row24 |" in prompt) or ("| M24 |" in prompt)

    # Note line with selection and aggregates should be present
    assert any("Showing 10 of 25 rows" in ln and "selection=max by Accuracy" in ln for ln in note_lines)
    # Numeric fidelity: mean and max should match Python-computed values
    assert any("Accuracy mean=0.74" in ln and "max=0.98" in ln for ln in note_lines)


if __name__ == "__main__":
    ok1 = ok2 = True
    try:
        test_small_table_preserved()
        print("✅ test_small_table_preserved passed")
    except AssertionError as e:
        print("❌ test_small_table_preserved failed:", e)
        ok1 = False

    try:
        test_large_table_compacted()
        print("✅ test_large_table_compacted passed")
    except AssertionError as e:
        print("❌ test_large_table_compacted failed:", e)
        ok2 = False

    import sys
    sys.exit(0 if (ok1 and ok2) else 1)