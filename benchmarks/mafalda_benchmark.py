#!/usr/bin/env python3
"""
Benchmark: Regulus Detector vs MAFALDA (Helwe et al., NAACL 2024)
=================================================================

MAFALDA = 200 gold-standard texts (137 fallacious, 63 clean).
Multi-label with alternatives. 23 fallacy types.

This evaluates at TEXT level (not span level):
  - Level 0: Binary detection (fallacious vs clean)
  - Level 1: Coarse-grained (pathos / logos / ethos)
  - Level 2: Fine-grained (23 types mapped to our 156 taxonomy)

Key: MAFALDA has 63 clean texts → we can measure FALSE POSITIVE rate.
LOGIC dataset had NO clean texts, so this is the first FP measurement.

Usage:
    uv run python benchmarks/mafalda_benchmark.py              # Regex-only
    uv run python benchmarks/mafalda_benchmark.py --llm --provider glm5 --mode cascade
    uv run python benchmarks/mafalda_benchmark.py --verbose
"""

from __future__ import annotations

import json
import os
import sys
import asyncio
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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

from regulus.fallacies.detector import detect, detect_all, DetectionResult
from regulus.fallacies.taxonomy import FallacyType

# =============================================================================
#              MAPPING: MAFALDA 23 types → Our 156 taxonomy
# =============================================================================
#
# MAFALDA has 23 fallacy types + "nothing" + "to clean" (annotation artifacts).
# We map each to the closest set of IDs in our Coq-verified taxonomy.
# "nothing" and "to clean" = no fallacy expected.

MAFALDA_TO_REGULUS: Dict[str, Dict] = {
    "ad hominem": {
        "our_ids": {
            "D1_AD_HOMINEM", "D1_TU_QUOQUE", "D1_GUILT_BY_ASSOCIATION",
            "D1_NAME_CALLING", "D1_TONE_POLICING", "D1_ARGUMENT_FROM_MOTIVES",
            "D1_MIND_READING", "D1_OTHERING", "D1_REDUCTIO_AD_HITLERUM",
            "T1B_BIG_BRAIN_LITTLE_BRAIN",
        },
        "coarse": "ethos",
    },
    "ad populum": {
        "our_ids": {
            "D3_BANDWAGON", "D3_APPEAL_TO_TRADITION", "D3_APPEAL_TO_NATURE",
            "D5_WISDOM_OF_CROWD", "D5_SILENT_MAJORITY",
            "D6_ARGUMENT_FROM_INERTIA", "T4_ECHO_CHAMBER", "T4_GROUPTHINK",
        },
        "coarse": "logos",
    },
    "appeal to anger": {
        "our_ids": {
            "T1B_SCARE_TACTICS", "T1B_PLAYING_ON_EMOTION", "T1B_F_BOMB",
            "T1B_AD_BACULUM",
        },
        "coarse": "pathos",
    },
    "appeal to fear": {
        "our_ids": {
            "T1B_SCARE_TACTICS", "T1B_AD_BACULUM",
            "T1B_WE_HAVE_TO_DO_SOMETHING",
        },
        "coarse": "pathos",
    },
    "appeal to pity": {
        "our_ids": {
            "T1B_APPEAL_TO_PITY", "T1B_SAVE_THE_CHILDREN", "T1B_THE_POUT",
        },
        "coarse": "pathos",
    },
    "appeal to positive emotion": {
        "our_ids": {
            "T1B_PLAYING_ON_EMOTION", "T1B_BRIBERY", "T1B_APPEASEMENT",
        },
        "coarse": "pathos",
    },
    "Appeal to Ridicule": {
        "our_ids": {
            "T1B_PLAYING_ON_EMOTION", "D1_NAME_CALLING",
            "D4_HERO_BUSTING", "D4_SIMPLETONS",
        },
        "coarse": "pathos",
    },
    "appeal to worse problems": {
        "our_ids": {
            "D4_WORST_NEGATES_BAD", "D1_RED_HERRING",
        },
        "coarse": "pathos",
    },
    "causal oversimplification": {
        "our_ids": {
            "D5_POST_HOC", "D5_WHERES_SMOKE", "D5_MAGICAL_THINKING",
            "D5_OVERGENERALIZATION",
        },
        "coarse": "logos",
    },
    "circular reasoning": {
        "our_ids": {
            "T3_CIRCULAR_REASONING", "T3_RATIONALIZATION",
            "D2_PLAIN_TRUTH",
        },
        "coarse": "logos",
    },
    "equivocation": {
        "our_ids": {
            "D2_EQUIVOCATION", "D2_ETYMOLOGICAL", "D2_REIFICATION",
        },
        "coarse": "logos",
    },
    "false analogy": {
        "our_ids": {
            "D4_FALSE_ANALOGY", "D4_SIMPLETONS",
        },
        "coarse": "logos",
    },
    "false causality": {
        "our_ids": {
            "D5_POST_HOC", "D5_WHERES_SMOKE", "D5_SCAPEGOATING",
        },
        "coarse": "logos",
    },
    "false dilemma": {
        "our_ids": {
            "D2_EITHER_OR", "T1B_TINA", "T1B_NO_DISCUSSION",
        },
        "coarse": "logos",
    },
    "hasty generalization": {
        "our_ids": {
            "D5_OVERGENERALIZATION", "D1_HALF_TRUTH",
            "D1_LYING_WITH_STATISTICS", "D1_AVAILABILITY_BIAS",
            "T4_CONFIRMATION_BIAS", "D6_ESSENTIALIZING",
        },
        "coarse": "logos",
    },
    "slippery slope": {
        "our_ids": {
            "D5_SLIPPERY_SLOPE", "D5_OVERGENERALIZATION",
        },
        "coarse": "logos",
    },
    "straw man": {
        "our_ids": {
            "D1_STRAW_MAN", "D2_REDUCTIONISM",
        },
        "coarse": "logos",
    },
    "red herring": {
        "our_ids": {
            "D1_RED_HERRING", "D3_BIG_BUT",
        },
        "coarse": "logos",
    },
    "fallacy of division": {
        "our_ids": {
            "D5_OVERGENERALIZATION", "D4_SIMPLETONS",
        },
        "coarse": "logos",
    },
    "appeal to (false) authority": {
        "our_ids": {
            "T1B_APPEAL_TO_HEAVEN", "D1_STAR_POWER", "D1_TRANSFER",
            "T1B_ALPHABET_SOUP", "T1B_BLIND_LOYALTY",
        },
        "coarse": "ethos",
    },
    "appeal to nature": {
        "our_ids": {
            "D3_APPEAL_TO_NATURE", "T5_APPEAL_NATURE_CONTEXT",
        },
        "coarse": "ethos",
    },
    "appeal to tradition": {
        "our_ids": {
            "D3_APPEAL_TO_TRADITION", "T5_APPEAL_TRADITION_CONTEXT",
            "D6_ARGUMENT_FROM_INERTIA",
        },
        "coarse": "ethos",
    },
    "guilt by association": {
        "our_ids": {
            "D1_GUILT_BY_ASSOCIATION", "D1_REDUCTIO_AD_HITLERUM",
        },
        "coarse": "ethos",
    },
    "tu quoque": {
        "our_ids": {
            "D1_TU_QUOQUE", "D4_DOUBLE_STANDARD",
        },
        "coarse": "ethos",
    },
}

# Labels that mean "no fallacy"
CLEAN_LABELS = {"nothing", "to clean"}

# Reverse lookup: our_id → set of MAFALDA labels
_REVERSE_MAP: Dict[str, Set[str]] = defaultdict(set)
for _mlabel, _mdata in MAFALDA_TO_REGULUS.items():
    for _oid in _mdata["our_ids"]:
        _REVERSE_MAP[_oid].add(_mlabel)


def _get_coarse(our_id: str) -> Optional[str]:
    """Map our fallacy ID to MAFALDA coarse category."""
    for mlabel, mdata in MAFALDA_TO_REGULUS.items():
        if our_id in mdata["our_ids"]:
            return mdata["coarse"]
    return None


# =============================================================================
#                        PARSE MAFALDA EXAMPLES
# =============================================================================

@dataclass
class MAFALDAExample:
    """Parsed MAFALDA example."""
    text: str
    gold_labels: List[str]          # fine-grained types (may include alternatives)
    gold_coarse: List[str]          # coarse categories
    is_fallacious: bool             # True if any non-nothing label
    has_alternatives: bool          # True if multiple valid annotations


def parse_examples(dataset) -> List[MAFALDAExample]:
    """Parse MAFALDA gold standard into structured examples."""
    examples = []
    for ex in dataset:
        labels_raw = ex["labels"]
        # Extract unique fine-grained labels (excluding clean markers)
        fine_labels = list(set(
            l["label"] for l in labels_raw
            if l["label"] not in CLEAN_LABELS
        ))
        coarse_labels = list(set(
            MAFALDA_TO_REGULUS[l]["coarse"]
            for l in fine_labels
            if l in MAFALDA_TO_REGULUS
        ))
        is_fallacious = len(fine_labels) > 0

        # Check for alternatives via sentences_with_labels
        swl = ex.get("sentences_with_labels", "")
        has_alts = False
        if isinstance(swl, str) and swl:
            try:
                swl_dict = json.loads(swl)
                for sent_labels in swl_dict.values():
                    if isinstance(sent_labels, list) and len(sent_labels) > 1:
                        has_alts = True
                        break
            except json.JSONDecodeError:
                pass

        examples.append(MAFALDAExample(
            text=ex["text"],
            gold_labels=fine_labels,
            gold_coarse=coarse_labels,
            is_fallacious=is_fallacious,
            has_alternatives=has_alts,
        ))
    return examples


# =============================================================================
#                        EVALUATION METRICS
# =============================================================================

@dataclass
class BinaryMetrics:
    """Confusion matrix for binary classification."""
    tp: int = 0    # fallacy text, detected fallacy
    fp: int = 0    # clean text, detected fallacy (FALSE ALARM)
    tn: int = 0    # clean text, no detection
    fn: int = 0    # fallacy text, no detection (MISS)

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def specificity(self) -> float:
        return self.tn / (self.tn + self.fp) if (self.tn + self.fp) > 0 else 0.0

    @property
    def fpr(self) -> float:
        """False positive rate."""
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) > 0 else 0.0


@dataclass
class TypeMetrics:
    """Per-type precision/recall/F1."""
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


def evaluate_regex(
    examples: List[MAFALDAExample],
    verbose: bool = False,
) -> Dict:
    """Evaluate regex detector on MAFALDA examples."""
    binary = BinaryMetrics()
    per_type = {label: TypeMetrics(label=label) for label in MAFALDA_TO_REGULUS}
    coarse_metrics = {c: TypeMetrics(label=c) for c in ["pathos", "logos", "ethos"]}

    confusion: Dict[str, Counter] = defaultdict(Counter)
    false_positives: List[Tuple[str, str]] = []

    for ex in examples:
        result = detect(ex.text)

        if ex.is_fallacious:
            # Gold = fallacy
            if result.valid:
                binary.fn += 1
                for gl in ex.gold_labels:
                    if gl in per_type:
                        per_type[gl].fn += 1
                for gc in ex.gold_coarse:
                    coarse_metrics[gc].fn += 1
            else:
                binary.tp += 1
                our_id = result.fallacy.id if result.fallacy else "UNKNOWN"
                our_coarse = _get_coarse(our_id)

                # Check type match (credit if matches ANY gold label)
                matched_type = False
                for gl in ex.gold_labels:
                    if gl in MAFALDA_TO_REGULUS and our_id in MAFALDA_TO_REGULUS[gl]["our_ids"]:
                        per_type[gl].tp += 1
                        matched_type = True
                        break

                if not matched_type:
                    for gl in ex.gold_labels:
                        if gl in per_type:
                            per_type[gl].fn += 1
                    # Count as FP for predicted type
                    predicted_mafalda = _REVERSE_MAP.get(our_id, set())
                    for pm in predicted_mafalda:
                        if pm in per_type and pm not in ex.gold_labels:
                            per_type[pm].fp += 1
                            break
                    if ex.gold_labels:
                        confusion[ex.gold_labels[0]][our_id] += 1

                # Coarse match
                matched_coarse = False
                if our_coarse and our_coarse in ex.gold_coarse:
                    coarse_metrics[our_coarse].tp += 1
                    matched_coarse = True
                if not matched_coarse:
                    for gc in ex.gold_coarse:
                        coarse_metrics[gc].fn += 1
                    if our_coarse and our_coarse not in ex.gold_coarse:
                        coarse_metrics[our_coarse].fp += 1
        else:
            # Gold = clean
            if result.valid:
                binary.tn += 1
            else:
                binary.fp += 1
                our_id = result.fallacy.id if result.fallacy else "UNKNOWN"
                false_positives.append((ex.text[:120], our_id))
                if verbose and len(false_positives) <= 5:
                    print(f"  FALSE POSITIVE: [{our_id}] {ex.text[:100]}...")

    # Macro F1 (fine-grained)
    type_f1s = [m.f1 for m in per_type.values() if (m.tp + m.fn) > 0]
    macro_f1_fine = sum(type_f1s) / len(type_f1s) if type_f1s else 0.0

    # Macro F1 (coarse)
    coarse_f1s = [m.f1 for m in coarse_metrics.values() if (m.tp + m.fn) > 0]
    macro_f1_coarse = sum(coarse_f1s) / len(coarse_f1s) if coarse_f1s else 0.0

    return {
        "total": len(examples),
        "total_fallacious": sum(1 for e in examples if e.is_fallacious),
        "total_clean": sum(1 for e in examples if not e.is_fallacious),
        "binary": binary,
        "per_type": per_type,
        "coarse_metrics": coarse_metrics,
        "macro_f1_fine": macro_f1_fine,
        "macro_f1_coarse": macro_f1_coarse,
        "confusion": dict(confusion),
        "false_positives": false_positives,
    }


# =============================================================================
#                    LLM EVALUATION (async)
# =============================================================================

async def evaluate_llm(
    examples: List[MAFALDAExample],
    provider: str = "glm5",
    mode: str = "cascade",
    concurrency: int = 5,
    verbose: bool = False,
) -> Dict:
    """Evaluate LLM-based detector on MAFALDA."""
    from regulus.fallacies.llm_extractor import LLMFallacyExtractor
    from regulus.fallacies.detector import detect_llm

    client = _create_client(provider)
    extractor = LLMFallacyExtractor(client, cache_enabled=True, mode=mode)

    binary = BinaryMetrics()
    per_type = {label: TypeMetrics(label=label) for label in MAFALDA_TO_REGULUS}
    coarse_metrics = {c: TypeMetrics(label=c) for c in ["pathos", "logos", "ethos"]}
    confusion: Dict[str, Counter] = defaultdict(Counter)
    false_positives: List[Tuple[str, str]] = []
    errors = 0

    sem = asyncio.Semaphore(concurrency)

    async def process_one(ex: MAFALDAExample) -> Tuple[MAFALDAExample, DetectionResult]:
        nonlocal errors
        async with sem:
            try:
                result = await detect_llm(ex.text, extractor)
                return (ex, result)
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [ERROR] {e}", file=sys.stderr)
                return (ex, detect(ex.text))

    print(f"  Processing {len(examples)} examples ({provider}/{mode}, concurrency={concurrency})...")
    start = time.time()
    results_list = await asyncio.gather(*[process_one(ex) for ex in examples])
    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s ({len(examples)/elapsed:.1f} ex/sec)")

    for ex, result in results_list:
        if ex.is_fallacious:
            if result.valid:
                binary.fn += 1
                for gl in ex.gold_labels:
                    if gl in per_type:
                        per_type[gl].fn += 1
                for gc in ex.gold_coarse:
                    coarse_metrics[gc].fn += 1
            else:
                binary.tp += 1
                our_id = result.fallacy.id if result.fallacy else "UNKNOWN"
                our_coarse = _get_coarse(our_id)

                matched_type = False
                for gl in ex.gold_labels:
                    if gl in MAFALDA_TO_REGULUS and our_id in MAFALDA_TO_REGULUS[gl]["our_ids"]:
                        per_type[gl].tp += 1
                        matched_type = True
                        break
                if not matched_type:
                    for gl in ex.gold_labels:
                        if gl in per_type:
                            per_type[gl].fn += 1
                    predicted_mafalda = _REVERSE_MAP.get(our_id, set())
                    for pm in predicted_mafalda:
                        if pm in per_type and pm not in ex.gold_labels:
                            per_type[pm].fp += 1
                            break
                    if ex.gold_labels:
                        confusion[ex.gold_labels[0]][our_id] += 1

                matched_coarse = False
                if our_coarse and our_coarse in ex.gold_coarse:
                    coarse_metrics[our_coarse].tp += 1
                    matched_coarse = True
                if not matched_coarse:
                    for gc in ex.gold_coarse:
                        coarse_metrics[gc].fn += 1
                    if our_coarse and our_coarse not in ex.gold_coarse:
                        coarse_metrics[our_coarse].fp += 1
        else:
            if result.valid:
                binary.tn += 1
            else:
                binary.fp += 1
                our_id = result.fallacy.id if result.fallacy else "UNKNOWN"
                false_positives.append((ex.text[:120], our_id))

    type_f1s = [m.f1 for m in per_type.values() if (m.tp + m.fn) > 0]
    macro_f1_fine = sum(type_f1s) / len(type_f1s) if type_f1s else 0.0
    coarse_f1s = [m.f1 for m in coarse_metrics.values() if (m.tp + m.fn) > 0]
    macro_f1_coarse = sum(coarse_f1s) / len(coarse_f1s) if coarse_f1s else 0.0

    return {
        "total": len(examples),
        "total_fallacious": sum(1 for e in examples if e.is_fallacious),
        "total_clean": sum(1 for e in examples if not e.is_fallacious),
        "binary": binary,
        "per_type": per_type,
        "coarse_metrics": coarse_metrics,
        "macro_f1_fine": macro_f1_fine,
        "macro_f1_coarse": macro_f1_coarse,
        "confusion": dict(confusion),
        "false_positives": false_positives,
        "elapsed_seconds": elapsed,
        "errors": errors,
        "provider": provider,
        "mode": mode,
    }


def _create_client(provider: str):
    """Create LLM client."""
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path, override=True)

    if provider == "glm5":
        from regulus.llm.zhipu import ZhipuClient
        api_key = os.environ.get("ZAI_API_KEY", "")
        if not api_key:
            raise ValueError("ZAI_API_KEY not set")
        return ZhipuClient(api_key=api_key, model="glm-4-plus")
    elif provider == "claude":
        from regulus.llm.claude import ClaudeClient
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return ClaudeClient(api_key=api_key, model="claude-sonnet-4-20250514")
    else:
        raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
#                        RICH OUTPUT
# =============================================================================

def print_results(results: Dict, mode: str = "regex"):
    """Print MAFALDA benchmark results."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console(force_terminal=True)
    b = results["binary"]

    console.print()
    console.print(Panel(
        f"[bold]MAFALDA Benchmark (Helwe et al., NAACL 2024)[/bold]\n"
        f"[dim]200 texts: {results['total_fallacious']} fallacious + "
        f"{results['total_clean']} clean | 23 fallacy types[/dim]\n"
        f"[dim]Detector: {mode}[/dim]",
        border_style="cyan",
    ))

    # Level 0: Binary
    console.print()
    t0 = Table(title="Level 0: Binary Detection", box=box.ROUNDED,
               header_style="bold cyan")
    t0.add_column("Metric", style="bold")
    t0.add_column("Value", justify="right")
    t0.add_row("True Positives (fallacy → detected)", f"{b.tp}")
    t0.add_row("False Negatives (fallacy → missed)", f"[red]{b.fn}[/red]")
    t0.add_row("True Negatives (clean → clean)", f"{b.tn}")
    t0.add_row("False Positives (clean → false alarm)", f"[yellow]{b.fp}[/yellow]")
    t0.add_row("", "")
    t0.add_row("Recall (sensitivity)", f"{b.recall:.1%}")
    t0.add_row("Precision", f"{b.precision:.1%}")
    t0.add_row("F1", f"{b.f1:.1%}")
    t0.add_row("Specificity", f"{b.specificity:.1%}")
    fpr_color = 'red' if b.fpr > 0.3 else 'yellow' if b.fpr > 0.1 else 'green'
    t0.add_row("False Positive Rate", f"[{fpr_color}]{b.fpr:.1%}[/{fpr_color}]")
    console.print(t0)

    # Level 1: Coarse
    console.print()
    t1 = Table(title="Level 1: Coarse Categories (pathos/logos/ethos)",
               box=box.ROUNDED, header_style="bold")
    t1.add_column("Category", style="bold")
    t1.add_column("TP", justify="right", style="green")
    t1.add_column("FN", justify="right", style="red")
    t1.add_column("FP", justify="right", style="yellow")
    t1.add_column("Recall", justify="right")
    t1.add_column("Precision", justify="right")
    t1.add_column("F1", justify="right")

    for cat in ["pathos", "logos", "ethos"]:
        m = results["coarse_metrics"][cat]
        t1.add_row(cat, str(m.tp), str(m.fn), str(m.fp),
                   f"{m.recall:.0%}", f"{m.precision:.0%}", f"{m.f1:.0%}")
    t1.add_row("", "", "", "", "", "",
               f"Macro: {results['macro_f1_coarse']:.1%}")
    console.print(t1)

    # Level 2: Fine-grained
    console.print()
    t2 = Table(title="Level 2: Fine-Grained (23 types)", box=box.ROUNDED,
               header_style="bold")
    t2.add_column("MAFALDA Type", style="bold")
    t2.add_column("TP", justify="right", style="green")
    t2.add_column("FN", justify="right", style="red")
    t2.add_column("FP", justify="right", style="yellow")
    t2.add_column("F1", justify="right")

    for label in sorted(MAFALDA_TO_REGULUS.keys()):
        m = results["per_type"][label]
        if (m.tp + m.fn + m.fp) == 0:
            continue
        t2.add_row(label, str(m.tp), str(m.fn), str(m.fp),
                   f"{m.f1:.0%}" if (m.tp + m.fn) > 0 else "-")
    t2.add_row("", "", "", "",
               f"Macro: {results['macro_f1_fine']:.1%}")
    console.print(t2)

    # False positives
    if results["false_positives"]:
        console.print()
        console.print(f"[bold yellow]False Positives ({len(results['false_positives'])} "
                      f"clean texts incorrectly flagged):[/bold yellow]")
        for text, fid in results["false_positives"][:8]:
            console.print(f"  [yellow]{fid}[/yellow] | [dim]{text}...[/dim]")

    # SOTA comparison
    console.print()
    console.print(Panel(
        f"[bold]MAFALDA SOTA Comparison (text-level)[/bold]\n\n"
        f"  Regulus ({mode}):        Binary F1 = {b.f1:.1%} | "
        f"Coarse F1 = {results['macro_f1_coarse']:.1%} | "
        f"Fine F1 = {results['macro_f1_fine']:.1%}\n"
        f"  GPT-3.5 (SOTA paper):   Binary F1 = 72.0% | "
        f"Coarse F1 = 61.1% | Fine F1 = 48.0%\n"
        f"  Vicuna 13B:             Binary F1 = 71.0% | "
        f"Coarse F1 = 54.2% | Fine F1 = 33.2%\n\n"
        f"[dim]Key metric for us: FPR = {b.fpr:.1%} "
        f"(LOGIC had NO clean texts → FPR was unknown)[/dim]",
        border_style="yellow",
    ))
    console.print()


# =============================================================================
#                        SAVE RESULTS
# =============================================================================

def save_results(results: Dict, mode: str, provider: str = "regex"):
    """Save results as JSON."""
    b = results["binary"]
    output = {
        "dataset": "Chadi1992/MAFALDA",
        "split": "gold_standard",
        "mode": mode,
        "provider": provider,
        "total": results["total"],
        "total_fallacious": results["total_fallacious"],
        "total_clean": results["total_clean"],
        "binary_recall": b.recall,
        "binary_precision": b.precision,
        "binary_f1": b.f1,
        "binary_specificity": b.specificity,
        "false_positive_rate": b.fpr,
        "tp": b.tp, "fp": b.fp, "tn": b.tn, "fn": b.fn,
        "macro_f1_coarse": results["macro_f1_coarse"],
        "macro_f1_fine": results["macro_f1_fine"],
        "per_type": {
            label: {"tp": m.tp, "fn": m.fn, "fp": m.fp, "f1": m.f1}
            for label, m in results["per_type"].items()
        },
        "coarse": {
            cat: {"tp": m.tp, "fn": m.fn, "fp": m.fp, "f1": m.f1}
            for cat, m in results["coarse_metrics"].items()
        },
    }
    if "elapsed_seconds" in results:
        output["elapsed_seconds"] = results["elapsed_seconds"]
        output["errors"] = results.get("errors", 0)

    suffix = f"_llm_{provider}_{mode}" if mode != "regex" else ""
    out_path = os.path.join(os.path.dirname(__file__), f"mafalda_results{suffix}.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {out_path}")


# =============================================================================
#                        MAIN
# =============================================================================

def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    use_llm = "--llm" in sys.argv

    provider = "glm5"
    if "--provider" in sys.argv:
        idx = sys.argv.index("--provider")
        if idx + 1 < len(sys.argv):
            provider = sys.argv[idx + 1]

    mode = "cascade"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]

    concurrency = 5
    if "--concurrency" in sys.argv:
        idx = sys.argv.index("--concurrency")
        if idx + 1 < len(sys.argv):
            concurrency = int(sys.argv[idx + 1])

    print("Loading MAFALDA dataset from HuggingFace...", flush=True)
    ds = load_dataset("Chadi1992/MAFALDA")
    gold = ds["gold_standard"]

    examples = parse_examples(gold)
    n_fallacy = sum(1 for e in examples if e.is_fallacious)
    n_clean = sum(1 for e in examples if not e.is_fallacious)
    print(f"Gold standard: {len(examples)} texts ({n_fallacy} fallacious, {n_clean} clean)")
    print()

    if use_llm:
        print(f"Running LLM detector ({provider}/{mode})...", flush=True)
        results = asyncio.run(evaluate_llm(
            examples, provider=provider, mode=mode,
            concurrency=concurrency, verbose=verbose,
        ))
        print_results(results, mode=f"llm-{provider}-{mode}")
        save_results(results, mode=mode, provider=provider)
    else:
        print("Running regex detector...", flush=True)
        results = evaluate_regex(examples, verbose=verbose)
        print_results(results, mode="regex")
        save_results(results, mode="regex")


if __name__ == "__main__":
    main()
