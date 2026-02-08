"""Compare three runs side-by-side: baseline (#25), v1.0b-calibrated (#26), v1.0b-fix (#29)."""
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from regulus.lab.models import LabDB

db = LabDB()

run_ids = [25, 26, 29]
labels = {25: "baseline", 26: "v1.0b-cal", 29: "v1.0b-fix"}
data = {}
for rid in run_ids:
    data[rid] = db.get_all_results(rid)

print("=" * 105)
print(f"{'Q':>3} | {'#25 baseline':^20} | {'#26 v1.0b-cal':^20} | {'#29 v1.0b-fix':^20} | Changes")
print("-" * 105)

for i in range(15):
    cols = []
    for rid in run_ids:
        r = data[rid][i]
        rj = json.loads(r.reasoning_json) if r.reasoning_json else {}
        audit = rj.get("final_audit", {})
        w = audit.get("total_weight", 0)
        ok = "Y" if r.correct else "N"
        vp = "Y" if audit.get("all_gates_passed") else "N"
        cols.append(f"{ok}/{vp} W={w:>3}")

    changes = []
    r25 = data[25][i]
    r26 = data[26][i]
    r29 = data[29][i]
    if not r25.correct and r29.correct:
        changes.append("+FIX25")
    elif r25.correct and not r29.correct:
        changes.append("-REG25")
    if not r26.correct and r29.correct:
        changes.append("+FIX26")
    elif r26.correct and not r29.correct:
        changes.append("-REG26")

    change_str = " ".join(changes)
    print(f"{i:>3} | {cols[0]:^20} | {cols[1]:^20} | {cols[2]:^20} | {change_str}")

print("-" * 105)

# Summary statistics
for rid in run_ids:
    label = labels[rid]
    results = data[rid]
    correct = sum(1 for r in results if r.correct)

    d1_depths = []
    d2_depths = []
    d3_pass = 0
    d6_gen = 0
    violations = 0
    false_rej = 0
    total_w = 0

    for r in results:
        if not r.reasoning_json:
            continue
        rj = json.loads(r.reasoning_json)
        audit = rj.get("final_audit", {})
        total_w += audit.get("total_weight", 0)
        vp = audit.get("violation_patterns", [])
        violations += len(vp)
        if not audit.get("all_gates_passed") and r.correct:
            false_rej += 1
        for d in audit.get("domains", []):
            if d.get("domain") == "D1" and d.get("d1_depth") is not None:
                d1_depths.append(d["d1_depth"])
            if d.get("domain") == "D2" and d.get("d2_depth") is not None:
                d2_depths.append(d["d2_depth"])
            if d.get("domain") == "D3" and d.get("d3_objectivity_pass"):
                d3_pass += 1
            if d.get("domain") == "D6" and d.get("d6_genuine"):
                d6_gen += 1

    avg_w = total_w / 15
    avg_d1 = sum(d1_depths) / len(d1_depths) if d1_depths else 0
    avg_d2 = sum(d2_depths) / len(d2_depths) if d2_depths else 0
    pct = correct / 15 * 100
    print(
        f"  {label:>12}: {correct}/15 ({pct:.0f}%) | "
        f"avgW={avg_w:.0f} | D1={avg_d1:.1f} D2={avg_d2:.1f} | "
        f"D3pass={d3_pass}/15 ({d3_pass/15*100:.0f}%) | "
        f"D6gen={d6_gen}/15 ({d6_gen/15*100:.0f}%) | "
        f"violations={violations} | false_rej={false_rej}"
    )

print()
print("Legend: Y/N = correct/gates_passed, W = total weight")
print("Changes: +FIX25 = v29 fixed what v25 missed, -REG25 = v29 regressed from v25")
