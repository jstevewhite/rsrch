#!/usr/bin/env python3
"""Test script for scraper implementation."""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Use package-relative imports
from rsrch.stages.scraper import Scraper
from rsrch.models import SearchResult


def test_scraper():
    """Test the scraper with sample URLs."""
    
    print("="*80)
    print("Testing Scraper Implementation")
    print("="*80)
    
    # Check if we have API keys (optional for primary scraper)
    jina_key = os.getenv('JINA_API_KEY')
    serper_key = os.getenv('SERPER_API_KEY')
    
    if jina_key:
        print("✅ JINA_API_KEY found (for fallback)")
    else:
        print("⚠️  JINA_API_KEY not found (fallback scraping may fail)")
    
    if serper_key:
        print("✅ SERPER_API_KEY found (for fallback)")
    else:
        print("⚠️  SERPER_API_KEY not found (fallback scraping may fail)")
    
    print()
    print("Note: Primary scraper (BeautifulSoup) doesn't need API keys")
    print()
    
    # Create test search results (simulating researcher output)
    test_results = [
        SearchResult(
            url="https://realpython.com/async-io-python/",
            title="Python's asyncio: A Hands-On Walkthrough",
            snippet="Learn how Python asyncio works...",
            rank=1
        ),
        SearchResult(
            url="https://docs.python.org/3/library/asyncio.html",
            title="asyncio — Asynchronous I/O",
            snippet="Official Python documentation for asyncio...",
            rank=2
        ),
        SearchResult(
            url="https://superfastpython.com/asyncio-in-python/",
            title="Asyncio in Python - Complete Guide",
            snippet="What is asyncio? How to use it?",
            rank=3
        ),
    ]
    
    print(f"Test URLs: {len(test_results)}")
    for i, result in enumerate(test_results, 1):
        print(f"  {i}. {result.title}")
        print(f"     {result.url}")
    print()
    
    # Initialize scraper
    scraper = Scraper()
    print("✅ Scraper initialized")
    print()
    
    # Test scraping
    try:
        print("Starting scrape...")
        print("-" * 80)
        scraped_content = scraper.scrape_results(test_results)
        
        print()
        print("="*80)
        print(f"✅ SUCCESS! Scraped {len(scraped_content)}/{len(test_results)} URLs")
        print("="*80)
        print()
        
        # Show results
        for i, content in enumerate(scraped_content, 1):
            print(f"\n{'='*80}")
            print(f"Result {i}: {content.title[:60]}...")
            print(f"{'='*80}")
            print(f"URL: {content.url}")
            print(f"Content Length: {len(content.content):,} characters")
            print(f"Chunks: {len(content.chunks)}")
            print(f"Scraper Used: {content.metadata.get('scraper_used', 'unknown')}")
            print(f"\nFirst 300 characters of content:")
            print("-" * 80)
            print(content.content[:300] + "...")
            print("-" * 80)
        
        # Show scraper statistics
        stats = scraper.get_fallback_usage_stats()
        print(f"\n{'='*80}")
        print("Scraper Statistics")
        print("="*80)
        print(f"Fallback scrapers used: {stats['fallback_used']} times")
        print(f"Estimated cost: ${stats['estimated_cost']:.3f}")
        
        if stats['fallback_used'] > 0:
            print("\n⚠️  Note: Fallback scrapers (Jina/Serper) incur API costs")
        else:
            print("\n✅ All scraping done with free BeautifulSoup scraper!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_single_url_scraping():
    """Test scraping a single URL with both methods."""
    
    print("\n\n")
    print("="*80)
    print("Testing Single URL Scraping (Direct)")
    print("="*80)
    
    test_url = "https://docs.python.org/3/library/asyncio.html"
    print(f"Test URL: {test_url}")
    print()
    
    scraper = Scraper()
    
    # Test primary scraper only
    try:
        print("Testing BeautifulSoup scraper (no fallback)...")
        content = scraper._scrape_single_url(test_url, use_fallback=False)
        
        print("✅ BeautifulSoup scraper succeeded!")
        print(f"Content length: {len(content.content):,} characters")
        print(f"\nFirst 200 characters:")
        print("-" * 80)
        print(content.content[:200] + "...")
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ BeautifulSoup scraper failed: {e}")
        print("\nThis is expected for some JS-heavy sites.")
        print("Fallback scrapers (Jina/Serper) would handle these.")
        return False


if __name__ == "__main__":
    print("\n")
    print("🧪 Running Scraper Tests")
    print("="*80)
    print()
    
    # Test 1: Batch scraping
    success1 = test_scraper()
    
    # Test 2: Single URL scraping
    success2 = test_single_url_scraping()
    
    print("\n\n")
    print("="*80)
    print("Test Summary")
    print("="*80)
    print(f"Batch scraping test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"Single URL test: {'✅ PASSED' if success2 else '❌ FAILED'}")
    print()
    
    sys.exit(0 if (success1 or success2) else 1)
