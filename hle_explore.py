#!/usr/bin/env python3
"""HLE Dataset Exploration — understand distribution before selecting seeds."""

from datasets import load_dataset
from collections import Counter
import json

print("Loading HLE dataset...")
dataset = load_dataset("cais/hle", split="test")
print(f"Total questions: {len(dataset)}")

# 1. All unique categories
categories = Counter(item['category'] for item in dataset)
print("\n=== CATEGORIES ===")
for cat, count in categories.most_common():
    print(f"  {cat}: {count}")

# 2. All unique raw_subjects
subjects = Counter(item['raw_subject'] for item in dataset)
print(f"\n=== RAW SUBJECTS (total unique: {len(subjects)}) ===")
for subj, count in subjects.most_common(50):
    print(f"  {subj}: {count}")

# 3. Answer type distribution
answer_types = Counter(item['answer_type'] for item in dataset)
print(f"\n=== ANSWER TYPES ===")
for at, count in answer_types.most_common():
    print(f"  {at}: {count}")

# 4. Text-only vs multimodal
text_only = sum(1 for item in dataset if not item.get('image'))
print(f"\n=== MODALITY ===")
print(f"  Text-only: {text_only}")
print(f"  With image: {len(dataset) - text_only}")

# 5. Category × answer_type cross
print(f"\n=== CATEGORY × ANSWER_TYPE ===")
cross = Counter((item['category'], item['answer_type']) for item in dataset)
for (cat, at), count in sorted(cross.items()):
    print(f"  {cat} | {at}: {count}")

# 6. Category × text-only
print(f"\n=== CATEGORY × TEXT-ONLY ===")
cross2 = Counter()
for item in dataset:
    cat = item['category']
    is_text = "text" if not item.get('image') else "img"
    cross2[(cat, is_text)] += 1
for (cat, mod), count in sorted(cross2.items()):
    print(f"  {cat} | {mod}: {count}")

# Save index for quick access
index = {}
for i, item in enumerate(dataset):
    cat = item['category']
    subj = item['raw_subject']
    at = item['answer_type']
    has_image = bool(item.get('image'))

    key = f"{cat}|{subj}|{at}|{'img' if has_image else 'text'}"
    if key not in index:
        index[key] = []
    index[key].append(i)

with open("hle_index.json", "w") as f:
    json.dump(index, f, indent=2)

print(f"\nIndex saved: {len(index)} unique buckets")
