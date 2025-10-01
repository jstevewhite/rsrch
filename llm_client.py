"""LLM client wrapper supporting OpenAI and litellm."""

import json
import logging
import re
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
        """Generate a JSON completion from the LLM with robust parsing."""
        response = self.complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        
        # Try multiple parsing strategies
        parsed = self._parse_json_response(response)
        if parsed is not None:
            return parsed
        
        # All parsing attempts failed
        logger.error(f"Failed to parse JSON response after all attempts")
        logger.error(f"Raw response (first 500 chars): {response[:500]}")
        raise ValueError(f"Model returned invalid JSON. Response preview: {response[:200]}")
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Try multiple strategies to parse JSON from model response.
        
        Args:
            response: Raw model response
            
        Returns:
            Parsed JSON dict, or None if all attempts fail
        """
        if not response or not response.strip():
            logger.error("Response was empty or whitespace only")
            return None
        
        # Strategy 1: Direct JSON parse (standard case)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.debug("Direct JSON parse failed, trying alternatives...")
        
        # Strategy 2: Extract from markdown code block with ```json
        json_match = re.search(r'```json\s*\n(.+?)\n```', response, re.DOTALL)
        if json_match:
            try:
                logger.debug("Found JSON in ```json code block")
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                logger.debug("JSON code block parse failed")
        
        # Strategy 3: Extract from any markdown code block ```
        code_match = re.search(r'```\s*\n(.+?)\n```', response, re.DOTALL)
        if code_match:
            try:
                logger.debug("Found content in ``` code block")
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                logger.debug("Generic code block parse failed")
        
        # Strategy 4: Extract from inline code blocks `{...}`
        inline_match = re.search(r'`({.+?})`', response, re.DOTALL)
        if inline_match:
            try:
                logger.debug("Found JSON in inline code block")
                return json.loads(inline_match.group(1))
            except json.JSONDecodeError:
                logger.debug("Inline code block parse failed")
        
        # Strategy 5: Find JSON object by looking for { ... } pattern
        # This handles cases where JSON is embedded in prose
        brace_match = re.search(r'(\{[^{}]*\{[^{}]*\}[^{}]*\}|\{[^{}]+\})', response, re.DOTALL)
        if brace_match:
            try:
                logger.debug("Found JSON-like braces pattern")
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                logger.debug("Brace pattern parse failed")
        
        # Strategy 6: Try stripping common prefixes/suffixes
        cleaned = response.strip()
        for prefix in ['```json', '```', 'json:', 'JSON:', 'Response:', 'Output:']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        for suffix in ['```']:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
        
        if cleaned != response:
            try:
                logger.debug("Trying cleaned response after stripping markers")
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.debug("Cleaned response parse failed")
        
        return None
    
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
