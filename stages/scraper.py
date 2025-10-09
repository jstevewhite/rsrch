"""Content scraping stage - extracts content from URLs."""

import logging
import re
import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup, NavigableString
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
    
    def __init__(self, max_workers: int = 5, output_format: str = "markdown", preserve_tables: bool = True):
        """Initialize the scraper.
        
        Args:
            max_workers: Maximum number of parallel scraping threads (default: 5)
            output_format: Preferred output format (e.g., 'markdown')
            preserve_tables: If True, attempt to preserve/emit tables in content
        """
        self.use_fallback_count = 0
        self.max_workers = max_workers
        self.output_format = (output_format or "").lower() or "markdown"
        self.preserve_tables = bool(preserve_tables)
    
    def scrape_url(self, url: str, use_fallback: bool = True) -> Optional[ScrapedContent]:
        """
        Scrape a single URL.
        
        Public method for scraping individual URLs, useful for re-scraping
        sources during claim verification.
        
        Args:
            url: URL to scrape
            use_fallback: Whether to use paid API fallbacks on failure (default: True)
            
        Returns:
            ScrapedContent object, or None if scraping failed
        """
        try:
            return self._scrape_single_url(url, use_fallback=use_fallback)
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
    
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
            Cleaned text (Markdown if configured) or None if failed
            
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
            
            # If we want Markdown output, convert entire DOM to Markdown
            if self.output_format == 'markdown':
                if self.preserve_tables:
                    try:
                        self._replace_tables_with_markdown(soup)
                    except Exception as e:
                        logger.debug(f"Table to Markdown conversion skipped due to error: {e}")
                md = self._html_to_markdown(soup)
                return md
            
            # Otherwise, extract plain text
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
            content: Scraped content (text/markdown)
            scraper: Which scraper was used ('beautifulsoup' or 'get_url')
            
        Returns:
            ScrapedContent object with parsed data
        """
        from datetime import datetime
        
        # Extract title from first non-empty line or URL
        lines = [ln for ln in content.split('\n') if ln.strip()]
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
                "chunk_count": len(chunks),
                "output_format": self.output_format,
                "preserve_tables": self.preserve_tables,
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
    
    # --- Internal helpers for table preservation ---
    def _replace_tables_with_markdown(self, soup: BeautifulSoup) -> None:
        """Replace all HTML <table> tags in the soup with Markdown table strings.
        Best-effort: handles simple tables without complex rowspan/colspan.
        """
        tables = soup.find_all('table')
        if not tables:
            return
        for tbl in tables:
            md = self._html_table_to_markdown(tbl)
            tbl.replace_with(NavigableString(md))
    
    def _html_table_to_markdown(self, table_tag) -> str:
        """Convert a BeautifulSoup <table> tag to a Markdown pipe table string.
        Limitations: minimal support for colspan/rowspan (ignored), nested tables treated as text.
        """
        def sanitize_cell(txt: str) -> str:
            if txt is None:
                return ""
            # Collapse whitespace, escape pipes, strip newlines
            s = ' '.join(txt.split())
            s = s.replace('|', '\\|')
            return s
        
        rows = table_tag.find_all('tr')
        if not rows:
            return "\n\n"  # empty placeholder
        
        # Determine header
        header_cells = []
        # Prefer thead > tr > th if present
        thead = table_tag.find('thead')
        if thead:
            ths = thead.find_all('th')
            header_cells = [sanitize_cell(th.get_text(strip=True)) for th in ths]
        if not header_cells and rows:
            # Fallback to first row's th/td
            first = rows[0]
            ths = first.find_all(['th', 'td'])
            header_cells = [sanitize_cell(th.get_text(strip=True)) for th in ths]
            # Remove first row from body if we used it as header
            rows = rows[1:]
        
        col_count = max(1, len(header_cells))
        header_line = "| " + " | ".join(header_cells) + " |"
        sep_line = "| " + " | ".join(["---"] * col_count) + " |"
        
        body_lines = []
        for tr in rows:
            tds = tr.find_all(['td', 'th'])
            cells = [sanitize_cell(td.get_text(strip=True)) for td in tds]
            # Normalize cell count
            if len(cells) < col_count:
                cells.extend([""] * (col_count - len(cells)))
            elif len(cells) > col_count:
                cells = cells[:col_count]
            body_lines.append("| " + " | ".join(cells) + " |")
        
        md = "\n\n" + "\n".join([header_line, sep_line] + body_lines) + "\n\n"
        return md
    
    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """Convert a BeautifulSoup DOM to Markdown (best-effort).
        Supports: headings, paragraphs, lists, links, code/pre, blockquotes, images, hr, and tables (pre-converted).
        """
        def node_to_md(node, list_depth=0, ordered=False, index=1):
            # Navigable text or pre-converted Markdown (e.g., tables)
            if isinstance(node, NavigableString):
                return str(node)
            if not hasattr(node, 'name'):
                return ''
            name = node.name.lower()
            # Gather child content
            def children_md():
                parts = []
                child_index = 1
                for child in node.children:
                    parts.append(node_to_md(child, list_depth=list_depth, ordered=ordered, index=child_index))
                    if ordered:
                        child_index += 1
                return ''.join(parts)
            
            if name in ['style', 'script', 'nav', 'footer', 'header', 'aside']:
                return ''
            if name in ['h1','h2','h3','h4','h5','h6']:
                level = int(name[1])
                return f"\n\n{'#'*level} {children_md().strip()}\n\n"
            if name in ['p']:
                return f"\n\n{children_md().strip()}\n\n"
            if name == 'br':
                return "\n"
            if name == 'a':
                href = node.get('href') or ''
                text = children_md() or (node.get_text(strip=True) if node else '')
                if href:
                    return f"[{text}]({href})"
                return text
            if name in ['strong','b']:
                return f"**{children_md().strip()}**"
            if name in ['em','i']:
                return f"*{children_md().strip()}*"
            if name == 'code':
                # Inline code unless inside pre
                if node.parent and node.parent.name and node.parent.name.lower() == 'pre':
                    return children_md()
                return f"`{children_md().strip()}`"
            if name == 'pre':
                # Preserve code blocks
                text = node.get_text('\n')
                return f"\n\n```\n{text.strip()}\n```\n\n"
            if name == 'blockquote':
                content = children_md().strip()
                quoted = '\n'.join([f"> {ln}" if ln.strip() else '>' for ln in content.splitlines()])
                return f"\n\n{quoted}\n\n"
            if name == 'hr':
                return "\n\n---\n\n"
            if name == 'img':
                alt = node.get('alt') or ''
                src = node.get('src') or ''
                return f"![{alt}]({src})"
            if name in ['ul','ol']:
                items = []
                for idx, li in enumerate(node.find_all('li', recursive=False), start=1):
                    li_text = node_to_md(li, list_depth=list_depth+1, ordered=(name=='ol'), index=idx)
                    items.append(li_text)
                return "".join(items) + ("\n" if items else '')
            if name == 'li':
                prefix = (f"{index}. " if ordered else "- ")
                content = ''.join(node_to_md(child, list_depth=list_depth, ordered=ordered) for child in node.children)
                # Indentation for nested lists
                indent = '  ' * max(0, list_depth-1)
                lines = [ln for ln in content.strip().splitlines() if ln.strip()]
                if not lines:
                    return ''
                first = f"{indent}{prefix}{lines[0]}\n"
                rest = ''.join(f"{indent}  {ln}\n" for ln in lines[1:])
                return first + rest
            if name in ['table']:
                # Should already be replaced by Markdown string; fallback to text
                return "\n\n" + node.get_text(" ", strip=True) + "\n\n"
            if name in ['tr','td','th','thead','tbody','tfoot']:
                # Should not occur if table replaced; ignore/flatten
                return node.get_text(" ", strip=True)
            # Generic container
            return children_md()
        
        # Prefer body if present
        root = soup.body if hasattr(soup, 'body') and soup.body else soup
        md = node_to_md(root)
        # Normalize excessive blank lines
        md = re.sub(r"\n{3,}", "\n\n", md)
        # Trim trailing spaces on lines
        md = "\n".join(line.rstrip() for line in md.splitlines())
        md = md.strip() + "\n"
        return md
