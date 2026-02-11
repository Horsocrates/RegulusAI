"""Run MAS on BBEH: seed=250, 15q, ALL domains on DeepSeek-R1 (ceiling test)."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from regulus.lab.runner import LabRunner, StepProgress


# Per-domain stats accumulator
domain_stats: dict[str, list[dict]] = {}


def on_progress(p: StepProgress):
    if p.type == "domain_complete":
        d = p.event_data
        domain = d.get("domain", "?")
        if domain in ("D1", "D2", "D3", "D4", "D5", "D6"):
            weight = d.get("weight", "?")
            gate = d.get("gate", "?")
            ms = d.get("time_ms", 0)
            model = d.get("model", "?")
            in_tok = d.get("input_tokens", 0)
            out_tok = d.get("output_tokens", 0)
            r_tok = d.get("reasoning_tokens", 0)
            print(
                f"  Q{d.get('question_index', '?'):>2} | {domain} w={weight} gate={gate} "
                f"{ms:>6}ms  in={in_tok} out={out_tok} reason={r_tok}  [{model}]"
            )
            # Accumulate stats
            domain_stats.setdefault(domain, []).append({
                "time_ms": ms,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "reasoning_tokens": r_tok,
            })
    elif p.type == "complete":
        print("\n=== STEP COMPLETE ===")
    elif p.type == "error":
        print(f"\n=== ERROR: {p.event_data} ===")


async def main():
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    print(f"DEEPSEEK_API_KEY: {'SET' if ds_key else 'MISSING'}")
    if not ds_key:
        print("ERROR: DEEPSEEK_API_KEY not found!")
        return

    runner = LabRunner()

    run = runner.create_run(
        name="MAS-BBEH-15q-ALL-R1",
        total_questions=15,
        num_steps=1,
        dataset="bbeh",
        provider="openai",  # doesn't matter, workers override
        concurrency=2,  # R1 is slower, lower concurrency
        mode="mas",
        reasoning_model="deepseek-r1",
        seed=250,
    )
    print(f"\nCreated run #{run.id}: {run.name}")
    print(f"  BBEH seed=250, 15q, concurrency=2")
    print(f"  ALL domains: deepseek-r1 (reasoning model)")
    print()

    final_run = await runner.run_all_steps(run.id, on_progress=on_progress)

    print(f"\nRun #{final_run.id} status: {final_run.status}")
    step = final_run.steps[0]
    passed = sum(1 for r in step.results if r.is_passed)
    total = len(step.results)
    print(f"  {passed}/{total} passed ({100*passed/total:.0f}%)")

    # Per-domain analysis
    print("\n--- Per-Domain Resource Analysis ---")
    print(f"{'Domain':<8} {'Avg Time':>10} {'Avg In':>10} {'Avg Out':>10} {'Avg Reason':>12} {'Total Cost':>12}")
    print("-" * 72)

    for domain in ["D1", "D2", "D3", "D4", "D5", "D6"]:
        stats = domain_stats.get(domain, [])
        if not stats:
            print(f"{domain:<8} {'N/A':>10}")
            continue
        n = len(stats)
        avg_time = sum(s["time_ms"] for s in stats) / n
        avg_in = sum(s["input_tokens"] for s in stats) / n
        avg_out = sum(s["output_tokens"] for s in stats) / n
        avg_reason = sum(s["reasoning_tokens"] for s in stats) / n
        # DeepSeek R1 pricing: $0.55/M input, $2.19/M output (reasoning counted as output)
        total_in = sum(s["input_tokens"] for s in stats)
        total_out = sum(s["output_tokens"] for s in stats)
        total_reason = sum(s["reasoning_tokens"] for s in stats)
        cost = (total_in * 0.55 + (total_out + total_reason) * 2.19) / 1_000_000
        print(
            f"{domain:<8} {avg_time/1000:>9.1f}s {avg_in:>10.0f} {avg_out:>10.0f} "
            f"{avg_reason:>12.0f} ${cost:>11.4f}"
        )

    # Grand totals
    all_stats = [s for stats in domain_stats.values() for s in stats]
    if all_stats:
        total_in = sum(s["input_tokens"] for s in all_stats)
        total_out = sum(s["output_tokens"] for s in all_stats)
        total_reason = sum(s["reasoning_tokens"] for s in all_stats)
        total_cost = (total_in * 0.55 + (total_out + total_reason) * 2.19) / 1_000_000
        print("-" * 72)
        print(
            f"{'TOTAL':<8} {'':>10} {total_in:>10} {total_out:>10} "
            f"{total_reason:>12} ${total_cost:>11.4f}"
        )

    # Per-question details
    print("\n--- Details ---")
    for i, r in enumerate(step.results):
        tag = "PASS" if r.is_passed else "FAIL"
        ans = (r.answer or "")[:100].replace("\n", " ")
        exp = (r.expected or "")[:80]
        t = r.time_seconds or 0
        print(f"Q{i:>2} {tag} {t:>6.1f}s | ans: {ans}")
        print(f"               | exp: {exp}")
        if r.failure_reason:
            print(f"               | why: {(r.failure_reason or '')[:80]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
