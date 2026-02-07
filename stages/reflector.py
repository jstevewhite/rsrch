"""Reflection stage - analyzes research completeness and identifies gaps."""

import logging
from typing import List, Optional
from ..models import Query, ResearchPlan, Summary, ReflectionResult, SearchQuery
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)


class Reflector:
    """
    Reflects on research completeness and identifies gaps.
    
    Analyzes gathered summaries against the original query and research plan
    to determine if additional research is needed.
    """
    
    def __init__(self, llm_client: LLMClient, model: str = "gpt-4o"):
        """
        Initialize the reflector.
        
        Args:
            llm_client: LLM client for generating reflections
            model: Model to use for reflection (should be capable model)
        """
        self.llm_client = llm_client
        self.model = model
        logger.info(f"Reflector initialized with model: {model}")
    
    def reflect(
        self,
        query: Query,
        plan: ResearchPlan,
        summaries: List[Summary]
    ) -> ReflectionResult:
        """
        Reflect on research completeness.
        
        Args:
            query: Original user query
            plan: Research plan with sections and queries
            summaries: Gathered summaries from research
            
        Returns:
            ReflectionResult with completeness assessment and gaps
        """
        logger.info(f"Reflecting on completeness of {len(summaries)} summaries for query")
        
        # Build context from summaries - truncate aggressively to avoid token limits
        summaries_text = "\n\n".join([
            f"Source {i+1}: {summary.url}\n{summary.text[:300]}..."
            for i, summary in enumerate(summaries[:6])  # Limit to first 6 summaries
        ])
        if len(summaries) > 6:
            summaries_text += f"\n\n[... and {len(summaries) - 6} more sources]"
        
        prompt = f"""You are a research quality analyst. Analyze the research gathered so far and determine if it's sufficient to answer the user's query comprehensively.

Original Query: "{query.text}"
Intent: {query.intent.value if query.intent else "general"}

Planned Report Sections:
{chr(10).join(f"- {section}" for section in plan.sections)}

Research Gathered ({len(summaries)} sources):
{summaries_text}

CRITICAL ANALYSIS REQUIRED:
Evaluate if the gathered research provides sufficient information to:
1. Fully answer the original query
2. Cover all planned report sections with adequate depth
3. Provide authoritative and diverse perspectives
4. Include necessary examples, data, or technical details

Identify specific information gaps such as:
- Missing perspectives or viewpoints
- Insufficient technical depth or examples
- Lack of recent/current information
- Missing comparison or context
- Unexplored aspects of the query
- Need for official documentation or primary sources

Respond with a JSON object:
{{
  "is_complete": true/false,
  "confidence": 0.0-1.0,
  "missing_information": [
    "Specific gap 1",
    "Specific gap 2",
    ...
  ],
  "additional_queries": [
    {{"query": "specific search query", "purpose": "what this will find", "priority": 1}}
  ],
  "rationale": "Detailed explanation of completeness assessment and why additional research is/isn't needed"
}}

Set is_complete to:
- true: Research is comprehensive and sufficient to produce a high-quality report
- false: Significant gaps exist that require additional research

Be critical but realistic. Minor gaps are acceptable if core query is well-addressed.
"""
        
        try:
            logger.debug(f"Reflection prompt length: {len(prompt)} characters")
            
            # Use text completion and parse JSON manually - more reliable across models
            text_response = self.llm_client.complete(
                prompt=prompt + "\n\nIMPORTANT: Return ONLY a valid JSON object. No other text.",
                model=self.model,
                temperature=0.3,
                max_tokens=4000,  # Increased from 2000 to avoid truncation
            )
            
            logger.debug(f"Reflection response length: {len(text_response)} chars")
            logger.debug(f"Reflection response preview: {text_response[:300]}...")
            logger.debug(f"Reflection response ending: ...{text_response[-200:]}")
            
            # Parse JSON from the text response
            import json
            import re
            # Try to extract JSON - first from markdown code block, then raw
            json_str = None
            # Look for ```json or ``` code blocks
            code_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text_response, re.DOTALL)
            if code_match:
                json_str = code_match.group(1).strip()
                logger.debug("Found JSON in markdown code block")
            else:
                # Look for raw JSON object
                obj_match = re.search(r'(\{[\s\S]*\})', text_response)
                if obj_match:
                    json_str = obj_match.group(1).strip()
                    logger.debug("Found raw JSON object")
            
            if json_str:
                try:
                    response = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed: {e}")
                    logger.warning(f"JSON string length: {len(json_str)} chars")
                    logger.warning(f"JSON ending (last 100 chars): ...{json_str[-100:]}")
                    # Try to fix common issues - truncate at the last complete property
                    last_brace = json_str.rfind('}')
                    if last_brace > 0:
                        truncated = json_str[:last_brace+1]
                        try:
                            response = json.loads(truncated)
                            logger.info("Successfully parsed truncated JSON")
                        except:
                            # Try to extract just the required fields with regex
                            is_complete_match = re.search(r'"is_complete"\s*:\s*(true|false)', json_str, re.IGNORECASE)
                            confidence_match = re.search(r'"confidence"\s*:\s*(0?\.\d+|1\.0|1)', json_str)
                            rationale_match = re.search(r'"rationale"\s*:\s*"([^"]*)"', json_str, re.DOTALL)
                            
                            if is_complete_match:
                                response = {
                                    "is_complete": is_complete_match.group(1).lower() == "true",
                                    "confidence": float(confidence_match.group(1)) if confidence_match else 0.5,
                                    "missing_information": [],
                                    "additional_queries": [],
                                    "rationale": rationale_match.group(1) if rationale_match else "Extracted from malformed response"
                                }
                                logger.info("Extracted required fields from malformed JSON")
                            else:
                                logger.error(f"Could not extract required fields from JSON: {json_str[:300]}")
                                raise
                    else:
                        logger.error(f"Could not parse JSON: {json_str[:300]}")
                        raise
            else:
                logger.error(f"No JSON found in response. Full response: {text_response[:500]}")
                raise Exception("No JSON in response")
            
            is_complete = response.get("is_complete", False)
            confidence = response.get("confidence", 0.5)
            missing_info = response.get("missing_information", [])
            additional_queries_data = response.get("additional_queries", [])
            rationale = response.get("rationale", "")
            
            # Convert additional queries
            additional_queries = [
                SearchQuery(
                    query=sq["query"],
                    purpose=sq["purpose"],
                    priority=sq.get("priority", 3)
                )
                for sq in additional_queries_data
            ]
            
            result = ReflectionResult(
                is_complete=is_complete,
                missing_information=missing_info,
                additional_queries=additional_queries,
                rationale=rationale,
            )
            
            if is_complete:
                logger.info(f"✓ Research deemed complete (confidence: {confidence:.2f})")
            else:
                logger.warning(f"✗ Research incomplete - {len(missing_info)} gaps identified, {len(additional_queries)} additional queries suggested")
                logger.info(f"Missing: {', '.join(missing_info[:3])}{'...' if len(missing_info) > 3 else ''}")
            
            logger.debug(f"Reflection rationale: {rationale[:200]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            # Return safe default - assume complete to avoid infinite loops
            return ReflectionResult(
                is_complete=True,
                missing_information=[],
                additional_queries=[],
                rationale=f"Reflection failed, proceeding with available research. Error: {e}",
            )


class GapValidator:
    """Validates whether declared research gaps are actually present in the final report.

    The reflector identifies gaps during the iterative research loop using truncated
    summaries. By the time the full report is generated, many of those gaps may have
    been addressed. This class checks the final report against declared gaps and
    removes any that are actually covered.
    """

    def __init__(self, llm_client: LLMClient, model: str = "gpt-4o"):
        """Initialize the gap validator.

        Args:
            llm_client: LLM client for validation
            model: Model to use (reuses reflection model)
        """
        self.llm_client = llm_client
        self.model = model
        logger.info(f"GapValidator initialized with model: {model}")

    def validate_gaps(
        self,
        report_content: str,
        declared_gaps: List[str],
        query: Query,
    ) -> List[str]:
        """Check which declared gaps are truly unaddressed in the final report.

        Args:
            report_content: The generated report text
            declared_gaps: List of gap descriptions from reflection
            query: Original query for context

        Returns:
            Filtered list containing only gaps that remain genuinely unaddressed
        """
        if not declared_gaps:
            return []

        gaps_list = "\n".join(f"{i+1}. {gap}" for i, gap in enumerate(declared_gaps))

        # Truncate report if very long to stay within context limits
        max_report_chars = 200000
        report_text = report_content[:max_report_chars]
        if len(report_content) > max_report_chars:
            report_text += "\n\n[Report truncated for gap validation...]"

        prompt = f"""You are a research quality analyst. A research report was generated for the query below.
During the research process, the following information gaps were identified.
Your task: determine which gaps are STILL genuinely unaddressed in the final report.

Original Query: "{query.text}"

Declared Gaps:
{gaps_list}

Final Report:
{report_text}

For each gap, determine if the report actually addresses it (even partially).
A gap is "addressed" if the report contains substantive information about that topic,
even if not exhaustive.

Return a JSON object:
{{
  "remaining_gaps": [
    "Gap description that is truly NOT addressed in the report"
  ],
  "removed_gaps": [
    {{"gap": "Gap that was addressed", "evidence": "Brief section reference or topic showing it's covered"}}
  ]
}}

Be strict about what counts as "unaddressed" -- if the report discusses the topic
at all with factual content, the gap is addressed."""

        try:
            response = self.llm_client.complete_json(
                prompt=prompt,
                model=self.model,
                temperature=0.2,
                max_tokens=2000,
            )

            remaining = response.get("remaining_gaps", declared_gaps)
            removed = response.get("removed_gaps", [])

            if removed:
                logger.info(f"Gap validation: {len(removed)}/{len(declared_gaps)} gaps were actually addressed in the report")
                for r in removed:
                    gap_text = r.get("gap", "unknown") if isinstance(r, dict) else str(r)
                    evidence = r.get("evidence", "none")[:100] if isinstance(r, dict) else ""
                    logger.debug(f"  Removed gap: {gap_text} (evidence: {evidence})")

            if not remaining:
                logger.info("Gap validation: ALL declared gaps are addressed in the report")
            else:
                logger.info(f"Gap validation: {len(remaining)} gaps remain unaddressed")

            return remaining

        except Exception as e:
            logger.error(f"Gap validation failed: {e}")
            # On failure, return original gaps (safe default)
            return declared_gaps
