"""
Test Configs CRUD API router.

Endpoints:
    GET    /api/lab/tests              -> list[TestConfigResponse]
    POST   /api/lab/tests              -> TestConfigResponse
    GET    /api/lab/tests/{id}         -> TestConfigResponse
    PUT    /api/lab/tests/{id}         -> TestConfigResponse
    DELETE /api/lab/tests/{id}         -> {"ok": true}
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB, TestConfig

router = APIRouter(prefix="/api/lab/tests", tags=["lab-tests"])

# ---------------------------------------------------------------------------
# Singleton DB instance (shared with teams router)
# ---------------------------------------------------------------------------

_db: LabNewDB | None = None


def get_db() -> LabNewDB:
    global _db
    if _db is None:
        _db = LabNewDB()
    return _db


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class JudgeConfigSchema(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    instructions: str = ""
    strict_mode: bool = False
    show_correct_answer: bool = False


class TestConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    benchmark: str = Field(default="bbeh")
    domains: list[str] = Field(default_factory=list)
    domain_limits: dict[str, int] = Field(default_factory=dict)
    question_count: Optional[int] = Field(default=None, ge=1, le=10000)
    question_ids: list[str] = Field(default_factory=list)
    shuffle: bool = False
    questions_per_team: int = Field(default=4, ge=1, le=100)
    steps_count: int = Field(default=1, ge=1, le=1000)
    team_id: str = ""
    auto_rotate_teams: bool = True
    judge_config: JudgeConfigSchema = Field(default_factory=JudgeConfigSchema)


class TestConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    benchmark: Optional[str] = None
    domains: Optional[list[str]] = None
    domain_limits: Optional[dict[str, int]] = None
    question_count: Optional[int] = Field(default=None, ge=1, le=10000)
    question_ids: Optional[list[str]] = None
    shuffle: Optional[bool] = None
    questions_per_team: Optional[int] = Field(default=None, ge=1, le=100)
    steps_count: Optional[int] = Field(default=None, ge=1, le=1000)
    team_id: Optional[str] = None
    auto_rotate_teams: Optional[bool] = None
    judge_config: Optional[JudgeConfigSchema] = None


class TestConfigResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    benchmark: str
    domains: list[str]
    domain_limits: dict[str, int]
    question_count: Optional[int]
    question_ids: list[str]
    shuffle: bool
    questions_per_team: int
    steps_count: int
    team_id: str
    auto_rotate_teams: bool
    judge_config: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg_to_response(cfg: TestConfig) -> TestConfigResponse:
    return TestConfigResponse(
        id=cfg.id,
        name=cfg.name,
        description=cfg.description,
        created_at=cfg.created_at,
        benchmark=cfg.benchmark,
        domains=cfg.domains,
        domain_limits=cfg.domain_limits,
        question_count=cfg.question_count,
        question_ids=cfg.question_ids,
        shuffle=cfg.shuffle,
        questions_per_team=cfg.questions_per_team,
        steps_count=cfg.steps_count,
        team_id=cfg.team_id,
        auto_rotate_teams=cfg.auto_rotate_teams,
        judge_config=cfg.judge_config,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TestConfigResponse])
async def list_test_configs():
    """List all test configurations."""
    db = get_db()
    configs = db.list_test_configs()
    return [_cfg_to_response(c) for c in configs]


@router.post("", response_model=TestConfigResponse, status_code=201)
async def create_test_config(body: TestConfigCreate):
    """Create a new test configuration."""
    db = get_db()

    # Validate team exists if specified
    if body.team_id:
        team = db.get_team(body.team_id)
        if not team:
            raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=body.team_id)

    # Validate benchmark exists
    try:
        from regulus.data.bbeh import get_loader
        get_loader(body.benchmark)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, detail=body.benchmark)

    # Validate domains if specified
    if body.domains:
        from regulus.data.bbeh import get_loader
        loader = get_loader(body.benchmark)
        valid_domains = set(loader.info().domains)
        invalid = [d for d in body.domains if d not in valid_domains]
        if invalid:
            raise lab_error(
                LabErrorCode.INVALID_QUESTION_RANGE,
                detail=f"Invalid domains for {body.benchmark}: {invalid}",
            )

    cfg = TestConfig(
        name=body.name,
        description=body.description,
        benchmark=body.benchmark,
        domains=body.domains,
        domain_limits=body.domain_limits,
        question_count=body.question_count,
        question_ids=body.question_ids,
        shuffle=body.shuffle,
        questions_per_team=body.questions_per_team,
        steps_count=body.steps_count,
        team_id=body.team_id,
        auto_rotate_teams=body.auto_rotate_teams,
        judge_config=body.judge_config.model_dump(),
    )
    cfg = db.create_test_config(cfg)
    return _cfg_to_response(cfg)


@router.get("/{config_id}", response_model=TestConfigResponse)
async def get_test_config(config_id: str):
    """Get test configuration by ID."""
    db = get_db()
    cfg = db.get_test_config(config_id)
    if not cfg:
        raise lab_error(LabErrorCode.CONFIG_NOT_FOUND, id=config_id)
    return _cfg_to_response(cfg)


@router.put("/{config_id}", response_model=TestConfigResponse)
async def update_test_config(config_id: str, body: TestConfigUpdate):
    """Update an existing test configuration."""
    db = get_db()
    cfg = db.get_test_config(config_id)
    if not cfg:
        raise lab_error(LabErrorCode.CONFIG_NOT_FOUND, id=config_id)

    if body.name is not None:
        cfg.name = body.name
    if body.description is not None:
        cfg.description = body.description
    if body.benchmark is not None:
        cfg.benchmark = body.benchmark
    if body.domains is not None:
        cfg.domains = body.domains
    if body.domain_limits is not None:
        cfg.domain_limits = body.domain_limits
    if body.question_count is not None:
        cfg.question_count = body.question_count
    if body.question_ids is not None:
        cfg.question_ids = body.question_ids
    if body.shuffle is not None:
        cfg.shuffle = body.shuffle
    if body.questions_per_team is not None:
        cfg.questions_per_team = body.questions_per_team
    if body.steps_count is not None:
        cfg.steps_count = body.steps_count
    if body.team_id is not None:
        cfg.team_id = body.team_id
    if body.auto_rotate_teams is not None:
        cfg.auto_rotate_teams = body.auto_rotate_teams
    if body.judge_config is not None:
        cfg.judge_config = body.judge_config.model_dump()

    cfg = db.update_test_config(cfg)
    return _cfg_to_response(cfg)


@router.delete("/{config_id}")
async def delete_test_config(config_id: str):
    """Delete a test configuration."""
    db = get_db()
    deleted = db.delete_test_config(config_id)
    if not deleted:
        raise lab_error(LabErrorCode.CONFIG_NOT_FOUND, id=config_id)
    return {"ok": True}
