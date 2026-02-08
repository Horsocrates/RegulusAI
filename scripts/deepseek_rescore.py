"""Re-score DeepSeek 10-question benchmark from saved checkpoints."""

import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from regulus.data.bbeh import load_dataset

SELECTED = [
    {"idx": 0,  "q_num": 1,  "category": "both_wrong",     "type": "table_parsing"},
    {"idx": 8,  "q_num": 9,  "category": "both_wrong",     "type": "truth_teller"},
    {"idx": 16, "q_num": 17, "category": "regulus_helped",  "type": "custom_operations"},
    {"idx": 18, "q_num": 19, "category": "regulus_helped",  "type": "object_tracking"},
    {"idx": 15, "q_num": 16, "category": "regulus_hurt",    "type": "logic_puzzle"},
    {"idx": 23, "q_num": 24, "category": "regulus_hurt",    "type": "expression_eval"},
    {"idx": 3,  "q_num": 4,  "category": "math_table",     "type": "table_parsing"},
    {"idx": 12, "q_num": 13, "category": "math_table",     "type": "date_time"},
    {"idx": 1,  "q_num": 2,  "category": "language",       "type": "sarcasm_detection"},
    {"idx": 21, "q_num": 22, "category": "language",       "type": "linguistics"},
]

JUDGE_MODEL = "gpt-4o-mini"


async def llm_judge(predicted, expected, question_snippet, judge_client):
    prompt = f"""You are an answer-matching judge. Determine if the model's answer is correct.

Question (first 300 chars): {question_snippet[:300]}

Expected answer: {expected}

Model's full response (look for the FINAL/CHOSEN answer, not mentions of wrong options):
{predicted[:3000]}

Rules:
- The model's answer is CORRECT if its FINAL/CHOSEN answer matches the expected answer.
- If the model says "the answer is X" but X != expected, mark INCORRECT even if expected appears elsewhere.
- For multiple choice: the model must SELECT the expected option as its answer, not just mention it.
- Ignore extra explanation, domain tags, formatting.
- For numbers: 5.84 and 5.84000 are the same. -25200.0 and -25200 are the same.
- For lists: "0,0,1" and "0, 0, 1" are the same. Order matters.
- "no, unknown, no" and "no, unknown, unknown" are NOT the same.
- For yes/no: "Yes" and "yes" are the same.

Reply with EXACTLY:
VERDICT: CORRECT or INCORRECT
REASON: <one sentence>"""

    response = await judge_client.chat.completions.create(
        model=JUDGE_MODEL, max_tokens=100, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    correct = "CORRECT" in text.split("\n")[0] and "INCORRECT" not in text.split("\n")[0]
    reason = ""
    for line in text.split("\n"):
        if line.startswith("REASON:"):
            reason = line[7:].strip()
    return {"correct": correct, "reason": reason}


async def main():
    items = load_dataset(n=25, seed=42)
    judge_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with open("data/deepseek_10_raw.json") as f:
        raw_results = json.load(f)
    with open("data/deepseek_10_audit.json") as f:
        audit_results = json.load(f)
    with open("data/bbeh_accuracy_results.json") as f:
        claude_data = json.load(f)

    print("RE-SCORING WITH IMPROVED JUDGE PROMPT")
    print("=" * 80)

    raw_scores = []
    audit_scores = []
    for i, sel in enumerate(SELECTED):
        item = items[sel["idx"]]
        expected = item.target

        rs = await llm_judge(raw_results[i]["answer"], expected, item.problem, judge_client)
        raw_scores.append(rs)

        aus = await llm_judge(audit_results[i]["answer"], expected, item.problem, judge_client)
        audit_scores.append(aus)

        r_raw = "OK" if rs["correct"] else "XX"
        r_aud = "OK" if aus["correct"] else "XX"
        print(f"  Q{sel['q_num']:>2}: exp={expected!r:22s} raw={r_raw} ({rs['reason'][:45]})")
        print(f"       {'':22s} aud={r_aud} ({aus['reason'][:45]})")

    # Pull Claude data
    claude_raw = [claude_data["questions"][s["idx"]] for s in SELECTED]

    n = 10
    ds_raw_c = sum(1 for s in raw_scores if s["correct"])
    ds_aud_c = sum(1 for s in audit_scores if s["correct"])
    cl_raw_c = sum(1 for q in claude_raw if q["raw_correct"])
    cl_reg_c = sum(1 for q in claude_raw if q["reg_correct"])

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY (10 strategically selected BBEH questions)")
    print("=" * 80)

    ds_raw_time = sum(r["time"] for r in raw_results) / n
    ds_aud_time = sum(r["time"] for r in audit_results) / n
    cl_raw_time = sum(claude_raw[i]["raw_time"] for i in range(n)) / n
    cl_reg_time = sum(claude_raw[i]["reg_time"] for i in range(n)) / n
    ds_aud_weight = sum(r["weight"] for r in audit_results) / n
    ds_aud_rounds = sum(r["rounds"] for r in audit_results) / n

    print(f"{'Metric':<22} {'Raw Claude':>12} {'Claude+ToS':>12} {'Raw DeepSeek':>14} {'DS+Audit':>12}")
    print("-" * 74)
    print(f"{'Correct':<22} {cl_raw_c:>8}/{n}   {cl_reg_c:>8}/{n}   {ds_raw_c:>10}/{n}   {ds_aud_c:>8}/{n}")
    print(f"{'Accuracy':<22} {100*cl_raw_c/n:>9.0f}%   {100*cl_reg_c/n:>9.0f}%   {100*ds_raw_c/n:>11.0f}%   {100*ds_aud_c/n:>9.0f}%")
    print(f"{'Avg time':<22} {cl_raw_time:>9.1f}s   {cl_reg_time:>9.1f}s   {ds_raw_time:>11.1f}s   {ds_aud_time:>9.1f}s")
    print(f"{'Avg weight':<22} {'N/A':>10}   {'N/A':>10}   {'N/A':>12}   {ds_aud_weight:>9.0f}")
    print(f"{'Avg rounds':<22} {'N/A':>10}   {'N/A':>10}   {'N/A':>12}   {ds_aud_rounds:>9.1f}")

    # Per-question table
    print()
    print("=" * 80)
    print("PER-QUESTION RESULTS")
    print("=" * 80)
    print(f"{'Q':>3} {'Type':<18} {'Cat':<16} {'Expected':>14} {'RawDS':>6} {'DS+Aud':>7} {'RawCl':>6} {'Cl+ToS':>7} {'DS_t':>6} {'Wt':>4} {'Rnd':>4}")
    print("-" * 108)
    for i, sel in enumerate(SELECTED):
        q = sel["q_num"]
        tp = sel["type"][:17]
        cat = sel["category"][:15]
        expected = raw_results[i]["expected"]
        exp = expected if len(expected) <= 14 else expected[:11] + "..."

        ds_r = "OK" if raw_scores[i]["correct"] else "FAIL"
        ds_a = "OK" if audit_scores[i]["correct"] else "FAIL"
        cl_r = "OK" if claude_raw[i]["raw_correct"] else "FAIL"
        cl_g = "OK" if claude_raw[i]["reg_correct"] else "FAIL"

        ds_t = f"{raw_results[i]['time']:.0f}s"
        wt = audit_results[i]["weight"]
        rnd = audit_results[i]["rounds"]

        print(f"{q:>3} {tp:<18} {cat:<16} {exp:>14} {ds_r:>6} {ds_a:>7} {cl_r:>6} {cl_g:>7} {ds_t:>6} {wt:>4} {rnd:>4}")

    # Interesting cases
    print()
    print("=" * 80)
    print("INTERESTING CASES")
    print("=" * 80)

    audit_helped = [(i, s) for i, s in enumerate(SELECTED)
                    if audit_scores[i]["correct"] and not raw_scores[i]["correct"]]
    print(f"\n  Audit HELPED (DS+Audit correct, Raw DS wrong): {len(audit_helped)}")
    for i, s in audit_helped:
        print(f"    Q{s['q_num']} ({s['type']}): expected={items[s['idx']].target!r}")

    audit_hurt = [(i, s) for i, s in enumerate(SELECTED)
                  if raw_scores[i]["correct"] and not audit_scores[i]["correct"]]
    print(f"\n  Audit HURT (Raw DS correct, DS+Audit wrong): {len(audit_hurt)}")
    for i, s in audit_hurt:
        print(f"    Q{s['q_num']} ({s['type']}): expected={items[s['idx']].target!r}")

    both_wrong_solved = [(i, s) for i, s in enumerate(SELECTED)
                         if s["category"] == "both_wrong" and raw_scores[i]["correct"]]
    print(f"\n  Both-wrong that DeepSeek solves: {len(both_wrong_solved)}")
    for i, s in both_wrong_solved:
        print(f"    Q{s['q_num']} ({s['type']}): expected={items[s['idx']].target!r}")

    corrected = [(i, s) for i, s in enumerate(SELECTED)
                 if audit_results[i]["rounds"] > 1]
    print(f"\n  Corrections triggered: {len(corrected)}")
    for i, s in corrected:
        r = audit_results[i]
        raw_was = "OK" if raw_scores[i]["correct"] else "FAIL"
        aud_now = "OK" if audit_scores[i]["correct"] else "FAIL"
        print(f"    Q{s['q_num']}: {r['rounds']} rounds, w={r['weight']}, "
              f"raw={raw_was} -> audit={aud_now}")

    # Per-category
    print()
    print("=" * 80)
    print("PER-CATEGORY ANALYSIS")
    print("=" * 80)
    cats = {}
    for i, sel in enumerate(SELECTED):
        c = sel["category"]
        if c not in cats:
            cats[c] = {"ds_r": [], "ds_a": [], "cl_r": [], "cl_g": []}
        cats[c]["ds_r"].append(raw_scores[i]["correct"])
        cats[c]["ds_a"].append(audit_scores[i]["correct"])
        cats[c]["cl_r"].append(claude_raw[i]["raw_correct"])
        cats[c]["cl_g"].append(claude_raw[i]["reg_correct"])

    print(f"{'Category':<20} {'Raw DS':>8} {'DS+Audit':>10} {'Raw Claude':>12} {'Claude+ToS':>12}")
    print("-" * 64)
    for c, d in cats.items():
        nc = len(d["ds_r"])
        print(f"{c:<20} {sum(d['ds_r']):>5}/{nc}   {sum(d['ds_a']):>7}/{nc}   "
              f"{sum(d['cl_r']):>9}/{nc}   {sum(d['cl_g']):>9}/{nc}")


if __name__ == "__main__":
    asyncio.run(main())
