"""
Fallacy Detector — signal extraction + classification.

Extends the Coq-verified demo.py with broader pattern coverage.
Maps extracted signals to the 156-fallacy taxonomy.

Detection layers (checked in order):
  1. Level Confusion (paradoxes) — self-reference, circular definition
  2. Type 1: Condition Violations — manipulation, coercion, bad faith
  3. Type 3: Sequence Violations — rationalization, circular reasoning
  4. Type 2: Domain Violations — D1-D6 specific failure modes
  5. Type 4: Syndromes — cross-domain patterns (confirmation bias, etc.)

Each layer returns the MOST SPECIFIC matching fallacy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from regulus.fallacies.taxonomy import (
    Domain,
    Fallacy,
    FallacyType,
    FailureMode,
    Severity,
    FALLACIES,
    get_fallacy,
)


# =============================================================================
#                           SIGNAL PATTERNS
# =============================================================================

# --- Person attacks (D1: Object Substitution) ---
PERSON_ATTACK_PATTERNS = [
    r"\bidiot\b", r"\bstupid\b", r"\bfool\b", r"\bdumb\b", r"\bmoron\b",
    r"\bignorant\b", r"\bincompetent\b", r"\bidiots\b",
    r"\byou'?re just\b", r"\byou are just\b", r"\bpeople like you\b",
    r"\bwhat do you know\b", r"\bshut up\b",
]

# --- Logical connectors (evidence of structured reasoning) ---
LOGICAL_CONNECTORS = [
    r"\btherefore\b", r"\bthus\b", r"\bhence\b", r"\bconsequently\b",
    r"\bbecause\b", r"\bsince\b", r"\bit follows\b", r"\bas a result\b",
    r"\bthis means\b", r"\bwe can conclude\b",
]

# --- Counter-evidence consideration (D6: Reflection) ---
COUNTER_PATTERNS = [
    r"\bhowever\b", r"\bbut\b", r"\balthough\b", r"\bon the other hand\b",
    r"\balternatively\b", r"\bcritics argue\b", r"\bsome disagree\b",
    r"\bcounterargument\b", r"\bnevertheless\b", r"\bdespite\b",
    r"\bone might object\b", r"\blimitation\b",
]

# --- Self-reference (Level Confusion / Paradox) ---
SELF_REFERENCE_PATTERNS = [
    r"\bi think i\b", r"\bi know i\b", r"\bi believe i\b",
    r"\bbecause i said\b", r"\btrust me\b", r"\bi'?m always right\b",
    r"\bthis statement is\b", r"\bi can prove that i\b",
]

# --- Tradition/nature appeals (D3: Irrelevant Criterion) ---
TRADITION_PATTERNS = [
    r"\balways been\b", r"\btradition\b", r"\bour ancestors\b",
    r"\btime immemorial\b", r"\bthat'?s how it'?s done\b",
    r"\bwe'?ve always\b", r"\bhistorically\b",
    r"\bnatural\b.*\bbetter\b", r"\bnature intended\b",
]

# --- Emotion/fear manipulation (Type 1: Condition Violation) ---
EMOTION_PATTERNS = [
    r"\bterrifying\b", r"\bscary\b", r"\bdangerous\b.*\bif you don'?t\b",
    r"\byou should be afraid\b", r"\bthink of the children\b",
    r"\bhow dare you\b", r"\bdisgusting\b",
]

# --- Authority without evidence (Type 1: False Authority) ---
AUTHORITY_PATTERNS = [
    r"\bexperts say\b(?!.*\bstudy\b)",
    r"\bscience says\b(?!.*\bresearch\b)", r"\bGod\b.*\bwants\b",
    r"\bit is written\b", r"\bthe universe\b.*\btells\b",
    r"\bI have authority\b",
]

# --- False dilemma (D2: Incomplete Analysis) ---
FALSE_DILEMMA_PATTERNS = [
    r"\beither\b.*\bor\b(?!.*\balso\b)", r"\byou'?re either\b.*\bor\b",
    r"\bthere are only two\b", r"\bit'?s either\b.*\bor\b",
    r"\byou must choose\b",
]

# --- Causal errors (D5: Post Hoc, Slippery Slope) ---
POST_HOC_PATTERNS = [
    r"\bafter\b.*\btherefore\b.*\bbecause\b",
    r"\bever since\b.*\b(started|began)\b",
    r"\bright after\b.*\bhappened\b",
]

SLIPPERY_SLOPE_PATTERNS = [
    r"\bif we allow\b.*\bnext\b", r"\bwhere does it end\b",
    r"\bslippery slope\b", r"\bthen they'?ll\b.*\bthen\b",
    r"\bfirst\b.*\bthen\b.*\bthen\b.*\bthen\b",
]

# --- Overgeneralization (D5: Scale Error) ---
OVERGENERALIZATION_PATTERNS = [
    r"\ball\b.*\bare\b", r"\beveryone\b.*\b(knows|agrees|thinks)\b",
    r"\bnobody\b.*\b(likes|wants|thinks)\b",
    r"\balways\b.*\b(wrong|right|fail|succeed|lie|cheat)\b",
    r"\bnever\b.*\b(works?|succeed|right)\b",
    r"\bno one ever\b",
]

# --- Cherry picking (D1: Data Filtration) ---
CHERRY_PICK_INDICATORS = [
    r"\bonly\b.*\bevidence\b", r"\bjust look at\b",
    r"\bthe fact is\b(?!.*\bhowever\b)", r"\bproof\b.*\bthat\b(?!.*\bbut\b)",
]

# --- Equivocation (D2: Meaning Drift) ---
EQUIVOCATION_PATTERNS = [
    r"(\b\w+\b).*\b\1\b.*\b(means?|sense|definition)\b",
]

# --- Whataboutism/Tu Quoque (D1: Object Substitution) ---
WHATABOUTISM_PATTERNS = [
    r"\bwhat about\b", r"\bbut they\b.*\btoo\b",
    r"\byou also\b", r"\byou did\b.*\btoo\b",
    r"\bhypocrit\b",
]

# --- Circular reasoning (Type 3: Sequence) ---
CIRCULAR_PATTERNS = [
    r"\bbecause\b.*\bis true\b.*\bbecause\b",
    r"\bproves itself\b", r"\bself-evident\b",
    r"\bby definition\b.*\btherefore\b",
]

# --- Bandwagon (D3: Irrelevant Criterion) ---
BANDWAGON_PATTERNS = [
    r"\beveryone\b.*\bdoing\b", r"\bmillions\b.*\bcan'?t be wrong\b",
    r"\bpopular\b.*\btherefore\b", r"\bmajority\b.*\bagree\b",
    r"\beveryone knows\b",
]

# --- Passive voice hiding agent (D2: Hidden Agent) ---
PASSIVE_VOICE_PATTERNS = [
    r"\bmistakes were made\b", r"\bit was decided\b",
    r"\bhas been determined\b", r"\bwere carried out\b",
]

# --- Moving goalposts (D3: Framework for Result) ---
GOALPOSTS_PATTERNS = [
    r"\bthat'?s not what I meant\b", r"\bbut that'?s different\b",
    r"\byes but\b.*\breal\b.*\b(question|issue|point)\b",
]

# --- Sunk cost (D6: Self-Assessment) ---
SUNK_COST_PATTERNS = [
    r"\balready invested\b", r"\bcome this far\b",
    r"\bcan'?t stop now\b", r"\btoo much\b.*\b(time|money|effort)\b.*\bto quit\b",
]


# =============================================================================
#                           SIGNAL EXTRACTION
# =============================================================================

@dataclass
class Signals:
    """Extracted boolean signals from text analysis."""
    attacks_person: bool = False
    addresses_argument: bool = False
    uses_tradition: bool = False
    considers_counter: bool = False
    self_reference: bool = False
    uses_emotion: bool = False
    false_authority: bool = False
    false_dilemma: bool = False
    post_hoc_pattern: bool = False
    slippery_slope: bool = False
    overgeneralizes: bool = False
    cherry_picks: bool = False
    whataboutism: bool = False
    circular: bool = False
    bandwagon: bool = False
    passive_hiding: bool = False
    moving_goalposts: bool = False
    sunk_cost: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {k: v for k, v in self.__dict__.items()}


def _check_patterns(text: str, patterns: list[str]) -> bool:
    """Check if any regex pattern matches in text (case-insensitive)."""
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def extract_signals(text: str) -> Signals:
    """
    Extract boolean signals from text.

    Maps to Coq: extract_signals in AI_FallacyDetector.v
    Each signal corresponds to one or more failure modes.
    """
    return Signals(
        attacks_person=_check_patterns(text, PERSON_ATTACK_PATTERNS),
        addresses_argument=_check_patterns(text, LOGICAL_CONNECTORS),
        uses_tradition=_check_patterns(text, TRADITION_PATTERNS),
        considers_counter=_check_patterns(text, COUNTER_PATTERNS),
        self_reference=_check_patterns(text, SELF_REFERENCE_PATTERNS),
        uses_emotion=_check_patterns(text, EMOTION_PATTERNS),
        false_authority=_check_patterns(text, AUTHORITY_PATTERNS),
        false_dilemma=_check_patterns(text, FALSE_DILEMMA_PATTERNS),
        post_hoc_pattern=_check_patterns(text, POST_HOC_PATTERNS),
        slippery_slope=_check_patterns(text, SLIPPERY_SLOPE_PATTERNS),
        overgeneralizes=_check_patterns(text, OVERGENERALIZATION_PATTERNS),
        cherry_picks=_check_patterns(text, CHERRY_PICK_INDICATORS),
        whataboutism=_check_patterns(text, WHATABOUTISM_PATTERNS),
        circular=_check_patterns(text, CIRCULAR_PATTERNS),
        bandwagon=_check_patterns(text, BANDWAGON_PATTERNS),
        passive_hiding=_check_patterns(text, PASSIVE_VOICE_PATTERNS),
        moving_goalposts=_check_patterns(text, GOALPOSTS_PATTERNS),
        sunk_cost=_check_patterns(text, SUNK_COST_PATTERNS),
    )


# =============================================================================
#                           DETECTION RESULT
# =============================================================================

@dataclass
class DetectionResult:
    """Result of fallacy analysis."""
    valid: bool
    fallacy: Optional[Fallacy] = None
    signals: Optional[Signals] = None
    confidence: float = 1.0  # 0-1, based on signal strength

    @property
    def domain_name(self) -> str:
        if self.fallacy is None:
            return ""
        d = self.fallacy.domain
        names = {
            Domain.D1_RECOGNITION: "D1: Recognition",
            Domain.D2_CLARIFICATION: "D2: Clarification",
            Domain.D3_FRAMEWORK: "D3: Framework",
            Domain.D4_COMPARISON: "D4: Comparison",
            Domain.D5_INFERENCE: "D5: Inference",
            Domain.D6_REFLECTION: "D6: Reflection",
            Domain.NONE: "Pre-domain",
        }
        return names.get(d, str(d))

    @property
    def failure_mode_name(self) -> str:
        if self.fallacy is None:
            return ""
        fm = self.fallacy.failure_mode
        from regulus.fallacies.taxonomy import FAILURE_MODES
        info = FAILURE_MODES.get(fm)
        if info:
            return info["name"]
        return fm.value

    @property
    def type_name(self) -> str:
        if self.fallacy is None:
            return ""
        names = {
            FallacyType.T1_CONDITION_VIOLATION: "Type 1: Condition Violation",
            FallacyType.T2_DOMAIN_VIOLATION: "Type 2: Domain Violation",
            FallacyType.T3_SEQUENCE_VIOLATION: "Type 3: Sequence Violation",
            FallacyType.T4_SYNDROME: "Type 4: Syndrome",
            FallacyType.T5_CONTEXT_DEPENDENT: "Type 5: Context-Dependent",
        }
        return names.get(self.fallacy.fallacy_type, "")


# =============================================================================
#                           DETECTION ENGINE
# =============================================================================

def detect(text: str) -> DetectionResult:
    """
    Analyze text for reasoning fallacies.

    Detection order (most severe first):
      1. Self-reference / paradox → Level Confusion
      2. Circular reasoning → Type 3
      3. Ad Hominem → D1 Object Substitution
      4. Whataboutism → D1 Object Substitution
      5. Emotion/fear manipulation → Type 1
      6. False authority → Type 1
      7. Tradition/nature appeals → D3
      8. Bandwagon → D3
      9. False dilemma → D2
      10. Passive voice hiding → D2
      11. Moving goalposts → D3
      12. Post hoc → D5
      13. Slippery slope → D5
      14. Cherry picking → D1
      15. Overgeneralization → D5
      16. Sunk cost → D6
      17. No counter-evidence → D6 (Confirmation Bias)
      18. All clear → Valid

    Returns DetectionResult with matched fallacy or valid=True.
    """
    sig = extract_signals(text)

    # --- Layer 1: Level Confusion (Paradox) ---
    if sig.self_reference:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T3_CIRCULAR_REASONING"),
            signals=sig,
            confidence=0.9,
        )

    # --- Layer 2: Type 3 — Sequence Violations ---
    if sig.circular:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T3_CIRCULAR_REASONING"),
            signals=sig,
            confidence=0.85,
        )

    # --- Layer 3: D1 — Object Substitution ---
    if sig.attacks_person and not sig.addresses_argument:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D1_AD_HOMINEM"),
            signals=sig,
            confidence=0.9,
        )

    if sig.whataboutism:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D1_TU_QUOQUE"),
            signals=sig,
            confidence=0.8,
        )

    # --- Layer 4: Type 1 — Condition Violations ---
    if sig.uses_emotion and not sig.addresses_argument:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T1B_SCARE_TACTICS"),
            signals=sig,
            confidence=0.75,
        )

    if sig.false_authority and not sig.addresses_argument:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T1B_APPEAL_TO_HEAVEN"),
            signals=sig,
            confidence=0.7,
        )

    # --- Layer 5: D3 — Framework Selection ---
    # Tradition appeal fires even with "because" — "because tradition" IS the fallacy
    if sig.uses_tradition:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D3_APPEAL_TO_TRADITION"),
            signals=sig,
            confidence=0.8,
        )

    if sig.bandwagon:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D3_BANDWAGON"),
            signals=sig,
            confidence=0.75,
        )

    # --- Layer 6: D2 — Clarification ---
    if sig.false_dilemma:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D2_EITHER_OR"),
            signals=sig,
            confidence=0.8,
        )

    if sig.passive_hiding:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D2_PASSIVE_VOICE"),
            signals=sig,
            confidence=0.7,
        )

    # --- Layer 7: D3 continued ---
    if sig.moving_goalposts:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D3_MOVING_GOALPOSTS"),
            signals=sig,
            confidence=0.7,
        )

    # --- Layer 8: D5 — Inference ---
    if sig.post_hoc_pattern:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D5_POST_HOC"),
            signals=sig,
            confidence=0.75,
        )

    if sig.slippery_slope:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D5_SLIPPERY_SLOPE"),
            signals=sig,
            confidence=0.8,
        )

    if sig.cherry_picks and not sig.considers_counter:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D1_HALF_TRUTH"),
            signals=sig,
            confidence=0.65,
        )

    if sig.overgeneralizes and not sig.considers_counter:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D5_OVERGENERALIZATION"),
            signals=sig,
            confidence=0.6,
        )

    # --- Layer 9: D6 — Reflection ---
    if sig.sunk_cost:
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("D6_SUNK_COST"),
            signals=sig,
            confidence=0.8,
        )

    # --- Layer 10: Syndrome — No counter-evidence at all ---
    if not sig.considers_counter and sig.addresses_argument:
        # Has argument structure but no counter-evidence = confirmation bias
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T4_CONFIRMATION_BIAS"),
            signals=sig,
            confidence=0.5,  # Lower confidence — absence-based
        )

    if not sig.considers_counter and not sig.addresses_argument:
        # Neither argument nor counter = very low quality
        return DetectionResult(
            valid=False,
            fallacy=get_fallacy("T4_CONFIRMATION_BIAS"),
            signals=sig,
            confidence=0.4,
        )

    # --- All checks passed ---
    return DetectionResult(
        valid=True,
        fallacy=None,
        signals=sig,
        confidence=1.0,
    )


def detect_all(text: str) -> List[DetectionResult]:
    """
    Detect ALL matching fallacies (not just the first).
    Returns a list sorted by confidence (highest first).
    """
    sig = extract_signals(text)
    results: List[DetectionResult] = []

    checks: List[Tuple[bool, str, float]] = [
        (sig.self_reference, "T3_CIRCULAR_REASONING", 0.9),
        (sig.circular, "T3_CIRCULAR_REASONING", 0.85),
        (sig.attacks_person and not sig.addresses_argument, "D1_AD_HOMINEM", 0.9),
        (sig.whataboutism, "D1_TU_QUOQUE", 0.8),
        (sig.uses_emotion and not sig.addresses_argument, "T1B_SCARE_TACTICS", 0.75),
        (sig.false_authority and not sig.addresses_argument, "T1B_APPEAL_TO_HEAVEN", 0.7),
        (sig.uses_tradition, "D3_APPEAL_TO_TRADITION", 0.8),
        (sig.bandwagon, "D3_BANDWAGON", 0.75),
        (sig.false_dilemma, "D2_EITHER_OR", 0.8),
        (sig.passive_hiding, "D2_PASSIVE_VOICE", 0.7),
        (sig.moving_goalposts, "D3_MOVING_GOALPOSTS", 0.7),
        (sig.post_hoc_pattern, "D5_POST_HOC", 0.75),
        (sig.slippery_slope, "D5_SLIPPERY_SLOPE", 0.8),
        (sig.cherry_picks and not sig.considers_counter, "D1_HALF_TRUTH", 0.65),
        (sig.overgeneralizes and not sig.considers_counter, "D5_OVERGENERALIZATION", 0.6),
        (sig.sunk_cost, "D6_SUNK_COST", 0.8),
        (not sig.considers_counter, "T4_CONFIRMATION_BIAS", 0.4),
    ]

    seen_ids: set[str] = set()
    for condition, fallacy_id, confidence in checks:
        if condition and fallacy_id not in seen_ids:
            f = get_fallacy(fallacy_id)
            if f:
                results.append(DetectionResult(
                    valid=False, fallacy=f, signals=sig, confidence=confidence,
                ))
                seen_ids.add(fallacy_id)

    results.sort(key=lambda r: r.confidence, reverse=True)
    return results
