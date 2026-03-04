"""
LLM-based Fallacy Signal Extraction — ERR + D1-D6 Domain-Aware.

Uses an LLM to classify fallacies through the Theory of Systems framework:
  1. Determine violation type (Type 1-5)
  2. Identify which D1-D6 domain is violated
  3. Identify which ERR component (Element/Role/Rule) is corrupted
  4. Map to specific fallacy ID from the 156-fallacy taxonomy

This mirrors the Coq-verified verify_reasoning pipeline from AI_FallacyDetector.v:
  structural verification → domain identification → failure mode → specific fallacy

Falls back to regex extract_signals() on LLM failure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from regulus.fallacies.detector import Signals, extract_signals as regex_extract_signals
from regulus.fallacies.taxonomy import FALLACIES, FallacyType, get_taxonomy_summary

logger = logging.getLogger(__name__)


# =============================================================================
#                           LLM RESPONSE MODEL
# =============================================================================

@dataclass
class LLMExtractionResult:
    """Result from LLM-based signal extraction."""
    signals: Signals
    primary_fallacy_id: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: str = ""
    used_llm: bool = True
    # ERR analysis fields
    domain: Optional[str] = None          # D1-D6 or T1/T3/T4
    err_component: Optional[str] = None   # Element/Role/Rule
    failure_mode: Optional[str] = None    # D1.1-D6.4


# =============================================================================
#                    SYSTEM PROMPT — ERR + D1-D6 Framework
# =============================================================================

# Legacy flat-signal prompt (kept for backward compat)
SYSTEM_PROMPT_LEGACY = """\
You are a Logic Censor — a formal fallacy detection system based on the \
Theory of Systems framework (509 Coq-verified theorems).

Your task: analyze a text for reasoning fallacies and extract structured signals.

## Signal Definitions (18 boolean signals)

1. attacks_person — Text attacks the arguer instead of the argument (name-calling, questioning motives/character)
2. addresses_argument — Text has logical structure (premises, connectors like "therefore", "because", evidence)
3. uses_tradition — Text appeals to tradition, history, "the way things have always been", or nature as justification
4. considers_counter — Text acknowledges counterarguments, limitations, or opposing evidence ("however", "although")
5. self_reference — Text uses circular self-validation ("I know I'm right because I believe I'm right", "trust me")
6. uses_emotion — Text manipulates through fear, pity, guilt, or outrage instead of reasoning
7. false_authority — Text appeals to irrelevant authority, divine mandate, or unqualified "experts" without evidence
8. false_dilemma — Text presents only two options when more exist ("either X or Y", "you must choose")
9. post_hoc_pattern — Text assumes causation from temporal sequence ("after X, therefore because of X")
10. slippery_slope — Text claims an action will inevitably lead to extreme consequences without justification
11. overgeneralizes — Text makes sweeping claims from limited evidence ("all X are Y", "nobody ever")
12. cherry_picks — Text selectively presents only supporting evidence while ignoring contradictions
13. whataboutism — Text deflects criticism by pointing to someone else's behavior ("what about them?")
14. circular — Text assumes its conclusion in its premises ("X is true because X")
15. bandwagon — Text appeals to popularity as proof ("everyone does it", "millions can't be wrong")
16. passive_hiding — Text uses passive voice to hide responsible agents ("mistakes were made")
17. moving_goalposts — Text shifts criteria after they're met ("that's not what I really meant")
18. sunk_cost — Text justifies continuing based on past investment rather than future value

## Taxonomy Summary

{taxonomy}

## Output Format

Return ONLY a JSON object:
{{
    "signals": {{
        "attacks_person": false,
        "addresses_argument": true,
        "uses_tradition": false,
        "considers_counter": false,
        "self_reference": false,
        "uses_emotion": false,
        "false_authority": false,
        "false_dilemma": false,
        "post_hoc_pattern": false,
        "slippery_slope": false,
        "overgeneralizes": false,
        "cherry_picks": false,
        "whataboutism": false,
        "circular": false,
        "bandwagon": false,
        "passive_hiding": false,
        "moving_goalposts": false,
        "sunk_cost": false
    }},
    "primary_fallacy_id": "D1_AD_HOMINEM or null if no fallacy",
    "confidence": 0.85,
    "reasoning": "One sentence explaining your classification"
}}

## Rules

- Be STRICT: absence of evidence for a signal = false
- If the text is valid reasoning with no fallacy, set ALL signals to false, primary_fallacy_id to null, confidence to 0.0
- If you detect a fallacy, primary_fallacy_id MUST be one of the IDs from the taxonomy
- confidence: 0.0 = no fallacy, 0.5 = uncertain, 0.7+ = confident detection
- considers_counter = true if the text acknowledges ANY limitation or opposing view
- addresses_argument = true if the text has ANY logical structure (not just assertions)
- You may detect multiple signals as true — primary_fallacy_id is the MOST IMPORTANT one
- Respond with JSON only, no markdown fences, no extra text"""


# =============================================================================
#       NEW: ERR + D1-D6 Domain-Aware Classification Prompt
# =============================================================================
#
# Based on AI_FallacyDetector.v verify_reasoning pipeline:
#   Step 1: Check violation type (pre-reasoning or within-reasoning)
#   Step 2: Identify domain (D1-D6) where reasoning fails
#   Step 3: Identify ERR corruption (Element/Role/Rule)
#   Step 4: Map to specific fallacy ID
#

SYSTEM_PROMPT_ERR = """\
You are a Logic Censor — a formal fallacy detection system based on the \
Theory of Systems framework (509 Coq-verified theorems).

Your task: classify a text's reasoning fallacy using the ERR (Elements/Roles/Rules) \
and D1-D6 domain framework. Follow this EXACT analysis sequence.

## STEP 1: Violation Type Check

Determine if the text contains a reasoning violation and what TYPE:

- **Type 1 (Condition Violation)**: Reasoning never properly begins — the text \
uses manipulation, emotional coercion, threats, appeals to irrelevant authority, \
or other bad-faith tactics instead of argument. The text substitutes pressure for logic.
- **Type 2 (Domain Violation)**: Reasoning begins but FAILS within a specific domain \
D1-D6. This is the most common type (105 of 156 fallacies).
- **Type 3 (Sequence Violation)**: The reasoning is circular — the conclusion is \
assumed in the premises, or the argument loops back on itself.
- **Type 4 (Syndrome)**: Cross-domain self-reinforcing pattern — confirmation bias, \
echo chamber, motivated reasoning.
- **No violation**: The text presents valid reasoning.

## STEP 2: Domain Identification (for Type 2)

If Type 2, determine WHICH domain fails. Each domain answers a specific question:

**D1 — Recognition: "What is actually here?"**
ERR corruption: Element (WHAT is being discussed is wrong)
Failure modes:
  D1.1 Object Deformation — distort/exaggerate the real claim (straw man)
  D1.2 Object Substitution — attack person instead of argument (ad hominem), redirect topic (red herring)
  D1.3 Data Filtration — cherry-pick evidence, ignore contradictions
  D1.4 Projection — impose internal biases onto external reality
  D1.5 Source Distortion — misrepresent or fabricate sources

**D2 — Clarification: "What exactly is this?"**
ERR corruption: Role (HOW terms/concepts function is wrong)
Failure modes:
  D2.1 Meaning Drift — same word used with different meanings (equivocation)
  D2.2 Hidden Agent — passive voice hides who is responsible
  D2.3 Incomplete Analysis — only two options presented when more exist (false dilemma)
  D2.4 Excessive Analysis — drown in irrelevant detail

**D3 — Framework: "How do we connect?"**
ERR corruption: Rule (the logical MODEL chosen is wrong)
Failure modes:
  D3.1 Category Mismatch — wrong type of model applied
  D3.2 Irrelevant Criterion — popularity, tradition, or novelty used as proof
  D3.3 Framework for Result — choose model specifically to reach predetermined answer

**D4 — Comparison: "How does it compare?"**
ERR corruption: Element (WHAT is compared is invalid)
Failure modes:
  D4.1 False Equation — unequal things treated as equal (false analogy, false equivalence)
  D4.2 Unstable Criteria — comparison criteria shift mid-argument
  D4.3 Comparison to Nonexistent — compare to ideal/impossible standard

**D5 — Inference: "What follows?"**
ERR corruption: Rule (the logical DERIVATION is wrong)
Failure modes:
  D5.1 Logical Gap — conclusion doesn't follow from premises (non sequitur, affirming consequent, denying antecedent)
  D5.2 Causal Error — mistaken cause-effect (post hoc, false cause, correlation≠causation)
  D5.3 Chain Error — inference chain breaks at a link (slippery slope)
  D5.4 Scale Error — wrong generalization level (hasty generalization, overgeneralization)

**D6 — Reflection: "Where doesn't it work?"**
ERR corruption: Rule (self-assessment of LIMITATIONS is wrong)
Failure modes:
  D6.1 Illusion of Completion — claim reasoning is finished when it isn't
  D6.2 Self-Assessment — misjudge own competence or knowledge
  D6.3 Past Investment — sunk cost reasoning
  D6.4 Immunization — block all testing/criticism (unfalsifiable claims, dogmatism)

## STEP 3: Specific Fallacy ID

{taxonomy}

## Output Format

Return ONLY a JSON object:
{{
    "violation_type": "type2",
    "domain": "D5",
    "failure_mode": "D5.2",
    "err_component": "Rule",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85,
    "reasoning": "The text assumes that because Y happened after X, X caused Y — a causal error in the inference domain."
}}

Field values:
- violation_type: "type1" | "type2" | "type3" | "type4" | "none"
- domain: "D1" | "D2" | "D3" | "D4" | "D5" | "D6" | null (null for Type 1/3/4/none)
- failure_mode: e.g. "D1.1", "D2.3", "D5.1" or null
- err_component: "Element" | "Role" | "Rule" | null
- primary_fallacy_id: exact ID from taxonomy, or null if no fallacy
- confidence: 0.0 (no fallacy) to 1.0 (certain)
- reasoning: one sentence explaining the classification

## Classification Rules

- Follow the step sequence: type → domain → failure mode → specific fallacy
- Type 1 bypasses domain analysis: if someone threatens or manipulates, it's Type 1 regardless of topic
- Type 3 is ONLY for circular reasoning (conclusion = premise)
- For Type 2: the domain tells you WHERE the error is; the failure mode tells you HOW; the fallacy ID tells you WHAT
- The ERR component tells you what's corrupted: Element (the WHAT), Role (the HOW), Rule (the WHY/connection)
- If credibility/authority is cited WITHOUT relevant expertise, that's Type 1 (T1B_APPEAL_TO_HEAVEN or D1_APPEAL_TO_AUTHORITY)
- If the argument distorts/exaggerates the opponent's position, that's D1.1 (straw man)
- If premises are irrelevant to the conclusion, that's D3.2 (irrelevant criterion) or D5.1 (logical gap)
- If formal logic structure is violated (affirming consequent, denying antecedent), that's D5.1
- If the text intentionally misrepresents reality, check D1 failure modes first
- confidence: 0.7+ = confident, 0.5-0.7 = uncertain, <0.5 = likely no fallacy
- Respond with JSON only, no markdown fences, no extra text"""


# =============================================================================
#        D6 TEAM LEAD VERIFICATION PROMPT (Pipeline Pass 2)
# =============================================================================
#
# Based on the P3 pipeline from HLE evaluation (claude/tender-murdock branch).
# D6 (Team Lead) reviews the initial classification and cross-checks against
# the ERR framework. Can override if the initial classification is inconsistent.

SYSTEM_PROMPT_D6_VERIFY = """\
You are the Team Lead (D6 — Reflection) in a structured reasoning system based on \
the Theory of Systems framework.

You are reviewing a PRIOR classification of a logical fallacy. Your job is to \
cross-check the classification and correct it if wrong.

## Your SPECIFIC Task

An analyst (Pass 1) has already classified a text. You will see:
1. The original text
2. The analyst's classification (violation_type, domain, failure_mode, fallacy_id, confidence, reasoning)

You must VERIFY or OVERRIDE the classification. Check for these common errors:

### ERROR 1: False Causality Over-prediction
The analyst often labels things as D5_POST_HOC (causal error) when there is NO temporal sequence.
D5_POST_HOC requires: "A happened, then B happened, therefore A caused B."
If there is no "after X, then Y" pattern, it is NOT post_hoc. Consider instead:
- D5_OVERGENERALIZATION (broad claim from limited evidence)
- D5_NON_SEQUITUR (conclusion doesn't follow from premises)
- D1_HALF_TRUTH (selective evidence)

### ERROR 2: Generalization Over-prediction
The analyst often labels things as D5_OVERGENERALIZATION when the real issue is different:
- If the text attacks a PERSON → D1_AD_HOMINEM family
- If the text uses EMOTION → T1B emotion family
- If the text cites AUTHORITY → T1B_APPEAL_TO_HEAVEN / D1_STAR_POWER

### ERROR 3: Missing Intentional Deception
Deliberate manipulation (gaslighting, big lie, dog whistle) is often missed.
If the text INTENTIONALLY misleads, check Type 1 manipulation IDs.

### ERROR 4: Missing Emotion
If the text uses fear, pity, guilt, or outrage to bypass logic, check T1B emotion IDs.
The analyst sometimes misses emotion because it also contains some reasoning.

### ERROR 5: Missing Credibility/Authority
If someone cites their credentials, divine authority, or "experts say" without evidence,
check T1B/D1 credibility IDs. The analyst often maps this to D5 instead.

### ERROR 6: OVERGENERALIZATION Over-prediction (CRITICAL — most common error)
D5_OVERGENERALIZATION is the MOST over-predicted fallacy. ONLY use it when the text EXPLICITLY:
- Makes a sweeping claim from LIMITED evidence ("all X are Y", "nobody ever", "always", "never")
- Extrapolates from a small sample to a large population
- Uses anecdotal evidence to make a universal claim
Do NOT use D5_OVERGENERALIZATION as a default. If the text:
- Attacks a person → D1_AD_HOMINEM (NOT overgeneralization)
- Cites irrelevant authority → T1B credibility IDs
- Uses emotional manipulation → T1B emotion IDs
- Has irrelevant premises → D1_RED_HERRING or D3 relevance IDs
- Misrepresents the opponent → D1_STRAW_MAN
- Is deliberately deceptive → T1B intentional IDs
- Draws wrong conclusion from valid premises → D5_NON_SEQUITUR

### ERROR 7: CONFIRMATION_BIAS Over-prediction
T4_CONFIRMATION_BIAS is a SYNDROME = cross-domain self-reinforcing cycle. ONLY use it when:
- The text shows SYSTEMATIC pattern of seeking only confirming evidence AND
- Actively dismissing ALL contradicting evidence AND
- This pattern spans multiple reasoning steps in the SAME text
If the text just shows ONE type of bias, use the specific domain fallacy instead:
- Selective evidence → D1_HALF_TRUTH or D1_CHERRY_PICKS
- Emotional reasoning → T1B_PLAYING_ON_EMOTION
- Authority claim → T1B_APPEAL_TO_HEAVEN

### ERROR 8: Missing Relevance/Red Herring
If the text introduces an IRRELEVANT topic to distract from the argument:
- Topic completely changes → D1_RED_HERRING
- Previous good behavior used to justify bad → D3_MORAL_LICENSING
- Only measured things count → D3_MEASURABILITY
- "Both sides" false balance → D4_TWO_SIDES
Do NOT label these as OVERGENERALIZATION or NON_SEQUITUR.

## Decision Protocol

1. Read the original text carefully
2. Read the analyst's classification
3. Check: does the analyst's domain + failure_mode MATCH what's actually happening?
4. If YES: keep the classification (set override=false)
5. If NO: provide your corrected classification (set override=true)

## Output Format

Return ONLY a JSON object:
{{
    "override": false,
    "verification_reasoning": "The analyst correctly identified D5.2 causal error because the text says 'after we changed X, Y improved'",
    "violation_type": "type2",
    "domain": "D5",
    "failure_mode": "D5.2",
    "err_component": "Rule",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85
}}

If overriding:
{{
    "override": true,
    "verification_reasoning": "The analyst said D5_POST_HOC but there is no temporal sequence. The text actually attacks the person's character → D1_AD_HOMINEM.",
    "violation_type": "type2",
    "domain": "D1",
    "failure_mode": "D1.2",
    "err_component": "Element",
    "primary_fallacy_id": "D1_AD_HOMINEM",
    "confidence": 0.90
}}

{taxonomy}

Rules:
- Be PRECISE about what the text actually says
- Don't override if the original classification is reasonable
- Override confidently when you find a clear mismatch
- Respond with JSON only, no markdown fences"""


# =============================================================================
#  D6 TL PROMPT — tuned for MULTIGATE error patterns (from 50-sample analysis)
# =============================================================================

SYSTEM_PROMPT_MULTIGATE_D6_TL = """\
You are the Team Lead (D6 — Reflection) reviewing a multi-gate classification.

A worker classified a text through gates: G1(Type1?) → G2(Type3?) → G3(Type4?) → G5(Domain→ID).
You see the worker's output and must VERIFY or OVERRIDE it.

## KNOWN ERROR PATTERNS (from empirical analysis)

### ERR-1: G2 OVER-TRIGGER — Circular reasoning false positives
The worker's Gate 2 catches "circular reasoning" too aggressively.
These are NOT circular reasoning:
- Loaded/complex questions ("Have you stopped X?") → check T1A_COMPLEX_QUESTION or D1_STRAW_MAN
- "If A then B, therefore B" (affirming consequent) → D5_NON_SEQUITUR, fallacy of LOGIC
- Tautologies used as examples/metaphors → consider the text's INTENT, not surface form
- Texts that DESCRIBE circularity without BEING circular
CIRCULAR REASONING requires: the CONCLUSION is smuggled into the PREMISES.

### ERR-2: D1_IDENTITY_FALLACY over-prediction
The worker puts too many things into D1_IDENTITY_FALLACY (judging by group identity).
Check if the text actually:
- Makes a sweeping claim about ALL members of a group → D5_OVERGENERALIZATION (faulty generalization)
- Exaggerates/distorts someone's position → D1_STRAW_MAN (fallacy of extension)
- Uses stereotypes to ATTACK a person → D1_AD_HOMINEM
D1_IDENTITY_FALLACY = "your GROUP membership makes your argument invalid" — not just mentioning groups.

### ERR-3: "Intentional" fallacies missed
Deliberate deception is the hardest category. Look for:
- Loaded questions designed to trap → T1A_COMPLEX_QUESTION
- Deliberate oversimplification to mislead → D2_SNOW_JOB or D2_REDUCTIONISM
- Gaslighting / big lie → T1B_GASLIGHTING, T1B_BIG_LIE
- Moving goalposts → D3_MOVING_GOALPOSTS
- Dog whistles → T1B_DOG_WHISTLE
If the text seems DESIGNED to mislead (not accidentally wrong), flag intentional IDs.

### ERR-4: "Fallacy of extension" missed
Distorting/exaggerating the opponent's argument is often misclassified:
- If someone's position is MISREPRESENTED → D1_STRAW_MAN
- If a complex argument is OVERSIMPLIFIED → D2_REDUCTIONISM
- If compared to an impossible ideal → D4_HERO_BUSTING
The worker often sees "D1 person mentioned" and picks AD_HOMINEM when it's STRAW_MAN.

### ERR-5: D5_NON_SEQUITUR sink
NON_SEQUITUR should be LAST RESORT. If the worker chose D5_NON_SEQUITUR, check:
- Is there a causal claim? → D5_POST_HOC (false causality)
- Is there a sweeping generalization? → D5_OVERGENERALIZATION
- Is the topic changed to distract? → D1_RED_HERRING (fallacy of relevance)
- Is the argument circular? → T3_CIRCULAR_REASONING
Only keep NON_SEQUITUR if the conclusion genuinely has NO logical connection to premises.

### ERR-6: Credibility/authority source blindness
When someone with a CONFLICT OF INTEREST makes a claim, the issue is SOURCE credibility:
- Product creator praising own product → T1B_STANDARD_VERSION or D6_DUNNING_KRUGER
- Biased expert recommending something they profit from → D1_TRANSFER
- "100% natural" claim by the manufacturer → this is credibility abuse, not just D3_APPEAL_TO_NATURE
Check WHO is making the claim. If they benefit → credibility family (D1/T1B).

## Your Decision

Read the original text + worker classification. Then:
1. If the classification is CORRECT → set override=false, explain briefly why it's right
2. If you find one of the above error patterns → set override=true, provide correct classification

Output ONLY JSON:
{{
    "override": false,
    "verification_reasoning": "Worker correctly identified X because Y",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85
}}

Or if overriding:
{{
    "override": true,
    "verification_reasoning": "Worker said X but the text actually does Y → Z",
    "primary_fallacy_id": "D1_STRAW_MAN",
    "domain": "D1",
    "confidence": 0.90
}}

{taxonomy}

Rules:
- Don't override if the worker's answer is reasonable, even if another answer is also possible
- Override CONFIDENTLY when you see a clear error pattern from ERR-1 through ERR-6
- Focus on WHAT THE TEXT ACTUALLY DOES, not surface keywords
- Respond with JSON only"""


# =============================================================================
#        CASCADE PROMPTS (Step 1: Type, Step 2: Domain+ID)
# =============================================================================
#
# Cascade approach: break the 156-fallacy classification into 2 focused steps.
# Data shows biggest accuracy loss is at Step 1 (Type): 100% → 70.8%.
# By making Type classification a SEPARATE, focused call, we recover ~29pp.

SYSTEM_PROMPT_CASCADE_STEP1 = """\
You are a Logic Censor. Your ONLY task: determine the VIOLATION TYPE of a \
reasoning error. There are exactly 5 types:

## Type 1: CONDITION VIOLATION (36 fallacies)
Reasoning NEVER properly begins. The text uses manipulation instead of argument:
- Emotional coercion (fear, pity, guilt, outrage)
- Threats or force ("do this or else")
- Appeals to irrelevant authority, divine mandate, credentials
- Deliberate deception (gaslighting, big lie, dog whistle, scripted messages)
- Bad faith (loaded questions, taboo topics, venue dismissal)

KEY TEST: Does the text SUBSTITUTE pressure/manipulation for logic?
If the text has NO genuine logical structure — just emotional/authority pressure → Type 1.

## Type 2: DOMAIN VIOLATION (105 fallacies) — MOST COMMON
Reasoning begins but FAILS within a specific logical step (D1-D6):
- D1: Wrong object (straw man, ad hominem, red herring, cherry picking)
- D2: Wrong definition (equivocation, false dilemma, passive voice)
- D3: Wrong framework (bandwagon, tradition, moving goalposts)
- D4: Wrong comparison (false analogy, double standard)
- D5: Wrong inference (post hoc, overgeneralization, non sequitur, slippery slope)
- D6: Wrong self-assessment (sunk cost, deliberate ignorance)

KEY TEST: Does the text attempt reasoning but make a LOGICAL error? → Type 2.

## Type 3: SEQUENCE VIOLATION (3 fallacies) — RARE
The conclusion is assumed in the premises. Reasoning is CIRCULAR:
- "X is true because X" (begging the question)
- The evidence IS the claim restated differently

KEY TEST: Can you find the conclusion hidden inside the premises? → Type 3.

## Type 4: SYNDROME (6 fallacies) — RARE
A SELF-REINFORCING cross-domain pattern spanning the ENTIRE text:
- Confirmation bias (systematically seek only confirming evidence)
- Echo chamber, groupthink
- Motivated reasoning

KEY TEST: Does the text show a SYSTEMATIC cycle of bias across multiple steps? → Type 4.
Type 4 is NOT just "having a bias" — it requires a REINFORCING LOOP.

## Type 5: CONTEXT-DEPENDENT (6 fallacies) — RARE
The method might be valid OR fallacious depending on context.

## Output Format

Return ONLY a JSON object:
{{
    "violation_type": "type2",
    "confidence": 0.85,
    "reasoning": "The text presents an argument but commits a logical error in the inference step."
}}

Rules:
- Type 2 is by far the most common (~65% of cases)
- Type 1 is second most common (~23% of cases)
- Types 3, 4, 5 are RARE (~12% combined)
- Do NOT use Type 4 unless you see a clear REINFORCING LOOP
- If the text uses EMOTION to bypass logic (not as supplement), that's Type 1
- If the text cites AUTHORITY without evidence, that's Type 1
- Respond with JSON only"""


def _build_cascade_step2_prompt(violation_type: str) -> str:
    """Build Step 2 prompt dynamically with ONLY fallacies of the classified type."""
    # Map violation_type string to FallacyType enum
    type_map = {
        "type1": FallacyType.T1_CONDITION_VIOLATION,
        "type2": FallacyType.T2_DOMAIN_VIOLATION,
        "type3": FallacyType.T3_SEQUENCE_VIOLATION,
        "type4": FallacyType.T4_SYNDROME,
        "type5": FallacyType.T5_CONTEXT_DEPENDENT,
    }

    fallacy_type = type_map.get(violation_type)
    if not fallacy_type:
        # Fallback: use all fallacies
        return _build_cascade_step2_full()

    # Collect fallacies of this type, organized by domain/failure_mode
    from collections import defaultdict
    by_domain = defaultdict(list)
    for fid, f in sorted(FALLACIES.items()):
        if f.fallacy_type == fallacy_type:
            key = f"{f.domain.name}: {f.failure_mode.name}" if f.failure_mode else f.domain.name
            by_domain[key].append(f"  - {f.id}: {f.name} — {f.description}")

    # Build the fallacy list
    fallacy_list_parts = []
    for domain_key in sorted(by_domain.keys()):
        fallacy_list_parts.append(f"\n### {domain_key}")
        fallacy_list_parts.extend(by_domain[domain_key])

    fallacy_list = "\n".join(fallacy_list_parts)
    count = sum(len(v) for v in by_domain.values())

    # Type-specific instructions
    if violation_type == "type1":
        type_desc = (
            "Type 1: CONDITION VIOLATION — reasoning never begins.\n"
            "The text uses manipulation instead of argument.\n\n"
            "Sub-categories:\n"
            "- T1A: Defective questions (loaded question, taboo, venue)\n"
            "- T1B: Manipulation tactics (threats, emotion, authority, deception)\n\n"
            "Focus on WHAT manipulation tactic is used."
        )
    elif violation_type == "type2":
        type_desc = (
            "Type 2: DOMAIN VIOLATION — reasoning fails within D1-D6.\n\n"
            "First identify the DOMAIN, then the specific fallacy:\n"
            "- D1 Recognition: WHAT is discussed is wrong (attack person, straw man, cherry pick)\n"
            "- D2 Clarification: HOW terms function is wrong (equivocation, false dilemma)\n"
            "- D3 Framework: WHICH logical model is wrong (bandwagon, tradition, goalposts)\n"
            "- D4 Comparison: WHAT is compared is invalid (false analogy, double standard)\n"
            "- D5 Inference: WHAT follows is wrong (post hoc, overgeneralization, non sequitur)\n"
            "- D6 Reflection: Self-assessment is wrong (sunk cost, deliberate ignorance)\n\n"
            "CRITICAL: D5 is NOT a catch-all. Only use D5 if the error is truly in the INFERENCE step.\n"
            "If the problem is with the INPUT (wrong object/person/data), that's D1.\n"
            "If the problem is with the FRAMEWORK (wrong criterion), that's D3."
        )
    elif violation_type == "type3":
        type_desc = "Type 3: SEQUENCE VIOLATION — the reasoning is circular."
    elif violation_type == "type4":
        type_desc = "Type 4: SYNDROME — cross-domain self-reinforcing pattern."
    else:
        type_desc = "Type 5: CONTEXT-DEPENDENT — valid only under certain conditions."

    return f"""\
You are a Logic Censor. The violation type has been confirmed as:

{type_desc}

Your task: identify the SPECIFIC fallacy from this list ({count} options).

## Available Fallacies
{fallacy_list}

## Output Format

Return ONLY a JSON object:
{{{{
    "domain": "D5",
    "failure_mode": "D5.2",
    "err_component": "Rule",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85,
    "reasoning": "The text claims causation from temporal sequence — a D5.2 causal error."
}}}}

Rules:
- Choose ONLY from the fallacies listed above
- For Type 2: first identify the DOMAIN, then narrow to the specific fallacy
- domain: "D1"|"D2"|"D3"|"D4"|"D5"|"D6" or null for non-domain types
- Be PRECISE about what the text actually says
- Respond with JSON only"""


# =============================================================================
#        MULTI-GATE PROMPTS (Elimination-by-Exclusion Architecture)
# =============================================================================
#
# Revised diagnostic algorithm: instead of checking domains at Step 2 (which
# lets LLM "invent" domain violations), we ELIMINATE simpler types first:
#   Gate 0: Binary (is there a violation?) — handled by detector.py
#   Gate 1: Is it Type 1? (manipulation replaces argument)  — yes/no
#   Gate 2: Is it Type 3? (sequence/circular)               — yes/no
#   Gate 3: Is it Type 4? (cross-domain syndrome)           — yes/no
#   Gate 4: Is it Type 5? (context-dependent)               — yes/no
#   Gate 5: GUARANTEED Type 2 → identify domain → FM → specific ID
#
# Domain identification comes LAST because:
# 1. It's the hardest (105 options) — needs deep understanding of domain structure
# 2. LLM can force-fit into domain if checked too early
# 3. Earlier gates are simple binary checks (yes/no + small set)
# 4. By elimination, anything reaching Gate 5 IS a domain violation

SYSTEM_PROMPT_MULTIGATE_G1 = """\
You are a Logic Censor. Your SINGLE task: determine if the text contains \
NO ARGUMENT AT ALL — just pure manipulation (Type 1 violation).

## Type 1: There Is NO Argument

Type 1 means the text is ENTIRELY manipulation with ZERO logical structure. \
No premises, no conclusion, no attempt at reasoning — just pressure, \
emotion, or deception standing alone.

Examples of PURE manipulation (Type 1 = YES):
- "Do this or you'll be fired." (pure threat, no argument)
- "Think of the starving children!" (pure emotional pressure, no premises)
- "The authorities have spoken — obey." (pure authority command, no reasoning)
- "You wouldn't understand, it's beyond your level." (pure dismissal)
- "Everyone knows this is true." (pure social pressure, no evidence offered)

## THE CRITICAL TEST

**Can you find even ONE premise→conclusion structure?**

If YES → **NOT Type 1**. Even a terrible argument is still an argument.

Type 1 is the ABSENCE of argument, not a BAD argument.

## NOT Type 1 — these all contain arguments (even bad ones):

- "You're ugly, so your opinion is wrong" → BAD argument, but HAS structure \
(premise: you're ugly; conclusion: opinion is wrong) → Type 2 (ad hominem)
- "Everyone does X, so X must be right" → HAS structure (premise: popularity; \
conclusion: correctness) → Type 2 (bandwagon)
- "He's a criminal, so his policy ideas are bad" → HAS structure \
(premise: character; conclusion: policy quality) → Type 2 (ad hominem)
- "40 million people can't be wrong" → HAS structure (premise: number; \
conclusion: correctness) → Type 2 (ad populum)
- "After X, Y happened, so X caused Y" → HAS structure → Type 2 (post hoc)
- "All X are Y because I saw one X that was Y" → HAS structure → Type 2

## STRICT CRITERIA — Type 1 is RARE

Answer YES *only* if:
1. There is NO premise→conclusion structure ANYWHERE in the text
2. The text is PURELY manipulation — threats, emotional pressure, commands, \
   or deception with NO reasoning whatsoever
3. You CANNOT identify even one claim supported by even one reason

If in doubt → answer NO. Most texts with fallacies still CONTAIN arguments.

## Output

Return ONLY JSON:
{
    "is_type1": false,
    "confidence": 0.85,
    "reasoning": "One sentence explanation"
}"""

SYSTEM_PROMPT_MULTIGATE_G2 = """\
You are a Logic Censor. Your SINGLE task: determine if the reasoning \
violates SEQUENCE (Type 3 — circular or backward reasoning).

## Type 3: Sequence Violations (3 fallacies)

The Order Law requires reasoning to move FORWARD: D1→D2→D3→D4→D5→D6.
Type 3 means this order is broken:

1. **Rationalization (A Priori)**: The conclusion was decided BEFORE examining \
evidence. Reasoning runs BACKWARD (D5→D1) — premises are selected to justify \
a predetermined answer.

2. **Circular Reasoning**: The conclusion IS the premise — the same concept \
restated in different words. No forward progress — the argument loops.

3. **Burden Shifting**: Instead of the claimer proving their point, they demand \
the opponent disprove it. The argumentative direction is INVERTED.

## FOUR FORMS of Circular Reasoning

Circularity is NOT limited to literal word-for-word repetition. Look for:

**A. Literal repetition**: "X because X." Same words in premise and conclusion.
   Example: "The Bible is true because it is the word of God, and we know it \
is the word of God because the Bible says so."

**B. Synonym circularity**: Premise and conclusion use DIFFERENT WORDS for the \
SAME concept. "A is B" where A and B mean the same thing.
   Example: "Something that kills is deadly." ("kills" = "deadly" = same concept)
   Example: "Poverty exists because of poor people." (poverty = being poor)
   Test: Can you replace one word with the other without changing meaning?

**C. Concept circularity**: The CAUSE is just the EFFECT restated. The \
"explanation" is the thing being explained in different words.
   Example: "The Philippines is in poverty because of poor people." \
(poverty → poor people → poverty = circular)
   Example: "He sleeps because he is tired." (if tired = needs sleep)
   Test: Does the "because" clause just RESTATE the thing being explained?

**D. Presupposition circularity**: A question ASSUMES its own conclusion as \
a given fact — the "answer" is already built into the question itself.
   Example: "Have you stopped cheating on exams?" (assumes you WERE cheating)
   Example: "Why is this approach ineffective?" (assumes it IS ineffective)
   Test: Does the question BUILD IN the very conclusion it pretends to investigate?
   NOTE: Not every loaded question is circular. The question must CONTAIN the \
conclusion it claims to be asking about. A question with mere bias is NOT circular.

## Key test

Ask: "Is the CONCLUSION just the PREMISE expressed differently?"

This includes:
- Same words repeated → YES
- Synonyms used (kills/deadly, poverty/poor) → YES
- Cause = effect restated ("poverty because of poor people") → YES
- Question assumes its own answer ("stopped doing X?" assumes X was done) → YES

NOT circular:
- Bad reasoning that moves FORWARD (wrong conclusion from real premises) → Type 2
- Overgeneralization, false causality, bad analogy → these move forward, just badly

## STRICT CRITERIA — Type 3 is RARE (~10% of cases, only 3 fallacies)

These are NOT Type 3:
- Overgeneralization from limited evidence → Type 2 (D5.4)
- False causality where cause ≠ effect → Type 2 (D5.2)
- Predetermined political opinion + selective evidence → Type 2 (D1.3)
- Using popularity/tradition as proof → Type 2 (D3)

## Output

Return ONLY JSON:
{
    "is_type3": false,
    "confidence": 0.85,
    "reasoning": "One sentence explanation"
}

If Type 3, also specify which:
{
    "is_type3": true,
    "subtype": "rationalization|circular|burden_shifting",
    "primary_fallacy_id": "T3_RATIONALIZATION|T3_CIRCULAR_REASONING|T3_BURDEN_SHIFTING",
    "confidence": 0.85,
    "reasoning": "One sentence explanation"
}"""

SYSTEM_PROMPT_MULTIGATE_G3 = """\
You are a Logic Censor. Your SINGLE task: determine if the text shows a \
SYNDROME — a self-reinforcing cross-domain pattern (Type 4).

## Type 4: Syndromes (6 patterns)

A syndrome is NOT a single error. It is a SYSTEM where multiple domains \
reinforce each other, creating a closed loop:

1. **Confirmation Bias**: D1 (see only confirming data) + D3 (choose confirming \
framework) + D4 (compare only favorably) → reinforcing cycle
2. **Echo Chamber**: D1 (filtered information) + D3 (shared framework) + \
D6 (no reflection) → self-sustaining bubble
3. **Groupthink**: D1 (conformity filters input) + D6 (dissent = betrayal) → \
social pressure suppresses critical thinking
4. **Cognitive Closure**: D6 blocks ALL revision — any uncertainty triggers \
discomfort, closure brings relief. Not one error but a system shutdown.
5. **Compartmentalization**: Contradictory beliefs held in separate "compartments" \
— A and not-A both accepted without conflict
6. **Motivated Reasoning**: ALL domains distorted toward desired conclusion — \
not one wrong step but a pervasive directional bias

## Key test

Ask: "Is this ONE error in ONE step, or a SELF-REINFORCING PATTERN across \
multiple reasoning steps?"

- Single error (even big) → **NOT Type 4** (probably Type 2)
- Multiple errors that REINFORCE each other in a LOOP → **Type 4: YES**
- "Having a bias" is NOT Type 4. The bias must create a CLOSED CYCLE.

## Output

Return ONLY JSON:
{
    "is_type4": false,
    "confidence": 0.85,
    "reasoning": "One sentence explanation"
}

If Type 4:
{
    "is_type4": true,
    "primary_fallacy_id": "T4_CONFIRMATION_BIAS|T4_ECHO_CHAMBER|T4_GROUPTHINK|T4_COGNITIVE_CLOSURE|T4_COMPARTMENTALIZATION|T4_MOTIVATED_REASONING",
    "confidence": 0.85,
    "reasoning": "One sentence explanation"
}"""

SYSTEM_PROMPT_MULTIGATE_G5_DOMAIN = """\
You are a Logic Censor. The text has been confirmed as a DOMAIN VIOLATION \
(Type 2). All other types have been excluded.

Your task: determine WHICH DOMAIN (D1-D6) contains the primary error.

## The Six Domains of Reasoning

Reasoning traverses six cognitive territories in sequence: D1→D2→D3→D4→D5→D6. \
Each domain has a FUNCTION (what cognitive operation it performs), a PRINCIPLE \
(the logical law it applies), and characteristic ERRORS (what goes wrong).

**D1 — Recognition: "What is actually here?"**
FUNCTION: Fixation of what is present — consciousness meets what presents itself.
PRINCIPLE: Presence — see A as A, not as projected B (Law of Identity applied to perception).
REALITY ASPECT: Givenness — reality presents itself for encounter.
ERR = Element (the OBJECT of reasoning is wrong).
DIAGNOSTIC: "Is the reasoner working with what is ACTUALLY there, or with a \
distortion/substitution/projection of it?"
ERRORS: Projection onto data (seeing what you expect), selective attention \
(filtering data by bias), substitution (attacking person not argument), \
distortion (straw man), irrelevance (red herring), half-truth (cherry picking).
COMPLETION: All relevant material received without addition or subtraction.

**D2 — Clarification: "What exactly is this?"**
FUNCTION: Understanding of what was recognized — grasping what things ARE.
PRINCIPLE: Infinite Questions — hold meaning stable throughout reasoning \
(Law of Identity applied to semantics + Law of Sufficient Reason for depth).
REALITY ASPECT: Determinateness — things have definite natures.
ERR = Role (HOW terms/concepts function is wrong).
DIAGNOSTIC: "Are ALL key terms stable in meaning throughout the argument? \
Is analysis deep enough for the purpose?"
ERRORS: Equivocation (term shifts meaning mid-argument), premature closure \
(stops clarifying too early), definitional circularity (defining X by X), \
false dilemma (options artificially limited), ambiguity exploitation.
COMPLETION: Key terms defined identically for all parties, equivocation \
excluded, hidden assumptions explicated.

**D3 — Framework Selection: "By what standard do we evaluate?"**
FUNCTION: Determination of the coordinate system for comparison — choosing \
the analytical lens.
PRINCIPLE: Objectivity — seeking truth excludes seeking confirmation \
(Law of Non-Contradiction: cannot simultaneously seek truth AND confirmation).
REALITY ASPECT: Multi-aspectuality — the same phenomenon admits multiple \
legitimate frameworks.
ERR = Rule (the EVALUATIVE MODEL is wrong).
DIAGNOSTIC: "Is the framework appropriate for the subject? Was it CHOSEN \
consciously, or imposed unconsciously by bias?"
ERRORS: Unconscious framework imposition, framework chosen for confirmation \
(not truth), wrong type of framework (category error), irrelevant criterion \
(popularity, tradition, nature, emotion, effort), framework smuggling.
COMPLETION: Framework explicitly selected with awareness of alternatives.

**D4 — Comparison: "Is the comparison valid?"**
FUNCTION: Application of framework to material — tracing relations between \
things under the chosen framework.
PRINCIPLE: Presence (operational) — A remains A throughout the comparison \
process (Law of Identity applied to operations).
REALITY ASPECT: Connectedness — things are related to each other.
ERR = Element (WHAT is compared is invalid).
DIAGNOSTIC: "Are the things being compared GENUINELY comparable under the \
same criteria? Do comparison criteria stay FIXED throughout?"
ERRORS: False analogy (unlike things treated as alike), false balance \
(unequal things given equal weight), double standard (criteria shift), \
comparison to impossible ideal (hero busting), selective comparison.
COMPLETION: All relevant comparisons made with consistent criteria.

**D5 — Inference: "Does the conclusion follow?"**
FUNCTION: Extraction of what follows from comparison — drawing conclusions \
from established grounds.
PRINCIPLE: Rationalism — conclusions must follow from sufficient grounds \
(Law of Sufficient Reason applied to derivation).
REALITY ASPECT: Necessity — one thing follows from another.
ERR = Rule (the logical DERIVATION is wrong).
DIAGNOSTIC: "Does the conclusion follow from the premises with the claimed \
degree of certainty? Does it claim MORE than the evidence supports?"
ERRORS: Non sequitur (conclusion doesn't follow), false cause / post hoc \
(mistaken causation), slippery slope (chain breaks), overgeneralization \
(some→all), argument from ignorance (absence→proof), affirming consequent.
COMPLETION: Conclusion formulated with appropriate certainty marking.

**D6 — Reflection: "What are the limits?"**
FUNCTION: Comprehension of the path traveled and its limits — knowing where \
one stands and where boundaries lie.
PRINCIPLE: Limitation — every answer has scope, rests on assumptions, and \
opens new questions (Law of Excluded Middle: applies or doesn't).
REALITY ASPECT: Inexhaustibility — reality exceeds every grasp.
ERR = Rule (SELF-ASSESSMENT is wrong).
DIAGNOSTIC: "Does the reasoner acknowledge the BOUNDARIES and ASSUMPTIONS \
of their conclusion? Or do they treat a provisional result as final?"
ERRORS: Overconfidence (ignoring limits), premature closure (provisional→final), \
rationalization (post-hoc justification mimicking reflection), excessive doubt \
(paralysis), unfalsifiability (immunized from testing), sunk cost.
COMPLETION: Boundaries recognized, assumptions identified, next cycle prepared.

## COMMON CONFUSIONS — Domain Boundaries

**D1 vs D5**: If someone attacks a PERSON instead of their argument, that is D1 \
(the object of reasoning is substituted) — NOT D5. D5 is about the logical step \
from premises to conclusion. D1 is about what ENTERS the argument. \
Test: "Is the problem with the INPUT (what's being discussed) or the OUTPUT \
(what conclusion is drawn)?"

**D1 vs D3**: Two tests:
1. "Is the data itself distorted, or is the standard of judgment wrong?" \
If someone selectively presents EVIDENCE (cherry picking) → D1. \
If someone uses the wrong CRITERION (popularity, tradition, nature) → D3.
2. "WHO is making the claim, and do they BENEFIT from the conclusion?" \
If the SOURCE of the argument is biased, self-interested, or falsely \
authoritative — the problem is WHO is reasoning (D1), not which criterion \
they use (D3). Examples:
- "3 out of 4 real estate agents recommend X" — agents PROFIT from X → D1 \
  (biased source, not bandwagon — bandwagon is GENERAL popularity)
- "Our product is better" (said by manufacturer) → D1 (self-certification)
- "My sister is a teacher, she says this school is bad" → D1 (transferred \
  authority — being a teacher ≠ expert on THIS school)
- "Everyone does X, so X is right" (no specific source) → D3 (bandwagon)

**D3 vs D5**: If someone uses popularity as PROOF ("everyone does it, so it's right"), \
that is D3 (wrong framework/criterion) — NOT D5. D5 is about the logical derivation \
step AFTER a framework is chosen. \
Test: "Is the problem in WHICH standard is applied, or in HOW the conclusion \
is derived from valid premises?"

**D5 vs D1**: "He's wrong because he's bad" — this is D1 (attacking person = \
substituting object), NOT D5. Even though the conclusion doesn't follow, the \
PRIMARY error is substitution of what's being reasoned about.

## Decision Method

1. Read the text and identify the PRIMARY reasoning error
2. Ask: "WHERE does the error FIRST occur in the reasoning chain?"
   - If the wrong OBJECT is being reasoned about → D1 (Recognition)
   - If MEANING drifts or is unclear → D2 (Clarification)
   - If the wrong STANDARD/FRAMEWORK is applied → D3 (Framework)
   - If the COMPARISON is illegitimate → D4 (Comparison)
   - If the CONCLUSION doesn't follow from premises → D5 (Inference)
   - If LIMITS aren't acknowledged → D6 (Reflection)
3. The ERR component tells you what's corrupted (Element/Role/Rule)
4. When in doubt, choose the EARLIEST domain where the error occurs

## Output

Return ONLY JSON:
{
    "domain": "D5",
    "err_component": "Rule",
    "confidence": 0.85,
    "reasoning": "The error is in the inference step — the conclusion does not follow from the premises."
}"""


def _build_multigate_g5_id_prompt(domain: str) -> str:
    """Build Gate 5b+c prompt: failure mode + specific ID within confirmed domain."""
    from collections import defaultdict

    # Map domain string to Domain enum
    domain_enum_map = {
        "D1": "D1_RECOGNITION",
        "D2": "D2_CLARIFICATION",
        "D3": "D3_FRAMEWORK",
        "D4": "D4_COMPARISON",
        "D5": "D5_INFERENCE",
        "D6": "D6_REFLECTION",
    }

    from regulus.fallacies.taxonomy import Domain as DomainEnum, FailureMode

    domain_name = domain_enum_map.get(domain, "")
    target_domain = None
    for d in DomainEnum:
        if d.name == domain_name:
            target_domain = d
            break

    if not target_domain:
        # Fallback: return all Type 2 fallacies
        return _build_cascade_step2_prompt("type2")

    # Collect fallacies for this domain, grouped by failure mode
    by_fm = defaultdict(list)
    for fid, f in sorted(FALLACIES.items()):
        if f.domain == target_domain:
            fm_label = f"{f.failure_mode.value}: {f.failure_mode.name}" if f.failure_mode else "unknown"
            by_fm[fm_label].append(f"  - {f.id}: {f.name} — {f.description}")

    # Build the failure mode + fallacy list
    fm_parts = []
    for fm_key in sorted(by_fm.keys()):
        fm_parts.append(f"\n### {fm_key}")
        fm_parts.extend(by_fm[fm_key])

    fm_list = "\n".join(fm_parts)
    count = sum(len(v) for v in by_fm.values())

    # Domain descriptions for context
    domain_desc = {
        "D1": "Recognition — WHAT is being discussed. ERR = Element.",
        "D2": "Clarification — HOW terms/meanings function. ERR = Role.",
        "D3": "Framework Selection — WHICH evaluative standard. ERR = Rule.",
        "D4": "Comparison — validity of comparisons. ERR = Element.",
        "D5": "Inference — does conclusion follow. ERR = Rule.",
        "D6": "Reflection — limits and self-assessment. ERR = Rule.",
    }

    # Domain-specific differential guidance to prevent misclassification
    domain_differential = {
        "D1": """\

## Differential Guidance for D1 (Recognition)

D1 errors are about WHAT the reasoner sees/presents — the INPUT to reasoning is wrong.
Ask: "Is the problem with what DATA enters the argument, or with what CONCLUSION exits it?"

**TWO OPPOSITE DIRECTIONS — both are D1:**

Direction 1: ATTACK ON person (to DISMISS argument)
- If someone attacks a PERSON instead of their ARGUMENT → D1 (object substituted)
  - AD_HOMINEM: directly attacks the person making the argument
  - NAME_CALLING: uses derogatory labels instead of addressing the argument
  - TU_QUOQUE: "you do it too" — substitutes person's behavior for their argument
  - IDENTITY_FALLACY: judges argument by WHO made it (race, gender, group)
  - GUILT_BY_ASSOCIATION: judges by who the person associates with

Direction 2: APPEAL TO authority (to SUPPORT argument)
- If someone uses a PERSON'S STATUS to validate a claim → D1 (false authority as input)
  - TRANSFER: credential from one area used to validate claim in another area \
("my sister is a teacher, so she knows this school is bad" — teaching ≠ evaluating this school)
  - STAR_POWER: celebrity/expert endorsement outside their expertise
  - JUST_PLAIN_FOLKS: "I'm just like you" used as credibility
  - BLOOD_IS_THICKER: family/kinship bond used as evidence

**Key distinction: AD_HOMINEM dismisses via person; TRANSFER/STAR_POWER supports via person. \
Both are D1 because the PERSON replaces the ARGUMENT as the object of reasoning.**

- If someone DISTORTS what was said → D1 (the object is deformed)
  - STRAW_MAN: exaggerates or misrepresents the opponent's actual position
- If someone introduces IRRELEVANT material → D1 (wrong object)
  - RED_HERRING: changes the subject to distract
- If someone FILTERS data selectively → D1 (partial object)
  - CHERRY_PICKING, HALF_TRUTH, LYING_WITH_STATISTICS""",

        "D5": """\

## CRITICAL: Differential Guidance for D5 (Inference)

D5_NON_SEQUITUR (D5.1) is the LAST RESORT — use it ONLY when NO other D5 fallacy fits.

Ask these questions IN ORDER to narrow down:

**Q1: Is there a CAUSAL claim?** (A caused B, A leads to B, because of A then B)
→ If YES → failure mode D5.2 (Causal Error):
  - POST_HOC: "After A, B happened, so A caused B" — temporal sequence ≠ causation
  - SCAPEGOATING: blaming a person/group for a systemic problem
  - MAGICAL_THINKING: wishes/thoughts cause real events
  - PERSONALIZATION: "it happened because of ME"

**Q2: Is the conclusion LARGER than the evidence?** (some→all, few→everyone, one case→universal)
→ If YES → failure mode D5.4 (Scale Error):
  - OVERGENERALIZATION: "I saw one X that was Y, so all X are Y" — hasty generalization
  - ARGUMENT_FROM_IGNORANCE: "nobody proved it false, so it's true"
  - WISDOM_OF_CROWD: "everyone believes it, so it's true" (if framed as inference)
  - SILENT_MAJORITY: "the silent majority agrees with me" (unpolled claim)
  - ARGUMENT_FROM_CONSEQUENCES: "if X were true, bad things follow, so X is false"
  - WHERES_SMOKE: treating rumors as evidence

**Q3: Does the argument form a CHAIN with a broken link?** (A→B→C→...→Z)
→ If YES → failure mode D5.3 (Chain Error):
  - SLIPPERY_SLOPE: "if A then inevitably Z" without justifying intermediate steps
  - EXCLUDED_MIDDLE: "if not A, then B" — ignoring options between A and B

**Q4: NONE of the above fit?** The conclusion simply doesn't follow from the premises.
→ ONLY THEN → D5.1 (Logical Gap):
  - NON_SEQUITUR: genuine logical disconnect — premises and conclusion are unrelated""",

        "D3": """\

## Differential Guidance for D3 (Framework Selection)

D3 errors are about the STANDARD/CRITERION used to evaluate — not about the data (D1) \
or the conclusion (D5).
Ask: "Is the problem with WHICH LENS is being applied, or with WHAT is being looked at?"

- If the argument uses POPULARITY as proof → D3 (wrong criterion)
  - BANDWAGON: "everyone does it, so it's right"
- If the argument uses TRADITION as proof → D3 (irrelevant framework)
  - APPEAL_TO_TRADITION: "we've always done it this way"
- If the argument uses NATURE as proof → D3
  - APPEAL_TO_NATURE: "natural = good, artificial = bad"
- If the argument applies the WRONG TYPE of framework → D3
  - CATEGORY_MISMATCH: judging art by scientific criteria, or vice versa""",
    }

    diff_guide = domain_differential.get(domain, "")

    return f"""\
You are a Logic Censor. The domain has been confirmed as:

{domain}: {domain_desc.get(domain, '')}

Your task: identify the FAILURE MODE and SPECIFIC FALLACY ({count} options).

First determine the failure mode (HOW the domain is violated), then the exact fallacy.

## Failure Modes and Fallacies for {domain}
{fm_list}
{diff_guide}

## Output

Return ONLY JSON:
{{{{
    "failure_mode": "D5.2",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85,
    "reasoning": "The text mistakes temporal sequence for causation."
}}}}

Rules:
- Choose ONLY from the fallacies listed above
- First narrow to the failure mode, then pick the specific fallacy
- NON_SEQUITUR is the LAST RESORT — only if no other fallacy fits
- Be PRECISE about what the text actually says
- Respond with JSON only"""


def _build_cascade_step2_full() -> str:
    """Fallback Step 2 prompt with all 156 fallacies."""
    taxonomy = get_taxonomy_summary()
    return f"""\
You are a Logic Censor. Identify the specific fallacy.

## Taxonomy
{taxonomy}

## Output Format
Return ONLY a JSON object:
{{{{
    "domain": "D5",
    "failure_mode": "D5.2",
    "err_component": "Rule",
    "primary_fallacy_id": "D5_POST_HOC",
    "confidence": 0.85,
    "reasoning": "explanation"
}}}}

Rules:
- primary_fallacy_id MUST be an exact ID from the taxonomy
- Respond with JSON only"""


# =============================================================================
#                           EXTRACTOR CLASS
# =============================================================================

class LLMFallacyExtractor:
    """
    LLM-based fallacy signal extraction with ERR + D1-D6 framework.

    Six modes:
      - "err" (default): Uses domain-aware ERR classification prompt (1 LLM call).
        Better at type classification (maps through D1-D6 → failure mode → fallacy).
      - "pipeline": ERR + D6 Team Lead verification (2 LLM calls).
        Pass 1 = ERR extraction, Pass 2 = D6 cross-check and correction.
        Based on the P3 agent pipeline tested on HLE benchmarks.
      - "cascade": 2-step focused classification (2 LLM calls).
        Step 1 = Type classification (5 options), Step 2 = Specific fallacy
        within confirmed type (dynamic prompt with only relevant fallacies).
      - "multigate": Elimination-by-exclusion (2-4 LLM calls).
        Gates 1-4 eliminate Type 1,3,4,5 via binary questions.
        Gate 5 identifies domain → FM → ID (only for confirmed Type 2).
        Domain identification comes LAST to prevent force-fitting.
      - "multigate_tl": Multigate + D6 Team Lead review (3-5 LLM calls).
        Worker = multigate pipeline, TL = D6 error-aware reviewer.
        TL can override worker when known error patterns are detected.
      - "legacy": Uses flat 18-signal extraction prompt (1 LLM call).
        Original approach, good at binary detection.

    Usage:
        from regulus.llm.claude import ClaudeClient
        client = ClaudeClient(model="claude-sonnet-4-20250514")
        extractor = LLMFallacyExtractor(client, mode="cascade")
        result = await extractor.extract(text)
    """

    def __init__(
        self,
        client: Any,
        cache_enabled: bool = True,
        mode: str = "err",
    ):
        """
        Args:
            client: An LLMClient instance (ClaudeClient, OpenAIClient, etc.)
            cache_enabled: Whether to cache results by text hash
            mode: "err" for domain-aware classification, "pipeline" for ERR + D6 TL,
                  "legacy" for flat signals
        """
        from regulus.llm.client import LLMClient
        self.client: LLMClient = client
        self.mode = mode
        self._system_prompt: Optional[str] = None
        self._d6_system_prompt: Optional[str] = None
        self._multigate_tl_prompt: Optional[str] = None
        self._cache: Dict[int, LLMExtractionResult] = {}
        self.cache_enabled = cache_enabled
        # TL logging: stores detailed worker↔TL communication for diagnostics
        self.tl_log: list = []

    @property
    def system_prompt(self) -> str:
        """Lazily build system prompt with taxonomy summary."""
        if self._system_prompt is None:
            taxonomy = get_taxonomy_summary()
            if self.mode in ("err", "pipeline"):
                self._system_prompt = SYSTEM_PROMPT_ERR.format(taxonomy=taxonomy)
            else:
                self._system_prompt = SYSTEM_PROMPT_LEGACY.format(taxonomy=taxonomy)
        return self._system_prompt

    @property
    def d6_system_prompt(self) -> str:
        """Lazily build D6 TL verification prompt with taxonomy."""
        if self._d6_system_prompt is None:
            taxonomy = get_taxonomy_summary()
            self._d6_system_prompt = SYSTEM_PROMPT_D6_VERIFY.format(taxonomy=taxonomy)
        return self._d6_system_prompt

    @property
    def multigate_tl_prompt(self) -> str:
        """Lazily build multigate-specific D6 TL prompt with taxonomy."""
        if self._multigate_tl_prompt is None:
            taxonomy = get_taxonomy_summary()
            self._multigate_tl_prompt = SYSTEM_PROMPT_MULTIGATE_D6_TL.format(taxonomy=taxonomy)
        return self._multigate_tl_prompt

    async def extract(self, text: str) -> LLMExtractionResult:
        """
        Extract signals and identify fallacy using LLM.

        Falls back to regex extraction on any LLM error.

        Args:
            text: Text to analyze

        Returns:
            LLMExtractionResult with signals, fallacy ID, confidence
        """
        # Check cache
        if self.cache_enabled:
            text_hash = hash(text)
            if text_hash in self._cache:
                return self._cache[text_hash]

        try:
            if self.mode == "multigate_tl":
                result = await self._extract_via_multigate_tl(text)
            elif self.mode == "multigate":
                result = await self._extract_via_multigate(text)
            elif self.mode == "cascade":
                result = await self._extract_via_cascade(text)
            elif self.mode == "pipeline":
                result = await self._extract_via_pipeline(text)
            elif self.mode == "err":
                result = await self._extract_via_llm_err(text)
            else:
                result = await self._extract_via_llm_legacy(text)
        except Exception as e:
            logger.warning("LLM extraction failed, falling back to regex: %s", e)
            result = self._fallback_regex(text)

        # Cache result
        if self.cache_enabled:
            self._cache[hash(text)] = result

        return result

    async def extract_signals(self, text: str) -> Signals:
        """
        Extract only the Signals object (compatible with detector API).

        Args:
            text: Text to analyze

        Returns:
            Signals dataclass
        """
        result = await self.extract(text)
        return result.signals

    async def _extract_via_llm_err(self, text: str) -> LLMExtractionResult:
        """ERR + D1-D6 domain-aware extraction."""
        prompt = f'Classify this text using the ERR + D1-D6 framework:\n\n"{text}"'

        response = await self.client.generate(
            prompt=prompt,
            system=self.system_prompt,
        )

        parsed = _parse_json_response(response)

        # Build signals from ERR analysis for backward compatibility
        signals = _signals_from_err_analysis(parsed)

        result = LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=parsed.get("primary_fallacy_id"),
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=str(parsed.get("reasoning", "")),
            raw_response=response,
            used_llm=True,
            domain=parsed.get("domain"),
            err_component=parsed.get("err_component"),
            failure_mode=parsed.get("failure_mode"),
        )
        # Store violation_type for pipeline Pass 2
        result._violation_type = parsed.get("violation_type")
        return result

    async def _extract_via_pipeline(self, text: str) -> LLMExtractionResult:
        """
        Pipeline mode: ERR extraction (Pass 1) + D6 TL verification (Pass 2).

        Based on P3 agent pipeline from HLE benchmarks:
        - Pass 1: ERR domain-aware classification (same as "err" mode)
        - Pass 2: D6 Team Lead reviews Pass 1 output and can override

        This is a 2-call pipeline: 2x the cost of single-call, but significantly
        better at avoiding over-prediction of common categories (post_hoc, overgeneralization).
        """
        # ---- Pass 1: ERR extraction ----
        pass1_result = await self._extract_via_llm_err(text)

        # If Pass 1 found no fallacy, skip Pass 2
        if not pass1_result.primary_fallacy_id or pass1_result.confidence < 0.3:
            return pass1_result

        # ---- Pass 2: D6 Team Lead verification ----
        pass1_summary = json.dumps({
            "violation_type": getattr(pass1_result, '_violation_type', None)
                or ("type2" if pass1_result.domain else "unknown"),
            "domain": pass1_result.domain,
            "failure_mode": pass1_result.failure_mode,
            "err_component": pass1_result.err_component,
            "primary_fallacy_id": pass1_result.primary_fallacy_id,
            "confidence": pass1_result.confidence,
            "reasoning": pass1_result.reasoning,
        }, ensure_ascii=False)

        d6_prompt = (
            f'ORIGINAL TEXT:\n"{text}"\n\n'
            f'ANALYST CLASSIFICATION (Pass 1):\n{pass1_summary}\n\n'
            "Verify or override this classification. Return JSON."
        )

        try:
            d6_response = await self.client.generate(
                prompt=d6_prompt,
                system=self.d6_system_prompt,
            )
            d6_parsed = _parse_json_response(d6_response)

            if d6_parsed.get("override", False):
                # D6 overrides Pass 1
                logger.debug(
                    "D6 override: %s → %s (%s)",
                    pass1_result.primary_fallacy_id,
                    d6_parsed.get("primary_fallacy_id"),
                    d6_parsed.get("verification_reasoning", "")[:80],
                )
                signals = _signals_from_err_analysis(d6_parsed)
                return LLMExtractionResult(
                    signals=signals,
                    primary_fallacy_id=d6_parsed.get("primary_fallacy_id"),
                    confidence=float(d6_parsed.get("confidence", pass1_result.confidence)),
                    reasoning=f"[D6 override] {d6_parsed.get('verification_reasoning', '')}",
                    raw_response=d6_response,
                    used_llm=True,
                    domain=d6_parsed.get("domain"),
                    err_component=d6_parsed.get("err_component"),
                    failure_mode=d6_parsed.get("failure_mode"),
                )
            else:
                # D6 confirms Pass 1 — keep original but note verification
                pass1_result.reasoning = (
                    f"[D6 confirmed] {d6_parsed.get('verification_reasoning', '')} "
                    f"| Original: {pass1_result.reasoning}"
                )
                return pass1_result

        except Exception as e:
            # D6 failed — return Pass 1 result anyway
            logger.warning("D6 verification failed, using Pass 1 result: %s", e)
            return pass1_result

    async def _extract_via_cascade(self, text: str) -> LLMExtractionResult:
        """
        Cascade mode: 2-step focused classification.

        Step 1: Determine violation TYPE (5 options — focused prompt)
        Step 2: Identify specific fallacy within that type (dynamic prompt)

        This narrows the search space from 156 → ~5 → ~20-105 options,
        giving the LLM a much easier classification task at each step.
        """
        # ---- Step 1: Type classification (5 options) ----
        step1_prompt = f'Determine the violation type of this text:\n\n"{text}"'

        step1_response = await self.client.generate(
            prompt=step1_prompt,
            system=SYSTEM_PROMPT_CASCADE_STEP1,
        )

        step1_parsed = _parse_json_response(step1_response)
        violation_type = step1_parsed.get("violation_type", "type2")
        step1_confidence = float(step1_parsed.get("confidence", 0.5))
        step1_reasoning = str(step1_parsed.get("reasoning", ""))

        logger.debug(
            "Cascade Step 1: type=%s conf=%.2f (%s)",
            violation_type, step1_confidence, step1_reasoning[:80],
        )

        # If Step 1 says no violation, return early
        if violation_type == "none":
            return LLMExtractionResult(
                signals=Signals(),
                primary_fallacy_id=None,
                confidence=0.0,
                reasoning=f"[Cascade Step 1] No violation: {step1_reasoning}",
                raw_response=step1_response,
                used_llm=True,
            )

        # ---- Step 2: Specific fallacy within confirmed type ----
        step2_system = _build_cascade_step2_prompt(violation_type)

        step2_prompt = (
            f'The violation type has been confirmed as: {violation_type}\n'
            f'(Step 1 reasoning: {step1_reasoning})\n\n'
            f'Now identify the SPECIFIC fallacy in this text:\n\n"{text}"'
        )

        step2_response = await self.client.generate(
            prompt=step2_prompt,
            system=step2_system,
        )

        step2_parsed = _parse_json_response(step2_response)

        # Build result from Step 2
        signals = _signals_from_err_analysis({
            **step2_parsed,
            "violation_type": violation_type,
        })

        fallacy_id = step2_parsed.get("primary_fallacy_id")
        step2_confidence = float(step2_parsed.get("confidence", step1_confidence))
        step2_reasoning = str(step2_parsed.get("reasoning", ""))

        # Combine confidence: geometric mean of both steps
        combined_confidence = (step1_confidence * step2_confidence) ** 0.5

        return LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=fallacy_id,
            confidence=combined_confidence,
            reasoning=f"[Cascade {violation_type}→{step2_parsed.get('domain', '?')}] {step2_reasoning}",
            raw_response=step2_response,
            used_llm=True,
            domain=step2_parsed.get("domain"),
            err_component=step2_parsed.get("err_component"),
            failure_mode=step2_parsed.get("failure_mode"),
        )

    async def _extract_via_multigate(self, text: str) -> LLMExtractionResult:
        """
        Multi-gate elimination-by-exclusion classification.

        Gates 1-4 eliminate Type 1, 3, 4, 5 via binary (yes/no) questions.
        Gate 5 (only reached by exclusion) identifies domain → FM → specific ID.

        This solves the force-fit problem: the LLM can't "invent" a domain
        violation because domain classification only happens AFTER all simpler
        types have been explicitly ruled out.

        Worst case: 3 LLM calls (G1 no → G2 no → G5a domain → G5b ID)
        Best case:  1 LLM call (G1 yes → Type 1 with specific ID)
        """
        # ---- Gate 1: Is it Type 1 (manipulation)? ----
        g1_response = await self.client.generate(
            prompt=f'Is the reasoning in this text replaced by manipulation?\n\n"{text}"',
            system=SYSTEM_PROMPT_MULTIGATE_G1,
        )
        g1 = _parse_json_response(g1_response)
        g1_conf = float(g1.get("confidence", 0.5))

        if g1.get("is_type1", False) and g1_conf >= 0.80:
            # Confirmed Type 1 — get specific ID (strict: 0.80)
            logger.debug("Multigate G1: Type 1 confirmed (conf=%.2f)", g1_conf)
            return await self._multigate_resolve_type1(text, g1)

        # ---- Gate 2: Is it Type 3 (sequence violation)? ----
        g2_response = await self.client.generate(
            prompt=(
                f'Does this text reason BACKWARD or IN CIRCLES?\n\n"{text}"'
            ),
            system=SYSTEM_PROMPT_MULTIGATE_G2,
        )
        g2 = _parse_json_response(g2_response)
        g2_conf = float(g2.get("confidence", 0.5))

        if g2.get("is_type3", False) and g2_conf >= 0.95:
            # Confirmed Type 3 — ID already in gate response (very strict: 0.95)
            logger.debug("Multigate G2: Type 3 confirmed (conf=%.2f)", g2_conf)
            fallacy_id = g2.get("primary_fallacy_id", "T3_CIRCULAR_REASONING")
            signals = _signals_from_err_analysis({
                "violation_type": "type3",
                "primary_fallacy_id": fallacy_id,
            })
            return LLMExtractionResult(
                signals=signals,
                primary_fallacy_id=fallacy_id,
                confidence=g2_conf,
                reasoning=f"[MG G2: Type3] {g2.get('reasoning', '')}",
                raw_response=g2_response,
                used_llm=True,
            )

        # ---- Gate 3: Is it Type 4 (syndrome)? ----
        g3_response = await self.client.generate(
            prompt=(
                f'Does this text show a self-reinforcing cross-domain pattern?\n\n"{text}"'
            ),
            system=SYSTEM_PROMPT_MULTIGATE_G3,
        )
        g3 = _parse_json_response(g3_response)
        g3_conf = float(g3.get("confidence", 0.5))

        if g3.get("is_type4", False) and g3_conf >= 0.90:
            # Confirmed Type 4 (very strict: 0.90 — syndromes are rare)
            logger.debug("Multigate G3: Type 4 confirmed (conf=%.2f)", g3_conf)
            fallacy_id = g3.get("primary_fallacy_id", "T4_CONFIRMATION_BIAS")
            signals = _signals_from_err_analysis({
                "violation_type": "type4",
                "primary_fallacy_id": fallacy_id,
            })
            return LLMExtractionResult(
                signals=signals,
                primary_fallacy_id=fallacy_id,
                confidence=g3_conf,
                reasoning=f"[MG G3: Type4] {g3.get('reasoning', '')}",
                raw_response=g3_response,
                used_llm=True,
            )

        # ---- Gate 4: Type 5 is rare and context-dependent, skip for now ----
        # Type 5 fallacies are dual-coded as Type 2 domain violations anyway.
        # If needed, they'll be caught as their domain counterpart in Gate 5.

        # ---- Gate 5: By exclusion → Type 2 (domain violation) ----
        logger.debug("Multigate G5: Reached domain classification by exclusion")

        # Gate 5a: Which domain?
        g5a_response = await self.client.generate(
            prompt=(
                f'This text contains a domain violation (Type 2). '
                f'All other types have been ruled out.\n'
                f'Identify WHICH domain (D1-D6) contains the primary error.\n\n'
                f'"{text}"'
            ),
            system=SYSTEM_PROMPT_MULTIGATE_G5_DOMAIN,
        )
        g5a = _parse_json_response(g5a_response)
        domain = g5a.get("domain", "D5")
        g5a_conf = float(g5a.get("confidence", 0.5))
        err_component = g5a.get("err_component")

        logger.debug("Multigate G5a: domain=%s conf=%.2f", domain, g5a_conf)

        # Gate 5b+c: Failure mode + specific ID within domain
        g5b_system = _build_multigate_g5_id_prompt(domain)
        g5b_response = await self.client.generate(
            prompt=(
                f'Domain confirmed: {domain}\n'
                f'(Reasoning: {g5a.get("reasoning", "")})\n\n'
                f'Identify the specific failure mode and fallacy:\n\n"{text}"'
            ),
            system=g5b_system,
        )
        g5b = _parse_json_response(g5b_response)

        fallacy_id = g5b.get("primary_fallacy_id")
        failure_mode = g5b.get("failure_mode")
        g5b_conf = float(g5b.get("confidence", g5a_conf))

        # Combined confidence: geometric mean of domain + ID confidence
        combined_conf = (g5a_conf * g5b_conf) ** 0.5

        signals = _signals_from_err_analysis({
            "violation_type": "type2",
            "domain": domain,
            "failure_mode": failure_mode,
            "primary_fallacy_id": fallacy_id,
        })

        return LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=fallacy_id,
            confidence=combined_conf,
            reasoning=f"[MG G5: {domain}→{failure_mode}] {g5b.get('reasoning', '')}",
            raw_response=g5b_response,
            used_llm=True,
            domain=domain,
            err_component=err_component,
            failure_mode=failure_mode,
        )

    async def _multigate_resolve_type1(
        self, text: str, g1_result: dict
    ) -> LLMExtractionResult:
        """Resolve Type 1 to specific fallacy ID using cascade Step 2."""
        step2_system = _build_cascade_step2_prompt("type1")
        step2_response = await self.client.generate(
            prompt=(
                f'The violation type has been confirmed as: type1 (manipulation)\n'
                f'(Reasoning: {g1_result.get("reasoning", "")})\n\n'
                f'Identify the SPECIFIC manipulation tactic:\n\n"{text}"'
            ),
            system=step2_system,
        )
        step2 = _parse_json_response(step2_response)

        fallacy_id = step2.get("primary_fallacy_id")
        g1_conf = float(g1_result.get("confidence", 0.5))
        s2_conf = float(step2.get("confidence", g1_conf))
        combined_conf = (g1_conf * s2_conf) ** 0.5

        signals = _signals_from_err_analysis({
            "violation_type": "type1",
            "primary_fallacy_id": fallacy_id,
        })

        return LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=fallacy_id,
            confidence=combined_conf,
            reasoning=f"[MG G1: Type1] {step2.get('reasoning', '')}",
            raw_response=step2_response,
            used_llm=True,
            domain=step2.get("domain"),
            err_component=step2.get("err_component"),
            failure_mode=step2.get("failure_mode"),
        )

    async def _extract_via_multigate_tl(self, text: str) -> LLMExtractionResult:
        """
        Multigate + D6 Team Lead review.

        Pass 1: Full multigate pipeline (worker) → classification
        Pass 2: D6 TL reviews worker output with error-aware prompt → verify/override

        Logs detailed worker↔TL communication in self.tl_log for diagnostics.
        """
        import time as _time

        # ---- Pass 1: Worker (multigate) ----
        worker_start = _time.time()
        worker_result = await self._extract_via_multigate(text)
        worker_elapsed = _time.time() - worker_start

        # Build worker summary for TL
        worker_summary = json.dumps({
            "primary_fallacy_id": worker_result.primary_fallacy_id,
            "confidence": worker_result.confidence,
            "domain": worker_result.domain,
            "failure_mode": worker_result.failure_mode,
            "reasoning": worker_result.reasoning,
        }, ensure_ascii=False)

        # ---- Pass 2: D6 TL review ----
        tl_prompt = (
            f'ORIGINAL TEXT:\n"{text}"\n\n'
            f'WORKER CLASSIFICATION:\n{worker_summary}\n\n'
            f'Review this classification. Check for known error patterns (ERR-1 through ERR-6). '
            f'Return JSON with override=true/false.'
        )

        tl_start = _time.time()
        try:
            tl_response = await self.client.generate(
                prompt=tl_prompt,
                system=self.multigate_tl_prompt,
            )
            tl_parsed = _parse_json_response(tl_response)
            tl_elapsed = _time.time() - tl_start

            override = tl_parsed.get("override", False)
            tl_reasoning = tl_parsed.get("verification_reasoning", "")

            # Log the full interaction
            log_entry = {
                "text_preview": text[:100],
                "worker_id": worker_result.primary_fallacy_id,
                "worker_conf": worker_result.confidence,
                "worker_reasoning": worker_result.reasoning,
                "worker_elapsed": round(worker_elapsed, 1),
                "tl_override": override,
                "tl_reasoning": tl_reasoning,
                "tl_id": tl_parsed.get("primary_fallacy_id") if override else worker_result.primary_fallacy_id,
                "tl_conf": float(tl_parsed.get("confidence", worker_result.confidence)),
                "tl_elapsed": round(tl_elapsed, 1),
            }
            self.tl_log.append(log_entry)

            if override:
                new_id = tl_parsed.get("primary_fallacy_id", worker_result.primary_fallacy_id)
                new_conf = float(tl_parsed.get("confidence", worker_result.confidence))
                logger.info(
                    "TL override: %s → %s (%s)",
                    worker_result.primary_fallacy_id, new_id, tl_reasoning[:80],
                )
                signals = _signals_from_err_analysis({
                    "primary_fallacy_id": new_id,
                    "domain": tl_parsed.get("domain", worker_result.domain),
                })
                return LLMExtractionResult(
                    signals=signals,
                    primary_fallacy_id=new_id,
                    confidence=new_conf,
                    reasoning=(
                        f"[TL override: {worker_result.primary_fallacy_id}→{new_id}] "
                        f"{tl_reasoning}"
                    ),
                    raw_response=tl_response,
                    used_llm=True,
                    domain=tl_parsed.get("domain", worker_result.domain),
                    failure_mode=tl_parsed.get("failure_mode", worker_result.failure_mode),
                )
            else:
                # TL confirms — keep worker result but note confirmation
                worker_result.reasoning = (
                    f"[TL confirmed] {tl_reasoning} | {worker_result.reasoning}"
                )
                return worker_result

        except Exception as e:
            logger.warning("TL review failed, using worker result: %s", e)
            self.tl_log.append({
                "text_preview": text[:100],
                "worker_id": worker_result.primary_fallacy_id,
                "worker_conf": worker_result.confidence,
                "worker_reasoning": worker_result.reasoning,
                "tl_override": None,
                "tl_reasoning": f"ERROR: {e}",
                "tl_id": worker_result.primary_fallacy_id,
            })
            return worker_result

    async def _extract_via_llm_legacy(self, text: str) -> LLMExtractionResult:
        """Legacy flat-signal extraction (original approach)."""
        prompt = f'Analyze this text for reasoning fallacies:\n\n"{text}"'

        response = await self.client.generate(
            prompt=prompt,
            system=self.system_prompt,
        )

        parsed = _parse_json_response(response)
        signals = _parse_signals(parsed.get("signals", {}))

        return LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=parsed.get("primary_fallacy_id"),
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=str(parsed.get("reasoning", "")),
            raw_response=response,
            used_llm=True,
        )

    def _fallback_regex(self, text: str) -> LLMExtractionResult:
        """Fall back to regex-based extraction."""
        signals = regex_extract_signals(text)
        return LLMExtractionResult(
            signals=signals,
            primary_fallacy_id=None,
            confidence=0.0,
            reasoning="Regex fallback (LLM unavailable)",
            raw_response="",
            used_llm=False,
        )

    def clear_cache(self) -> int:
        """Clear the cache. Returns number of entries cleared."""
        n = len(self._cache)
        self._cache.clear()
        return n


# =============================================================================
#                           JSON PARSING HELPERS
# =============================================================================

def _parse_json_response(response: str) -> Dict[str, Any]:
    """
    Extract JSON from LLM response, handling markdown code blocks.

    Mirrors the pattern from regulus/llm/sensor.py:_parse_json_response.
    """
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

    # Fix double-brace issue from GPT-4o ({{ → {, }} → })
    if "{{" in text and "}}" in text:
        text = text.replace("{{", "{").replace("}}", "}")

    # Try direct parse
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    if parsed is None:
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                parsed = json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass

    if parsed is None:
        raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")

    # Validate fallacy ID if present
    if "primary_fallacy_id" in parsed and parsed["primary_fallacy_id"]:
        parsed["primary_fallacy_id"] = _validate_fallacy_id(parsed["primary_fallacy_id"])

    return parsed


# All valid fallacy IDs for validation
_VALID_IDS: set = set(FALLACIES.keys())


def _validate_fallacy_id(raw_id: Optional[str]) -> Optional[str]:
    """Validate and fix a fallacy ID from LLM output.

    1. If exact match in FALLACIES → return as-is
    2. If case-insensitive match → fix case
    3. If edit distance ≤ 2 from a valid ID → fix typo (e.g. D1_STRAM_MAN → D1_STRAW_MAN)
    4. If prefix matches a valid ID → return closest
    5. Otherwise → return as-is (will show as UNKNOWN in diagnostics)
    """
    if not raw_id:
        return raw_id

    # 1. Exact match
    if raw_id in _VALID_IDS:
        return raw_id

    # 2. Case-insensitive
    upper = raw_id.upper()
    for vid in _VALID_IDS:
        if vid.upper() == upper:
            logger.debug("ID case fix: %s → %s", raw_id, vid)
            return vid

    # 3. Edit distance ≤ 2 (simple Levenshtein)
    best_dist = 999
    best_match = None
    for vid in _VALID_IDS:
        d = _edit_distance(upper, vid.upper())
        if d < best_dist:
            best_dist = d
            best_match = vid
    if best_dist <= 2 and best_match:
        logger.info("ID fuzzy fix: %s → %s (dist=%d)", raw_id, best_match, best_dist)
        return best_match

    # 4. No match — return as-is
    logger.warning("Unknown fallacy ID from LLM: %s", raw_id)
    return raw_id


def _edit_distance(s1: str, s2: str) -> int:
    """Simple Levenshtein distance."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _parse_signals(raw: Dict[str, Any]) -> Signals:
    """Parse a dict of signal values into a Signals dataclass."""
    return Signals(
        attacks_person=bool(raw.get("attacks_person", False)),
        addresses_argument=bool(raw.get("addresses_argument", False)),
        uses_tradition=bool(raw.get("uses_tradition", False)),
        considers_counter=bool(raw.get("considers_counter", False)),
        self_reference=bool(raw.get("self_reference", False)),
        uses_emotion=bool(raw.get("uses_emotion", False)),
        false_authority=bool(raw.get("false_authority", False)),
        false_dilemma=bool(raw.get("false_dilemma", False)),
        post_hoc_pattern=bool(raw.get("post_hoc_pattern", False)),
        slippery_slope=bool(raw.get("slippery_slope", False)),
        overgeneralizes=bool(raw.get("overgeneralizes", False)),
        cherry_picks=bool(raw.get("cherry_picks", False)),
        whataboutism=bool(raw.get("whataboutism", False)),
        circular=bool(raw.get("circular", False)),
        bandwagon=bool(raw.get("bandwagon", False)),
        passive_hiding=bool(raw.get("passive_hiding", False)),
        moving_goalposts=bool(raw.get("moving_goalposts", False)),
        sunk_cost=bool(raw.get("sunk_cost", False)),
    )


def _signals_from_err_analysis(parsed: Dict[str, Any]) -> Signals:
    """
    Build backward-compatible Signals from ERR domain analysis.

    Maps domain + failure_mode + fallacy_id back to the 18 boolean signals
    so the existing cascade detector can still work as fallback.
    """
    fallacy_id = parsed.get("primary_fallacy_id") or ""
    domain = parsed.get("domain") or ""
    failure_mode = parsed.get("failure_mode") or ""
    vtype = parsed.get("violation_type") or ""

    # Default all false
    sig = Signals()

    # Map known fallacy IDs / domains / failure modes to signals
    fid = fallacy_id.upper()

    # D1 signals
    if "AD_HOMINEM" in fid or "TU_QUOQUE" in fid or "POISONING" in fid:
        sig.attacks_person = True
    if "WHATABOUT" in fid or "TU_QUOQUE" in fid:
        sig.whataboutism = True
    if "HALF_TRUTH" in fid or "CHERRY" in fid or "ANECDOTAL" in fid:
        sig.cherry_picks = True
    if "STRAW_MAN" in fid:
        sig.attacks_person = True  # arguable, but needed for cascade

    # D2 signals
    if "EITHER_OR" in fid or "FALSE_DILEMMA" in fid or failure_mode == "D2.3":
        sig.false_dilemma = True
    if "EQUIVOCATION" in fid or "AMPHIBOLY" in fid or failure_mode == "D2.1":
        pass  # No signal for equivocation in legacy
    if "PASSIVE" in fid or failure_mode == "D2.2":
        sig.passive_hiding = True

    # D3 signals
    if "BANDWAGON" in fid or failure_mode == "D3.2":
        sig.bandwagon = True
    if "TRADITION" in fid or "NOVELTY" in fid:
        sig.uses_tradition = True
    if "GOALPOSTS" in fid or "MOVING" in fid or failure_mode == "D3.3":
        sig.moving_goalposts = True

    # D5 signals
    if "POST_HOC" in fid or "FALSE_CAUSE" in fid or "CORRELATION" in fid or failure_mode == "D5.2":
        sig.post_hoc_pattern = True
    if "SLIPPERY" in fid or failure_mode == "D5.3":
        sig.slippery_slope = True
    if "OVERGENERALIZATION" in fid or "HASTY" in fid or failure_mode == "D5.4":
        sig.overgeneralizes = True

    # D6 signals
    if "SUNK_COST" in fid or failure_mode == "D6.3":
        sig.sunk_cost = True

    # Type 1 signals
    if "SCARE" in fid or "PITY" in fid or "FLATTERY" in fid or vtype == "type1":
        if "EMOTION" in fid or "SCARE" in fid or "PITY" in fid or "FEAR" in fid:
            sig.uses_emotion = True
    if "HEAVEN" in fid or "AUTHORITY" in fid or "APPEAL_TO_AUTHORITY" in fid:
        sig.false_authority = True

    # Type 3 signals
    if "CIRCULAR" in fid or vtype == "type3":
        sig.circular = True

    # Type 4 signals
    if "CONFIRMATION" in fid or vtype == "type4":
        pass  # Handled by cascade fallback

    # Meta: if any fallacy detected, the text does address argument
    if fallacy_id and vtype != "none":
        sig.addresses_argument = True

    return sig
