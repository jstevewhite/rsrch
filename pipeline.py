"""Research pipeline orchestrator."""

import logging
from typing import Optional
from pathlib import Path

from .config import Config
from .models import Query, Report
from .llm_client import LLMClient
from .stages import IntentClassifier, Planner

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
        
        # Stage 4: Research (stub - needs implementation)
        logger.info("Stage 4: Conducting research...")
        logger.warning("Research stage not yet implemented - using placeholder")
        search_results = []
        
        # Stage 5: Scrape content (stub - needs implementation)
        logger.info("Stage 5: Scraping content...")
        logger.warning("Scraping stage not yet implemented - using placeholder")
        scraped_content = []
        
        # Stage 6: Generate summaries (stub - needs implementation)
        logger.info("Stage 6: Generating summaries...")
        logger.warning("Summary stage not yet implemented - using placeholder")
        summaries = []
        
        # Stage 7: Assemble context (stub - needs implementation)
        logger.info("Stage 7: Assembling context...")
        logger.warning("Context assembly stage not yet implemented - using placeholder")
        
        # Stage 8: Reflection (stub - needs implementation)
        logger.info("Stage 8: Reflecting on completeness...")
        logger.warning("Reflection stage not yet implemented - using placeholder")
        
        # Stage 9: Generate report
        logger.info("Stage 9: Generating report...")
        report = self._generate_report(query, plan)
        
        # Save report
        report_path = self._save_report(report)
        logger.info(f"Report saved to: {report_path}")
        
        return report
    
    def _generate_report(self, query: Query, plan) -> Report:
        """Generate the final report (simplified version)."""
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
                temperature=0.7,
                max_tokens=4000,
            )
            
            report = Report(
                query=query,
                content=content,
                citations=[],  # Will be populated when research is implemented
                metadata={
                    "intent": query.intent.value if query.intent else "unknown",
                    "sections": str(plan.sections),
                    "status": "preliminary",
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
            f.write("\n\n---\n\n")
            f.write(f"**Metadata:**\n")
            for key, value in report.metadata.items():
                f.write(f"- {key}: {value}\n")
        
        return filepath
