"""
Download HLE from HuggingFace and split into question/answer files.
Questions go to tests/HLE/questions/ (safe to load)
Answers go to tests/HLE/answers/ (NEVER load in test session)

Usage:
  python tests/HLE/prepare_questions.py [--seed 42] [--n-batches 3] [--batch-size 10]
"""

import json
import os
import random
import argparse
from datasets import load_dataset

HF_TOKEN = os.environ.get("HF_TOKEN", "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")


def prepare(seed=42, n_batches=3, batch_size=10, text_only=True, start_batch=1):
    print(f"Loading HLE dataset (seed={seed}, {n_batches} batches x {batch_size}, start=batch_{start_batch:03d})...")
    dataset = load_dataset("cais/hle", split="test", token=HF_TOKEN)

    items = list(dataset)
    total = len(items)
    print(f"Total items: {total}")

    if text_only:
        items = [q for q in items if not q["image"]]
        print(f"Text-only items: {len(items)}")

    random.seed(seed)
    random.shuffle(items)

    needed = n_batches * batch_size
    if needed > len(items):
        print(f"WARNING: requested {needed} but only {len(items)} available")
        needed = len(items)

    base = os.path.dirname(os.path.abspath(__file__))
    q_dir = os.path.join(base, "questions")
    a_dir = os.path.join(base, ".judge_only", "answers")
    os.makedirs(q_dir, exist_ok=True)
    os.makedirs(a_dir, exist_ok=True)

    for batch_idx in range(n_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(items))
        batch = items[start:end]

        if not batch:
            break

        batch_name = f"batch_{start_batch + batch_idx:03d}"

        # Questions — NO ANSWERS
        questions = [
            {
                "id": q["id"],
                "question": q["question"],
                "answer_type": q["answer_type"],
                "category": q["category"],
                "raw_subject": q["raw_subject"],
            }
            for q in batch
        ]

        q_path = os.path.join(q_dir, f"{batch_name}.json")
        with open(q_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        # Answers — SEPARATE FILE
        answers = [
            {
                "id": q["id"],
                "answer": q["answer"],
            }
            for q in batch
        ]

        a_path = os.path.join(a_dir, f"{batch_name}_answers.json")
        with open(a_path, "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, ensure_ascii=False)

        print(f"\n{batch_name}: {len(batch)} questions")
        for i, q in enumerate(batch, 1):
            print(
                f"  Q{i:02d}  {q['id'][:8]}  {q['raw_subject']:30s}  "
                f"{q['answer_type']:15s}  {q['category']}"
            )

    # Verify no contamination
    print("\n--- Contamination check ---")
    for fname in os.listdir(q_dir):
        fpath = os.path.join(q_dir, fname)
        with open(fpath) as f:
            qs = json.load(f)
        for q in qs:
            if "answer" in q:
                print(f"  FAIL: {fname} contains 'answer' field!")
                return False
    print("  PASS: No answer fields in question files")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare HLE question batches")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-batches", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--start-batch", type=int, default=1, help="Starting batch number (default: 1)")
    args = parser.parse_args()

    prepare(seed=args.seed, n_batches=args.n_batches, batch_size=args.batch_size, start_batch=args.start_batch)
