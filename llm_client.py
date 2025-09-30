"""LLM client wrapper supporting OpenAI and litellm."""

import json
import logging
from typing import List, Dict, Optional, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLMs."""
    
    def __init__(self, api_key: str, api_endpoint: str, default_model: str):
        """Initialize the LLM client."""
        self.client = OpenAI(api_key=api_key, base_url=api_endpoint)
        self.default_model = default_model
        logger.info(f"Initialized LLM client with endpoint: {api_endpoint}")
    
    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Generate a completion from the LLM."""
        model = model or self.default_model
        
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        try:
            logger.debug(f"Calling {model} with prompt length: {len(prompt)}")
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            logger.debug(f"Received response length: {len(content)}")
            return content
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise
    
    def complete_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON completion from the LLM."""
        response = self.complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response}")
            raise
    
    def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Generate embeddings for the given texts."""
        model = model or "text-embedding-3-small"
        
        try:
            logger.debug(f"Generating embeddings for {len(texts)} texts")
            response = self.client.embeddings.create(
                model=model,
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
