"""Structured error codes for Lab API (LAB_001–LAB_010).

Each error has a code, default HTTP status, and message template.
Use `lab_error()` to raise an HTTPException with a structured detail body.
"""

from __future__ import annotations

from fastapi import HTTPException


# ── Error code definitions ────────────────────────────────────────────

class LabErrorCode:
    CONFIG_NOT_FOUND = "LAB_001"
    TEAM_NOT_FOUND = "LAB_002"
    BENCHMARK_LOAD_FAILED = "LAB_003"
    LLM_API_ERROR = "LAB_004"
    JUDGE_EVAL_FAILED = "LAB_005"
    STREAM_CONNECTION_LOST = "LAB_006"
    TEST_ALREADY_RUNNING = "LAB_007"
    INVALID_QUESTION_RANGE = "LAB_008"
    RATE_LIMIT_EXCEEDED = "LAB_009"
    DATABASE_ERROR = "LAB_010"
    RUN_NOT_FOUND = "LAB_011"
    INVALID_RUN_STATUS = "LAB_012"
    INSTRUCTION_SET_NOT_FOUND = "LAB_013"
    PARADIGM_VERSION_CONFLICT = "LAB_014"
    BENCHMARK_NOT_INDEXED = "LAB_015"
    PARADIGM_CONFIG_NOT_FOUND = "LAB_016"
    ANALYSIS_NOT_FOUND = "LAB_017"


_DEFAULTS: dict[str, tuple[int, str]] = {
    "LAB_001": (404, "Test config {id} not found"),
    "LAB_002": (404, "Team {id} not found"),
    "LAB_003": (400, "Failed to load benchmark: {detail}"),
    "LAB_004": (502, "LLM API error: {detail}"),
    "LAB_005": (500, "Judge evaluation failed: {detail}"),
    "LAB_006": (500, "Stream connection lost"),
    "LAB_007": (409, "Test is already running (status: {status})"),
    "LAB_008": (400, "Invalid question range: {detail}"),
    "LAB_009": (429, "Rate limit exceeded"),
    "LAB_010": (500, "Database error: {detail}"),
    "LAB_011": (404, "Run {id} not found"),
    "LAB_012": (400, "Invalid run status: expected {expected}, got {actual}"),
    "LAB_013": (404, "Instruction set {id} not found"),
    "LAB_014": (409, "Version {version} already exists for paradigm {paradigm}"),
    "LAB_015": (400, "Benchmark {id} is not indexed"),
    "LAB_016": (404, "Paradigm config {id} not found"),
    "LAB_017": (404, "Analysis for result {id} not found"),
}


# ── Helper ────────────────────────────────────────────────────────────

def lab_error(
    code: str,
    status_code: int | None = None,
    **kwargs: str,
) -> HTTPException:
    """Create an HTTPException with structured error detail.

    Returns (not raises) so callers can `raise lab_error(...)`.

    The response body will be:
        {"code": "LAB_001", "message": "Test config abc not found"}
    """
    default_status, template = _DEFAULTS.get(code, (500, code))
    message = template.format(**kwargs) if kwargs else template
    return HTTPException(
        status_code=status_code or default_status,
        detail={"code": code, "message": message},
    )
