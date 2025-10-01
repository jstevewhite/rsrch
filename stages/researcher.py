"""Research stage - conducts web searches using Serper API."""

import logging
import os
import requests
from typing import List, Dict, Any
from ..models import ResearchPlan, SearchResult, Intent

logger = logging.getLogger(__name__)


class Researcher:
    """Conducts web searches based on research plan."""
    
    def __init__(self):
        """Initialize the researcher."""
        pass
    
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
        logger.info(f"Executing research with {len(plan.search_queries)} queries")
        
        # Determine which search type to use based on intent
        search_type = self._select_search_type(plan.query.intent)
        logger.info(f"Using search type: {search_type}")
        
        all_results = []
        
        # Execute each search query
        for i, search_query in enumerate(plan.search_queries):
            logger.info(f"Query {i+1}/{len(plan.search_queries)}: {search_query.query}")
            
            try:
                # Execute search via Serper API
                results = self._execute_search(
                    query=search_query.query,
                    search_type=search_type,
                    num_results=10
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
        serper_api_key = os.getenv('SERPER_API_KEY')
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
            return self._parse_serper_response(data, search_type)
            
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
