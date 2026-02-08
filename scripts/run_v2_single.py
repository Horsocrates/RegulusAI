"""Run a single v2 benchmark (no v1 comparison)."""
import asyncio
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from regulus.lab.runner import LabRunner

async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 137
    label = sys.argv[3] if len(sys.argv) > 3 else ""

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = label or f"v2_bbeh_{n}q_{timestamp}"

    runner = LabRunner()
    run = runner.create_run(
        name=name,
        dataset="bbeh",
        total_questions=n,
        num_steps=1,
        mode="v2",
        reasoning_model="deepseek",
        concurrency=5,
        seed=seed,
    )
    print(f"Created v2 run #{run.id} (seed={seed})")
    print(f"  mode={run.mode}, dataset={run.dataset}, n={n}, reasoning_model={run.reasoning_model}")
    print()

    await runner.run_all_steps(run.id)

    # Print summary
    from regulus.lab.models import LabDB
    db = LabDB()
    results = db.get_all_results(run.id)
    passed = sum(1 for r in results if r.is_passed)
    judge_errors = sum(1 for r in results if r.correct is None and r.valid)
    print(f"\nCompleted: {passed}/{len(results)} passed")
    print(f"Accuracy: {passed/len(results)*100:.1f}%")
    if judge_errors:
        print(f"Judge errors: {judge_errors} (counted as passed since structurally valid)")
    print(f"Run ID: #{run.id}")

if __name__ == "__main__":
    asyncio.run(main())
