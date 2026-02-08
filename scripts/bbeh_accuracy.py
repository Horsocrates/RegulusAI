"""BBEH Accuracy Benchmark: Raw Claude vs Regulus v2 (ToS).

Compares answer correctness (not just structural quality) between:
1. Raw Claude — same model, no pipeline, no ToS prompt
2. Regulus v2 + ToS — calibrated auditor + ToS system prompt

Uses LLM judge (gpt-4o-mini) for robust answer matching.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from regulus.data.bbeh import load_dataset

N = 25
CONCURRENCY = 5
JUDGE_MODEL = "gpt-4o-mini"


# ─── Raw Claude baseline ──────────────────────────────────────────

async def raw_claude_answer(query: str, client, model: str) -> dict:
    """Call Claude directly — no Regulus pipeline, no ToS prompt."""
    start = time.time()
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": query}],
    )
    elapsed = time.time() - start
    text = response.content[0].text
    return {
        "answer": text,
        "time": round(elapsed, 1),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


# ─── LLM Judge ────────────────────────────────────────────────────

async def llm_judge(predicted: str, expected: str, question_snippet: str, judge_client) -> dict:
    """Use gpt-4o-mini to judge if predicted matches expected answer."""
    prompt = f"""You are an answer-matching judge. Determine if the model's answer is correct.

Question (first 300 chars): {question_snippet[:300]}

Expected answer: {expected}

Model's full response (may be long — look for the final answer):
{predicted[:3000]}

Rules:
- The model's answer is CORRECT if it contains or implies the expected answer.
- Ignore extra explanation, domain tags (<D1>...</D6>), formatting differences.
- For numbers: 5.84 and 5.84000 are the same. -557 and -557.0 are the same.
- For multiple choice: (A) and A are the same.
- For yes/no: "Yes" and "yes" are the same.
- For lists: "0,0,1" and "0, 0, 1" are the same. Order matters.
- If the model gives a clearly wrong answer or says "cannot determine", mark INCORRECT.
- If the model's answer is close but not exactly right (e.g., rounding error), mark INCORRECT.

Reply with EXACTLY one line in this format:
VERDICT: CORRECT or INCORRECT
REASON: <one sentence explanation>"""

    response = await judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=100,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()

    correct = "CORRECT" in text.split("\n")[0] and "INCORRECT" not in text.split("\n")[0]
    reason = ""
    for line in text.split("\n"):
        if line.startswith("REASON:"):
            reason = line[7:].strip()

    return {"correct": correct, "reason": reason, "raw_judge": text}


# ─── Quick heuristic pre-check (skip judge if obvious match) ─────

def quick_match(predicted: str, expected: str) -> bool | None:
    """Fast heuristic check. Returns True/False if confident, None if unsure."""
    exp = expected.strip().lower()

    # Extract answer from common patterns in predicted text
    candidates = [predicted]

    # Look for explicit answer markers
    for pattern in [
        r'(?i)(?:the\s+)?(?:final\s+)?answer\s*(?:is)?[:\s]+(.+?)(?:\.|$)',
        r'(?i)\*\*(?:final\s+)?answer[:\s]*\*\*[:\s]*(.+?)(?:\n|$)',
        r'(?i)(?:therefore|thus|so|hence)[,:\s]+(?:the answer is\s+)?(.+?)(?:\.|$)',
    ]:
        for m in re.finditer(pattern, predicted):
            candidates.append(m.group(1).strip())

    # Also try last non-empty line
    lines = [l.strip() for l in predicted.strip().split("\n") if l.strip()]
    if lines:
        candidates.append(lines[-1])

    for cand in candidates:
        c = cand.strip().lower()
        # Remove trailing punctuation
        c = c.rstrip(".")

        # Exact match
        if c == exp:
            return True

        # Expected contained in candidate
        if exp in c and len(exp) > 1:
            return True

        # Number comparison
        try:
            if abs(float(c) - float(exp)) < 0.001:
                return True
        except (ValueError, OverflowError):
            pass

    return None  # Unsure — need LLM judge


# ─── Main ─────────────────────────────────────────────────────────

async def main():
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI

    anthropic_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Model must match what Regulus uses
    MODEL = "claude-sonnet-4-5-20250929"

    # Load same 25 questions (seed=42)
    items = load_dataset(n=N, seed=42)
    print(f"BBEH Accuracy Benchmark: {len(items)} questions")
    print(f"Raw model: {MODEL}")
    print(f"Judge: {JUDGE_MODEL}")
    print()

    # ── Load existing Regulus v2+ToS results ──
    tos_path = Path(__file__).parent.parent / "data" / "bbeh_25_results_tos.json"
    if not tos_path.exists():
        print(f"ERROR: {tos_path} not found. Run bbeh_25_run.py --tos first.")
        sys.exit(1)

    with open(tos_path, "r", encoding="utf-8") as f:
        regulus_results = json.load(f)

    print(f"Loaded {len(regulus_results)} Regulus v2+ToS results")

    # ── Run raw Claude baseline ──
    print("\n=== Running Raw Claude Baseline ===")
    sem = asyncio.Semaphore(CONCURRENCY)
    completed = 0

    async def run_raw(idx, item):
        nonlocal completed
        async with sem:
            result = await raw_claude_answer(item.problem, anthropic_client, MODEL)
            completed += 1
            print(f"  [{completed}/{N}] Q{idx+1} done ({result['time']}s)")
            return {"idx": idx, **result}

    raw_start = time.time()
    raw_tasks = [run_raw(i, item) for i, item in enumerate(items)]
    raw_results = await asyncio.gather(*raw_tasks)
    raw_elapsed = time.time() - raw_start
    raw_results.sort(key=lambda r: r["idx"])

    raw_tokens_in = sum(r["input_tokens"] for r in raw_results)
    raw_tokens_out = sum(r["output_tokens"] for r in raw_results)
    raw_avg_time = sum(r["time"] for r in raw_results) / N

    print(f"\nRaw baseline done: {raw_elapsed:.0f}s wall, {raw_avg_time:.1f}s/q avg")
    print(f"Tokens: {raw_tokens_in:,}in / {raw_tokens_out:,}out")

    # ── Score all answers ──
    print("\n=== Scoring Answers ===")
    raw_scores = []
    reg_scores = []
    judge_calls = 0

    for i, item in enumerate(items):
        expected = item.target
        raw_answer = raw_results[i]["answer"]
        reg_answer = regulus_results[i]["answer"]
        q_snippet = item.problem[:300]

        # Score raw
        raw_quick = quick_match(raw_answer, expected)
        if raw_quick is not None:
            raw_scores.append({"correct": raw_quick, "reason": "heuristic", "raw_judge": ""})
        else:
            judge_calls += 1
            raw_scores.append(await llm_judge(raw_answer, expected, q_snippet, openai_client))

        # Score regulus
        reg_quick = quick_match(reg_answer, expected)
        if reg_quick is not None:
            reg_scores.append({"correct": reg_quick, "reason": "heuristic", "raw_judge": ""})
        else:
            judge_calls += 1
            reg_scores.append(await llm_judge(reg_answer, expected, q_snippet, openai_client))

        r_raw = "OK" if raw_scores[-1]["correct"] else "XX"
        r_reg = "OK" if reg_scores[-1]["correct"] else "XX"
        print(f"  Q{i+1}: expected={expected!r:25s} raw={r_raw} reg={r_reg}")

    print(f"\nJudge calls: {judge_calls} (rest matched heuristically)")

    # ── Compute stats ──
    raw_correct = sum(1 for s in raw_scores if s["correct"])
    reg_correct = sum(1 for s in reg_scores if s["correct"])

    regulus_avg_time = sum(r["time"] for r in regulus_results) / N
    reg_tokens_in = sum(r["input_tokens"] for r in regulus_results)
    reg_tokens_out = sum(r["output_tokens"] for r in regulus_results)

    # ── Classify per question ──
    categories = {"regulus_wins": [], "both_correct": [], "raw_wins": [], "both_wrong": []}
    for i in range(N):
        rc = raw_scores[i]["correct"]
        gc = reg_scores[i]["correct"]
        if gc and not rc:
            categories["regulus_wins"].append(i + 1)
        elif rc and gc:
            categories["both_correct"].append(i + 1)
        elif rc and not gc:
            categories["raw_wins"].append(i + 1)
        else:
            categories["both_wrong"].append(i + 1)

    # ── Print results ──
    print()
    print("=" * 70)
    print("BBEH ACCURACY: Raw Claude vs Regulus v2+ToS (25 questions)")
    print("=" * 70)
    print()
    print(f"{'Metric':<22} {'Raw Claude':>12} {'Regulus v2+ToS':>16}")
    print("-" * 52)
    print(f"{'Correct answers':<22} {raw_correct:>8}/25   {reg_correct:>12}/25")
    print(f"{'Accuracy':<22} {100*raw_correct/N:>9.0f}%   {100*reg_correct/N:>13.0f}%")
    print(f"{'Avg time':<22} {raw_avg_time:>9.1f}s   {regulus_avg_time:>13.1f}s")
    print(f"{'Tokens in':<22} {raw_tokens_in:>9,}   {reg_tokens_in:>13,}")
    print(f"{'Tokens out':<22} {raw_tokens_out:>9,}   {reg_tokens_out:>13,}")
    print()

    print("CLASSIFICATION:")
    print(f"  Regulus wins (correct, raw wrong): {len(categories['regulus_wins'])} — {categories['regulus_wins']}")
    print(f"  Both correct:                      {len(categories['both_correct'])} — {categories['both_correct']}")
    print(f"  Raw wins (correct, Regulus wrong):  {len(categories['raw_wins'])} — {categories['raw_wins']}")
    print(f"  Both wrong:                         {len(categories['both_wrong'])} — {categories['both_wrong']}")
    net = len(categories["regulus_wins"]) - len(categories["raw_wins"])
    print(f"\n  Net improvement: {'+' if net >= 0 else ''}{net} questions")
    print()

    # Per-question table
    print("PER-QUESTION BREAKDOWN:")
    print(f"{'Q':>3} {'Expected':>25} {'Raw':>5} {'Reg':>5} {'Category':<15} {'Judge reason'}")
    print("-" * 90)
    for i in range(N):
        exp = items[i].target
        r_raw = "OK" if raw_scores[i]["correct"] else "FAIL"
        r_reg = "OK" if reg_scores[i]["correct"] else "FAIL"

        if i + 1 in categories["regulus_wins"]:
            cat = "REG WINS"
        elif i + 1 in categories["raw_wins"]:
            cat = "RAW WINS"
        elif i + 1 in categories["both_wrong"]:
            cat = "BOTH WRONG"
        else:
            cat = "both ok"

        reason = ""
        if not raw_scores[i]["correct"] or not reg_scores[i]["correct"]:
            # Show reason for failures
            if not raw_scores[i]["correct"]:
                reason = f"raw: {raw_scores[i]['reason'][:40]}"
            if not reg_scores[i]["correct"]:
                reason += f" reg: {reg_scores[i]['reason'][:40]}"

        print(f"{i+1:>3} {exp:>25} {r_raw:>5} {r_reg:>5} {cat:<15} {reason}")

    # ── Save full results ──
    out_path = Path(__file__).parent.parent / "data" / "bbeh_accuracy_results.json"
    save_data = {
        "config": {
            "n": N, "seed": 42, "model": MODEL, "judge": JUDGE_MODEL,
        },
        "summary": {
            "raw_correct": raw_correct, "reg_correct": reg_correct,
            "raw_accuracy": raw_correct / N, "reg_accuracy": reg_correct / N,
            "raw_avg_time": raw_avg_time, "reg_avg_time": regulus_avg_time,
            "raw_tokens_in": raw_tokens_in, "raw_tokens_out": raw_tokens_out,
            "reg_tokens_in": reg_tokens_in, "reg_tokens_out": reg_tokens_out,
            "net_improvement": net,
        },
        "categories": categories,
        "questions": [],
    }
    for i in range(N):
        save_data["questions"].append({
            "idx": i,
            "expected": items[i].target,
            "raw_answer": raw_results[i]["answer"][:500],
            "raw_correct": raw_scores[i]["correct"],
            "raw_reason": raw_scores[i]["reason"],
            "raw_time": raw_results[i]["time"],
            "reg_answer": regulus_results[i]["answer"][:500],
            "reg_correct": reg_scores[i]["correct"],
            "reg_reason": reg_scores[i]["reason"],
            "reg_time": regulus_results[i]["time"],
            "reg_rounds": regulus_results[i]["rounds"],
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
