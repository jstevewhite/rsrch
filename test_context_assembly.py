#!/usr/bin/env python3
"""Test script for context assembly implementation."""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# Load environment
load_dotenv()

# Use package-relative imports
from rsrch.stages.context_assembler import ContextAssembler, EmbeddingClient, VectorStore
from rsrch.models import Summary, Citation, ResearchPlan, Query, SearchQuery, Intent
from rsrch.config import Config


def test_context_assembly():
    """Test the context assembler with sample summaries."""
    
    print("="*80)
    print("Testing Context Assembly Implementation")
    print("="*80)
    
    # Load config
    try:
        config = Config.from_env()
        print(f"✅ Config loaded")
        print(f"   Embedding URL: {config.embedding_url}")
        print(f"   Embedding Model: {config.embedding_model}")
        print(f"   Top-K Ratio: {config.rerank_top_k}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False
    
    print()
    
    # Initialize components
    try:
        embedding_client = EmbeddingClient(
            api_url=config.embedding_url,
            api_key=config.embedding_api_key,
            model=config.embedding_model
        )
        print("✅ Embedding client initialized")
        
        vector_store = VectorStore(db_path=config.vector_db_path)
        print("✅ Vector store initialized")
        
        context_assembler = ContextAssembler(
            embedding_client=embedding_client,
            vector_store=vector_store,
            top_k_ratio=config.rerank_top_k
        )
        print("✅ Context assembler initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize components: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Create test data
    query = Query(text="What is Python asyncio?", intent=Intent.CODE)
    plan = ResearchPlan(
        query=query,
        sections=["Overview", "Core Concepts", "Usage Examples"],
        search_queries=[
            SearchQuery(query="Python asyncio tutorial", purpose="Learn basics", priority=1)
        ],
        rationale="Research Python asyncio for coding purposes"
    )
    
    # Create diverse test summaries
    test_summaries = [
        Summary(
            text="Python's asyncio is a library for writing concurrent code using async/await syntax. It provides event loops and coroutines for asynchronous programming.",
            citations=[Citation(text="...", url="https://docs.python.org/3/library/asyncio.html", title="Python asyncio documentation")],
            url="https://docs.python.org/3/library/asyncio.html",
            relevance_score=0.0
        ),
        Summary(
            text="JavaScript has similar async patterns with promises and async/await. React hooks also use asynchronous patterns for state management.",
            citations=[Citation(text="...", url="https://example.com/js", title="JavaScript async patterns")],
            url="https://example.com/js",
            relevance_score=0.0
        ),
        Summary(
            text="Asyncio allows Python programs to handle multiple I/O operations concurrently. Common use cases include web scraping, network servers, and database queries.",
            citations=[Citation(text="...", url="https://realpython.com/async-io-python/", title="Real Python asyncio guide")],
            url="https://realpython.com/async-io-python/",
            relevance_score=0.0
        ),
        Summary(
            text="Django is a web framework that traditionally used synchronous code. However, Django 3.0+ now supports asynchronous views and middleware.",
            citations=[Citation(text="...", url="https://example.com/django", title="Django async")],
            url="https://example.com/django",
            relevance_score=0.0
        ),
        Summary(
            text="The asyncio event loop is the core of async Python programming. It schedules coroutines, manages callbacks, and handles I/O operations efficiently.",
            citations=[Citation(text="...", url="https://superfastpython.com/asyncio-event-loop/", title="Asyncio Event Loop Guide")],
            url="https://superfastpython.com/asyncio-event-loop/",
            relevance_score=0.0
        ),
    ]
    
    print(f"Query: {query.text}")
    print(f"Test summaries: {len(test_summaries)}")
    print()
    
    # Test context assembly
    try:
        print("Starting context assembly...")
        print("-" * 80)
        
        context = context_assembler.assemble_context(
            summaries=test_summaries,
            plan=plan
        )
        
        print()
        print("="*80)
        print(f"✅ SUCCESS! Context assembled")
        print("="*80)
        print()
        
        # Show results
        print(f"Total summaries: {context.additional_context['total_summaries']}")
        print(f"Selected summaries: {context.additional_context['selected_summaries']}")
        print(f"Top-K ratio: {context.additional_context['top_k_ratio']:.2%}")
        print(f"Relevance range: {context.additional_context['min_relevance_score']:.3f} - {context.additional_context['max_relevance_score']:.3f}")
        print()
        
        print("Ranked summaries (by relevance):")
        print("-" * 80)
        for i, summary in enumerate(context.summaries, 1):
            print(f"\n{i}. Score: {summary.relevance_score:.3f}")
            print(f"   URL: {summary.url}")
            print(f"   Preview: {summary.text[:100]}...")
        
        print("\n" + "="*80)
        print("Analysis:")
        print("="*80)
        
        # Check if most relevant summaries are actually about asyncio
        asyncio_summaries = [s for s in context.summaries if 'asyncio' in s.text.lower()]
        print(f"Summaries mentioning 'asyncio': {len(asyncio_summaries)}/{len(context.summaries)}")
        
        if len(asyncio_summaries) == len(context.summaries):
            print("✅ Perfect filtering - all selected summaries are relevant!")
        elif len(asyncio_summaries) >= len(context.summaries) * 0.8:
            print("✅ Good filtering - most selected summaries are relevant")
        else:
            print("⚠️  Filtering could be improved - some less relevant summaries included")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n")
    print("🧪 Running Context Assembly Test")
    print("="*80)
    print()
    
    success = test_context_assembly()
    
    print("\n\n")
    print("="*80)
    print("Test Summary")
    print("="*80)
    print(f"Context assembly test: {'✅ PASSED' if success else '❌ FAILED'}")
    print()
    
    sys.exit(0 if success else 1)
