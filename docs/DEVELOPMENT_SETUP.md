# Development Setup Guide

## Why Run Tests from Parent Directory?

When you run Python modules with `-m`, Python needs to find the package in its search path. The behavior differs based on your current directory:

### From Inside `rsrch/` (Doesn't Work)

```bash
cd /Users/stwhite/CODE/rsrch
python -m rsrch.test_llm_retry  # ❌ ModuleNotFoundError
```

**Why**: Python looks for `rsrch` package starting from current directory. Since you're already inside `rsrch`, it can't find it as a proper package.

### From Parent Directory (Works)

```bash
cd /Users/stwhite/CODE
python -m rsrch.test_llm_retry  # ✅ Works
```

**Why**: Python finds `rsrch` as a package in the current directory and can import it properly.

## Better Solution: Development Installation

Install the package in development mode so you can run it from **anywhere**:

### Step 1: Install in Development Mode

```bash
cd /Users/stwhite/CODE/rsrch
pip install -e .
```

**What this does**:
- Creates a symbolic link to your code
- Makes `rsrch` importable from anywhere
- Changes to code are immediately available (no reinstall needed)
- Professional Python development practice

### Step 2: Verify Installation

```bash
# Test from anywhere
cd ~
python -c "import rsrch; print('✓ Package installed')"
```

### Step 3: Run Tests From Anywhere

```bash
# From inside rsrch/
cd /Users/stwhite/CODE/rsrch
python -m rsrch.test_llm_retry  # ✅ Now works!

# From parent directory
cd /Users/stwhite/CODE
python -m rsrch.test_llm_retry  # ✅ Works!

# From home
cd ~
python -m rsrch.test_llm_retry  # ✅ Works!

# From any directory
cd /tmp
python -m rsrch.test_llm_retry  # ✅ Works!
```

## Alternative Methods

### Method 1: Run as Script (Not Module)

From inside `rsrch/`:

```bash
cd /Users/stwhite/CODE/rsrch
python test_llm_retry.py  # Run directly
```

**Pros**: Simple, works from inside directory  
**Cons**: Requires changing imports, less professional

### Method 2: Temporary PYTHONPATH

```bash
cd /Users/stwhite/CODE/rsrch
PYTHONPATH=/Users/stwhite/CODE:$PYTHONPATH python -m rsrch.test_llm_retry
```

**Pros**: No installation needed  
**Cons**: Verbose, have to set every time

### Method 3: Development Installation (RECOMMENDED)

```bash
pip install -e /Users/stwhite/CODE/rsrch
```

**Pros**: 
- Run from anywhere
- Professional approach
- Auto-updates with code changes
- Works with IDE tools

**Cons**: Requires one-time setup

## Uninstalling

If you ever want to remove the development installation:

```bash
pip uninstall rsrch
```

Your code stays intact - only the package link is removed.

## IDE Configuration

### VS Code

After `pip install -e .`, VS Code will automatically:
- Recognize imports
- Provide autocomplete
- Enable go-to-definition
- Show type hints

### PyCharm

Mark `/Users/stwhite/CODE/rsrch` as "Sources Root":
1. Right-click `rsrch` directory
2. Mark Directory as → Sources Root

## Checking Package Status

```bash
# Check if installed
pip show rsrch

# See where it's installed
pip show -f rsrch

# List all packages
pip list | grep rsrch
```

## Development Workflow

### Before Development Installation

```bash
# Must be in parent directory
cd /Users/stwhite/CODE
python -m rsrch.pipeline
python -m rsrch.test_llm_retry
```

### After Development Installation

```bash
# Can be anywhere!
cd ~/Documents
python -m rsrch.pipeline

cd /tmp
python -m rsrch.test_llm_retry

# Even absolute imports work
python -c "from rsrch.llm_client import LLMClient"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'rsrch'"

**Solution 1**: Run from parent directory
```bash
cd /Users/stwhite/CODE
python -m rsrch.test_llm_retry
```

**Solution 2**: Install in development mode
```bash
cd /Users/stwhite/CODE/rsrch
pip install -e .
```

### "ImportError: attempted relative import with no known parent package"

**Cause**: Running Python file directly when it uses relative imports

**Solution**: Use module syntax
```bash
# Instead of:
python test_llm_retry.py  # ❌

# Use:
python -m rsrch.test_llm_retry  # ✅
```

### Changes Not Reflected After Edit

**With development installation**: Changes should be immediate

**Without development installation**: Must reinstall
```bash
cd /Users/stwhite/CODE/rsrch
pip install -e . --force-reinstall
```

## Best Practices

### For Development

1. ✅ Install in development mode: `pip install -e .`
2. ✅ Use module syntax: `python -m rsrch.module`
3. ✅ Keep tests in package: `rsrch/test_*.py`

### For Production

1. ✅ Use regular install: `pip install .`
2. ✅ Pin dependencies: `requirements.txt`
3. ✅ Build wheel: `python setup.py bdist_wheel`

## Summary

**Quick Fix**: Run from parent directory
```bash
cd /Users/stwhite/CODE
python -m rsrch.test_llm_retry
```

**Permanent Solution**: Development installation
```bash
cd /Users/stwhite/CODE/rsrch
pip install -e .
# Now works from anywhere!
```
