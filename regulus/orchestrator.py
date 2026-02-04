"""
Regulus AI - Orchestrator
==========================

Main verification loop: Query -> LLM reasoning -> Sensor -> Zero-Gate -> Status Machine.

Pipeline:
    User Query
        -> LLM generates D1-D6 reasoning steps
        -> Sensor extracts signals (LLM referee or heuristic)
        -> Zero-Gate checks structural integrity
        -> If Gate=0: correction loop (fix prompt -> retry -> re-verify)
        -> Status Machine assigns PrimaryMax
        -> Return VerifiedResponse
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
from .core.optimizer import TrisectionOptimizer, TrisectionState
from .llm.client import LLMClient
from .llm.sensor import HeuristicSignalExtractor, LLMSignalExtractor
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

        return VerifiedResponse(
            query=query,
            result=result,
            reasoning_steps=steps,
            corrections=corrections,
            trisection=trisection_state,
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
                    steps.append({"domain": s["domain"], "content": s["content"]})
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
