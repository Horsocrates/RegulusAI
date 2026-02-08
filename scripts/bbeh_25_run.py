"""Run 25 BBEH questions with full correction diagnostics."""

import asyncio
import os
import sys
import time
import json
from dotenv import load_dotenv
load_dotenv()

from regulus.data.bbeh import load_dataset
from regulus.reasoning.factory import get_provider
from regulus.audit.orchestrator import AuditOrchestrator
from regulus.audit.types import AuditConfig
from regulus.llm.openai import OpenAIClient

N = 25
CONCURRENCY = 3
USE_TOS = "--tos" in sys.argv


async def run_question(idx, item, reasoning_provider, config):
    """Run one question and capture per-round audit details."""
    audit_llm = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini")

    orch = AuditOrchestrator(
        reasoning_provider=reasoning_provider,
        audit_llm=audit_llm,
        config=config,
    )

    start = time.time()
    result = await orch.process_query(item.problem)
    elapsed = time.time() - start

    # Collect per-round audit details
    rounds_detail = []
    for r_idx, audit in enumerate(result.all_audits):
        round_info = {
            "round": r_idx + 1,
            "total_weight": audit.total_weight,
            "domains_present": audit.domains_present,
            "domains_missing": audit.domains_missing,
            "failed_gates": audit.failed_gates,
            "all_gates_passed": audit.all_gates_passed,
            "passing": config.is_passing(audit),
            "domains": [],
        }
        for d in audit.domains:
            if d.present:
                g = d.gate
                dinfo = {
                    "domain": d.domain,
                    "weight": d.weight,
                    "gate_passed": g.is_valid,
                    "err_complete": g.err_complete,
                    "deps_valid": g.deps_valid,
                    "levels_valid": g.levels_valid,
                    "order_valid": g.order_valid,
                    "e_exists": d.e_exists,
                    "r_exists": d.r_exists,
                    "rule_exists": d.rule_exists,
                    "s_exists": d.s_exists,
                    "deps_declared": d.deps_declared,
                    "issues": d.issues,
                }
                round_info["domains"].append(dinfo)
        rounds_detail.append(round_info)

    # Collect correction info
    corrections_detail = []
    for fb in result.corrections:
        corrections_detail.append({
            "round": fb.round_number,
            "failed_domains": fb.failed_domains,
            "failed_gates": fb.failed_gates,
            "issues": fb.issues[:5],
        })

    return {
        "idx": idx,
        "question": item.problem[:150],
        "expected": item.target,
        "answer": result.answer or "",
        "valid": result.valid,
        "rounds": result.audit_rounds,
        "time": round(elapsed, 1),
        "weight": result.final_audit.total_weight if result.final_audit else 0,
        "max_weight": result.final_audit.max_possible_weight if result.final_audit else 0,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "rounds_detail": rounds_detail,
        "corrections": corrections_detail,
    }


async def main():
    items = load_dataset(n=N, seed=42)
    print(f"Running {len(items)} BBEH questions, concurrency={CONCURRENCY}")
    print()

    reasoning_provider = get_provider(
        "claude-thinking", api_key=os.environ["ANTHROPIC_API_KEY"],
        use_tos_prompt=USE_TOS,
    )
    config = AuditConfig(min_domains=4, weight_threshold=60, max_corrections=2)
    tos_label = " + ToS prompt" if USE_TOS else ""
    print(f"Config: claude-thinking{tos_label}")

    sem = asyncio.Semaphore(CONCURRENCY)
    completed = 0

    async def run_with_sem(idx, item):
        nonlocal completed
        async with sem:
            r = await run_question(idx, item, reasoning_provider, config)
            completed += 1
            status = "PASS" if r["valid"] else "FAIL"
            print(
                f"[{completed}/{N}] Q{r['idx']+1}: {status} r={r['rounds']} "
                f"w={r['weight']} t={r['time']}s"
            )
            return r

    total_start = time.time()
    tasks = [run_with_sem(i, item) for i, item in enumerate(items)]
    all_results = await asyncio.gather(*tasks)
    total_elapsed = time.time() - total_start

    # Sort by index
    all_results.sort(key=lambda r: r["idx"])

    # Save full results to JSON
    suffix = "_tos" if USE_TOS else ""
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", f"bbeh_25_results{suffix}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved detailed results to {out_path}")

    # === SUMMARY STATISTICS ===
    print()
    print("=" * 70)
    valid_count = sum(1 for r in all_results if r["valid"])
    avg_time = sum(r["time"] for r in all_results) / N
    avg_weight = sum(r["weight"] for r in all_results) / N
    avg_rounds = sum(r["rounds"] for r in all_results) / N
    total_tokens_in = sum(r["input_tokens"] for r in all_results)
    total_tokens_out = sum(r["output_tokens"] for r in all_results)

    print(f"SUMMARY ({N} BBEH questions)")
    print(f"  Valid:       {valid_count}/{N} ({100*valid_count/N:.0f}%)")
    print(f"  Avg weight:  {avg_weight:.0f}")
    print(f"  Avg rounds:  {avg_rounds:.1f}")
    print(f"  Avg time:    {avg_time:.1f}s/q")
    print(f"  Wall time:   {total_elapsed:.0f}s")
    print(f"  Tokens:      {total_tokens_in:,}in / {total_tokens_out:,}out")
    print()

    # === CORRECTION ANALYSIS ===
    corrected = [r for r in all_results if r["rounds"] > 1]
    single_round = [r for r in all_results if r["rounds"] == 1]

    print("CORRECTION ANALYSIS")
    print(f"  Pass on round 1: {len(single_round)}/{N}")
    print(f"  Needed corrections: {len(corrected)}/{N}")
    print()

    # Analyze what failed in round 1 for corrected questions
    failure_signals = {}
    failure_domains = {}

    for r in corrected:
        if r["rounds_detail"]:
            rd1 = r["rounds_detail"][0]
            for d in rd1["domains"]:
                if not d["gate_passed"]:
                    dom = d["domain"]
                    failure_domains[dom] = failure_domains.get(dom, 0) + 1

                    if not d["err_complete"]:
                        if not d["e_exists"]:
                            failure_signals["e_exists=F"] = failure_signals.get("e_exists=F", 0) + 1
                        if not d["r_exists"]:
                            failure_signals["r_exists=F"] = failure_signals.get("r_exists=F", 0) + 1
                        if not d["rule_exists"]:
                            failure_signals["rule_exists=F"] = failure_signals.get("rule_exists=F", 0) + 1
                        if not d["s_exists"]:
                            failure_signals["s_exists=F"] = failure_signals.get("s_exists=F", 0) + 1
                    if not d["deps_valid"]:
                        failure_signals["deps_declared=F"] = failure_signals.get("deps_declared=F", 0) + 1
                    if not d["levels_valid"]:
                        failure_signals["l1_l3_ok=F"] = failure_signals.get("l1_l3_ok=F", 0) + 1
                    if not d["order_valid"]:
                        failure_signals["l5_ok=F"] = failure_signals.get("l5_ok=F", 0) + 1

            # Missing domains
            missing = rd1.get("domains_missing", [])
            for m in missing:
                failure_signals[f"{m}_missing"] = failure_signals.get(f"{m}_missing", 0) + 1

    print("  Round 1 failure signals (across corrected questions):")
    for sig, count in sorted(failure_signals.items(), key=lambda x: -x[1]):
        pct = 100 * count / len(corrected) if corrected else 0
        print(f"    {sig}: {count} ({pct:.0f}%)")
    print()

    print("  Round 1 failed gate domains:")
    for dom, count in sorted(failure_domains.items(), key=lambda x: -x[1]):
        print(f"    {dom}: {count}")
    print()

    # Correction effectiveness
    fixed = sum(1 for r in corrected if r["valid"])
    still_failed = sum(1 for r in corrected if not r["valid"])
    print("  Correction effectiveness:")
    print(f"    Fixed by correction: {fixed}/{len(corrected)}")
    print(f"    Still failed: {still_failed}/{len(corrected)}")
    print()

    # Per-question table
    print("PER-QUESTION RESULTS:")
    print(f"{'Q':>3} {'Valid':>5} {'Rnd':>3} {'Wt':>4} {'Time':>5} {'R1 Failures'}")
    print("-" * 70)
    for r in all_results:
        r1_fails = ""
        if r["rounds_detail"]:
            rd1 = r["rounds_detail"][0]
            parts = []
            fails = rd1.get("failed_gates", [])
            missing = rd1.get("domains_missing", [])
            if fails:
                parts.append("gate:" + ",".join(fails))
            if missing:
                parts.append("miss:" + ",".join(missing))
            if not rd1.get("passing", False) and not fails and not missing:
                parts.append(f"wt={rd1['total_weight']}<thr")
            r1_fails = " ".join(parts)
        status = "PASS" if r["valid"] else "FAIL"
        print(f"{r['idx']+1:>3} {status:>5} {r['rounds']:>3} {r['weight']:>4} {r['time']:>4.0f}s {r1_fails}")


if __name__ == "__main__":
    asyncio.run(main())
