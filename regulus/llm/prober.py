"""
Regulus AI - Diagnostic Prober
==============================

Generates diagnostic probes and evaluates probe answers for the
Socratic Verification Pipeline.

When a domain criterion fails, the Prober:
1. Uses the pre-defined probe question for that criterion
2. Generates an LLM response to the probe
3. For factual claims: searches web/Wikipedia for authoritative sources
4. Evaluates whether the probe answer strengthens the domain output
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, List, Optional

from ..core.domains import (
    CriterionResult,
    DomainCheckResult,
    get_domain_criteria,
    get_domain_threshold,
    get_probe_for_criterion,
)
from .source_verifier import SourceVerifier, VerificationResult

if TYPE_CHECKING:
    from .client import LLMClient


# ============================================================
# Prompts
# ============================================================

CRITERIA_EVAL_SYSTEM = """\
You are a strict Logic Referee evaluating reasoning quality.

For each criterion, score 0-100:
- 0-30: Criterion clearly violated
- 31-60: Criterion partially met, issues present
- 61-80: Criterion met with minor gaps
- 81-100: Criterion fully satisfied

STRICT FACT-CHECKING RULES:
- If specific numbers/statistics are claimed WITHOUT a source → score 0-30
- If the answer says "approximately X" with made-up numbers → score 0-30
- If factual claims have [SOURCE] or [REASONING] or [UNCERTAIN] tags → score higher
- Admitting uncertainty ("I don't know the exact figure") is BETTER than guessing

Be strict. Absence of evidence = low score. Respond with JSON only."""

CRITERIA_EVAL_PROMPT = """\
Evaluate this domain output against its criteria.

DOMAIN: {domain} ({domain_name})
DOMAIN QUESTION: {domain_question}

DOMAIN OUTPUT:
{content}

CRITERIA TO EVALUATE:
{criteria_list}

For each criterion, respond with JSON:
{{
    "criterion_name_1": {{"score": 0-100, "reason": "brief explanation"}},
    "criterion_name_2": {{"score": 0-100, "reason": "brief explanation"}},
    ...
}}"""

PROBE_ANSWER_SYSTEM = """\
You are addressing a specific weakness in your reasoning.

A logic referee identified a gap. Answer the diagnostic probe
directly and thoroughly. Focus only on what is asked.

CRITICAL FACT-CHECKING RULES:
- If asked about factual data, you MUST provide a source or admit uncertainty
- DO NOT invent statistics, numbers, or rankings
- If you don't know exact figures, say: "I cannot verify the exact numbers"
- Use [SOURCE], [REASONING], or [UNCERTAIN] tags for factual claims
- It is BETTER to say "I don't know" than to hallucinate data

Be precise and factual. Acknowledge limitations if present."""

PROBE_ANSWER_PROMPT = """\
ORIGINAL QUESTION: {original_question}

YOUR PREVIOUS REASONING ({domain}):
{current_context}

A logic referee identified this criterion as weak:
CRITERION: {criterion}
ISSUE: {criterion_description}

DIAGNOSTIC PROBE: {probe_question}

Answer the probe directly. This will strengthen your reasoning."""


# ============================================================
# Prober Class
# ============================================================

class Prober:
    """
    Diagnostic probe generator and evaluator.

    Responsibilities:
    1. Evaluate domain outputs against criteria checklists
    2. Generate probe answers for failed criteria
    3. For factual claims: search and verify using external sources
    4. Track probe history for audit trail
    """

    def __init__(self, llm_client: "LLMClient", enable_source_lookup: bool = True) -> None:
        self.llm = llm_client
        self.enable_source_lookup = enable_source_lookup
        self.source_verifier = SourceVerifier(llm_client) if enable_source_lookup else None
        self.verification_results: List[VerificationResult] = []

    async def evaluate_domain_criteria(
        self,
        domain: str,
        domain_name: str,
        domain_question: str,
        content: str,
    ) -> DomainCheckResult:
        """
        Evaluate domain output against all criteria.

        Args:
            domain: Domain identifier (D1-D6)
            domain_name: Human-readable name
            domain_question: The guiding question for this domain
            content: The domain output to evaluate

        Returns:
            DomainCheckResult with scores and pass/fail status
        """
        criteria = get_domain_criteria(domain)
        threshold = get_domain_threshold(domain)

        # Format criteria for prompt
        criteria_list = "\n".join(
            f"- {name}: {desc}" for name, desc in criteria.items()
        )

        prompt = CRITERIA_EVAL_PROMPT.format(
            domain=domain,
            domain_name=domain_name,
            domain_question=domain_question,
            content=content,
            criteria_list=criteria_list,
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system=CRITERIA_EVAL_SYSTEM,
            )
            scores = self._parse_criteria_scores(response, list(criteria.keys()))
        except Exception:
            # Fallback: assume all criteria marginally pass
            scores = {name: {"score": 55, "reason": "Evaluation failed"} for name in criteria}

        # Build criterion results
        criterion_results: List[CriterionResult] = []
        failed_criteria: List[str] = []

        for name, desc in criteria.items():
            score_data = scores.get(name, {"score": 50, "reason": ""})
            score = score_data["score"]
            passed = score >= 60  # Criterion-level threshold

            result = CriterionResult(
                name=name,
                passed=passed,
                score=score,
                reason=score_data.get("reason", ""),
            )
            criterion_results.append(result)

            if not passed:
                failed_criteria.append(name)

        # Compute total weight (average of all scores)
        total_weight = (
            sum(c.score for c in criterion_results) // len(criterion_results)
            if criterion_results
            else 0
        )

        return DomainCheckResult(
            domain=domain,
            criteria=criterion_results,
            total_weight=total_weight,
            passed=total_weight >= threshold,
            failed_criteria=failed_criteria,
        )

    async def generate_probe_answer(
        self,
        original_question: str,
        domain: str,
        current_context: str,
        failed_criterion: str,
        probe_question: str,
    ) -> str:
        """
        Generate an answer to a diagnostic probe.

        Args:
            original_question: The user's original question
            domain: Current domain (D1-D6)
            current_context: The domain output so far
            failed_criterion: Name of the criterion that failed
            probe_question: The diagnostic probe question

        Returns:
            LLM-generated answer to the probe
        """
        # Get criterion description
        criteria = get_domain_criteria(domain)
        criterion_desc = criteria.get(failed_criterion, failed_criterion)

        prompt = PROBE_ANSWER_PROMPT.format(
            original_question=original_question,
            domain=domain,
            current_context=current_context,
            criterion=failed_criterion,
            criterion_description=criterion_desc,
            probe_question=probe_question,
        )

        response = await self.llm.generate(
            prompt=prompt,
            system=PROBE_ANSWER_SYSTEM,
        )

        return response.strip()

    async def probe_and_strengthen(
        self,
        original_question: str,
        domain: str,
        domain_name: str,
        domain_question: str,
        current_content: str,
        failed_criteria: List[str],
    ) -> tuple[str, List[tuple[str, str, str]]]:
        """
        Generate probe answers for all failed criteria and merge them.

        For `source_grounded` criterion: triggers web search and source verification.

        Args:
            original_question: User's original question
            domain: Domain identifier
            domain_name: Human-readable domain name
            domain_question: Guiding question for domain
            current_content: Current domain output
            failed_criteria: List of failed criterion names

        Returns:
            (strengthened_content, probe_records)
            - strengthened_content: Original + probe answers merged
            - probe_records: List of (criterion, probe_q, probe_a) tuples
        """
        probe_records: List[tuple[str, str, str]] = []
        additional_content: List[str] = []

        for criterion in failed_criteria:
            probe_q = get_probe_for_criterion(domain, criterion)
            if not probe_q:
                continue

            # Special handling for source_grounded: use web search
            if criterion == "source_grounded" and self.source_verifier:
                probe_a = await self._probe_with_source_lookup(
                    original_question=original_question,
                    domain=domain,
                    current_context=current_content,
                    failed_criterion=criterion,
                    probe_question=probe_q,
                )
            else:
                probe_a = await self.generate_probe_answer(
                    original_question=original_question,
                    domain=domain,
                    current_context=current_content,
                    failed_criterion=criterion,
                    probe_question=probe_q,
                )

            probe_records.append((criterion, probe_q, probe_a))
            additional_content.append(f"[{criterion} clarification] {probe_a}")

        # Merge: original content + probe answers
        if additional_content:
            strengthened = current_content + "\n\n" + "\n\n".join(additional_content)
        else:
            strengthened = current_content

        return strengthened, probe_records

    async def _probe_with_source_lookup(
        self,
        original_question: str,
        domain: str,
        current_context: str,
        failed_criterion: str,
        probe_question: str,
    ) -> str:
        """
        Generate probe answer with external source lookup.

        This method:
        1. Searches web/Wikipedia for authoritative sources
        2. Verifies factual claims against found sources
        3. Generates probe answer incorporating verified information

        Args:
            original_question: The user's original question
            domain: Current domain (D1-D6)
            current_context: The domain output so far
            failed_criterion: Name of the criterion that failed
            probe_question: The diagnostic probe question

        Returns:
            Probe answer with source verification
        """
        # Step 1: Search for sources related to the question
        from .source_verifier import search_web, search_wikipedia

        sources_text = ""
        source_urls: List[str] = []

        # Try Wikipedia first
        wiki_result = await search_wikipedia(original_question)
        if wiki_result and wiki_result.content:
            sources_text += f"\n[Wikipedia] {wiki_result.content[:500]}"
            if wiki_result.source_url:
                source_urls.append(wiki_result.source_url)

        # Web search for additional info
        web_results = await search_web(original_question)
        for result in web_results[:2]:
            if result.content:
                sources_text += f"\n[{result.source_name}] {result.content[:300]}"
                if result.source_url:
                    source_urls.append(result.source_url)

        # Step 2: Verify claims in current context
        verification_results, _ = await self.source_verifier.verify_domain_output(
            domain_output=current_context,
            original_question=original_question,
        )
        self.verification_results.extend(verification_results)

        # Step 3: Generate probe answer with source information
        criteria = get_domain_criteria(domain)
        criterion_desc = criteria.get(failed_criterion, failed_criterion)

        # Build enhanced prompt with source information
        source_section = ""
        if sources_text:
            source_section = f"\n\nEXTERNAL SOURCES FOUND:\n{sources_text}"

        verification_section = ""
        if verification_results:
            verification_section = "\n\nVERIFICATION RESULTS:\n"
            for vr in verification_results:
                if vr.verified:
                    verification_section += f"- VERIFIED: {vr.claim}\n"
                elif vr.corrected_claim:
                    verification_section += f"- CORRECTED: {vr.claim} → {vr.corrected_claim}\n"
                else:
                    verification_section += f"- UNCERTAIN: {vr.claim}\n"

        prompt = f"""\
ORIGINAL QUESTION: {original_question}

YOUR PREVIOUS REASONING ({domain}):
{current_context}

A logic referee identified this criterion as weak:
CRITERION: {failed_criterion}
ISSUE: {criterion_desc}

DIAGNOSTIC PROBE: {probe_question}
{source_section}
{verification_section}

Based on the external sources found, answer the probe.
- If sources VERIFY a claim, cite the source URL
- If sources REFUTE a claim, provide the CORRECTED information with source
- If no sources found or uncertain, explicitly state [UNCERTAIN]

DO NOT invent information. Use ONLY what the sources provide."""

        enhanced_system = PROBE_ANSWER_SYSTEM + """

IMPORTANT: You have access to external source information above.
- Always cite source URLs when making factual claims
- If sources contradict your original claim, CORRECT IT
- Format: [SOURCE: url] for verified facts"""

        response = await self.llm.generate(
            prompt=prompt,
            system=enhanced_system,
        )

        # Append source URLs
        if source_urls:
            response += "\n\n[SOURCES: " + ", ".join(source_urls[:3]) + "]"

        return response.strip()

    def _parse_criteria_scores(
        self, response: str, expected_criteria: List[str]
    ) -> dict:
        """Parse JSON scores from LLM response."""
        text = response.strip()

        # Remove markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines)
            for i, line in enumerate(lines):
                if i > 0 and line.strip().startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[start:end]).strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        # Fallback: return default scores
        return {name: {"score": 50, "reason": "Parse failed"} for name in expected_criteria}


# ============================================================
# Convenience Functions
# ============================================================

async def evaluate_and_probe(
    llm_client: "LLMClient",
    original_question: str,
    domain: str,
    domain_name: str,
    domain_question: str,
    content: str,
    max_probes: int = 2,
) -> tuple[DomainCheckResult, str, List[tuple[str, str, str]]]:
    """
    Evaluate domain and run probes if needed.

    This is the main entry point for the Socratic verification of a single domain.

    Args:
        llm_client: LLM client for generation
        original_question: User's original question
        domain: Domain identifier (D1-D6)
        domain_name: Human-readable name
        domain_question: Guiding question
        content: Domain output to evaluate
        max_probes: Maximum probe attempts

    Returns:
        (final_check_result, final_content, probe_records)
    """
    prober = Prober(llm_client)
    all_probe_records: List[tuple[str, str, str]] = []
    current_content = content

    for _ in range(max_probes):
        check_result = await prober.evaluate_domain_criteria(
            domain=domain,
            domain_name=domain_name,
            domain_question=domain_question,
            content=current_content,
        )

        if check_result.passed:
            return check_result, current_content, all_probe_records

        # Run probes for failed criteria
        current_content, probe_records = await prober.probe_and_strengthen(
            original_question=original_question,
            domain=domain,
            domain_name=domain_name,
            domain_question=domain_question,
            current_content=current_content,
            failed_criteria=check_result.failed_criteria,
        )
        all_probe_records.extend(probe_records)

        if not probe_records:
            # No probes available, can't strengthen further
            break

    # Final evaluation after all probes
    final_result = await prober.evaluate_domain_criteria(
        domain=domain,
        domain_name=domain_name,
        domain_question=domain_question,
        content=current_content,
    )

    return final_result, current_content, all_probe_records
