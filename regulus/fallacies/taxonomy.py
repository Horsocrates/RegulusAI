"""
Complete Fallacy Taxonomy: All 156 Violations.

Direct port from Coq-verified formalization:
  CompleteFallacyTaxonomy.v — 156 fallacies, counts verified by reflexivity
  DomainViolations_Complete.v — failure mode assignments
  AI_FallacyDetector.v — domain mapping, detection structures

Structure:
  Type 1: Violations of Conditions (36) — reasoning doesn't begin
  Type 2: Domain Violations (105) — reasoning fails within D1-D6
  Type 3: Violations of Sequence (3) — D1->D6 order broken
  Type 4: Syndromes (6) — self-reinforcing cross-domain corruption
  Type 5: Context-Dependent Methods (6) — valid only under conditions

Author: Horsocrates (Coq) -> Claude (Python port)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
#                           ENUMS (mirror Coq Inductive types)
# =============================================================================

class FallacyType(Enum):
    """Maps to Coq: Type 1-5 from CompleteFallacyTaxonomy.v"""
    T1_CONDITION_VIOLATION = 1   # Reasoning doesn't begin
    T2_DOMAIN_VIOLATION = 2      # Fails within a domain
    T3_SEQUENCE_VIOLATION = 3    # D1->D6 order broken
    T4_SYNDROME = 4              # Self-reinforcing corruption
    T5_CONTEXT_DEPENDENT = 5     # Valid only under conditions


class Domain(Enum):
    """Maps to Coq: Inductive Domain in AI_FallacyDetector.v"""
    D1_RECOGNITION = 1       # What is actually here?
    D2_CLARIFICATION = 2     # What exactly is this?
    D3_FRAMEWORK = 3         # How do we connect?
    D4_COMPARISON = 4        # How does it compare?
    D5_INFERENCE = 5         # What follows?
    D6_REFLECTION = 6        # Where doesn't it work?
    NONE = 0                 # For Type 1, 3, 4, 5 (pre/meta-domain)


class FailureMode(Enum):
    """
    Maps to Coq: Inductive FailureMode in AI_FallacyDetector.v
    23 failure modes across 6 domains.
    """
    # D1: Recognition (5 modes)
    D1_OBJECT_DEFORMATION = "D1.1"       # A -> A' (distort object)
    D1_OBJECT_SUBSTITUTION = "D1.2"      # A -> B (replace object)
    D1_DATA_FILTRATION = "D1.3"          # Selective data
    D1_PROJECTION = "D1.4"              # Impose internal onto external
    D1_SOURCE_DISTORTION = "D1.5"        # Corrupt the source
    # D2: Clarification (4 modes)
    D2_MEANING_DRIFT = "D2.1"           # Term changes meaning
    D2_HIDDEN_AGENT = "D2.2"            # Who did it?
    D2_INCOMPLETE_ANALYSIS = "D2.3"      # Too few options
    D2_EXCESSIVE_ANALYSIS = "D2.4"       # Drown in detail
    # D3: Framework Selection (3 modes)
    D3_CATEGORY_MISMATCH = "D3.1"        # Wrong type of model
    D3_IRRELEVANT_CRITERION = "D3.2"     # Criterion doesn't apply
    D3_FRAMEWORK_FOR_RESULT = "D3.3"     # Choose model to get answer
    # D4: Comparison (3 modes)
    D4_FALSE_EQUATION = "D4.1"           # Unequal things equated
    D4_UNSTABLE_CRITERIA = "D4.2"        # Criteria shift mid-comparison
    D4_COMPARISON_NONEXISTENT = "D4.3"   # Compare to ideal/nonexistent
    # D5: Inference (4 modes)
    D5_LOGICAL_GAP = "D5.1"             # Conclusion doesn't follow
    D5_CAUSAL_ERROR = "D5.2"            # Wrong cause-effect
    D5_CHAIN_ERROR = "D5.3"             # Chain of inference breaks
    D5_SCALE_ERROR = "D5.4"             # Wrong generalization level
    # D6: Reflection (4 modes)
    D6_ILLUSION_COMPLETION = "D6.1"      # Think you're done
    D6_SELF_ASSESSMENT = "D6.2"          # Misjudge own competence
    D6_PAST_INVESTMENT = "D6.3"          # Sunk cost reasoning
    D6_IMMUNIZATION = "D6.4"             # Block all testing
    # Meta (for Type 1, 3, 4, 5)
    CONDITION_BLOCKED = "T1"             # Reasoning never started
    SEQUENCE_BROKEN = "T3"               # Domain order violated
    SYNDROME = "T4"                      # Cross-domain corruption
    CONTEXT_DEPENDENT = "T5"             # Conditionally valid


class ManipulationCategory(Enum):
    """Maps to Coq: Inductive ManipulationCategory"""
    FORCE = "force"
    PITY = "pity"
    EMOTION = "emotion"
    BENEFIT = "benefit"
    PRESSURE = "pressure"
    FALSE_AUTHORITY = "false_authority"
    DISINFORMATION = "disinformation"
    DELEGATION = "delegation"
    FALSE_ETHOS = "false_ethos"
    BAD_FAITH = "bad_faith"
    DEFECTIVE_QUESTION = "defective_question"


class Severity(Enum):
    """Severity of the fallacy for diagnostics."""
    CRITICAL = "critical"    # Blocks reasoning entirely
    HIGH = "high"            # Major logical error
    MEDIUM = "medium"        # Significant but recoverable
    LOW = "low"              # Minor or context-dependent


# =============================================================================
#                           FALLACY DATACLASS
# =============================================================================

@dataclass(frozen=True)
class Fallacy:
    """
    A single classified fallacy.

    Mirrors the Coq record structure from DomainViolations_Complete.v:
      fallacy_domain : Domain
      fallacy_failure_mode : FailureMode
      + human-readable fields for diagnostics
    """
    id: str                          # Unique identifier (e.g., "D1_AD_HOMINEM")
    name: str                        # Human name (e.g., "Ad Hominem")
    fallacy_type: FallacyType        # Type 1-5
    domain: Domain                   # Which domain it violates
    failure_mode: FailureMode        # How it fails
    description: str                 # One-line description
    fix_prompt: str                  # Correction instruction
    severity: Severity = Severity.HIGH
    manipulation_category: Optional[ManipulationCategory] = None  # Type 1 only
    example: str = ""                # Example text exhibiting this fallacy


# =============================================================================
#           FAILURE MODE REGISTRY (maps to Coq failure_mode_name)
# =============================================================================

FAILURE_MODES: Dict[FailureMode, Dict[str, str]] = {
    # D1
    FailureMode.D1_OBJECT_DEFORMATION: {
        "name": "Object Deformation",
        "description": "The original object is distorted before reasoning begins (A -> A')",
        "domain": "D1: Recognition",
    },
    FailureMode.D1_OBJECT_SUBSTITUTION: {
        "name": "Object Substitution",
        "description": "The object is replaced entirely (A -> B, typically person for argument)",
        "domain": "D1: Recognition",
    },
    FailureMode.D1_DATA_FILTRATION: {
        "name": "Data Filtration",
        "description": "Selective data inclusion/exclusion biases the input",
        "domain": "D1: Recognition",
    },
    FailureMode.D1_PROJECTION: {
        "name": "Projection",
        "description": "Internal states imposed onto external objects",
        "domain": "D1: Recognition",
    },
    FailureMode.D1_SOURCE_DISTORTION: {
        "name": "Source Distortion",
        "description": "The information source itself is corrupted",
        "domain": "D1: Recognition",
    },
    # D2
    FailureMode.D2_MEANING_DRIFT: {
        "name": "Meaning Drift",
        "description": "A term silently changes meaning during reasoning",
        "domain": "D2: Clarification",
    },
    FailureMode.D2_HIDDEN_AGENT: {
        "name": "Hidden Agent",
        "description": "The responsible actor is obscured (passive voice, etc.)",
        "domain": "D2: Clarification",
    },
    FailureMode.D2_INCOMPLETE_ANALYSIS: {
        "name": "Incomplete Analysis",
        "description": "Too few options/categories considered",
        "domain": "D2: Clarification",
    },
    FailureMode.D2_EXCESSIVE_ANALYSIS: {
        "name": "Excessive Analysis",
        "description": "Overwhelm with irrelevant detail to obscure the point",
        "domain": "D2: Clarification",
    },
    # D3
    FailureMode.D3_CATEGORY_MISMATCH: {
        "name": "Category Mismatch",
        "description": "Applying a framework to the wrong type of problem",
        "domain": "D3: Framework",
    },
    FailureMode.D3_IRRELEVANT_CRITERION: {
        "name": "Irrelevant Criterion",
        "description": "Selection criterion doesn't apply to this domain",
        "domain": "D3: Framework",
    },
    FailureMode.D3_FRAMEWORK_FOR_RESULT: {
        "name": "Framework for Result",
        "description": "Framework chosen to guarantee desired conclusion",
        "domain": "D3: Framework",
    },
    # D4
    FailureMode.D4_FALSE_EQUATION: {
        "name": "False Equation",
        "description": "Fundamentally different things treated as equivalent",
        "domain": "D4: Comparison",
    },
    FailureMode.D4_UNSTABLE_CRITERIA: {
        "name": "Unstable Criteria",
        "description": "Comparison criteria shift during the comparison",
        "domain": "D4: Comparison",
    },
    FailureMode.D4_COMPARISON_NONEXISTENT: {
        "name": "Comparison with Nonexistent",
        "description": "Comparing to an ideal/fictional standard",
        "domain": "D4: Comparison",
    },
    # D5
    FailureMode.D5_LOGICAL_GAP: {
        "name": "Logical Gap",
        "description": "Conclusion does not follow from premises",
        "domain": "D5: Inference",
    },
    FailureMode.D5_CAUSAL_ERROR: {
        "name": "Causal Error",
        "description": "Wrong or fabricated cause-effect relationship",
        "domain": "D5: Inference",
    },
    FailureMode.D5_CHAIN_ERROR: {
        "name": "Chain Error",
        "description": "Chain of inferences breaks at some link",
        "domain": "D5: Inference",
    },
    FailureMode.D5_SCALE_ERROR: {
        "name": "Scale Error",
        "description": "Incorrect generalization level (too broad or too narrow)",
        "domain": "D5: Inference",
    },
    # D6
    FailureMode.D6_ILLUSION_COMPLETION: {
        "name": "Illusion of Completion",
        "description": "Believing the analysis is complete when it isn't",
        "domain": "D6: Reflection",
    },
    FailureMode.D6_SELF_ASSESSMENT: {
        "name": "Self-Assessment Distortion",
        "description": "Misjudging own competence or the quality of own reasoning",
        "domain": "D6: Reflection",
    },
    FailureMode.D6_PAST_INVESTMENT: {
        "name": "Past Investment Influence",
        "description": "Prior effort distorts current evaluation",
        "domain": "D6: Reflection",
    },
    FailureMode.D6_IMMUNIZATION: {
        "name": "Immunization from Testing",
        "description": "Making the conclusion unfalsifiable or untestable",
        "domain": "D6: Reflection",
    },
}


# =============================================================================
#        ALL 156 FALLACIES (mirrors Coq lists exactly)
# =============================================================================

_ALL_FALLACIES: List[Fallacy] = [

    # =========================================================================
    # TYPE 1: VIOLATIONS OF CONDITIONS (36)
    # Reasoning does not begin; manipulation/coercion takes its place.
    # =========================================================================

    # --- 1.A: Defective Questions (3) ---
    Fallacy("T1A_COMPLEX_QUESTION", "Complex Question (Loaded Question)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Question contains hidden assumption that must be accepted to answer",
            "Decompose the question. Identify the hidden premise. Address it separately.",
            Severity.HIGH, ManipulationCategory.DEFECTIVE_QUESTION),
    Fallacy("T1A_TABOO", "Taboo (Dogmatism)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Topic declared off-limits for discussion",
            "Identify the taboo. Explain why open examination is necessary.",
            Severity.MEDIUM, ManipulationCategory.DEFECTIVE_QUESTION),
    Fallacy("T1A_VENUE_FALLACY", "Venue Fallacy",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Dismissing argument because of where/when it's raised",
            "Evaluate the argument on its merits, not its context.",
            Severity.LOW, ManipulationCategory.DEFECTIVE_QUESTION),

    # --- 1.B: Manipulations — Force (8) ---
    Fallacy("T1B_AD_BACULUM", "Ad Baculum (Appeal to Force)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Threatening consequences if argument not accepted",
            "Remove the threat. Evaluate the argument without coercion.",
            Severity.CRITICAL, ManipulationCategory.FORCE),
    Fallacy("T1B_JUST_DO_IT", "Just Do It",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Demanding action without justification",
            "Ask: why? Require reasons before action.",
            Severity.HIGH, ManipulationCategory.FORCE),
    Fallacy("T1B_NO_DISCUSSION", "No Discussion",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Shutting down debate entirely",
            "Insist on examining the reasoning. Silence is not an argument.",
            Severity.CRITICAL, ManipulationCategory.FORCE),
    Fallacy("T1B_PLAUSIBLE_DENIABILITY", "Plausible Deniability",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Structuring claims to avoid accountability",
            "Pin down the exact claim. Remove escape routes.",
            Severity.HIGH, ManipulationCategory.FORCE),
    Fallacy("T1B_THE_POUT", "The Pout",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Emotional withdrawal to end discussion",
            "Acknowledge emotion but return to the argument.",
            Severity.MEDIUM, ManipulationCategory.FORCE),
    Fallacy("T1B_STANDARD_VERSION", "Standard Version",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Imposing one narrative as the only acceptable version",
            "Ask: whose standard? Present alternative versions.",
            Severity.HIGH, ManipulationCategory.FORCE),
    Fallacy("T1B_THOUSAND_FLOWERS", "Thousand Flowers",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Flooding with contradictory claims to paralyze reasoning",
            "Isolate one claim at a time. Evaluate sequentially.",
            Severity.HIGH, ManipulationCategory.FORCE),
    Fallacy("T1B_TINA", "TINA (There Is No Alternative)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Claiming no alternatives exist",
            "Generate at least two alternatives. Evaluate each.",
            Severity.HIGH, ManipulationCategory.FORCE),

    # --- 1.B: Manipulations — Pity (3) ---
    Fallacy("T1B_APPEAL_TO_PITY", "Appeal to Pity (Ad Misericordiam)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Using sympathy instead of evidence",
            "Acknowledge the situation but evaluate the argument on evidence.",
            Severity.MEDIUM, ManipulationCategory.PITY),
    Fallacy("T1B_NARRATIVE_FALLACY", "Narrative Fallacy",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Replacing evidence with compelling story",
            "Separate narrative from data. Evaluate evidence independently.",
            Severity.HIGH, ManipulationCategory.PITY),
    Fallacy("T1B_SAVE_THE_CHILDREN", "Save the Children",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Using children/vulnerable groups as rhetorical shield",
            "Focus on the specific policy/claim. Evaluate independently of emotional framing.",
            Severity.MEDIUM, ManipulationCategory.PITY),

    # --- 1.B: Manipulations — Emotion (7) ---
    Fallacy("T1B_SCARE_TACTICS", "Scare Tactics",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Inducing fear to bypass reasoning",
            "Assess actual probability and magnitude. Remove fear framing.",
            Severity.HIGH, ManipulationCategory.EMOTION),
    Fallacy("T1B_DOG_WHISTLE", "Dog Whistle",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Coded language targeting specific audience",
            "Make the implicit explicit. Evaluate the actual claim.",
            Severity.HIGH, ManipulationCategory.EMOTION),
    Fallacy("T1B_F_BOMB", "F-Bomb (Profanity as Argument)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Using shock/profanity to shut down reasoning",
            "Ignore emotional charge. Extract and evaluate the underlying claim.",
            Severity.LOW, ManipulationCategory.EMOTION),
    Fallacy("T1B_PLAYING_ON_EMOTION", "Playing on Emotion",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Generic emotional manipulation to bypass logic",
            "Identify the emotion being targeted. Evaluate argument without it.",
            Severity.MEDIUM, ManipulationCategory.EMOTION),
    Fallacy("T1B_PROSOPOLOGY", "Prosopology",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Attributing emotions/motives to gain sympathy",
            "Separate attributed emotions from factual claims.",
            Severity.MEDIUM, ManipulationCategory.EMOTION),
    Fallacy("T1B_SHOPPING_HUNGRY", "Shopping Hungry",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Exploiting current emotional state for decisions",
            "Delay decision until emotional state normalizes.",
            Severity.MEDIUM, ManipulationCategory.EMOTION),
    Fallacy("T1B_WE_HAVE_TO_DO_SOMETHING", "We Have To Do Something",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Urgency used to bypass analysis",
            "Pause. Evaluate whether urgency is real. Consider doing nothing as an option.",
            Severity.HIGH, ManipulationCategory.EMOTION),

    # --- 1.B: Benefit/Pressure/Authority (5) ---
    Fallacy("T1B_BRIBERY", "Bribery",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Offering benefit in exchange for agreement",
            "Separate benefit from argument. Evaluate claim without incentive.",
            Severity.CRITICAL, ManipulationCategory.BENEFIT),
    Fallacy("T1B_APPEASEMENT", "Appeasement",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Accepting bad reasoning to avoid conflict",
            "Evaluate the argument on merits regardless of social pressure.",
            Severity.MEDIUM, ManipulationCategory.PRESSURE),
    Fallacy("T1B_APPEAL_TO_HEAVEN", "Appeal to Heaven",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Claiming divine/transcendent authority",
            "Require earthly evidence. Divine authority is not verifiable.",
            Severity.HIGH, ManipulationCategory.FALSE_AUTHORITY),
    Fallacy("T1B_AD_MYSTERIAM", "Ad Mysteriam",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Appealing to mystery/incomprehensibility",
            "If something is truly incomprehensible, no conclusion can follow from it.",
            Severity.MEDIUM, ManipulationCategory.FALSE_AUTHORITY),
    Fallacy("T1B_PSEUDO_ESOTERIC", "Pseudo-Esoteric",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Claiming special hidden knowledge",
            "Knowledge must be shareable and verifiable. Request evidence.",
            Severity.HIGH, ManipulationCategory.FALSE_AUTHORITY),

    # --- 1.B: Disinformation (5) ---
    Fallacy("T1B_BIG_LIE", "Big Lie",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Lie so large it seems impossible to fabricate",
            "Check each factual claim independently. Scale doesn't equal truth.",
            Severity.CRITICAL, ManipulationCategory.DISINFORMATION),
    Fallacy("T1B_ALTERNATIVE_TRUTH", "Alternative Truth",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Presenting fabrication as equally valid perspective",
            "Apply same verification standards to all claims. Facts are not opinions.",
            Severity.CRITICAL, ManipulationCategory.DISINFORMATION),
    Fallacy("T1B_GASLIGHTING", "Gaslighting",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Making someone doubt their own perception/memory",
            "Ground in verifiable facts. Document and reference evidence.",
            Severity.CRITICAL, ManipulationCategory.DISINFORMATION),
    Fallacy("T1B_INFOTAINMENT", "Infotainment",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Mixing entertainment with information to lower critical thinking",
            "Separate factual claims from entertainment framing.",
            Severity.MEDIUM, ManipulationCategory.DISINFORMATION),
    Fallacy("T1B_SCRIPTED_MESSAGE", "Scripted Message",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Pre-packaged talking points replacing genuine reasoning",
            "Ask for the reasoning behind each point. Scripts are not arguments.",
            Severity.HIGH, ManipulationCategory.DISINFORMATION),

    # --- 1.B: Delegation/Ethos/BadFaith (5) ---
    Fallacy("T1B_BLIND_LOYALTY", "Blind Loyalty",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Following authority without examining reasoning",
            "Evaluate the argument independent of its source.",
            Severity.HIGH, ManipulationCategory.DELEGATION),
    Fallacy("T1B_BIG_BRAIN_LITTLE_BRAIN", "Big Brain/Little Brain",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Claiming superior intellect to dismiss criticism",
            "Arguments stand on their logic, not on who makes them.",
            Severity.HIGH, ManipulationCategory.DELEGATION),
    Fallacy("T1B_ALPHABET_SOUP", "Alphabet Soup (Credential Fallacy)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Substituting credentials for evidence",
            "Credentials don't replace evidence. Evaluate the argument itself.",
            Severity.MEDIUM, ManipulationCategory.FALSE_ETHOS),
    Fallacy("T1B_MALA_FIDES", "Mala Fides (Bad Faith)",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Arguing in bad faith while appearing reasonable",
            "Test for consistency. Bad faith often contradicts itself.",
            Severity.CRITICAL, ManipulationCategory.BAD_FAITH),
    Fallacy("T1B_OCTOBER_SURPRISE", "October Surprise",
            FallacyType.T1_CONDITION_VIOLATION, Domain.NONE,
            FailureMode.CONDITION_BLOCKED,
            "Timing information release to prevent proper analysis",
            "Demand time for analysis regardless of timing pressure.",
            Severity.HIGH, ManipulationCategory.BAD_FAITH),

    # =========================================================================
    # TYPE 2: DOMAIN VIOLATIONS (105)
    # Reasoning begins but fails within a specific D1-D6 domain.
    # =========================================================================

    # --- D1: Recognition — 26 fallacies ---
    # Object Deformation (2)
    Fallacy("D1_STRAW_MAN", "Straw Man",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_DEFORMATION,
            "Distorting opponent's argument to make it easier to attack",
            "Restate the ORIGINAL argument accurately. Attack that, not the distortion.",
            Severity.HIGH,
            example="They want to reduce military spending? So they want us defenseless!"),
    Fallacy("D1_RED_HERRING", "Red Herring",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_DEFORMATION,
            "Introducing irrelevant topic to divert from the real issue",
            "Return to the original topic. The diversion is not relevant.",
            Severity.MEDIUM),
    # Object Substitution (16)
    Fallacy("D1_AD_HOMINEM", "Ad Hominem",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Attacking the person instead of addressing the argument",
            "Address the ARGUMENT, not the person. What is the actual claim?",
            Severity.HIGH,
            example="You're an idiot, so your climate data must be wrong."),
    Fallacy("D1_ARGUMENT_FROM_MOTIVES", "Argument from Motives",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Dismissing argument based on speaker's presumed motives",
            "Evaluate the argument regardless of who benefits from it.",
            Severity.MEDIUM),
    Fallacy("D1_BLOOD_IS_THICKER", "Blood Is Thicker than Water",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using kinship/loyalty to override logical evaluation",
            "Family bonds don't determine truth. Evaluate evidence independently.",
            Severity.MEDIUM),
    Fallacy("D1_GUILT_BY_ASSOCIATION", "Guilt by Association",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Rejecting argument because of who else holds it",
            "Judge the argument on its own merits, not its proponents.",
            Severity.HIGH),
    Fallacy("D1_IDENTITY_FALLACY", "Identity Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Only members of group X can understand/discuss topic Y",
            "Arguments are evaluated by logic and evidence, not by who makes them.",
            Severity.MEDIUM),
    Fallacy("D1_JUST_PLAIN_FOLKS", "Just Plain Folks",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using 'ordinary person' image to gain trust without evidence",
            "Evaluate the claim, not the persona.",
            Severity.LOW),
    Fallacy("D1_NAME_CALLING", "Name Calling",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using derogatory labels instead of addressing arguments",
            "Remove the labels. What is the actual argument?",
            Severity.HIGH),
    Fallacy("D1_OLFACTORY_RHETORIC", "Olfactory Rhetoric",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using disgust/revulsion to replace reasoning",
            "Disgust is not an argument. Evaluate on evidence.",
            Severity.MEDIUM),
    Fallacy("D1_OTHERING", "Othering",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Dismissing by categorizing as 'not one of us'",
            "In-group/out-group status doesn't affect argument validity.",
            Severity.HIGH),
    Fallacy("D1_PATERNALISM", "Paternalism",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Claiming to know what's best, bypassing the person's reasoning",
            "Respect the person's capacity to reason. Present evidence, don't dictate.",
            Severity.MEDIUM),
    Fallacy("D1_REDUCTIO_AD_HITLERUM", "Reductio ad Hitlerum",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Comparing opponent to Hitler/Nazis to dismiss argument",
            "Historical comparisons must be specific and evidence-based.",
            Severity.HIGH),
    Fallacy("D1_ROMANTIC_REBEL", "Romantic Rebel",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using outsider/rebel image as substitute for evidence",
            "Rebellion is not evidence. What are the specific claims?",
            Severity.LOW),
    Fallacy("D1_STAR_POWER", "Star Power (Celebrity Appeal)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Using celebrity endorsement as evidence",
            "Celebrity status doesn't confer expertise. Evaluate the evidence.",
            Severity.MEDIUM),
    Fallacy("D1_TONE_POLICING", "Tone Policing",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Dismissing argument based on how it's expressed",
            "The tone doesn't affect the validity. Address the content.",
            Severity.MEDIUM),
    Fallacy("D1_TRANSFER", "Transfer (Name-Dropping)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Borrowing prestige from unrelated authority/symbol",
            "Prestige doesn't transfer to unrelated claims. Evaluate independently.",
            Severity.MEDIUM),
    Fallacy("D1_TU_QUOQUE", "Tu Quoque (Whataboutism)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_OBJECT_SUBSTITUTION,
            "Deflecting criticism by pointing to opponent's similar behavior",
            "Your actions don't affect whether my argument is valid. Address the claim.",
            Severity.HIGH,
            example="Why criticize us? What about their failures?"),
    # Data Filtration (5)
    Fallacy("D1_AVAILABILITY_BIAS", "Availability Bias",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_DATA_FILTRATION,
            "Overweighting easily recalled information",
            "Consider the full dataset, not just memorable examples.",
            Severity.MEDIUM),
    Fallacy("D1_DISCIPLINARY_BLINDERS", "Disciplinary Blinders",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_DATA_FILTRATION,
            "Seeing only through one discipline's lens",
            "Consider perspectives from other relevant fields.",
            Severity.MEDIUM),
    Fallacy("D1_HALF_TRUTH", "Half-Truth (Cherry Picking)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_DATA_FILTRATION,
            "Presenting only supporting evidence, hiding contradicting data",
            "Present ALL relevant evidence, including what contradicts your position.",
            Severity.HIGH),
    Fallacy("D1_LYING_WITH_STATISTICS", "Lying with Statistics",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_DATA_FILTRATION,
            "Manipulating statistical presentation to mislead",
            "Show raw numbers, sample size, methodology. Statistics require context.",
            Severity.HIGH),
    Fallacy("D1_NIMBY", "NIMBY Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_DATA_FILTRATION,
            "Accepting in principle but filtering out personal impact",
            "Apply the same standard regardless of personal proximity.",
            Severity.LOW),
    # Projection (2)
    Fallacy("D1_MIND_READING", "Mind Reading",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_PROJECTION,
            "Claiming to know someone's thoughts/intentions without evidence",
            "You cannot know internal states. Stick to observable behavior and statements.",
            Severity.MEDIUM),
    Fallacy("D1_POLLYANNA", "Pollyanna Principle",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_PROJECTION,
            "Filtering reality through excessive optimism",
            "Consider negative outcomes as well. Reality includes both positive and negative.",
            Severity.LOW),
    # Source Distortion (1)
    Fallacy("D1_BRAINWASHING", "Brainwashing",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D1_RECOGNITION,
            FailureMode.D1_SOURCE_DISTORTION,
            "Systematic corruption of information source",
            "Verify information through independent sources.",
            Severity.CRITICAL),

    # --- D2: Clarification — 13 fallacies ---
    # Meaning Drift (7)
    Fallacy("D2_ACTIONS_CONSEQUENCES", "Actions Have Consequences (Dismissal)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Using vague 'consequences' to avoid specific reasoning",
            "Specify WHICH consequences and WHY they follow.",
            Severity.MEDIUM),
    Fallacy("D2_DIMINISHED_RESPONSIBILITY", "Diminished Responsibility",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Redefining responsibility to avoid accountability",
            "Define responsibility clearly and consistently.",
            Severity.HIGH),
    Fallacy("D2_EQUIVOCATION", "Equivocation",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Using a word in two different senses within the same argument",
            "Define each key term precisely. Use one definition consistently.",
            Severity.HIGH,
            example="The bank is by the river. Banks have money. Therefore the river has money."),
    Fallacy("D2_ETYMOLOGICAL", "Etymological Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Arguing a word must mean what it originally meant",
            "Words evolve. Use current meaning in current context.",
            Severity.LOW),
    Fallacy("D2_HEROES_ALL", "Heroes All",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Stretching 'hero' to cover everyone, diluting meaning",
            "Use precise terms. Not everyone is a hero; distinguish contributions.",
            Severity.LOW),
    Fallacy("D2_POLITICAL_CORRECTNESS", "Political Correctness (as fallacy)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Changing terms to avoid uncomfortable truths",
            "Use the most precise and accurate term available.",
            Severity.MEDIUM),
    Fallacy("D2_REIFICATION", "Reification",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_MEANING_DRIFT,
            "Treating abstract concept as concrete entity",
            "Abstract concepts cannot act. Identify the actual actors.",
            Severity.MEDIUM),
    # Hidden Agent (1)
    Fallacy("D2_PASSIVE_VOICE", "Passive Voice Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_HIDDEN_AGENT,
            "Using passive voice to hide who performed the action",
            "Restate in active voice: WHO did WHAT?",
            Severity.HIGH),
    # Incomplete Analysis (3)
    Fallacy("D2_EITHER_OR", "Either-Or Reasoning (False Dilemma)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_INCOMPLETE_ANALYSIS,
            "Presenting only two options when more exist",
            "List ALL viable options (minimum 3). Evaluate each.",
            Severity.HIGH,
            example="You're either with us or against us."),
    Fallacy("D2_PLAIN_TRUTH", "Plain Truth Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_INCOMPLETE_ANALYSIS,
            "Claiming truth is 'obvious' to avoid analysis",
            "Nothing is self-evident. Provide the reasoning chain.",
            Severity.MEDIUM),
    Fallacy("D2_REDUCTIONISM", "Reductionism",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_INCOMPLETE_ANALYSIS,
            "Oversimplifying a complex phenomenon",
            "Acknowledge complexity. Identify what's lost in simplification.",
            Severity.MEDIUM),
    # Excessive Analysis (2)
    Fallacy("D2_OVEREXPLANATION", "Overexplanation",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_EXCESSIVE_ANALYSIS,
            "Providing so much detail that the core point is lost",
            "State the core claim in one sentence. Then support it concisely.",
            Severity.LOW),
    Fallacy("D2_SNOW_JOB", "Snow Job",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D2_CLARIFICATION,
            FailureMode.D2_EXCESSIVE_ANALYSIS,
            "Overwhelming with jargon/complexity to prevent understanding",
            "Request simple explanation. If it can't be simplified, it may be empty.",
            Severity.HIGH),

    # --- D3: Framework — 16 fallacies ---
    # Category Mismatch (3)
    Fallacy("D3_ESCHATOLOGICAL", "Eschatological Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_CATEGORY_MISMATCH,
            "Applying end-times thinking to everyday decisions",
            "Use a framework proportional to the actual situation.",
            Severity.MEDIUM),
    Fallacy("D3_MEASURABILITY", "Measurability Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_CATEGORY_MISMATCH,
            "Only valuing what can be measured, ignoring qualitative factors",
            "Not everything important is measurable. Include qualitative analysis.",
            Severity.MEDIUM),
    Fallacy("D3_PROCRUSTEAN", "Procrustean Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_CATEGORY_MISMATCH,
            "Forcing data to fit a predetermined model",
            "Let the data determine the model, not the other way around.",
            Severity.HIGH),
    # Irrelevant Criterion (9)
    Fallacy("D3_ABLEISM", "Ableism Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using physical/mental ability as criterion where irrelevant",
            "Is ability actually relevant to this specific evaluation?",
            Severity.MEDIUM),
    Fallacy("D3_AFFECTIVE", "Affective Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using emotional response as evaluation criterion",
            "Emotional response doesn't determine truth or quality.",
            Severity.MEDIUM),
    Fallacy("D3_APPEAL_TO_NATURE", "Appeal to Nature",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Claiming natural = good, artificial = bad",
            "Natural/artificial is irrelevant to quality or safety. Evaluate on evidence.",
            Severity.MEDIUM),
    Fallacy("D3_APPEAL_TO_TRADITION", "Appeal to Tradition",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using 'tradition' as the sole justification",
            "Tradition is not evidence. Why is this practice correct on its own merits?",
            Severity.MEDIUM,
            example="We've always done it this way, so it must be right."),
    Fallacy("D3_BANDWAGON", "Bandwagon (Ad Populum)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using popularity as evidence of truth",
            "Popularity doesn't determine truth. Evaluate on evidence.",
            Severity.HIGH),
    Fallacy("D3_COST_BIAS", "Cost Bias",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Equating cost with value or quality",
            "Price doesn't determine quality. Evaluate independently.",
            Severity.LOW),
    Fallacy("D3_E_FOR_EFFORT", "E for Effort",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Evaluating result based on effort rather than quality",
            "Results are evaluated by their quality, not the effort invested.",
            Severity.LOW),
    Fallacy("D3_MORTIFICATION", "Mortification",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using suffering as evidence of truth or value",
            "Suffering doesn't validate a position. Evaluate on evidence.",
            Severity.MEDIUM),
    Fallacy("D3_SOLDIERS_HONOR", "Soldier's Honor",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_IRRELEVANT_CRITERION,
            "Using sacrifice/service to place claims beyond criticism",
            "Service is admirable but doesn't make every claim correct.",
            Severity.MEDIUM),
    # Framework for Result (4)
    Fallacy("D3_BIG_BUT", "Big But Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_FRAMEWORK_FOR_RESULT,
            "Acknowledging facts but dismissing their significance with 'but'",
            "If you acknowledge the facts, your conclusion must account for them.",
            Severity.MEDIUM),
    Fallacy("D3_MORAL_LICENSING", "Moral Licensing",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_FRAMEWORK_FOR_RESULT,
            "Using past good behavior to justify current bad behavior",
            "Each action is evaluated independently. Past good doesn't excuse present bad.",
            Severity.MEDIUM),
    Fallacy("D3_MORAL_SUPERIORITY", "Moral Superiority",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_FRAMEWORK_FOR_RESULT,
            "Claiming moral high ground to bypass logical evaluation",
            "Moral claims require the same evidence as any other claim.",
            Severity.HIGH),
    Fallacy("D3_MOVING_GOALPOSTS", "Moving Goalposts",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D3_FRAMEWORK,
            FailureMode.D3_FRAMEWORK_FOR_RESULT,
            "Changing criteria after evidence is presented",
            "Fix criteria BEFORE evaluation. Any change must be explicitly justified.",
            Severity.HIGH),

    # --- D4: Comparison — 8 fallacies ---
    # False Equation (4)
    Fallacy("D4_FALSE_ANALOGY", "False Analogy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_FALSE_EQUATION,
            "Comparing fundamentally different things as if they were similar",
            "List the actual similarities AND differences. Are they relevant?",
            Severity.HIGH),
    Fallacy("D4_SCORING_FALLACY", "Scoring Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_FALSE_EQUATION,
            "Reducing qualitative comparison to numerical score",
            "Some comparisons can't be reduced to numbers. Compare qualitatively.",
            Severity.MEDIUM),
    Fallacy("D4_SIMPLETONS", "Simpleton's Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_FALSE_EQUATION,
            "Treating all instances of a category as identical",
            "Identify the relevant differences within the category.",
            Severity.MEDIUM),
    Fallacy("D4_TWO_SIDES", "Two Sides Fallacy (False Balance)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_FALSE_EQUATION,
            "Treating unequal positions as equally valid",
            "Weight of evidence matters. Not all positions deserve equal time.",
            Severity.HIGH),
    # Unstable Criteria (3)
    Fallacy("D4_FUNDAMENTAL_ATTRIBUTION", "Fundamental Attribution Error",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_UNSTABLE_CRITERIA,
            "Attributing others' behavior to character, own to circumstances",
            "Apply the same explanatory framework to yourself and others.",
            Severity.MEDIUM),
    Fallacy("D4_DOUBLE_STANDARD", "Double Standard (Moving Goalposts D4)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_UNSTABLE_CRITERIA,
            "Applying different standards to different subjects",
            "Use the same criteria for all subjects being compared.",
            Severity.HIGH),
    Fallacy("D4_WORST_NEGATES_BAD", "Worst Negates the Bad",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_UNSTABLE_CRITERIA,
            "Using worse examples to make bad seem acceptable",
            "Bad is bad regardless of worse. Evaluate against the standard, not the worst.",
            Severity.MEDIUM),
    # Comparison with Nonexistent (1)
    Fallacy("D4_HERO_BUSTING", "Hero Busting (Nirvana Fallacy)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D4_COMPARISON,
            FailureMode.D4_COMPARISON_NONEXISTENT,
            "Comparing to impossible ideal to declare failure",
            "Compare to realistic alternatives, not to perfection.",
            Severity.MEDIUM),

    # --- D5: Inference — 20 fallacies ---
    # Logical Gap (1)
    Fallacy("D5_NON_SEQUITUR", "Non Sequitur",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_LOGICAL_GAP,
            "Conclusion does not follow from premises",
            "Show the logical chain: premise A + premise B -> conclusion. Where does it break?",
            Severity.CRITICAL,
            example="She's tall, therefore she must be good at math."),
    # Causal Error (7)
    Fallacy("D5_JOBS_COMFORTER", "Job's Comforter",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Claiming suffering is caused by victim's own fault",
            "Correlation between suffering and behavior doesn't prove causation.",
            Severity.MEDIUM),
    Fallacy("D5_MAGICAL_THINKING", "Magical Thinking",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Believing thoughts/wishes can directly cause events",
            "Identify the actual causal mechanism. Wishes are not causes.",
            Severity.MEDIUM),
    Fallacy("D5_PERSONALIZATION", "Personalization",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Attributing external events to personal actions without evidence",
            "Consider all possible causes. Your involvement may be coincidental.",
            Severity.LOW),
    Fallacy("D5_POSITIVE_THINKING", "Positive Thinking Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Believing positive attitude causes positive outcomes",
            "Attitude may correlate with outcomes but doesn't cause them.",
            Severity.LOW),
    Fallacy("D5_POST_HOC", "Post Hoc Ergo Propter Hoc",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Assuming because B followed A, A caused B",
            "Temporal sequence doesn't prove causation. Identify the mechanism.",
            Severity.HIGH,
            example="I wore my lucky socks and we won. The socks caused the victory."),
    Fallacy("D5_SCAPEGOATING", "Scapegoating",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Blaming a person/group for systemic problems",
            "Identify the actual systemic causes. One entity rarely causes complex problems.",
            Severity.HIGH),
    Fallacy("D5_TRUST_YOUR_GUT", "Trust Your Gut",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CAUSAL_ERROR,
            "Using intuition as evidence in analytical context",
            "Intuition is a starting hypothesis, not a conclusion. Verify with evidence.",
            Severity.MEDIUM),
    # Chain Error (2)
    Fallacy("D5_EXCLUDED_MIDDLE", "Excluded Middle (False Dichotomy in D5)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CHAIN_ERROR,
            "Inferring that if not-A then B, ignoring middle options",
            "Identify the full range of possible conclusions.",
            Severity.HIGH),
    Fallacy("D5_SLIPPERY_SLOPE", "Slippery Slope",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_CHAIN_ERROR,
            "Claiming A leads inevitably to Z without justifying each step",
            "Show each step in the chain. Where does the inevitability break?",
            Severity.HIGH,
            example="If we allow X, next they'll want Y, then Z, and civilization collapses."),
    # Scale Error (10)
    Fallacy("D5_ARGUMENT_FROM_CONSEQUENCES", "Argument from Consequences",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Concluding something is true/false based on consequences",
            "Truth is independent of consequences. Evaluate evidence, not outcomes.",
            Severity.MEDIUM),
    Fallacy("D5_ARGUMENT_FROM_IGNORANCE", "Argument from Ignorance",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Claiming something is true because it hasn't been proven false",
            "Absence of evidence is not evidence of absence. The burden of proof applies.",
            Severity.HIGH),
    Fallacy("D5_ARGUMENT_FROM_SILENCE", "Argument from Silence",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Interpreting silence as agreement or evidence",
            "Silence can mean many things. Don't interpret it without evidence.",
            Severity.MEDIUM),
    Fallacy("D5_DRAW_OWN_CONCLUSION", "Draw Your Own Conclusion",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Presenting facts suggestively, leaving audience to make the wrong inference",
            "State the conclusion explicitly. Don't hide it behind suggestive presentation.",
            Severity.MEDIUM),
    Fallacy("D5_HOYLES_FALLACY", "Hoyle's Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Multiplying low probabilities to make something seem impossible",
            "Check if events are truly independent. Consider alternative pathways.",
            Severity.MEDIUM),
    Fallacy("D5_OVERGENERALIZATION", "Overgeneralization (Hasty Generalization)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Drawing broad conclusion from too few examples",
            "How many cases were examined? Is the sample representative?",
            Severity.HIGH),
    Fallacy("D5_SILENT_MAJORITY", "Silent Majority",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Claiming unpolled majority agrees with you",
            "Without data, you cannot claim majority support. Present evidence.",
            Severity.HIGH),
    Fallacy("D5_WHERES_SMOKE", "Where There's Smoke",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Treating rumors/accusations as evidence of truth",
            "Accusations are not evidence. Require actual evidence.",
            Severity.MEDIUM),
    Fallacy("D5_WISDOM_OF_CROWD", "Wisdom of the Crowd (when misapplied)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Assuming collective opinion equals truth",
            "Crowds can be wrong (see: every bubble). Evaluate evidence independently.",
            Severity.MEDIUM),
    Fallacy("D5_WORST_CASE", "Worst Case Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D5_INFERENCE,
            FailureMode.D5_SCALE_ERROR,
            "Assuming worst outcome is most likely",
            "Assess actual probabilities, not just worst case.",
            Severity.MEDIUM),

    # --- D6: Reflection — 22 fallacies ---
    # Illusion of Completion (6)
    Fallacy("D6_APPEAL_TO_CLOSURE", "Appeal to Closure",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Accepting conclusion to end discomfort of uncertainty",
            "Uncertainty is acceptable. Don't rush to false closure.",
            Severity.MEDIUM),
    Fallacy("D6_DEFAULT_BIAS", "Default Bias",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Preferring current state merely because it's the default",
            "Evaluate the default option with the same rigor as alternatives.",
            Severity.LOW),
    Fallacy("D6_ESSENTIALIZING", "Essentializing",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Attributing fixed 'essence' to things that change",
            "Consider how the subject might change under different conditions.",
            Severity.MEDIUM),
    Fallacy("D6_UNINTENDED_CONSEQUENCES", "Law of Unintended Consequences (as excuse)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Using possibility of unintended consequences to block all action",
            "Unintended consequences exist but don't justify inaction. Analyze specifically.",
            Severity.MEDIUM),
    Fallacy("D6_NOTHING_NEW", "Nothing New Under the Sun",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Dismissing novelty by claiming everything has been seen before",
            "Identify what IS actually new. Novel elements deserve analysis.",
            Severity.LOW),
    Fallacy("D6_PARALYSIS_OF_ANALYSIS", "Paralysis of Analysis",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_ILLUSION_COMPLETION,
            "Endless analysis preventing any conclusion",
            "Set a decision deadline. Perfect analysis is impossible; good enough is sufficient.",
            Severity.MEDIUM),
    # Self-Assessment Distortion (2)
    Fallacy("D6_DUNNING_KRUGER", "Dunning-Kruger Effect",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_SELF_ASSESSMENT,
            "Overestimating own competence due to lack of knowledge",
            "Seek external evaluation. Consider what you might not know.",
            Severity.HIGH),
    Fallacy("D6_SUNK_COST", "Sunk Cost Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_SELF_ASSESSMENT,
            "Continuing because of past investment rather than future value",
            "Past costs are irrelevant to future decisions. Evaluate from NOW.",
            Severity.HIGH),
    # Past Investment Influence (2)
    Fallacy("D6_ARGUMENT_FROM_INERTIA", "Argument from Inertia",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_PAST_INVESTMENT,
            "Resisting change merely because change is uncomfortable",
            "Evaluate the new option on its merits, not on the comfort of the status quo.",
            Severity.MEDIUM),
    Fallacy("D6_DEFENSIVENESS", "Defensiveness",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_PAST_INVESTMENT,
            "Refusing to reconsider a position because ego is invested",
            "Separate your ego from your argument. Being wrong is information, not failure.",
            Severity.MEDIUM),
    # Immunization from Testing (12)
    Fallacy("D6_ARGUMENT_FROM_INCREDULITY", "Argument from Incredulity",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Rejecting something because it seems hard to believe",
            "Your ability to imagine it doesn't determine its truth. Check evidence.",
            Severity.MEDIUM),
    Fallacy("D6_CALLING_CARDS", "Calling Cards",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Using credentials to block questioning",
            "Credentials don't make every claim correct. Evaluate the argument.",
            Severity.MEDIUM),
    Fallacy("D6_DELIBERATE_IGNORANCE", "Deliberate Ignorance",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Choosing not to seek disconfirming evidence",
            "Actively seek evidence that could prove you wrong.",
            Severity.HIGH),
    Fallacy("D6_FINISH_THE_JOB", "Finish the Job",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Using commitment to block reassessment",
            "Commitment to a course doesn't prohibit re-evaluation.",
            Severity.MEDIUM),
    Fallacy("D6_FREE_SPEECH", "Free Speech Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Using right to speak as shield against criticism",
            "Free speech means you can say it, not that it's correct. Evaluate the content.",
            Severity.MEDIUM),
    Fallacy("D6_MAGIC_WAND", "Magic Wand Fallacy",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Dismissing criticism because perfect solution isn't offered",
            "Identifying a problem doesn't require having a solution.",
            Severity.MEDIUM),
    Fallacy("D6_MYOB", "MYOB (Mind Your Own Business)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Blocking criticism by claiming it's not your concern",
            "Public claims are open to public scrutiny.",
            Severity.MEDIUM),
    Fallacy("D6_NON_RECOGNITION", "Non-Recognition",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Refusing to acknowledge a problem exists",
            "Identify the specific evidence of the problem. Denial is not refutation.",
            Severity.HIGH),
    Fallacy("D6_WRONG_MESSAGE", "Sending the Wrong Message",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Opposing truth because of the message it might send",
            "Truth is independent of its social implications. Report accurately.",
            Severity.MEDIUM),
    Fallacy("D6_ALL_CROOKS", "They're All Crooks",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Blanket cynicism used to avoid evaluating specific claims",
            "Evaluate each claim individually. Cynicism is not analysis.",
            Severity.MEDIUM),
    Fallacy("D6_THIRD_PERSON_EFFECT", "Third Person Effect",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Believing you're immune to the biases that affect others",
            "You are not immune to cognitive biases. Apply the same scrutiny to yourself.",
            Severity.MEDIUM),
    Fallacy("D6_VENTING", "Venting (as substitute for analysis)",
            FallacyType.T2_DOMAIN_VIOLATION, Domain.D6_REFLECTION,
            FailureMode.D6_IMMUNIZATION,
            "Expressing frustration instead of analyzing the problem",
            "Vent first if needed, then analyze. Emotion is not a conclusion.",
            Severity.LOW),

    # =========================================================================
    # TYPE 3: VIOLATIONS OF SEQUENCE (3)
    # D1->D6 order broken: backward jumps, skips, or loops.
    # =========================================================================
    Fallacy("T3_RATIONALIZATION", "Rationalization",
            FallacyType.T3_SEQUENCE_VIOLATION, Domain.NONE,
            FailureMode.SEQUENCE_BROKEN,
            "Starting from conclusion (D5) and working backward to justify it",
            "Start from D1 (Recognition). Build forward. Don't reverse-engineer justification.",
            Severity.CRITICAL),
    Fallacy("T3_CIRCULAR_REASONING", "Circular Reasoning (Begging the Question)",
            FallacyType.T3_SEQUENCE_VIOLATION, Domain.NONE,
            FailureMode.SEQUENCE_BROKEN,
            "Using conclusion as premise (D5 feeds back to D1)",
            "Identify the circular dependency. Break it by finding independent evidence.",
            Severity.CRITICAL,
            example="The Bible is true because God wrote it, and God exists because the Bible says so."),
    Fallacy("T3_BURDEN_SHIFTING", "Shifting Burden of Proof",
            FallacyType.T3_SEQUENCE_VIOLATION, Domain.NONE,
            FailureMode.SEQUENCE_BROKEN,
            "Demanding opponent disprove instead of proving your claim",
            "The burden of proof is on the claimant. Provide your evidence first.",
            Severity.HIGH),

    # =========================================================================
    # TYPE 4: SYNDROMES (6)
    # Self-reinforcing cross-domain corruption.
    # =========================================================================
    Fallacy("T4_CONFIRMATION_BIAS", "Confirmation Bias",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Seeking only information that confirms existing beliefs",
            "Actively search for disconfirming evidence. Steel-man the opposing view.",
            Severity.HIGH,
            example="Our product is the best. All customers love it. No problems exist."),
    Fallacy("T4_COMPARTMENTALIZATION", "Compartmentalization",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Holding contradictory beliefs by isolating them in different contexts",
            "Apply your principles consistently across all domains.",
            Severity.MEDIUM),
    Fallacy("T4_MOTIVATED_REASONING", "Motivated Reasoning",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Biased cognitive processes serving emotional needs",
            "Identify what you WANT to be true. Then evaluate as if you wanted the opposite.",
            Severity.HIGH),
    Fallacy("T4_ECHO_CHAMBER", "Echo Chamber",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Information environment that only reinforces existing views",
            "Seek out sources that disagree. Include critics in your information diet.",
            Severity.HIGH),
    Fallacy("T4_COGNITIVE_CLOSURE", "Cognitive Closure",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Need for definitive answer overrides need for correct answer",
            "Tolerate ambiguity. Premature certainty is worse than productive uncertainty.",
            Severity.MEDIUM),
    Fallacy("T4_GROUPTHINK", "Groupthink",
            FallacyType.T4_SYNDROME, Domain.NONE,
            FailureMode.SYNDROME,
            "Group cohesion suppresses critical thinking",
            "Assign a devil's advocate. Encourage dissent before consensus.",
            Severity.HIGH),

    # =========================================================================
    # TYPE 5: CONTEXT-DEPENDENT METHODS (6)
    # Valid under specific conditions, fallacious otherwise.
    # =========================================================================
    Fallacy("T5_TRUST_GUT_CONTEXT", "Trust Your Gut (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Intuition valid for domain experts, fallacious for novices",
            "If you have 10,000+ hours in this domain, intuition has value. Otherwise, verify.",
            Severity.LOW),
    Fallacy("T5_AFFECTIVE_REASONING", "Affective Reasoning (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Emotional reasoning valid in interpersonal context, fallacious in analytical",
            "Is this an interpersonal or analytical context? Choose method accordingly.",
            Severity.LOW),
    Fallacy("T5_APPEAL_TRADITION_CONTEXT", "Appeal to Tradition (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Tradition valid when it embodies tested wisdom, fallacious as sole argument",
            "Has this tradition been tested? Can you articulate WHY it works?",
            Severity.LOW),
    Fallacy("T5_APPEAL_NATURE_CONTEXT", "Appeal to Nature (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Natural = good is sometimes valid in evolutionary fitness context",
            "Is natural selection actually relevant here? If not, evaluate on other grounds.",
            Severity.LOW),
    Fallacy("T5_ARGUMENT_SILENCE_CONTEXT", "Argument from Silence (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Silence meaningful when records should exist, fallacious otherwise",
            "Would evidence be expected here? If records should exist but don't, that's significant.",
            Severity.LOW),
    Fallacy("T5_ARGUMENT_CONSEQUENCES_CONTEXT", "Argument from Consequences (context-dependent)",
            FallacyType.T5_CONTEXT_DEPENDENT, Domain.NONE,
            FailureMode.CONTEXT_DEPENDENT,
            "Consequences relevant for policy decisions, fallacious for truth claims",
            "Is this a truth claim or a policy decision? Only the latter considers consequences.",
            Severity.LOW),
]


# =============================================================================
#                           INDEXES & LOOKUPS
# =============================================================================

# Primary index: id -> Fallacy
FALLACIES: Dict[str, Fallacy] = {f.id: f for f in _ALL_FALLACIES}

# By domain
FALLACIES_BY_DOMAIN: Dict[Domain, List[Fallacy]] = {}
for f in _ALL_FALLACIES:
    FALLACIES_BY_DOMAIN.setdefault(f.domain, []).append(f)

# By type
FALLACIES_BY_TYPE: Dict[FallacyType, List[Fallacy]] = {}
for f in _ALL_FALLACIES:
    FALLACIES_BY_TYPE.setdefault(f.fallacy_type, []).append(f)

# By failure mode
_FALLACIES_BY_FM: Dict[FailureMode, List[Fallacy]] = {}
for f in _ALL_FALLACIES:
    _FALLACIES_BY_FM.setdefault(f.failure_mode, []).append(f)


def get_fallacy(fallacy_id: str) -> Optional[Fallacy]:
    """Look up fallacy by ID."""
    return FALLACIES.get(fallacy_id)


def get_domain_fallacies(domain: Domain) -> List[Fallacy]:
    """Get all fallacies for a specific domain."""
    return FALLACIES_BY_DOMAIN.get(domain, [])


def get_failure_mode_fallacies(fm: FailureMode) -> List[Fallacy]:
    """Get all fallacies for a specific failure mode."""
    return _FALLACIES_BY_FM.get(fm, [])


# =============================================================================
#                           VERIFICATION (mirrors Coq counting lemmas)
# =============================================================================

def _verify_counts() -> bool:
    """
    Runtime verification matching Coq lemmas:
      D1_count : length all_D1 = 26
      D2_count : length all_D2 = 13
      D3_count : length all_D3 = 16
      D4_count : length all_D4 = 8
      D5_count : length all_D5 = 20
      D6_count : length all_D6 = 22
      type1_is_36 : type1_total = 36
      total_type2_is_105
      total_is_156
    """
    t1 = len(FALLACIES_BY_TYPE.get(FallacyType.T1_CONDITION_VIOLATION, []))
    t2 = len(FALLACIES_BY_TYPE.get(FallacyType.T2_DOMAIN_VIOLATION, []))
    t3 = len(FALLACIES_BY_TYPE.get(FallacyType.T3_SEQUENCE_VIOLATION, []))
    t4 = len(FALLACIES_BY_TYPE.get(FallacyType.T4_SYNDROME, []))
    t5 = len(FALLACIES_BY_TYPE.get(FallacyType.T5_CONTEXT_DEPENDENT, []))

    d1 = len(FALLACIES_BY_DOMAIN.get(Domain.D1_RECOGNITION, []))
    d2 = len(FALLACIES_BY_DOMAIN.get(Domain.D2_CLARIFICATION, []))
    d3 = len(FALLACIES_BY_DOMAIN.get(Domain.D3_FRAMEWORK, []))
    d4 = len(FALLACIES_BY_DOMAIN.get(Domain.D4_COMPARISON, []))
    d5 = len(FALLACIES_BY_DOMAIN.get(Domain.D5_INFERENCE, []))
    d6 = len(FALLACIES_BY_DOMAIN.get(Domain.D6_REFLECTION, []))

    assert t1 == 36, f"Type 1 count: {t1} != 36"
    assert t2 == 105, f"Type 2 count: {t2} != 105"
    assert t3 == 3, f"Type 3 count: {t3} != 3"
    assert t4 == 6, f"Type 4 count: {t4} != 6"
    assert t5 == 6, f"Type 5 count: {t5} != 6"
    assert d1 == 26, f"D1 count: {d1} != 26"
    assert d2 == 13, f"D2 count: {d2} != 13"
    assert d3 == 16, f"D3 count: {d3} != 16"
    assert d4 == 8, f"D4 count: {d4} != 8"
    assert d5 == 20, f"D5 count: {d5} != 20"
    assert d6 == 22, f"D6 count: {d6} != 22"
    assert len(FALLACIES) == 156, f"Total: {len(FALLACIES)} != 156"
    return True


# Run verification at import time (matches Coq reflexivity proofs)
_verify_counts()
