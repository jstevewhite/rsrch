"""Content type detection and source authority classification using URL heuristics."""

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


class SourceTier(Enum):
    """Authority tier for source domains.

    Used to weight verification confidence scores based on source authority.
    """
    TIER_1 = "tier_1"  # Authoritative: peer-reviewed, government, primary databases
    TIER_2 = "tier_2"  # Professional: major news, official docs, established organizations
    TIER_3 = "tier_3"  # Community: wikis, forums, user-generated content
    TIER_4 = "tier_4"  # Unvetted: unknown blogs, unclassifiable


class SourceTierClassifier:
    """Classifies source URLs into authority tiers based on domain."""

    # Tier 1: Authoritative - peer-reviewed journals, government, primary databases
    TIER_1_DOMAINS: Set[str] = {
        # Academic / peer-reviewed
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
        'plos.org',
        'biorxiv.org',
        'medrxiv.org',
        'nejm.org',
        'thelancet.com',
        'bmj.com',
        'cell.com',
        'pnas.org',
        'wiley.com',
        'oxfordjournals.org',
        'academic.oup.com',
        'annualreviews.org',
        'jamanetwork.com',
        'acc.org',
        'ahajournals.org',
        'clinicaltrials.gov',
        # Government
        'cdc.gov',
        'fda.gov',
        'who.int',
        'europa.eu',
        'whitehouse.gov',
        'congress.gov',
        'sec.gov',
        'census.gov',
        'bls.gov',
        'nist.gov',
        'ema.europa.eu',
    }

    # Tier 1: TLDs that indicate institutional authority
    TIER_1_TLDS: Set[str] = {'.gov', '.edu', '.mil'}

    # Tier 2: Professional - major news, official documentation, established organizations
    TIER_2_DOMAINS: Set[str] = {
        # Major news organizations
        'nytimes.com',
        'apnews.com',
        'reuters.com',
        'bbc.com',
        'bbc.co.uk',
        'washingtonpost.com',
        'wsj.com',
        'bloomberg.com',
        'ft.com',
        'npr.org',
        'economist.com',
        'cnn.com',
        'theguardian.com',
        # Established tech news
        'techcrunch.com',
        'theverge.com',
        'wired.com',
        'arstechnica.com',
        'forbes.com',
        # Official documentation
        'docs.python.org',
        'docs.microsoft.com',
        'learn.microsoft.com',
        'developer.apple.com',
        'developer.mozilla.org',
        'cloud.google.com',
        'aws.amazon.com',
        # Pre-prints (not peer-reviewed but high quality)
        'arxiv.org',
        'researchgate.net',
        'scholar.google.com',
        # Medical news (professional)
        'medscape.com',
        'statnews.com',
        'fiercepharma.com',
    }

    # Tier 2: Documentation host prefixes
    TIER_2_HOST_PREFIXES: Set[str] = {'docs.', 'developer.', 'dev.', 'api.'}

    # Tier 3: Community - user-generated, wikis, forums
    TIER_3_DOMAINS: Set[str] = {
        'wikipedia.org',
        'en.wikipedia.org',
        'reddit.com',
        'stackoverflow.com',
        'stackexchange.com',
        'medium.com',
        'quora.com',
        'github.com',
        'gitlab.com',
        'dev.to',
        'hashnode.dev',
        'substack.com',
        'wordpress.com',
        'blogspot.com',
        'fandom.com',
        'healthline.com',
        'webmd.com',
        'verywellhealth.com',
    }

    @classmethod
    def classify(cls, url: str) -> SourceTier:
        """Classify a URL into an authority tier.

        Args:
            url: Source URL to classify

        Returns:
            SourceTier enum value (defaults to TIER_4 for unknown domains)
        """
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or '').lower()
        except Exception:
            return SourceTier.TIER_4

        if not host:
            return SourceTier.TIER_4

        # Check Tier 1 TLDs first (.gov, .edu, .mil)
        for tld in cls.TIER_1_TLDS:
            if host.endswith(tld):
                return SourceTier.TIER_1

        # Check Tier 1 domains
        if ContentPatterns._match_domain(host, cls.TIER_1_DOMAINS):
            return SourceTier.TIER_1

        # Check Tier 2 domains
        if ContentPatterns._match_domain(host, cls.TIER_2_DOMAINS):
            return SourceTier.TIER_2

        # Check Tier 2 host prefixes (docs.*, developer.*, etc.)
        if any(host.startswith(prefix) for prefix in cls.TIER_2_HOST_PREFIXES):
            return SourceTier.TIER_2

        # Check Tier 3 domains
        if ContentPatterns._match_domain(host, cls.TIER_3_DOMAINS):
            return SourceTier.TIER_3

        # Default: Tier 4 (unknown / unvetted)
        return SourceTier.TIER_4
