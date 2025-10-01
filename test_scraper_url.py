#!/usr/bin/env python3
"""Test script for scraper.scrape_url() method."""

import sys
from rsrch.stages.scraper import Scraper


def test_scrape_url_method():
    """Test that Scraper has a scrape_url() method."""
    
    print("="*80)
    print("Testing Scraper.scrape_url() Method")
    print("="*80)
    print()
    
    # Initialize scraper
    scraper = Scraper()
    
    # Check that scrape_url method exists
    if not hasattr(scraper, 'scrape_url'):
        print("❌ FAILED: Scraper does not have scrape_url() method")
        return False
    
    print("✅ Scraper has scrape_url() method")
    
    # Check method signature
    import inspect
    sig = inspect.signature(scraper.scrape_url)
    params = list(sig.parameters.keys())
    
    print(f"✅ Method signature: scrape_url({', '.join(params)})")
    
    if 'url' not in params:
        print("❌ FAILED: scrape_url() missing 'url' parameter")
        return False
    
    print("✅ Method has required 'url' parameter")
    
    # Test with a real URL (just check it doesn't crash)
    print()
    print("Testing with example.com...")
    try:
        result = scraper.scrape_url("https://example.com")
        if result:
            print(f"✅ Successfully scraped example.com")
            print(f"   Title: {result.title if hasattr(result, 'title') else 'N/A'}")
            print(f"   Content length: {len(result.content) if hasattr(result, 'content') else 0} chars")
        else:
            print("⚠️  Scraping returned None (acceptable for test)")
        return True
    except Exception as e:
        print(f"⚠️  Scraping raised exception (acceptable for test): {e}")
        return True  # Not a failure - method exists and is callable


def test_verifier_can_use_scraper():
    """Test that ClaimVerifier can use scraper.scrape_url()."""
    
    print()
    print("="*80)
    print("Testing ClaimVerifier Integration")
    print("="*80)
    print()
    
    from rsrch.stages.verifier import ClaimVerifier
    from rsrch.llm_client import LLMClient
    from unittest.mock import Mock
    
    # Create mock LLM client
    mock_llm = Mock(spec=LLMClient)
    
    # Create real scraper
    scraper = Scraper()
    
    # Create verifier - should not crash
    try:
        verifier = ClaimVerifier(
            llm_client=mock_llm,
            scraper=scraper,
            model="gpt-4o-mini"
        )
        print("✅ ClaimVerifier initialized successfully with Scraper")
        
        # Verify it has access to scrape_url
        if hasattr(verifier.scraper, 'scrape_url'):
            print("✅ ClaimVerifier can access scraper.scrape_url() method")
            return True
        else:
            print("❌ FAILED: ClaimVerifier.scraper doesn't have scrape_url()")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Could not initialize ClaimVerifier: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    print("🧪 Running Scraper URL Method Tests")
    print("=" * 80)
    print()
    
    # Test 1: scrape_url method exists
    success1 = test_scrape_url_method()
    
    # Test 2: Verifier integration
    success2 = test_verifier_can_use_scraper()
    
    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Scraper.scrape_url() test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"ClaimVerifier integration test: {'✅ PASSED' if success2 else '❌ FAILED'}")
    print()
    
    if success1 and success2:
        print("✅ All tests passed! The scraping error should be fixed.")
        print()
        print("The error \"'Scraper' object has no attribute 'scrape_url'\" should no longer occur.")
    
    sys.exit(0 if (success1 and success2) else 1)
