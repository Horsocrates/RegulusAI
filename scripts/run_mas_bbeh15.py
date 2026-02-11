"""Run MAS pipeline on BBEH: seed=250, 15 questions, all gpt-4o-mini."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.lab.runner import LabRunner, StepProgress
from regulus.mas.routing import RoutingConfig, DomainRoute
from regulus.mas.table import DOMAIN_CODES
from regulus.mas.worker_factory import create_workers_from_routing, clear_client_cache


def on_progress(p: StepProgress):
    if p.type == "domain_complete":
        d = p.event_data
        domain = d.get("domain", "?")
        if domain in ("D1", "D2", "D3", "D4", "D5", "D6"):
            weight = d.get("weight", "?")
            gate = d.get("gate", "?")
            ms = d.get("time_ms", 0)
            print(f"  Q{d.get('question_index', '?'):>2} | {domain} w={weight} gate={gate} {ms}ms")
    elif p.type == "complete":
        print("\n=== STEP COMPLETE ===")
    elif p.type == "error":
        print(f"\n=== ERROR: {p.event_data} ===")


async def main():
    runner = LabRunner()

    run = runner.create_run(
        name="MAS-BBEH-15q-seed250-mini",
        total_questions=15,
        num_steps=1,
        dataset="bbeh",
        provider="openai",
        concurrency=3,  # lower to avoid rate limits
        mode="mas",
        seed=250,
    )
    print(f"Created run #{run.id}: {run.name}")
    print(f"  mode=mas, dataset=bbeh, seed=250, questions=15, concurrency=3")
    print(f"  ALL domains: gpt-4o-mini")
    print()

    final_run = await runner.run_all_steps(run.id, on_progress=on_progress)

    print(f"\nRun #{final_run.id} status: {final_run.status}")
    step = final_run.steps[0]
    passed = sum(1 for r in step.results if r.is_passed)
    total = len(step.results)
    print(f"  {passed}/{total} passed ({100*passed/total:.0f}%)")

    print("\n--- Details ---")
    for i, r in enumerate(step.results):
        tag = "PASS" if r.is_passed else "FAIL"
        ans = (r.answer or "")[:100].replace("\n", " ")
        exp = (r.expected or "")[:80]
        t = r.time_seconds or 0
        print(f"Q{i:>2} {tag} {t:>5.1f}s | ans: {ans}")
        print(f"              | exp: {exp}")
        if r.failure_reason:
            print(f"              | why: {(r.failure_reason or '')[:80]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
