"""Content type detection using URL heuristics."""

import logging
from enum import Enum
from typing import Set
from urllib.parse import urlparse

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
        'scholar.google.com',
        'plos.org',
        'nature.com',
        'science.org',
        'sciencedirect.com',
        'springer.com',
        'ieee.org',
        'acm.org',
        'pubmed.ncbi.nlm.nih.gov',
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
        'crates.io',
        'packagist.org',
        'rubygems.org',
        'maven.org',
        'nuget.org',
    }

    # News & Media
    NEWS_DOMAINS: Set[str] = {
        'nytimes.com',
        'apnews.com',
        'reuters.com',
        'bbc.com',
        'cnn.com',
        'theguardian.com',
        'washingtonpost.com',
        'wsj.com',
        'bloomberg.com',
        'ft.com',
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

    # Documentation hostname prefixes (matched against start of hostname)
    DOCS_HOST_PREFIXES: Set[str] = {
        'docs.',
        'developer.',
        'dev.',
        'api.',
    }

    # Documentation path segments (matched against URL path components)
    DOCS_PATH_SEGMENTS: Set[str] = {
        'documentation',
        'reference',
        'manual',
        'wiki',
    }

    @classmethod
    def _match_domain(cls, host: str, domains: Set[str]) -> bool:
        """Check if hostname matches any domain (exact or subdomain match).

        Args:
            host: Parsed hostname (e.g. 'www.arxiv.org')
            domains: Set of domain patterns to match

        Returns:
            True if host matches any domain
        """
        for domain in domains:
            if host == domain or host.endswith('.' + domain):
                return True
        return False

    @classmethod
    def detect_from_url(cls, url: str) -> ContentType:
        """Detect content type from URL using hostname and path matching.

        Uses proper URL parsing to avoid false positives from substring
        matching (e.g. 'arxiv.org' in a URL path won't match).

        Args:
            url: URL to analyze

        Returns:
            Detected ContentType (defaults to GENERAL if no match)
        """
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or '').lower()
            path = (parsed.path or '').lower()
        except Exception:
            return ContentType.GENERAL

        if not host:
            return ContentType.GENERAL

        # Check research domains
        if cls._match_domain(host, cls.RESEARCH_DOMAINS):
            logger.debug(f"Detected RESEARCH content from URL: {url}")
            return ContentType.RESEARCH

        # Check code domains
        if cls._match_domain(host, cls.CODE_DOMAINS):
            logger.debug(f"Detected CODE content from URL: {url}")
            return ContentType.CODE

        # Check news domains
        if cls._match_domain(host, cls.NEWS_DOMAINS):
            logger.debug(f"Detected NEWS content from URL: {url}")
            return ContentType.NEWS

        # Check documentation: hostname prefixes
        if any(host.startswith(prefix) for prefix in cls.DOCS_HOST_PREFIXES):
            logger.debug(f"Detected DOCUMENTATION content from URL: {url}")
            return ContentType.DOCUMENTATION

        # Check documentation: path segments
        path_parts = [p for p in path.split('/') if p]
        if any(segment in path_parts for segment in cls.DOCS_PATH_SEGMENTS):
            logger.debug(f"Detected DOCUMENTATION content from URL: {url}")
            return ContentType.DOCUMENTATION

        return ContentType.GENERAL
