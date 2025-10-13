"""Context Assembly stage - ranks and filters summaries using embeddings."""

import logging
import sqlite3
import requests
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from ..models import Summary, ContextPackage, ResearchPlan, Query

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Client for generating embeddings via API."""
    
    def __init__(self, api_url: str, api_key: Optional[str], model: str):
        """
        Initialize embedding client.
        
        Args:
            api_url: Base URL for embedding API
            api_key: API key for authentication
            model: Model name for embeddings
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        logger.info(f"Embedding client initialized: {api_url} (model: {model})")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        # OpenAI-compatible embedding API
        url = f"{self.api_url}/embeddings"
        
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "input": text,
            "model": self.model
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract embedding from response
            embedding = data["data"][0]["embedding"]
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # For now, generate one at a time
        # Could be optimized to use batch API if available
        embeddings = []
        for i, text in enumerate(texts):
            try:
                logger.debug(f"Generating embedding {i+1}/{len(texts)}")
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for text {i}: {e}")
                # Use zero vector as fallback
                embeddings.append([0.0] * 1536)  # Assume 1536 dimensions
        
        return embeddings


class VectorStore:
    """SQLite-based vector store using VSS extension."""
    
    def __init__(self, db_path: Path):
        """
        Initialize vector store.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _connect(self) -> sqlite3.Connection:
        """Open a connection and register custom SQL functions (e.g., cosine_sim)."""
        conn = sqlite3.connect(str(self.db_path))
        # Register cosine similarity over BLOB embeddings
        def _cosine_sim_sql(emb_blob: bytes, query_blob: bytes, dim: int) -> float:
            try:
                a = np.frombuffer(emb_blob, dtype=np.float32, count=dim)
                b = np.frombuffer(query_blob, dtype=np.float32, count=dim)
                na = np.linalg.norm(a)
                nb = np.linalg.norm(b)
                if na == 0 or nb == 0:
                    return 0.0
                return float(np.dot(a, b) / (na * nb))
            except Exception:
                return 0.0
        conn.create_function("cosine_sim", 3, _cosine_sim_sql)
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._connect()
        cursor = conn.cursor()
        
        # Create summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                relevance_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create embeddings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_id INTEGER NOT NULL,
                embedding BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                FOREIGN KEY (summary_id) REFERENCES summaries(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Vector store initialized at: {self.db_path}")
    
    def store_summaries(self, summaries: List[Summary], embeddings: List[List[float]]) -> List[int]:
        """
        Store summaries and their embeddings.
        
        Args:
            summaries: List of Summary objects
            embeddings: List of embedding vectors
            
        Returns:
            List of summary IDs
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        summary_ids = []
        for summary, embedding in zip(summaries, embeddings):
            # Store summary
            cursor.execute("""
                INSERT INTO summaries (url, title, summary_text, relevance_score)
                VALUES (?, ?, ?, ?)
            """, (
                summary.url,
                summary.citations[0].title if summary.citations else "Unknown",
                summary.text,
                summary.relevance_score
            ))
            summary_id = cursor.lastrowid
            summary_ids.append(summary_id)
            
            # Store embedding as binary blob
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            dimension = len(embedding)
            
            cursor.execute("""
                INSERT INTO embeddings (summary_id, embedding, dimension)
                VALUES (?, ?, ?)
            """, (summary_id, embedding_bytes, dimension))
        
        conn.commit()
        conn.close()
        logger.info(f"Stored {len(summaries)} summaries with embeddings")
        return summary_ids
    
    def get_embedding(self, summary_id: int) -> Optional[np.ndarray]:
        """
        Retrieve embedding for a summary.
        
        Args:
            summary_id: Summary ID
            
        Returns:
            Embedding as numpy array or None
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT embedding, dimension FROM embeddings
            WHERE summary_id = ?
        """, (summary_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            embedding_bytes, dimension = row
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
            return embedding
        return None


    def search_similar_in_ids(self, summary_ids: List[int], query_embedding: List[float], top_k: int) -> List[Tuple[int, float]]:
        """Search top-k similar summaries among a given set of summary IDs using SQL cosine_sim.
        Returns list of (summary_id, score) sorted by score desc.
        """
        if not summary_ids:
            return []
        conn = self._connect()
        cursor = conn.cursor()
        emb_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        # Build parameterized IN clause
        placeholders = ','.join(['?'] * len(summary_ids))
        sql = f"""
            SELECT s.id, cosine_sim(e.embedding, ?, e.dimension) AS score
            FROM summaries s
            JOIN embeddings e ON e.summary_id = s.id
            WHERE s.id IN ({placeholders})
            ORDER BY score DESC
            LIMIT ?
        """
        params = [emb_bytes] + summary_ids + [top_k]
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [(int(r[0]), float(r[1])) for r in rows]

class ContextAssembler:
    """
    Assembles context for report generation using embedding-based ranking.
    
    Strategy:
    1. Generate embeddings for query and all summaries
    2. Calculate cosine similarity between query and each summary
    3. Rank summaries by relevance
    4. Filter top K% most relevant summaries
    5. Package for report generation
    """
    
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        top_k_ratio: float = 0.25
    ):
        """
        Initialize context assembler.
        
        Args:
            embedding_client: Client for generating embeddings
            vector_store: Vector database for storage
            top_k_ratio: Ratio of top summaries to keep (0.0-1.0)
        """
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.top_k_ratio = top_k_ratio
        logger.info(f"Context assembler initialized (top_k: {top_k_ratio*100:.0f}%)")
    
    def assemble_context(
        self,
        summaries: List[Summary],
        plan: ResearchPlan
    ) -> ContextPackage:
        """
        Assemble context package with ranked summaries.
        
        Args:
            summaries: List of summaries to rank
            plan: Research plan with query
            
        Returns:
            ContextPackage with top-ranked summaries
        """
        logger.info(f"Assembling context from {len(summaries)} summaries")
        
        if not summaries:
            logger.warning("No summaries provided for context assembly")
            return ContextPackage(
                query=plan.query,
                plan=plan,
                summaries=[],
                additional_context={}
            )
        
        # Deduplicate by URL (keep first occurrence of each URL)
        seen_urls = set()
        deduplicated = []
        for summary in summaries:
            if summary.url not in seen_urls:
                seen_urls.add(summary.url)
                deduplicated.append(summary)
            else:
                logger.debug(f"Skipping duplicate URL: {summary.url}")
        
        if len(deduplicated) < len(summaries):
            logger.info(f"Deduplicated: {len(summaries)} → {len(deduplicated)} summaries")
        
        summaries = deduplicated
        
        # Step 1: Generate embeddings for query
        logger.info("Generating query embedding...")
        query_text = plan.query.text
        query_embedding = self.embedding_client.generate_embedding(query_text)
        
        # Step 2: Generate embeddings for summaries
        logger.info(f"Generating embeddings for {len(summaries)} summaries...")
        summary_texts = [s.text for s in summaries]
        summary_embeddings = self.embedding_client.generate_embeddings_batch(summary_texts)
        
        # Step 3: Store in vector database
        logger.info("Storing embeddings in vector database...")
        summary_ids = self.vector_store.store_summaries(summaries, summary_embeddings)
        
        # Step 4: Calculate relevance scores via SQLite vector search
        logger.info("Calculating relevance scores (SQLite vector search)...")
        # Determine top-k count first for efficiency
        top_k_count = max(1, int(len(summaries) * self.top_k_ratio))
        id_score_pairs = self.vector_store.search_similar_in_ids(summary_ids, query_embedding, top_k_count)
        # Map summary_id -> summary object (preserve only those returned)
        id_to_summary = {sid: s for sid, s in zip(summary_ids, summaries)}
        top_summaries: List[Summary] = []
        for sid, score in id_score_pairs:
            s = id_to_summary.get(sid)
            if s is not None:
                s.relevance_score = float(score)
                top_summaries.append(s)
        
        if not top_summaries:
            logger.warning("SQLite vector search returned no matches; falling back to in-memory ranking")
            ranked_summaries = self._rank_by_relevance(
                summaries,
                summary_embeddings,
                query_embedding
            )
            top_summaries = ranked_summaries[:top_k_count]
        
        logger.info(f"Selected top {len(top_summaries)}/{len(summaries)} summaries (threshold: {top_summaries[-1].relevance_score:.3f})")
        
        # Step 6: Package context
        context = ContextPackage(
            query=plan.query,
            plan=plan,
            summaries=top_summaries,
            additional_context={
                "total_summaries": len(summaries),
                "selected_summaries": len(top_summaries),
                "top_k_ratio": self.top_k_ratio,
                "min_relevance_score": top_summaries[-1].relevance_score if top_summaries else 0.0,
                "max_relevance_score": top_summaries[0].relevance_score if top_summaries else 0.0,
            }
        )
        
        return context
    
    def _rank_by_relevance(
        self,
        summaries: List[Summary],
        summary_embeddings: List[List[float]],
        query_embedding: List[float]
    ) -> List[Summary]:
        """
        Rank summaries by cosine similarity to query.
        
        Args:
            summaries: List of summaries
            summary_embeddings: Embedding vectors for summaries
            query_embedding: Embedding vector for query
            
        Returns:
            Sorted list of summaries (highest relevance first)
        """
        # Convert to numpy for efficient computation
        query_vec = np.array(query_embedding, dtype=np.float32)
        
        # Calculate cosine similarity for each summary
        scored_summaries = []
        for summary, embedding in zip(summaries, summary_embeddings):
            summary_vec = np.array(embedding, dtype=np.float32)
            
            # Cosine similarity
            similarity = self._cosine_similarity(query_vec, summary_vec)
            
            # Update summary with relevance score
            summary.relevance_score = float(similarity)
            scored_summaries.append(summary)
        
        # Sort by relevance (descending)
        ranked = sorted(scored_summaries, key=lambda s: s.relevance_score, reverse=True)
        
        # Log top scores
        if ranked:
            logger.info(f"Relevance scores: min={ranked[-1].relevance_score:.3f}, max={ranked[0].relevance_score:.3f}")
            logger.debug(f"Top 5 scores: {[f'{s.relevance_score:.3f}' for s in ranked[:5]]}")
        
        return ranked
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        
        # Clamp to [0, 1] range
        return max(0.0, min(1.0, similarity))
