"""Report generation for Lab runs."""

import json
from datetime import datetime
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
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"run_{run.id}_{timestamp}.json"

        filepath = self.output_dir / filename

        report = {
            "meta": {
                "run_id": run.id,
                "name": run.name,
                "dataset": run.dataset,
                "provider": run.provider,
                "created_at": run.created_at,
                "exported_at": datetime.utcnow().isoformat(),
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
                report["results"].append({
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
                })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return filepath

    def generate_markdown(self, run: Run, filename: Optional[str] = None) -> Path:
        """Generate Markdown report."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
        lines.append(f"*Generated by RegulusAI Lab on {datetime.utcnow().isoformat()}*")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    def export(self, run: Run) -> dict:
        """Export both JSON and Markdown reports."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"run_{run.id}_{timestamp}"

        json_path = self.generate_json(run, f"{base_name}.json")
        md_path = self.generate_markdown(run, f"{base_name}.md")

        return {
            "json": str(json_path),
            "markdown": str(md_path),
        }

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
