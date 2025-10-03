"""Research stage - conducts web searches using configurable search providers."""

import logging
import os
import requests
from typing import List, Dict, Any
from ..models import ResearchPlan, SearchResult, Intent
from ..config import Config

logger = logging.getLogger(__name__)


class Researcher:
    """Conducts web searches based on research plan using configurable providers."""
    
    def __init__(self, config: Config):
        """Initialize the researcher with configuration."""
        self.config = config
    
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
        
        all_results = []
        
        # Execute each search query
        for i, search_query in enumerate(plan.search_queries):
            logger.info(f"Query {i+1}/{len(plan.search_queries)}: {search_query.query}")
            
            try:
                # Execute search using configured provider
                results = self._execute_search(
                    query=search_query.query,
                    search_type=search_type,
                    num_results=self.config.search_results_per_query
                )
                
                logger.info(f"Found {len(results)} results for query: {search_query.query}")
                all_results.extend(results)
                
            except Exception as e:
                logger.error(f"Error executing search '{search_query.query}': {e}")
                continue
        
        logger.info(f"Research complete: found {len(all_results)} total results")
        return all_results
    
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
        
        payload = {
            'query': query,
            'search_depth': 'basic' if not self.config.tavily_api_key else 'advanced',
            'include_images': False,
            'include_answer': False,
            'include_raw_content': False,
            'max_results': num_results,
            'include_domains': [],
            'exclude_domains': []
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
