"""
Regulus AI - Sensor Layer
=========================

The Sensor Layer provides signal extraction for reasoning verification.

For MVP, this includes:
1. Mock signals for testing
2. Paradox examples (Liar, Russell, etc.)
3. Simple heuristic-based signal extraction
4. LLM wrapper interface (for future integration)

In production, this layer would use NLP classifiers or LLM calls
to extract gate_signals from raw text.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import re

from ..core.types import GateSignals, RawScores, Node


# ============================================================
# Paradox Examples (Pre-built test cases)
# ============================================================

class ParadoxType(Enum):
    """Classic paradoxes that should trigger Zero-Gate"""
    LIAR = "liar"                      # "This statement is false"
    RUSSELL = "russell"                # Set of all sets that don't contain themselves
    BARBER = "barber"                  # Who shaves the barber?
    GRELLING = "grelling"              # Is "heterological" heterological?
    CURRY = "curry"                    # "If this sentence is true, then P"
    YABLO = "yablo"                    # Infinite sequence of liar-like statements
    BERRY = "berry"                    # "Smallest number not definable in < 100 chars"
    BURALI_FORTI = "burali_forti"      # Ordinal of all ordinals


@dataclass
class ParadoxExample:
    """A paradox test case with expected Zero-Gate failure"""
    name: str
    paradox_type: ParadoxType
    statement: str
    explanation: str
    expected_gate_failure: str  # Which gate should fail: "ERR", "LEVELS", "ORDER"
    tree: Dict[str, Any]


def create_liar_paradox() -> ParadoxExample:
    """The Liar Paradox: 'This statement is false'"""
    return ParadoxExample(
        name="Liar Paradox",
        paradox_type=ParadoxType.LIAR,
        statement="This statement is false.",
        explanation="Self-reference creates L1-L3 level violation. "
                   "The statement attempts to be both object (L1) and "
                   "truth-evaluator (L2) simultaneously.",
        expected_gate_failure="LEVELS",
        tree={
            "reasoning_tree": [
                {
                    "node_id": "liar_claim",
                    "parent_id": None,
                    "entity_id": "LIAR_1",
                    "content": "D1: Consider the statement 'This statement is false'",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # LEVEL VIOLATION: self-reference
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 5, "current_domain": 1}
                },
                {
                    "node_id": "liar_eval_true",
                    "parent_id": "liar_claim",
                    "entity_id": "LIAR_2",
                    "content": "D5: If the statement is TRUE, then it is FALSE (by its content)",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # Inherits level violation
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 5}
                },
                {
                    "node_id": "liar_eval_false",
                    "parent_id": "liar_claim",
                    "entity_id": "LIAR_3",
                    "content": "D5: If the statement is FALSE, then it is TRUE (contradiction)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # Inherits level violation
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 5}
                }
            ]
        }
    )


def create_russell_paradox() -> ParadoxExample:
    """Russell's Paradox: Set of all sets that don't contain themselves"""
    return ParadoxExample(
        name="Russell's Paradox",
        paradox_type=ParadoxType.RUSSELL,
        statement="Let R be the set of all sets that do not contain themselves. Does R contain itself?",
        explanation="Self-membership query creates level confusion. "
                   "R tries to operate on itself (L2 on L2), violating hierarchy.",
        expected_gate_failure="LEVELS",
        tree={
            "reasoning_tree": [
                {
                    "node_id": "russell_define",
                    "parent_id": None,
                    "entity_id": "RUSSELL_1",
                    "content": "D2: Define R = {x : x ∉ x} (set of sets not containing themselves)",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,  # Definition itself is OK
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 2}
                },
                {
                    "node_id": "russell_query",
                    "parent_id": "russell_define",
                    "entity_id": "RUSSELL_2",
                    "content": "D3: Apply membership criterion to R itself: R ∈ R?",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,  # LEVEL VIOLATION: self-application
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 7, "current_domain": 3}
                },
                {
                    "node_id": "russell_yes",
                    "parent_id": "russell_query",
                    "entity_id": "RUSSELL_3A",
                    "content": "D5: If R ∈ R, then by definition R ∉ R (contradiction)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 5}
                },
                {
                    "node_id": "russell_no",
                    "parent_id": "russell_query",
                    "entity_id": "RUSSELL_3B",
                    "content": "D5: If R ∉ R, then by definition R ∈ R (contradiction)",
                    "legacy_idx": 3,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": False,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 5}
                }
            ]
        }
    )


def create_non_sequitur_example() -> ParadoxExample:
    """Non-sequitur: Conclusion doesn't follow from premises"""
    return ParadoxExample(
        name="Non-Sequitur Fallacy",
        paradox_type=ParadoxType.CURRY,
        statement="All cats are animals. Therefore, the economy will improve.",
        explanation="Missing logical connection (Rule) between premise and conclusion. "
                   "ERR structure is incomplete.",
        expected_gate_failure="ERR",
        tree={
            "reasoning_tree": [
                {
                    "node_id": "premise",
                    "parent_id": None,
                    "entity_id": "NS_1",
                    "content": "D1: All cats are animals (true premise)",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
                },
                {
                    "node_id": "invalid_conclusion",
                    "parent_id": "premise",
                    "entity_id": "NS_2",
                    "content": "D5: Therefore, the economy will improve",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": False,  # ERR VIOLATION: no logical rule connecting
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 5, "domain_points": 10, "current_domain": 5}
                }
            ]
        }
    )


def create_domain_skip_example() -> ParadoxExample:
    """Domain skip: Jumping from D1 to D5 without D2-D4"""
    return ParadoxExample(
        name="Domain Skip (Order Violation)",
        paradox_type=ParadoxType.CURRY,
        statement="I see a bird. Therefore, evolution is true.",
        explanation="Skips clarification (D2), framework selection (D3), and comparison (D4). "
                   "Violates L5 sequence requirement.",
        expected_gate_failure="ORDER",
        tree={
            "reasoning_tree": [
                {
                    "node_id": "observation",
                    "parent_id": None,
                    "entity_id": "DS_1",
                    "content": "D1: I observe a bird",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
                },
                {
                    "node_id": "premature_conclusion",
                    "parent_id": "observation",
                    "entity_id": "DS_2",
                    "content": "D5: Therefore, evolution is true",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": False  # ORDER VIOLATION: skipped D2-D4
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 5, "current_domain": 5}
                }
            ]
        }
    )


def create_valid_reasoning_example() -> ParadoxExample:
    """Valid reasoning that should pass all gates"""
    return ParadoxExample(
        name="Valid Syllogism",
        paradox_type=ParadoxType.LIAR,  # N/A - valid
        statement="All humans are mortal. Socrates is human. Therefore, Socrates is mortal.",
        explanation="Classic valid syllogism. All ERR components present, "
                   "no level violations, proper D1→D5 sequence.",
        expected_gate_failure="NONE",
        tree={
            "reasoning_tree": [
                {
                    "node_id": "major_premise",
                    "parent_id": None,
                    "entity_id": "VALID_1",
                    "content": "D1: All humans are mortal (major premise)",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 9, "current_domain": 1}
                },
                {
                    "node_id": "minor_premise",
                    "parent_id": "major_premise",
                    "entity_id": "VALID_2",
                    "content": "D2: Socrates is human (minor premise, clarification)",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 9, "current_domain": 2}
                },
                {
                    "node_id": "framework",
                    "parent_id": "minor_premise",
                    "entity_id": "VALID_3",
                    "content": "D3: Apply syllogistic reasoning (Barbara form)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 3}
                },
                {
                    "node_id": "conclusion",
                    "parent_id": "framework",
                    "entity_id": "VALID_4",
                    "content": "D5: Therefore, Socrates is mortal",
                    "legacy_idx": 3,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 10, "current_domain": 5}
                },
                {
                    "node_id": "reflection",
                    "parent_id": "conclusion",
                    "entity_id": "VALID_5",
                    "content": "D6: This assumes the premises are true and the syllogism is complete",
                    "legacy_idx": 4,
                    "gate_signals": {
                        "e_exists": True,
                        "r_exists": True,
                        "rule_exists": True,
                        "s_exists": True,
                        "deps_declared": True,
                        "l1_l3_ok": True,
                        "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 9, "current_domain": 6}
                }
            ]
        }
    )


# Pre-built paradox library
PARADOX_EXAMPLES = {
    "liar": create_liar_paradox,
    "russell": create_russell_paradox,
    "non_sequitur": create_non_sequitur_example,
    "domain_skip": create_domain_skip_example,
    "valid_syllogism": create_valid_reasoning_example,
}


def get_paradox_example(name: str) -> ParadoxExample:
    """Get a pre-built paradox example by name"""
    if name not in PARADOX_EXAMPLES:
        available = ", ".join(PARADOX_EXAMPLES.keys())
        raise ValueError(f"Unknown paradox: {name}. Available: {available}")
    return PARADOX_EXAMPLES[name]()


def list_paradox_examples() -> List[str]:
    """List available paradox examples"""
    return list(PARADOX_EXAMPLES.keys())


# ============================================================
# Simple Heuristic Signal Extractor
# ============================================================

class HeuristicSignalExtractor:
    """
    Simple rule-based signal extraction from text.

    This is a placeholder for more sophisticated NLP analysis.
    In production, this would be replaced by trained classifiers or LLM calls.
    """

    # Patterns indicating self-reference (potential LEVELS violation)
    SELF_REFERENCE_PATTERNS = [
        r"this statement",
        r"this sentence",
        r"itself",
        r"self-referent",
        r"contains? itself",
        r"set of all sets",
        r"\\bR \\in R\\b",
        r"\\bR ∈ R\\b",
    ]

    # Patterns indicating missing logical connection (ERR_RULE)
    NON_SEQUITUR_PATTERNS = [
        r"therefore.*unrelated",
        r"thus.*nothing to do",
        r"hence.*random",
    ]

    # Domain keywords
    DOMAIN_KEYWORDS = {
        1: ["observe", "see", "notice", "identify", "recognize", "claim", "statement"],
        2: ["define", "clarify", "mean", "term", "definition", "specifically"],
        3: ["framework", "model", "criteria", "apply", "use", "method"],
        4: ["compare", "contrast", "similar", "different", "calculate"],
        5: ["therefore", "thus", "conclude", "follows", "hence", "infer"],
        6: ["however", "but", "limit", "exception", "assumes", "unless", "caveat"],
    }

    def __init__(self):
        self.self_ref_patterns = [re.compile(p, re.IGNORECASE) for p in self.SELF_REFERENCE_PATTERNS]
        self.non_seq_patterns = [re.compile(p, re.IGNORECASE) for p in self.NON_SEQUITUR_PATTERNS]

    def detect_self_reference(self, text: str) -> bool:
        """Check for self-referential patterns"""
        for pattern in self.self_ref_patterns:
            if pattern.search(text):
                return True
        return False

    def detect_non_sequitur(self, text: str) -> bool:
        """Check for obvious non-sequitur patterns"""
        for pattern in self.non_seq_patterns:
            if pattern.search(text):
                return True
        return False

    def detect_domain(self, text: str) -> int:
        """Estimate which domain (1-6) the text belongs to"""
        text_lower = text.lower()
        scores = {d: 0 for d in range(1, 7)}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[domain] += 1

        # Return domain with highest score, default to 1
        best_domain = max(scores, key=scores.get)
        return best_domain if scores[best_domain] > 0 else 1

    def extract_signals(self, text: str, parent_domain: Optional[int] = None) -> Dict[str, Any]:
        """
        Extract gate signals from text using heuristics.

        Returns:
            Dict with gate_signals and raw_scores
        """
        has_self_ref = self.detect_self_reference(text)
        has_non_seq = self.detect_non_sequitur(text)
        current_domain = self.detect_domain(text)

        # Check for domain sequence violation
        l5_ok = True
        if parent_domain is not None and current_domain < parent_domain:
            l5_ok = False

        # Simple heuristic: text has content = element exists
        e_exists = len(text.strip()) > 10
        r_exists = any(text.lower().startswith(w) for w in ["if", "when", "because", "since", "as"]) or len(text) > 20
        rule_exists = not has_non_seq and len(text) > 30

        return {
            "gate_signals": {
                "e_exists": e_exists,
                "r_exists": r_exists,
                "rule_exists": rule_exists,
                "s_exists": True,         # Permissive default for v1 pipeline
                "deps_declared": True,    # Permissive default for v1 pipeline
                "l1_l3_ok": not has_self_ref,
                "l5_ok": l5_ok
            },
            "raw_scores": {
                "struct_points": 10 if (e_exists and r_exists and rule_exists) else 5,
                "domain_points": 7,  # Default quality
                "current_domain": current_domain
            }
        }


# ============================================================
# LLM Wrapper Interface
# ============================================================

class LLMSignalExtractor:
    """
    LLM-based signal extraction using a Referee LLM.

    Calls an LLM to analyze reasoning steps and extract structural signals
    (ERR, Levels, Order) as JSON. Falls back to heuristics on failure.
    """

    SYSTEM_PROMPT = """\
You are a Logic Referee analyzing reasoning for structural integrity.

For a given reasoning step, extract these signals as JSON:
{
    "e_exists": true/false,
    "r_exists": true/false,
    "rule_exists": true/false,
    "s_exists": true/false,
    "deps_declared": true/false,
    "l1_l3_ok": true/false,
    "l5_ok": true/false,
    "current_domain": 1-6,
    "struct_points": 0-10,
    "domain_points": 0-10
}

Rules:
- e_exists: Is there a concrete, identifiable object/claim being reasoned about?
- r_exists: Is there a defined functional purpose or relationship?
- rule_exists: Is there a logical principle connecting premises to conclusion?
- s_exists: Are states defined (possible states + current state for key elements)?
- deps_declared: Are dependencies on prior domains/steps explicitly stated?
- l1_l3_ok: false if self-reference, circular definitions, or level confusion detected
- l5_ok: false if reasoning jumps domains or skips required steps
- current_domain: 1=Recognition, 2=Clarification, 3=Framework, 4=Comparison, 5=Inference, 6=Reflection
- struct_points: 0-10 quality of ERRS structure (Element/Role/Rule/Status completeness)
- domain_points: 0-10 quality of reasoning within the domain

Be strict. Absence of evidence = false/0. Respond with JSON only."""

    def __init__(self, client: "LLMClient"):
        from .client import LLMClient
        self.client: LLMClient = client
        self.heuristic_fallback = HeuristicSignalExtractor()

    async def extract_signals(self, text: str,
                              parent_domain: Optional[int] = None) -> Dict[str, Any]:
        """
        Extract signals using LLM referee, with heuristic fallback.

        Args:
            text: Reasoning step text to analyze
            parent_domain: Domain index of the previous step (for sequence check)

        Returns:
            Dict with "gate_signals" and "raw_scores" keys
        """
        try:
            return await self._extract_via_llm(text, parent_domain)
        except Exception:
            return self.heuristic_fallback.extract_signals(text, parent_domain)

    async def _extract_via_llm(self, text: str,
                               parent_domain: Optional[int] = None) -> Dict[str, Any]:
        """Make LLM call and parse structured signal response."""
        context = ""
        if parent_domain is not None:
            context = f"\nPrevious step was in domain D{parent_domain}."

        prompt = f"Analyze this reasoning step:{context}\n\n\"{text}\""

        response = await self.client.generate(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
        )

        parsed = self._parse_json_response(response)

        return {
            "gate_signals": {
                "e_exists": bool(parsed.get("e_exists", False)),
                "r_exists": bool(parsed.get("r_exists", False)),
                "rule_exists": bool(parsed.get("rule_exists", False)),
                "s_exists": bool(parsed.get("s_exists", False)),
                "deps_declared": bool(parsed.get("deps_declared", False)),
                "l1_l3_ok": bool(parsed.get("l1_l3_ok", True)),
                "l5_ok": bool(parsed.get("l5_ok", True)),
            },
            "raw_scores": {
                "struct_points": int(parsed.get("struct_points", 5)),
                "domain_points": int(parsed.get("domain_points", 5)),
                "current_domain": int(parsed.get("current_domain", 1)),
            },
        }

    async def analyze_reasoning_chain(self, steps: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze a full chain of reasoning steps.

        Args:
            steps: List of reasoning step texts

        Returns:
            List of signal dictionaries for each step
        """
        results = []
        parent_domain = None

        for step in steps:
            signals = await self.extract_signals(step, parent_domain)
            results.append(signals)
            parent_domain = signals["raw_scores"]["current_domain"]

        return results

    @staticmethod
    def _parse_json_response(response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks."""
        import json

        text = response.strip()

        # Remove markdown code fences if present
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

        # Try to find JSON object in the text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


# ============================================================
# Convenience Functions
# ============================================================

def build_tree_from_texts(steps: List[str],
                           extractor: Optional[HeuristicSignalExtractor] = None) -> Dict[str, Any]:
    """
    Build a reasoning tree from a list of text steps.

    Args:
        steps: List of reasoning step texts (in order)
        extractor: Signal extractor to use (default: HeuristicSignalExtractor)

    Returns:
        Dict in reasoning_tree format ready for LogicGuardEngine
    """
    if extractor is None:
        extractor = HeuristicSignalExtractor()

    nodes = []
    parent_domain = None

    for i, text in enumerate(steps):
        signals = extractor.extract_signals(text, parent_domain)

        node = {
            "node_id": f"step_{i}",
            "parent_id": f"step_{i-1}" if i > 0 else None,
            "entity_id": f"E_{i}",
            "content": text,
            "legacy_idx": i,
            "gate_signals": signals["gate_signals"],
            "raw_scores": signals["raw_scores"]
        }
        nodes.append(node)
        parent_domain = signals["raw_scores"]["current_domain"]

    return {"reasoning_tree": nodes}


def quick_analyze(text: str) -> Dict[str, Any]:
    """
    Quick analysis of a single reasoning text.

    Returns extracted signals.
    """
    extractor = HeuristicSignalExtractor()
    return extractor.extract_signals(text)
