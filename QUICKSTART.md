# Quick Start Guide

Get your research pipeline up and running in 5 minutes!

## 1) Install (PEP 660 editable)

Modern, location-independent install that works from anywhere and across symlinks:

```bash
pip install -e .
```

This uses pyproject.toml (setuptools >= 64) for a PEP 660 editable install. No dependency on a specific parent directory (e.g., /Users vs /Volumes). If you move or clone the repo elsewhere, just run `pip install -e .` again in the new location.

Alternative (not recommended):

```bash
pip install -r requirements.txt
```

## 2) Configure Environment

Copy example config and set your keys:

```bash
cp .env.example .env
```

Required: Serper.dev API key (for search and scraping fallback)

```bash
SERPER_API_KEY=your_serper_api_key
```

Optional knobs:

```bash
SEARCH_RESULTS_PER_QUERY=15   # Default: 10
SEARCH_PROVIDER=TAVILY        # Free tier 1,000 req/mo (no key needed)
TAVILY_API_KEY=your_tavily_api_key  # Optional for higher limits
```

## 3) Verify install

```bash
python -c "import rsrch; from rsrch.stages import Scraper; print('OK')"
```

## 4) Run your first query

Using the installed console script (preferred):

```bash
rsrch "What is the Anthropic Model Context Protocol?"
```

Or with the module directly:

```bash
python cli.py "What is the Anthropic Model Context Protocol?"
```

## 5) Check your report

Reports are written to `./reports/` by default. The CLI prints the exact path on completion.

## Example Output

```text
================================================================================
Research Pipeline
================================================================================
Query: What is the latest research on tirzepatide?

2025-01-30 14:30:22 - INFO - Loading configuration...
2025-01-30 14:30:22 - INFO - Initializing research pipeline...
2025-01-30 14:30:22 - INFO - Stage 1: Query parsed
2025-01-30 14:30:23 - INFO - Stage 2: Identifying intent...
2025-01-30 14:30:24 - INFO - Intent identified: research
2025-01-30 14:30:24 - INFO - Stage 3: Planning research...
2025-01-30 14:30:26 - INFO - Research plan created with 4 queries
...
================================================================================
Report Generated Successfully
================================================================================
Report saved to: ./reports/report_20250130_143022.md
```

## Next Steps

- Check the full README.md for advanced options
- Configure stage-specific models in .env
- Review logs in `research_pipeline.log`

## Troubleshooting

- ImportError after moving/cloning the repo: re-run `pip install -e .` in the new location
- Using Anaconda/conda: ensure `which python` and `which pip` point to the same interpreter you used to install
- Missing deps: `pip install -r requirements.txt`
- Missing API keys: ensure `.env` exists and contains required keys

## Need Help?

Check `research_pipeline.log` for detailed error messages and use `--log-level DEBUG` for verbose output.
