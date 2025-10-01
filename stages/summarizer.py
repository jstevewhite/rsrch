"""Summarization stage - generates summaries with citations from scraped content."""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

from ..models import ScrapedContent, Summary, Citation, ResearchPlan
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class ChunkSummary:
    """Summary of a single content chunk."""
    text: str
    chunk_id: int
    url: str
    title: str


class Summarizer:
    """
    Generates summaries from scraped content using map-reduce approach.
    
    Strategy:
    1. Chunk long content into manageable pieces
    2. Summarize each chunk individually (MAP phase)
    3. Combine chunk summaries into final summary (REDUCE phase)
    4. Extract citations during summarization
    """
    
    # Token limits for chunking (approximate)
    MAX_CHUNK_TOKENS = 30000  # Conservative limit for context window (must fit prompt + chunk)
    CHARS_PER_TOKEN = 4       # Rough approximation: 1 token ≈ 4 chars
    MAX_CHUNK_CHARS = MAX_CHUNK_TOKENS * CHARS_PER_TOKEN  # ~120,000 chars per chunk
    
    # Direct summarization threshold (no chunking needed)
    DIRECT_SUMMARIZATION_CHARS = 50000  # ~12,500 tokens
    
    def __init__(self, llm_client: LLMClient, model: str = "gpt-4o-mini"):
        """
        Initialize the summarizer.
        
        Args:
            llm_client: LLM client for generating summaries
            model: Model to use for summarization
        """
        self.llm_client = llm_client
        self.model = model
        logger.info(f"Summarizer initialized with model: {model}")
    
    def summarize_all(
        self, 
        scraped_contents: List[ScrapedContent],
        plan: ResearchPlan,
        max_summaries: Optional[int] = None
    ) -> List[Summary]:
        """
        Generate summaries for all scraped content.
        
        Args:
            scraped_contents: List of scraped content to summarize
            plan: Research plan to guide summarization
            max_summaries: Optional limit on number of summaries
            
        Returns:
            List of Summary objects with citations
        """
        logger.info(f"Starting summarization of {len(scraped_contents)} documents")
        
        # Deduplicate by URL (keep first occurrence)
        seen_urls = set()
        deduplicated = []
        for content in scraped_contents:
            if content.url not in seen_urls:
                seen_urls.add(content.url)
                deduplicated.append(content)
            else:
                logger.debug(f"Skipping duplicate URL for summarization: {content.url}")
        
        if len(deduplicated) < len(scraped_contents):
            logger.info(f"Deduplicated scraped content: {len(scraped_contents)} → {len(deduplicated)} unique URLs")
        
        scraped_contents = deduplicated
        
        summaries = []
        for i, content in enumerate(scraped_contents[:max_summaries] if max_summaries else scraped_contents):
            try:
                logger.info(f"Summarizing {i+1}/{len(scraped_contents)}: {content.title[:60]}...")
                summary = self.summarize_content(content, plan)
                
                if summary:
                    summaries.append(summary)
                    logger.info(f"✓ Summary generated for: {content.url}")
                else:
                    logger.warning(f"✗ No summary generated for: {content.url}")
                    
            except Exception as e:
                logger.error(f"Error summarizing {content.url}: {e}")
                continue
        
        logger.info(f"Summarization complete: {len(summaries)}/{len(scraped_contents)} successful")
        return summaries
    
    def summarize_content(
        self, 
        content: ScrapedContent, 
        plan: ResearchPlan
    ) -> Optional[Summary]:
        """
        Summarize a single piece of scraped content.
        
        Uses map-reduce for long content:
        1. Chunk the content if too long
        2. Summarize each chunk
        3. Combine chunk summaries into final summary
        
        Args:
            content: ScrapedContent to summarize
            plan: Research plan for context
            
        Returns:
            Summary object with citations or None if failed
        """
        content_length = len(content.content)
        
        # Decide on strategy based on content length
        if content_length <= self.DIRECT_SUMMARIZATION_CHARS:
            # Short content: Direct summarization
            logger.debug(f"Using direct summarization for {content.url} ({content_length} chars)")
            return self._summarize_direct(content, plan)
        else:
            # Long content: Map-reduce approach
            logger.info(f"Using map-reduce for {content.url} ({content_length:,} chars → chunking needed)")
            return self._summarize_map_reduce(content, plan)
    
    def _summarize_direct(
        self, 
        content: ScrapedContent, 
        plan: ResearchPlan
    ) -> Optional[Summary]:
        """
        Directly summarize content that fits in context window.
        
        Args:
            content: ScrapedContent to summarize
            plan: Research plan for context
            
        Returns:
            Summary object with citations
        """
        prompt = self._build_summary_prompt(
            text=content.content,
            url=content.url,
            title=content.title,
            query=plan.query.text,
            sections=plan.sections
        )
        
        try:
            summary_text = self.llm_client.complete(
                prompt=prompt,
                model=self.model,
                temperature=0.3,  # Lower temp for factual summarization
                max_tokens=1000,
            )
            
            # Extract citations from content
            citations = self._extract_citations(
                summary_text=summary_text,
                url=content.url,
                title=content.title
            )
            
            return Summary(
                text=summary_text,
                citations=citations,
                url=content.url,
                relevance_score=1.0  # Will be updated by re-ranking later
            )
            
        except Exception as e:
            logger.error(f"Direct summarization failed for {content.url}: {e}")
            return None
    
    def _summarize_map_reduce(
        self, 
        content: ScrapedContent, 
        plan: ResearchPlan
    ) -> Optional[Summary]:
        """
        Summarize long content using map-reduce approach.
        
        MAP: Chunk content and summarize each chunk
        REDUCE: Combine chunk summaries into final summary
        
        Args:
            content: ScrapedContent to summarize
            plan: Research plan for context
            
        Returns:
            Summary object with citations
        """
        # Step 1: Chunk the content
        chunks = self._chunk_content(content.content)
        logger.debug(f"Split content into {len(chunks)} chunks")
        
        # Step 2: MAP - Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            try:
                chunk_summary = self._summarize_chunk(
                    chunk=chunk,
                    chunk_id=i,
                    url=content.url,
                    title=content.title,
                    query=plan.query.text
                )
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)
            except Exception as e:
                logger.warning(f"Failed to summarize chunk {i}: {e}")
                continue
        
        if not chunk_summaries:
            logger.error(f"No chunk summaries generated for {content.url}")
            return None
        
        # Step 3: REDUCE - Combine chunk summaries
        try:
            final_summary = self._combine_chunk_summaries(
                chunk_summaries=chunk_summaries,
                url=content.url,
                title=content.title,
                query=plan.query.text,
                sections=plan.sections
            )
            return final_summary
            
        except Exception as e:
            logger.error(f"Failed to combine chunk summaries for {content.url}: {e}")
            return None
    
    def _chunk_content(self, content: str) -> List[str]:
        """
        Split content into chunks that fit in context window.
        
        Strategy: Split on paragraph boundaries to maintain coherence.
        Each chunk MUST be <= MAX_CHUNK_CHARS to avoid context overflow.
        
        Args:
            content: Full text content
            
        Returns:
            List of content chunks (each <= MAX_CHUNK_CHARS)
        """
        chunks = []
        current_chunk = []
        current_size = 0
        
        logger.debug(f"Chunking content: {len(content):,} chars (max per chunk: {self.MAX_CHUNK_CHARS:,})")
        
        # Split into paragraphs
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            para_size = len(para)
            
            # If single paragraph exceeds max size, split it
            if para_size > self.MAX_CHUNK_CHARS:
                # Save current chunk if exists
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph by sentences
                sentences = para.split('. ')
                temp_chunk = []
                temp_size = 0
                
                for sentence in sentences:
                    if temp_size + len(sentence) > self.MAX_CHUNK_CHARS and temp_chunk:
                        chunks.append('. '.join(temp_chunk) + '.')
                        temp_chunk = [sentence]
                        temp_size = len(sentence)
                    else:
                        temp_chunk.append(sentence)
                        temp_size += len(sentence)
                
                if temp_chunk:
                    chunks.append('. '.join(temp_chunk))
                    
            # If adding paragraph would exceed limit, start new chunk
            elif current_size + para_size > self.MAX_CHUNK_CHARS and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # Add final chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # Validate all chunks are within limit
        for i, chunk in enumerate(chunks):
            chunk_len = len(chunk)
            if chunk_len > self.MAX_CHUNK_CHARS:
                logger.error(f"Chunk {i} exceeds limit: {chunk_len:,} > {self.MAX_CHUNK_CHARS:,} chars")
                # Emergency truncation to prevent API errors
                chunks[i] = chunk[:self.MAX_CHUNK_CHARS]
                logger.warning(f"Truncated chunk {i} to {self.MAX_CHUNK_CHARS:,} chars")
        
        logger.info(f"Created {len(chunks)} chunks (sizes: {[f'{len(c):,}' for c in chunks[:5]]}{'...' if len(chunks) > 5 else ''})")
        return chunks
    
    def _summarize_chunk(
        self,
        chunk: str,
        chunk_id: int,
        url: str,
        title: str,
        query: str
    ) -> Optional[ChunkSummary]:
        """
        Summarize a single chunk of content.
        
        Args:
            chunk: Content chunk to summarize
            chunk_id: Chunk identifier
            url: Source URL
            title: Source title
            query: Original research query
            
        Returns:
            ChunkSummary object
        """
        # Safety check: Ensure chunk is not too large
        chunk_len = len(chunk)
        if chunk_len > self.MAX_CHUNK_CHARS:
            logger.error(f"Chunk {chunk_id} too large: {chunk_len:,} chars (max: {self.MAX_CHUNK_CHARS:,})")
            logger.warning(f"Truncating chunk {chunk_id} to prevent API error")
            chunk = chunk[:self.MAX_CHUNK_CHARS]
        
        logger.debug(f"Summarizing chunk {chunk_id}: {chunk_len:,} chars (~{chunk_len // self.CHARS_PER_TOKEN:,} tokens)")
        
        prompt = f"""Summarize the following content chunk in relation to the research query.

Research Query: "{query}"

Source: {title}
URL: {url}
Chunk {chunk_id + 1}

Content:
{chunk}

Provide a concise summary focusing on information relevant to the research query.
Extract key facts, findings, and insights. Aim for 2-3 paragraphs."""

        try:
            summary_text = self.llm_client.complete(
                prompt=prompt,
                model=self.model,
                temperature=0.3,
                max_tokens=500,
            )
            
            return ChunkSummary(
                text=summary_text,
                chunk_id=chunk_id,
                url=url,
                title=title
            )
            
        except Exception as e:
            logger.error(f"Chunk summarization failed: {e}")
            return None
    
    def _combine_chunk_summaries(
        self,
        chunk_summaries: List[ChunkSummary],
        url: str,
        title: str,
        query: str,
        sections: List[str]
    ) -> Summary:
        """
        Combine multiple chunk summaries into final summary (REDUCE phase).
        
        Args:
            chunk_summaries: List of chunk summaries
            url: Source URL
            title: Source title
            query: Research query
            sections: Report sections from plan
            
        Returns:
            Final Summary object
        """
        # Combine all chunk summaries
        combined_text = '\n\n'.join([cs.text for cs in chunk_summaries])
        
        prompt = f"""Synthesize the following summaries into a coherent final summary.

Research Query: "{query}"
Source: {title}
URL: {url}

Report Sections:
{chr(10).join(f"- {section}" for section in sections)}

Chunk Summaries:
{combined_text}

Create a comprehensive summary that:
1. Eliminates redundancy across chunks
2. Organizes information logically
3. Highlights key findings relevant to the research query
4. Maintains factual accuracy

Aim for 3-5 paragraphs."""

        try:
            final_text = self.llm_client.complete(
                prompt=prompt,
                model=self.model,
                temperature=0.3,
                max_tokens=1000,
            )
            
            # Extract citations
            citations = self._extract_citations(
                summary_text=final_text,
                url=url,
                title=title
            )
            
            return Summary(
                text=final_text,
                citations=citations,
                url=url,
                relevance_score=1.0
            )
            
        except Exception as e:
            logger.error(f"Failed to combine summaries: {e}")
            raise
    
    def _build_summary_prompt(
        self,
        text: str,
        url: str,
        title: str,
        query: str,
        sections: List[str]
    ) -> str:
        """
        Build prompt for direct summarization.
        
        Args:
            text: Content to summarize
            url: Source URL
            title: Source title
            query: Research query
            sections: Report sections
            
        Returns:
            Formatted prompt string
        """
        return f"""Summarize the following content in relation to the research query.

Research Query: "{query}"

Source: {title}
URL: {url}

Report Sections (for context):
{chr(10).join(f"- {section}" for section in sections)}

Content:
{text}

Provide a comprehensive summary that:
1. Extracts key information relevant to the research query
2. Identifies main findings, arguments, or insights
3. Maintains factual accuracy
4. Organizes information clearly

Aim for 3-5 paragraphs. Focus on substance over style."""
    
    def _extract_citations(
        self,
        summary_text: str,
        url: str,
        title: str
    ) -> List[Citation]:
        """
        Extract citations from summary text.
        
        For now, creates a single citation for the entire summary.
        Future enhancement: Extract specific quotes and line them to chunks.
        
        Args:
            summary_text: Summary text
            url: Source URL
            title: Source title
            
        Returns:
            List of Citation objects
        """
        # For now, create single citation for the whole summary
        # TODO: Implement more granular citation extraction
        citation = Citation(
            text=summary_text[:200] + "..." if len(summary_text) > 200 else summary_text,
            url=url,
            title=title,
            chunk_id=None
        )
        
        return [citation]
