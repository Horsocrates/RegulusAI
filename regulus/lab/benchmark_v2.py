"""
Regulus AI - v1 vs v2 Benchmark Comparison
============================================

Runs the same questions through both v1 (Socratic) and v2 (audit) pipelines,
then compares accuracy, time, tokens, and correction rates.

Usage:
    python -m regulus.lab.benchmark_v2 --dataset bbeh --n 10 --reasoning-model deepseek
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from regulus.lab.models import LabDB
from regulus.lab.runner import LabRunner


def extract_v2_metrics(db: LabDB, run_id: int) -> dict:
    """Extract v1.0a audit metrics from a v2 run."""
    results = db.get_all_results(run_id)

    metrics = {
        "d1_depths": [],
        "d2_depths": [],
        "d3_objectivity": [],
        "d4_aristotle": [],
        "d5_certainty": [],
        "d6_genuine": [],
        "violation_patterns": [],
        "total_weight_per_q": [],
        "field_population": {
            "d1_depth": 0, "d2_depth": 0, "d3_objectivity_pass": 0,
            "d4_aristotle_ok": 0, "d5_certainty_type": 0, "d6_genuine": 0,
        },
        "false_rejections": 0,
        "diagnostic_warnings": [],
    }

    n = 0
    for r in results:
        if not r.reasoning_json:
            continue
        try:
            rj = json.loads(r.reasoning_json)
            if rj.get("version") != "2.0" or not rj.get("final_audit"):
                continue
        except (json.JSONDecodeError, KeyError):
            continue

        n += 1
        audit = rj["final_audit"]
        metrics["total_weight_per_q"].append(audit.get("total_weight", 0))

        if not r.valid and r.correct:
            metrics["false_rejections"] += 1

        vps = audit.get("violation_patterns", [])
        metrics["violation_patterns"].extend(vps)

        # Diagnostic warnings
        for issue in audit.get("overall_issues", []):
            if isinstance(issue, str) and issue.startswith("DIAG:"):
                metrics["diagnostic_warnings"].append(issue)

        for d in audit.get("domains", []):
            domain = d.get("domain", "")
            if domain == "D1" and d.get("d1_depth") is not None:
                metrics["d1_depths"].append(d["d1_depth"])
                metrics["field_population"]["d1_depth"] += 1
            if domain == "D2" and d.get("d2_depth") is not None:
                metrics["d2_depths"].append(d["d2_depth"])
                metrics["field_population"]["d2_depth"] += 1
            if domain == "D3" and d.get("d3_objectivity_pass") is not None:
                metrics["d3_objectivity"].append(d["d3_objectivity_pass"])
                metrics["field_population"]["d3_objectivity_pass"] += 1
            if domain == "D4" and d.get("d4_aristotle_ok") is not None:
                metrics["d4_aristotle"].append(d["d4_aristotle_ok"])
                metrics["field_population"]["d4_aristotle_ok"] += 1
            if domain == "D5" and d.get("d5_certainty_type"):
                metrics["d5_certainty"].append(d["d5_certainty_type"])
                metrics["field_population"]["d5_certainty_type"] += 1
            if domain == "D6" and d.get("d6_genuine") is not None:
                metrics["d6_genuine"].append(d["d6_genuine"])
                metrics["field_population"]["d6_genuine"] += 1

    metrics["n"] = n
    return metrics


def print_v2_analysis(metrics: dict):
    """Print v1.0a audit analysis summary."""
    n = metrics["n"]
    if n == 0:
        print("\n  No v2 audit data to analyze.")
        return

    print(f"\n{'='*60}")
    print(f"  v1.0a AUDIT SIGNAL ANALYSIS ({n} questions)")
    print(f"{'='*60}")

    print(f"\n  Signal Population:")
    for field, count in metrics["field_population"].items():
        rate = count / n if n else 0
        status = "+" if rate >= 0.8 else ("?" if rate >= 0.5 else "-")
        print(f"    {status} {field:<24} {count}/{n} ({rate:.0%})")

    if metrics["d1_depths"]:
        avg = sum(metrics["d1_depths"]) / len(metrics["d1_depths"])
        print(f"\n  D1 Recognition depth:   avg={avg:.1f}  distribution={dict(sorted(Counter(metrics['d1_depths']).items()))}")
    if metrics["d2_depths"]:
        avg = sum(metrics["d2_depths"]) / len(metrics["d2_depths"])
        print(f"  D2 Clarification depth: avg={avg:.1f}  distribution={dict(sorted(Counter(metrics['d2_depths']).items()))}")

    if metrics["d3_objectivity"]:
        pass_rate = sum(metrics["d3_objectivity"]) / len(metrics["d3_objectivity"])
        warn = " << TOO STRICT" if pass_rate < 0.7 else ""
        print(f"\n  D3 Objectivity pass rate: {pass_rate:.0%}{warn}")
    if metrics["d4_aristotle"]:
        pass_rate = sum(metrics["d4_aristotle"]) / len(metrics["d4_aristotle"])
        print(f"  D4 Aristotle pass rate:  {pass_rate:.0%}")
    if metrics["d6_genuine"]:
        genuine_rate = sum(metrics["d6_genuine"]) / len(metrics["d6_genuine"])
        print(f"  D6 Genuine reflection:   {genuine_rate:.0%}")

    if metrics["d5_certainty"]:
        cert_dist = Counter(metrics["d5_certainty"])
        print(f"\n  D5 Certainty types: {dict(cert_dist.most_common())}")

    if metrics["violation_patterns"]:
        vp_dist = Counter(metrics["violation_patterns"])
        print(f"\n  Violations ({len(metrics['violation_patterns'])} total):")
        for pattern, count in vp_dist.most_common():
            print(f"    {pattern}: {count}")
    else:
        print(f"\n  No violations detected")

    # Diagnostic warnings
    if metrics.get("diagnostic_warnings"):
        diag_types = Counter(
            w.split(" — ")[0] if " — " in w else w.split(" ")[0]
            for w in metrics["diagnostic_warnings"]
        )
        print(f"\n  Diagnostic warnings ({len(metrics['diagnostic_warnings'])} total):")
        for wtype, count in diag_types.most_common():
            print(f"    {wtype}: {count}")
    else:
        print(f"\n  No diagnostic warnings")

    print(f"\n  False rejections (valid=F, correct=T): {metrics['false_rejections']}/{n}")

    if metrics["total_weight_per_q"]:
        avg_w = sum(metrics["total_weight_per_q"]) / len(metrics["total_weight_per_q"])
        print(f"  Avg total weight: {avg_w:.0f}/600")

    print()


def create_comparison_runs(
    runner: LabRunner,
    dataset: str,
    n: int,
    reasoning_model: str,
    provider: str = "openai",
    seed: int = 42,
) -> tuple[int, int]:
    """Create matched v1 and v2 runs for comparison."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    v1_run = runner.create_run(
        name=f"bench_v1_{dataset}_{n}q_{timestamp}",
        total_questions=n,
        num_steps=1,
        dataset=dataset,
        provider=provider,
        concurrency=5,
        mode="v1",
        seed=seed,
    )

    v2_run = runner.create_run(
        name=f"bench_v2_{dataset}_{n}q_{timestamp}",
        total_questions=n,
        num_steps=1,
        dataset=dataset,
        provider=provider,
        concurrency=5,
        mode="v2",
        reasoning_model=reasoning_model,
        seed=seed,
    )

    return v1_run.id, v2_run.id


def compare_runs(db: LabDB, v1_run_id: int, v2_run_id: int) -> dict:
    """Compare results from v1 and v2 runs."""
    v1_run = db.get_run(v1_run_id)
    v2_run = db.get_run(v2_run_id)

    if not v1_run or not v2_run:
        raise ValueError("One or both runs not found")

    v1_results = db.get_all_results(v1_run_id)
    v2_results = db.get_all_results(v2_run_id)

    # Build question → result map
    v1_map = {r.question: r for r in v1_results}
    v2_map = {r.question: r for r in v2_results}

    # Compare matched questions
    common_questions = set(v1_map.keys()) & set(v2_map.keys())

    v1_correct = sum(1 for q in common_questions if v1_map[q].is_passed)
    v2_correct = sum(1 for q in common_questions if v2_map[q].is_passed)
    v1_valid = sum(1 for q in common_questions if v1_map[q].valid)
    v2_valid = sum(1 for q in common_questions if v2_map[q].valid)

    v1_time = sum(v1_map[q].time_seconds for q in common_questions)
    v2_time = sum(v2_map[q].time_seconds for q in common_questions)

    v1_tokens = sum(v1_map[q].total_tokens for q in common_questions)
    v2_tokens = sum(v2_map[q].total_tokens for q in common_questions)

    v1_corrections = sum(v1_map[q].corrections for q in common_questions)
    v2_corrections = sum(v2_map[q].corrections for q in common_questions)

    n = len(common_questions)

    # Per-question comparison
    improvements = []
    regressions = []
    for q in common_questions:
        r1, r2 = v1_map[q], v2_map[q]
        if not r1.is_passed and r2.is_passed:
            improvements.append(q[:80])
        elif r1.is_passed and not r2.is_passed:
            regressions.append(q[:80])

    return {
        "matched_questions": n,
        "v1": {
            "run_id": v1_run_id,
            "mode": "v1",
            "correct": v1_correct,
            "accuracy": v1_correct / n if n else 0,
            "valid_rate": v1_valid / n if n else 0,
            "total_time": round(v1_time, 1),
            "avg_time": round(v1_time / n, 1) if n else 0,
            "total_tokens": v1_tokens,
            "avg_tokens": v1_tokens // n if n else 0,
            "total_corrections": v1_corrections,
        },
        "v2": {
            "run_id": v2_run_id,
            "mode": "v2",
            "reasoning_model": v2_run.reasoning_model,
            "correct": v2_correct,
            "accuracy": v2_correct / n if n else 0,
            "valid_rate": v2_valid / n if n else 0,
            "total_time": round(v2_time, 1),
            "avg_time": round(v2_time / n, 1) if n else 0,
            "total_tokens": v2_tokens,
            "avg_tokens": v2_tokens // n if n else 0,
            "total_corrections": v2_corrections,
        },
        "delta": {
            "accuracy_diff": round((v2_correct - v1_correct) / n, 3) if n else 0,
            "speedup": round(v1_time / v2_time, 2) if v2_time > 0 else 0,
            "token_savings": round(1 - v2_tokens / v1_tokens, 3) if v1_tokens > 0 else 0,
        },
        "improvements": improvements[:10],
        "regressions": regressions[:10],
    }


def print_comparison(comparison: dict):
    """Pretty-print comparison results."""
    n = comparison["matched_questions"]
    v1 = comparison["v1"]
    v2 = comparison["v2"]
    delta = comparison["delta"]

    print(f"\n{'='*60}")
    print(f"  REGULUS v1 vs v2 BENCHMARK COMPARISON")
    print(f"  {n} matched questions")
    print(f"{'='*60}\n")

    print(f"{'Metric':<25} {'v1 (Socratic)':<18} {'v2 (Audit)':<18}")
    print(f"{'-'*60}")
    print(f"{'Accuracy':<25} {v1['accuracy']:.1%}{'':<12} {v2['accuracy']:.1%}")
    print(f"{'Valid rate':<25} {v1['valid_rate']:.1%}{'':<12} {v2['valid_rate']:.1%}")
    print(f"{'Avg time/q':<25} {v1['avg_time']:.1f}s{'':<13} {v2['avg_time']:.1f}s")
    print(f"{'Avg tokens/q':<25} {v1['avg_tokens']:<18} {v2['avg_tokens']}")
    print(f"{'Total corrections':<25} {v1['total_corrections']:<18} {v2['total_corrections']}")

    print(f"\n{'DELTA':=^60}")
    print(f"  Accuracy diff:  {delta['accuracy_diff']:+.1%}")
    print(f"  Speedup:        {delta['speedup']:.1f}x")
    print(f"  Token savings:  {delta['token_savings']:.1%}")

    if comparison["improvements"]:
        print(f"\n  Improvements (v2 fixed what v1 missed):")
        for q in comparison["improvements"]:
            print(f"    + {q}")

    if comparison["regressions"]:
        print(f"\n  Regressions (v1 got right, v2 missed):")
        for q in comparison["regressions"]:
            print(f"    - {q}")

    print()


async def run_benchmark(
    dataset: str = "bbeh",
    n: int = 10,
    reasoning_model: str = "deepseek",
    provider: str = "openai",
    seed: int = 42,
):
    """Run full v1 vs v2 benchmark."""
    runner = LabRunner()

    print(f"Creating benchmark runs: {dataset}, {n} questions, v2 model={reasoning_model}, seed={seed}")
    v1_id, v2_id = create_comparison_runs(runner, dataset, n, reasoning_model, provider, seed=seed)
    print(f"  v1 run #{v1_id}, v2 run #{v2_id}")

    # Run v1
    print(f"\nRunning v1 (Socratic pipeline)...")
    await runner.run_all_steps(v1_id)
    v1_run = runner.get_run(v1_id)
    print(f"  v1 complete: {v1_run.correct_count}/{v1_run.completed_questions} correct in {v1_run.total_time:.1f}s")

    # Run v2
    print(f"\nRunning v2 (Audit pipeline with {reasoning_model})...")
    await runner.run_all_steps(v2_id)
    v2_run = runner.get_run(v2_id)
    print(f"  v2 complete: {v2_run.correct_count}/{v2_run.completed_questions} correct in {v2_run.total_time:.1f}s")

    # Compare
    comparison = compare_runs(runner.db, v1_id, v2_id)
    print_comparison(comparison)

    # v1.0a analysis (v2 only)
    v2_metrics = extract_v2_metrics(runner.db, v2_id)
    print_v2_analysis(v2_metrics)

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Regulus v1 vs v2 benchmark")
    parser.add_argument("--dataset", default="bbeh", choices=["bbeh", "simpleqa"])
    parser.add_argument("--n", type=int, default=10, help="Number of questions")
    parser.add_argument("--reasoning-model", default="deepseek",
                        choices=["deepseek", "claude-thinking", "openai-reasoning"])
    parser.add_argument("--provider", default="openai", choices=["openai", "claude"])
    parser.add_argument("--seed", type=int, default=42, help="Random seed for dataset sampling")
    parser.add_argument("--compare", nargs=2, type=int, metavar=("V1_ID", "V2_ID"),
                        help="Compare existing runs instead of creating new ones")
    parser.add_argument("--analyze", type=int, metavar="RUN_ID",
                        help="Analyze an existing v2 run (generate v1.0a report)")
    args = parser.parse_args()

    if args.analyze:
        db = LabDB()
        run = db.get_run(args.analyze)
        if not run:
            print(f"Run #{args.analyze} not found")
            sys.exit(1)

        metrics = extract_v2_metrics(db, args.analyze)
        print_v2_analysis(metrics)

        if run.mode == "v2":
            from regulus.lab.reports import ReportGenerator
            reporter = ReportGenerator()
            path = reporter.generate_v2_analysis(run)
            print(f"  Report saved to: {path}")
        return
    elif args.compare:
        db = LabDB()
        comparison = compare_runs(db, args.compare[0], args.compare[1])
        print_comparison(comparison)
    else:
        asyncio.run(run_benchmark(args.dataset, args.n, args.reasoning_model, args.provider, seed=args.seed))


if __name__ == "__main__":
    main()
