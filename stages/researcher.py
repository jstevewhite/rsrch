"""Research stage - conducts web searches using configurable search providers."""

import logging
import os
import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
from ..models import ResearchPlan, SearchResult, Intent
from ..config import Config

logger = logging.getLogger(__name__)


class Researcher:
    """Conducts web searches based on research plan using configurable providers."""
    
    def __init__(self, config: Config):
        """Initialize the researcher with configuration."""
        self.config = config
        self.max_workers = getattr(config, "search_parallel", 1)
        logger.info(f"Researcher initialized with {self.max_workers} parallel workers")
    
    def search(self, plan: ResearchPlan) -> List[SearchResult]:
        """
        Execute searches based on the research plan.
        
        Uses intent-aware search type selection:
        - NEWS intent -> news search
        - RESEARCH intent -> scholar search
        - Others -> general web search
        
        Args:
            plan: The research plan containing search queries
            
        Returns:
            List of SearchResult objects
        """
        logger.info(f"Executing research with {len(plan.search_queries)} queries using {self.config.search_provider}")
        
        # Determine which search type to use based on intent
        search_type = self._select_search_type(plan.query.intent)
        logger.info(f"Using search type: {search_type}")
        
        # Choose execution strategy
        if self.max_workers > 1 and len(plan.search_queries) > 1:
            logger.info(f"Using parallel search with {self.max_workers} workers")
            return self._search_parallel(plan, search_type)
        else:
            logger.info("Using sequential search")
            return self._search_sequential(plan, search_type)

    def _search_parallel(self, plan: ResearchPlan, search_type: str) -> List[SearchResult]:
        """Execute search queries in parallel using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_results: List[SearchResult] = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                future_to_query = {
                    executor.submit(
                        self._execute_search_safe,
                        q.query,
                        search_type,
                        self.config.search_results_per_query,
                    ): q
                    for q in plan.search_queries
                }
                
                for future in as_completed(future_to_query):
                    q = future_to_query[future]
                    try:
                        results = future.result()
                        if results:
                            logger.info(f"✓ Found {len(results)} results for: {q.query}")
                            all_results.extend(results)
                        else:
                            logger.warning(f"✗ No results for: {q.query}")
                    except Exception as e:
                        logger.error(f"✗ Search failed for '{q.query}': {e}")
            finally:
                executor.shutdown(wait=True)
        
        logger.info(f"Parallel search complete: {len(all_results)} results across {len(plan.search_queries)} queries")
        return all_results

    def _search_sequential(self, plan: ResearchPlan, search_type: str) -> List[SearchResult]:
        """Execute search queries sequentially (existing behavior)."""
        all_results: List[SearchResult] = []
        for i, search_query in enumerate(plan.search_queries):
            logger.info(f"Query {i+1}/{len(plan.search_queries)}: {search_query.query}")
            try:
                results = self._execute_search(
                    query=search_query.query,
                    search_type=search_type,
                    num_results=self.config.search_results_per_query,
                )
                results = self._filter_excluded_results(results)
                logger.info(f"Found {len(results)} results for query: {search_query.query}")
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error executing search '{search_query.query}': {e}")
                continue
        logger.info(f"Sequential search complete: {len(all_results)} total results")
        return all_results

    def _execute_search_safe(self, query: str, search_type: str, num_results: int) -> List[SearchResult]:
        """Safely execute a single search (returns empty list on failure)."""
        try:
            results = self._execute_search(query, search_type, num_results)
            return self._filter_excluded_results(results)
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []
        
    
    def _select_search_type(self, intent: Intent) -> str:
        """
        Select appropriate search type based on query intent.
        
        Args:
            intent: The classified query intent
            
        Returns:
            Serper API search type ('search', 'news', or 'scholar')
        """
        if intent == Intent.NEWS:
            return "news"
        elif intent == Intent.RESEARCH:
            return "scholar"
        else:
            return "search"
    
    def _execute_search(self, query: str, search_type: str = "search", num_results: int = 10) -> List[SearchResult]:
        """
        Execute a search using the configured search provider.
        
        Args:
            query: Search query string
            search_type: Type of search ('search', 'news', or 'scholar')
            num_results: Number of results to return
            
        Returns:
            List of SearchResult objects
            
        Raises:
            Exception if API call fails
        """
        provider = self.config.search_provider
        
        if provider == "SERP":
            return self._execute_serp_search(query, search_type, num_results)
        elif provider == "TAVILY":
            return self._execute_tavily_search(query, search_type, num_results)
        elif provider == "PERPLEXITY":
            # Perplexity Search API does not support distinct types like 'news' or 'scholar'.
            # We'll ignore search_type and perform a general search.
            return self._execute_perplexity_search(query, num_results)
        else:
            raise ValueError(f"Unknown search provider: {provider}")
    
    def _execute_serp_search(self, query: str, search_type: str = "search", num_results: int = 10) -> List[SearchResult]:
        """
        Execute a search using Serper API.
        
        Args:
            query: Search query string
            search_type: Type of search ('search', 'news', or 'scholar')
            num_results: Number of results to return
            
        Returns:
            List of SearchResult objects
            
        Raises:
            Exception if API call fails
        """
        serper_api_key = self.config.serper_api_key
        if not serper_api_key:
            raise Exception("SERPER_API_KEY not found in environment")
        
        # Serper API endpoint
        url = "https://google.serper.dev/search"
        
        # Prepare request
        headers = {
            'X-API-KEY': serper_api_key,
            'Content-Type': 'application/json'
        }
        
        # Apply domain exclusions via query operators if configured
        if self.config.exclude_domains:
            exclude_ops = ' '.join(f"-site:{d}" for d in self.config.exclude_domains)
            query = f"{query} {exclude_ops}".strip()
        
        payload = {
            'q': query,
            'num': num_results,
            'type': search_type  # 'search', 'news', or 'scholar'
        }
        
        try:
            logger.debug(f"Calling Serper API: type={search_type}, query={query}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Serper API returned {len(data.get('organic', []))} organic results")
            
            # Parse the response and limit results to requested number
            results = self._parse_serper_response(data, search_type)
            
            # Limit results to requested number if API returned more
            if len(results) > num_results:
                results = results[:num_results]
                logger.debug(f"Limited results from {len(results)} to {num_results} as requested")
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"Serper API request failed: {e}")
            raise
    
    def _parse_serper_response(self, data: Dict[str, Any], search_type: str) -> List[SearchResult]:
        """
        Parse Serper API response into SearchResult objects.
        
        Args:
            data: JSON response from Serper API
            search_type: Type of search that was performed
            
        Returns:
            List of SearchResult objects
        """
        results = []
        
        # Different response structures for different search types
        if search_type == "news":
            # News results are in 'news' field
            items = data.get('news', [])
        elif search_type == "scholar":
            # Scholar results are in 'organic' field
            items = data.get('organic', [])
        else:
            # Regular search results are in 'organic' field
            items = data.get('organic', [])
        
        # Parse each result
        for i, item in enumerate(items):
            try:
                result = SearchResult(
                    url=item.get('link', ''),
                    title=item.get('title', ''),
                    snippet=item.get('snippet', ''),
                    rank=i + 1,
                    relevance_score=None  # Serper doesn't provide scores
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Error parsing search result: {e}")
                continue
        
        return results
    
    def _execute_tavily_search(self, query: str, search_type: str = "search", num_results: int = 10) -> List[SearchResult]:
        """
        Execute a search using Tavily API.
        
        Args:
            query: Search query string
            search_type: Type of search (currently ignored for Tavily)
            num_results: Number of results to return
            
        Returns:
            List of SearchResult objects
            
        Raises:
            Exception if API call fails
        """
        # Tavily API endpoint
        url = "https://api.tavily.com/search"
        
        # Prepare request
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Use API key if provided (for higher rate limits)
        if self.config.tavily_api_key:
            headers['Authorization'] = f'Bearer {self.config.tavily_api_key}'
            logger.info("Using Tavily API with provided API key")
        else:
            logger.info("Using Tavily API with free tier (no API key)")
        
        # Apply domain exclusions to payload if configured
        exclude_domains = self.config.exclude_domains or []
        payload = {
            'query': query,
            'search_depth': 'basic' if not self.config.tavily_api_key else 'advanced',
            'include_images': False,
            'include_answer': False,
            'include_raw_content': False,
            'max_results': num_results,
            'include_domains': [],
            'exclude_domains': exclude_domains
        }
        
        try:
            logger.debug(f"Calling Tavily API: query={query}")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse the response and limit results to requested number
            results = self._parse_tavily_response(data)
            
            # Limit results to requested number if API returned more
            if len(results) > num_results:
                results = results[:num_results]
                logger.debug(f"Limited Tavily results from {len(results)} to {num_results} as requested")
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"Tavily API request failed: {e}")
            raise
    
    def _parse_tavily_response(self, data: Dict[str, Any]) -> List[SearchResult]:
        """
        Parse Tavily API response into SearchResult objects.
        
        Args:
            data: JSON response from Tavily API
            
        Returns:
            List of SearchResult objects
        """
        results = []
        
        # Tavily returns results in 'results' field
        items = data.get('results', [])
        
        # Parse each result
        for i, item in enumerate(items):
            try:
                result = SearchResult(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    snippet=item.get('content', ''),
                    rank=i + 1,
                    relevance_score=item.get('score')  # Tavily provides relevance scores
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Error parsing Tavily search result: {e}")
                continue
        
        return results

    def _execute_perplexity_search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """
        Execute a search using Perplexity Search API.

        Tries the official Python SDK if available, and falls back to direct HTTP
        if the SDK is not installed. Parses results into SearchResult objects.

        Args:
            query: Search query string
            num_results: Number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            Exception if API call fails or API key is missing
        """
        api_key = self.config.perplexity_api_key or os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise Exception("PERPLEXITY_API_KEY not found in environment")

        # Try SDK first
        try:
            from perplexity import Perplexity  # type: ignore

            logger.debug("Using Perplexity SDK for search")
            client = Perplexity(api_key=api_key)
            response = client.search.create(
                query=query,
                max_results=num_results,
                max_tokens_per_page=1024,
            )

            items = getattr(response, "results", None)
            if items is None and isinstance(response, dict):
                items = response.get("results", [])
            if items is None:
                items = []

            results: List[SearchResult] = []
            for i, item in enumerate(items):
                try:
                    title = getattr(item, "title", None) or item.get("title", "")
                    url = getattr(item, "url", None) or item.get("url", "")
                    snippet = getattr(item, "snippet", None) or item.get("snippet", "")
                    results.append(SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet,
                        rank=i + 1,
                        relevance_score=None
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing Perplexity SDK result: {e}")
                    continue

            # Limit to requested count
            if len(results) > num_results:
                results = results[:num_results]

            return results
        except ImportError:
            logger.info("Perplexity SDK not installed; using HTTP fallback")
        except Exception as e:
            logger.warning(f"Perplexity SDK call failed ({e}); falling back to HTTP")

        # HTTP fallback
        url = "https://api.perplexity.ai/search"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # Apply domain exclusions via query operators if configured
        if self.config.exclude_domains:
            exclude_ops = ' '.join(f"-site:{d}" for d in self.config.exclude_domains)
            query = f"{query} {exclude_ops}".strip()
        
        payload = {
            "query": query,
            # Some docs/sdks use max_results; include top_k for compatibility
            "max_results": num_results,
            "top_k": num_results,
            "max_tokens_per_page": 1024,
        }

        try:
            logger.debug(f"Calling Perplexity Search API: query={query}")
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("results", [])

            results: List[SearchResult] = []
            for i, item in enumerate(items):
                try:
                    results.append(SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        rank=i + 1,
                        relevance_score=None
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing Perplexity HTTP result: {e}")
                    continue

            if len(results) > num_results:
                results = results[:num_results]

            return results
        except requests.RequestException as e:
            logger.error(f"Perplexity API request failed: {e}")
            raise
    
    # --- helpers ---
    def _filter_excluded_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Filter out results whose domain matches configured exclude_domains."""
        if not self.config.exclude_domains:
            return results
        excluded = set(self.config.exclude_domains)
        filtered: List[SearchResult] = []
        for r in results:
            try:
                netloc = urlparse(r.url).netloc.lower()
                # Strip port
                host = netloc.split(':')[0]
                # Match against end of host (handles subdomains)
                if any(host == d or host.endswith(f".{d}") for d in excluded):
                    continue
                filtered.append(r)
            except Exception:
                filtered.append(r)
        return filtered
