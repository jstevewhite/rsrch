#!/usr/bin/env python3
"""Test script for temporal context in claim verification."""

import sys
from unittest.mock import Mock
from datetime import datetime

from rsrch.stages.verifier import ClaimVerifier, ExtractedClaim
from rsrch.llm_client import LLMClient
from rsrch.stages.scraper import Scraper
from rsrch.models import ScrapedContent


def test_temporal_context_in_prompt():
    """Test that verification prompt includes temporal context."""
    
    print("="*80)
    print("Testing Temporal Context in Verification Prompt")
    print("="*80)
    print()
    
    # Create mock LLM client that captures the prompt
    captured_prompt = {}
    
    def mock_complete_json(prompt, **kwargs):
        captured_prompt['prompt'] = prompt
        # Return minimal valid response
        return {
            "verifications": [
                {
                    "claim_id": 0,
                    "verdict": "supported",
                    "confidence": 0.95,
                    "evidence": "Test evidence",
                    "reasoning": "Test reasoning"
                }
            ]
        }
    
    mock_llm = Mock(spec=LLMClient)
    mock_llm.complete_json = mock_complete_json
    
    # Create mock scraper
    mock_scraper = Mock(spec=Scraper)
    mock_scraper.scrape_url.return_value = ScrapedContent(
        url="https://example.com",
        title="Test Article",
        content="President Donald Trump announced a plan in 2025.",
        chunks=["President Donald Trump announced a plan in 2025."],
        metadata={"scraper_used": "test"},
        retrieved_at=datetime(2025, 10, 1, 12, 0, 0)
    )
    
    # Create verifier
    verifier = ClaimVerifier(
        llm_client=mock_llm,
        scraper=mock_scraper,
        model="gpt-4o-mini"
    )
    
    print("✅ ClaimVerifier initialized")
    
    # Create test claim about Trump in 2025
    claims = [
        ExtractedClaim(
            text="President Donald Trump announced a plan in 2025",
            source_number=1,
            source_url="https://example.com",
            claim_type="factual",
            context="Testing temporal context"
        )
    ]
    
    # Verify claims (this will capture the prompt)
    print("Testing claim verification with temporal context...")
    results = verifier.verify_source_claims("https://example.com", claims)
    
    # Check that prompt was captured
    if not captured_prompt.get('prompt'):
        print("❌ FAILED: Prompt was not captured")
        return False
    
    prompt = captured_prompt['prompt']
    
    print("✅ Prompt captured successfully")
    print()
    
    # Check for temporal context elements
    checks = {
        "Current date": "Current date:" in prompt,
        "Source retrieved": "Source retrieved:" in prompt,
        "Training data warning": "IGNORE any conflicts with your training data" in prompt,
        "Trump example": 'If source says "President Trump" in 2025' in prompt,
        "Source focus": "Does the SOURCE support the claim?" in prompt,
        "Source-based verdict": "based on source" in prompt.lower(),
    }
    
    print("Checking for temporal context elements:")
    print("-" * 80)
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {'Present' if passed else 'MISSING'}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("="*80)
        print("✅ SUCCESS! All temporal context elements present")
        print("="*80)
        print()
        print("The prompt now includes:")
        print("  • Current date context")
        print("  • Source retrieval date")
        print("  • Explicit instruction to ignore training data conflicts")
        print("  • Example about President Trump in 2025")
        print("  • Focus on source-based verification")
        print()
        print("This should prevent the model from rejecting claims like")
        print("'President Trump in 2025' based on training data.")
        return True
    else:
        print("="*80)
        print("❌ FAILED: Some temporal context elements missing")
        print("="*80)
        return False


def test_date_context_helper():
    """Test the date context helper method."""
    
    print()
    print("="*80)
    print("Testing Date Context Helper")
    print("="*80)
    print()
    
    date_context = ClaimVerifier._get_current_date_context()
    
    print(f"Current date context: {date_context}")
    
    # Check format
    if "2025" not in date_context:
        print("❌ FAILED: Year not in date context")
        return False
    
    if "(" not in date_context or ")" not in date_context:
        print("❌ FAILED: Year not in parentheses")
        return False
    
    print("✅ Date context format correct")
    return True


if __name__ == "__main__":
    print()
    print("🧪 Running Temporal Context Verification Tests")
    print("=" * 80)
    print()
    
    # Test 1: Temporal context in prompt
    success1 = test_temporal_context_in_prompt()
    
    # Test 2: Date context helper
    success2 = test_date_context_helper()
    
    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Temporal context in prompt: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"Date context helper: {'✅ PASSED' if success2 else '❌ FAILED'}")
    print()
    
    if success1 and success2:
        print("✅ All tests passed!")
        print()
        print("The verification stage should now handle temporal facts correctly,")
        print("including facts like 'President Trump in 2025' that might conflict")
        print("with the model's training data.")
    
    sys.exit(0 if (success1 and success2) else 1)
