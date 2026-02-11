"""Run MAS on BBEH: seed=250, 15q, D4+D5=deepseek-chat, rest=gpt-4o-mini."""

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


def on_progress(p: StepProgress):
    if p.type == "domain_complete":
        d = p.event_data
        domain = d.get("domain", "?")
        if domain in ("D1", "D2", "D3", "D4", "D5", "D6"):
            weight = d.get("weight", "?")
            gate = d.get("gate", "?")
            ms = d.get("time_ms", 0)
            model = d.get("model", "?")
            print(f"  Q{d.get('question_index', '?'):>2} | {domain} w={weight} gate={gate} {ms:>6}ms  [{model}]")
    elif p.type == "complete":
        print("\n=== STEP COMPLETE ===")
    elif p.type == "error":
        print(f"\n=== ERROR: {p.event_data} ===")


async def main():
    # Verify keys
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    oa_key = os.environ.get("OPENAI_API_KEY", "")
    print(f"DEEPSEEK_API_KEY: {'SET' if ds_key else 'MISSING'}")
    print(f"OPENAI_API_KEY: {'SET' if oa_key else 'MISSING'}")
    if not ds_key:
        print("ERROR: DEEPSEEK_API_KEY not found!")
        return

    runner = LabRunner()

    run = runner.create_run(
        name="MAS-BBEH-15q-DS-D4D5",
        total_questions=15,
        num_steps=1,
        dataset="bbeh",
        provider="openai",
        concurrency=3,
        mode="mas",
        seed=250,
    )
    print(f"\nCreated run #{run.id}: {run.name}")
    print(f"  BBEH seed=250, 15q, concurrency=3")
    print(f"  D1+D2+D3+D6: gpt-4o-mini")
    print(f"  D4+D5: deepseek-chat (V3)")
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
        print(f"Q{i:>2} {tag} {t:>6.1f}s | ans: {ans}")
        print(f"               | exp: {exp}")
        if r.failure_reason:
            print(f"               | why: {(r.failure_reason or '')[:80]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
