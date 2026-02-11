"""Report generation for Lab runs."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from regulus.lab.models import Run, Step, Result, RunStatus, StepStatus


class ReportGenerator:
    """Generates markdown and JSON reports from Lab runs."""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "data" / "lab_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir

    def generate_json(self, run: Run, filename: Optional[str] = None) -> Path:
        """Generate JSON report."""
        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"run_{run.id}_{timestamp}.json"

        filepath = self.output_dir / filename

        report = {
            "meta": {
                "run_id": run.id,
                "name": run.name,
                "dataset": run.dataset,
                "provider": run.provider,
                "created_at": run.created_at,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "config": {
                "total_questions": run.total_questions,
                "num_steps": run.num_steps,
                "concurrency": run.concurrency,
            },
            "summary": {
                "status": run.status.value,
                "completed_questions": run.completed_questions,
                "valid_count": run.valid_count,
                "correct_count": run.correct_count,
                "valid_rate": (run.valid_count / run.completed_questions * 100) if run.completed_questions > 0 else 0,
                "correct_rate": (run.correct_count / run.completed_questions * 100) if run.completed_questions > 0 else 0,
                "total_time_seconds": run.total_time,
                "avg_time_per_question": run.total_time / run.completed_questions if run.completed_questions > 0 else 0,
            },
            "steps": [],
            "results": [],
        }

        for step in run.steps:
            step_data = {
                "step_number": step.step_number,
                "status": step.status.value,
                "questions_range": [step.questions_start, step.questions_end],
                "questions_count": step.questions_end - step.questions_start,
                "valid_count": step.valid_count,
                "correct_count": step.correct_count,
                "total_time": step.total_time,
                "started_at": step.started_at,
                "completed_at": step.completed_at,
            }
            report["steps"].append(step_data)

            for result in step.results:
                result_data = {
                    "step": step.step_number,
                    "question": result.question,
                    "expected": result.expected,
                    "answer": result.answer,
                    "valid": result.valid,
                    "correct": result.correct,
                    "informative": result.informative,
                    "judge_reason": result.judge_reason,
                    "corrections": result.corrections,
                    "time_seconds": result.time_seconds,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
                # Include audit data for v2 runs
                if result.reasoning_json:
                    try:
                        rj = json.loads(result.reasoning_json)
                        if rj.get("version") == "2.0":
                            result_data["audit"] = rj.get("final_audit")
                    except (json.JSONDecodeError, KeyError):
                        pass
                report["results"].append(result_data)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return filepath

    def generate_markdown(self, run: Run, filename: Optional[str] = None) -> Path:
        """Generate Markdown report."""
        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"run_{run.id}_{timestamp}.md"

        filepath = self.output_dir / filename

        lines = []

        # Header
        lines.append(f"# Lab Report: {run.name}")
        lines.append("")
        lines.append(f"**Run ID:** {run.id}")
        lines.append(f"**Dataset:** {run.dataset}")
        lines.append(f"**Provider:** {run.provider}")
        lines.append(f"**Created:** {run.created_at}")
        lines.append(f"**Status:** {run.status.value}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Questions | {run.total_questions} |")
        lines.append(f"| Completed | {run.completed_questions} |")
        lines.append(f"| Valid | {run.valid_count} |")
        lines.append(f"| Correct | {run.correct_count} |")

        valid_rate = (run.valid_count / run.completed_questions * 100) if run.completed_questions > 0 else 0
        correct_rate = (run.correct_count / run.completed_questions * 100) if run.completed_questions > 0 else 0
        avg_time = run.total_time / run.completed_questions if run.completed_questions > 0 else 0

        lines.append(f"| Valid Rate | {valid_rate:.1f}% |")
        lines.append(f"| Correct Rate | {correct_rate:.1f}% |")
        lines.append(f"| Total Time | {run.total_time:.1f}s |")
        lines.append(f"| Avg Time/Question | {avg_time:.1f}s |")
        lines.append("")

        # Steps Overview
        lines.append("## Steps")
        lines.append("")
        lines.append("| Step | Status | Questions | Valid | Correct | Time |")
        lines.append("|------|--------|-----------|-------|---------|------|")

        for step in run.steps:
            q_count = step.questions_end - step.questions_start
            status_emoji = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
            }.get(step.status, "❓")

            lines.append(
                f"| {step.step_number} | {status_emoji} {step.status.value} | "
                f"{q_count} | {step.valid_count} | {step.correct_count} | {step.total_time:.1f}s |"
            )

        lines.append("")

        # Detailed Results
        lines.append("## Detailed Results")
        lines.append("")

        for step in run.steps:
            if not step.results:
                continue

            lines.append(f"### Step {step.step_number}")
            lines.append("")

            for i, result in enumerate(step.results, 1):
                status_emoji = "✅" if result.correct else ("⚠️" if result.valid else "❌")

                lines.append(f"#### {i}. {status_emoji}")
                lines.append("")
                lines.append(f"**Question:** {result.question}")
                lines.append("")
                lines.append(f"**Expected:** {result.expected}")
                lines.append("")
                lines.append(f"**Answer:** {result.answer or 'No answer'}")
                lines.append("")

                if result.judge_reason:
                    lines.append(f"**Judge:** {result.judge_reason}")
                    lines.append("")

                details = []
                details.append(f"valid={result.valid}")
                details.append(f"correct={result.correct}")
                if result.corrections > 0:
                    details.append(f"corrections={result.corrections}")
                details.append(f"time={result.time_seconds:.1f}s")
                lines.append(f"*{', '.join(details)}*")
                lines.append("")
                lines.append("---")
                lines.append("")

        # Footer
        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by RegulusAI Lab on {datetime.now(timezone.utc).isoformat()}*")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    def generate_v2_analysis(self, run: Run, filename: Optional[str] = None) -> Path:
        """Generate a comprehensive v2 audit analysis report (Markdown)."""
        from collections import Counter

        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"v2_analysis_{run.id}_{timestamp}.md"

        filepath = self.output_dir / filename

        # Collect all audit data from reasoning_json
        audits = []
        results_with_audits = []
        for step in run.steps:
            for result in step.results:
                if not result.reasoning_json:
                    continue
                try:
                    rj = json.loads(result.reasoning_json)
                    if rj.get("version") == "2.0" and rj.get("final_audit"):
                        audits.append(rj["final_audit"])
                        results_with_audits.append((result, rj))
                except (json.JSONDecodeError, KeyError):
                    continue

        n = len(audits)
        if n == 0:
            lines = [f"# v2 Analysis: {run.name}", "", "No v2 audit data found in this run."]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return filepath

        lines = []
        lines.append(f"# v2 Audit Analysis: {run.name}")
        lines.append("")
        lines.append(f"**Run ID:** {run.id}")
        lines.append(f"**Dataset:** {run.dataset}")
        lines.append(f"**Questions with audit data:** {n}")
        lines.append(f"**Date:** {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        # === SECTION 1: AGGREGATE STATISTICS ===
        lines.append("## 1. Aggregate Statistics")
        lines.append("")

        valid_count = sum(1 for r, _ in results_with_audits if r.valid)
        correct_count = sum(1 for r, _ in results_with_audits if r.correct)
        false_rejections = sum(1 for r, _ in results_with_audits if not r.valid and r.correct)

        lines.append("### Pass/Fail")
        lines.append("")
        lines.append("| Metric | Count | Rate |")
        lines.append("|--------|-------|------|")
        lines.append(f"| Structurally valid | {valid_count} | {valid_count/n:.0%} |")
        lines.append(f"| Correct answer | {correct_count} | {correct_count/n:.0%} |")
        lines.append(f"| **False rejections** (invalid but correct) | {false_rejections} | {false_rejections/n:.0%} |")
        lines.append("")

        lines.append("### Per-Domain Weight Distribution")
        lines.append("")
        lines.append("| Domain | Avg Weight | Min | Max | Present% |")
        lines.append("|--------|-----------|-----|-----|----------|")

        for di in range(1, 7):
            dname = f"D{di}"
            domain_data = []
            present_count = 0
            for audit in audits:
                dd = next((d for d in audit["domains"] if d["domain"] == dname), None)
                if dd and dd["present"]:
                    present_count += 1
                    domain_data.append(dd["weight"])

            if domain_data:
                avg_w = sum(domain_data) / len(domain_data)
                min_w = min(domain_data)
                max_w = max(domain_data)
            else:
                avg_w = min_w = max_w = 0
            lines.append(f"| {dname} | {avg_w:.0f} | {min_w} | {max_w} | {present_count/n:.0%} |")
        lines.append("")

        # === SECTION 2: v1.0a SIGNAL ANALYSIS ===
        lines.append("## 2. v1.0a Signal Analysis")
        lines.append("")

        # D1 Depth
        d1_depths = [d.get("d1_depth") for a in audits for d in a["domains"] if d["domain"] == "D1" and d.get("d1_depth") is not None]
        lines.append("### D1 Recognition Depth")
        lines.append("")
        if d1_depths:
            depth_names = {1: "Data", 2: "Information", 3: "Qualities", 4: "Characteristics"}
            for level in [1, 2, 3, 4]:
                count = d1_depths.count(level)
                bar = "#" * count
                lines.append(f"  Level {level} ({depth_names[level]:<16}): {count:3d} ({count/len(d1_depths):.0%}) {bar}")
            lines.append(f"  Average depth: {sum(d1_depths)/len(d1_depths):.1f}")
        else:
            lines.append("  No d1_depth data")
        lines.append("")

        # D2 Depth
        d2_depths = [d.get("d2_depth") for a in audits for d in a["domains"] if d["domain"] == "D2" and d.get("d2_depth") is not None]
        lines.append("### D2 Clarification Depth")
        lines.append("")
        if d2_depths:
            depth_names = {1: "Nominal", 2: "Operational", 3: "Structural", 4: "Essential"}
            for level in [1, 2, 3, 4]:
                count = d2_depths.count(level)
                bar = "#" * count
                lines.append(f"  Level {level} ({depth_names[level]:<16}): {count:3d} ({count/len(d2_depths):.0%}) {bar}")
            lines.append(f"  Average depth: {sum(d2_depths)/len(d2_depths):.1f}")
        else:
            lines.append("  No d2_depth data")
        lines.append("")

        # D3 Objectivity
        d3_obj = [d.get("d3_objectivity_pass") for a in audits for d in a["domains"] if d["domain"] == "D3" and d.get("d3_objectivity_pass") is not None]
        lines.append("### D3 Objectivity Test")
        lines.append("")
        if d3_obj:
            pass_count = sum(1 for x in d3_obj if x)
            fail_count = sum(1 for x in d3_obj if not x)
            lines.append(f"  Pass: {pass_count} ({pass_count/len(d3_obj):.0%})")
            lines.append(f"  Fail: {fail_count} ({fail_count/len(d3_obj):.0%})")
            if fail_count / len(d3_obj) > 0.3:
                lines.append(f"  WARNING: >30% failure rate -- auditor may be too strict")
        else:
            lines.append("  No d3_objectivity data")
        lines.append("")

        # D4 Aristotle
        d4_arist = [d.get("d4_aristotle_ok") for a in audits for d in a["domains"] if d["domain"] == "D4" and d.get("d4_aristotle_ok") is not None]
        lines.append("### D4 Aristotle's Rules")
        lines.append("")
        if d4_arist:
            pass_count = sum(1 for x in d4_arist if x)
            lines.append(f"  Pass: {pass_count}/{len(d4_arist)} ({pass_count/len(d4_arist):.0%})")
        else:
            lines.append("  No d4_aristotle data")
        lines.append("")

        # D5 Certainty
        d5_certs = [d.get("d5_certainty_type") for a in audits for d in a["domains"] if d["domain"] == "D5" and d.get("d5_certainty_type")]
        lines.append("### D5 Certainty Type Distribution")
        lines.append("")
        if d5_certs:
            cert_counts = Counter(d5_certs)
            for ct in ["necessary", "probabilistic", "evaluative", "unmarked"]:
                count = cert_counts.get(ct, 0)
                bar = "#" * count
                lines.append(f"  {ct:<16}: {count:3d} ({count/len(d5_certs):.0%}) {bar}")
            if cert_counts.get("unmarked", 0) / len(d5_certs) > 0.3:
                lines.append(f"  WARNING: Many unmarked conclusions -- LRM prompt may not be followed")
        else:
            lines.append("  No d5_certainty data")
        lines.append("")

        # D6 Genuine
        d6_gen = [d.get("d6_genuine") for a in audits for d in a["domains"] if d["domain"] == "D6" and d.get("d6_genuine") is not None]
        lines.append("### D6 Genuine Reflection")
        lines.append("")
        if d6_gen:
            genuine = sum(1 for x in d6_gen if x)
            lines.append(f"  Genuine: {genuine}/{len(d6_gen)} ({genuine/len(d6_gen):.0%})")
        else:
            lines.append("  No d6_genuine data")
        lines.append("")

        # Violations
        all_violations = []
        for a in audits:
            vp = a.get("violation_patterns", [])
            all_violations.extend(vp)

        lines.append("### Violation Patterns Detected")
        lines.append("")
        if all_violations:
            vp_counts = Counter(all_violations)
            for pattern, count in vp_counts.most_common():
                bar = "#" * count
                lines.append(f"  {pattern:<30}: {count:3d} {bar}")
            lines.append(f"  Total violations: {len(all_violations)} across {n} questions ({len(all_violations)/n:.1f} avg)")
            lines.append(f"  Questions with >=1 violation: {sum(1 for a in audits if a.get('violation_patterns'))}")
        else:
            lines.append("  No violations detected")
        lines.append("")

        # Diagnostic warnings
        all_diag_warnings = []
        for a in audits:
            for issue in a.get("overall_issues", []):
                if isinstance(issue, str) and issue.startswith("DIAG:"):
                    all_diag_warnings.append(issue)

        lines.append("### Diagnostic Warnings")
        lines.append("")
        if all_diag_warnings:
            warning_types = []
            for w in all_diag_warnings:
                wtype = w.split(" — ")[0] if " — " in w else w.split(" ")[0]
                warning_types.append(wtype)
            wt_counts = Counter(warning_types)
            for wtype, count in wt_counts.most_common():
                bar = "#" * count
                lines.append(f"  {wtype:<40}: {count:3d} {bar}")
            lines.append(f"  Total warnings: {len(all_diag_warnings)} across {n} questions ({len(all_diag_warnings)/n:.1f} avg)")
            lines.append(f"  Questions with >=1 warning: {sum(1 for a in audits if any(isinstance(i, str) and i.startswith('DIAG:') for i in a.get('overall_issues', [])))}")
        else:
            lines.append("  No diagnostic warnings generated")
        lines.append("")

        # === SECTION 3: SIGNAL POPULATION RATE ===
        lines.append("## 3. Signal Population Rate")
        lines.append("")
        lines.append("How often does the auditor actually return each v1.0a field?")
        lines.append("")

        field_checks = [
            ("d1_depth", "D1"), ("d2_depth", "D2"), ("d3_objectivity_pass", "D3"),
            ("d4_aristotle_ok", "D4"), ("d5_certainty_type", "D5"), ("d6_genuine", "D6"),
        ]

        lines.append("| Field | Domain | Populated | Rate |")
        lines.append("|-------|--------|-----------|------|")
        for field_name, domain_name in field_checks:
            populated = sum(
                1 for a in audits
                for d in a["domains"]
                if d["domain"] == domain_name and d.get(field_name) is not None
            )
            lines.append(f"| {field_name} | {domain_name} | {populated}/{n} | {populated/n:.0%} |")

        vp_populated = sum(1 for a in audits if "violation_patterns" in a)
        lines.append(f"| violation_patterns | all | {vp_populated}/{n} | {vp_populated/n:.0%} |")
        lines.append("")

        # === SECTION 4: CORRECTION TRAJECTORY ===
        lines.append("## 4. Correction Trajectory")
        lines.append("")

        multi_round = [(r, rj) for r, rj in results_with_audits if rj.get("audit_rounds", 1) > 1]
        if multi_round:
            lines.append(f"Questions with corrections: {len(multi_round)}/{n}")
            lines.append("")
            for r, rj in multi_round[:10]:
                all_audits_data = rj.get("audits", [])
                if len(all_audits_data) >= 2:
                    w1 = all_audits_data[0].get("total_weight", 0)
                    wf = all_audits_data[-1].get("total_weight", 0)
                    delta = wf - w1
                    arrow = "+" if delta > 0 else ("-" if delta < 0 else "=")
                    lines.append(f"  Q: {r.question[:70]}...")
                    lines.append(f"     Round 1: W={w1} -> Final: W={wf} ({arrow}{abs(delta)}) | correct={r.correct}")
                    lines.append("")
        else:
            lines.append("No questions required corrections.")
        lines.append("")

        # === SECTION 5: PER-QUESTION DETAIL ===
        lines.append("## 5. Per-Question Detail")
        lines.append("")

        for i, (result, rj) in enumerate(results_with_audits, 1):
            audit = rj["final_audit"]
            status = "CORRECT" if result.correct else ("VALID" if result.valid else "FAIL")

            lines.append(f"### Q{i}. {status}")
            lines.append("")
            lines.append(f"**Question:** {result.question[:200]}")
            lines.append(f"**Expected:** {result.expected}")
            lines.append(f"**Answer:** {result.answer or 'None'}")
            lines.append(f"**Valid:** {result.valid} | **Correct:** {result.correct} | **Time:** {result.time_seconds:.1f}s | **Corrections:** {result.corrections}")
            lines.append("")

            lines.append("| Domain | W | Gate | ERRS | Depth/Signal | Issues |")
            lines.append("|--------|---|------|------|--------------|--------|")

            for dd in audit["domains"]:
                if not dd["present"]:
                    lines.append(f"| {dd['domain']} | -- | -- | -- | -- | not present |")
                    continue

                gate = "PASS" if dd["gate_passed"] else "FAIL"
                errs = f"{'E' if dd['e_exists'] else '_'}{'R' if dd['r_exists'] else '_'}{'r' if dd['rule_exists'] else '_'}{'S' if dd['s_exists'] else '_'}"

                signal = ""
                dom = dd["domain"]
                if dom == "D1" and dd.get("d1_depth") is not None:
                    signal = f"depth={dd['d1_depth']}"
                elif dom == "D2" and dd.get("d2_depth") is not None:
                    signal = f"depth={dd['d2_depth']}"
                elif dom == "D3" and dd.get("d3_objectivity_pass") is not None:
                    signal = f"obj={'PASS' if dd['d3_objectivity_pass'] else 'FAIL'}"
                elif dom == "D4" and dd.get("d4_aristotle_ok") is not None:
                    signal = f"arist={'PASS' if dd['d4_aristotle_ok'] else 'FAIL'}"
                elif dom == "D5" and dd.get("d5_certainty_type"):
                    signal = dd["d5_certainty_type"]
                elif dom == "D6" and dd.get("d6_genuine") is not None:
                    signal = f"genuine={'PASS' if dd['d6_genuine'] else 'FAIL'}"

                issues_str = "; ".join(dd.get("issues", [])[:2]) or "--"
                lines.append(f"| {dd['domain']} | {dd['weight']} | {gate} | {errs} | {signal} | {issues_str} |")

            vp = audit.get("violation_patterns", [])
            if vp:
                lines.append(f"\n**Violations:** {', '.join(vp)}")

            if audit.get("overall_issues"):
                lines.append(f"\n**Overall issues:** {'; '.join(audit['overall_issues'])}")

            if result.judge_reason:
                lines.append(f"\n**Judge:** {result.judge_reason}")

            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"\n*Generated by Regulus v1.0a Analysis on {datetime.now(timezone.utc).isoformat()}*")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    def export(self, run: Run) -> dict:
        """Export reports. Includes v2 analysis for v2 runs."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_name = f"run_{run.id}_{timestamp}"

        json_path = self.generate_json(run, f"{base_name}.json")
        md_path = self.generate_markdown(run, f"{base_name}.md")

        result = {
            "json": str(json_path),
            "markdown": str(md_path),
        }

        # Auto-generate v2 analysis for audit pipeline runs
        if run.mode == "v2":
            v2_path = self.generate_v2_analysis(run, f"{base_name}_v2_analysis.md")
            result["v2_analysis"] = str(v2_path)

        return result

    def list_reports(self) -> list[dict]:
        """List all generated reports."""
        reports = []

        for json_file in sorted(self.output_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    reports.append({
                        "filename": json_file.name,
                        "run_id": data["meta"]["run_id"],
                        "name": data["meta"]["name"],
                        "dataset": data["meta"]["dataset"],
                        "created_at": data["meta"]["created_at"],
                        "exported_at": data["meta"]["exported_at"],
                        "correct_rate": data["summary"]["correct_rate"],
                    })
            except Exception:
                continue

        return reports

    def get_report(self, filename: str) -> Optional[dict]:
        """Get report content by filename."""
        filepath = self.output_dir / filename
        if not filepath.exists():
            return None

        if filename.endswith(".json"):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        elif filename.endswith(".md"):
            with open(filepath, "r", encoding="utf-8") as f:
                return {"content": f.read(), "type": "markdown"}

        return None
