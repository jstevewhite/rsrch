#!/usr/bin/env python3
"""Test script for LLM client retry logic."""

import os
import sys
from unittest.mock import Mock, patch
from dotenv import load_dotenv

# Load environment
load_dotenv()

from rsrch.llm_client import LLMClient


def test_retry_on_empty_response():
    """Test that client retries when receiving empty responses."""
    
    print("="*80)
    print("Testing LLM Client Retry Logic")
    print("="*80)
    print()
    
    # Check API key
    if not os.getenv('API_KEY'):
        print("❌ ERROR: API_KEY not found in environment")
        return False
    
    print("✅ API_KEY found")
    
    # Create mock client that returns empty then valid response
    mock_openai_client = Mock()
    
    # First call returns empty response (simulating the bug)
    # Second call returns valid JSON
    mock_response_1 = Mock()
    mock_response_1.choices = [Mock(message=Mock(content=""))]
    
    mock_response_2 = Mock()
    mock_response_2.choices = [Mock(message=Mock(content='{"status": "success"}'))]
    
    mock_openai_client.chat.completions.create.side_effect = [
        mock_response_1,  # First call - empty
        mock_response_2,  # Second call - valid
    ]
    
    # Create LLM client with mock
    llm_client = LLMClient(
        api_key="test-key",
        api_endpoint="https://test.example.com/v1",
        default_model="test-model",
        max_retries=3
    )
    llm_client.client = mock_openai_client
    
    print(f"✅ LLM client initialized with max_retries=3")
    print()
    
    # Test retry logic
    try:
        print("Testing complete_json with simulated empty response...")
        print("-" * 80)
        
        result = llm_client.complete_json(
            prompt="Test prompt",
            temperature=0.7
        )
        
        print()
        print("=" * 80)
        print("✅ SUCCESS! Retry logic worked correctly")
        print("=" * 80)
        print(f"Result: {result}")
        print()
        print("Expected behavior:")
        print("  1. First call returned empty response")
        print("  2. Client logged warning and retried")
        print("  3. Second call returned valid JSON")
        print("  4. Client successfully parsed and returned result")
        print()
        
        # Verify the client made 2 calls
        assert mock_openai_client.chat.completions.create.call_count == 2
        print(f"✅ Verified: Made {mock_openai_client.chat.completions.create.call_count} API calls (as expected)")
        
        return True
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ FAILURE! Retry logic did not work")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_retry_exhaustion():
    """Test that client eventually fails after max retries."""
    
    print()
    print("="*80)
    print("Testing Retry Exhaustion")
    print("="*80)
    print()
    
    # Create mock client that always returns empty responses
    mock_openai_client = Mock()
    
    # All calls return empty response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=""))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Create LLM client with mock
    llm_client = LLMClient(
        api_key="test-key",
        api_endpoint="https://test.example.com/v1",
        default_model="test-model",
        max_retries=3
    )
    llm_client.client = mock_openai_client
    
    print("Testing retry exhaustion (all responses empty)...")
    print("-" * 80)
    
    try:
        result = llm_client.complete_json(
            prompt="Test prompt",
            temperature=0.7
        )
        
        print()
        print("❌ FAILURE! Should have raised an exception")
        return False
        
    except ValueError as e:
        print()
        print("=" * 80)
        print("✅ SUCCESS! Correctly exhausted retries and raised exception")
        print("=" * 80)
        print(f"Exception message: {e}")
        print()
        
        # Verify the client made max_retries calls
        call_count = mock_openai_client.chat.completions.create.call_count
        print(f"✅ Verified: Made {call_count} API calls (max_retries={3})")
        assert call_count == 3
        
        return True
        
    except Exception as e:
        print()
        print("❌ FAILURE! Wrong exception type")
        print(f"Expected ValueError, got: {type(e).__name__}")
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    print()
    print("🧪 Running LLM Client Retry Tests")
    print("=" * 80)
    print()
    
    # Test 1: Successful retry
    success1 = test_retry_on_empty_response()
    
    # Test 2: Retry exhaustion
    success2 = test_retry_exhaustion()
    
    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Successful retry test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"Retry exhaustion test: {'✅ PASSED' if success2 else '❌ FAILED'}")
    print()
    
    sys.exit(0 if (success1 and success2) else 1)
