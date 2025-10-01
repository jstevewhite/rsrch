"""Content scraping stage - extracts content from URLs."""

import logging
import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from ..models import SearchResult, ScrapedContent

logger = logging.getLogger(__name__)


class Scraper:
    """
    Scrapes content from URLs using a dual-strategy approach.
    
    Strategy:
    1. Primary: Custom scraper with BeautifulSoup/requests (free, full content)
    2. Fallback: Serper's get_url MCP tool (paid, for difficult/JS-heavy sites)
    """
    
    # User agent to avoid basic bot detection
    USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    
    def __init__(self, max_workers: int = 5):
        """Initialize the scraper.
        
        Args:
            max_workers: Maximum number of parallel scraping threads (default: 5)
        """
        self.use_fallback_count = 0
        self.max_workers = max_workers
    
    def scrape_results(self, search_results: List[SearchResult]) -> List[ScrapedContent]:
        """
        Scrape content from a list of search results.
        
        Uses parallel scraping for efficiency, with fallback to sequential
        if parallel fails.
        
        Args:
            search_results: List of SearchResult objects containing URLs
            
        Returns:
            List of ScrapedContent objects
        """
        logger.info(f"Scraping content from {len(search_results)} URLs")
        
        urls = [result.url for result in search_results]
        
        # Try parallel scraping first (most efficient)
        try:
            return self._scrape_parallel(urls, search_results)
        except Exception as e:
            logger.warning(f"Parallel scraping failed, using sequential: {e}")
            return self._scrape_sequential(urls, search_results)
    
    def _scrape_parallel(self, urls: List[str], search_results: List[SearchResult]) -> List[ScrapedContent]:
        """
        Scrape multiple URLs in parallel using ThreadPoolExecutor.
        
        Uses multiple threads to scrape URLs concurrently, significantly
        faster than sequential scraping for I/O-bound operations.
        
        Args:
            urls: List of URLs to scrape
            search_results: Original search results for metadata
            
        Returns:
            List of ScrapedContent objects
        """
        logger.info(f"Starting parallel scraping of {len(urls)} URLs with {self.max_workers} workers")
        
        scraped = []
        failed_urls = []
        
        # Use ThreadPoolExecutor for parallel scraping
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scraping tasks
            future_to_url = {
                executor.submit(self._scrape_single_url_safe, url): url 
                for url in urls
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    content = future.result()
                    if content:
                        scraped.append(content)
                        logger.debug(f"✓ Scraped: {url}")
                    else:
                        failed_urls.append(url)
                        logger.warning(f"✗ Failed to scrape: {url}")
                except Exception as e:
                    failed_urls.append(url)
                    logger.error(f"✗ Error scraping {url}: {e}")
        
        logger.info(f"Parallel scraping complete: {len(scraped)}/{len(urls)} successful")
        if failed_urls:
            logger.warning(f"Failed URLs: {failed_urls}")
        
        return scraped
    
    def _scrape_single_url_safe(self, url: str) -> Optional[ScrapedContent]:
        """
        Safely scrape a single URL (returns None on failure instead of raising).
        Used for parallel scraping where we want to continue on errors.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent object or None if scraping failed
        """
        try:
            return self._scrape_single_url(url, use_fallback=True)
        except Exception as e:
            logger.debug(f"Safe scrape failed for {url}: {e}")
            return None
    
    def _scrape_sequential(self, urls: List[str], search_results: List[SearchResult]) -> List[ScrapedContent]:
        """
        Scrape URLs one at a time with primary/fallback strategy.
        
        Args:
            urls: List of URLs to scrape
            search_results: Original search results for metadata
            
        Returns:
            List of ScrapedContent objects
        """
        logger.info("Using sequential scraping with primary/fallback")
        
        scraped = []
        for i, url in enumerate(urls):
            try:
                content = self._scrape_single_url(url)
                if content:
                    scraped.append(content)
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                continue
        
        logger.info(f"Successfully scraped {len(scraped)}/{len(urls)} URLs")
        return scraped
    
    def _scrape_single_url(self, url: str, use_fallback: bool = True) -> ScrapedContent:
        """
        Scrape a single URL using primary method with API fallbacks.
        
        Strategy:
        1. Try BeautifulSoup scraper (free, full content)
        2. If fails and use_fallback=True, try Jina.ai r.jina.ai (paid, handles JS)
        3. If Jina fails, try Serper scrape API (paid, handles JS)
        
        Args:
            url: URL to scrape
            use_fallback: Whether to use paid API fallbacks on failure
            
        Returns:
            ScrapedContent object
            
        Raises:
            Exception if all methods fail
        """
        # Primary: Try BeautifulSoup scraper (FREE)
        try:
            logger.debug(f"Attempting primary scraper (BeautifulSoup) for: {url}")
            content = self._scrape_with_beautifulsoup(url)
            
            if content:
                logger.info(f"✓ Primary scraper succeeded for: {url}")
                return self._create_scraped_content(url, content, scraper="beautifulsoup")
            
        except Exception as e:
            logger.warning(f"Primary scraper failed for {url}: {e}")
            
            if not use_fallback:
                raise Exception(f"Scraping failed for {url}: {e}")
            
            # Try fallback APIs for JS-heavy sites
            logger.info(f"Attempting fallback scrapers for: {url}")
            return self._scrape_with_fallback(url)
    
    def _scrape_with_beautifulsoup(self, url: str, timeout: int = 10) -> Optional[str]:
        """
        Scrape URL content using requests + BeautifulSoup.
        
        Args:
            url: URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Cleaned text content or None if failed
            
        Raises:
            Exception if request fails
        """
        headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script, style, and other non-content tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text = '\n'.join(line for line in lines if line)
            
            return text
            
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise
    
    def _scrape_with_fallback(self, url: str) -> ScrapedContent:
        """
        Try paid API fallbacks for JS-heavy sites.
        
        Tries in order:
        1. Jina.ai r.jina.ai (simpler API, returns markdown)
        2. Serper scrape API (fallback, returns markdown)
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent object
            
        Raises:
            Exception if all fallbacks fail
        """
        # Try Jina.ai first (simpler API)
        try:
            logger.info(f"Trying Jina.ai r.jina.ai for: {url}")
            content = self._scrape_with_jina(url)
            if content:
                self.use_fallback_count += 1
                logger.info(f"✓ Jina.ai scraper succeeded for: {url}")
                return self._create_scraped_content(url, content, scraper="jina.ai")
        except Exception as e:
            logger.warning(f"Jina.ai scraper failed for {url}: {e}")
        
        # Try Serper as final fallback
        try:
            logger.info(f"Trying Serper scrape API for: {url}")
            content = self._scrape_with_serper(url)
            if content:
                self.use_fallback_count += 1
                logger.info(f"✓ Serper scraper succeeded for: {url}")
                return self._create_scraped_content(url, content, scraper="serper")
        except Exception as e:
            logger.error(f"Serper scraper failed for {url}: {e}")
            raise Exception(f"All scrapers failed for {url}")
    
    def _scrape_with_jina(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Scrape URL using Jina.ai r.jina.ai API.
        
        Returns clean markdown. Can handle JS-heavy sites.
        
        Args:
            url: URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Clean markdown content
            
        Raises:
            Exception if request fails
        """
        jina_url = f"https://r.jina.ai/{url}"
        headers = {}
        
        # Add API key if available (for higher rate limit)
        # TODO: Add JINA_API_KEY to .env if you have one
        import os
        jina_api_key = os.getenv('JINA_API_KEY')
        if jina_api_key:
            headers['Authorization'] = f'Bearer {jina_api_key}'
        
        try:
            response = requests.get(jina_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Jina.ai request failed: {e}")
            raise
    
    def _scrape_with_serper(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Scrape URL using Serper scrape API.
        
        Returns markdown content. Handles JS-heavy sites.
        
        Args:
            url: URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Markdown content
            
        Raises:
            Exception if request fails
        """
        import os
        serper_api_key = os.getenv('SERPER_API_KEY')
        if not serper_api_key:
            raise Exception("SERPER_API_KEY not found in environment")
        
        serper_url = "https://scrape.serper.dev"
        headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            'url': url,
            'includeMarkdown': True
        }
        
        try:
            response = requests.post(serper_url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            # Serper returns markdown in 'markdown' or 'text' field
            return data.get('markdown') or data.get('text') or data.get('content')
        except requests.RequestException as e:
            logger.error(f"Serper API request failed: {e}")
            raise
    
    def _create_scraped_content(self, url: str, content: str, scraper: str) -> ScrapedContent:
        """
        Create a ScrapedContent object from raw content.
        
        Args:
            url: Source URL
            content: Scraped content (text)
            scraper: Which scraper was used ('beautifulsoup' or 'get_url')
            
        Returns:
            ScrapedContent object with parsed data
        """
        from datetime import datetime
        
        # Extract title from first line or URL
        lines = content.split('\n')
        title = lines[0][:100] if lines else url
        
        # TODO: Implement proper chunking
        # For now, return full content
        chunks = [content]  # Simple single-chunk approach
        
        return ScrapedContent(
            url=url,
            title=title,
            content=content,
            chunks=chunks,
            metadata={
                "scraper_used": scraper,
                "content_length": len(content),
                "chunk_count": len(chunks)
            },
            retrieved_at=datetime.now()
        )
    
    def get_fallback_usage_stats(self) -> dict:
        """
        Get statistics about fallback scraper usage.
        Useful for monitoring costs.
        
        Returns:
            Dict with usage statistics
        """
        return {
            "fallback_used": self.use_fallback_count,
            "estimated_cost": self.use_fallback_count * 0.005  # Approximate cost per scrape
        }
