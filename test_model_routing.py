"""Test script for content type detection and model routing."""

import logging
from config import Config
from stages.content_detector import ContentPatterns, ContentType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_content_detection():
    """Test URL-based content type detection."""
    print("="*80)
    print("CONTENT TYPE DETECTION TESTS")
    print("="*80)
    print()
    
    test_cases = [
        # Research
        ("https://arxiv.org/abs/2301.00001", ContentType.RESEARCH),
        ("https://plos.org/plosone/article?id=10.1371/journal.pone.0123456", ContentType.RESEARCH),
        ("https://scholar.google.com/scholar?q=machine+learning", ContentType.RESEARCH),
        
        # Code
        ("https://github.com/openai/gpt-4", ContentType.CODE),
        ("https://stackoverflow.com/questions/12345", ContentType.CODE),
        ("https://pypi.org/project/numpy/", ContentType.CODE),
        
        # News
        ("https://nytimes.com/2024/01/01/technology/ai-advances.html", ContentType.NEWS),
        ("https://reuters.com/technology/2024/01/01/ai-breakthrough/", ContentType.NEWS),
        ("https://techcrunch.com/2024/01/01/startup-funding/", ContentType.NEWS),
        
        # Documentation
        ("https://docs.python.org/3/library/", ContentType.DOCUMENTATION),
        ("https://developer.mozilla.org/en-US/docs/Web/JavaScript", ContentType.DOCUMENTATION),
        
        # General
        ("https://example.com/blog/post", ContentType.GENERAL),
        ("https://random-website.org/article", ContentType.GENERAL),
    ]
    
    passed = 0
    failed = 0
    
    for url, expected in test_cases:
        detected = ContentPatterns.detect_from_url(url)
        status = "✓" if detected == expected else "✗"
        
        if detected == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {url}")
        print(f"  Expected: {expected.value}, Got: {detected.value}")
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()


def test_model_routing():
    """Test model routing configuration."""
    print("="*80)
    print("MODEL ROUTING TESTS")
    print("="*80)
    print()
    
    # Load config
    config = Config.from_env()
    
    print(f"Default MRS model: {config.mrs_model_default}")
    print()
    
    # Test model selection for each content type
    content_types = [
        ContentType.CODE,
        ContentType.RESEARCH,
        ContentType.NEWS,
        ContentType.DOCUMENTATION,
        ContentType.GENERAL,
    ]
    
    print("Model Selection by Content Type:")
    print("-" * 80)
    for content_type in content_types:
        model = config.get_mrs_model_for_content_type(content_type.value)
        print(f"{content_type.value:15} -> {model}")
    
    print()
    
    # Test with real URLs
    print("Model Selection by URL:")
    print("-" * 80)
    
    test_urls = [
        "https://arxiv.org/abs/2301.00001",
        "https://stackoverflow.com/questions/12345",
        "https://nytimes.com/article",
        "https://docs.python.org/3/",
        "https://example.com/blog",
    ]
    
    for url in test_urls:
        content_type = ContentPatterns.detect_from_url(url)
        model = config.get_mrs_model_for_content_type(content_type.value)
        print(f"{url:50} -> {content_type.value:15} -> {model}")
    
    print()


def main():
    """Run all tests."""
    test_content_detection()
    test_model_routing()


if __name__ == "__main__":
    main()
