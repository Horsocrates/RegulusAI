"""
Paradigm Configuration API router — question classification paradigms with
per-role models, signals, and subprocess agents.

Endpoints:
    GET    /api/lab/paradigm-config                -> list[ParadigmConfigResponse]
    GET    /api/lab/paradigm-config/{id}           -> ParadigmConfigResponse
    PUT    /api/lab/paradigm-config/{id}           -> ParadigmConfigResponse
    POST   /api/lab/paradigm-config/seed           -> {"seeded": int}
    DELETE /api/lab/paradigm-config/{id}           -> {"ok": true}
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from regulus.api.models.lab import LabNewDB, ParadigmConfig

router = APIRouter(prefix="/api/lab/paradigm-config", tags=["lab-paradigm-config"])

# ---------------------------------------------------------------------------
# Default paradigm configs (seeded on first use)
# ---------------------------------------------------------------------------

DEFAULT_PARADIGM_CONFIGS = [
    {
        "id": "base",
        "name": "BASE",
        "label": "Default",
        "color": "#64748b",
        "description": "Standard D1-D6 pipeline. No special mechanisms.",
        "signals": ["Interdisciplinary", "Novel/unusual", "Qualitative answer", "Low classification confidence"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": [],
    },
    {
        "id": "compute",
        "name": "COMPUTE",
        "label": "Computation",
        "color": "#3b82f6",
        "description": "Exact numerical value, expression, or formula.",
        "signals": ["Calculate", "Find the value", "What is [number]", "Evaluate", "Solve for"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["dual_solver"],
    },
    {
        "id": "multi_verify",
        "name": "MULTI-VERIFY",
        "label": "Multi-Statement",
        "color": "#8b5cf6",
        "description": "Check which statements are true/false from a set.",
        "signals": ["Which statements are true", "Which of I-VI", "Select all that apply"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["consistency"],
    },
    {
        "id": "mc_eliminate",
        "name": "MC-ELIMINATE",
        "label": "Multiple Choice",
        "color": "#ef4444",
        "description": "Choose A/B/C/D with adversarial verification.",
        "signals": ["Choose A/B/C/D", "Which of the following", "Select the correct answer"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["re_reader", "adversarial"],
    },
    {
        "id": "enumerate",
        "name": "ENUMERATE",
        "label": "Enumeration",
        "color": "#f59e0b",
        "description": "Find/list/count ALL elements satisfying a condition.",
        "signals": ["List all", "How many satisfy", "Find all", "Count the number"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["dual_solver", "exhaustive"],
    },
    {
        "id": "code_trace",
        "name": "CODE-TRACE",
        "label": "Code Analysis",
        "color": "#10b981",
        "description": "Analyze program behavior. Execute first, reason second.",
        "signals": ["What does this program output", "code", "function returns", "trace"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["executor"],
    },
    {
        "id": "fact_deep",
        "name": "FACT-DEEP",
        "label": "Deep Factual",
        "color": "#ec4899",
        "description": "Obscure factual claim requiring sourced verification.",
        "signals": ["Who said", "In which year", "Name the", "What [specific entity] did"],
        "active_roles": ["team_lead", "d1", "d2", "d3", "d4", "d5", "d6"],
        "active_subprocesses": ["searcher"],
    },
]

# ---------------------------------------------------------------------------
# DB singleton
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


class ParadigmConfigUpdate(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    signals: Optional[list[str]] = None
    active_roles: Optional[list[str]] = None
    active_subprocesses: Optional[list[str]] = None
    role_models: Optional[dict[str, str]] = None
    role_instructions: Optional[dict[str, str]] = None
    instruction_set_id: Optional[str] = None


class ParadigmConfigResponse(BaseModel):
    id: str
    name: str
    label: str
    color: str
    description: str
    signals: list[str]
    active_roles: list[str]
    active_subprocesses: list[str]
    role_models: dict[str, str]
    role_instructions: dict[str, str]
    instruction_set_id: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg_to_response(cfg: ParadigmConfig) -> ParadigmConfigResponse:
    return ParadigmConfigResponse(
        id=cfg.id,
        name=cfg.name,
        label=cfg.label,
        color=cfg.color,
        description=cfg.description,
        signals=cfg.signals,
        active_roles=cfg.active_roles,
        active_subprocesses=cfg.active_subprocesses,
        role_models=cfg.role_models,
        role_instructions=cfg.role_instructions,
        instruction_set_id=cfg.instruction_set_id,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ParadigmConfigResponse])
async def list_paradigm_configs():
    """List all paradigm configurations. Seeds defaults if empty."""
    db = get_db()
    configs = db.list_paradigm_configs()
    if not configs:
        db.seed_default_paradigm_configs()
        configs = db.list_paradigm_configs()
    return [_cfg_to_response(c) for c in configs]


@router.get("/{config_id}", response_model=ParadigmConfigResponse)
async def get_paradigm_config(config_id: str):
    """Get a single paradigm configuration."""
    db = get_db()
    cfg = db.get_paradigm_config(config_id)
    if not cfg:
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.PARADIGM_CONFIG_NOT_FOUND, id=config_id)
    return _cfg_to_response(cfg)


@router.put("/{config_id}", response_model=ParadigmConfigResponse)
async def update_paradigm_config(config_id: str, body: ParadigmConfigUpdate):
    """Update a paradigm configuration (partial update)."""
    db = get_db()
    cfg = db.get_paradigm_config(config_id)
    if not cfg:
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.PARADIGM_CONFIG_NOT_FOUND, id=config_id)

    if body.name is not None:
        cfg.name = body.name
    if body.label is not None:
        cfg.label = body.label
    if body.color is not None:
        cfg.color = body.color
    if body.description is not None:
        cfg.description = body.description
    if body.signals is not None:
        cfg.signals = body.signals
    if body.active_roles is not None:
        cfg.active_roles = body.active_roles
    if body.active_subprocesses is not None:
        cfg.active_subprocesses = body.active_subprocesses
    if body.role_models is not None:
        cfg.role_models = body.role_models
    if body.role_instructions is not None:
        cfg.role_instructions = body.role_instructions
    if body.instruction_set_id is not None:
        cfg.instruction_set_id = body.instruction_set_id

    cfg = db.upsert_paradigm_config(cfg)
    return _cfg_to_response(cfg)


@router.post("/seed")
async def seed_paradigm_configs():
    """Seed default paradigm configs (idempotent — only if table is empty)."""
    db = get_db()
    count = db.seed_default_paradigm_configs()
    return {"seeded": count}


@router.delete("/{config_id}")
async def delete_paradigm_config(config_id: str):
    """Delete a paradigm configuration."""
    db = get_db()
    deleted = db.delete_paradigm_config(config_id)
    if not deleted:
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.PARADIGM_CONFIG_NOT_FOUND, id=config_id)
    return {"ok": True}
