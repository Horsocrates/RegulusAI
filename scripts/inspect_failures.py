"""Inspect failures from a v2 run - print detailed reasoning for incorrect answers."""
import json
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from regulus.lab.models import LabDB

run_id = int(sys.argv[1]) if len(sys.argv) > 1 else 25

db = LabDB()
results = db.get_all_results(run_id)

fail_count = 0
for i, r in enumerate(results):
    if r.correct:
        continue
    fail_count += 1
    print("=" * 80)
    print(f"FAILURE #{fail_count}: Q{i}")
    print("=" * 80)
    print(f"Q: {r.question[:200]}")
    print(f"Expected: {r.expected}")
    print(f"Got:      {(r.answer or '(none)')[:200]}")
    print(f"Judge:    {r.judge_reason}")
    print()

    if not r.reasoning_json:
        print("  NO REASONING DATA")
        print()
        continue

    rj = json.loads(r.reasoning_json)
    if rj.get("version") != "2.0":
        print("  v1 format (not v2)")
        print()
        continue

    audit = rj.get("final_audit")
    if not audit:
        print("  NO AUDIT DATA")
        print()
        continue

    print(f"  Total weight: {audit['total_weight']}")
    print(f"  Gates passed: {audit['all_gates_passed']}")
    print(f"  Failed gates: {audit['failed_gates']}")
    if audit.get("violation_patterns"):
        print(f"  VIOLATIONS: {audit['violation_patterns']}")
    print()

    for d in audit["domains"]:
        summary = d.get("segment_summary", "")[:150]
        gate_str = "PASS" if d["gate_passed"] else "FAIL"
        print(f"  {d['domain']} W={d['weight']:>2d} gate={gate_str} | {summary}")

        # Print domain-specific signals
        signals = []
        if d.get("d1_depth") is not None:
            signals.append(f"d1_depth={d['d1_depth']}")
        if d.get("d2_depth") is not None:
            signals.append(f"d2_depth={d['d2_depth']}")
        if d.get("d3_objectivity_pass") is not None:
            signals.append(f"obj={'OK' if d['d3_objectivity_pass'] else 'FAIL'}")
        if d.get("d4_aristotle_ok") is not None:
            signals.append(f"arist={'OK' if d['d4_aristotle_ok'] else 'FAIL'}")
        if d.get("d5_certainty_type"):
            signals.append(f"cert={d['d5_certainty_type']}")
        if d.get("d6_genuine") is not None:
            signals.append(f"genuine={'OK' if d['d6_genuine'] else 'FAIL'}")
        if signals:
            print(f"         {' | '.join(signals)}")

        if d.get("issues"):
            for iss in d["issues"]:
                print(f"         ISSUE: {iss}")

    # Print correction trajectory if any
    audits = rj.get("audits", [])
    if len(audits) > 1:
        print()
        print("  Correction trajectory:")
        for j, a in enumerate(audits):
            w = a.get("total_weight", 0)
            gp = a.get("all_gates_passed", False)
            print(f"    Round {j}: W={w} gates={'OK' if gp else 'FAIL'}")

    print()

print(f"Total failures: {fail_count}/{len(results)}")
