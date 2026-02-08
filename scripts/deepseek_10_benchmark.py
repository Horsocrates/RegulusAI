"""DeepSeek V3.2 Thinking — 10 Question Benchmark.

Runs 10 strategically selected BBEH questions through:
  Config 1: Raw DeepSeek (no audit, no ToS)
  Config 2: DeepSeek + Regulus audit pipeline (no ToS)

Compares with existing Claude results for the same questions.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

from regulus.data.bbeh import load_dataset
from regulus.reasoning.factory import get_provider
from regulus.audit.orchestrator import AuditOrchestrator
from regulus.audit.types import AuditConfig
from regulus.llm.openai import OpenAIClient

# ── Strategic selection: 10 questions from the 25-question set (seed=42) ──
# idx is 0-based position in load_dataset(n=25, seed=42)
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


# ── Answer scoring ──

def quick_match(predicted: str, expected: str) -> bool | None:
    """Fast heuristic check. Returns True/False if confident, None if unsure."""
    exp = expected.strip().lower()
    candidates = [predicted]

    for pattern in [
        r'(?i)(?:the\s+)?(?:final\s+)?answer\s*(?:is)?[:\s]+(.+?)(?:\.|$)',
        r'(?i)\*\*(?:final\s+)?answer[:\s]*\*\*[:\s]*(.+?)(?:\n|$)',
        r'(?i)(?:therefore|thus|so|hence)[,:\s]+(?:the answer is\s+)?(.+?)(?:\.|$)',
    ]:
        for m in re.finditer(pattern, predicted):
            candidates.append(m.group(1).strip())

    lines = [l.strip() for l in predicted.strip().split("\n") if l.strip()]
    if lines:
        candidates.append(lines[-1])

    for cand in candidates:
        c = cand.strip().lower().rstrip(".")
        if c == exp:
            return True
        if exp in c and len(exp) > 1:
            return True
        try:
            if abs(float(c) - float(exp)) < 0.001:
                return True
        except (ValueError, OverflowError):
            pass

    return None


async def llm_judge(predicted: str, expected: str, question_snippet: str, judge_client) -> dict:
    """Use gpt-4o-mini to judge if predicted matches expected answer."""
    prompt = f"""You are an answer-matching judge. Determine if the model's answer is correct.

Question (first 300 chars): {question_snippet[:300]}

Expected answer: {expected}

Model's full response (may be long -- look for the final answer):
{predicted[:3000]}

Rules:
- The model's answer is CORRECT if it contains or implies the expected answer.
- Ignore extra explanation, domain tags (<D1>...</D6>), formatting differences.
- For numbers: 5.84 and 5.84000 are the same. -557 and -557.0 are the same.
- For multiple choice: (A) and A are the same.
- For yes/no: "Yes" and "yes" are the same.
- For lists: "0,0,1" and "0, 0, 1" are the same. Order matters.
- If the model gives a clearly wrong answer or says "cannot determine", mark INCORRECT.

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

    return {"correct": correct, "reason": reason}


async def score_answer(predicted: str, expected: str, question: str, judge_client) -> dict:
    """Score an answer: try heuristic first, fallback to LLM judge."""
    quick = quick_match(predicted, expected)
    if quick is not None:
        return {"correct": quick, "reason": "heuristic", "method": "heuristic"}
    result = await llm_judge(predicted, expected, question, judge_client)
    result["method"] = "llm_judge"
    return result


# ── Main ──

async def main():
    from openai import AsyncOpenAI

    judge_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Load all 25 BBEH questions (same seed)
    all_items = load_dataset(n=25, seed=42)

    # Load existing Claude results
    acc_path = Path(__file__).parent.parent / "data" / "bbeh_accuracy_results.json"
    with open(acc_path, "r", encoding="utf-8") as f:
        claude_data = json.load(f)

    # Create providers
    deepseek_provider = get_provider(
        "deepseek", api_key=os.environ["DEEPSEEK_API_KEY"]
    )

    audit_llm = OpenAIClient(
        api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini"
    )
    config = AuditConfig(min_domains=4, weight_threshold=60, max_corrections=2)

    print("=" * 80)
    print("DeepSeek V3.2 Thinking -- 10 Question Benchmark")
    print("=" * 80)
    print(f"Questions: {[s['q_num'] for s in SELECTED]}")
    print(f"Categories: {[s['category'] for s in SELECTED]}")
    print()

    # ── Config 1: Raw DeepSeek ──
    print("=" * 80)
    print("CONFIG 1: Raw DeepSeek (no audit, no ToS)")
    print("=" * 80)

    raw_results = []
    for i, sel in enumerate(SELECTED):
        item = all_items[sel["idx"]]
        q_num = sel["q_num"]

        print(f"\n  [{i+1}/10] Q{q_num} ({sel['type']}) expected={item.target!r}")
        start = time.time()
        try:
            result = await deepseek_provider.reason(item.problem)
            elapsed = time.time() - start

            raw_results.append({
                "q_num": q_num,
                "idx": sel["idx"],
                "category": sel["category"],
                "type": sel["type"],
                "expected": item.target,
                "answer": result.answer,
                "thinking_len": len(result.thinking),
                "time": round(elapsed, 1),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "reasoning_tokens": result.reasoning_tokens,
            })
            print(f"    Done: {elapsed:.0f}s, answer={result.answer[:100]!r}")
        except Exception as e:
            elapsed = time.time() - start
            print(f"    ERROR: {e}")
            raw_results.append({
                "q_num": q_num, "idx": sel["idx"],
                "category": sel["category"], "type": sel["type"],
                "expected": item.target, "answer": f"ERROR: {e}",
                "thinking_len": 0, "time": round(elapsed, 1),
                "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
            })

    # Save raw checkpoint
    ckpt_path = Path(__file__).parent.parent / "data" / "deepseek_10_raw.json"
    with open(ckpt_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved raw checkpoint: {ckpt_path}")

    # ── Config 2: DeepSeek + Regulus audit ──
    print()
    print("=" * 80)
    print("CONFIG 2: DeepSeek + Regulus audit pipeline (no ToS)")
    print("=" * 80)

    audit_results = []
    for i, sel in enumerate(SELECTED):
        item = all_items[sel["idx"]]
        q_num = sel["q_num"]

        print(f"\n  [{i+1}/10] Q{q_num} ({sel['type']}) expected={item.target!r}")

        orch = AuditOrchestrator(
            reasoning_provider=deepseek_provider,
            audit_llm=audit_llm,
            config=config,
        )

        start = time.time()
        try:
            result = await orch.process_query(item.problem)
            elapsed = time.time() - start

            final = result.final_audit
            audit_results.append({
                "q_num": q_num,
                "idx": sel["idx"],
                "category": sel["category"],
                "type": sel["type"],
                "expected": item.target,
                "answer": result.answer,
                "valid": result.valid,
                "rounds": result.audit_rounds,
                "weight": final.total_weight if final else 0,
                "failed_gates": final.failed_gates if final else [],
                "domains_present": final.domains_present if final else [],
                "domains_missing": final.domains_missing if final else [],
                "parse_quality": final.parse_quality if final else 0,
                "time": round(elapsed, 1),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "domain_details": [],
            })

            if final:
                for d in final.domains:
                    audit_results[-1]["domain_details"].append({
                        "domain": d.domain,
                        "present": d.present,
                        "weight": d.weight,
                        "gate_passed": d.gate_passed,
                        "e": d.e_exists, "r": d.r_exists,
                        "ru": d.rule_exists, "s": d.s_exists,
                        "dep": d.deps_declared,
                    })

            status = "PASS" if result.valid else "FAIL"
            w = final.total_weight if final else 0
            print(f"    Done: {elapsed:.0f}s, {status} w={w} r={result.audit_rounds} "
                  f"answer={result.answer[:80]!r}")
        except Exception as e:
            elapsed = time.time() - start
            print(f"    ERROR: {e}")
            audit_results.append({
                "q_num": q_num, "idx": sel["idx"],
                "category": sel["category"], "type": sel["type"],
                "expected": item.target, "answer": f"ERROR: {e}",
                "valid": False, "rounds": 0, "weight": 0,
                "failed_gates": [], "domains_present": [], "domains_missing": [],
                "parse_quality": 0, "time": round(elapsed, 1),
                "input_tokens": 0, "output_tokens": 0, "domain_details": [],
            })

    # Save audit checkpoint
    ckpt2_path = Path(__file__).parent.parent / "data" / "deepseek_10_audit.json"
    with open(ckpt2_path, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved audit checkpoint: {ckpt2_path}")

    # ── Score all answers ──
    print()
    print("=" * 80)
    print("SCORING ANSWERS")
    print("=" * 80)

    raw_scores = []
    audit_scores = []
    for i, sel in enumerate(SELECTED):
        item = all_items[sel["idx"]]
        q_num = sel["q_num"]

        rs = await score_answer(raw_results[i]["answer"], item.target, item.problem, judge_client)
        raw_scores.append(rs)

        aus = await score_answer(audit_results[i]["answer"], item.target, item.problem, judge_client)
        audit_scores.append(aus)

        r_raw = "OK" if rs["correct"] else "XX"
        r_aud = "OK" if aus["correct"] else "XX"
        print(f"  Q{q_num}: expected={item.target!r:20s} raw={r_raw} audit={r_aud}")

    # ── Pull Claude data for same 10 questions ──
    claude_raw_scores = []
    claude_reg_scores = []
    for sel in SELECTED:
        cq = claude_data["questions"][sel["idx"]]
        claude_raw_scores.append({"correct": cq["raw_correct"], "time": cq["raw_time"]})
        claude_reg_scores.append({
            "correct": cq["reg_correct"], "time": cq["reg_time"],
            "rounds": cq["reg_rounds"],
        })

    # ── Summary table ──
    print()
    print("=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)

    n = len(SELECTED)
    ds_raw_correct = sum(1 for s in raw_scores if s["correct"])
    ds_aud_correct = sum(1 for s in audit_scores if s["correct"])
    cl_raw_correct = sum(1 for s in claude_raw_scores if s["correct"])
    cl_reg_correct = sum(1 for s in claude_reg_scores if s["correct"])

    ds_raw_time = sum(r["time"] for r in raw_results) / n
    ds_aud_time = sum(r["time"] for r in audit_results) / n
    cl_raw_time = sum(s["time"] for s in claude_raw_scores) / n
    cl_reg_time = sum(s["time"] for s in claude_reg_scores) / n

    ds_aud_weight = sum(r["weight"] for r in audit_results) / n
    ds_aud_rounds = sum(r["rounds"] for r in audit_results) / n

    print(f"{'Metric':<22} {'Raw Claude':>12} {'Claude+ToS':>12} {'Raw DeepSeek':>14} {'DS+Audit':>12}")
    print("-" * 74)
    print(f"{'Correct':<22} {cl_raw_correct:>8}/{n}   {cl_reg_correct:>8}/{n}   {ds_raw_correct:>10}/{n}   {ds_aud_correct:>8}/{n}")
    print(f"{'Accuracy':<22} {100*cl_raw_correct/n:>9.0f}%   {100*cl_reg_correct/n:>9.0f}%   {100*ds_raw_correct/n:>11.0f}%   {100*ds_aud_correct/n:>9.0f}%")
    print(f"{'Avg time':<22} {cl_raw_time:>9.1f}s   {cl_reg_time:>9.1f}s   {ds_raw_time:>11.1f}s   {ds_aud_time:>9.1f}s")
    print(f"{'Avg weight':<22} {'N/A':>10}   {'N/A':>10}   {'N/A':>12}   {ds_aud_weight:>9.0f}")
    print(f"{'Avg rounds':<22} {'N/A':>10}   {'N/A':>10}   {'N/A':>12}   {ds_aud_rounds:>9.1f}")
    print()

    # ── Per-category analysis ──
    print("=" * 80)
    print("PER-CATEGORY ANALYSIS")
    print("=" * 80)

    categories = {}
    for i, sel in enumerate(SELECTED):
        cat = sel["category"]
        if cat not in categories:
            categories[cat] = {"ds_raw": [], "ds_aud": [], "cl_raw": [], "cl_reg": []}
        categories[cat]["ds_raw"].append(raw_scores[i]["correct"])
        categories[cat]["ds_aud"].append(audit_scores[i]["correct"])
        categories[cat]["cl_raw"].append(claude_raw_scores[i]["correct"])
        categories[cat]["cl_reg"].append(claude_reg_scores[i]["correct"])

    print(f"{'Category':<20} {'Raw DS':>8} {'DS+Audit':>10} {'Raw Claude':>12} {'Claude+ToS':>12}")
    print("-" * 64)
    for cat, data in categories.items():
        n_cat = len(data["ds_raw"])
        ds_r = sum(data["ds_raw"])
        ds_a = sum(data["ds_aud"])
        cl_r = sum(data["cl_raw"])
        cl_g = sum(data["cl_reg"])
        print(f"{cat:<20} {ds_r:>5}/{n_cat}   {ds_a:>7}/{n_cat}   {cl_r:>9}/{n_cat}   {cl_g:>9}/{n_cat}")
    print()

    # ── Per-question table ──
    print("=" * 80)
    print("PER-QUESTION RESULTS")
    print("=" * 80)

    print(f"{'Q':>3} {'Type':<18} {'Cat':<16} {'Expected':>14} {'RawDS':>6} {'DS+Aud':>7} {'RawCl':>6} {'Cl+ToS':>7} {'DS time':>8} {'Wt':>4} {'Rnd':>4}")
    print("-" * 110)
    for i, sel in enumerate(SELECTED):
        q = sel["q_num"]
        tp = sel["type"][:17]
        cat = sel["category"][:15]
        expected = raw_results[i]["expected"]
        exp = expected if len(expected) <= 14 else expected[:11] + "..."

        ds_r = "OK" if raw_scores[i]["correct"] else "FAIL"
        ds_a = "OK" if audit_scores[i]["correct"] else "FAIL"
        cl_r = "OK" if claude_raw_scores[i]["correct"] else "FAIL"
        cl_g = "OK" if claude_reg_scores[i]["correct"] else "FAIL"

        ds_t = f"{raw_results[i]['time']:.0f}s"
        wt = audit_results[i]["weight"]
        rnd = audit_results[i]["rounds"]

        print(f"{q:>3} {tp:<18} {cat:<16} {exp:>14} {ds_r:>6} {ds_a:>7} {cl_r:>6} {cl_g:>7} {ds_t:>8} {wt:>4} {rnd:>4}")

    # ── Interesting cases ──
    print()
    print("=" * 80)
    print("INTERESTING CASES")
    print("=" * 80)

    # DS audit helped
    audit_helped = [(i, s) for i, s in enumerate(SELECTED)
                    if audit_scores[i]["correct"] and not raw_scores[i]["correct"]]
    print(f"\n  DeepSeek+Audit correct, Raw DeepSeek wrong: {len(audit_helped)}")
    for i, s in audit_helped:
        print(f"    Q{s['q_num']} ({s['type']}): expected={all_items[s['idx']].target!r}")

    # DS audit hurt
    audit_hurt = [(i, s) for i, s in enumerate(SELECTED)
                  if raw_scores[i]["correct"] and not audit_scores[i]["correct"]]
    print(f"\n  Raw DeepSeek correct, DS+Audit wrong: {len(audit_hurt)}")
    for i, s in audit_hurt:
        print(f"    Q{s['q_num']} ({s['type']}): expected={all_items[s['idx']].target!r}")

    # DS solved what Claude couldn't
    both_wrong_solved = [(i, s) for i, s in enumerate(SELECTED)
                         if s["category"] == "both_wrong" and raw_scores[i]["correct"]]
    print(f"\n  'Both wrong' that Raw DeepSeek solves: {len(both_wrong_solved)}")
    for i, s in both_wrong_solved:
        print(f"    Q{s['q_num']} ({s['type']}): expected={all_items[s['idx']].target!r}")

    # Correction changed answer
    corrected = [(i, s) for i, s in enumerate(SELECTED)
                 if audit_results[i]["rounds"] > 1]
    print(f"\n  Questions where audit triggered correction: {len(corrected)}")
    for i, s in corrected:
        r = audit_results[i]
        print(f"    Q{s['q_num']}: {r['rounds']} rounds, weight={r['weight']}, "
              f"correct={audit_scores[i]['correct']}")

    # ── Audit detail for failed gates ──
    print()
    print("=" * 80)
    print("AUDIT GATE DETAILS")
    print("=" * 80)

    for i, sel in enumerate(SELECTED):
        r = audit_results[i]
        if r["failed_gates"] or not r["valid"]:
            print(f"\n  Q{sel['q_num']} ({sel['type']}): valid={r['valid']} weight={r['weight']}")
            print(f"    Failed gates: {r['failed_gates']}")
            print(f"    Missing domains: {r['domains_missing']}")

        if r.get("domain_details"):
            has_fail = any(not d["gate_passed"] for d in r["domain_details"] if d["present"])
            if has_fail:
                for d in r["domain_details"]:
                    if d["present"] and not d["gate_passed"]:
                        print(f"    {d['domain']}: e={d['e']} r={d['r']} ru={d['ru']} "
                              f"s={d['s']} dep={d['dep']}")

    # ── Save full results ──
    out_path = Path(__file__).parent.parent / "data" / "deepseek_10_results.json"
    save_data = {
        "config": {
            "n": n, "seed": 42, "judge": JUDGE_MODEL,
            "selected": SELECTED,
        },
        "summary": {
            "ds_raw_correct": ds_raw_correct,
            "ds_aud_correct": ds_aud_correct,
            "cl_raw_correct": cl_raw_correct,
            "cl_reg_correct": cl_reg_correct,
            "ds_raw_avg_time": ds_raw_time,
            "ds_aud_avg_time": ds_aud_time,
        },
        "questions": [],
    }
    for i, sel in enumerate(SELECTED):
        save_data["questions"].append({
            "q_num": sel["q_num"],
            "idx": sel["idx"],
            "category": sel["category"],
            "type": sel["type"],
            "expected": all_items[sel["idx"]].target,
            "ds_raw_answer": raw_results[i]["answer"][:500],
            "ds_raw_correct": raw_scores[i]["correct"],
            "ds_raw_time": raw_results[i]["time"],
            "ds_raw_reasoning_tokens": raw_results[i]["reasoning_tokens"],
            "ds_aud_answer": audit_results[i]["answer"][:500],
            "ds_aud_correct": audit_scores[i]["correct"],
            "ds_aud_time": audit_results[i]["time"],
            "ds_aud_weight": audit_results[i]["weight"],
            "ds_aud_rounds": audit_results[i]["rounds"],
            "ds_aud_valid": audit_results[i]["valid"],
            "cl_raw_correct": claude_raw_scores[i]["correct"],
            "cl_reg_correct": claude_reg_scores[i]["correct"],
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved full results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
