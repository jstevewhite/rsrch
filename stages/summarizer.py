"""Summarization stage - generates summaries with citations from scraped content."""

import logging
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import ScrapedContent, Summary, Citation, ResearchPlan
from ..llm_client import LLMClient
from .content_detector import ContentPatterns, ContentType

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
    
    # Table-aware preprocessing settings
    ENABLE_TABLE_AWARE = True
    TABLE_MAX_ROWS_VERBATIM = 15
    TABLE_MAX_COLS_VERBATIM = 8
    TABLE_TOPK_ROWS = 10
    
    def __init__(
        self, 
        llm_client: LLMClient, 
        default_model: str = "gpt-4o-mini",
        model_selector: Optional[Callable[[str], str]] = None,
        max_workers: int = 1,
        *,
        enable_table_aware: Optional[bool] = None,
        table_topk_rows: Optional[int] = None,
        table_max_rows_verbatim: Optional[int] = None,
        table_max_cols_verbatim: Optional[int] = None,
    ):
        """
        Initialize the summarizer.
        
        Args:
            llm_client: LLM client for generating summaries
            default_model: Default model to use for summarization
            model_selector: Optional function that takes content type and returns model name
            max_workers: Number of parallel workers for summarization
        """
        self.llm_client = llm_client
        self.default_model = default_model
        self.model_selector = model_selector
        self.max_workers = max(1, int(max_workers))
        # Instance-level table settings (override class defaults if provided)
        self.enable_table_aware = self.ENABLE_TABLE_AWARE if enable_table_aware is None else bool(enable_table_aware)
        self.table_topk_rows = self.TABLE_TOPK_ROWS if table_topk_rows is None else int(table_topk_rows)
        self.table_max_rows_verbatim = self.TABLE_MAX_ROWS_VERBATIM if table_max_rows_verbatim is None else int(table_max_rows_verbatim)
        self.table_max_cols_verbatim = self.TABLE_MAX_COLS_VERBATIM if table_max_cols_verbatim is None else int(table_max_cols_verbatim)
        logger.info(
            f"Summarizer initialized with default model: {default_model}, max_workers: {self.max_workers} "
            f"(tables: aware={self.enable_table_aware}, topk={self.table_topk_rows}, small<={self.table_max_rows_verbatim}x{self.table_max_cols_verbatim})"
        )
    
    def _select_model(self, url: str) -> str:
        """Select the appropriate model based on URL content type.
        
        Args:
            url: URL to analyze for content type
            
        Returns:
            Model name to use for summarization
        """
        # If no model selector is provided, use default
        if not self.model_selector:
            return self.default_model
        
        # Detect content type from URL
        content_type = ContentPatterns.detect_from_url(url)
        
        # Get model for content type
        model = self.model_selector(content_type.value)
        
        logger.debug(f"Selected model '{model}' for content type '{content_type.value}' (URL: {url})")
        return model
    
    def _get_source_grounding_context(self) -> str:
        """Generate instructions to prioritize source content over training data.
        
        Returns:
            Formatted source-grounding instructions
        """
        current_date = datetime.now(timezone.utc)
        date_str = current_date.strftime("%B %d, %Y")
        
        return f"""CRITICAL INSTRUCTIONS - SOURCE PRIORITIZATION:

Current Date: {date_str}

YOU MUST FOLLOW THESE RULES ABSOLUTELY:

1. **TRUST THE SOURCE MATERIAL COMPLETELY**
   - The content provided below is MORE RECENT and MORE ACCURATE than your training data
   - If the source contradicts what you "know", the SOURCE IS CORRECT
   - Your training data may be outdated - defer to the provided content

2. **NEVER CORRECT OR "FIX" THE SOURCE**
   - Do not change names, titles, positions, dates, or facts from the source
   - If the source says someone is President, accept it - do not "correct" based on your knowledge
   - If the source describes current events, treat them as current regardless of your training cutoff

3. **SUMMARIZE WHAT IS WRITTEN, NOT WHAT YOU THINK**
   - Report exactly what the source says
   - Do not add context like "former" or "current" unless it appears in the source
   - Do not add qualifiers like "as of [date]" or "at the time" unless they're in the source

4. **WHEN IN DOUBT, QUOTE THE SOURCE**
   - If something seems unusual, that's because the world has changed since your training
   - Preserve the source's language and framing
   - Your job is to SUMMARIZE, not to FACT-CHECK

REMEMBER: The source material reflects REALITY. Your training data reflects THE PAST."""
    
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
        
        contents_to_summarize = scraped_contents[:max_summaries] if max_summaries else scraped_contents
        
        # Choose execution strategy based on config
        if self.max_workers > 1 and len(contents_to_summarize) > 1:
            logger.info(f"Using parallel summarization with {self.max_workers} workers")
            summaries = self._summarize_parallel(contents_to_summarize, plan)
        else:
            logger.info("Using sequential summarization")
            summaries = self._summarize_sequential(contents_to_summarize, plan)
        
        logger.info(f"Summarization complete: {len(summaries)}/{len(contents_to_summarize)} successful")
        return summaries
    
    def _summarize_parallel(self, contents: List[ScrapedContent], plan: ResearchPlan) -> List[Summary]:
        """Summarize multiple documents in parallel using ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results: List[Summary] = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            try:
                future_to_content = {
                    executor.submit(self._summarize_content_safe, content, plan): content
                    for content in contents
                }
                for future in as_completed(future_to_content):
                    content = future_to_content[future]
                    try:
                        summary = future.result()
                        if summary:
                            results.append(summary)
                            logger.info(f"✓ Summary generated for: {content.url}")
                        else:
                            logger.warning(f"✗ No summary generated for: {content.url}")
                    except Exception as e:
                        logger.error(f"✗ Summarization failed for {content.url}: {e}")
            finally:
                executor.shutdown(wait=True)
        return results

    def _summarize_sequential(self, contents: List[ScrapedContent], plan: ResearchPlan) -> List[Summary]:
        """Summarize documents sequentially (existing behavior)."""
        summaries: List[Summary] = []
        for i, content in enumerate(contents):
            try:
                logger.info(f"Summarizing {i+1}/{len(contents)}: {content.title[:60]}...")
                summary = self.summarize_content(content, plan)
                if summary:
                    summaries.append(summary)
                    logger.info(f"✓ Summary generated for: {content.url}")
                else:
                    logger.warning(f"✗ No summary generated for: {content.url}")
            except Exception as e:
                logger.error(f"Error summarizing {content.url}: {e}")
                continue
        return summaries

    def _summarize_content_safe(self, content: ScrapedContent, plan: ResearchPlan) -> Optional[Summary]:
        """Safely summarize a single document (returns None on failure)."""
        try:
            return self.summarize_content(content, plan)
        except Exception as e:
            logger.error(f"Safe summarization failed for {content.url}: {e}")
            return None
    
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
        # Preprocess content to preserve/compact tables
        text_pre = self._preprocess_for_tables(content.content, plan.query.text) if self.enable_table_aware else content.content
        prompt = self._build_summary_prompt(
            text=text_pre,
            url=content.url,
            title=content.title,
            query=plan.query.text,
            sections=plan.sections
        )
        
        # Select appropriate model based on content type
        model = self._select_model(content.url)
        
        try:
            summary_text = self.llm_client.complete(
                prompt=prompt,
                model=model,
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
    
    # ===== Table-aware preprocessing helpers =====
    def _preprocess_for_tables(self, text: str, query: str) -> str:
        """Detect Markdown tables in text and preserve or compress them.
        Small tables are kept verbatim; large tables are compacted deterministically.
        """
        try:
            tables = self._find_markdown_tables(text)
            if not tables:
                return text
            # Build new text by replacing from the end to keep indices stable
            new_text = text
            offset = 0
            for tbl in tables:
                start, end = tbl['start'], tbl['end']
                md_table = text[start:end]
                info = self._analyze_table(md_table)
                if info['rows'] <= self.table_max_rows_verbatim and info['cols'] <= self.table_max_cols_verbatim:
                    replacement = md_table  # keep verbatim
                else:
                    # Choose salient rows
                    top_indices, criterion = self._select_salient_rows(info, self.table_topk_rows, query)
                    # Compute aggregates
                    aggs = self._compute_column_aggregates(info)
                    replacement = self._compress_markdown_table(info, top_indices, criterion, aggs)
                # Apply replacement considering prior offset
                adj_start = start + offset
                adj_end = end + offset
                new_text = new_text[:adj_start] + replacement + new_text[adj_end:]
                offset += len(replacement) - (end - start)
            return new_text
        except Exception as e:
            logger.debug(f"Table preprocessing failed, returning original text: {e}")
            return text
    
    def _find_markdown_tables(self, text: str) -> List[Dict]:
        """Locate pipe-style Markdown tables and return their spans.
        Strategy: line-scan for header line with pipes followed by a separator line of --- cells.
        """
        lines = text.split('\n')
        indices = []
        i = 0
        pos = 0  # char offset tracker
        while i < len(lines) - 1:
            line = lines[i]
            next_line = lines[i+1]
            # Quick checks: must contain at least two pipes and a separator line next
            if line.count('|') >= 2 and self._is_md_table_sep(next_line):
                # collect table block lines until empty line or non-table-looking line
                start_char = pos
                j = i + 2
                while j < len(lines) and lines[j].count('|') >= 2 and lines[j].strip():
                    j += 1
                end_char = pos + sum(len(l)+1 for l in lines[i:j])  # include newlines
                # Ensure header row has at least one cell
                if '|' in line:
                    indices.append({'start': start_char, 'end': end_char, 'line_start': i, 'line_end': j})
                i = j
                pos = end_char
                continue
            # advance
            pos += len(line) + 1
            i += 1
        return indices
    
    @staticmethod
    def _is_md_table_sep(line: str) -> bool:
        # A separator line looks like: | --- | :---: | ---: |
        segs = [seg.strip() for seg in line.strip().strip('|').split('|')]
        if len(segs) < 1:
            return False
        for seg in segs:
            if not seg:
                return False
            # Allow :, -, and spaces only; must include at least three hyphens
            if not all(c in ':- ' for c in seg):
                return False
            if seg.count('-') < 3:
                return False
        return True
    
    def _analyze_table(self, md_table: str) -> Dict:
        """Parse a Markdown pipe table into headers/rows and compute basic typing and numeric values."""
        lines = [ln for ln in md_table.strip().split('\n') if ln.strip()]
        if len(lines) < 2:
            return {'headers': [], 'rows': 0, 'cols': 0, 'cells': [], 'numeric_cols': []}
        header_cells = [c.strip() for c in lines[0].strip().strip('|').split('|')]
        body_lines = lines[2:] if self._is_md_table_sep(lines[1]) else lines[1:]
        rows = []
        num_pattern = re.compile(r"^-?\d+(?:[\.,]\d+)?%?$")
        for bl in body_lines:
            cells = [c.strip() for c in bl.strip().strip('|').split('|')]
            # normalize width
            if len(cells) < len(header_cells):
                cells.extend([''] * (len(header_cells) - len(cells)))
            elif len(cells) > len(header_cells):
                cells = cells[:len(header_cells)]
            rows.append(cells)
        cols = len(header_cells)
        # Determine numeric columns
        numeric_cols = []
        for ci in range(cols):
            col_vals = [rows[ri][ci] for ri in range(len(rows)) if ri < len(rows)]
            # normalize comma decimal
            parsed = []
            for v in col_vals:
                vv = v.replace(',', '')
                if num_pattern.match(vv):
                    try:
                        val = float(vv.rstrip('%'))
                        if v.endswith('%'):
                            val = val  # keep raw percent value
                        parsed.append(val)
                    except Exception:
                        pass
            density = (len(parsed) / max(1, len(col_vals)))
            numeric_cols.append(density >= 0.6)
        return {
            'headers': header_cells,
            'cells': rows,
            'rows': len(rows),
            'cols': cols,
            'numeric_cols': numeric_cols,
        }
    
    def _select_salient_rows(self, info: Dict, k: int, query: str) -> (List[int], str):
        """Select up to k salient rows. Prefer a target metric column based on header keywords; else use sum across numeric cols."""
        headers = [h.lower() for h in info['headers']]
        numeric_cols = info['numeric_cols']
        target_keywords = ['accuracy', 'f1', 'f1-score', 'auc', 'roc', 'revenue', 'cost', 'price', 'score', 'latency']
        target_col = None
        for idx, h in enumerate(headers):
            if numeric_cols[idx] and any(kw in h for kw in target_keywords):
                target_col = idx
                break
        # If query mentions a header
        if target_col is None and query:
            for idx, h in enumerate(headers):
                if numeric_cols[idx] and h in query.lower():
                    target_col = idx
                    break
        rows = info['cells']
        # Parse numeric values for selection
        def parse_float(s: str) -> float:
            s2 = s.replace(',', '')
            s2 = s2.rstrip('%')
            try:
                return float(s2)
            except Exception:
                return float('-inf')
        if target_col is not None:
            scored = [(ri, parse_float(rows[ri][target_col])) for ri in range(len(rows))]
            scored.sort(key=lambda x: x[1], reverse=True)
            top = [ri for ri, _ in scored if _ != float('-inf')][:k]
            criterion = f"max by {info['headers'][target_col]}"
            if not top:
                # fallback
                target_col = None
        if target_col is None:
            # Sum across numeric columns
            num_indices = [i for i, is_num in enumerate(numeric_cols) if is_num]
            scored = []
            for ri in range(len(rows)):
                total = 0.0
                for ci in num_indices:
                    val = parse_float(rows[ri][ci])
                    total += 0 if val == float('-inf') else val
                scored.append((ri, total))
            scored.sort(key=lambda x: x[1], reverse=True)
            top = [ri for ri, _ in scored][:k]
            criterion = "top by combined numeric values"
        return top, criterion
    
    def _compute_column_aggregates(self, info: Dict) -> Dict:
        """Compute min/max/mean for numeric columns and top categories for non-numeric."""
        from collections import Counter
        rows = info['cells']
        cols = info['cols']
        aggs = {}
        for ci in range(cols):
            col_name = info['headers'][ci]
            if info['numeric_cols'][ci]:
                vals = []
                for r in rows:
                    try:
                        v = float(r[ci].replace(',', '').rstrip('%'))
                        vals.append(v)
                    except Exception:
                        pass
                if vals:
                    aggs[col_name] = {
                        'min': min(vals),
                        'mean': (sum(vals)/len(vals)) if vals else None,
                        'max': max(vals),
                    }
            else:
                from collections import Counter
                ctr = Counter([r[ci] for r in rows if r[ci]])
                aggs[col_name] = {
                    'top': ctr.most_common(3)
                }
        return aggs
    
    def _compress_markdown_table(self, info: Dict, top_indices: List[int], criterion: str, aggs: Dict) -> str:
        """Emit a compact Markdown table with header + selected rows and a notes line about selection and aggregates."""
        headers = info['headers']
        body = info['cells']
        # Build table
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        sel_rows = [body[i] for i in top_indices]
        body_lines = ["| " + " | ".join(r) + " |" for r in sel_rows]
        # Build aggregates summary (numeric only)
        agg_parts = []
        for col, a in aggs.items():
            if 'min' in a:
                def fmt(x):
                    try:
                        return f"{x:.4g}"
                    except Exception:
                        return str(x)
                agg_parts.append(f"{col} mean={fmt(a['mean'])}, max={fmt(a['max'])}")
        agg_str = ", ".join(agg_parts) if agg_parts else "none"
        notes = f"\n\n> Note: Showing {len(sel_rows)} of {info['rows']} rows; selection={criterion}; aggregates: {agg_str}.\n\n"
        return "\n\n" + "\n".join([header_line, sep_line] + body_lines) + notes
    
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
        
        source_grounding = self._get_source_grounding_context()
        
        # Preprocess chunk for tables
        processed_chunk = self._preprocess_for_tables(chunk, query) if self.enable_table_aware else chunk
        
        prompt = f"""{source_grounding}

---

Summarize the following content chunk in relation to the research query.

Research Query: "{query}"

Source: {title}
URL: {url}
Chunk {chunk_id + 1}

Content:
{processed_chunk}

Table handling:
- Preserve any Markdown tables verbatim as they appear.
- If a compacted table is present, use it as-is; do not recompute totals or statistics.
- Do not reformat tables.

Provide a concise summary focusing on information relevant to the research query.
Extract key facts, findings, and insights. Maintain temporal accuracy. Aim for 2-3 paragraphs."""

        # Select appropriate model based on content type
        model = self._select_model(url)
        
        try:
            summary_text = self.llm_client.complete(
                prompt=prompt,
                model=model,
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
        
        source_grounding = self._get_source_grounding_context()
        
        prompt = f"""{source_grounding}

---

Synthesize the following summaries into a coherent final summary.

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
4. Maintains factual accuracy and temporal correctness

Table handling:
- Preserve any Markdown tables verbatim as they appear.
- If a compacted table is present, use it as-is; do not recompute totals or statistics.
- Do not reformat tables.

Aim for 3-5 paragraphs."""

        # Select appropriate model based on content type
        model = self._select_model(url)
        
        try:
            final_text = self.llm_client.complete(
                prompt=prompt,
                model=model,
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
        source_grounding = self._get_source_grounding_context()
        
        return f"""{source_grounding}

---

Summarize the following content in relation to the research query.

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
3. Maintains factual accuracy and temporal correctness
4. Organizes information clearly

Table handling:
- Preserve any Markdown tables verbatim as they appear.
- If a compacted table is present, use it as-is; do not recompute totals or statistics.
- Do not reformat tables.

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
