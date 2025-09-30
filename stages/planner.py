"""Research planning stage."""

import logging
from typing import List
from ..models import Query, ResearchPlan, SearchQuery, Intent
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)


class Planner:
    """Plans research approach based on query and intent."""
    
    def __init__(self, llm_client: LLMClient, model: str):
        """Initialize the planner."""
        self.llm_client = llm_client
        self.model = model
    
    def plan(self, query: Query) -> ResearchPlan:
        """Create a research plan for the query."""
        logger.info(f"Planning research for query: {query.text[:100]}...")
        
        intent_str = query.intent.value if query.intent else "general"
        
        prompt = f"""You are a research planner. Given a user query and its intent, create a comprehensive research plan.

Query: "{query.text}"
Intent: {intent_str}

Create a research plan with:
1. A list of report sections that should be covered
2. Specific search queries to gather information for each section
3. Rationale for the overall approach

Consider:
- What information is needed to fully answer the query?
- What are the most important aspects to cover?
- What search queries will find the most relevant and authoritative sources?
- For CODE intent: focus on documentation, examples, and best practices
- For NEWS intent: prioritize recent sources and multiple perspectives
- For RESEARCH intent: include academic sources and in-depth analysis

Respond with a JSON object:
{{
  "sections": ["Section 1 title", "Section 2 title", ...],
  "search_queries": [
    {{"query": "search query 1", "purpose": "what this query aims to find", "priority": 1}},
    {{"query": "search query 2", "purpose": "what this query aims to find", "priority": 2}}
  ],
  "rationale": "Explanation of the research approach"
}}

Priority is 1 (highest) to 5 (lowest).
"""
        
        try:
            response = self.llm_client.complete_json(
                prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_tokens=2000,
            )
            
            sections = response.get("sections", [])
            search_queries_data = response.get("search_queries", [])
            rationale = response.get("rationale", "")
            
            search_queries = [
                SearchQuery(
                    query=sq["query"],
                    purpose=sq["purpose"],
                    priority=sq.get("priority", 3)
                )
                for sq in search_queries_data
            ]
            
            plan = ResearchPlan(
                query=query,
                sections=sections,
                search_queries=search_queries,
                rationale=rationale,
            )
            
            logger.info(f"Created plan with {len(sections)} sections and {len(search_queries)} queries")
            logger.debug(f"Sections: {sections}")
            
            return plan
            
        except Exception as e:
            logger.error(f"Error creating research plan: {e}")
            # Return a minimal plan
            return ResearchPlan(
                query=query,
                sections=["Overview", "Details", "Summary"],
                search_queries=[SearchQuery(query=query.text, purpose="Main query", priority=1)],
                rationale="Fallback plan due to error",
            )
