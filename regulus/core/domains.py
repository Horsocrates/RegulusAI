"""
Domain Quality Gates — Socratic Verification System
====================================================

Each domain has:
- criteria: what must be satisfied to pass
- threshold: minimum weight to advance
- probes: targeted questions for weak criteria
- max_probes: maximum probe attempts before forced advance

This replaces the old "generate all D1-D6 then pick winner" approach
with a sequential pipeline where each domain must pass before advancing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CriterionResult:
    """Result of evaluating a single criterion."""
    name: str
    passed: bool
    score: int  # 0-100
    reason: str = ""


@dataclass
class DomainCheckResult:
    """Result of evaluating all criteria for a domain."""
    domain: str
    criteria: List[CriterionResult]
    total_weight: int
    passed: bool
    failed_criteria: List[str] = field(default_factory=list)


@dataclass
class ProbeRecord:
    """Record of a diagnostic probe and its result."""
    criterion: str
    probe_question: str
    probe_answer: str
    weight_before: int
    weight_after: int


@dataclass
class DomainPassRecord:
    """Complete record of a domain's passage through the pipeline."""
    domain: str
    attempts: int  # how many times evaluated
    probes_used: List[ProbeRecord] = field(default_factory=list)
    final_weight: int = 0
    passed: bool = False
    content: str = ""  # the domain's output content


# ============================================================
# Domain Definitions
# ============================================================

DOMAIN_DEFINITIONS: Dict[str, dict] = {
    "D1": {
        "name": "Recognition",
        "question": "What is actually here?",
        "criteria": {
            "prompt_type_classified": (
                "The prompt TYPE is explicitly classified as one of: "
                "[FACT] - requires verifiable data, "
                "[REASONING] - requires logical analysis, "
                "[OPINION] - asks for subjective view, "
                "[QUESTION] - meta-question about something, "
                "[COMMAND] - instruction to perform action"
            ),
            "task_goal_identified": (
                "The GOAL of the task is clearly stated:\n"
                "GOAL: <what the questioner wants to know/achieve>\n"
                "SUCCESS CRITERIA: <what counts as a correct/complete answer>"
            ),
            "task_decomposed": (
                "The task is decomposed into its structural ELEMENTS using ERR:\n"
                "For each component of the task (not just words, but logical parts):\n"
                "ELEMENT: <what is this component>\n"
                "  ROLE: <what function does it serve in solving the task>\n"
                "  RULE: <what principle governs it / constraints>\n"
                "Minimum 2 elements, maximum 6."
            ),
            "solution_approach": (
                "A solution APPROACH is identified:\n"
                "APPROACH: <method to solve this>\n"
                "STEPS: <high-level sequence of steps needed>\n"
                "RISK: <what could go wrong / where errors are likely>"
            ),
            "no_hallucination": "No fabricated objects, people, laws, or facts",
            "factual_claim_tagged": (
                "If TYPE is [FACT], tag as [FACTUAL DATA REQUIRED: UNCONFIRMED] "
                "and classify:\n"
                "[STABLE] — established fact (definitions, geography, history, science, "
                "known people, completed events, physical constants)\n"
                "[VOLATILE] — fact that changes or requires data (statistics, rankings, "
                "current holders, prices, populations, production, recent events)\n"
                "Then list specific facts needing verification."
            ),
        },
        "threshold": 60,
        "max_probes": 3,
        "probes": {
            "prompt_type_classified": (
                "Classify this prompt's TYPE. Is it asking for:\n"
                "- [FACT]: verifiable data (statistics, rankings, dates, names)\n"
                "- [REASONING]: logical analysis, puzzle, math, deduction\n"
                "- [OPINION]: subjective viewpoint\n"
                "- [QUESTION]: meta-inquiry\n"
                "- [COMMAND]: action to perform\n"
                "State the TYPE explicitly."
            ),
            "task_goal_identified": (
                "What is the GOAL of this task? What does the questioner want?\n"
                "State it as:\n"
                "GOAL: <concrete objective>\n"
                "SUCCESS CRITERIA: <what makes the answer correct>\n\n"
                "Example for 'What is 2+2?':\n"
                "GOAL: Compute the sum of 2 and 2\n"
                "SUCCESS CRITERIA: A single numerical value"
            ),
            "task_decomposed": (
                "Break this task into its structural components.\n"
                "For each component, apply ERR:\n"
                "ELEMENT: <the component> — ROLE: <its function> — RULE: <constraints>\n\n"
                "Example for 'Which state produces the most peaches?':\n"
                "ELEMENT: 'state' — ROLE: target entity to identify — RULE: must be a US state\n"
                "ELEMENT: 'produces' — ROLE: measurement metric — RULE: agricultural production data\n"
                "ELEMENT: 'most' — ROLE: comparison operator — RULE: requires ranking, superlative\n"
                "ELEMENT: 'peaches' — ROLE: subject of measurement — RULE: specific fruit crop\n\n"
                "Example for 'White elephant gift exchange: who ends up with gift 3?':\n"
                "ELEMENT: participants {A,B,C,D} — ROLE: agents — RULE: each holds exactly 1 gift\n"
                "ELEMENT: initial state {A→1, B→2...} — ROLE: starting condition — RULE: defines t=0\n"
                "ELEMENT: steal operations — ROLE: state transformations — RULE: swap mechanics\n"
                "ELEMENT: move sequence — ROLE: ordered input — RULE: execute sequentially"
            ),
            "solution_approach": (
                "How should this task be solved? Identify:\n"
                "APPROACH: <the method> (e.g., state tracking, arithmetic, lookup, deduction)\n"
                "STEPS: <ordered list of what to do>\n"
                "RISK: <where errors are most likely>\n\n"
                "Example for arithmetic: APPROACH: step-by-step calculation\n"
                "  STEPS: 1) Parse operands 2) Apply operations 3) Verify result\n"
                "  RISK: Order of operations, sign errors\n\n"
                "Example for logic puzzle: APPROACH: constraint satisfaction\n"
                "  STEPS: 1) List all constraints 2) Eliminate impossibilities 3) Find unique solution\n"
                "  RISK: Missing a constraint, contradictory assumptions"
            ),
            "no_hallucination": (
                "Verify: does this object/concept/entity actually exist as described? "
                "List only verifiable facts."
            ),
            "factual_claim_tagged": (
                "If TYPE is [FACT], explicitly state:\n"
                "[FACTUAL DATA REQUIRED: UNCONFIRMED]\n"
                "Classify: [STABLE] or [VOLATILE]\n"
                "- STABLE: won't change tomorrow (capital of France, who wrote Hamlet)\n"
                "- VOLATILE: could change or needs data (GDP, population, current CEO)\n\n"
                "Then list facts needing verification:\n"
                "- Fact 1: <claim>\n"
                "If TYPE is not [FACT], state: [NO FACTUAL VERIFICATION NEEDED]"
            ),
        },
    },
    "D2": {
        "name": "Clarification",
        "question": "What exactly is this?",
        "criteria": {
            "d1_validation": (
                "D1 outputs validated: TYPE classification confirmed, "
                "GOAL and SUCCESS CRITERIA reviewed, "
                "task decomposition (ELEMENTS) reviewed and approved or corrected, "
                "APPROACH confirmed as appropriate"
            ),
            "terms_defined": "Key terms are precisely defined in context",
            "boundaries_set": "Scope of the question is clearly delimited",
            "no_equivocation": "No term is used in multiple senses without distinction",
            "certainty_check": (
                "Certainty level assessed.\n"
                "For FACT tasks: if understanding < 90%, list clarifying questions. "
                "Format: [CERTAINTY: X%]\n"
                "For REASONING tasks: assess whether you have enough information to solve "
                "the problem. If all data is in the prompt, [CERTAINTY: 100%] — proceed to solve. "
                "Do NOT lower certainty because the problem is 'complex'."
            ),
            "fact_status": (
                "If D1 tagged [FACTUAL DATA REQUIRED: UNCONFIRMED], update status:\n"
                "If STABLE fact (definitions, geography, history, science, known people):\n"
                "  [CONFIRMED BY KNOWLEDGE] — state the fact from training knowledge directly.\n"
                "  Do NOT mark as UNCONFIRMED just because no external source was searched.\n"
                "  Your training knowledge IS a valid source for established facts.\n"
                "If VOLATILE fact (statistics, rankings, current state):\n"
                "  [CONFIRMED] — external source found and verified, OR\n"
                "  [UPDATED] — original assumption wrong, correct data found, OR\n"
                "  [UNCONFIRMED] — could not verify from external sources"
            ),
        },
        "threshold": 60,
        "max_probes": 3,
        "probes": {
            "d1_validation": (
                "Review D1's analysis:\n"
                "1. Is the TYPE classification correct?\n"
                "2. Is the GOAL and SUCCESS CRITERIA accurate?\n"
                "3. Is the task decomposition (ELEMENTS) complete and correct?\n"
                "4. Is the APPROACH appropriate for this task?\n"
                "State: [D1 VALIDATED] or [D1 CORRECTED: <corrections>]"
            ),
            "terms_defined": (
                "Define each key term precisely as used in this specific context. "
                "Are there alternative meanings that could cause confusion?"
            ),
            "boundaries_set": (
                "What is included and what is excluded from this question's scope? "
                "What are we NOT asking?"
            ),
            "no_equivocation": (
                "Are any terms being used ambiguously? "
                "List each term and its single precise meaning here."
            ),
            "certainty_check": (
                "Assess certainty:\n"
                "- For FACT tasks: How sure are you about the terms and scope? (0-100%)\n"
                "- For REASONING tasks: Do you have all the information needed to solve this?\n"
                "  If the problem statement contains all necessary data, your certainty is 100%.\n"
                "  Complexity does NOT reduce certainty — only missing information does.\n"
                "Format: [CERTAINTY: X%]"
            ),
            "fact_status": (
                "For each fact tagged as UNCONFIRMED in D1:\n"
                "If the fact is STABLE (established, well-known):\n"
                "  State it directly: [CONFIRMED BY KNOWLEDGE] Fact: <claim> — <your answer>\n"
                "  Your training data is reliable for geography, history, science, definitions.\n"
                "If the fact is VOLATILE (statistics, rankings, current):\n"
                "  Use external sources: [CONFIRMED] Source: <source>\n"
                "  Or if no source: [UNCONFIRMED] Reason: <why>\n\n"
                "NEVER mark a well-known fact as UNCONFIRMED just because you didn't search for it."
            ),
        },
    },
    "D3": {
        "name": "Modeling",
        "question": "How do we connect this?",
        "criteria": {
            "model_appropriate": (
                "A reasoning framework matching D1's APPROACH is applied.\n"
                "Use the APPROACH identified in D1 as the framework.\n"
                "If D1 said APPROACH: state tracking → apply state tracking.\n"
                "If D1 said APPROACH: constraint satisfaction → apply constraint elimination.\n"
                "Name the framework explicitly."
            ),
            "no_category_error": "No type mismatches or category errors in comparisons",
            "connections_valid": "Logical/causal connections between elements are justified",
        },
        "threshold": 60,
        "max_probes": 2,
        "probes": {
            "model_appropriate": (
                "What framework or model are you using to analyze this? "
                "Is it the right one for this type of question, or would another be more appropriate?"
            ),
            "no_category_error": (
                "Are you comparing things of the same kind? "
                "Check for any type mismatches in your reasoning."
            ),
            "connections_valid": (
                "What are the causal or logical connections between the elements? "
                "Are any connections assumed without justification?"
            ),
        },
    },
    "D4": {
        "name": "Calculation",
        "question": "How does the process work?",
        "criteria": {
            "no_contradiction": "No internal contradictions in the reasoning chain",
            "process_complete": "No missing steps — all necessary reasoning is present",
            "steps_justified": "Each reasoning step is supported, no unsupported leaps",
        },
        "threshold": 60,
        "max_probes": 2,
        "probes": {
            "no_contradiction": (
                "Review your claims so far. Do any contradict each other? "
                "List each claim and check for conflicts."
            ),
            "process_complete": (
                "What steps in the reasoning might be missing? "
                "What hasn't been considered that should be?"
            ),
            "steps_justified": (
                "For each reasoning step, what is the justification? "
                "Identify any unsupported logical leaps."
            ),
        },
    },
    "D5": {
        "name": "Inference",
        "question": "What follows from this?",
        "criteria": {
            "follows_from_evidence": (
                "Conclusion follows from the analysis in previous domains. "
                "For REASONING tasks: the conclusion must follow from logical steps, "
                "not external evidence. Completing a logical derivation IS sufficient evidence."
            ),
            "no_logical_jump": "No gap between evidence and conclusion",
            "no_unsupported_inference": (
                "Do NOT make inferences about dates, deaths, or events unless explicitly verified. "
                "If you know a fact directly, state it without constructing additional logic chains."
            ),
            "conclusion_stated": (
                "A clear, direct answer to the original question is stated. "
                "The answer must satisfy D1's SUCCESS CRITERIA. "
                "For REASONING tasks: show the derived answer — NEVER say 'cannot determine'. "
                "For FACT tasks: state the confirmed fact."
            ),
        },
        "threshold": 70,  # Higher — this IS the answer
        "max_probes": 3,  # More attempts allowed — this matters most
        "is_answer": True,
        "probes": {
            "follows_from_evidence": (
                "Does your conclusion follow from the analysis performed? "
                "For REASONING tasks: logical derivation IS evidence. "
                "What specific reasoning steps support your conclusion?"
            ),
            "no_logical_jump": (
                "Is there any gap between your evidence and your conclusion? "
                "What bridges that gap?"
            ),
            "no_unsupported_inference": (
                "Check: Are you making inferences about dates, deaths, or events that you "
                "haven't verified? If you know the direct answer (e.g., 'X won the tournament'), "
                "state it WITHOUT inferring additional facts (e.g., death dates) that might "
                "contradict your knowledge. Direct knowledge beats constructed inferences."
            ),
            "conclusion_stated": (
                "State your conclusion as a clear, direct answer "
                "to the original question.\n"
                "- If this is a REASONING task, show the logical steps and give the answer.\n"
                "- If facts were CONFIRMED or CONFIRMED BY KNOWLEDGE, state them directly.\n"
                "- NEVER say 'cannot determine' — if you can reason through it, do it.\n"
                "- NEVER say 'computationally impractical' — break it into steps.\n"
                "- No hedging, no meta-commentary."
            ),
        },
    },
    "D6": {
        "name": "Reflection",
        "question": "Where does this not work?",
        "criteria": {
            "limitations_noted": "Conditions where the answer might be wrong or incomplete",
            "no_dogmatism": "Alternative interpretations acknowledged",
        },
        "threshold": 50,  # Lower — this is supplementary
        "max_probes": 1,
        "is_qualifier": True,
        "probes": {
            "limitations_noted": (
                "Under what specific conditions might this answer be wrong or incomplete?"
            ),
            "no_dogmatism": (
                "What alternative answers or interpretations exist? "
                "Why might someone reasonably disagree?"
            ),
        },
    },
}

DOMAIN_ORDER = ["D1", "D2", "D3", "D4", "D5", "D6"]


# ============================================================
# Domain Access Functions
# ============================================================

def get_domain_def(domain: str) -> dict:
    """Get the full definition for a domain."""
    return DOMAIN_DEFINITIONS.get(domain, {})


def get_domain_name(domain: str) -> str:
    """Get the human-readable name for a domain."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("name", domain)


def get_domain_question(domain: str) -> str:
    """Get the guiding question for a domain."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("question", "")


def get_domain_threshold(domain: str) -> int:
    """Get the minimum weight threshold for a domain to pass."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("threshold", 60)


def get_domain_criteria(domain: str) -> Dict[str, str]:
    """Get the criteria checklist for a domain."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("criteria", {})


def get_probe_for_criterion(domain: str, criterion: str) -> str:
    """Get the diagnostic probe question for a failed criterion."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("probes", {}).get(criterion, "")


def get_failed_probes(domain: str, failed_criteria: List[str]) -> List[tuple]:
    """
    Return list of (criterion, probe_question) for all failed criteria.

    Args:
        domain: The domain identifier (D1-D6)
        failed_criteria: List of criterion names that failed

    Returns:
        List of (criterion_name, probe_question) tuples
    """
    result = []
    for crit in failed_criteria:
        probe = get_probe_for_criterion(domain, crit)
        if probe:
            result.append((crit, probe))
    return result


def is_answer_domain(domain: str) -> bool:
    """Check if this domain produces the main answer (D5)."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("is_answer", False)


def is_qualifier_domain(domain: str) -> bool:
    """Check if this domain is a qualifier/caveat (D6)."""
    d = DOMAIN_DEFINITIONS.get(domain, {})
    return d.get("is_qualifier", False)


# ============================================================
# Weight Calculation (domain-local)
# ============================================================

def compute_domain_weight(criteria_results: List[CriterionResult]) -> int:
    """
    Compute total weight from criteria results.

    Weight is average of all criteria scores (0-100).
    This is quality-within-domain, not cross-domain comparison.
    """
    if not criteria_results:
        return 0
    total = sum(c.score for c in criteria_results)
    return total // len(criteria_results)


def check_domain_passed(domain: str, weight: int) -> bool:
    """Check if domain weight meets threshold."""
    threshold = get_domain_threshold(domain)
    return weight >= threshold


# ============================================================
# Confidence Level System
# ============================================================

CONFIDENCE_LEVELS = {
    "unconfirmed": {"min": 0, "max": 49, "label": "unconfirmed"},
    "low": {"min": 50, "max": 60, "label": "low confidence"},
    "medium": {"min": 61, "max": 70, "label": "medium confidence"},
    "high": {"min": 71, "max": 85, "label": "high confidence"},
    "very_high": {"min": 86, "max": 100, "label": "very high confidence"},
}


def compute_confidence_score(domain_records: list) -> int:
    """
    Compute overall confidence score (0-100) from domain records.

    Based purely on RESULTS (final domain weights), not process.

    Formula:
    - D5 (Inference) weight × 40% — this IS the answer
    - D1-D4 average weight × 40% — reasoning chain quality
    - D6 (Reflection) weight × 20% — self-awareness

    If pipeline was interrupted (domain not passed), returns 0.
    """
    if not domain_records:
        return 0

    # If any domain failed to pass, pipeline should have stopped
    # This means we have no valid result
    for rec in domain_records:
        if not rec.passed:
            return 0

    weights = {rec.domain: rec.final_weight for rec in domain_records}

    # D5 weight (40%)
    d5_score = weights.get("D5", 0) * 0.40

    # D1-D4 average (40%)
    d1_d4 = [weights.get(d, 0) for d in ["D1", "D2", "D3", "D4"]]
    d1_d4_avg = sum(d1_d4) / len(d1_d4) if d1_d4 else 0
    reasoning_score = d1_d4_avg * 0.40

    # D6 weight (20%)
    d6_score = weights.get("D6", 0) * 0.20

    final = max(0, min(100, int(d5_score + reasoning_score + d6_score)))
    return final


def get_confidence_level(score: int) -> str:
    """Map numeric score to confidence level label."""
    if score < 50:
        return "unconfirmed"
    elif score <= 60:
        return "low confidence"
    elif score <= 70:
        return "medium confidence"
    elif score <= 85:
        return "high confidence"
    else:
        return "very high confidence"
