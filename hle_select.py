#!/usr/bin/env python3
"""HLE Seed Selection — select questions for Regulus testing."""

from datasets import load_dataset
from datetime import datetime
import json
import random

# ─── CONFIG ─────────────────────────────────────
DOMAIN = "Chemistry"              # category from HLE
SUBJECT = None                    # raw_subject substring (None = all in domain)
ANSWER_TYPE = None                # "exactMatch" | "multipleChoice" | None (both)
TEXT_ONLY = True                  # Exclude questions with images
N_QUESTIONS = 10                  # Start with 10 for pipeline validation
SEED = 42                        # For reproducibility
# ─────────────────────────────────────────────────

def matches_subject(raw_subject, target):
    """Soft match — does raw_subject contain the target keyword."""
    if target is None:
        return True
    return target.lower() in raw_subject.lower()

def select_seeds(dataset, domain, subject=None, answer_type=None,
                 text_only=True, n=10, seed=42):
    """Select seed questions from HLE by given criteria."""
    random.seed(seed)

    candidates = []
    for i, item in enumerate(dataset):
        if item['category'].lower() != domain.lower():
            continue
        if not matches_subject(item['raw_subject'], subject):
            continue
        if answer_type and item['answer_type'] != answer_type:
            continue
        if text_only and item.get('image'):
            continue
        candidates.append(i)

    print(f"Candidates after filtering: {len(candidates)}")

    if len(candidates) < n:
        print(f"WARNING: Only {len(candidates)} available, requested {n}")
        n = len(candidates)

    selected_indices = random.sample(candidates, n)

    seed_set = []
    for idx in selected_indices:
        item = dataset[idx]
        seed_set.append({
            "hle_id": item['id'],
            "hle_index": idx,
            "question": item['question'],
            "answer": item['answer'],
            "answer_type": item['answer_type'],
            "raw_subject": item['raw_subject'],
            "category": item['category'],
            "rationale": item['rationale'],
            "has_image": bool(item.get('image'))
        })

    return seed_set


# ─── MAIN ─────────────────────────────────────────
print("Loading HLE dataset...")
dataset = load_dataset("cais/hle", split="test")
print(f"Total: {len(dataset)}")

seeds = select_seeds(dataset,
                     domain=DOMAIN,
                     subject=SUBJECT,
                     answer_type=ANSWER_TYPE,
                     text_only=TEXT_ONLY,
                     n=N_QUESTIONS,
                     seed=SEED)

print(f"\nSelected {len(seeds)} questions:")
for i, s in enumerate(seeds):
    print(f"  [{i}] {s['raw_subject']} ({s['answer_type']})")
    print(f"      Q: {s['question'][:100]}...")
    print(f"      A: {s['answer'][:80]}")
    print()

# Save seed set
seed_set_meta = {
    "created": datetime.now().isoformat(),
    "domain": DOMAIN,
    "subject": SUBJECT,
    "answer_type": ANSWER_TYPE,
    "text_only": TEXT_ONLY,
    "n_questions": len(seeds),
    "seed": SEED,
    "questions": seeds
}

filename = f"hle_seed_{DOMAIN.lower()}_{len(seeds)}q_{SEED}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(seed_set_meta, f, indent=2, ensure_ascii=False)

print(f"Saved: {filename}")
