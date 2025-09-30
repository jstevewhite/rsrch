"""Intent classification stage."""

import logging
from typing import Dict, Any
from ..models import Query, Intent
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Classifies user query intent."""
    
    def __init__(self, llm_client: LLMClient, model: str):
        """Initialize the intent classifier."""
        self.llm_client = llm_client
        self.model = model
    
    def classify(self, query: Query) -> Intent:
        """Classify the intent of a query."""
        logger.info(f"Classifying intent for query: {query.text[:100]}...")
        
        prompt = f"""Analyze the following user query and classify its intent into one of these categories:

- INFORMATIONAL: General questions seeking factual information
- COMPARATIVE: Questions comparing multiple things
- NEWS: Questions about current events or recent news
- CODE: Questions about programming, code examples, or technical implementation
- TUTORIAL: Questions seeking step-by-step instructions or how-to guides
- RESEARCH: Academic or in-depth research questions
- GENERAL: General conversational queries

Query: "{query.text}"

Respond with a JSON object containing:
- "intent": the category (one of the above)
- "confidence": a number between 0 and 1
- "reasoning": brief explanation for the classification

Example response:
{{"intent": "NEWS", "confidence": 0.95, "reasoning": "Query asks about latest news on a specific topic"}}
"""
        
        try:
            response = self.llm_client.complete_json(
                prompt=prompt,
                model=self.model,
                temperature=0.3,
            )
            
            intent_str = response.get("intent", "GENERAL").upper()
            confidence = response.get("confidence", 0.5)
            reasoning = response.get("reasoning", "")
            
            logger.info(f"Classified as {intent_str} (confidence: {confidence:.2f})")
            logger.debug(f"Reasoning: {reasoning}")
            
            # Map string to Intent enum
            try:
                intent = Intent[intent_str]
            except KeyError:
                logger.warning(f"Unknown intent '{intent_str}', defaulting to GENERAL")
                intent = Intent.GENERAL
            
            query.intent = intent
            return intent
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            query.intent = Intent.GENERAL
            return Intent.GENERAL
