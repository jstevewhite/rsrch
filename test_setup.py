#!/usr/bin/env python3
"""Test script to verify the research pipeline setup."""

import sys
from pathlib import Path

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from config import Config
        from models import Query, Intent
        from llm_client import LLMClient
        from pipeline import ResearchPipeline
        from stages import IntentClassifier, Planner
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        from config import Config
        
        # Check if .env exists
        if not Path(".env").exists():
            print("⚠️  .env file not found (this is OK for initial setup)")
            print("   Run: cp .env.example .env")
            return True
        
        # Try loading config
        config = Config.from_env()
        print(f"✅ Configuration loaded")
        print(f"   API endpoint: {config.api_endpoint}")
        print(f"   Default model: {config.default_model}")
        print(f"   Output dir: {config.output_dir}")
        return True
    except ValueError as e:
        print(f"⚠️  Configuration error: {e}")
        print("   Make sure API_KEY is set in .env")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_models():
    """Test data models."""
    print("\nTesting data models...")
    try:
        from models import Query, Intent, SearchQuery, ResearchPlan
        
        # Create test query
        query = Query(text="Test query")
        query.intent = Intent.INFORMATIONAL
        
        # Create test search query
        search_query = SearchQuery(
            query="test search",
            purpose="testing",
            priority=1
        )
        
        # Create test plan
        plan = ResearchPlan(
            query=query,
            sections=["Section 1", "Section 2"],
            search_queries=[search_query],
            rationale="Test rationale"
        )
        
        print("✅ Data models working correctly")
        return True
    except Exception as e:
        print(f"❌ Model error: {e}")
        return False

def test_directories():
    """Test that required directories can be created."""
    print("\nTesting directory creation...")
    try:
        from config import Config
        config = Config.from_env() if Path(".env").exists() else None
        
        if config:
            config.ensure_directories()
            print(f"✅ Directories created/verified")
            print(f"   Output: {config.output_dir}")
            print(f"   DB path: {config.vector_db_path.parent}")
        else:
            print("⚠️  Skipping (no .env file)")
        
        return True
    except Exception as e:
        print(f"❌ Directory error: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("Research Pipeline - Setup Test")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Data Models", test_models()))
    results.append(("Directories", test_directories()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s} {status}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests passed!")
        print("\nNext steps:")
        print("1. Make sure .env has your API_KEY")
        print("2. Run: python cli.py \"your test query\"")
        print("3. Check ./reports/ for output")
    else:
        print("⚠️  Some tests failed")
        print("\nTroubleshooting:")
        print("1. Run: pip install -r requirements.txt")
        print("2. Make sure you're in the rsrch directory")
        print("3. Check that .env.example exists")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
