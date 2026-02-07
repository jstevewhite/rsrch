"""Reranker for search results and content."""

import logging
import requests
from typing import List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RankedItem:
    """A ranked item with its score."""
    index: int
    score: float
    original_item: Any


class RerankerClient:
    """
    Client for reranking via API.
    
    Supports multiple API formats:
    - Jina AI Reranker API
    - Cohere Rerank API  
    - LMStudio (OpenAI-compatible format)
    - Custom reranker endpoints
    """
    
    def __init__(
        self,
        api_url: Optional[str],
        api_key: Optional[str],
        model: Optional[str]
    ):
        """
        Initialize reranker client.
        
        Args:
            api_url: Base URL for reranker API
            api_key: API key for authentication
            model: Model name for reranking
        """
        self.api_url = api_url.rstrip('/') if api_url else None
        self.api_key = api_key
        self.model = model
        self.enabled = bool(api_url and model)
        
        if self.enabled:
            logger.info(f"Reranker client initialized: {api_url} (model: {model})")
        else:
            logger.info("Reranker disabled (no URL/model configured)")
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[RankedItem]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: Search query
            documents: List of documents/snippets to rerank
            top_k: Optional limit on results (returns all if None)
            
        Returns:
            List of RankedItem objects sorted by relevance (highest first)
        """
        if not self.enabled:
            logger.warning("Reranker not enabled, returning documents in original order")
            return [
                RankedItem(index=i, score=1.0 - (i / len(documents)), original_item=doc)
                for i, doc in enumerate(documents)
            ]
        
        if not documents:
            return []
        
        try:
            # Try different API formats
            ranked = self._try_rerank_apis(query, documents, top_k)
            logger.info(f"Reranked {len(documents)} documents, returning top {len(ranked)}")
            return ranked
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            logger.warning("Falling back to original order")
            # Return in original order on failure
            return [
                RankedItem(index=i, score=1.0 - (i / len(documents)), original_item=doc)
                for i, doc in enumerate(documents)
            ]
    
    def _try_rerank_apis(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int]
    ) -> List[RankedItem]:
        """
        Try different API formats for reranking.
        
        Args:
            query: Search query
            documents: Documents to rerank
            top_k: Optional top K limit
            
        Returns:
            List of ranked items
        """
        errors = []
        
        # Try Jina AI format (works with LMStudio too)
        try:
            logger.debug("Attempting Jina reranker format...")
            return self._rerank_jina_format(query, documents, top_k)
        except Exception as e:
            error_msg = f"Jina format failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
        
        # Try Cohere format
        try:
            logger.debug("Attempting Cohere reranker format...")
            return self._rerank_cohere_format(query, documents, top_k)
        except Exception as e:
            error_msg = f"Cohere format failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
        
        # Try OpenAI embeddings format (fallback)
        try:
            logger.debug("Attempting embeddings fallback format...")
            return self._rerank_embedding_format(query, documents, top_k)
        except Exception as e:
            error_msg = f"Embedding format failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
        
        # Log all errors before raising
        logger.error(f"All reranking API formats failed. Errors: {'; '.join(errors)}")
        raise Exception("All reranking API formats failed")
    
    def _rerank_jina_format(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int]
    ) -> List[RankedItem]:
        """
        Rerank using Jina AI reranker format.
        
        This format is also compatible with LMStudio when using reranker models.
        """
        url = self.api_url
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_k if top_k else len(documents)
        }
        
        logger.debug(f"Calling Jina reranker: {url}")
        logger.debug(f"Payload: {payload}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response body: {response.text[:500]}")
        response.raise_for_status()
        data = response.json()
        
        # Parse Jina response format
        results = data.get("results", [])
        ranked = []
        for result in results:
            ranked.append(RankedItem(
                index=result.get("index", 0),
                score=result.get("relevance_score", 0.0),
                original_item=documents[result.get("index", 0)]
            ))
        
        return ranked
    
    def _rerank_cohere_format(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int]
    ) -> List[RankedItem]:
        """
        Rerank using Cohere reranker format.
        """
        url = self.api_url
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_k if top_k else len(documents)
        }
        
        logger.debug(f"Calling Cohere reranker: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Parse Cohere response format
        results = data.get("results", [])
        ranked = []
        for result in results:
            ranked.append(RankedItem(
                index=result.get("index", 0),
                score=result.get("relevance_score", 0.0),
                original_item=documents[result.get("index", 0)]
            ))
        
        return ranked
    
    def _rerank_embedding_format(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int]
    ) -> List[RankedItem]:
        """
        Rerank using embeddings + cosine similarity (fallback method).
        
        This uses the standard OpenAI embeddings API format.
        """
        import numpy as np
        
        url = f"{self.api_url}/embeddings"
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Get query embedding
        query_payload = {"input": query, "model": self.model}
        response = requests.post(url, json=query_payload, headers=headers, timeout=30)
        response.raise_for_status()
        query_embedding = np.array(response.json()["data"][0]["embedding"])
        
        # Get document embeddings and calculate similarities
        ranked = []
        for i, doc in enumerate(documents):
            doc_payload = {"input": doc, "model": self.model}
            response = requests.post(url, json=doc_payload, headers=headers, timeout=30)
            response.raise_for_status()
            doc_embedding = np.array(response.json()["data"][0]["embedding"])
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            
            ranked.append(RankedItem(
                index=i,
                score=float(similarity),
                original_item=doc
            ))
        
        # Sort by score
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        # Return top K
        if top_k:
            ranked = ranked[:top_k]
        
        return ranked


class SearchResultReranker:
    """
    Reranks search results before scraping.
    
    Uses reranker API to score query vs. search result snippets,
    then filters to keep only the most relevant results.
    """
    
    def __init__(self, reranker_client: RerankerClient, top_k_ratio: float = 0.25):
        """
        Initialize search result reranker.
        
        Args:
            reranker_client: Reranker API client
            top_k_ratio: Ratio of top results to keep (0.0-1.0)
        """
        self.reranker = reranker_client
        self.top_k_ratio = top_k_ratio
        logger.info(f"Search result reranker initialized (top_k: {top_k_ratio*100:.0f}%)")
    
    def rerank_search_results(self, query: str, search_results: List[Any]) -> List[Any]:
        """
        Rerank search results by relevance.
        
        Args:
            query: Original search query
            search_results: List of SearchResult objects
            
        Returns:
            Filtered list of most relevant SearchResult objects
        """
        if not search_results:
            return []
        
        logger.info(f"Reranking {len(search_results)} search results...")
        
        # Deduplicate by URL (keep first occurrence)
        seen_urls = set()
        deduplicated = []
        for result in search_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                deduplicated.append(result)
            else:
                logger.debug(f"Skipping duplicate URL for reranking: {result.url}")
        
        if len(deduplicated) < len(search_results):
            logger.info(f"Deduplicated search results: {len(search_results)} → {len(deduplicated)} unique URLs")
        
        search_results = deduplicated
        
        # Extract snippets for reranking
        documents = []
        for result in search_results:
            # Combine title and snippet for better context
            doc_text = f"{result.title}. {result.snippet}"
            documents.append(doc_text)
        
        # Calculate top K
        top_k_count = max(1, int(len(search_results) * self.top_k_ratio))
        
        # Rerank using API
        ranked_items = self.reranker.rerank(
            query=query,
            documents=documents,
            top_k=top_k_count
        )
        
        # Extract top results
        top_results = []
        for ranked_item in ranked_items:
            original_result = search_results[ranked_item.index]
            # Update relevance score
            original_result.relevance_score = ranked_item.score
            top_results.append(original_result)
        
        if top_results:
            logger.info(f"Selected top {len(top_results)}/{len(search_results)} results")
            logger.info(f"Relevance scores: {top_results[-1].relevance_score:.3f} - {top_results[0].relevance_score:.3f}")
        
        return top_results
