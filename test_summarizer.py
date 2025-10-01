#!/usr/bin/env python3
"""Test script for summarizer implementation."""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv()

# Use package-relative imports
from rsrch.stages.summarizer import Summarizer
from rsrch.models import ScrapedContent, ResearchPlan, Query, SearchQuery, Intent
from rsrch.llm_client import LLMClient
from rsrch.config import Config


def test_summarizer():
    """Test the summarizer with sample scraped content."""
    
    print("="*80)
    print("Testing Summarizer Implementation")
    print("="*80)
    
    # Check API key
    if not os.getenv('API_KEY'):
        print("❌ ERROR: API_KEY not found in environment")
        print("Please set it in your .env file")
        return False
    
    print("✅ API_KEY found")
    print()
    
    # Load config
    try:
        config = Config.from_env()
        print(f"✅ Config loaded (model: {config.mrs_model})")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False
    
    # Initialize LLM client
    try:
        llm_client = LLMClient(
            api_key=config.api_key,
            api_endpoint=config.api_endpoint,
            default_model=config.default_model
        )
        print("✅ LLM client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        return False
    
    # Initialize summarizer
    try:
        summarizer = Summarizer(
            llm_client=llm_client,
            model=config.mrs_model
        )
        print("✅ Summarizer initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize summarizer: {e}")
        return False
    
    # Create test research plan
    query = Query(text="What is Python asyncio?", intent=Intent.CODE)
    plan = ResearchPlan(
        query=query,
        sections=["Overview", "Core Concepts", "Usage Examples", "Best Practices"],
        search_queries=[
            SearchQuery(
                query="Python asyncio tutorial",
                purpose="Learn basics",
                priority=1
            )
        ],
        rationale="Research Python asyncio for coding purposes"
    )
    
    print(f"Query: {query.text}")
    print(f"Sections: {', '.join(plan.sections)}")
    print()
    
    # Create test scraped content (simulating scraper output)
    test_content = [
        ScrapedContent(
            url="https://docs.python.org/3/library/asyncio.html",
            title="asyncio — Asynchronous I/O",
            content="""asyncio is a library to write concurrent code using the async/await syntax.

asyncio is used as a foundation for multiple Python asynchronous frameworks that provide high-performance network and web-servers, database connection libraries, distributed task queues, etc.

asyncio is often a perfect fit for IO-bound and high-level structured network code.

asyncio provides a set of high-level APIs to:
- Run Python coroutines concurrently and have full control over their execution
- Perform network IO and IPC
- Control subprocesses
- Distribute tasks via queues
- Synchronize concurrent code

Additionally, there are low-level APIs for library and framework developers to:
- Create and manage event loops, which provide asynchronous APIs for networking, running subprocesses, handling OS signals, etc
- Implement efficient protocols using transports
- Bridge callback-based libraries and code with async/await syntax""",
            chunks=["Full content as single chunk"],
            metadata={"scraper_used": "beautifulsoup", "content_length": 800},
            retrieved_at=datetime.now()
        ),
        ScrapedContent(
            url="https://realpython.com/async-io-python/",
            title="Python's asyncio: A Hands-On Walkthrough",
            content="""Async IO is a concurrent programming design that has received dedicated support in Python, evolving rapidly from Python 3.4 through 3.7, and probably beyond.

You may be thinking with dread, "Concurrency, parallelism, threading, multiprocessing. That's a lot to grasp already. Where does async IO fit in?"

This tutorial is built to help you answer that question, giving you a firmer grasp of Python's approach to async IO.

Here's what you'll cover:
- Asynchronous IO (async IO): a language-agnostic paradigm (model) that has implementations across a host of programming languages
- async/await: two new Python keywords that are used to define coroutines
- asyncio: the Python package that provides a foundation and API for running and managing coroutines

Coroutines (specialized generator functions) are the heart of async IO in Python, and we'll dive into them later on.""",
            chunks=["Full content"],
            metadata={"scraper_used": "beautifulsoup", "content_length": 900},
            retrieved_at=datetime.now()
        ),
    ]
    
    print(f"Test content: {len(test_content)} documents")
    for i, content in enumerate(test_content, 1):
        print(f"  {i}. {content.title} ({len(content.content)} chars)")
    print()
    
    # Test summarization
    try:
        print("Starting summarization...")
        print("-" * 80)
        summaries = summarizer.summarize_all(
            scraped_contents=test_content,
            plan=plan,
            max_summaries=None
        )
        
        print()
        print("="*80)
        print(f"✅ SUCCESS! Generated {len(summaries)}/{len(test_content)} summaries")
        print("="*80)
        print()
        
        # Show results
        for i, summary in enumerate(summaries, 1):
            print(f"\n{'='*80}")
            print(f"Summary {i}")
            print(f"{'='*80}")
            print(f"URL: {summary.url}")
            print(f"Relevance Score: {summary.relevance_score}")
            print(f"Citations: {len(summary.citations)}")
            print(f"\nSummary Text ({len(summary.text)} chars):")
            print("-" * 80)
            print(summary.text)
            print("-" * 80)
            
            if summary.citations:
                print(f"\nCitations:")
                for j, citation in enumerate(summary.citations, 1):
                    print(f"  [{j}] {citation.title}")
                    print(f"      {citation.url}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_long_content_chunking():
    """Test map-reduce for long content."""
    
    print("\n\n")
    print("="*80)
    print("Testing Long Content (Map-Reduce)")
    print("="*80)
    
    config = Config.from_env()
    llm_client = LLMClient(
        api_key=config.api_key,
        api_endpoint=config.api_endpoint,
        default_model=config.default_model
    )
    summarizer = Summarizer(llm_client=llm_client, model=config.mrs_model)
    
    # Create long content (exceeds MAX_CHUNK_CHARS)
    long_text = """Python asyncio module """ * 2000  # Artificially long
    
    long_content = ScrapedContent(
        url="https://example.com/long-article",
        title="Very Long Article on Asyncio",
        content=long_text,
        chunks=["chunk"],
        metadata={"scraper_used": "test"},
        retrieved_at=datetime.now()
    )
    
    query = Query(text="What is asyncio?", intent=Intent.CODE)
    plan = ResearchPlan(
        query=query,
        sections=["Overview"],
        search_queries=[SearchQuery(query="asyncio", purpose="test", priority=1)],
        rationale="test"
    )
    
    print(f"Content length: {len(long_text):,} characters")
    print(f"Expected chunks: ~{len(long_text) // summarizer.MAX_CHUNK_CHARS}")
    print()
    
    try:
        print("Testing map-reduce summarization...")
        summary = summarizer.summarize_content(long_content, plan)
        
        if summary:
            print(f"✅ Map-reduce succeeded!")
            print(f"Summary length: {len(summary.text)} chars")
            print(f"Citations: {len(summary.citations)}")
            return True
        else:
            print("❌ No summary generated")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n")
    print("🧪 Running Summarizer Tests")
    print("="*80)
    print()
    
    # Test 1: Basic summarization
    success1 = test_summarizer()
    
    # Test 2: Long content (map-reduce)
    success2 = test_long_content_chunking()
    
    print("\n\n")
    print("="*80)
    print("Test Summary")
    print("="*80)
    print(f"Basic summarization test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"Map-reduce test: {'✅ PASSED' if success2 else '❌ FAILED'}")
    print()
    
    sys.exit(0 if (success1 and success2) else 1)
