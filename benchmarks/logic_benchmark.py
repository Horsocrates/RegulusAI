#!/usr/bin/env python3
"""
Benchmark: Regulus Detector vs LOGIC Dataset (Jin et al., EMNLP 2022)
=====================================================================

Evaluates the regex-based fallacy detector against the standard
LOGIC dataset (2,680 train / 570 dev / 511 test).

The 13 LOGIC fallacy types are mapped to our 156-fallacy taxonomy.

Usage:
    uv run python benchmarks/logic_benchmark.py              # Full benchmark
    uv run python benchmarks/logic_benchmark.py --verbose    # Show misclassifications
    uv run python benchmarks/logic_benchmark.py --examples 5 # Show N examples per class
"""

from __future__ import annotations

import sys
import os
import json
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

from regulus.fallacies.detector import detect, detect_all, extract_signals, DetectionResult
from regulus.fallacies.taxonomy import FallacyType, Domain

# =============================================================================
#                     MAPPING: LOGIC labels -> Our taxonomy
# =============================================================================
#
# LOGIC has 13 labels. Our taxonomy has 156 fallacies.
# We map each LOGIC label to the set of our fallacy IDs that should match.
# "detected" = our detector returned one of these IDs (or any fallacy for broad match).

LOGIC_TO_REGULUS: Dict[str, Dict] = {
    "ad hominem": {
        "our_ids": {"D1_AD_HOMINEM", "D1_TU_QUOQUE", "D1_POISONING_THE_WELL",
                     "D1_GUILT_BY_ASSOCIATION", "D1_GENETIC_FALLACY"},
        "our_signal": "attacks_person",
        "description": "Attack on person instead of argument",
    },
    "ad populum": {
        "our_ids": {"D3_BANDWAGON", "D3_APPEAL_TO_TRADITION", "D3_APPEAL_TO_NOVELTY"},
        "our_signal": "bandwagon",
        "description": "Appeal to popularity/majority",
    },
    "appeal to emotion": {
        "our_ids": {"T1B_SCARE_TACTICS", "T1B_APPEAL_TO_PITY", "T1B_APPEAL_TO_FLATTERY"},
        "our_signal": "uses_emotion",
        "description": "Emotional manipulation instead of logic",
    },
    "circular reasoning": {
        "our_ids": {"T3_CIRCULAR_REASONING"},
        "our_signal": "circular",
        "description": "Conclusion assumed in premises",
    },
    "equivocation": {
        "our_ids": {"D2_EQUIVOCATION", "D2_AMPHIBOLY"},
        "our_signal": None,  # Hard to detect with regex
        "description": "Same word used with different meanings",
    },
    "fallacy of credibility": {
        "our_ids": {"T1B_APPEAL_TO_HEAVEN", "D1_APPEAL_TO_AUTHORITY"},
        "our_signal": "false_authority",
        "description": "False/irrelevant authority",
    },
    "fallacy of extension": {
        "our_ids": {"D1_STRAW_MAN"},
        "our_signal": None,  # Straw man hard to detect with regex
        "description": "Distorting the opponent's argument (straw man)",
    },
    "fallacy of logic": {
        "our_ids": {"D5_AFFIRMING_CONSEQUENT", "D5_DENYING_ANTECEDENT",
                     "D5_NON_SEQUITUR"},
        "our_signal": None,  # Formal logic errors need structural analysis
        "description": "Formal logical errors (affirming consequent, etc.)",
    },
    "fallacy of relevance": {
        "our_ids": {"D3_IRRELEVANT_CONCLUSION", "D1_RED_HERRING"},
        "our_signal": None,  # Red herring = topic change, hard with regex
        "description": "Irrelevant premises (red herring)",
    },
    "false causality": {
        "our_ids": {"D5_POST_HOC", "D5_FALSE_CAUSE", "D5_CORRELATION_CAUSATION"},
        "our_signal": "post_hoc_pattern",
        "description": "Mistaken causal inference",
    },
    "false dilemma": {
        "our_ids": {"D2_EITHER_OR"},
        "our_signal": "false_dilemma",
        "description": "Artificially limiting options to two",
    },
    "faulty generalization": {
        "our_ids": {"D5_OVERGENERALIZATION", "D5_SLIPPERY_SLOPE",
                     "D1_HALF_TRUTH", "D1_ANECDOTAL_EVIDENCE"},
        "our_signal": "overgeneralizes",
        "description": "Hasty/broad generalization from limited evidence",
    },
    "intentional": {
        "our_ids": {"D1_STRAW_MAN", "D3_MOVING_GOALPOSTS", "D2_PASSIVE_VOICE"},
        "our_signal": None,  # Deliberate deception hard to detect
        "description": "Intentional misrepresentation/deception",
    },
}


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
    Evaluate detector on LOGIC examples.

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


def _reverse_lookup(our_id: str) -> Optional[str]:
    """Find which LOGIC label maps to this fallacy ID."""
    for label, mapping in LOGIC_TO_REGULUS.items():
        if our_id in mapping["our_ids"]:
            return label
    return None


# =============================================================================
#                           RICH OUTPUT
# =============================================================================

def print_results(results: Dict, split: str = "test"):
    """Print benchmark results with Rich."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console(force_terminal=True)

    console.print()
    console.print(Panel(
        f"[bold]LOGIC Dataset Benchmark ({split} split)[/bold]\n"
        f"[dim]Jin et al., EMNLP 2022 — 13 fallacy types[/dim]\n"
        f"[dim]Regulus regex-based detector vs {results['total']} examples[/dim]",
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
        f"  Regulus (regex signals):       Macro F1 = {results['macro_f1']:.1%}\n"
        "  NL2FOL (neurosymbolic, 2024):  Macro F1 = 78%\n"
        "  Fine-tuned BERT (supervised):   Macro F1 ~ 72%\n"
        "  GPT-4 zero-shot:               Macro F1 ~ 65%\n"
        "  GPT-3.5 zero-shot:             Macro F1 ~ 55%\n\n"
        "[dim]Our detector uses ONLY regex patterns (no ML, no LLM).[/dim]\n"
        "[dim]The gap is in signal extraction, not detection logic.[/dim]\n"
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

    print("Loading LOGIC dataset from HuggingFace...", flush=True)
    ds = load_dataset("tasksource/logical-fallacy")

    test_data = [dict(ex) for ex in ds["test"]]
    dev_data = [dict(ex) for ex in ds["dev"]]

    print(f"Test set: {len(test_data)} examples")
    print(f"Dev set: {len(dev_data)} examples")
    print()
    print("Running detector on test set...", flush=True)

    results = evaluate_detection(test_data, verbose=verbose)
    print_results(results, split="test")

    # Also save raw results as JSON
    output = {
        "dataset": "tasksource/logical-fallacy",
        "split": "test",
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

    out_path = os.path.join(os.path.dirname(__file__), "logic_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
