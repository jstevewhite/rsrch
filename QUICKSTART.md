# Quick Start Guide

Get your research pipeline up and running in 5 minutes!

## 1. Install Dependencies

```bash
cd /Users/stwhite/CODE/rsrch
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your API key
nano .env  # or use your favorite editor
```

Add your OpenAI API key:

```bash
API_KEY=sk-your-key-here
```

## 3. Run Your First Query

```bash
python cli.py "What is the latest research on tirzepatide?"
```

## 4. Check Your Report

Reports are saved in `./reports/` by default. Open the generated `.md` file to view your research report!

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

**Problem**: `ModuleNotFoundError: No module named 'openai'`
**Solution**: Run `pip install -r requirements.txt`

**Problem**: `ValueError: Required environment variable API_KEY is not set`
**Solution**: Ensure your `.env` file exists and contains `API_KEY=your-key`

**Problem**: Import errors
**Solution**: Make sure you're in the `/Users/stwhite/CODE/rsrch` directory when running

## Need Help?

Check `research_pipeline.log` for detailed error messages and use `--log-level DEBUG` for verbose output.
