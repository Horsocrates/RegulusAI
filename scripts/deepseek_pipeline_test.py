"""Run 1 BBEH question through the full DeepSeek v2 pipeline with all intermediate outputs."""

import asyncio
import os
import sys
import time
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

from regulus.data.bbeh import load_dataset
from regulus.reasoning.factory import get_provider
from regulus.audit.orchestrator import AuditOrchestrator
from regulus.audit.types import AuditConfig
from regulus.llm.openai import OpenAIClient


async def main():
    USE_TOS = "--tos" in sys.argv
    tos_label = " + ToS prompt" if USE_TOS else " (raw, no ToS)"

    items = load_dataset(n=1, seed=42)
    q = items[0]

    print("=" * 70)
    print(f"DEEPSEEK V3.2 THINKING -> REGULUS v2 PIPELINE{tos_label}")
    print("=" * 70)
    print(f"\nQuestion ({len(q.problem)} chars): {q.problem[:200]}...")
    print(f"Expected answer: {q.target}")
    print()

    # Create reasoning provider
    reasoning_provider = get_provider(
        "deepseek",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        use_tos_prompt=USE_TOS,
    )

    # Create audit LLM
    audit_llm = OpenAIClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model="gpt-4o-mini",
    )

    config = AuditConfig(min_domains=4, weight_threshold=60, max_corrections=2)

    # SSE callbacks for live progress
    def on_domain_start(domain, name):
        print(f"  [{domain}] Starting: {name}")

    def on_domain_complete(domain, result):
        if "weight" in result:
            gate = "PASS" if result.get("gate", 0) else "FAIL"
            print(f"  [{domain}] Done: weight={result['weight']} gate={gate}")
        else:
            t = result.get("time_ms", 0) / 1000
            print(f"  [{domain}] Done: {result.get('model', '')} ({t:.1f}s)")

    def on_correction(domain, attempt, violation, fix):
        print(f"  [CORRECTION {attempt}] {violation}: {fix}")

    orch = AuditOrchestrator(
        reasoning_provider=reasoning_provider,
        audit_llm=audit_llm,
        config=config,
        on_domain_start=on_domain_start,
        on_domain_complete=on_domain_complete,
        on_correction=on_correction,
    )

    print("Starting pipeline...")
    print("-" * 70)

    total_start = time.time()
    result = await orch.process_query(q.problem)
    total_elapsed = time.time() - total_start

    # === DEEPSEEK REASONING ===
    print()
    print("=" * 70)
    print("DEEPSEEK REASONING")
    print("=" * 70)
    print(f"  Model:            {result.reasoning_model}")
    print(f"  Trace format:     {result.trace_format}")
    print(f"  Thinking length:  {len(result.thinking):,} chars")
    print(f"  Answer length:    {len(result.answer):,} chars")

    # === THINKING TRACE ===
    print()
    print("=" * 70)
    print("THINKING TRACE (first 600 chars)")
    print("=" * 70)
    print(result.thinking[:600])
    print("...")
    print()
    print("=" * 70)
    print("THINKING TRACE (last 600 chars)")
    print("=" * 70)
    print(result.thinking[-600:])

    # === ANSWER ===
    print()
    print("=" * 70)
    print("ANSWER")
    print("=" * 70)
    print(result.answer)

    # === CORRECTNESS ===
    print()
    print("=" * 70)
    print("CORRECTNESS CHECK")
    print("=" * 70)
    expected = q.target.strip().lower()
    answer_text = result.answer.strip().lower()
    correct = expected in answer_text
    # Also try numeric comparison
    if not correct:
        try:
            if abs(float(expected) - float(answer_text.rstrip("."))) < 0.01:
                correct = True
        except (ValueError, OverflowError):
            pass
    print(f"  Expected: {q.target}")
    print(f"  Got:      {result.answer[:200]}")
    print(f"  Correct:  {'YES' if correct else 'NO (heuristic — may need LLM judge)'}")

    # === AUDIT RESULT ===
    print()
    print("=" * 70)
    print("AUDIT RESULT")
    print("=" * 70)
    final = result.final_audit
    if final:
        print(f"  Parse quality:    {final.parse_quality:.2f}")
        print(f"  Total weight:     {final.total_weight}/{final.max_possible_weight}")
        print(f"  Domains present:  {', '.join(final.domains_present)}")
        print(f"  Domains missing:  {', '.join(final.domains_missing) or 'none'}")
        print(f"  Failed gates:     {', '.join(final.failed_gates) or 'none'}")
        print(f"  All gates passed: {final.all_gates_passed}")
        print()

        # Per-domain detail
        print(f"  {'Domain':<6} {'Present':>7} {'Wt':>4} {'Gate':>5}  {'E':>2} {'R':>2} {'Ru':>3} {'S':>2} {'Dep':>4} {'L13':>4} {'L5':>3}  Issues")
        print("  " + "-" * 80)
        for d in final.domains:
            gate = "PASS" if d.gate_passed else "FAIL"
            p = "yes" if d.present else "no"
            e = "T" if d.e_exists else "F"
            r = "T" if d.r_exists else "F"
            ru = "T" if d.rule_exists else "F"
            s = "T" if d.s_exists else "F"
            dep = "T" if d.deps_declared else "F"
            l13 = "T" if d.l1_l3_ok else "F"
            l5 = "T" if d.l5_ok else "F"
            issues = "; ".join(d.issues[:2]) if d.issues else ""
            print(f"  {d.domain:<6} {p:>7} {d.weight:>4} {gate:>5}  {e:>2} {r:>2} {ru:>3} {s:>2} {dep:>4} {l13:>4} {l5:>3}  {issues[:60]}")

        if final.overall_issues:
            print(f"\n  Overall issues: {'; '.join(final.overall_issues)}")
    else:
        print("  No audit result available!")

    # === CORRECTIONS ===
    print()
    print("=" * 70)
    print("CORRECTIONS")
    print("=" * 70)
    print(f"  Audit rounds:     {result.audit_rounds}")
    print(f"  Corrections:      {len(result.corrections)}")
    if result.corrections:
        for fb in result.corrections:
            print(f"\n  Round {fb.round_number}:")
            print(f"    Failed domains: {', '.join(fb.failed_domains)}")
            print(f"    Failed gates:   {', '.join(fb.failed_gates)}")
            print(f"    Issues:         {'; '.join(fb.issues[:3])}")

    # Show all rounds if multiple
    if len(result.all_audits) > 1:
        print(f"\n  Per-round weights:")
        for i, audit in enumerate(result.all_audits):
            passing = config.is_passing(audit)
            print(f"    Round {i+1}: weight={audit.total_weight} domains={len(audit.domains_present)} "
                  f"failed_gates={audit.failed_gates} passing={passing}")

    # === PIPELINE VALID? ===
    print()
    print("=" * 70)
    print("PIPELINE RESULT")
    print("=" * 70)
    print(f"  Valid (structural): {result.valid}")
    print(f"  Correct (answer):   {'YES' if correct else 'NO (heuristic)'}")
    print(f"  Total time:         {total_elapsed:.1f}s")
    print(f"  Input tokens:       {result.input_tokens:,}")
    print(f"  Output tokens:      {result.output_tokens:,}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
