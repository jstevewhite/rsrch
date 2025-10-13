#!/usr/bin/env python3
"""Targeted tests for scraper HTML→Markdown table conversion.

Validates that a simple HTML table is converted into a Markdown pipe table
by the primary BeautifulSoup-based scraper when OUTPUT_FORMAT=markdown and
PRESERVE_TABLES=true.
"""

from bs4 import BeautifulSoup
from rsrch.stages.scraper import Scraper


def test_html_table_to_markdown_basic():
    html = """
    <html>
      <body>
        <h1>Title</h1>
        <table>
          <tr><th>Name</th><th>Score</th></tr>
          <tr><td>Alice</td><td>95</td></tr>
          <tr><td>Bob</td><td>88</td></tr>
        </table>
        <p>Tail</p>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    scraper = Scraper(output_format='markdown', preserve_tables=True)

    # Replace tables with Markdown first, then convert full DOM to Markdown
    scraper._replace_tables_with_markdown(soup)
    md = scraper._html_to_markdown(soup)

    # Assert a pipe table is present with header and rows
    assert "| Name | Score |" in md
    assert "| --- | --- |" in md
    assert "| Alice | 95 |" in md
    assert "| Bob | 88 |" in md


if __name__ == "__main__":
    try:
        test_html_table_to_markdown_basic()
        print("✅ test_html_table_to_markdown_basic passed")
    except AssertionError as e:
        print("❌ test_html_table_to_markdown_basic failed:", e)
        import sys
        sys.exit(1)