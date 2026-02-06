"""
Humor/Sarcasm detection module.

Uses 5-marker framework to detect sarcasm in text.
Called by D1 when task involves sentiment/sarcasm/tone analysis.

Markers:
  M1: Polarity inversion (positive words + negative context or vice versa)
  M2: Hyperbole (exaggeration disproportionate to situation)
  M3: Incongruity (statement contradicts known facts or common sense)
  M4: Pragmatic markers (oh really, sure, wow, totally, of course)
  M5: Sincerity violation (speaker cannot genuinely believe statement)
"""

import re
from dataclasses import dataclass


# ── Marker weights ──────────────────────────────────────────

MARKER_WEIGHTS = {
    "polarity_inversion": 0.30,
    "hyperbole": 0.20,
    "incongruity": 0.25,
    "pragmatic_markers": 0.10,
    "sincerity_violation": 0.15,
}

# ── Lexicons ────────────────────────────────────────────────

POSITIVE_WORDS = {
    "love", "great", "wonderful", "amazing", "fantastic", "brilliant",
    "excellent", "perfect", "awesome", "best", "beautiful", "incredible",
    "superb", "magnificent", "terrific", "fabulous", "delightful",
    "splendid", "marvelous", "outstanding", "enjoy", "glad", "happy",
    "thrilled", "excited", "lucky", "fortunate", "blessed",
}

NEGATIVE_WORDS = {
    "hate", "terrible", "awful", "horrible", "worst", "disgusting",
    "pathetic", "miserable", "dreadful", "catastrophe", "disaster",
    "fail", "failed", "failure", "broken", "ruined", "destroyed",
    "cancelled", "canceled", "crash", "die", "died", "dead",
    "loss", "lost", "pain", "suffering", "ugly", "stupid",
}

NEGATIVE_SITUATIONS = {
    "traffic", "delay", "wait", "waiting", "queue", "line",
    "monday", "tax", "taxes", "rain", "storm", "stuck",
    "overtime", "meeting", "meetings", "bug", "error",
    "dentist", "alarm", "fine", "penalty", "flat tire",
}

PRAGMATIC_MARKERS = {
    "oh really", "oh great", "oh wonderful", "oh fantastic",
    "oh sure", "oh yeah", "oh perfect", "oh brilliant",
    "sure because", "totally", "of course",
    "wow just wow", "yeah right", "yeah sure",
    "what a surprise", "how lovely", "how nice",
    "how wonderful", "just great", "just perfect",
    "just what i needed", "exactly what i wanted",
    "thanks a lot", "thanks so much",
    "as if", "like that matters",
}

HYPERBOLE_MARKERS = {
    "absolutely", "literally", "nothing better than",
    "best thing ever", "always", "never", "every single",
    "just love", "so much fun", "thrilled to",
    "can't wait to", "my favorite thing",
    "nothing like", "couldn't be happier",
    "world's best", "greatest ever",
}


@dataclass
class SarcasmResult:
    """Result of sarcasm analysis."""
    is_sarcastic: bool
    confidence: float          # 0.0 - 1.0
    score: float               # raw score 0.0 - 1.0
    markers_found: dict        # marker_name → bool
    markers_evidence: dict     # marker_name → explanation
    explanation: str           # human-readable summary


def detect_sarcasm_heuristic(text: str, context: str = "") -> SarcasmResult:
    """
    Fast heuristic sarcasm detection using 5-marker framework.

    No LLM calls — pure lexicon + pattern matching.
    Use as pre-filter before LLM-based analysis.
    """
    text_lower = text.lower().strip()
    words = set(text_lower.split())

    markers_found = {}
    markers_evidence = {}

    # ── M1: Polarity inversion ─────────────────────────
    pos_found = words & POSITIVE_WORDS
    neg_found = words & (NEGATIVE_WORDS | NEGATIVE_SITUATIONS)
    has_inversion = bool(pos_found and neg_found)
    markers_found["polarity_inversion"] = has_inversion
    if has_inversion:
        markers_evidence["polarity_inversion"] = (
            f"Positive ({', '.join(pos_found)}) + Negative ({', '.join(neg_found)})"
        )

    # ── M2: Hyperbole ──────────────────────────────────
    has_hyperbole = any(m in text_lower for m in HYPERBOLE_MARKERS)
    markers_found["hyperbole"] = has_hyperbole
    if has_hyperbole:
        found = [m for m in HYPERBOLE_MARKERS if m in text_lower]
        markers_evidence["hyperbole"] = f"Hyperbole markers: {', '.join(found[:3])}"

    # ── M3: Incongruity ───────────────────────────────
    # Heuristic: positive sentiment about inherently negative things
    neg_topics = words & NEGATIVE_SITUATIONS
    pos_sentiment = words & POSITIVE_WORDS
    has_incongruity = bool(neg_topics and pos_sentiment)
    markers_found["incongruity"] = has_incongruity
    if has_incongruity:
        markers_evidence["incongruity"] = (
            f"Positive sentiment ({', '.join(pos_sentiment)}) "
            f"about negative topic ({', '.join(neg_topics)})"
        )

    # ── M4: Pragmatic markers ──────────────────────────
    has_pragmatic = any(m in text_lower for m in PRAGMATIC_MARKERS)
    markers_found["pragmatic_markers"] = has_pragmatic
    if has_pragmatic:
        found = [m for m in PRAGMATIC_MARKERS if m in text_lower]
        markers_evidence["pragmatic_markers"] = f"Markers: {', '.join(found[:3])}"

    # ── M5: Sincerity violation ────────────────────────
    # Heuristic: expressions of enjoyment about universally negative experiences
    sincerity_patterns = [
        r"i (?:just )?love .*(wait|traffic|tax|rain|monday|meeting|cancel)",
        r"(?:can't|cannot) wait (?:for|to) .*(monday|dentist|alarm|overtime)",
        r"(?:so|really) glad .*(broke|failed|lost|stuck|cancelled)",
        r"nothing better than .*(wait|traffic|queue|delay)",
    ]
    has_sincerity = any(re.search(p, text_lower) for p in sincerity_patterns)
    markers_found["sincerity_violation"] = has_sincerity
    if has_sincerity:
        markers_evidence["sincerity_violation"] = "Expression of enjoyment about negative experience"

    # ── Score ──────────────────────────────────────────
    score = sum(
        MARKER_WEIGHTS[m] for m, found in markers_found.items() if found
    )

    # Determine result
    if score >= 0.6:
        is_sarcastic = True
        confidence = min(1.0, score)
    elif score >= 0.3:
        is_sarcastic = True
        confidence = score
    else:
        is_sarcastic = False
        confidence = 1.0 - score

    # Build explanation
    active = [m for m, f in markers_found.items() if f]
    if is_sarcastic:
        explanation = (
            f"Sarcasm detected (score={score:.2f}). "
            f"Active markers: {', '.join(active)}."
        )
    else:
        explanation = (
            f"No sarcasm detected (score={score:.2f}). "
            f"{'No markers found.' if not active else f'Weak markers: {chr(44).join(active)}'}"
        )

    return SarcasmResult(
        is_sarcastic=is_sarcastic,
        confidence=round(confidence, 2),
        score=round(score, 2),
        markers_found=markers_found,
        markers_evidence=markers_evidence,
        explanation=explanation,
    )


# ── LLM-enhanced analysis prompt ───────────────────────

SARCASM_ANALYSIS_PROMPT = """Analyze this text for sarcasm using the 5-marker framework:

TEXT: "{text}"
CONTEXT: "{context}"

Evaluate each marker (present/absent + evidence):

M1 POLARITY INVERSION: Are positive words used in a negative context (or vice versa)?
M2 HYPERBOLE: Is there exaggeration disproportionate to the situation?
M3 INCONGRUITY: Does the statement contradict known facts or common sense?
M4 PRAGMATIC MARKERS: Are there sarcasm markers (oh really, sure, wow, etc.)?
M5 SINCERITY VIOLATION: Can the speaker genuinely believe what they're saying?

For each marker, respond:
[M1: PRESENT/ABSENT] Evidence: ...
[M2: PRESENT/ABSENT] Evidence: ...
[M3: PRESENT/ABSENT] Evidence: ...
[M4: PRESENT/ABSENT] Evidence: ...
[M5: PRESENT/ABSENT] Evidence: ...

Then:
[SARCASM SCORE: X.XX] (sum of marker weights: M1=0.30, M2=0.20, M3=0.25, M4=0.10, M5=0.15)
[VERDICT: SARCASTIC / NOT SARCASTIC / AMBIGUOUS]
[TARGET: what is being mocked/criticized, if sarcastic]
[INTENDED MEANING: what the speaker actually means]
"""
