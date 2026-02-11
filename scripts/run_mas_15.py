"""Run MAS pipeline: seed=250, 15 questions, mode=mas."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.lab.runner import LabRunner, StepProgress


def on_progress(p: StepProgress):
    if p.type == "domain_start":
        d = p.event_data
        print(f"  Q{d.get('question_index', '?')} | {d.get('domain', '?')}: {d.get('domain_name', '')}")
    elif p.type == "domain_complete":
        d = p.event_data
        domain = d.get("domain", "?")
        weight = d.get("weight", "?")
        gate = d.get("gate", "?")
        ms = d.get("time_ms", 0)
        print(f"  Q{d.get('question_index', '?')} | {domain} done: w={weight} gate={gate} {ms}ms")
    elif p.type == "question_complete":
        d = p.event_data or {}
        print(f"  --- Q{d.get('question_index', '?')} finished ---")
    elif p.type == "complete":
        print("\n=== STEP COMPLETE ===")
    elif p.type == "error":
        print(f"\n=== ERROR: {p.event_data} ===")


async def main():
    runner = LabRunner()

    run = runner.create_run(
        name="MAS-15q-seed250",
        total_questions=15,
        num_steps=1,
        dataset="simpleqa",
        provider="openai",
        concurrency=5,
        mode="mas",
        seed=250,
    )
    print(f"Created run #{run.id}: {run.name}")
    print(f"  mode={run.mode}, seed=250, questions=15, concurrency=5")
    print()

    final_run = await runner.run_all_steps(run.id, on_progress=on_progress)

    print(f"\nRun #{final_run.id} status: {final_run.status}")
    for step in final_run.steps:
        print(f"  Step {step.step_number}: {step.status}")
        if step.results:
            passed = sum(1 for r in step.results if r.is_passed)
            total = len(step.results)
            print(f"    Results: {passed}/{total} passed ({100*passed/total:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
