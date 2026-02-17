#!/usr/bin/env python3
"""
Select Math questions from HLE dataset for Regulus testing.
Run: python select_hle_math.py [n_questions] [seed]
Output: hle_seed_math_{n}q_{seed}.json

Requires: pip install datasets
"""

import json
import random
import sys
from datetime import datetime

# Fix Windows cp1251 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def main():
    n_questions = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    print(f"Loading HLE dataset...")
    from datasets import load_dataset
    ds = load_dataset("cais/hle", split="test")
    print(f"  Total questions: {len(ds)}")

    # ─── CATEGORY OVERVIEW ───
    cats = {}
    for row in ds:
        cat = row["category"]
        cats[cat] = cats.get(cat, 0) + 1

    print(f"\n  Category distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        pct = 100 * count / len(ds)
        print(f"    {cat:40s} {count:4d} ({pct:.1f}%)")

    # ─── FILTER: Math, text-only ───
    math_questions = []
    for row in ds:
        # Category filter: "Math" (actual HLE category name)
        if row["category"] != "Math":
            continue
        # Text-only filter: skip if image path is non-empty
        img = row.get("image")
        if img:  # non-empty string = has image
            continue
        math_questions.append(row)

    print(f"\n  Math text-only questions: {len(math_questions)}")

    if not math_questions:
        print("  ERROR: No math text-only questions found!")
        print("  Check category names in the dataset.")
        return

    # ─── ANSWER TYPE BREAKDOWN ───
    types = {}
    for q in math_questions:
        t = q["answer_type"]
        types[t] = types.get(t, 0) + 1
    print(f"  Answer types:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")

    # ─── SUBJECT BREAKDOWN (top 15) ───
    subjects = {}
    for q in math_questions:
        s = q["raw_subject"]
        subjects[s] = subjects.get(s, 0) + 1
    print(f"\n  Top 15 raw_subjects:")
    for s, c in sorted(subjects.items(), key=lambda x: -x[1])[:15]:
        print(f"    {s}: {c}")

    # ─── SELECT ───
    random.seed(seed)
    selected = random.sample(math_questions, min(n_questions, len(math_questions)))

    print(f"\n  Selected {len(selected)} questions (seed={seed}):")
    for i, q in enumerate(selected):
        ans_preview = q["answer"][:40]
        q_preview = q["question"][:80].replace('\n', ' ')
        print(f"    {i+1}. [{q['answer_type'][:5]}] {q['raw_subject'][:25]:25s} | ans={ans_preview}")
        print(f"       {q_preview}...")

    # ─── BUILD SEED FILE ───
    seed_data = {
        "domain": "Mathematics",
        "category_filter": "Math",
        "text_only": True,
        "n_questions": len(selected),
        "seed": seed,
        "created": datetime.now().isoformat(),
        "source": "cais/hle",
        "questions": []
    }

    for q in selected:
        seed_data["questions"].append({
            "hle_id": q["id"],
            "question": q["question"],
            "answer": q["answer"],
            "answer_type": q["answer_type"],
            "raw_subject": q["raw_subject"],
            "category": q["category"],
        })

    outfile = f"hle_seed_math_{len(selected)}q_{seed}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(seed_data, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved: {outfile}")
    print(f"  Run: python hle_pilot.py {outfile}")


if __name__ == "__main__":
    main()
