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
    Reflector,
    GapValidator,
    ClaimExtractor,
    ClaimVerifier,
    VerificationReporter,
)
from .stages.content_detector import SourceTier

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
            max_retries=config.llm_max_retries,
            enable_policy=config.prompt_policy_include,
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
        self.researcher = Researcher(config)
        
        # Initialize scraper (content extraction)
        self.scraper = Scraper(
            max_workers=config.scrape_parallel,  # from config
            output_format=config.output_format,
            preserve_tables=config.preserve_tables,
        )
        
        # Initialize summarizer with model selector
        self.summarizer = Summarizer(
            llm_client=self.llm_client,
            default_model=config.mrs_model_default,
            model_selector=config.get_mrs_model_for_content_type,
            max_workers=config.summary_parallel,  # from config
            enable_table_aware=config.summarizer_enable_table_aware,
            table_topk_rows=config.summarizer_table_topk_rows,
            table_max_rows_verbatim=config.summarizer_table_max_rows_verbatim,
            table_max_cols_verbatim=config.summarizer_table_max_cols_verbatim,
        )
        
        # Initialize context assembler
        embedding_client = EmbeddingClient(
            api_url=config.embedding_url,
            api_key=config.embedding_api_key,
            model=config.embedding_model,
        )
        self.vector_store = VectorStore(db_path=config.vector_db_path)
        self.context_assembler = ContextAssembler(
            embedding_client=embedding_client,
            vector_store=self.vector_store,
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
        
        # Initialize reflector
        self.reflector = Reflector(
            llm_client=self.llm_client,
            model=config.reflection_model,
        )

        # Initialize gap validator (post-report gap check)
        if config.validate_gaps:
            self.gap_validator = GapValidator(
                llm_client=self.llm_client,
                model=config.reflection_model,
            )
        else:
            self.gap_validator = None
            logger.info("Post-report gap validation disabled")

        # Initialize verification components (optional)
        if config.verify_claims:
            tier_weights = {
                SourceTier.TIER_1: config.verify_tier_1_weight,
                SourceTier.TIER_2: config.verify_tier_2_weight,
                SourceTier.TIER_3: config.verify_tier_3_weight,
                SourceTier.TIER_4: config.verify_tier_4_weight,
            }
            self.claim_extractor = ClaimExtractor(
                llm_client=self.llm_client,
                model=config.verify_model,
            )
            self.claim_verifier = ClaimVerifier(
                llm_client=self.llm_client,
                scraper=self.scraper,
                model=config.verify_model,
                vector_store=self.vector_store,
                tier_weights=tier_weights,
            )
            self.verification_reporter = VerificationReporter(
                confidence_threshold=config.verify_confidence_threshold,
            )
            logger.info(f"Claim verification enabled with model: {config.verify_model}")
            logger.info(f"Source tier weights: T1={config.verify_tier_1_weight}, T2={config.verify_tier_2_weight}, T3={config.verify_tier_3_weight}, T4={config.verify_tier_4_weight}")
        else:
            self.claim_extractor = None
            self.claim_verifier = None
            self.verification_reporter = None
            logger.info("Claim verification disabled")
        
        logger.info("Research pipeline initialized")
        
        # Rate limit awareness warning for high summarization parallelism
        if self.config.summary_parallel > 4:
            logger.warning(
                f"SUMMARY_PARALLEL is set to {self.config.summary_parallel}. "
                f"This makes {self.config.summary_parallel} concurrent LLM API calls. "
                f"If you see 429 (Too Many Requests) errors, reduce SUMMARY_PARALLEL."
            )
    
    def run(self, query_text: str, show_plan: bool = False) -> Report:
        """Run the complete research pipeline with iterative refinement.

        Args:
            query_text: The research query to investigate
            show_plan: If True, print the research plan before executing
        """
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

        if show_plan:
            self._display_plan(plan, intent)

        # Initialize for iterative research
        all_summaries = []
        all_scraped = {}  # Cache: url -> ScrapedContent
        iteration = 1
        max_iterations = self.config.max_iterations
        final_reflection = None  # Track final reflection result
        
        # Iterative research loop
        while iteration <= max_iterations:
            if iteration > 1:
                logger.info(f"\n{'='*80}")
                logger.info(f"ITERATION {iteration}/{max_iterations} - Additional Research")
                logger.info(f"{'='*80}\n")
            else:
                logger.info(f"\nITERATION {iteration}/{max_iterations} - Initial Research\n")
            
            # Stage 4: Research (web search)
            logger.info(f"Stage 4 (iter {iteration}): Conducting research...")
            try:
                search_results = self.researcher.search(plan)
                logger.info(f"Found {len(search_results)} search results")
            except Exception as e:
                logger.error(f"Research stage failed: {e}")
                search_results = []

            # Fail fast on first iteration if no results found
            if not search_results and not all_summaries:
                if iteration == 1:
                    logger.error("No search results found on initial research iteration")
                    raise RuntimeError(
                        "Search returned no results. Check your search provider "
                        "configuration and API key. Query: " + query_text[:100]
                    )

            # Stage 4.5: Rerank search results (before scraping)
            if self.search_reranker and search_results:
                logger.info(f"Stage 4.5 (iter {iteration}): Reranking search results...")
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
            logger.info(f"Stage 5 (iter {iteration}): Scraping content...")
            try:
                scraped_content = self.scraper.scrape_results(search_results)
                logger.info(f"Scraped {len(scraped_content)} URLs")

                # Cache scraped content for later use (e.g., verification)
                # Also store in database for future interactive queries
                for sc in scraped_content:
                    all_scraped[sc.url] = sc
                    # Store in vector store's database
                    try:
                        self.vector_store.store_scraped_content(
                            url=sc.url,
                            title=sc.title,
                            content=sc.content,
                            metadata=sc.metadata
                        )
                    except Exception as store_err:
                        logger.warning(f"Failed to store scraped content in DB for {sc.url}: {store_err}")

                # Log scraper statistics
                stats = self.scraper.get_fallback_usage_stats()
                if stats['fallback_used'] > 0:
                    logger.info(f"Fallback scraping used: {stats['fallback_used']} times (cost: ${stats['estimated_cost']:.2f})")
            except Exception as e:
                logger.error(f"Scraping stage failed: {e}")
                scraped_content = []
        
            # Stage 6: Generate summaries
            logger.info(f"Stage 6 (iter {iteration}): Generating summaries...")
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
        
            # Accumulate summaries from this iteration
            all_summaries.extend(summaries)
            logger.info(f"Total summaries accumulated: {len(all_summaries)}")
        
            # Stage 8: Reflection (evaluate completeness)
            logger.info(f"Stage 8 (iter {iteration}): Reflecting on completeness...")
            try:
                reflection = self.reflector.reflect(
                    query=query,
                    plan=plan,
                    summaries=all_summaries
                )
                
                # Always save the latest reflection
                final_reflection = reflection
                
                if not reflection.is_complete and reflection.additional_queries:
                    logger.warning(f"Reflection identified {len(reflection.missing_information)} gaps")
                    logger.info(f"Suggested {len(reflection.additional_queries)} additional queries")
                    
                    # Check if we can do another iteration
                    if iteration < max_iterations:
                        logger.info(f"Proceeding with iteration {iteration + 1} to address gaps")
                        
                        # Create new research plan with additional queries
                        from .models import ResearchPlan
                        plan = ResearchPlan(
                            query=query,
                            sections=plan.sections,
                            search_queries=reflection.additional_queries,
                            rationale=f"Iteration {iteration + 1}: {reflection.rationale}"
                        )
                        
                        iteration += 1
                        continue  # Continue the loop
                    else:
                        logger.warning(f"Maximum iterations ({max_iterations}) reached")
                        logger.info("Proceeding with available summaries")
                        break
                else:
                    logger.info("✓ Research deemed complete")
                    break
                    
            except Exception as e:
                logger.error(f"Reflection stage failed: {e}")
                logger.warning("Proceeding without reflection")
                break
        
        # End of iterative research loop
        logger.info(f"\nCompleted {iteration} iteration(s) with {len(all_summaries)} total summaries\n")
        
        # Stage 7: Final context assembly (rank and filter all accumulated summaries)
        logger.info("Stage 7: Assembling final context...")
        try:
            context = self.context_assembler.assemble_context(
                summaries=all_summaries,
                plan=plan
            )
            logger.info(f"Context assembled: {context.additional_context['selected_summaries']}/{context.additional_context['total_summaries']} summaries selected")
            logger.info(f"Relevance range: {context.additional_context['min_relevance_score']:.3f} - {context.additional_context['max_relevance_score']:.3f}")
            
            # Use filtered summaries for report
            final_summaries = context.summaries
        except Exception as e:
            logger.error(f"Context assembly stage failed: {e}")
            logger.warning("Using all summaries without re-ranking")
            final_summaries = all_summaries
        
        # Stage 9: Generate report
        logger.info("Stage 9: Generating report...")
        report = self._generate_report(query, plan, final_summaries, final_reflection)

        # Stage 9.5: Validate declared gaps against actual report content
        if (self.gap_validator
            and final_reflection
            and not final_reflection.is_complete
            and final_reflection.missing_information):
            logger.info("Stage 9.5: Validating declared research gaps...")
            try:
                validated_gaps = self.gap_validator.validate_gaps(
                    report_content=report.content,
                    declared_gaps=final_reflection.missing_information,
                    query=query,
                )
                original_count = len(final_reflection.missing_information)
                report.metadata["missing_information"] = validated_gaps
                report.metadata["original_gap_count"] = original_count
                report.metadata["validated_gap_count"] = len(validated_gaps)

                if not validated_gaps:
                    report.metadata["research_complete"] = True
                    report.metadata["status"] = "complete"
                    logger.info(f"All {original_count} declared gaps are addressed in the report -- upgrading status to complete")
                else:
                    logger.info(f"Gap validation: {original_count - len(validated_gaps)}/{original_count} gaps addressed, {len(validated_gaps)} remain")
            except Exception as e:
                logger.error(f"Gap validation failed: {e}")
                logger.warning("Continuing with original gap list")

        # Stage 10: Verify claims (OPTIONAL)
        if self.config.verify_claims and self.claim_extractor:
            logger.info("Stage 10: Verifying claims...")
            try:
                # Extract claims and group by source
                claims_by_source = self.claim_extractor.extract_and_group(
                    report_text=report.content,
                    summaries=final_summaries
                )
                
                if claims_by_source:
                    # Verify all claims (pass scraped content cache to avoid re-scraping)
                    results_by_source = self.claim_verifier.verify_all_sources(
                        claims_by_source, scraped_cache=all_scraped
                    )
                    
                    # Create summary and annotate report
                    verification_summary = self.verification_reporter.create_summary(results_by_source)
                    report = self.verification_reporter.annotate_report(report, verification_summary)
                    
                    logger.info(f"✓ Verification complete: {verification_summary.supported_claims}/{verification_summary.total_claims} claims supported")
                    if verification_summary.flagged_claims:
                        logger.warning(f"⚠️  Flagged {len(verification_summary.flagged_claims)} claims for review")
                else:
                    logger.info("No claims found to verify")
                    
            except Exception as e:
                logger.error(f"Verification stage failed: {e}")
                logger.warning("Continuing with unverified report")
        
        # Save report
        report_path = self._save_report(report)
        logger.info(f"Report saved to: {report_path}")
        
        return report
    
    def _display_plan(self, plan, intent) -> None:
        """Print the research plan to stdout."""
        print(f"\n{'='*80}")
        print("Research Plan")
        print(f"{'='*80}")
        print(f"Intent: {intent.value}")
        print(f"\nSections ({len(plan.sections)}):")
        for i, section in enumerate(plan.sections, 1):
            print(f"  {i}. {section}")
        print(f"\nSearch Queries ({len(plan.search_queries)}):")
        for i, sq in enumerate(plan.search_queries, 1):
            priority_marker = f"[P{sq.priority}]" if sq.priority else ""
            print(f"  {i}. {sq.query} {priority_marker}")
            print(f"     Purpose: {sq.purpose}")
        if plan.rationale:
            print(f"\nRationale: {plan.rationale}")
        print(f"{'='*80}\n")

    def _generate_report(self, query: Query, plan, summaries: list, reflection=None) -> Report:
        """Generate the final report from research summaries.
        
        Args:
            query: Original query
            plan: Research plan
            summaries: Final summaries for report
            reflection: Optional reflection result with gaps identified
        """
        
        # Build context from summaries
        if summaries:
            sources_text = "\n\n".join([
                f"Source {i+1}: {summary.url}\nTitle: {summary.citations[0].title if summary.citations else 'N/A'}\n{summary.text}"
                for i, summary in enumerate(summaries)
            ])
            
            # Add source-grounding context
            from datetime import datetime, timezone
            current_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
            
            source_grounding = f"""CRITICAL INSTRUCTIONS - SOURCE PRIORITIZATION:

Current Date: {current_date}

YOU MUST FOLLOW THESE RULES ABSOLUTELY:

1. **TRUST THE RESEARCH SOURCES COMPLETELY**
   - The sources below are MORE RECENT and MORE ACCURATE than your training data
   - If sources contradict what you "know", the SOURCES ARE CORRECT
   - Your training data may be outdated - defer to the provided research

2. **NEVER CORRECT OR "FIX" THE SOURCES**
   - Do not change names, titles, positions, dates, or facts from the sources
   - If sources say someone holds a position, accept it - do not "correct" based on your knowledge
   - If sources describe current events, treat them as current regardless of your training cutoff

3. **WRITE BASED ON SOURCES, NOT YOUR KNOWLEDGE**
   - Report exactly what the sources say
   - Do not add context like "former" or "current" unless it appears in the sources
   - Do not add qualifiers like "as of [date]" or "at the time" unless they're in the sources
   - Do not add background information from your training if it contradicts the sources

4. **WHEN IN DOUBT, STAY CLOSER TO THE SOURCE TEXT**
   - If something seems unusual, that's because the world has changed since your training
   - Preserve the sources' language and framing
   - Your job is to SYNTHESIZE THE RESEARCH, not to FACT-CHECK against outdated knowledge

5. **SOURCE CITATIONS ARE MANDATORY**
   - Use [Source N] citations for EVERY factual claim
   - Base EVERY statement on the provided sources
   - Do not speculate or infer beyond what sources state

REMEMBER: The research sources reflect REALITY. Your training data reflects THE PAST.
"""
            
            prompt = f"""{source_grounding}

---

Generate a comprehensive research report based on the following research.

Query: "{query.text}"
Intent: {query.intent.value if query.intent else "general"}

Report Sections to Cover:
{chr(10).join(f"- {section}" for section in plan.sections)}

Research Summaries:
{sources_text}

ADDITIONAL QUALITY GUIDELINES:
1. You are writing a FACTUAL RESEARCH REPORT, not a creative story
2. DO NOT invent contradictions, controversies, or disputes not in the sources
3. DO NOT claim sources "contradict" each other unless they make directly opposing statements
4. If all sources agree on something, report it as established fact - do not manufacture doubt
5. If a source clearly states something exists or is true, report it as such
6. When official/primary sources exist, they are authoritative
7. Only report what sources ACTUALLY say - do not paraphrase in ways that change meaning
8. Your goal is ACCURACY and CLARITY, not drama

TABLE HANDLING:
- If any Markdown tables appear in the research summaries, include them verbatim in the relevant sections.
- If a large table has been compacted in the summaries, include the compacted version as-is, including its note line. Do NOT recompute totals or statistics and do NOT reformat tables.
- If a table doesn't fit naturally inline, create a short "Tables" subsection under the appropriate section or add an "Appendix: Tables" at the end and reference it inline.

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
            
            # Check if research was complete
            research_complete = reflection.is_complete if reflection else True
            
            report = Report(
                query=query,
                content=content,
                citations=all_citations,
                metadata={
                    "intent": query.intent.value if query.intent else "unknown",
                    "sections": str(plan.sections),
                    "status": "complete" if research_complete else "incomplete",
                    "num_sources": len(summaries),
                    "research_complete": research_complete,
                    "missing_information": reflection.missing_information if reflection and not reflection.is_complete else [],
                    "reflection_rationale": reflection.rationale if reflection else "",
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
            
            # Add research limitations if incomplete
            if not report.metadata.get("research_complete", True):
                missing_info = report.metadata.get("missing_information", [])
                rationale = report.metadata.get("reflection_rationale", "")
                
                if missing_info:
                    f.write("\n\n---\n\n")
                    f.write("## ⚠️ Research Limitations\n\n")
                    f.write("This report was generated with the maximum number of research iterations, ")
                    f.write("but the following information gaps were identified:\n\n")
                    
                    for i, gap in enumerate(missing_info, 1):
                        f.write(f"{i}. {gap}\n")
                    
                    if rationale:
                        f.write(f"\n**Assessment:** {rationale}\n")
                    
                    f.write("\n*Note: The report above is based on available sources. ")
                    f.write("Additional research may be needed to fully address these gaps.*\n")
            
            # Add metadata
            f.write("\n---\n\n")
            f.write(f"**Metadata:**\n")
            for key, value in report.metadata.items():
                # Skip internal fields that were already presented
                if key not in ["missing_information", "reflection_rationale"]:
                    f.write(f"- {key}: {value}\n")
        
        return filepath
