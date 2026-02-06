"""
Regulus AI - Orchestrator
==========================

Two orchestration modes:

1. **Original Orchestrator** (legacy):
   Query -> LLM generates D1-D6 all at once -> Zero-Gate -> Status Machine

2. **SocraticOrchestrator** (v2):
   Query -> Sequential domain generation with quality gates
   D1 -> evaluate criteria -> probe if needed -> pass threshold -> advance
   D2 -> evaluate criteria -> probe if needed -> pass threshold -> advance
   ... through D6

The Socratic pipeline ensures each domain meets quality standards before
advancing, using targeted diagnostic probes to strengthen weak criteria.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .core.types import (
    Domain, Status, Policy, Node, GateSignals, RawScores,
    Diagnostic, VerificationResult,
)
from .core.zero_gate import compute_gate, get_diagnostic_code, get_diagnostic_reason
from .core.weight import compute_final_weight
from .core.status_machine import (
    assign_all_statuses, create_diagnostic,
    find_max_entity, find_secondary_max,
    find_historical_max, build_entity_history,
)
from .core.optimizer import (
    TrisectionOptimizer, TrisectionState,
    SocraticTrisection, SocraticTrisectionState,
)
from .core.domains import (
    DOMAIN_ORDER, DOMAIN_DEFINITIONS,
    DomainPassRecord, ProbeRecord,
    get_domain_def, get_domain_name, get_domain_question,
    get_domain_threshold, get_domain_criteria,
    is_answer_domain, is_qualifier_domain,
    compute_confidence_score, get_confidence_level,
)
from .llm.client import LLMClient
from .llm.sensor import HeuristicSignalExtractor, LLMSignalExtractor
from .llm.prober import Prober
from .llm.source_verifier import (
    SourceVerifier,
    search_all_sources,
    search_web,
    search_wikipedia,
    format_source_citation,
    SERP_API_KEY,
    BRAVE_API_KEY,
    GOOGLE_API_KEY,
)
from .prompts.correction import get_fix_prompt

logger = logging.getLogger(__name__)


# ============================================================
# Domain mapping
# ============================================================

DOMAIN_INDEX: dict[str, int] = {
    "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5, "D6": 6,
}


# ============================================================
# System prompts
# ============================================================

REASONING_SYSTEM_PROMPT = """\
You are a structured reasoning engine following the Theory of Systems framework.

Given a query, produce reasoning in exactly 6 steps following these domains in order:

D1 (Recognition): What is actually here? Identify the core claim, question, or object.
D2 (Clarification): What exactly is this? Define key terms and boundaries precisely.
D3 (Framework): How do we connect this? Choose the evaluation criteria or model.
D4 (Comparison): How does it process? Apply the framework, make relevant comparisons.
D5 (Inference): What follows? Draw conclusions that logically follow from the analysis.
D6 (Reflection): Where doesn't it work? Acknowledge limitations, edge cases, caveats.

Each step MUST contain:
- An identifiable Element (E): a concrete object, claim, or concept
- A defined Role (R): the functional purpose or relationship
- A connecting Rule: the logical principle binding the reasoning

Respond in JSON format only:
{
    "steps": [
        {"domain": "D1", "content": "..."},
        {"domain": "D2", "content": "..."},
        {"domain": "D3", "content": "..."},
        {"domain": "D4", "content": "..."},
        {"domain": "D5", "content": "..."},
        {"domain": "D6", "content": "..."}
    ]
}"""

CORRECTION_TEMPLATE = """\
The following reasoning step failed structural verification:

Step: {step_content}

Failure: {fix_prompt}

Original query: {query}
Current domain: {domain}

Please rewrite this reasoning step to fix the structural issue. \
Maintain the same domain ({domain}) and address the specific failure above.

Each step must contain:
- Element (E): A concrete, identifiable object or claim
- Role (R): A defined functional purpose or relationship
- Rule: A logical principle connecting the reasoning

Respond with just the corrected reasoning text, no JSON wrapper."""

COMPLETE_INFERENCE_PROMPT = """You have performed a thorough analysis of a question.
Here is your verified reasoning chain:

{verified_chain}

Original question: {question}
Confidence level: {confidence_level}

Now provide a clear, direct, natural-language answer to the question.
- Be concise and informative
- Include key facts from your analysis
- Do NOT use Element/Role/Rule format
- Do NOT include meta-commentary about your reasoning process
- Do NOT hedge or say "I cannot verify" if you found the answer in your reasoning
- If confidence is "unconfirmed", state clearly that the answer could not be verified
- Otherwise, state the answer directly and confidently
- At the very end, on a new line, add confidence indicator

Format for the last line:
- If unconfirmed: "⚠️ This answer could not be verified through reliable sources."
- If low confidence: "Confidence: low"
- If medium confidence: "Confidence: medium"
- If high confidence: "Confidence: high"
- If very high confidence: "Confidence: very high"
"""


# ============================================================
# Data types
# ============================================================

@dataclass
class CorrectionAttempt:
    """Record of a single correction attempt for a reasoning step."""
    step_index: int
    attempt: int
    original_content: str
    diagnostic_code: str
    fix_prompt: str
    corrected_content: str | None = None
    success: bool = False


@dataclass
class VerifiedResponse:
    """Final verified response with full diagnostics."""
    query: str
    result: VerificationResult
    reasoning_steps: list[dict[str, str]]
    corrections: list[CorrectionAttempt] = field(default_factory=list)
    trisection: "TrisectionState | None" = None
    final_answer: str | None = None  # Clean natural-language answer

    @property
    def is_valid(self) -> bool:
        """True if a PrimaryMax was found."""
        return self.result.primary_max is not None

    @property
    def total_corrections(self) -> int:
        return len(self.corrections)

    @property
    def primary_answer(self) -> str | None:
        """Content of the PrimaryMax node, if any."""
        if self.result.primary_max:
            return self.result.primary_max.content
        return None

    @property
    def alternatives(self) -> list[str]:
        """Content of SecondaryMax nodes."""
        return [n.content for n in self.result.secondary_max]


# ============================================================
# Orchestrator
# ============================================================

class Orchestrator:
    """
    Main control loop for Regulus AI verification.

    Pipeline:
        Query -> LLM (D1-D6 reasoning) -> Sensor (signal extraction)
            -> Zero-Gate check -> [correction loop if Gate=0]
            -> Status Machine -> VerifiedResponse

    Args:
        llm_client: LLM client for generation (and optionally sensor)
        policy: Tie-breaking policy for Status Machine
        max_corrections: Maximum correction attempts per failed step
        use_llm_sensor: If True, use LLM referee for signal extraction;
                        if False, use heuristic extractor
        use_trisection: If True, run trisection optimizer before status assignment
    """

    def __init__(
        self,
        llm_client: LLMClient,
        policy: Policy = Policy.LEGACY_PRIORITY,
        max_corrections: int = 3,
        use_llm_sensor: bool = True,
        use_trisection: bool = False,
    ):
        self.llm = llm_client
        self.policy = policy
        self.max_corrections = max_corrections
        self.use_llm_sensor = use_llm_sensor
        self.use_trisection = use_trisection
        self.heuristic = HeuristicSignalExtractor()
        self.llm_sensor: LLMSignalExtractor | None = (
            LLMSignalExtractor(llm_client) if use_llm_sensor else None
        )

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    async def process_query(self, query: str) -> VerifiedResponse:
        """
        Run the full verification cycle on a user query.

        1. Generate D1-D6 reasoning chain via LLM
        2. For each step: extract signals -> Zero-Gate check
        3. If Gate=0: generate fix prompt, retry (max N times)
        4. (Optional) Trisection narrowing of candidate set
        5. Assign statuses via Status Machine
        6. Return VerifiedResponse with PrimaryMax path
        """
        # Step 1: Generate reasoning chain
        steps = await self._generate_reasoning(query)
        corrections: list[CorrectionAttempt] = []

        # Step 2: Verify each step (with correction loop)
        nodes: list[Node] = []
        parent_domain: int | None = None

        for i, step in enumerate(steps):
            domain_key = step["domain"]
            content = step["content"]
            domain_idx = DOMAIN_INDEX.get(domain_key, i + 1)

            node, step_corrections = await self._verify_step(
                step_index=i,
                content=content,
                domain_idx=domain_idx,
                domain_key=domain_key,
                parent_domain=parent_domain,
                query=query,
            )

            if step_corrections:
                corrections.extend(step_corrections)
                last = step_corrections[-1]
                if last.success and last.corrected_content:
                    steps[i] = {"domain": domain_key, "content": last.corrected_content}

            nodes.append(node)
            parent_domain = node.raw_scores.current_domain

        # Step 3 (optional): Trisection narrowing
        trisection_state: TrisectionState | None = None
        if self.use_trisection:
            optimizer = TrisectionOptimizer(policy=self.policy)
            trisection_state = optimizer.optimize(nodes)
            logger.info(
                "Trisection: %d iterations, %d candidates remaining",
                trisection_state.iterations, len(trisection_state.candidates),
            )

        # Step 4: Assign statuses via Status Machine
        nodes = assign_all_statuses(nodes, self.policy)

        # Step 5: Generate diagnostics
        parent_domains = self._build_parent_domains(nodes)
        diagnostics: list[Diagnostic] = []
        for node in nodes:
            code = get_diagnostic_code(node, parent_domains.get(node.node_id))
            reason = get_diagnostic_reason(code)
            diag = create_diagnostic(node, code, reason)
            diagnostics.append(diag)

        # Step 6: Build VerificationResult
        primary = find_max_entity(nodes, self.policy)
        secondary = find_secondary_max(nodes, primary, self.policy) if primary else []
        entity_history = build_entity_history(nodes)
        historical = find_historical_max(nodes, entity_history)
        invalid_count = sum(1 for n in nodes if n.status == Status.INVALID)

        result = VerificationResult(
            nodes=nodes,
            diagnostics=diagnostics,
            primary_max=primary,
            secondary_max=secondary,
            historical_max=historical,
            invalid_count=invalid_count,
        )

        # Step 7: Generate clean final answer (only if valid PrimaryMax)
        final_answer = None
        if primary is not None:
            try:
                final_answer = await self._generate_final_answer(query, steps)
            except Exception as e:
                logger.warning("Failed to generate final answer: %s", e)

        return VerifiedResponse(
            query=query,
            result=result,
            reasoning_steps=steps,
            corrections=corrections,
            trisection=trisection_state,
            final_answer=final_answer,
        )

    # ----------------------------------------------------------
    # Reasoning generation
    # ----------------------------------------------------------

    async def _generate_reasoning(self, query: str) -> list[dict[str, str]]:
        """Ask LLM to generate D1-D6 reasoning steps."""
        response = await self.llm.generate(
            prompt=f"Query: {query}",
            system=REASONING_SYSTEM_PROMPT,
        )
        return self._parse_reasoning_response(response)

    async def _generate_final_answer(
        self,
        query: str,
        steps: list[dict[str, str]],
    ) -> str:
        """Generate a clean, natural-language final answer from verified chain."""
        # Build verified chain summary (D1-D6 content without ERR format cruft)
        chain_parts = []
        for step in steps:
            domain = step.get("domain", "?")
            content = step.get("content", "")
            # Simple cleaning of content for the summary
            chain_parts.append(f"{domain}: {content}")

        verified_chain = "\n\n".join(chain_parts)

        prompt = COMPLETE_INFERENCE_PROMPT.format(
            verified_chain=verified_chain,
            question=query,
        )

        response = await self.llm.generate(prompt=prompt)
        return response.strip()

    # ----------------------------------------------------------
    # Step verification with correction loop
    # ----------------------------------------------------------

    async def _verify_step(
        self,
        step_index: int,
        content: str,
        domain_idx: int,
        domain_key: str,
        parent_domain: int | None,
        query: str,
    ) -> tuple[Node, list[CorrectionAttempt]]:
        """
        Verify a single reasoning step, retrying on gate failure.

        Returns:
            (verified_node, list_of_correction_attempts)
        """
        corrections: list[CorrectionAttempt] = []
        current_content = content
        node: Node | None = None

        for attempt in range(self.max_corrections + 1):
            # Extract signals
            signals = await self._extract_signals(
                current_content, parent_domain, domain_idx,
            )

            # Build node
            node = Node(
                node_id=f"step_{step_index}",
                parent_id=f"step_{step_index - 1}" if step_index > 0 else None,
                entity_id=f"E_{step_index}",
                content=current_content,
                legacy_idx=step_index,
                gate_signals=GateSignals(**signals["gate_signals"]),
                raw_scores=RawScores(**signals["raw_scores"]),
            )

            # Compute gate and weight
            node.gate = compute_gate(node, parent_domain)
            node.final_weight = compute_final_weight(node, node.gate)

            # Gate passed -> done
            if node.gate.is_valid:
                if attempt > 0 and corrections:
                    corrections[-1].success = True
                    corrections[-1].corrected_content = current_content
                return node, corrections

            # Gate failed -> attempt correction (if budget remains)
            if attempt < self.max_corrections:
                diag_code = get_diagnostic_code(node, parent_domain) or "UNKNOWN"
                fix_prompt_text = get_fix_prompt(diag_code)

                correction = CorrectionAttempt(
                    step_index=step_index,
                    attempt=attempt + 1,
                    original_content=current_content,
                    diagnostic_code=diag_code,
                    fix_prompt=fix_prompt_text,
                )
                corrections.append(correction)

                logger.info(
                    "Step %d failed gate (%s), correction attempt %d/%d",
                    step_index, diag_code, attempt + 1, self.max_corrections,
                )

                corrected = await self._correct_step(
                    current_content, fix_prompt_text, query, domain_key,
                )
                if corrected:
                    current_content = corrected
                else:
                    break  # LLM couldn't produce a fix

        # Exhausted corrections — return node as-is (will be Invalid)
        assert node is not None
        return node, corrections

    # ----------------------------------------------------------
    # Signal extraction
    # ----------------------------------------------------------

    async def _extract_signals(
        self,
        text: str,
        parent_domain: int | None,
        expected_domain: int,
    ) -> dict[str, Any]:
        """Extract structural signals from a reasoning step."""
        if self.llm_sensor is not None:
            try:
                signals = await self.llm_sensor.extract_signals(text, parent_domain)
                # Ensure domain matches expected when LLM agrees
                if signals["raw_scores"]["current_domain"] == 0:
                    signals["raw_scores"]["current_domain"] = expected_domain
                return signals
            except Exception as e:
                logger.warning("LLM sensor failed, using heuristics: %s", e)

        # Heuristic fallback
        signals = self.heuristic.extract_signals(text, parent_domain)
        signals["raw_scores"]["current_domain"] = expected_domain
        return signals

    # ----------------------------------------------------------
    # Correction
    # ----------------------------------------------------------

    async def _correct_step(
        self,
        step_content: str,
        fix_prompt: str,
        query: str,
        domain_key: str,
    ) -> str | None:
        """Ask LLM to rewrite a failed reasoning step."""
        prompt = CORRECTION_TEMPLATE.format(
            step_content=step_content,
            fix_prompt=fix_prompt,
            query=query,
            domain=domain_key,
        )

        try:
            response = await self.llm.generate(prompt=prompt)
            return response.strip() if response else None
        except Exception as e:
            logger.warning("Correction LLM call failed: %s", e)
            return None

    # ----------------------------------------------------------
    # Parsing helpers
    # ----------------------------------------------------------

    def _parse_reasoning_response(self, response: str) -> list[dict[str, str]]:
        """Parse LLM reasoning response into a list of domain steps."""
        parsed = _parse_json_response(response)

        if "steps" in parsed and isinstance(parsed["steps"], list):
            steps: list[dict[str, str]] = []
            for s in parsed["steps"]:
                if isinstance(s, dict) and "domain" in s and "content" in s:
                    content = s["content"]
                    # Handle structured content (GPT-4o sometimes returns nested dicts)
                    if isinstance(content, dict):
                        content = " ".join(f"{k}: {v}" for k, v in content.items())
                    steps.append({"domain": s["domain"], "content": str(content)})
            if steps:
                return steps

        # Fallback: try to find D1-D6 markers in freeform text
        return _parse_freeform_reasoning(response)

    @staticmethod
    def _build_parent_domains(nodes: list[Node]) -> dict[str, int | None]:
        """Build mapping from node_id to parent's domain index."""
        node_map = {n.node_id: n for n in nodes}
        parent_domains: dict[str, int | None] = {}
        for node in nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                parent_domains[node.node_id] = parent.raw_scores.current_domain
            else:
                parent_domains[node.node_id] = None
        return parent_domains


# ============================================================
# Module-level parsing helpers
# ============================================================

def _parse_json_response(response: str) -> dict[str, Any]:
    """Extract JSON from an LLM response, handling markdown code blocks."""
    text = response.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end]).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { ... last }
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse JSON from LLM response")
    return {}


def _parse_freeform_reasoning(text: str) -> list[dict[str, str]]:
    """Parse unstructured reasoning text by finding D1-D6 markers."""
    pattern = r"(D[1-6])\s*[\(:](.+?)(?=D[1-6]\s*[\(:]|$)"
    matches = re.findall(pattern, text, re.DOTALL)

    if matches:
        return [{"domain": m[0], "content": m[1].strip()} for m in matches]

    # Last resort: entire response as a single D1 step
    return [{"domain": "D1", "content": text.strip()}]


# ============================================================
# Socratic Pipeline v2 — Prompts
# ============================================================

SOCRATIC_DOMAIN_PROMPT = """\
You are performing structured reasoning step by step.

ORIGINAL QUESTION: {question}

{context_section}

Now complete domain {domain} ({domain_name}).

GUIDING QUESTION: {domain_question}

CRITERIA YOU MUST SATISFY:
{criteria_list}

=== DOMAIN-SPECIFIC INSTRUCTIONS ===

IF D1 (Recognition):
1. CLASSIFY the prompt TYPE: [FACT], [REASONING], [OPINION], [QUESTION], or [COMMAND]
2. Apply ERR methodology to KEY words:
   - WORD: [E: element] [R: role] [RULE: governing principle]
3. If TYPE is [FACT], tag: [FACTUAL DATA REQUIRED: UNCONFIRMED]
   - List each specific fact that needs verification

IF D2 (Clarification):
1. VALIDATE D1 outputs: [D1 VALIDATED] or [D1 CORRECTED: ...]
2. Assess certainty: [CERTAINTY: X%]
   - If < 90%, list clarifying questions needed
3. For UNCONFIRMED facts from D1, assign status:
   - [CONFIRMED] - found and verified with source
   - [UPDATED] - original was wrong, correct data found
   - [UNCONFIRMED] - could not verify

=== GENERAL RULES ===
- NEVER invent statistics or specific numbers
- Use provided SOURCE data when available
- It is BETTER to say "I don't know" than to guess

Provide your reasoning for this domain. Be thorough and precise.
Structure your response with:
- Element (E): The concrete object, claim, or concept you're addressing
- Role (R): Its functional purpose in the reasoning
- Rule: The logical principle that governs this step

Respond with just the domain content, no JSON wrapper."""

SOCRATIC_CONTEXT_TEMPLATE = """\
PREVIOUS REASONING:
{previous_domains}
"""

SOCRATIC_FINAL_ANSWER_PROMPT = """\
You have completed a thorough analysis of a question. Now synthesize a clean final answer.

QUESTION: {question}
Confidence level: {confidence_level}

YOUR REASONING (internal analysis):
{full_chain}

---

Write a FINAL ANSWER that:
1. Directly answers the question in plain English
2. Includes the key conclusion with supporting facts
3. Cites sources if available (e.g., "According to USDA data...")
4. Is concise but complete (2-4 paragraphs max)

DO NOT:
- Use Element/Role/Rule format
- Use [E:], [R:], [RULE:] tags
- Include domain labels like [D1], [D5]
- Add meta-commentary about the reasoning process
- Use academic/technical structure headers
- Hedge or say "I cannot verify" if you found the answer in your reasoning

If confidence is "unconfirmed", state clearly that the answer could not be verified.
Otherwise, state the answer directly and confidently.

At the very end, on a new line, add confidence indicator:
- If unconfirmed: "⚠️ This answer could not be verified through reliable sources."
- If low confidence: "Confidence: low"
- If medium confidence: "Confidence: medium"
- If high confidence: "Confidence: high"
- If very high confidence: "Confidence: very high"

FINAL ANSWER:"""


# ============================================================
# Socratic Pipeline v2 — Response Types
# ============================================================

@dataclass
class SocraticResponse:
    """Response from the Socratic verification pipeline."""
    query: str
    result: VerificationResult
    reasoning_steps: list[dict[str, str]]
    domain_records: list[DomainPassRecord] = field(default_factory=list)
    final_answer: str | None = None
    # Trisection tracking (v2)
    trisection_state: SocraticTrisectionState | None = None
    branches_explored: int = 1
    branch_weights: dict[int, float] | None = None

    @property
    def is_valid(self) -> bool:
        """True if D5 (inference) passed and a PrimaryMax was found."""
        return self.result.primary_max is not None

    @property
    def total_probes(self) -> int:
        """Total number of probes used across all domains."""
        return sum(len(r.probes_used) for r in self.domain_records)

    @property
    def used_trisection(self) -> bool:
        """True if trisection was used during processing."""
        return (
            self.trisection_state is not None
            and self.trisection_state.total_iterations > 0
        )

    @property
    def trisection_iterations(self) -> int:
        """Total trisection iterations across all levels."""
        if self.trisection_state:
            return self.trisection_state.total_iterations
        return 0

    @property
    def primary_answer(self) -> str | None:
        """Content of the PrimaryMax node, if any."""
        if self.result.primary_max:
            return self.result.primary_max.content
        return None

    @property
    def corrections(self) -> list:
        """List of corrections (probes used) for exporter compatibility."""
        # In Socratic pipeline, probes are the equivalent of corrections
        return []  # Socratic uses probes, not corrections

    @property
    def total_corrections(self) -> int:
        """Total corrections count (probes used) for exporter compatibility."""
        return self.total_probes

    @property
    def d5_content(self) -> str | None:
        """Content of D5 (inference) domain."""
        for step in self.reasoning_steps:
            if step.get("domain") == "D5":
                return step.get("content")
        return None

    @property
    def d6_content(self) -> str | None:
        """Content of D6 (reflection) domain."""
        for step in self.reasoning_steps:
            if step.get("domain") == "D6":
                return step.get("content")
        return None

    @property
    def confidence_score(self) -> int:
        """Compute confidence score (0-100) from domain records."""
        return compute_confidence_score(self.domain_records)

    @property
    def confidence_level(self) -> str:
        """Human-readable confidence level."""
        return get_confidence_level(self.confidence_score)


# ============================================================
# Socratic Pipeline v2 — Orchestrator
# ============================================================

class SocraticOrchestrator:
    """
    Socratic Verification Pipeline v2.

    Sequential domain processing with quality gates:
    1. Generate D1 output
    2. Evaluate D1 against criteria checklist
    3. If below threshold: run diagnostic probes, re-evaluate
    4. Advance to D2 when D1 passes (or max probes exhausted)
    5. Continue through D6
    6. Generate final answer from verified chain

    Two-level trisection integration:
    - Level 1 (intra-domain): When multiple probe versions exist, trisection
      selects the structurally strongest, not just the last one.
    - Level 2 (cross-branch): When D3 generates multiple frameworks, each
      spawns a complete D4→D5→D6 chain. Trisection selects the best branch.

    Args:
        llm_client: LLM client for generation and probing
        policy: Tie-breaking policy for Status Machine
        use_llm_sensor: Use LLM referee for gate signal extraction
        use_trisection: Enable trisection for intra-domain version selection
        use_branching: Enable D3 branching (generates multiple frameworks)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        policy: Policy = Policy.LEGACY_PRIORITY,
        use_llm_sensor: bool = True,
        use_trisection: bool = True,
        use_branching: bool = False,
    ):
        self.llm = llm_client
        self.policy = policy
        self.use_llm_sensor = use_llm_sensor
        self.use_trisection = use_trisection
        self.use_branching = use_branching
        self.heuristic = HeuristicSignalExtractor()
        self.llm_sensor: LLMSignalExtractor | None = (
            LLMSignalExtractor(llm_client) if use_llm_sensor else None
        )
        self.prober = Prober(llm_client, enable_source_lookup=True)
        self.source_verifier = SourceVerifier(llm_client)
        self.trisection: SocraticTrisection | None = (
            SocraticTrisection(policy=policy) if use_trisection else None
        )
        # Note: factual_data_required and source_context are now local to process_query
        # to avoid race conditions when processing multiple queries in parallel

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    async def process_query(self, query: str) -> SocraticResponse:
        """
        Run the Socratic verification pipeline.

        Processes domains D1-D6 sequentially, with quality gates,
        diagnostic probes, and trisection-based version selection.
        """
        # Reset trisection state for new query
        if self.trisection:
            self.trisection.reset()

        domain_records: list[DomainPassRecord] = []
        reasoning_steps: list[dict[str, str]] = []
        accumulated_context: list[str] = []
        all_version_nodes: dict[str, list[Node]] = {}  # domain → all versions

        # LOCAL source lookup flags (not instance vars - avoids race condition in parallel)
        factual_data_required = False
        source_context = ""

        # Process each domain sequentially
        for domain in DOMAIN_ORDER:
            domain_def = get_domain_def(domain)
            domain_name = domain_def.get("name", domain)
            domain_question = domain_def.get("question", "")
            max_probes = domain_def.get("max_probes", 2)

            # Generate initial domain content
            content = await self._generate_domain(
                query=query,
                domain=domain,
                domain_name=domain_name,
                domain_question=domain_question,
                context=accumulated_context,
            )

            # D1 check: detect if factual data is required
            content_upper = content.upper()
            if domain == "D1" and (
                "[FACTUAL DATA REQUIRED" in content_upper or
                "TYPE: [FACT]" in content_upper or
                "[FACT]" in content_upper
            ):
                factual_data_required = True

                # Classify fact subtype from D1 content and query
                fact_subtype = self._classify_fact_subtype(query, content)
                logger.info("D1 detected factual question — subtype: %s", fact_subtype)

                if fact_subtype in ("statistic", "ranking", "quantity", "current_state"):
                    # Statistics, rankings, quantities, current holders —
                    # Model is unreliable on these. ALWAYS search.
                    logger.info("Subtype %s — forcing source search", fact_subtype)
                    source_context = await self._search_sources_for_query(query)
                elif fact_subtype in ("date", "definition"):
                    # Dates and definitions — model usually knows these.
                    # Skip search, let D2-D5 reasoning handle it.
                    logger.info("Subtype %s — skipping search, model reliable", fact_subtype)
                    source_context = ""
                else:
                    # "name", "event", "unknown" — search to be safe
                    logger.info("Subtype %s — searching for safety", fact_subtype)
                    source_context = await self._search_sources_for_query(query)

            # D2: inject source context if factual data was required
            if domain == "D2" and factual_data_required and source_context:
                content = content + "\n\n" + source_context
                logger.info("D2 enhanced with source context (%d chars)", len(source_context))

            # Evaluate and probe, collecting ALL versions for trisection
            record = DomainPassRecord(domain=domain, attempts=1, content=content)
            current_content = content
            version_contents: list[str] = [content]  # Track all versions

            for probe_attempt in range(max_probes + 1):
                # Evaluate against criteria
                check_result = await self.prober.evaluate_domain_criteria(
                    domain=domain,
                    domain_name=domain_name,
                    domain_question=domain_question,
                    content=current_content,
                )

                if check_result.passed:
                    record.passed = True
                    record.final_weight = check_result.total_weight
                    record.content = current_content
                    break

                # Run probes if we have attempts left
                if probe_attempt < max_probes and check_result.failed_criteria:
                    record.attempts += 1

                    strengthened, probe_list = await self.prober.probe_and_strengthen(
                        original_question=query,
                        domain=domain,
                        domain_name=domain_name,
                        domain_question=domain_question,
                        current_content=current_content,
                        failed_criteria=check_result.failed_criteria,
                    )

                    # Record probes
                    for crit, probe_q, probe_a in probe_list:
                        probe_rec = ProbeRecord(
                            criterion=crit,
                            probe_question=probe_q,
                            probe_answer=probe_a,
                            weight_before=check_result.total_weight,
                            weight_after=0,
                        )
                        record.probes_used.append(probe_rec)

                    current_content = strengthened
                    version_contents.append(strengthened)

                    if not probe_list:
                        break

            # Build Node objects for ALL versions (for trisection)
            domain_idx = DOMAIN_INDEX.get(domain, 1)
            parent_domain = None
            if reasoning_steps:
                prev_domain = reasoning_steps[-1]["domain"]
                parent_domain = DOMAIN_INDEX.get(prev_domain)

            version_nodes: list[Node] = []
            for v_idx, v_content in enumerate(version_contents):
                signals = await self._extract_signals(v_content, parent_domain, domain_idx)
                node = Node(
                    node_id=f"{domain}_v{v_idx}",
                    parent_id=reasoning_steps[-1]["domain"] if reasoning_steps else None,
                    entity_id=f"E_{domain}_{v_idx}",
                    content=v_content,
                    legacy_idx=v_idx,
                    gate_signals=GateSignals(**signals["gate_signals"]),
                    raw_scores=RawScores(**signals["raw_scores"]),
                )
                node.gate = compute_gate(node, parent_domain)
                node.final_weight = compute_final_weight(node, node.gate)
                version_nodes.append(node)

            all_version_nodes[domain] = version_nodes

            # TRISECTION: Select best version (Level 1)
            if self.trisection and len(version_nodes) >= 2:
                selected_node = self.trisection.select_best_version(version_nodes, domain)
                selected_content = selected_node.content
                record.final_weight = selected_node.final_weight
                record.passed = selected_node.gate and selected_node.gate.is_valid
                logger.info(
                    "Domain %s: trisection selected v%d from %d versions",
                    domain, version_nodes.index(selected_node), len(version_nodes),
                )
            else:
                # No trisection: use last content
                selected_content = current_content
                # Final evaluation for weight
                final_check = await self.prober.evaluate_domain_criteria(
                    domain=domain,
                    domain_name=domain_name,
                    domain_question=domain_question,
                    content=current_content,
                )
                record.final_weight = final_check.total_weight
                record.passed = final_check.passed

            record.content = selected_content

            # Update probe weight_after values
            for probe_rec in record.probes_used:
                probe_rec.weight_after = record.final_weight

            domain_records.append(record)
            reasoning_steps.append({"domain": domain, "content": selected_content})
            accumulated_context.append(f"[{domain}] {selected_content}")

            logger.info(
                "Domain %s: weight=%d, passed=%s, probes=%d, versions=%d",
                domain, record.final_weight, record.passed,
                len(record.probes_used), len(version_nodes),
            )

        # Build final verification result with Zero-Gate checking
        nodes = await self._build_nodes_from_steps(reasoning_steps)
        nodes = assign_all_statuses(nodes, self.policy)

        # Generate diagnostics
        parent_domains = self._build_parent_domains(nodes)
        diagnostics: list[Diagnostic] = []
        for node in nodes:
            code = get_diagnostic_code(node, parent_domains.get(node.node_id))
            reason = get_diagnostic_reason(code)
            diag = create_diagnostic(node, code, reason)
            diagnostics.append(diag)

        # Find max entities
        primary = find_max_entity(nodes, self.policy)
        secondary = find_secondary_max(nodes, primary, self.policy) if primary else []
        entity_history = build_entity_history(nodes)
        historical = find_historical_max(nodes, entity_history)
        invalid_count = sum(1 for n in nodes if n.status == Status.INVALID)

        result = VerificationResult(
            nodes=nodes,
            diagnostics=diagnostics,
            primary_max=primary,
            secondary_max=secondary,
            historical_max=historical,
            invalid_count=invalid_count,
        )

        # Generate final answer if we have D5 content (always synthesize)
        final_answer = None
        d5_record = next((r for r in domain_records if r.domain == "D5"), None)
        if d5_record:
            try:
                conf_score = compute_confidence_score(domain_records)
                conf_level = get_confidence_level(conf_score)
                final_answer = await self._generate_final_answer(
                    query, reasoning_steps, confidence_level=conf_level
                )
            except Exception as e:
                logger.warning("Failed to generate final answer: %s", e)

        # Get trisection state
        trisection_state = self.trisection.finalize() if self.trisection else None

        return SocraticResponse(
            query=query,
            result=result,
            reasoning_steps=reasoning_steps,
            domain_records=domain_records,
            final_answer=final_answer,
            trisection_state=trisection_state,
            branches_explored=trisection_state.branches_explored if trisection_state else 1,
        )

    # ----------------------------------------------------------
    # Domain generation
    # ----------------------------------------------------------

    async def _generate_domain(
        self,
        query: str,
        domain: str,
        domain_name: str,
        domain_question: str,
        context: list[str],
    ) -> str:
        """Generate content for a single domain."""
        # Build context section
        if context:
            context_section = SOCRATIC_CONTEXT_TEMPLATE.format(
                previous_domains="\n\n".join(context)
            )
        else:
            context_section = ""

        # Build criteria list
        criteria = get_domain_criteria(domain)
        criteria_list = "\n".join(f"- {name}: {desc}" for name, desc in criteria.items())

        prompt = SOCRATIC_DOMAIN_PROMPT.format(
            question=query,
            context_section=context_section,
            domain=domain,
            domain_name=domain_name,
            domain_question=domain_question,
            criteria_list=criteria_list,
        )

        response = await self.llm.generate(prompt=prompt)
        return response.strip()

    async def _generate_final_answer(
        self,
        query: str,
        steps: list[dict[str, str]],
        confidence_level: str = "medium confidence",
    ) -> str:
        """Generate clean final answer from verified chain."""
        chain_parts = []
        for step in steps:
            domain = step.get("domain", "?")
            content = step.get("content", "")
            chain_parts.append(f"{domain}: {content}")

        full_chain = "\n\n".join(chain_parts)

        prompt = SOCRATIC_FINAL_ANSWER_PROMPT.format(
            question=query,
            full_chain=full_chain,
            confidence_level=confidence_level,
        )

        response = await self.llm.generate(prompt=prompt)
        return response.strip()

    # ----------------------------------------------------------
    # Proactive source lookup for factual questions
    # ----------------------------------------------------------

    def _classify_fact_subtype(self, query: str, d1_content: str) -> str:
        """
        Classify what KIND of factual data is needed — no LLM call, pure heuristics.

        Returns one of:
        - "statistic"     — numbers, percentages, amounts, production data
        - "ranking"       — most/least/first/last/top/biggest/smallest
        - "quantity"      — how many, how much, population, revenue
        - "current_state" — who is the current..., what is the current...
        - "date"          — when did, what year, what date
        - "name"          — who is, what is the name of, birth name
        - "definition"    — what is, what does X mean
        - "event"         — what happened, did X happen
        - "unknown"       — can't classify

        Heuristic-only: fast, deterministic, no API cost.
        """
        q = query.lower().strip()
        content_lower = d1_content.lower()

        # RANKING indicators — ALWAYS unreliable
        ranking_keywords = [
            "most", "least", "largest", "smallest", "biggest",
            "highest", "lowest", "top", "best", "worst",
            "first", "last", "oldest", "newest", "youngest",
            "leading", "primary", "dominant", "major",
            "number one", "#1", "ranks", "ranking",
        ]
        if any(kw in q for kw in ranking_keywords):
            return "ranking"

        # STATISTIC indicators — ALWAYS unreliable
        statistic_keywords = [
            "how much", "how many", "percentage", "percent",
            "production", "produces", "output", "volume",
            "revenue", "gdp", "population", "rate",
            "average", "median", "total", "annual",
            "per capita", "growth", "decline", "increase",
            "statistics", "data", "figures", "numbers",
        ]
        if any(kw in q for kw in statistic_keywords):
            return "statistic"

        # QUANTITY — close to statistic
        quantity_keywords = [
            "how many", "how much", "count", "number of",
            "amount", "quantity", "size of", "length of",
            "weight of", "height of", "distance",
        ]
        if any(kw in q for kw in quantity_keywords):
            return "quantity"

        # CURRENT STATE — changes over time, unreliable
        current_keywords = [
            "current", "currently", "now", "today",
            "who is the", "what is the current",
            "as of", "present", "latest", "recent",
            "still", "anymore",
        ]
        if any(kw in q for kw in current_keywords):
            return "current_state"

        # DATE — model usually reliable
        date_keywords = [
            "when did", "when was", "what year",
            "what date", "born in", "died in",
            "founded in", "established in",
            "which year", "which century",
        ]
        if any(kw in q for kw in date_keywords):
            return "date"

        # DEFINITION — model reliable
        definition_keywords = [
            "what is a ", "what is an ", "what does",
            "define ", "definition of", "meaning of",
            "what are ", "explain what",
        ]
        if any(kw in q for kw in definition_keywords):
            return "definition"

        # NAME — sometimes reliable, sometimes not
        name_keywords = [
            "birth name", "real name", "full name",
            "maiden name", "original name", "stage name",
            "who wrote", "who created", "who invented",
            "who discovered", "who founded", "who directed",
            "named after", "what is the name",
        ]
        if any(kw in q for kw in name_keywords):
            return "name"

        # EVENT
        event_keywords = [
            "what happened", "did it", "has it",
            "was there", "were there",
        ]
        if any(kw in q for kw in event_keywords):
            return "event"

        # Check D1 content for additional signals
        if any(kw in content_lower for kw in ["statistic", "ranking", "data needed", "numbers"]):
            return "statistic"
        if any(kw in content_lower for kw in ["current holder", "current state", "may have changed"]):
            return "current_state"

        return "unknown"

    async def _search_sources_for_query(self, query: str) -> str:
        """
        Search external sources for factual information.

        Called when D1 detects [FACTUAL DATA REQUIRED].
        Returns formatted source context to inject into D2.

        Uses priority: Brave Search > Google > Wikipedia > DuckDuckGo
        """
        sources_parts: list[str] = []

        # Log which search APIs are available
        if SERP_API_KEY:
            logger.info("Using SerpAPI (Google Search)")
        elif BRAVE_API_KEY:
            logger.info("Using Brave Search API")
        elif GOOGLE_API_KEY:
            logger.info("Using Google Custom Search API")
        else:
            logger.info("Using Wikipedia/DuckDuckGo fallback (set SERP_API_KEY for better results)")

        try:
            # Use unified search (tries best sources first)
            all_results = await search_all_sources(query, num_results=5)

            for i, result in enumerate(all_results[:4]):
                if result.content:
                    # Format with "According to [source]" style
                    citation = format_source_citation(result)
                    sources_parts.append(
                        f"[SOURCE {i+1}]\n"
                        f"{citation}:\n"
                        f"\"{result.content[:500]}\"\n"
                        f"URL: {result.source_url}"
                    )

            if all_results:
                logger.info("Found %d sources for query", len(all_results))

        except Exception as e:
            logger.warning("Source lookup failed: %s", e)
            sources_parts.append("[UNCERTAIN] Source lookup failed - proceed with caution")

        if sources_parts:
            return (
                "\n\n[EXTERNAL SOURCES RETRIEVED]\n"
                "IMPORTANT: Use these sources to answer. Format your response as:\n"
                "\"According to [Source Name], [factual claim].\"\n"
                "If sources conflict or are insufficient, state [UNCERTAIN].\n\n"
                + "\n\n".join(sources_parts)
            )
        return "[UNCERTAIN] No external sources found for verification"

    # ----------------------------------------------------------
    # Node building (for Zero-Gate verification)
    # ----------------------------------------------------------

    async def _build_nodes_from_steps(
        self, steps: list[dict[str, str]]
    ) -> list[Node]:
        """Build Node objects from reasoning steps for Zero-Gate verification."""
        nodes: list[Node] = []
        parent_domain: int | None = None

        for i, step in enumerate(steps):
            domain_key = step["domain"]
            content = step["content"]
            domain_idx = DOMAIN_INDEX.get(domain_key, i + 1)

            # Extract signals
            signals = await self._extract_signals(content, parent_domain, domain_idx)

            # Build node
            node = Node(
                node_id=f"step_{i}",
                parent_id=f"step_{i - 1}" if i > 0 else None,
                entity_id=f"E_{i}",
                content=content,
                legacy_idx=i,
                gate_signals=GateSignals(**signals["gate_signals"]),
                raw_scores=RawScores(**signals["raw_scores"]),
            )

            # Compute gate and weight
            node.gate = compute_gate(node, parent_domain)
            node.final_weight = compute_final_weight(node, node.gate)

            nodes.append(node)
            parent_domain = node.raw_scores.current_domain

        return nodes

    async def _extract_signals(
        self,
        text: str,
        parent_domain: int | None,
        expected_domain: int,
    ) -> dict[str, Any]:
        """Extract structural signals from a reasoning step."""
        if self.llm_sensor is not None:
            try:
                signals = await self.llm_sensor.extract_signals(text, parent_domain)
                if signals["raw_scores"]["current_domain"] == 0:
                    signals["raw_scores"]["current_domain"] = expected_domain
                return signals
            except Exception as e:
                logger.warning("LLM sensor failed, using heuristics: %s", e)

        signals = self.heuristic.extract_signals(text, parent_domain)
        signals["raw_scores"]["current_domain"] = expected_domain
        return signals

    @staticmethod
    def _build_parent_domains(nodes: list[Node]) -> dict[str, int | None]:
        """Build mapping from node_id to parent's domain index."""
        node_map = {n.node_id: n for n in nodes}
        parent_domains: dict[str, int | None] = {}
        for node in nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                parent_domains[node.node_id] = parent.raw_scores.current_domain
            else:
                parent_domains[node.node_id] = None
        return parent_domains
