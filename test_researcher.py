#!/usr/bin/env python3
"""Test script for researcher implementation."""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Use package-relative imports
from rsrch.stages.researcher import Researcher
from rsrch.models import ResearchPlan, Query, SearchQuery, Intent

def test_researcher():
    """Test the researcher with a simple query."""
    
    print("="*80)
    print("Testing Researcher Implementation")
    print("="*80)
    
    # Check API key
    if not os.getenv('SERPER_API_KEY'):
        print("❌ ERROR: SERPER_API_KEY not found in environment")
        print("Please set it in your .env file")
        return False
    
    print("✅ SERPER_API_KEY found")
    print()
    
    # Create a test query and plan
    query = Query(text="What is Python asyncio?", intent=Intent.CODE)
    
    plan = ResearchPlan(
        query=query,
        sections=["Overview", "Key Concepts", "Examples"],
        search_queries=[
            SearchQuery(
                query="Python asyncio tutorial",
                purpose="Learn basics of asyncio",
                priority=1
            ),
            SearchQuery(
                query="asyncio best practices",
                purpose="Understand how to use it properly",
                priority=2
            )
        ],
        rationale="Research Python asyncio for coding purposes"
    )
    
    print(f"Query: {query.text}")
    print(f"Intent: {query.intent.value}")
    print(f"Search queries: {len(plan.search_queries)}")
    print()
    
    # Initialize researcher
    researcher = Researcher()
    print("✅ Researcher initialized")
    print()
    
    # Execute search
    try:
        print("Executing searches...")
        results = researcher.search(plan)
        
        print(f"\n✅ SUCCESS! Found {len(results)} total results")
        print()
        
        # Show first few results
        print("Sample results:")
        for i, result in enumerate(results[:5], 1):
            print(f"\n{i}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   Snippet: {result.snippet[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_researcher()
    sys.exit(0 if success else 1)
