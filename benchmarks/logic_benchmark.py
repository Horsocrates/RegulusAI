#!/usr/bin/env python3
"""
Benchmark: Regulus Detector vs LOGIC Dataset (Jin et al., EMNLP 2022)
=====================================================================

Evaluates the regex-based and LLM-based fallacy detectors against the
standard LOGIC dataset (2,680 train / 570 dev / 511 test).

The 13 LOGIC fallacy types are mapped to our 156-fallacy taxonomy.

Usage:
    uv run python benchmarks/logic_benchmark.py              # Regex-only
    uv run python benchmarks/logic_benchmark.py --verbose     # Show misclassifications
    uv run python benchmarks/logic_benchmark.py --llm --provider claude  # LLM mode (legacy)
    uv run python benchmarks/logic_benchmark.py --llm --provider openai  # OpenAI mode
    uv run python benchmarks/logic_benchmark.py --llm --provider deepseek
    uv run python benchmarks/logic_benchmark.py --llm --provider glm5    # ZhipuAI GLM-5
    uv run python benchmarks/logic_benchmark.py --llm --provider glm5 --mode err  # ERR+D1-D6
    uv run python benchmarks/logic_benchmark.py --llm --provider glm5 --mode pipeline  # ERR+D6 TL
    uv run python benchmarks/logic_benchmark.py --llm --provider glm5 --mode cascade  # 2-step cascade
    uv run python benchmarks/logic_benchmark.py --llm --limit 50  # Quick test on 50 examples
    uv run python benchmarks/logic_benchmark.py --llm --mode err  # ERR framework (default)
    uv run python benchmarks/logic_benchmark.py --llm --mode pipeline  # ERR + D6 Team Lead (2 calls)
    uv run python benchmarks/logic_benchmark.py --llm --mode cascade  # Cascade: type → specific ID
    uv run python benchmarks/logic_benchmark.py --llm --mode legacy  # Legacy flat signals
"""

from __future__ import annotations

import sys
import os
import json
import asyncio
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datasets import load_dataset

from regulus.fallacies.detector import detect, detect_all, detect_llm, extract_signals, DetectionResult
from regulus.fallacies.taxonomy import FallacyType, Domain

# =============================================================================
#                     MAPPING: LOGIC labels -> Our taxonomy
# =============================================================================
#
# LOGIC has 13 labels. Our taxonomy has 156 fallacies.
# We map each LOGIC label to the set of our fallacy IDs that should match.
# "detected" = our detector returned one of these IDs (or any fallacy for broad match).

LOGIC_TO_REGULUS: Dict[str, Dict] = {
    # COMPLETE mapping: all 156 taxonomy IDs assigned to LOGIC categories.
    # Based on Coq-verified taxonomy (CompleteFallacyTaxonomy.v):
    #   Type 1 (36): Condition violations → mostly "appeal to emotion" / "intentional" / "credibility"
    #   Type 2 (105): Domain violations → mapped by D1-D6 semantics
    #   Type 3 (3): Sequence violations → "circular reasoning"
    #   Type 4 (6): Syndromes → not directly in LOGIC, mapped to closest
    #   Type 5 (6): Context-dependent → mapped to closest LOGIC type
    #
    # An ID can appear in multiple LOGIC types when semantically appropriate.

    "ad hominem": {
        # D1 object substitution: attack person instead of argument
        "our_ids": {
            "D1_AD_HOMINEM", "D1_TU_QUOQUE", "D1_GUILT_BY_ASSOCIATION",
            "D1_NAME_CALLING", "D1_TONE_POLICING", "D1_ARGUMENT_FROM_MOTIVES",
            "D1_MIND_READING", "D1_OTHERING", "D1_REDUCTIO_AD_HITLERUM",
            "D1_IDENTITY_FALLACY", "D1_BLOOD_IS_THICKER",
            "D1_OLFACTORY_RHETORIC", "D1_PATERNALISM",
            "D4_FUNDAMENTAL_ATTRIBUTION",  # character attribution = ad hominem variant
            "T1B_BIG_BRAIN_LITTLE_BRAIN",  # intellectual ad hominem
        },
        "our_signal": "attacks_person",
        "description": "Attack on person instead of argument",
    },
    "ad populum": {
        # D3 irrelevant criterion: popularity/tradition/nature as proof
        "our_ids": {
            "D3_BANDWAGON", "D3_APPEAL_TO_TRADITION", "D3_APPEAL_TO_NATURE",
            "D3_MORAL_SUPERIORITY", "D3_SOLDIERS_HONOR", "D3_MORTIFICATION",
            "D3_E_FOR_EFFORT", "D3_ESCHATOLOGICAL",
            "D5_WISDOM_OF_CROWD", "D5_SILENT_MAJORITY",
            "T5_APPEAL_TRADITION_CONTEXT", "T5_APPEAL_NATURE_CONTEXT",
            "D6_ARGUMENT_FROM_INERTIA",  # status quo = popularity of current state
            "D6_DEFAULT_BIAS",  # preferring default = status quo bandwagon
            "T4_ECHO_CHAMBER",  # reinforcing views in closed group
            "T4_GROUPTHINK",  # group pressure = bandwagon
        },
        "our_signal": "bandwagon",
        "description": "Appeal to popularity/majority/tradition/nature",
    },
    "appeal to emotion": {
        # Type 1 manipulation: emotional bypass of reasoning
        "our_ids": {
            "T1B_SCARE_TACTICS", "T1B_APPEAL_TO_PITY", "T1B_PLAYING_ON_EMOTION",
            "T1B_SAVE_THE_CHILDREN", "T1B_THE_POUT", "T1B_F_BOMB",
            "T1B_SHOPPING_HUNGRY", "T1B_WE_HAVE_TO_DO_SOMETHING",
            "T1B_AD_BACULUM",  # threat = fear
            "T1B_BRIBERY",  # greed/benefit appeal
            "T1B_PROSOPOLOGY",  # attributing emotions for sympathy
            "T1B_APPEASEMENT",  # emotional avoidance
            "D3_AFFECTIVE",  # emotional framework
            "D5_JOBS_COMFORTER",  # victim blaming through emotion
            "T5_AFFECTIVE_REASONING",  # emotional reasoning
            "D6_VENTING",  # expressing frustration instead of reasoning
        },
        "our_signal": "uses_emotion",
        "description": "Emotional manipulation instead of logic",
    },
    "circular reasoning": {
        # Type 3: sequence violations (D5→D1 feedback loop)
        "our_ids": {
            "T3_CIRCULAR_REASONING", "T3_RATIONALIZATION", "T3_BURDEN_SHIFTING",
            "D2_PLAIN_TRUTH",  # "it's obvious" = circular justification
            "D6_PARALYSIS_OF_ANALYSIS",  # endless loop = circular
            "T4_COGNITIVE_CLOSURE",  # need for answer = closed reasoning loop
        },
        "our_signal": "circular",
        "description": "Conclusion assumed in premises / reasoning backward",
    },
    "equivocation": {
        # D2 meaning drift: terms change meaning within argument
        "our_ids": {
            "D2_EQUIVOCATION", "D2_ETYMOLOGICAL", "D2_REIFICATION",
            "D2_POLITICAL_CORRECTNESS",  # term substitution
            "D2_HEROES_ALL",  # stretching word meaning
        },
        "our_signal": None,
        "description": "Same word used with different meanings",
    },
    "fallacy of credibility": {
        # Authority/credential-based appeals without evidence
        "our_ids": {
            "T1B_APPEAL_TO_HEAVEN", "D1_STAR_POWER", "D1_TRANSFER",
            "T1B_AD_MYSTERIAM", "T1B_ALPHABET_SOUP",
            "T1B_PSEUDO_ESOTERIC",  # hidden knowledge claim
            "D1_JUST_PLAIN_FOLKS",  # fake ordinary-person credibility
            "D1_ROMANTIC_REBEL",  # outsider credibility
            "T1B_BLIND_LOYALTY",  # unquestioned authority
            "T1B_STANDARD_VERSION",  # imposing authorized narrative
            "D6_CALLING_CARDS",  # credentials blocking questions
            "D6_THIRD_PERSON_EFFECT",  # "I'm not affected by bias"
            "D6_DUNNING_KRUGER",  # false self-credentialing
        },
        "our_signal": "false_authority",
        "description": "False/irrelevant authority or credential",
    },
    "fallacy of extension": {
        # Distorting/exaggerating opponent's argument (straw man family)
        "our_ids": {
            "D1_STRAW_MAN", "D2_REDUCTIONISM",
            "D2_OVEREXPLANATION",  # extending argument beyond intent
            "D4_HERO_BUSTING",  # comparing to impossible ideal
            "D4_SIMPLETONS",  # treating all instances as identical
        },
        "our_signal": None,
        "description": "Distorting/extending the opponent's argument",
    },
    "fallacy of logic": {
        # D5 formal inference errors: conclusion doesn't follow
        "our_ids": {
            "D5_NON_SEQUITUR", "D5_EXCLUDED_MIDDLE",
            "D5_ARGUMENT_FROM_IGNORANCE", "D5_ARGUMENT_FROM_CONSEQUENCES",
            "D5_ARGUMENT_FROM_SILENCE",
            "D5_HOYLES_FALLACY",  # probability miscalculation
            "D5_PERSONALIZATION",  # attributing external to personal
            "D5_POSITIVE_THINKING",  # belief → reality
            "D5_TRUST_YOUR_GUT",  # intuition as proof
            "T5_ARGUMENT_CONSEQUENCES_CONTEXT",
            "T5_ARGUMENT_SILENCE_CONTEXT",
            "T5_TRUST_GUT_CONTEXT",
            "D4_FALSE_ANALOGY",  # structural logic error via comparison
            "D4_DOUBLE_STANDARD",  # inconsistent logic
            "D6_APPEAL_TO_CLOSURE",  # accepting conclusion to end uncertainty
            "D6_ARGUMENT_FROM_INCREDULITY",  # rejecting because hard to believe
            "T4_COMPARTMENTALIZATION",  # contradictory beliefs = inconsistent logic
        },
        "our_signal": None,
        "description": "Formal logical errors (non sequitur, etc.)",
    },
    "fallacy of relevance": {
        # Premises irrelevant to conclusion (red herring family)
        "our_ids": {
            "D1_RED_HERRING", "D3_BIG_BUT",
            "D3_MORAL_LICENSING",  # past behavior irrelevant to current claim
            "D3_COST_BIAS",  # cost irrelevant to truth
            "D3_MEASURABILITY",  # only measured things count (irrelevant criterion)
            "D3_PROCRUSTEAN",  # forcing data to fit (irrelevant framework)
            "D3_ABLEISM",  # ability irrelevant to argument
            "D4_TWO_SIDES",  # false balance (irrelevant equivalence)
            "D4_WORST_NEGATES_BAD",  # worse examples irrelevant to current issue
            "D4_SCORING_FALLACY",  # numerical score irrelevant
            "D1_NIMBY",  # personal impact irrelevant to general principle
            "D1_DISCIPLINARY_BLINDERS",  # narrow lens irrelevant to full picture
            "D6_FREE_SPEECH",  # right to speak irrelevant to argument validity
            "D6_MAGIC_WAND",  # absence of perfect solution irrelevant
            "D6_MYOB",  # "not your concern" = irrelevant deflection
            "D6_UNINTENDED_CONSEQUENCES",  # possible consequences irrelevant to truth
            "D6_WRONG_MESSAGE",  # message perception irrelevant to truth
        },
        "our_signal": None,
        "description": "Irrelevant premises (red herring, topic shift)",
    },
    "false causality": {
        # D5 causal errors: mistaken cause-effect relationship
        "our_ids": {
            "D5_POST_HOC", "D5_WHERES_SMOKE", "D5_MAGICAL_THINKING",
            "D5_SCAPEGOATING",
            "D5_WORST_CASE",  # assuming worst outcome = causal thinking error
        },
        "our_signal": "post_hoc_pattern",
        "description": "Mistaken causal inference",
    },
    "false dilemma": {
        # D2 incomplete analysis: artificially limited options
        "our_ids": {
            "D2_EITHER_OR", "T1B_TINA",
            "T1B_NO_DISCUSSION",  # "only one way" = false dilemma
            "T1B_JUST_DO_IT",  # only action vs inaction
            "D2_ACTIONS_CONSEQUENCES",  # vague "consequences" as only alternative
            "D6_FINISH_THE_JOB",  # only options: continue or waste = false dilemma
        },
        "our_signal": "false_dilemma",
        "description": "Artificially limiting options to two",
    },
    "faulty generalization": {
        # D5 scale error + D1 data filtration: over-broad conclusions
        "our_ids": {
            "D5_OVERGENERALIZATION", "D5_SLIPPERY_SLOPE", "D1_HALF_TRUTH",
            "D5_DRAW_OWN_CONCLUSION", "D1_LYING_WITH_STATISTICS",
            "D1_AVAILABILITY_BIAS",
            "D1_POLLYANNA",  # over-optimistic generalization
            "D6_ALL_CROOKS",  # blanket cynical generalization
            "D6_ESSENTIALIZING",  # fixed essence = over-generalization
            "D6_NOTHING_NEW",  # "everything's been seen" = overgeneralization
            "D4_SIMPLETONS",  # treating all instances as identical
            "T4_CONFIRMATION_BIAS",  # selective evidence = biased generalization
            "D6_SUNK_COST",  # past investment generalized to future value
        },
        "our_signal": "overgeneralizes",
        "description": "Hasty/broad generalization from limited evidence",
    },
    "intentional": {
        # Deliberate deception / manipulation
        "our_ids": {
            "D1_STRAW_MAN", "D3_MOVING_GOALPOSTS", "D2_PASSIVE_VOICE",
            "T1B_BIG_LIE", "T1B_GASLIGHTING", "T1B_ALTERNATIVE_TRUTH",
            "T1B_PLAUSIBLE_DENIABILITY", "T1B_MALA_FIDES",
            "T1B_DOG_WHISTLE", "T1B_SCRIPTED_MESSAGE",
            "T1B_OCTOBER_SURPRISE",  # timed deception
            "T1B_NARRATIVE_FALLACY",  # story replaces evidence
            "T1B_INFOTAINMENT",  # mixing entertainment to lower guard
            "T1B_THOUSAND_FLOWERS",  # flooding with contradictions
            "D1_BRAINWASHING",  # systematic source corruption
            "D2_SNOW_JOB",  # overwhelming with jargon
            "D2_DIMINISHED_RESPONSIBILITY",  # redefining responsibility
            "T1A_COMPLEX_QUESTION",  # hidden assumption
            "T1A_TABOO",  # topic declared off-limits
            "T1A_VENUE_FALLACY",  # dismissing by context
            "D6_DELIBERATE_IGNORANCE",  # deliberately not seeking truth
            "D6_NON_RECOGNITION",  # refusing to acknowledge
            "D6_DEFENSIVENESS",  # ego-driven rejection of criticism
            "T4_MOTIVATED_REASONING",  # biased reasoning serving emotional needs
        },
        "our_signal": None,
        "description": "Intentional misrepresentation/deception",
    },
}
# All 156 taxonomy IDs are now mapped to LOGIC categories (100% coverage).


# =============================================================================
#                           EVALUATION METRICS
# =============================================================================

@dataclass
class ClassMetrics:
    """Per-class precision/recall/F1."""
    label: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def evaluate_detection(
    examples: List[Dict],
    verbose: bool = False,
) -> Dict:
    """
    Evaluate regex detector on LOGIC examples.

    We measure TWO things:
      1. Binary detection: did we flag it as a fallacy? (any fallacy)
      2. Type matching: did we detect the RIGHT type?
    """
    # Counters
    total = len(examples)
    detected_any = 0       # We flagged something (any fallacy)
    detected_correct = 0   # We flagged the right type
    detected_wrong = 0     # We flagged wrong type
    not_detected = 0       # We said "valid" (missed)

    per_class = {label: ClassMetrics(label=label) for label in LOGIC_TO_REGULUS}
    confusion: Dict[str, Counter] = defaultdict(Counter)
    misses: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for ex in examples:
        text = ex["source_article"]
        gold_label = ex["logical_fallacies"]
        mapping = LOGIC_TO_REGULUS.get(gold_label)

        if mapping is None:
            continue

        result = detect(text)

        if result.valid:
            # Missed — we said valid but it's a fallacy
            not_detected += 1
            per_class[gold_label].fn += 1
            confusion[gold_label]["MISSED"] += 1
            if verbose and len(misses[gold_label]) < 3:
                misses[gold_label].append((text[:120], "VALID (missed)"))
        else:
            detected_any += 1
            our_id = result.fallacy.id if result.fallacy else "UNKNOWN"

            if our_id in mapping["our_ids"]:
                # Correct type
                detected_correct += 1
                per_class[gold_label].tp += 1
            else:
                # Detected a fallacy, but wrong type
                detected_wrong += 1
                per_class[gold_label].fn += 1
                confusion[gold_label][our_id] += 1
                # Count as FP for whatever class we predicted
                predicted_gold = _reverse_lookup(our_id)
                if predicted_gold and predicted_gold != gold_label:
                    per_class[predicted_gold].fp += 1
                if verbose and len(misses[gold_label]) < 3:
                    misses[gold_label].append(
                        (text[:120], f"Predicted: {our_id}")
                    )

    # Macro F1
    f1_scores = [m.f1 for m in per_class.values() if (m.tp + m.fn) > 0]
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "total": total,
        "detected_any": detected_any,
        "detected_correct": detected_correct,
        "detected_wrong": detected_wrong,
        "not_detected": not_detected,
        "binary_recall": detected_any / total if total > 0 else 0.0,
        "type_accuracy": detected_correct / total if total > 0 else 0.0,
        "type_precision": (
            detected_correct / detected_any if detected_any > 0 else 0.0
        ),
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion": dict(confusion),
        "misses": dict(misses),
    }


# =============================================================================
#                      LLM-BASED EVALUATION (async)
# =============================================================================

async def evaluate_detection_llm(
    examples: List[Dict],
    provider: str = "claude",
    concurrency: int = 5,
    verbose: bool = False,
    mode: str = "err",
) -> Dict:
    """
    Evaluate LLM-based detector on LOGIC examples.

    Uses async concurrency with rate limiting to process examples in parallel.

    Args:
        examples: List of LOGIC dataset examples
        provider: LLM provider ("claude", "openai", "deepseek", "moonshot", "glm5")
        concurrency: Max parallel LLM calls
        verbose: Show misclassification details
        mode: "err" for ERR+D1-D6 framework, "legacy" for flat 18-signal extraction
    """
    from regulus.fallacies.llm_extractor import LLMFallacyExtractor

    # Create LLM client based on provider
    client = _create_client(provider)
    extractor = LLMFallacyExtractor(client, cache_enabled=True, mode=mode)

    # Counters
    total = len(examples)
    detected_any = 0
    detected_correct = 0
    detected_wrong = 0
    not_detected = 0

    per_class = {label: ClassMetrics(label=label) for label in LOGIC_TO_REGULUS}
    confusion: Dict[str, Counter] = defaultdict(Counter)
    misses: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    # Process with semaphore for rate limiting
    sem = asyncio.Semaphore(concurrency)
    errors = 0

    async def process_one(ex: Dict) -> Optional[Tuple[str, DetectionResult]]:
        nonlocal errors
        text = ex["source_article"]
        gold_label = ex["logical_fallacies"]
        mapping = LOGIC_TO_REGULUS.get(gold_label)
        if mapping is None:
            return None

        async with sem:
            try:
                result = await detect_llm(text, extractor)
                return (gold_label, result)
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [ERROR] {e}", file=sys.stderr)
                return (gold_label, detect(text))  # Fallback to regex

    # Run all tasks
    tasks = [process_one(ex) for ex in examples]

    print(f"  Processing {total} examples (concurrency={concurrency})...", flush=True)
    start_time = time.time()

    results_list = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    print(f"  Done in {elapsed:.1f}s ({total / elapsed:.1f} examples/sec)", flush=True)
    if errors > 0:
        print(f"  {errors} LLM errors (fell back to regex)", flush=True)

    # Aggregate results
    for item in results_list:
        if item is None:
            continue

        gold_label, result = item
        mapping = LOGIC_TO_REGULUS[gold_label]

        if result.valid:
            not_detected += 1
            per_class[gold_label].fn += 1
            confusion[gold_label]["MISSED"] += 1
            if verbose and len(misses[gold_label]) < 3:
                text_preview = "..."  # Can't access text here easily
                misses[gold_label].append((text_preview, "VALID (missed)"))
        else:
            detected_any += 1
            our_id = result.fallacy.id if result.fallacy else "UNKNOWN"

            if our_id in mapping["our_ids"]:
                detected_correct += 1
                per_class[gold_label].tp += 1
            else:
                detected_wrong += 1
                per_class[gold_label].fn += 1
                confusion[gold_label][our_id] += 1
                predicted_gold = _reverse_lookup(our_id)
                if predicted_gold and predicted_gold != gold_label:
                    per_class[predicted_gold].fp += 1
                if verbose and len(misses[gold_label]) < 3:
                    misses[gold_label].append(("...", f"Predicted: {our_id}"))

    f1_scores = [m.f1 for m in per_class.values() if (m.tp + m.fn) > 0]
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "total": total,
        "detected_any": detected_any,
        "detected_correct": detected_correct,
        "detected_wrong": detected_wrong,
        "not_detected": not_detected,
        "binary_recall": detected_any / total if total > 0 else 0.0,
        "type_accuracy": detected_correct / total if total > 0 else 0.0,
        "type_precision": (
            detected_correct / detected_any if detected_any > 0 else 0.0
        ),
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion": dict(confusion),
        "misses": dict(misses),
        "elapsed_seconds": elapsed,
        "errors": errors,
        "provider": provider,
        "extraction_mode": mode,
    }


def _create_client(provider: str):
    """Create an LLM client for the given provider. Reads API keys from env/.env."""
    from dotenv import load_dotenv
    # Load from project root .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path, override=True)

    if provider == "claude":
        from regulus.llm.claude import ClaudeClient
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to .env or environment.")
        return ClaudeClient(api_key=api_key, model="claude-sonnet-4-20250514")
    elif provider == "openai":
        from regulus.llm.openai import OpenAIClient
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        return OpenAIClient(api_key=api_key, model="gpt-4o-mini")
    elif provider == "deepseek":
        from regulus.llm.deepseek import DeepSeekClient
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not set.")
        return DeepSeekClient(api_key=api_key)
    elif provider == "moonshot":
        from regulus.llm.moonshot import MoonshotClient
        api_key = os.environ.get("MOONSHOT_API_KEY", "")
        if not api_key:
            raise ValueError("MOONSHOT_API_KEY not set.")
        return MoonshotClient(api_key=api_key)
    elif provider == "glm5":
        from regulus.llm.zhipu import ZhipuClient
        api_key = os.environ.get("ZAI_API_KEY", "")
        if not api_key:
            raise ValueError("ZAI_API_KEY not set. Add it to .env or environment.")
        return ZhipuClient(api_key=api_key, model="glm-4-plus")
    elif provider == "gpt4o":
        from regulus.llm.openai import OpenAIClient
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set.")
        return OpenAIClient(api_key=api_key, model="gpt-4o")
    else:
        raise ValueError(f"Unknown provider: {provider}. Use: claude, openai, gpt4o, deepseek, moonshot, glm5")


def _reverse_lookup(our_id: str) -> Optional[str]:
    """Find which LOGIC label maps to this fallacy ID."""
    for label, mapping in LOGIC_TO_REGULUS.items():
        if our_id in mapping["our_ids"]:
            return label
    return None


# =============================================================================
#                           RICH OUTPUT
# =============================================================================

def print_results(results: Dict, split: str = "test", mode: str = "regex"):
    """Print benchmark results with Rich."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console(force_terminal=True)

    mode_label = "regex-based" if mode == "regex" else f"LLM-based ({results.get('provider', '?')})"

    console.print()
    console.print(Panel(
        f"[bold]LOGIC Dataset Benchmark ({split} split)[/bold]\n"
        f"[dim]Jin et al., EMNLP 2022 — 13 fallacy types[/dim]\n"
        f"[dim]Regulus {mode_label} detector vs {results['total']} examples[/dim]",
        border_style="cyan",
    ))

    # Summary
    console.print()
    summary = Table(title="Overall Results", box=box.ROUNDED, show_header=True,
                    header_style="bold cyan")
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")

    summary.add_row("Total examples", str(results["total"]))
    summary.add_row("Detected (any fallacy)", f"{results['detected_any']} ({results['binary_recall']:.1%})")
    summary.add_row("Correct type", f"{results['detected_correct']} ({results['type_accuracy']:.1%})")
    summary.add_row("Wrong type", str(results["detected_wrong"]))
    summary.add_row("Missed (said valid)", str(results["not_detected"]))
    summary.add_row("", "")
    summary.add_row("[bold]Binary Recall[/bold]", f"[bold]{results['binary_recall']:.1%}[/bold]")
    summary.add_row("[bold]Type Accuracy[/bold]", f"[bold]{results['type_accuracy']:.1%}[/bold]")
    summary.add_row("[bold]Type Precision[/bold]", f"[bold]{results['type_precision']:.1%}[/bold]")
    summary.add_row("[bold]Macro F1[/bold]", f"[bold]{results['macro_f1']:.1%}[/bold]")

    if "elapsed_seconds" in results:
        summary.add_row("", "")
        summary.add_row("Time", f"{results['elapsed_seconds']:.1f}s")
        if results.get("errors", 0) > 0:
            summary.add_row("LLM Errors", str(results["errors"]))

    console.print(summary)

    # Per-class
    console.print()
    class_table = Table(title="Per-Class Results", box=box.ROUNDED, show_header=True,
                        header_style="bold")
    class_table.add_column("LOGIC Label", style="bold")
    class_table.add_column("TP", justify="right", style="green")
    class_table.add_column("FN", justify="right", style="red")
    class_table.add_column("FP", justify="right", style="yellow")
    class_table.add_column("Recall", justify="right")
    class_table.add_column("Precision", justify="right")
    class_table.add_column("F1", justify="right")
    class_table.add_column("Signal", style="dim")

    for label in sorted(LOGIC_TO_REGULUS.keys()):
        m = results["per_class"][label]
        mapping = LOGIC_TO_REGULUS[label]
        signal = mapping.get("our_signal") or "[dim red]none[/dim red]"

        recall_str = f"{m.recall:.0%}" if (m.tp + m.fn) > 0 else "—"
        prec_str = f"{m.precision:.0%}" if (m.tp + m.fp) > 0 else "—"
        f1_str = f"{m.f1:.0%}" if (m.tp + m.fn) > 0 else "—"

        class_table.add_row(
            label, str(m.tp), str(m.fn), str(m.fp),
            recall_str, prec_str, f1_str, signal,
        )

    console.print(class_table)

    # Confusion analysis
    console.print()
    conf_table = Table(title="Top Confusion Patterns", box=box.ROUNDED,
                       show_header=True, header_style="bold")
    conf_table.add_column("Gold Label", style="bold")
    conf_table.add_column("Predicted As")
    conf_table.add_column("Count", justify="right")

    for gold_label, counts in sorted(results["confusion"].items()):
        for predicted, count in counts.most_common(3):
            if count >= 2:
                conf_table.add_row(gold_label, predicted, str(count))

    console.print(conf_table)

    # Comparison with SOTA
    console.print()
    console.print(Panel(
        "[bold]Context: SOTA on LOGIC dataset[/bold]\n\n"
        f"  Regulus ({mode_label}):{' ' * (24 - len(mode_label))}Macro F1 = {results['macro_f1']:.1%}\n"
        "  NL2FOL (neurosymbolic, 2024):  Macro F1 = 78%\n"
        "  Fine-tuned BERT (supervised):   Macro F1 ~ 72%\n"
        "  GPT-4 zero-shot:               Macro F1 ~ 65%\n"
        "  GPT-3.5 zero-shot:             Macro F1 ~ 55%\n\n"
        "[dim]Detection logic is Coq-verified: once signals are correct,[/dim]\n"
        "[dim]classification is theorem-guaranteed.[/dim]",
        border_style="yellow",
    ))

    # Misclassification examples
    if results["misses"]:
        console.print()
        console.print("[bold]Sample misclassifications:[/bold]")
        for gold_label, examples in sorted(results["misses"].items()):
            for text, pred in examples[:2]:
                console.print(f"  [dim]{gold_label}[/dim] -> [red]{pred}[/red]")
                console.print(f"    [dim italic]{text}...[/dim italic]")

    console.print()


# =============================================================================
#                           MAIN
# =============================================================================

def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    use_llm = "--llm" in sys.argv

    # Parse provider
    provider = "claude"
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider = sys.argv[idx + 1]

    # Parse mode (err = ERR+D1-D6 domain-aware, legacy = flat signals)
    mode = "err"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]

    # Parse limit
    limit = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    # Parse concurrency
    concurrency = 5
    if "--concurrency" in sys.argv:
        idx = sys.argv.index("--concurrency")
        if idx + 1 < len(sys.argv):
            concurrency = int(sys.argv[idx + 1])

    print("Loading LOGIC dataset from HuggingFace...", flush=True)
    ds = load_dataset("tasksource/logical-fallacy")

    test_data = [dict(ex) for ex in ds["test"]]
    dev_data = [dict(ex) for ex in ds["dev"]]

    if limit > 0:
        test_data = test_data[:limit]
        print(f"Test set: {len(test_data)} examples (limited from {len(ds['test'])})")
    else:
        print(f"Test set: {len(test_data)} examples")
    print(f"Dev set: {len(dev_data)} examples")
    print()

    if use_llm:
        print(f"Running LLM detector ({provider}, extraction={mode}) on test set...", flush=True)
        results = asyncio.run(evaluate_detection_llm(
            test_data,
            provider=provider,
            concurrency=concurrency,
            verbose=verbose,
            mode=mode,
        ))
        out_name = f"logic_results_llm_{provider}_{mode}.json"
        display_mode = "llm"
    else:
        print("Running regex detector on test set...", flush=True)
        results = evaluate_detection(test_data, verbose=verbose)
        display_mode = "regex"
        out_name = "logic_results.json"

    print_results(results, split="test", mode=display_mode)

    # Also save raw results as JSON
    output = {
        "dataset": "tasksource/logical-fallacy",
        "split": "test",
        "mode": display_mode,
        "extraction_mode": results.get("extraction_mode", mode if use_llm else "regex"),
        "provider": provider if use_llm else "regex",
        "total": results["total"],
        "binary_recall": results["binary_recall"],
        "type_accuracy": results["type_accuracy"],
        "type_precision": results["type_precision"],
        "macro_f1": results["macro_f1"],
        "per_class": {
            label: {
                "tp": m.tp, "fn": m.fn, "fp": m.fp,
                "recall": m.recall, "precision": m.precision, "f1": m.f1,
            }
            for label, m in results["per_class"].items()
        },
    }
    if use_llm:
        output["elapsed_seconds"] = results.get("elapsed_seconds", 0)
        output["errors"] = results.get("errors", 0)

    out_path = os.path.join(os.path.dirname(__file__), out_name)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
