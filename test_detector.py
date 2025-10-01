#!/usr/bin/env python3
"""Simple test for content type detection."""

import sys
import os

# Add the stages directory to path to avoid __init__.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'stages'))

# Import directly without going through __init__.py
import content_detector

def main():
    print("="*80)
    print("CONTENT TYPE DETECTION TESTS")
    print("="*80)
    print()
    
    test_cases = [
        ("https://arxiv.org/abs/2301.00001", "research"),
        ("https://plos.org/journal.pone.0123456", "research"),
        ("https://stackoverflow.com/questions/12345", "code"),
        ("https://github.com/user/repo", "code"),
        ("https://nytimes.com/article", "news"),
        ("https://reuters.com/article", "news"),
        ("https://techcrunch.com/2024/startup", "news"),
        ("https://docs.python.org/3/", "documentation"),
        ("https://example.com/blog", "general"),
    ]
    
    passed = 0
    failed = 0
    
    for url, expected in test_cases:
        detected = content_detector.ContentPatterns.detect_from_url(url)
        status = "✓" if detected.value == expected else "✗"
        
        if detected.value == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {url}")
        print(f"  Expected: {expected}, Got: {detected.value}")
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()


if __name__ == "__main__":
    main()
