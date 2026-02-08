"""
Extract all failed questions across runs into a registry file.
Usage: python scripts/build_failure_registry.py 24 25 26 29 30
"""
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from regulus.lab.models import LabDB


def build_registry(run_ids: list[int]):
    db = LabDB()
    registry = {}  # question_key → {question, expected, failures, passes, ...}

    for run_id in run_ids:
        results = db.get_all_results(run_id)
        run = db.get_run(run_id)
        if not results:
            print(f"  Run #{run_id}: no results, skipping")
            continue

        for r in results:
            # Use first 100 chars as key (stable across runs with same seed)
            q_key = r.question[:100]

            if q_key not in registry:
                registry[q_key] = {
                    "question": r.question[:500],
                    "expected": r.expected,
                    "runs_seen": [],
                    "failures": [],
                    "passes": [],
                }

            entry = registry[q_key]
            entry["runs_seen"].append(run_id)

            if r.correct:
                entry["passes"].append({
                    "run_id": run_id,
                    "answer": (r.answer or "")[:200],
                    "mode": run.mode if run else "?",
                })
            else:
                # Check if it's a false rejection
                rj = {}
                audit_detail = ""
                false_rejection = False
                if r.reasoning_json:
                    try:
                        rj = json.loads(r.reasoning_json)
                        if rj.get("final_audit"):
                            audit = rj["final_audit"]
                            # Check if answer matches expected but gates failed
                            if audit.get("all_gates_passed") is False:
                                # Approximate false rejection check
                                pass

                            d3 = next((d for d in audit.get("domains", []) if d["domain"] == "D3"), None)
                            if d3 and d3.get("d3_objectivity_pass") is False:
                                audit_detail = "D3_OBJECTIVITY_ZERO_GATE"
                            violations = audit.get("violation_patterns", [])
                            if violations:
                                if audit_detail:
                                    audit_detail += " "
                                audit_detail += f"VIOLATIONS:{','.join(str(v) for v in violations)}"
                    except Exception:
                        audit_detail = "PARSE_ERROR"

                entry["failures"].append({
                    "run_id": run_id,
                    "answer": (r.answer or "")[:200],
                    "judge_reason": (r.judge_reason or "")[:200],
                    "audit_detail": audit_detail,
                    "mode": run.mode if run else "?",
                })

    # Sort: always-failed first, then sometimes-failed
    def sort_key(item):
        q_key, data = item
        fail_rate = len(data["failures"]) / max(len(data["runs_seen"]), 1)
        return (-fail_rate, -len(data["failures"]))

    sorted_registry = dict(sorted(registry.items(), key=sort_key))

    # Save
    output_path = Path("data/failure_registry.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_registry, f, indent=2, ensure_ascii=False)

    # Print summary
    total_questions = len(sorted_registry)
    always_fail = sum(1 for d in sorted_registry.values() if len(d["passes"]) == 0 and len(d["failures"]) > 0)
    sometimes_fail = sum(1 for d in sorted_registry.values() if len(d["passes"]) > 0 and len(d["failures"]) > 0)
    always_pass = sum(1 for d in sorted_registry.values() if len(d["failures"]) == 0)
    d3_failures = sum(
        sum(1 for f in d["failures"] if "D3_OBJECTIVITY" in f.get("audit_detail", ""))
        for d in sorted_registry.values()
    )

    print(f"\n{'=' * 60}")
    print(f"  FAILURE REGISTRY - {total_questions} unique questions across {len(run_ids)} runs")
    print(f"{'=' * 60}")
    print(f"  Always fail:       {always_fail}")
    print(f"  Sometimes fail:    {sometimes_fail}")
    print(f"  Always pass:       {always_pass}")
    print(f"  D3 objectivity kills: {d3_failures}")
    print(f"\n  Saved to: {output_path}")

    # Print always-fail questions
    if always_fail > 0:
        print(f"\n  ALWAYS FAIL ({always_fail}):")
        for q_key, data in sorted_registry.items():
            if len(data["passes"]) == 0 and len(data["failures"]) > 0:
                details = set(f["audit_detail"] for f in data["failures"] if f["audit_detail"])
                print(f"    Q: {q_key[:80]}...")
                print(f"       Expected: {data['expected']}")
                if details:
                    print(f"       Audit: {details}")
                print()

    # Print sometimes-fail questions
    if sometimes_fail > 0:
        print(f"  SOMETIMES FAIL ({sometimes_fail}):")
        for q_key, data in sorted_registry.items():
            if len(data["passes"]) > 0 and len(data["failures"]) > 0:
                pass_runs = [p["run_id"] for p in data["passes"]]
                fail_runs = [f["run_id"] for f in data["failures"]]
                print(f"    Q: {q_key[:80]}...")
                print(f"       Expected: {data['expected']}")
                print(f"       Pass: {pass_runs} | Fail: {fail_runs}")
                print()


if __name__ == "__main__":
    run_ids = [int(x) for x in sys.argv[1:]]
    if not run_ids:
        print("Usage: python scripts/build_failure_registry.py RUN_ID [RUN_ID ...]")
        sys.exit(1)
    build_registry(run_ids)
