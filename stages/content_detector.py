"""Content type detection using URL heuristics."""

import logging
from enum import Enum
from typing import Set

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of content that can be detected."""
    CODE = "code"
    RESEARCH = "research"
    NEWS = "news"
    DOCUMENTATION = "documentation"
    GENERAL = "general"


class ContentPatterns:
    """Domain and keyword patterns for content type detection."""
    
    # Research Papers & Academic
    RESEARCH_DOMAINS: Set[str] = {
        'arxiv.org',
        'scholar.google',
        'plos.org',           # PLOS journals (Public Library of Science)
        'nature.com',
        'science.org',
        'sciencedirect.com',
        'springer.com',
        'ieee.org',
        'acm.org',
        'pubmed.ncbi',
        'nih.gov',
        'doi.org',
        'jstor.org',
        'researchgate.net',
        'biorxiv.org',
        'medrxiv.org',
    }
    
    # Code & Developer Content
    CODE_DOMAINS: Set[str] = {
        'github.com',
        'gitlab.com',
        'stackoverflow.com',
        'stackexchange.com',
        'bitbucket.org',
        'codepen.io',
        'repl.it',
        'codesandbox.io',
        'glitch.com',
        'pypi.org',
        'npmjs.com',
        'crates.io',          # Rust packages
        'packagist.org',      # PHP packages
        'rubygems.org',       # Ruby gems
        'maven.org',
        'nuget.org',
    }
    
    # News & Media
    NEWS_DOMAINS: Set[str] = {
        'nytimes.com',
        'apnews.com',         # Associated Press
        'reuters.com',
        'bbc.com',
        'cnn.com',
        'theguardian.com',
        'washingtonpost.com',
        'wsj.com',            # Wall Street Journal
        'bloomberg.com',
        'ft.com',             # Financial Times
        'npr.org',
        'axios.com',
        'politico.com',
        'techcrunch.com',
        'theverge.com',
        'wired.com',
        'arstechnica.com',
        'forbes.com',
        'businessinsider.com',
    }
    
    # Documentation
    DOCS_PATTERNS: Set[str] = {
        'docs.',              # docs.python.org, docs.microsoft.com, etc.
        'documentation',      # /documentation/ in URL
        'developer.',         # developer.mozilla.org, developer.apple.com
        'dev.',               # dev.to, dev.azure.com
        'api.',               # api.example.com
        'reference',          # /reference/ in URL
        'manual',             # /manual/ in URL
        'wiki',               # /wiki/ in URL
    }
    
    @classmethod
    def detect_from_url(cls, url: str) -> ContentType:
        """Detect content type from URL using pattern matching.
        
        Args:
            url: URL to analyze
            
        Returns:
            Detected ContentType (defaults to GENERAL if no match)
        """
        url_lower = url.lower()
        
        # Check research domains
        if any(domain in url_lower for domain in cls.RESEARCH_DOMAINS):
            logger.debug(f"Detected RESEARCH content from URL: {url}")
            return ContentType.RESEARCH
        
        # Check code domains
        if any(domain in url_lower for domain in cls.CODE_DOMAINS):
            logger.debug(f"Detected CODE content from URL: {url}")
            return ContentType.CODE
        
        # Check news domains
        if any(domain in url_lower for domain in cls.NEWS_DOMAINS):
            logger.debug(f"Detected NEWS content from URL: {url}")
            return ContentType.NEWS
        
        # Check documentation patterns
        if any(pattern in url_lower for pattern in cls.DOCS_PATTERNS):
            logger.debug(f"Detected DOCUMENTATION content from URL: {url}")
            return ContentType.DOCUMENTATION
        
        return ContentType.GENERAL
