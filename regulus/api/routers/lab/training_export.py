"""
Training Data Export API router.

Endpoints:
    GET /api/lab/v2/export/training-data   -> JSONL/CSV/JSON export for fine-tuning
    GET /api/lab/v2/export/training-stats  -> Training data readiness stats
"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from regulus.api.models.lab import LabNewDB

router = APIRouter(tags=["lab-training-export"])

# ---------------------------------------------------------------------------
# Singleton DB instance
# ---------------------------------------------------------------------------

_db: LabNewDB | None = None


def get_db() -> LabNewDB:
    global _db
    if _db is None:
        _db = LabNewDB()
    return _db


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/lab/v2/export/training-stats")
async def get_training_stats():
    """Get training data readiness statistics."""
    db = get_db()
    return db.get_training_stats()


@router.get("/api/lab/v2/export/training-data")
async def export_training_data(
    format: str = Query(default="jsonl", pattern="^(jsonl|csv|json)$"),
    domain: Optional[str] = Query(default=None),
    skill_type: Optional[str] = Query(default=None),
    verdict: Optional[str] = Query(default=None, pattern="^(correct|wrong|all)$"),
    run_id: Optional[str] = Query(default=None),
    include_thinking: bool = Query(default=True),
    include_domain_outputs: bool = Query(default=True),
    limit: int = Query(default=10000, ge=1, le=100000),
):
    """Export training data in JSONL, CSV, or JSON format.

    JSONL: One JSON object per line, OpenAI fine-tuning compatible.
    CSV: Flat with d1_weight..d6_weight, d1_gate..d6_gate columns.
    JSON: Full nested structure with export metadata.
    """
    db = get_db()

    # Build filters
    verdict_filter = verdict if verdict and verdict != "all" else None
    results = db.list_all_results(
        verdict=verdict_filter,
        domain=domain,
        run_id=run_id,
        skill_type=skill_type,
        limit=limit,
        offset=0,
    )

    # Filter to only results with agent_outputs (training-ready)
    results = [r for r in results if r.agent_outputs and r.agent_outputs != {}]

    if format == "jsonl":
        return _export_jsonl(results, db, include_thinking, include_domain_outputs)
    elif format == "csv":
        return _export_training_csv(results, db, include_domain_outputs)
    else:
        return _export_training_json(results, db, include_thinking, include_domain_outputs)


# ---------------------------------------------------------------------------
# Export formatters
# ---------------------------------------------------------------------------


def _export_jsonl(results, db, include_thinking, include_domain_outputs):
    """JSONL format for OpenAI/DeepSeek fine-tuning."""

    def generate():
        for r in results:
            # Build assistant content: reasoning trace + answer
            thinking = ""
            if include_thinking and r.agent_outputs.get("thinking"):
                thinking = r.agent_outputs["thinking"]

            assistant_content = ""
            if thinking:
                assistant_content += f"<thinking>\n{thinking}\n</thinking>\n\n"
            assistant_content += r.final_answer or ""

            record = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a careful reasoning assistant. Think step by step.",
                    },
                    {"role": "user", "content": r.input_text},
                    {"role": "assistant", "content": assistant_content},
                ],
                "metadata": {
                    "question_id": r.question_id,
                    "domain": r.domain,
                    "verdict": r.judgment_verdict,
                    "correct_answer": r.correct_answer,
                    "skill_type": r.skill_type,
                    "pipeline": r.agent_outputs.get("pipeline", ""),
                    "reasoning_model": r.agent_outputs.get("reasoning_model", ""),
                },
            }

            if include_domain_outputs:
                domains = r.agent_outputs.get("domains", {})
                if domains:
                    record["metadata"]["domains"] = {
                        d: {"weight": v.get("weight", 0), "gate_passed": v.get("gate_passed", False)}
                        for d, v in domains.items()
                    }

            yield json.dumps(record, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="training_data.jsonl"',
        },
    )


def _export_training_csv(results, db, include_domain_outputs):
    """Flat CSV with d1_weight..d6_weight, d1_gate..d6_gate columns."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = [
        "question_id", "domain", "skill_type", "input_text",
        "final_answer", "correct_answer", "verdict",
        "pipeline", "reasoning_model",
        "total_time_ms", "total_tokens_in", "total_tokens_out", "estimated_cost",
    ]
    if include_domain_outputs:
        for d in ["D1", "D2", "D3", "D4", "D5", "D6"]:
            header.extend([f"{d.lower()}_weight", f"{d.lower()}_gate"])
    writer.writerow(header)

    for r in results:
        domains = r.agent_outputs.get("domains", {}) if r.agent_outputs else {}
        row = [
            r.question_id,
            r.domain,
            r.skill_type or "",
            r.input_text,
            r.final_answer or "",
            r.correct_answer or "",
            r.judgment_verdict or "",
            r.agent_outputs.get("pipeline", "") if r.agent_outputs else "",
            r.agent_outputs.get("reasoning_model", "") if r.agent_outputs else "",
            r.total_time_ms,
            r.total_tokens_in,
            r.total_tokens_out,
            r.estimated_cost,
        ]
        if include_domain_outputs:
            for d in ["D1", "D2", "D3", "D4", "D5", "D6"]:
                d_data = domains.get(d, {})
                row.extend([
                    d_data.get("weight", 0) if d_data else 0,
                    int(d_data.get("gate_passed", False)) if d_data else 0,
                ])
        writer.writerow(row)

    content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="training_data.csv"',
        },
    )


def _export_training_json(results, db, include_thinking, include_domain_outputs):
    """Full nested JSON with export metadata."""
    items = []
    for r in results:
        item = {
            "question_id": r.question_id,
            "domain": r.domain,
            "skill_type": r.skill_type,
            "input_text": r.input_text,
            "final_answer": r.final_answer,
            "correct_answer": r.correct_answer,
            "verdict": r.judgment_verdict,
            "confidence": r.judgment_confidence,
            "pipeline": r.agent_outputs.get("pipeline", "") if r.agent_outputs else "",
            "reasoning_model": r.agent_outputs.get("reasoning_model", "") if r.agent_outputs else "",
            "total_time_ms": r.total_time_ms,
            "total_tokens_in": r.total_tokens_in,
            "total_tokens_out": r.total_tokens_out,
            "estimated_cost": r.estimated_cost,
        }

        if include_thinking and r.agent_outputs and r.agent_outputs.get("thinking"):
            item["thinking"] = r.agent_outputs["thinking"]

        if include_domain_outputs and r.agent_outputs:
            item["domains"] = r.agent_outputs.get("domains", {})

        items.append(item)

    data = {
        "export_format": "training_data",
        "version": "1.0",
        "total_records": len(items),
        "records": items,
    }

    content = json.dumps(data, indent=2, ensure_ascii=False)

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="training_data.json"',
        },
    )
