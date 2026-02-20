#!/usr/bin/env python3
"""
Baseline test: raw GLM-5 with thinking, no Regulus pipeline.
Single-shot prompt → answer. For comparison with full pipeline.

Usage: uv run python baseline_glm5.py hle_seed_math_q2.json
       uv run python baseline_glm5.py hle_seed_math_10q_42.json 3
"""

import anthropic
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env
load_dotenv(override=True)
_here = Path(__file__).resolve().parent
for _ancestor in list(_here.parents):
    _candidate = _ancestor / ".env"
    if _candidate.exists() and _candidate != _here / ".env":
        load_dotenv(_candidate, override=False)
        break

if os.environ.get("ZAI_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
    os.environ["ANTHROPIC_AUTH_TOKEN"] = os.environ["ZAI_API_KEY"]

# Windows encoding fix
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─── CONFIG ───
BASE_URL = "https://api.z.ai/api/anthropic"
MODEL = "glm-5"
THINKING_BUDGET = 64000
MAX_OUTPUT = 128000

api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(base_url=BASE_URL, api_key=api_key)


def run_baseline(question_text: str) -> tuple[str, str, int, int]:
    """Single-shot: question → answer. Returns (answer, thinking, in_tokens, out_tokens)."""

    prompt = f"""Solve this problem. Think step by step. At the very end, give your final answer
inside <final_answer></final_answer> tags. The answer should be concise — just the value.

Question:
{question_text}"""

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_OUTPUT,
        thinking={"type": "enabled", "budget_tokens": THINKING_BUDGET},
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        response = stream.get_final_message()

    text_parts = []
    thinking_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif getattr(block, 'type', '') == "thinking":
            thinking_parts.append(block.thinking)

    text = "\n".join(text_parts)
    thinking = "\n---\n".join(thinking_parts)

    # Extract answer
    match = re.search(r'<final_answer>(.*?)</final_answer>', text, re.DOTALL)
    answer = match.group(1).strip() if match else text.strip()[:200]

    return answer, thinking, response.usage.input_tokens, response.usage.output_tokens


def normalize(s):
    s = s.strip().lower()
    s = re.sub(r'\$+', '', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\frac\{(\d+)\}\{(\d+)\}', r'\1/\2', s)
    sub_map = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
    s = s.translate(sub_map)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def check_answer(got, expected):
    ng = normalize(got)
    ne = normalize(expected)
    if ng == ne:
        return True
    # Numeric
    try:
        def pn(s):
            if '/' in s:
                a, b = s.split('/')
                return float(a) / float(b)
            return float(s)
        return abs(pn(ng) - pn(ne)) < 1e-6
    except:
        pass
    # Contains as token
    if len(ne) >= 1:
        pattern = r'(?<![a-z0-9])' + re.escape(ne) + r'(?![a-z0-9])'
        if re.search(pattern, ng):
            return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python baseline_glm5.py <seed.json> [max_q]")
        sys.exit(1)

    seed_file = Path(sys.argv[1])
    max_q = int(sys.argv[2]) if len(sys.argv) > 2 else None

    with open(seed_file, encoding='utf-8') as f:
        data = json.load(f)

    questions = data["questions"]
    if max_q:
        questions = questions[:max_q]

    print(f"\n{'='*60}")
    print(f"  BASELINE: Raw GLM-5 + Thinking (no Regulus pipeline)")
    print(f"  Model: {MODEL} | Thinking budget: {THINKING_BUDGET}")
    print(f"  Questions: {len(questions)}")
    print(f"{'='*60}")

    results = []
    for i, q in enumerate(questions):
        print(f"\n  [{i+1}/{len(questions)}] {q['hle_id'][:16]}")
        print(f"    Subject: {q['raw_subject']}")
        print(f"    Expected: {q['answer'][:60]}")

        t0 = time.time()
        try:
            answer, thinking, tok_in, tok_out = run_baseline(q["question"])
            elapsed = time.time() - t0
            correct = check_answer(answer, q["answer"])

            print(f"    Got: {answer[:80]}")
            print(f"    Judge: {'CORRECT' if correct else 'INCORRECT'}")
            print(f"    Time: {elapsed:.0f}s | Tokens: {tok_in + tok_out:,}")

            results.append({
                "qid": q["hle_id"],
                "subject": q["raw_subject"],
                "expected": q["answer"],
                "got": answer,
                "correct": correct,
                "time": round(elapsed, 1),
                "tokens": tok_in + tok_out,
                "thinking_excerpt": thinking[:500],
            })
        except Exception as e:
            elapsed = time.time() - t0
            print(f"    ERROR: {e}")
            results.append({"qid": q["hle_id"], "error": str(e), "time": round(elapsed, 1)})

    # Summary
    ok = sum(1 for r in results if r.get("correct"))
    total = sum(1 for r in results if "error" not in r)
    total_tok = sum(r.get("tokens", 0) for r in results)

    print(f"\n{'='*60}")
    print(f"  BASELINE SUMMARY: {ok}/{total} correct ({100*ok/total if total else 0:.0f}%)")
    print(f"  Total tokens: {total_tok:,}")
    print(f"{'='*60}")

    for r in results:
        if "error" in r:
            print(f"  {r['qid'][:16]}: ERROR")
        else:
            s = "✓" if r["correct"] else "✗"
            print(f"  {s} {r['qid'][:16]}: got={r['got'][:40]:40s} exp={r['expected'][:30]}")

    # Save
    outfile = f"baseline_glm5_{len(questions)}q_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump({"model": MODEL, "results": results, "accuracy": ok / total if total else 0}, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {outfile}")


if __name__ == "__main__":
    main()
