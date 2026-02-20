"""
Compare any two participants' verdicts and generate comparison tables.

Participants:
  p1        = Raw Opus 4.6 (no tools, no structure)
  p2_opus_tools  = Opus 4.6 with tools (no D1-D6 structure) — ablation control
  p3        = Opus 4.6 with tools + D1-D6 agents (full pipeline)

Usage:
  python tests/HLE/compare.py --all                                       # P1 vs P2_tools
  python tests/HLE/compare.py --all --left p1 --right p3                  # P1 vs P3
  python tests/HLE/compare.py --all --left p2_opus_tools --right p3            # P2 vs P3 (structure effect)
  python tests/HLE/compare.py --batch batch_004 --left p1 --right p3

Reads from .judge_only/verdicts/, outputs to comparison/.
"""

import json
import os
import argparse
from collections import Counter


def classify(left_correct: bool, right_correct: bool) -> str:
    """Classify a question pair. LIFT = right got it, left didn't."""
    if right_correct and not left_correct:
        return "LIFT"
    if right_correct and left_correct:
        return "BOTH"
    if not right_correct and left_correct:
        return "HURT"
    return "NEITHER"


def compare_batch(batch_name: str, base: str, left: str = "p1", right: str = "p2"):
    judge_dir = os.path.join(base, ".judge_only")
    left_path = os.path.join(judge_dir, "verdicts", f"{left}_{batch_name}_verdict.json")
    right_path = os.path.join(judge_dir, "verdicts", f"{right}_{batch_name}_verdict.json")

    if not os.path.exists(left_path):
        print(f"  Missing {left.upper()} verdict: {left_path}")
        return None
    if not os.path.exists(right_path):
        print(f"  Missing {right.upper()} verdict: {right_path}")
        return None

    with open(left_path, encoding="utf-8") as f:
        left_data = json.load(f)
    with open(right_path, encoding="utf-8") as f:
        right_data = json.load(f)

    # Load questions for subject info
    q_path = os.path.join(base, "questions", f"{batch_name}.json")
    q_map = {}
    if os.path.exists(q_path):
        with open(q_path, encoding="utf-8") as f:
            for q in json.load(f):
                q_map[q["id"]] = q

    left_map = {v["question_id"]: v for v in left_data["verdicts"]}
    right_map = {v["question_id"]: v for v in right_data["verdicts"]}

    all_ids = list(left_map.keys() | right_map.keys())
    rows = []
    cats = Counter()

    L = left.upper()
    R = right.upper()

    for qid in sorted(all_ids):
        lv = left_map.get(qid, {})
        rv = right_map.get(qid, {})
        l_ok = lv.get("correct", False)
        r_ok = rv.get("correct", False)
        cat = classify(l_ok, r_ok)
        cats[cat] += 1

        q_info = q_map.get(qid, {})
        rows.append({
            "question_id": qid,
            "subject": q_info.get("raw_subject", "?"),
            "category": q_info.get("category", "?"),
            "answer_type": q_info.get("answer_type", "?"),
            f"{left}_correct": l_ok,
            f"{right}_correct": r_ok,
            "delta": cat,
            f"{left}_answer": lv.get("extracted_final_answer", "?"),
            f"{right}_answer": rv.get("extracted_final_answer", "?"),
        })

    total = len(rows)
    left_total = sum(1 for r in rows if r[f"{left}_correct"])
    right_total = sum(1 for r in rows if r[f"{right}_correct"])

    result = {
        "batch": batch_name,
        "left": left,
        "right": right,
        "total": total,
        f"{left}_correct": left_total,
        f"{left}_accuracy": round(left_total / total * 100, 1) if total else 0,
        f"{right}_correct": right_total,
        f"{right}_accuracy": round(right_total / total * 100, 1) if total else 0,
        "lift": cats["LIFT"],
        "both": cats["BOTH"],
        "hurt": cats["HURT"],
        "neither": cats["NEITHER"],
        "rows": rows,
    }

    # Print table
    print(f"\n{'='*70}")
    print(f"  {batch_name}: {L}={left_total}/{total} ({result[f'{left}_accuracy']}%)  "
          f"{R}={right_total}/{total} ({result[f'{right}_accuracy']}%)")
    print(f"  LIFT={cats['LIFT']}  BOTH={cats['BOTH']}  "
          f"HURT={cats['HURT']}  NEITHER={cats['NEITHER']}")
    print(f"{'='*70}")
    print(f"  {'Q':3s}  {'Subject':25s}  {L:4s}  {R:4s}  {'Delta':8s}")
    print(f"  {'-'*3}  {'-'*25}  {'-'*4}  {'-'*4}  {'-'*8}")
    for i, r in enumerate(rows, 1):
        ls = "+" if r[f"{left}_correct"] else "x"
        rs = "+" if r[f"{right}_correct"] else "x"
        print(f"  {i:3d}  {r['subject'][:25]:25s}  {ls:4s}  {rs:4s}  {r['delta']:8s}")

    # Save
    suffix = f"{left}_vs_{right}"
    fname = f"{batch_name}_comparison_{suffix}.json"
    out_path = os.path.join(base, "comparison", fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to {out_path}")

    return result


def compare_all(base: str, left: str = "p1", right: str = "p2"):
    verdicts_dir = os.path.join(base, ".judge_only", "verdicts")
    if not os.path.exists(verdicts_dir):
        print("No verdicts directory found")
        return

    # Find batches that have BOTH left and right verdicts
    left_batches = set()
    right_batches = set()
    for f in os.listdir(verdicts_dir):
        if f.startswith(f"{left}_") and f.endswith("_verdict.json"):
            batch = f.replace(f"{left}_", "").replace("_verdict.json", "")
            left_batches.add(batch)
        if f.startswith(f"{right}_") and f.endswith("_verdict.json"):
            batch = f.replace(f"{right}_", "").replace("_verdict.json", "")
            right_batches.add(batch)

    batches = left_batches & right_batches
    if not batches:
        print(f"No batches with both {left.upper()} and {right.upper()} verdicts")
        return

    all_results = []
    for batch in sorted(batches):
        r = compare_batch(batch, base, left, right)
        if r:
            all_results.append(r)

    if not all_results:
        print("No completed batches to compare")
        return

    L = left.upper()
    R = right.upper()

    # Summary across all batches
    total = sum(r["total"] for r in all_results)
    left_total = sum(r[f"{left}_correct"] for r in all_results)
    right_total = sum(r[f"{right}_correct"] for r in all_results)
    lift = sum(r["lift"] for r in all_results)
    both = sum(r["both"] for r in all_results)
    hurt = sum(r["hurt"] for r in all_results)
    neither = sum(r["neither"] for r in all_results)

    summary = {
        "left": left,
        "right": right,
        "total_questions": total,
        "batches": len(all_results),
        f"{left}_correct": left_total,
        f"{left}_accuracy": round(left_total / total * 100, 1) if total else 0,
        f"{right}_correct": right_total,
        f"{right}_accuracy": round(right_total / total * 100, 1) if total else 0,
        "lift": lift,
        "both": both,
        "hurt": hurt,
        "neither": neither,
    }

    print(f"\n{'='*70}")
    print(f"  OVERALL ({total} questions across {len(all_results)} batches)")
    print(f"  {L}: {left_total}/{total} ({summary[f'{left}_accuracy']}%)")
    print(f"  {R}: {right_total}/{total} ({summary[f'{right}_accuracy']}%)")
    print(f"  LIFT={lift}  BOTH={both}  HURT={hurt}  NEITHER={neither}")
    print(f"{'='*70}")

    suffix = f"{left}_vs_{right}"
    fname = f"summary_{suffix}.json"
    out_path = os.path.join(base, "comparison", fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare participant verdicts")
    parser.add_argument("--batch", help="Single batch name")
    parser.add_argument("--all", action="store_true", help="Compare all batches")
    parser.add_argument("--left", default="p1", help="Left participant (default: p1)")
    parser.add_argument("--right", default="p2_opus_tools", help="Right participant (default: p2_opus_tools)")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))

    if args.all:
        compare_all(base, args.left, args.right)
    elif args.batch:
        compare_batch(args.batch, base, args.left, args.right)
    else:
        parser.print_help()
