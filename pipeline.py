"""Research pipeline orchestrator."""

import logging
from typing import Optional
from pathlib import Path

from .config import Config
from .models import Query, Report
from .llm_client import LLMClient
from .stages import (
    IntentClassifier,
    Planner,
    Researcher,
    Scraper,
    Summarizer,
    ContextAssembler,
    EmbeddingClient,
    VectorStore,
    RerankerClient,
    SearchResultReranker,
)

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """Main research pipeline orchestrator."""
    
    def __init__(self, config: Config):
        """Initialize the research pipeline."""
        self.config = config
        self.config.ensure_directories()
        
        # Initialize LLM client
        self.llm_client = LLMClient(
            api_key=config.api_key,
            api_endpoint=config.api_endpoint,
            default_model=config.default_model,
        )
        
        # Initialize stages
        self.intent_classifier = IntentClassifier(
            llm_client=self.llm_client,
            model=config.intent_model,
        )
        
        self.planner = Planner(
            llm_client=self.llm_client,
            model=config.planner_model,
        )
        
        # Initialize researcher (web search)
        self.researcher = Researcher()
        
        # Initialize scraper (content extraction)
        self.scraper = Scraper()
        
        # Initialize summarizer
        self.summarizer = Summarizer(
            llm_client=self.llm_client,
            model=config.mrs_model,  # Map-Reduce Summarization model
        )
        
        # Initialize context assembler
        embedding_client = EmbeddingClient(
            api_url=config.embedding_url,
            api_key=config.embedding_api_key,
            model=config.embedding_model,
        )
        vector_store = VectorStore(db_path=config.vector_db_path)
        self.context_assembler = ContextAssembler(
            embedding_client=embedding_client,
            vector_store=vector_store,
            top_k_ratio=config.rerank_top_k_sum,  # Use summary-level ratio
        )
        
        # Initialize search result reranker
        if config.use_reranker and config.reranker_url and config.reranker_model:
            reranker_client = RerankerClient(
                api_url=config.reranker_url,
                api_key=config.reranker_api_key,
                model=config.reranker_model,
            )
            self.search_reranker = SearchResultReranker(
                reranker_client=reranker_client,
                top_k_ratio=config.rerank_top_k_url,  # Use URL-level ratio
            )
        else:
            self.search_reranker = None
            logger.info("Search result reranking disabled")
        
        logger.info("Research pipeline initialized")
    
    def run(self, query_text: str) -> Report:
        """Run the complete research pipeline."""
        logger.info(f"Starting research pipeline for query: {query_text[:100]}...")
        
        # Stage 1: Parse query
        query = Query(text=query_text)
        logger.info("Stage 1: Query parsed")
        
        # Stage 2: Identify intent
        logger.info("Stage 2: Identifying intent...")
        intent = self.intent_classifier.classify(query)
        logger.info(f"Intent identified: {intent.value}")
        
        # Stage 3: Plan research
        logger.info("Stage 3: Planning research...")
        plan = self.planner.plan(query)
        logger.info(f"Research plan created with {len(plan.search_queries)} queries")
        
        # Stage 4: Research (web search)
        logger.info("Stage 4: Conducting research...")
        try:
            search_results = self.researcher.search(plan)
            logger.info(f"Found {len(search_results)} search results")
        except Exception as e:
            logger.error(f"Research stage failed: {e}")
            search_results = []
        
        # Stage 4.5: Rerank search results (before scraping)
        if self.search_reranker and search_results:
            logger.info("Stage 4.5: Reranking search results...")
            try:
                original_count = len(search_results)
                search_results = self.search_reranker.rerank_search_results(
                    query=plan.query.text,
                    search_results=search_results
                )
                logger.info(f"Filtered from {original_count} to {len(search_results)} search results")
            except Exception as e:
                logger.error(f"Search reranking failed: {e}")
                logger.warning("Continuing with all search results")
        
        # Stage 5: Scrape content
        logger.info("Stage 5: Scraping content...")
        try:
            scraped_content = self.scraper.scrape_results(search_results)
            logger.info(f"Scraped {len(scraped_content)} URLs")
            
            # Log scraper statistics
            stats = self.scraper.get_fallback_usage_stats()
            if stats['fallback_used'] > 0:
                logger.info(f"Fallback scraping used: {stats['fallback_used']} times (cost: ${stats['estimated_cost']:.2f})")
        except Exception as e:
            logger.error(f"Scraping stage failed: {e}")
            scraped_content = []
        
        # Stage 6: Generate summaries
        logger.info("Stage 6: Generating summaries...")
        try:
            summaries = self.summarizer.summarize_all(
                scraped_contents=scraped_content,
                plan=plan,
                max_summaries=None  # Summarize all content
            )
            logger.info(f"Generated {len(summaries)} summaries")
        except Exception as e:
            logger.error(f"Summarization stage failed: {e}")
            summaries = []
        
        # Stage 7: Assemble context
        logger.info("Stage 7: Assembling context...")
        try:
            context = self.context_assembler.assemble_context(
                summaries=summaries,
                plan=plan
            )
            logger.info(f"Context assembled: {context.additional_context['selected_summaries']}/{context.additional_context['total_summaries']} summaries selected")
            logger.info(f"Relevance range: {context.additional_context['min_relevance_score']:.3f} - {context.additional_context['max_relevance_score']:.3f}")
            
            # Use filtered summaries from context
            summaries = context.summaries
        except Exception as e:
            logger.error(f"Context assembly stage failed: {e}")
            # Continue with all summaries if context assembly fails
            logger.warning("Using all summaries without re-ranking")
        
        # Stage 8: Reflection (stub - needs implementation)
        logger.info("Stage 8: Reflecting on completeness...")
        logger.warning("Reflection stage not yet implemented - using placeholder")
        
        # Stage 9: Generate report
        logger.info("Stage 9: Generating report...")
        report = self._generate_report(query, plan, summaries)
        
        # Save report
        report_path = self._save_report(report)
        logger.info(f"Report saved to: {report_path}")
        
        return report
    
    def _generate_report(self, query: Query, plan, summaries: list) -> Report:
        """Generate the final report from research summaries."""
        
        # Build context from summaries
        if summaries:
            sources_text = "\n\n".join([
                f"Source {i+1}: {summary.url}\nTitle: {summary.citations[0].title if summary.citations else 'N/A'}\n{summary.text}"
                for i, summary in enumerate(summaries)
            ])
            
            prompt = f"""Generate a comprehensive research report based on the following research.

Query: "{query.text}"
Intent: {query.intent.value if query.intent else "general"}

Report Sections to Cover:
{chr(10).join(f"- {section}" for section in plan.sections)}

Research Summaries:
{sources_text}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. You are writing a FACTUAL RESEARCH REPORT, not a creative story
2. DO NOT invent contradictions, controversies, or disputes that are not explicitly present in the sources
3. DO NOT claim sources "contradict" each other unless they make directly opposing statements about the same fact
4. If all sources agree on something, report it as established fact - do not manufacture doubt
5. Base EVERY statement on the provided sources - do not speculate, infer, or add dramatic framing
6. If a source clearly states something exists or is true, report it as such - do not hedge with "allegedly" or "claims to be"
7. Use [Source N] citations for EVERY factual claim
8. When official/primary sources (GitHub, official docs) exist, they are authoritative - trust them over blog speculation
9. Only report what sources ACTUALLY say - do not paraphrase in ways that change meaning
10. Your goal is ACCURACY and CLARITY, not drama or "comprehensive analysis of contradictions"

Please provide a well-structured report with:
1. Executive summary
2. Main content organized by the sections listed above
3. Key findings with direct source citations
4. Conclusion based on evidence

Format the report in Markdown.
"""
        else:
            # Fallback if no summaries available
            prompt = f"""Generate a comprehensive research report for the following query:

Query: "{query.text}"
Intent: {query.intent.value if query.intent else "general"}

Report Sections to Cover:
{chr(10).join(f"- {section}" for section in plan.sections)}

Research Approach:
{plan.rationale}

Note: This is a preliminary report. Full research results will be integrated in future iterations.

Please provide a well-structured report with:
1. Executive summary
2. Main content organized by the sections listed above
3. Key findings and insights
4. Conclusion

Format the report in Markdown.
"""
        
        try:
            content = self.llm_client.complete(
                prompt=prompt,
                model=self.config.report_model,
                temperature=0.2,  # Low temperature for factual accuracy
                max_tokens=self.config.report_max_tokens,
            )
            
            # Collect all citations from summaries
            all_citations = []
            for summary in summaries:
                all_citations.extend(summary.citations)
            
            report = Report(
                query=query,
                content=content,
                citations=all_citations,
                metadata={
                    "intent": query.intent.value if query.intent else "unknown",
                    "sections": str(plan.sections),
                    "status": "complete" if summaries else "preliminary",
                    "num_sources": len(summaries),
                },
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise
    
    def _save_report(self, report: Report) -> Path:
        """Save the report to a file."""
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.md"
        filepath = self.config.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Research Report\n\n")
            f.write(f"**Query:** {report.query.text}\n\n")
            f.write(f"**Intent:** {report.query.intent.value if report.query.intent else 'unknown'}\n\n")
            f.write(f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(report.content)
            
            # Add citations section
            if report.citations:
                f.write("\n\n---\n\n")
                f.write("## Sources\n\n")
                for i, citation in enumerate(report.citations, 1):
                    f.write(f"**[Source {i}]** {citation.title}\n")
                    f.write(f"- URL: {citation.url}\n")
                    if citation.chunk_id is not None:
                        f.write(f"- Chunk: {citation.chunk_id}\n")
                    f.write("\n")
            
            # Add metadata
            f.write("\n---\n\n")
            f.write(f"**Metadata:**\n")
            for key, value in report.metadata.items():
                f.write(f"- {key}: {value}\n")
        
        return filepath
