"""LLM client wrapper supporting OpenAI and litellm."""

import json
import logging
import re
import time
from typing import List, Dict, Optional, Any, Union
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with LLMs."""
    
    # Global prompt policy to prevent knowledge cutoff refusals
    GLOBAL_POLICY = """You have tool access for web search and scraping. Do not rely on your pretraining knowledge for time-sensitive topics. Never refuse or defer based on a model knowledge cutoff. For any question that could involve recent or evolving info, always perform web search and cite sources with dates. If no sources are found after searching, say "No current sources found" and suggest follow-up queries. Never claim "information won't exist because the date is in the future."""
    
    def __init__(self, api_key: str, api_endpoint: str, default_model: str, max_retries: int = 3, enable_policy: bool = True):
        """Initialize the LLM client.
        
        Args:
            api_key: API key for the LLM service
            api_endpoint: Base URL for the API endpoint
            default_model: Default model to use
            max_retries: Maximum number of retry attempts for empty/invalid responses (default: 3)
        """
        self.client = OpenAI(api_key=api_key, base_url=api_endpoint)
        self.default_model = default_model
        self.max_retries = max_retries
        self.enable_policy = enable_policy
        logger.info(f"Initialized LLM client with endpoint: {api_endpoint}, max_retries: {max_retries}, policy: {enable_policy}")
    
    def complete(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Generate a completion from the LLM."""
        model = model or self.default_model
        
        # Handle both string prompts and message arrays
        if isinstance(prompt, str):
            if self.enable_policy:
                # Prepend global policy to prevent knowledge cutoff refusals
                final_prompt = f"{self.GLOBAL_POLICY}\n\nTask:\n{prompt}"
            else:
                final_prompt = prompt
            messages = [{"role": "user", "content": final_prompt}]
        else:
            # User provided message array - use as-is but optionally inject policy
            messages = prompt
            if self.enable_policy and not any(msg.get("role") == "system" for msg in messages):
                # No system message found - inject policy as system message
                messages = [{"role": "system", "content": self.GLOBAL_POLICY}] + messages
        
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
            prompt_len = len(prompt) if isinstance(prompt, str) else sum(len(msg.get("content", "")) for msg in prompt)
            logger.debug(f"Calling {model} with prompt length: {prompt_len}")
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            logger.debug(f"Received response length: {len(content)}")
            
            # Optional: Detect refusals and auto-retry with stricter reminder
            if self.enable_policy and self._detect_refusal(content):
                logger.warning("Detected knowledge cutoff refusal, retrying with stricter reminder")
                retry_prompt = f"{self.GLOBAL_POLICY}\n\nSTRICT RULE: Never mention knowledge cutoff. Use web search.\n\nTask:\n{prompt if isinstance(prompt, str) else 'Previous task'}"
                kwargs["messages"] = [{"role": "user", "content": retry_prompt}]
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                logger.info("Successfully retried after refusal detection")
            
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
        """Generate a JSON completion from the LLM with robust parsing and retry logic.
        
        Retries up to max_retries times with exponential backoff when:
        - Response is empty or whitespace only
        - Response cannot be parsed as valid JSON
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    backoff = 2 ** (attempt - 1)
                    logger.info(f"Retrying JSON completion (attempt {attempt + 1}/{self.max_retries}) after {backoff}s backoff...")
                    time.sleep(backoff)
                
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
                    if attempt > 0:
                        logger.info(f"Successfully parsed JSON on retry attempt {attempt + 1}")
                    return parsed
                
                # Parsing failed but we have a response - save error and retry
                last_error = ValueError(f"Model returned invalid JSON. Response preview: {response[:200]}")
                logger.warning(f"Failed to parse JSON response on attempt {attempt + 1}/{self.max_retries}")
                logger.debug(f"Raw response (first 500 chars): {response[:500]}")
                
            except Exception as e:
                # Network or API error - save and retry
                last_error = e
                logger.warning(f"Error during JSON completion attempt {attempt + 1}/{self.max_retries}: {e}")
        
        # All retry attempts exhausted
        logger.error(f"Failed to get valid JSON response after {self.max_retries} attempts")
        if last_error:
            raise last_error
        else:
            raise ValueError("Failed to get valid JSON response after all retry attempts")
    
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
    
    def _detect_refusal(self, response: str) -> bool:
        """Detect if the model refused based on knowledge cutoff."""
        refusal_patterns = [
            r"knowledge cutoff",
            r"cannot browse",
            r"as an ai",
            r"training data.*cutoff",
            r"information.*won't exist.*future",
            r"cannot access.*recent",
            r"training.*ends.*in"
        ]
        
        return any(re.search(pattern, response, re.IGNORECASE) for pattern in refusal_patterns)
    
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
