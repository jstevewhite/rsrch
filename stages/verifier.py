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
        # Find citations in report. Support formats:
        # - [Source 1], [source1], [Source 1, 2]
        # - [1], [1, 2, 3]
        # Capture the content inside brackets and then extract all digits
        citation_pattern = r'\[(?:source\s*)?([\d,\s]+)\]'
        inner_groups = re.findall(citation_pattern, report_text, flags=re.IGNORECASE)
        cited_numbers = set(
            int(n) for group in inner_groups for n in re.findall(r'\d+', group)
        )
        
        if not cited_numbers:
            return {}
        
        # Map to URLs (assuming Source/number N corresponds to summaries[N-1])
        source_map = {}
        for num in cited_numbers:
            if 0 < num <= len(summaries):
                source_map[num] = summaries[num - 1].url
            else:
                logger.warning(f"Source number {num} cited but not in summaries list (len={len(summaries)})")
        
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
2. Identify which source numbers it cites by reading bracketed citations, e.g. [1], [1, 3], [Source 2]
   - Return all cited numbers for the claim as an array in \"source_numbers\"
3. Classify the claim type:
   - factual: General factual statement
   - statistic: Contains numbers, percentages, counts
   - quote: Direct quote from someone
   - date: Specific date or time reference

Return as JSON:
{{
  \"claims\": [
    {{
      \"text\": \"The government shut down at 12:01 a.m. on October 1, 2025\",
      \"source_numbers\": [1, 2, 3],
      \"type\": \"date\",
      \"context\": \"surrounding sentence for context\"
    }},
    {{
      \"text\": \"Approximately 750,000 federal employees are furloughed\",
      \"source_numbers\": [3, 4, 5],
      \"type\": \"statistic\",
      \"context\": \"...\"
    }}
  ]
}}

IMPORTANT:
- Extract COMPLETE claims that can stand alone (don't cut off mid-sentence)
- Include ALL factual assertions that have bracketed source citations like [1], [1, 2] or [Source 2]
- Don't extract opinions, analysis, or unsourced statements
- Each claim should be verifiable against its source(s)
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
                # Support both legacy single "source_number" and new plural "source_numbers"
                numbers = []
                if "source_numbers" in claim_data and isinstance(claim_data["source_numbers"], list):
                    # Filter to ints only
                    numbers = [int(n) for n in claim_data["source_numbers"] if isinstance(n, (int, str)) and str(n).isdigit()]
                elif "source_number" in claim_data:
                    n = claim_data.get("source_number")
                    if isinstance(n, (int, str)) and str(n).isdigit():
                        numbers = [int(n)]
                
                if not numbers:
                    logger.warning("Claim missing source_numbers/source_number; skipping")
                    continue
                
                # If multiple sources cited, check if claim should be split or verified against all
                if len(numbers) > 1:
                    # For multi-source claims, create a special composite claim
                    # that will be verified against all cited sources
                    valid_urls = [source_map[n] for n in numbers if n in source_map]
                    if valid_urls:
                        claims.append(ExtractedClaim(
                            text=claim_data.get("text", "").strip(),
                            source_number=numbers[0],  # Primary source for grouping
                            source_url=source_map.get(numbers[0], valid_urls[0]),
                            claim_type=claim_data.get("type", "factual"),
                            context=claim_data.get("context", ""),
                            additional_sources=[source_map[n] for n in numbers[1:] if n in source_map],
                        ))
                else:
                    for source_number in numbers:
                        if source_number in source_map:
                            claims.append(ExtractedClaim(
                                text=claim_data.get("text", "").strip(),
                                source_number=source_number,
                                source_url=source_map[source_number],
                                claim_type=claim_data.get("type", "factual"),
                                context=claim_data.get("context", ""),
                                additional_sources=[],
                            ))
                        else:
                            logger.warning(f"Claim references invalid source number: {source_number}")
            
            # Fallback: if LLM returned no claims, try regex-based extraction of sentences with citations
            if not claims:
                logger.warning("LLM returned no claims; attempting regex-based extraction fallback")
                try:
                    # Split text into rough sentences (simple heuristic)
                    # Keep punctuation; split on . ! ? followed by space/newline
                    sentence_pattern = r'[^.!?\n]*\[[^\]]+\][^.!?\n]*[.!?]'
                    sentence_matches = re.finditer(sentence_pattern, report_text, flags=re.IGNORECASE)
                    seen = set()
                    for m in sentence_matches:
                        sentence = m.group(0).strip()
                        key = sentence.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        # Extract all cited numbers in this sentence using the same pattern as _build_source_map
                        bracket_groups = re.findall(r'\[(?:source\s*)?([\d,\s]+)\]', sentence, flags=re.IGNORECASE)
                        nums = [int(n) for g in bracket_groups for n in re.findall(r'\d+', g)]
                        valid_nums = [n for n in nums if n in source_map]
                        if not valid_nums:
                            continue
                        # Create a single claim with all sources (multi-source support)
                        primary_num = valid_nums[0]
                        additional_urls = [source_map[n] for n in valid_nums[1:]] if len(valid_nums) > 1 else None
                        claims.append(ExtractedClaim(
                            text=sentence,
                            source_number=primary_num,
                            source_url=source_map[primary_num],
                            claim_type="factual",
                            context=sentence,
                            additional_sources=additional_urls,
                        ))
                    if claims:
                        logger.info(f"Regex fallback extracted {len(claims)} claims")
                except Exception as ex:
                    logger.error(f"Regex fallback extraction failed: {ex}")
            
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
    
    def __init__(self, llm_client: LLMClient, scraper: Scraper, model: str, vector_store=None):
        """
        Initialize claim verifier.
        
        Args:
            llm_client: LLM client for verification
            scraper: Scraper for re-fetching source content
            model: Model to use for verification
            vector_store: Optional vector store for accessing cached scraped content
        """
        self.llm_client = llm_client
        self.scraper = scraper
        self.model = model
        self.vector_store = vector_store
    
    def verify_all_sources(
        self,
        claims_by_source: Dict[str, List[ExtractedClaim]],
        scraped_cache: Optional[Dict[str, ScrapedContent]] = None
    ) -> Dict[str, List[VerificationResult]]:
        """
        Verify all claims, grouped by source.

        Args:
            claims_by_source: Dictionary mapping source URL to claims
            scraped_cache: Optional cache of already-scraped content

        Returns:
            Dictionary mapping source URL to verification results
        """
        results_by_source = {}

        for i, (url, claims) in enumerate(claims_by_source.items(), 1):
            logger.info(f"Verifying {len(claims)} claims from source {i}/{len(claims_by_source)}: {url}")
            results = self.verify_source_claims(url, claims, scraped_cache=scraped_cache)
            results_by_source[url] = results

        return results_by_source
    
    def verify_source_claims(
        self,
        source_url: str,
        claims: List[ExtractedClaim],
        scraped_cache: Optional[Dict[str, ScrapedContent]] = None
    ) -> List[VerificationResult]:
        """
        Verify all claims from one source in a single LLM call.

        Args:
            source_url: The source URL
            claims: List of claims from this source
            scraped_cache: Optional cache of already-scraped content

        Returns:
            List of verification results
        """
        # Step 1: Get source content (from cache, DB, or scrape)
        scraped = None
        
        # Try in-memory cache first
        if scraped_cache and source_url in scraped_cache:
            scraped = scraped_cache[source_url]
            logger.debug(f"Using in-memory cached content for {source_url}")
        # Try database cache
        elif self.vector_store:
            db_content = self.vector_store.get_scraped_content(source_url)
            if db_content:
                logger.debug(f"Using DB cached content for {source_url}")
                from datetime import datetime
                from ..models import ScrapedContent
                scraped = ScrapedContent(
                    url=db_content['url'],
                    title=db_content['title'],
                    content=db_content['content'],
                    chunks=[],
                    metadata=db_content['metadata'],
                    retrieved_at=datetime.fromisoformat(db_content['scraped_at']) if db_content.get('scraped_at') else datetime.now()
                )
        
        # Fall back to scraping
        if not scraped:
            logger.debug(f"Re-scraping {source_url} (not in cache or DB)...")
            try:
                scraped = self.scraper.scrape_url(source_url)
            except Exception as e:
                logger.error(f"Error scraping {source_url}: {e}")
                return self._mark_unverifiable(claims, f"Scraping error: {str(e)}")

        if not scraped or not scraped.content:
            logger.warning(f"Failed to scrape {source_url}")
            return self._mark_unverifiable(claims, "Source unavailable or empty")
        
        # Step 2: Check content length and truncate if needed
        source_text = self._prepare_source_content(scraped.content)
        
        # Step 3: Build verification prompt
        claims_json = json.dumps([
            {
                "id": i,
                "claim": claim.text,
                "type": claim.claim_type,
                "all_sources": [source_url] + (claim.additional_sources or [])
            }
            for i, claim in enumerate(claims)
        ], indent=2)
        
        # Get current date context
        current_date = self._get_current_date_context()
        source_date = scraped.retrieved_at.strftime('%B %d, %Y') if scraped.retrieved_at else "Unknown"
        
        # Build source content section with primary and additional sources
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
- Note: Some claims cite multiple sources. Verify against THIS source only; partial support is acceptable if this source supports part of the claim.

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
- For claims citing multiple sources, mark as "partial" if this source supports only part of the claim
- For absence claims (e.g., "no legislation was passed"), mark as "supported" if the source explicitly discusses the absence or confirms nothing happened
- Provide exact quotes from the source as evidence when possible
- Confidence scale:
  * 0.9-1.0 = very confident in verdict based on source
  * 0.7-0.9 = confident based on source
  * 0.5-0.7 = uncertain
  * <0.5 = very uncertain
"""
        
        # Step 4: Get verification results
        try:
            logger.debug(f"Verification prompt length: {len(prompt)} chars for {len(claims)} claims")
            
            # Use complete_json which has better retry and parsing logic
            try:
                response = self.llm_client.complete_json(
                    prompt=prompt,
                    model=self.model,
                    temperature=0.1,
                    max_tokens=2000,
                )
                logger.debug(f"Verification response keys: {list(response.keys())}")
            except Exception as json_error:
                logger.warning(f"complete_json failed: {json_error}, trying text mode fallback")
                # Fallback to text mode if JSON mode fails
                text_response = self.llm_client.complete(
                    prompt=prompt + "\n\nRETURN ONLY VALID JSON - no explanatory text before or after.",
                    model=self.model,
                    temperature=0.1,
                    max_tokens=2000,
                )
                
                if not text_response or not text_response.strip():
                    logger.error("Empty response from model")
                    return self._mark_unverifiable(claims, "Model returned empty response")
                
                logger.debug(f"Text response length: {len(text_response)}, preview: {text_response[:200]}")
                
                # Parse JSON manually
                json_str = None
                code_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text_response, re.DOTALL)
                if code_match:
                    json_str = code_match.group(1).strip()
                else:
                    obj_match = re.search(r'(\{[\s\S]*\})', text_response)
                    if obj_match:
                        json_str = obj_match.group(1).strip()
                
                if not json_str:
                    logger.error(f"No JSON found in response")
                    return self._mark_unverifiable(claims, "No JSON in response")
                
                try:
                    response = json.loads(json_str)
                except json.JSONDecodeError as e:
                    # Try truncating at last }
                    last_brace = json_str.rfind('}')
                    if last_brace > 0:
                        try:
                            response = json.loads(json_str[:last_brace+1])
                            logger.info("Parsed truncated JSON")
                        except:
                            logger.error(f"JSON parse failed: {e}")
                            return self._mark_unverifiable(claims, f"JSON parse error: {e}")
                    else:
                        logger.error(f"JSON parse failed: {e}")
                        return self._mark_unverifiable(claims, f"JSON parse error: {e}")
            
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
        
        # Handle both formats: {"verifications": [...]} and single claim object
        verifications = []
        if "verifications" in response and isinstance(response["verifications"], list):
            verifications = response["verifications"]
        elif "claim_id" in response:
            # LLM returned a single verification object instead of array
            logger.debug("LLM returned single verification object, converting to array")
            verifications = [response]
        else:
            logger.warning(f"Unexpected response format: {list(response.keys())}")
        
        for verification in verifications:
            claim_id = verification.get("claim_id")
            if claim_id is None or claim_id >= len(claims):
                logger.warning(f"Invalid claim_id in response: {claim_id}")
                continue
            
            claim = claims[claim_id]
            results.append(VerificationResult(
                claim=claim,
                verdict=verification.get("verdict", "unsupported"),
                confidence=float(verification.get("confidence", 0.5)),  # Default to 0.5 if not provided
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
