"""Archive system for Lab benchmark results."""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import LabDB, Run, Result


class ArchiveManager:
    """Manages archiving and retrieval of benchmark results."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = str(Path(__file__).parent.parent.parent / "data" / "archive")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def archive_run(self, db: LabDB, run_id: int) -> dict:
        """
        Archive a completed run to filesystem.
        Returns: {"archive_path": str, "files": list[str]}
        """
        run = db.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        if run.status.value not in ("completed", "stopped", "paused", "failed"):
            raise ValueError(f"Run {run_id} is {run.status.value}, not completed")

        dataset_name = self._normalize_dataset_name(run.dataset)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"run_{run_id:03d}_{timestamp}"
        archive_path = self.base_dir / dataset_name / folder_name
        archive_path.mkdir(parents=True, exist_ok=True)

        files = []

        # 1. summary.json
        summary = self._build_summary(db, run)
        (archive_path / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        files.append("summary.json")

        # 2. config.json
        config = self._build_config(run)
        (archive_path / "config.json").write_text(
            json.dumps(config, indent=2), encoding="utf-8"
        )
        files.append("config.json")

        # 3. results.csv
        results = db.get_all_results(run_id)
        self._write_results_csv(archive_path / "results.csv", results)
        files.append("results.csv")

        # 4. report.md (optional)
        try:
            from .reports import ReportGenerator
            gen = ReportGenerator()
            report_md = gen.generate_markdown(run)
            import shutil
            if report_md.exists():
                shutil.copy2(report_md, archive_path / "report.md")
                files.append("report.md")
        except Exception:
            pass

        # 5. Update leaderboard
        self._update_leaderboard(dataset_name, run, summary, folder_name)

        return {
            "archive_path": str(archive_path),
            "folder_name": folder_name,
            "dataset": dataset_name,
            "files": files,
        }

    def get_leaderboard(self, dataset: str) -> dict:
        """Get leaderboard for a dataset."""
        dataset_name = self._normalize_dataset_name(dataset)
        lb_path = self.base_dir / dataset_name / "leaderboard.json"
        if not lb_path.exists():
            return {"dataset": dataset_name, "entries": []}
        return json.loads(lb_path.read_text(encoding="utf-8"))

    def list_archives(self, dataset: str) -> list[dict]:
        """List all archives for a dataset."""
        dataset_name = self._normalize_dataset_name(dataset)
        dataset_dir = self.base_dir / dataset_name
        if not dataset_dir.exists():
            return []

        archives = []
        for folder in sorted(dataset_dir.iterdir()):
            if folder.is_dir() and folder.name.startswith("run_"):
                summary_path = folder / "summary.json"
                if summary_path.exists():
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    archives.append({
                        "folder": folder.name,
                        "run_id": summary.get("run_id"),
                        "accuracy": summary.get("accuracy"),
                        "date": summary.get("timestamp"),
                        "total_questions": summary.get("total_questions"),
                    })
        return archives

    def get_archive_file(self, dataset: str, folder: str, filename: str) -> Optional[Path]:
        """Get path to specific file in archive."""
        dataset_name = self._normalize_dataset_name(dataset)
        file_path = self.base_dir / dataset_name / folder / filename
        if file_path.exists():
            return file_path
        return None

    def refresh_leaderboard(self, dataset: str) -> dict:
        """Rebuild leaderboard from all archives."""
        dataset_name = self._normalize_dataset_name(dataset)
        dataset_dir = self.base_dir / dataset_name
        if not dataset_dir.exists():
            return {"dataset": dataset_name, "entries": []}

        entries = []
        for folder in sorted(dataset_dir.iterdir()):
            if not folder.is_dir():
                continue
            summary_path = folder / "summary.json"
            if not summary_path.exists():
                continue
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            entries.append({
                "run_id": summary.get("run_id"),
                "model_version": summary.get("model_version", ""),
                "provider": summary.get("provider", ""),
                "accuracy": summary.get("accuracy", 0),
                "truthful_pct": summary.get("truthful_pct", 0),
                "informative_pct": summary.get("informative_pct", 0),
                "t_plus_i_pct": summary.get("truthful_and_informative_pct", 0),
                "total_questions": summary.get("total_questions", 0),
                "date": summary.get("timestamp", ""),
                "archive_folder": folder.name,
            })

        entries.sort(key=lambda e: e.get("accuracy", 0), reverse=True)

        leaderboard = {"dataset": dataset_name, "entries": entries}
        lb_path = dataset_dir / "leaderboard.json"
        lb_path.write_text(json.dumps(leaderboard, indent=2, ensure_ascii=False), encoding="utf-8")
        return leaderboard

    # === Private methods ===

    def _build_summary(self, db: LabDB, run: Run) -> dict:
        results = db.get_all_results(run.id)
        passed = [r for r in results if r.is_passed]
        failed = [r for r in results if not r.is_passed]
        fixed = [r for r in results if getattr(r, 'retry_status', None) == "fixed"]

        total = len(results) or 1
        total_time = sum(r.time_seconds for r in results)
        total_input = sum(r.input_tokens for r in results)
        total_output = sum(r.output_tokens for r in results)

        return {
            "run_id": run.id,
            "dataset": run.dataset,
            "model_version": getattr(run, 'model_version', ''),
            "provider": run.provider,
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "fixed": len(fixed),
            "accuracy": round(len(passed) / total * 100, 1),
            "avg_time_seconds": round(total_time / total, 1),
            "total_time_seconds": round(total_time, 1),
            "total_cost_usd": round(self._estimate_cost(total_input, total_output), 2),
            "total_tokens": {
                "input": total_input,
                "output": total_output,
            },
            "config": {
                "concurrency": run.concurrency,
                "num_steps": run.num_steps,
            }
        }

    def _build_config(self, run: Run) -> dict:
        return {
            "run_id": run.id,
            "name": run.name,
            "dataset": run.dataset,
            "total_questions": run.total_questions,
            "concurrency": run.concurrency,
            "source_run_id": getattr(run, 'source_run_id', None),
            "model_version": getattr(run, 'model_version', ''),
            "created_at": run.created_at,
        }

    def _write_results_csv(self, path: Path, results: list[Result]):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "question", "expected", "answer", "valid", "correct",
                "informative", "judge_reason", "failure_reason", "retry_status",
                "corrections", "time_seconds", "input_tokens", "output_tokens"
            ])
            for r in results:
                writer.writerow([
                    r.id, r.question, r.expected, r.answer, r.valid,
                    r.correct, r.informative,
                    r.judge_reason, r.failure_reason,
                    r.retry_status,
                    r.corrections, r.time_seconds,
                    r.input_tokens, r.output_tokens,
                ])

    def _update_leaderboard(self, dataset_name: str, run: Run, summary: dict, folder_name: str):
        lb = self.get_leaderboard(dataset_name)
        lb["entries"].append({
            "run_id": run.id,
            "model_version": summary.get("model_version", ""),
            "provider": summary.get("provider", ""),
            "accuracy": summary["accuracy"],
            "total_questions": summary["total_questions"],
            "date": summary["timestamp"],
            "archive_folder": folder_name,
        })
        lb["entries"].sort(key=lambda e: e.get("accuracy", 0), reverse=True)

        lb_path = self.base_dir / dataset_name / "leaderboard.json"
        lb_path.write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")

    def _normalize_dataset_name(self, name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
