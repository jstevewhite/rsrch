"""Research stage - conducts web searches using serper-api-mcp."""

import logging
from typing import List
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
        
        Uses intent-aware search tool selection:
        - NEWS intent -> search_news
        - RESEARCH intent -> search_scholar
        - Others -> search (general web search)
        
        Args:
            plan: The research plan containing search queries
            
        Returns:
            List of SearchResult objects
        """
        logger.info(f"Executing research with {len(plan.search_queries)} queries")
        
        # Determine which search tool to use based on intent
        search_tool = self._select_search_tool(plan.query.intent)
        logger.info(f"Using search tool: {search_tool}")
        
        all_results = []
        
        # Execute each search query
        for i, search_query in enumerate(plan.search_queries):
            logger.info(f"Query {i+1}/{len(plan.search_queries)}: {search_query.query}")
            
            try:
                # TODO: Implement actual MCP tool call
                # results = call_mcp_tool(
                #     name=search_tool,
                #     input={
                #         "query": search_query.query,
                #         "num_results": 10,
                #         "country_code": "us",
                #         "language": "en"
                #     }
                # )
                
                # Parse results into SearchResult objects
                # For now, placeholder:
                logger.warning("MCP tool call not yet implemented - using placeholder")
                results = []
                
                all_results.extend(results)
                
            except Exception as e:
                logger.error(f"Error executing search '{search_query.query}': {e}")
                continue
        
        logger.info(f"Research complete: found {len(all_results)} total results")
        return all_results
    
    def _select_search_tool(self, intent: Intent) -> str:
        """
        Select appropriate search tool based on query intent.
        
        Args:
            intent: The classified query intent
            
        Returns:
            Name of the search tool to use
        """
        if intent == Intent.NEWS:
            return "search_news"
        elif intent == Intent.RESEARCH:
            return "search_scholar"
        else:
            return "search"
