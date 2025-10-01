"""Claim verification stage - extracts and verifies claims against sources."""

import logging
import re
import json
from typing import List, Dict, Optional
from collections import defaultdict

from ..models import (
    Report, Summary, ExtractedClaim, VerificationResult, 
    VerificationSummary, ScrapedContent
)
from ..llm_client import LLMClient
from .scraper import Scraper

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """Extract claims from report and group by source."""
    
    def __init__(self, llm_client: LLMClient, model: str):
        """
        Initialize claim extractor.
        
        Args:
            llm_client: LLM client for extraction
            model: Model to use for extraction
        """
        self.llm_client = llm_client
        self.model = model
    
    def extract_and_group(
        self, 
        report_text: str,
        summaries: List[Summary]
    ) -> Dict[str, List[ExtractedClaim]]:
        """
        Extract claims from report and group by source URL.
        
        Args:
            report_text: The generated report text
            summaries: List of summaries with URLs (to map source numbers to URLs)
            
        Returns:
            Dictionary mapping source URL to list of claims from that source
        """
        logger.info("Extracting claims from report...")
        
        # Build source number to URL mapping
        source_map = self._build_source_map(report_text, summaries)
        if not source_map:
            logger.warning("No sources found in report")
            return {}
        
        # Extract all claims with citations
        claims = self._extract_claims(report_text, source_map)
        
        if not claims:
            logger.warning("No claims with citations found in report")
            return {}
        
        # Group by source URL
        claims_by_source = defaultdict(list)
        for claim in claims:
            claims_by_source[claim.source_url].append(claim)
        
        logger.info(f"Extracted {len(claims)} claims from {len(claims_by_source)} sources")
        for url, url_claims in claims_by_source.items():
            logger.debug(f"  {url}: {len(url_claims)} claims")
        
        return dict(claims_by_source)
    
    def _build_source_map(
        self, 
        report_text: str,
        summaries: List[Summary]
    ) -> Dict[int, str]:
        """
        Build mapping from [Source N] to URL.
        
        Args:
            report_text: Report text
            summaries: List of summaries
            
        Returns:
            Dictionary mapping source number to URL
        """
        # Find all [Source N] citations in report
        citation_pattern = r'\[Source (\d+)\]'
        cited_numbers = set(int(match) for match in re.findall(citation_pattern, report_text))
        
        if not cited_numbers:
            return {}
        
        # Map to URLs (assuming Source N corresponds to summaries[N-1])
        source_map = {}
        for num in cited_numbers:
            if 0 < num <= len(summaries):
                source_map[num] = summaries[num - 1].url
            else:
                logger.warning(f"Source {num} cited but not in summaries list")
        
        return source_map
    
    def _extract_claims(
        self,
        report_text: str,
        source_map: Dict[int, str]
    ) -> List[ExtractedClaim]:
        """
        Extract claims with citations from report text.
        
        Args:
            report_text: Report text
            source_map: Mapping from source number to URL
            
        Returns:
            List of extracted claims
        """
        prompt = f"""
Extract all factual claims from this report that cite sources.

Report:
{report_text}

For each claim:
1. Extract the claim text (complete, standalone assertion)
2. Note which [Source N] it cites (extract the N)
3. Classify the claim type:
   - factual: General factual statement
   - statistic: Contains numbers, percentages, counts
   - quote: Direct quote from someone
   - date: Specific date or time reference

Return as JSON:
{{
  "claims": [
    {{
      "text": "Donald Trump announced a 20-point peace plan",
      "source_number": 1,
      "type": "factual",
      "context": "surrounding sentence for context"
    }},
    {{
      "text": "The plan was unveiled on September 29",
      "source_number": 1,
      "type": "date",
      "context": "..."
    }}
  ]
}}

IMPORTANT:
- Extract COMPLETE claims that can stand alone (don't cut off mid-sentence)
- Include ALL factual assertions that have [Source N] citations
- Don't extract opinions, analysis, or unsourced statements
- Each claim should be verifiable against its source
- Include the surrounding context (1-2 sentences)
"""
        
        try:
            response = self.llm_client.complete_json(
                prompt=prompt,
                model=self.model,
                temperature=0.2,  # Low temperature for consistency
            )
            
            claims = []
            for claim_data in response.get("claims", []):
                source_number = claim_data.get("source_number")
                if source_number and source_number in source_map:
                    claims.append(ExtractedClaim(
                        text=claim_data["text"],
                        source_number=source_number,
                        source_url=source_map[source_number],
                        claim_type=claim_data.get("type", "factual"),
                        context=claim_data.get("context", ""),
                    ))
                else:
                    logger.warning(f"Claim references invalid source: {source_number}")
            
            return claims
            
        except Exception as e:
            logger.error(f"Failed to extract claims: {e}")
            return []


class ClaimVerifier:
    """Verify claims against source content."""
    
    # Model context limits (approximate, in characters)
    MODEL_CONTEXT_LIMITS = {
        "gpt-4o-mini": 500000,  # ~128K tokens
        "gpt-4o": 500000,
        "gpt-4": 320000,  # ~80K tokens
        "default": 300000,  # Conservative default
    }
    
    @staticmethod
    def _get_current_date_context() -> str:
        """Get current date context for verification prompt."""
        from datetime import datetime
        now = datetime.now()
        return f"{now.strftime('%B %d, %Y')} ({now.year})"
    
    def __init__(self, llm_client: LLMClient, scraper: Scraper, model: str):
        """
        Initialize claim verifier.
        
        Args:
            llm_client: LLM client for verification
            scraper: Scraper for re-fetching source content
            model: Model to use for verification
        """
        self.llm_client = llm_client
        self.scraper = scraper
        self.model = model
    
    def verify_all_sources(
        self,
        claims_by_source: Dict[str, List[ExtractedClaim]]
    ) -> Dict[str, List[VerificationResult]]:
        """
        Verify all claims, grouped by source.
        
        Args:
            claims_by_source: Dictionary mapping source URL to claims
            
        Returns:
            Dictionary mapping source URL to verification results
        """
        results_by_source = {}
        
        for i, (url, claims) in enumerate(claims_by_source.items(), 1):
            logger.info(f"Verifying {len(claims)} claims from source {i}/{len(claims_by_source)}: {url}")
            results = self.verify_source_claims(url, claims)
            results_by_source[url] = results
        
        return results_by_source
    
    def verify_source_claims(
        self,
        source_url: str,
        claims: List[ExtractedClaim]
    ) -> List[VerificationResult]:
        """
        Verify all claims from one source in a single LLM call.
        
        Args:
            source_url: The source URL
            claims: List of claims from this source
            
        Returns:
            List of verification results
        """
        # Step 1: Re-scrape the source
        logger.debug(f"Re-scraping {source_url}...")
        try:
            scraped = self.scraper.scrape_url(source_url)
            if not scraped or not scraped.content:
                logger.warning(f"Failed to scrape {source_url}")
                return self._mark_unverifiable(claims, "Source unavailable or empty")
        except Exception as e:
            logger.error(f"Error scraping {source_url}: {e}")
            return self._mark_unverifiable(claims, f"Scraping error: {str(e)}")
        
        # Step 2: Check content length and truncate if needed
        source_text = self._prepare_source_content(scraped.content)
        
        # Step 3: Build verification prompt
        claims_json = json.dumps([
            {
                "id": i,
                "claim": claim.text,
                "type": claim.claim_type
            }
            for i, claim in enumerate(claims)
        ], indent=2)
        
        # Get current date context
        current_date = self._get_current_date_context()
        source_date = scraped.retrieved_at.strftime('%B %d, %Y') if scraped.retrieved_at else "Unknown"
        
        prompt = f"""
TASK: Verify if these claims are supported by the source content.

IMPORTANT VERIFICATION CONTEXT:
- Current date: {current_date}
- Source retrieved: {source_date}
- Your task is to verify claims based ONLY on what the source states
- IGNORE any conflicts with your training data
- If the source explicitly states a fact, accept it as stated in the source
- Example: If source says "President Trump" in 2025, verify based on source text, not your training knowledge
- Focus on: Does the SOURCE support the claim? Not: Does your training data support it?

SOURCE: {source_url}

CLAIMS TO VERIFY:
{claims_json}

SOURCE CONTENT:
{source_text}

---

For EACH claim, analyze:
1. Is it explicitly stated in the source? (direct support)
2. Is it strongly implied by the source? (indirect support)
3. Is it partially true but missing nuance? (partial support)
4. Is it not mentioned or unsupported? (unsupported)
5. Does the source contradict it? (contradicted)

Return JSON:
{{
  "verifications": [
    {{
      "claim_id": 0,
      "verdict": "supported",
      "confidence": 0.95,
      "evidence": "exact quote or relevant passage from source",
      "reasoning": "brief explanation of why this verdict"
    }},
    {{
      "claim_id": 1,
      "verdict": "partial",
      "confidence": 0.60,
      "evidence": "source says X but claim says Y",
      "reasoning": "claim is close but not exact"
    }}
  ]
}}

GUIDELINES:
- Be strict: only "supported" if clearly stated or strongly implied IN THE SOURCE
- Use "partial" for claims that are approximately correct but imprecise
- Use "unsupported" if not mentioned in the source
- Use "contradicted" ONLY if the source explicitly contradicts it (not your training data)
- Provide exact quotes from the source as evidence when possible
- Confidence scale:
  * 0.9-1.0 = very confident in verdict based on source
  * 0.7-0.9 = confident based on source
  * 0.5-0.7 = uncertain
  * <0.5 = very uncertain
"""
        
        # Step 4: Get verification results
        try:
            response = self.llm_client.complete_json(
                prompt=prompt,
                model=self.model,
                temperature=0.1,  # Very low temperature for consistency
            )
            
            return self._parse_verification_response(response, claims)
            
        except Exception as e:
            logger.error(f"Verification failed for {source_url}: {e}")
            return self._mark_unverifiable(claims, f"Verification error: {str(e)}")
    
    def _prepare_source_content(self, content: str) -> str:
        """
        Prepare source content, truncating if too large.
        
        Args:
            content: Raw source content
            
        Returns:
            Prepared content (possibly truncated)
        """
        max_length = self.MODEL_CONTEXT_LIMITS.get(
            self.model,
            self.MODEL_CONTEXT_LIMITS["default"]
        )
        
        if len(content) <= max_length:
            return content
        
        logger.warning(f"Source content too large ({len(content)} chars), truncating to {max_length}")
        # Truncate and add notice
        return content[:max_length] + "\n\n[Content truncated due to length...]"
    
    def _parse_verification_response(
        self,
        response: Dict,
        claims: List[ExtractedClaim]
    ) -> List[VerificationResult]:
        """
        Parse verification response into VerificationResult objects.
        
        Args:
            response: JSON response from LLM
            claims: Original claims (for mapping by ID)
            
        Returns:
            List of verification results
        """
        results = []
        verifications = response.get("verifications", [])
        
        for verification in verifications:
            claim_id = verification.get("claim_id")
            if claim_id is None or claim_id >= len(claims):
                logger.warning(f"Invalid claim_id in response: {claim_id}")
                continue
            
            claim = claims[claim_id]
            results.append(VerificationResult(
                claim=claim,
                verdict=verification.get("verdict", "unsupported"),
                confidence=float(verification.get("confidence", 0.0)),
                evidence=verification.get("evidence"),
                reasoning=verification.get("reasoning", "No reasoning provided"),
            ))
        
        # Handle missing verifications
        verified_ids = {v.get("claim_id") for v in verifications}
        for i, claim in enumerate(claims):
            if i not in verified_ids:
                logger.warning(f"Claim {i} not verified, marking as unverifiable")
                results.append(VerificationResult(
                    claim=claim,
                    verdict="unsupported",
                    confidence=0.0,
                    evidence=None,
                    reasoning="Not included in verification response",
                ))
        
        return results
    
    def _mark_unverifiable(
        self,
        claims: List[ExtractedClaim],
        reason: str
    ) -> List[VerificationResult]:
        """
        Mark all claims as unverifiable.
        
        Args:
            claims: List of claims
            reason: Reason they couldn't be verified
            
        Returns:
            List of verification results marking all as unverifiable
        """
        return [
            VerificationResult(
                claim=claim,
                verdict="unsupported",
                confidence=0.0,
                evidence=None,
                reasoning=f"Cannot verify: {reason}",
            )
            for claim in claims
        ]


class VerificationReporter:
    """Create verification report and annotate original report."""
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize verification reporter.
        
        Args:
            confidence_threshold: Minimum confidence to not flag a claim
        """
        self.confidence_threshold = confidence_threshold
    
    def create_summary(
        self,
        results_by_source: Dict[str, List[VerificationResult]]
    ) -> VerificationSummary:
        """
        Create summary of verification results.
        
        Args:
            results_by_source: Results grouped by source URL
            
        Returns:
            Verification summary with statistics
        """
        all_results = [
            result
            for results in results_by_source.values()
            for result in results
        ]
        
        total = len(all_results)
        supported = sum(1 for r in all_results if r.verdict == "supported")
        partial = sum(1 for r in all_results if r.verdict == "partial")
        unsupported = sum(1 for r in all_results if r.verdict == "unsupported")
        contradicted = sum(1 for r in all_results if r.verdict == "contradicted")
        
        # Flag problematic claims
        flagged = [
            result for result in all_results
            if result.verdict in ["unsupported", "contradicted", "partial"]
               or result.confidence < self.confidence_threshold
        ]
        
        # Calculate average confidence
        avg_confidence = (
            sum(r.confidence for r in all_results) / total
            if total > 0 else 0.0
        )
        
        return VerificationSummary(
            total_claims=total,
            supported_claims=supported,
            partial_claims=partial,
            unsupported_claims=unsupported,
            contradicted_claims=contradicted,
            flagged_claims=flagged,
            avg_confidence=avg_confidence,
            by_source=results_by_source,
        )
    
    def create_appendix(self, summary: VerificationSummary) -> str:
        """
        Create verification appendix for report.
        
        Args:
            summary: Verification summary
            
        Returns:
            Markdown formatted appendix
        """
        lines = []
        lines.append("# Verification Report\n")
        lines.append("## Summary\n")
        lines.append(f"- **Total Claims**: {summary.total_claims}")
        lines.append(f"- **Fully Supported**: {summary.supported_claims} ({self._percentage(summary.supported_claims, summary.total_claims)}%)")
        lines.append(f"- **Partially Supported**: {summary.partial_claims} ({self._percentage(summary.partial_claims, summary.total_claims)}%)")
        lines.append(f"- **Unsupported**: {summary.unsupported_claims} ({self._percentage(summary.unsupported_claims, summary.total_claims)}%)")
        if summary.contradicted_claims > 0:
            lines.append(f"- **Contradicted**: {summary.contradicted_claims} ({self._percentage(summary.contradicted_claims, summary.total_claims)}%)")
        lines.append(f"- **Average Confidence**: {summary.avg_confidence:.2f}\n")
        
        if summary.flagged_claims:
            lines.append("## Flagged Claims\n")
            lines.append(f"The following {len(summary.flagged_claims)} claims require attention:\n")
            
            for i, result in enumerate(summary.flagged_claims, 1):
                icon = self._get_verdict_icon(result.verdict)
                lines.append(f"### {icon} Claim {i}: {result.verdict.upper()}\n")
                lines.append(f"**Claim**: \"{result.claim.text}\"\n")
                lines.append(f"- **Source**: {result.claim.source_url}")
                lines.append(f"- **Confidence**: {result.confidence:.2f}")
                lines.append(f"- **Reasoning**: {result.reasoning}")
                if result.evidence:
                    lines.append(f"- **Evidence**: \"{result.evidence}\"")
                lines.append("")
        
        # By-source breakdown
        lines.append("## By-Source Analysis\n")
        for url, results in summary.by_source.items():
            total_for_source = len(results)
            supported_for_source = sum(1 for r in results if r.verdict == "supported")
            flagged_for_source = sum(1 for r in results if r.verdict in ["unsupported", "contradicted", "partial"] or r.confidence < self.confidence_threshold)
            avg_conf_for_source = sum(r.confidence for r in results) / total_for_source if total_for_source > 0 else 0.0
            
            lines.append(f"**Source**: {url}")
            lines.append(f"- Claims verified: {total_for_source}")
            lines.append(f"- Supported: {supported_for_source} ({self._percentage(supported_for_source, total_for_source)}%)")
            lines.append(f"- Flagged: {flagged_for_source}")
            lines.append(f"- Avg confidence: {avg_conf_for_source:.2f}\n")
        
        return "\n".join(lines)
    
    def annotate_report(
        self,
        report: Report,
        summary: VerificationSummary
    ) -> Report:
        """
        Add verification information to report.
        
        Args:
            report: Original report
            summary: Verification summary
            
        Returns:
            Report with verification appendix and metadata
        """
        # Add metadata
        report.metadata["verification"] = {
            "total_claims": summary.total_claims,
            "supported": summary.supported_claims,
            "partial": summary.partial_claims,
            "unsupported": summary.unsupported_claims,
            "contradicted": summary.contradicted_claims,
            "avg_confidence": summary.avg_confidence,
            "flagged_count": len(summary.flagged_claims),
            "verification_pass": len(summary.flagged_claims) == 0,
        }
        
        # Add appendix
        appendix = self.create_appendix(summary)
        report.content += f"\n\n---\n\n{appendix}"
        
        logger.info(f"Verification complete: {summary.supported_claims}/{summary.total_claims} claims supported")
        if summary.flagged_claims:
            logger.warning(f"Flagged {len(summary.flagged_claims)} claims for review")
        
        return report
    
    @staticmethod
    def _percentage(part: int, total: int) -> int:
        """Calculate percentage, handling division by zero."""
        return int(100 * part / total) if total > 0 else 0
    
    @staticmethod
    def _get_verdict_icon(verdict: str) -> str:
        """Get emoji icon for verdict."""
        icons = {
            "supported": "✅",
            "partial": "⚠️",
            "unsupported": "❌",
            "contradicted": "🚫",
        }
        return icons.get(verdict, "❓")
