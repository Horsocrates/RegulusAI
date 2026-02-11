"""
Model Settings API router — per-paradigm/role model configuration
(thinking budget, context window, max tokens, interleaved thinking).

Endpoints:
    GET    /api/lab/model-settings              -> list saved settings
    GET    /api/lab/model-settings/resolve       -> cascade-resolve for given scope
    PUT    /api/lab/model-settings              -> upsert settings
    DELETE /api/lab/model-settings/{id}         -> delete override
    GET    /api/lab/model-settings/limits       -> MODEL_LIMITS (static)
    GET    /api/lab/model-settings/defaults     -> MODEL_DEFAULTS (static)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from regulus.api.models.lab import (
    LabNewDB, ModelSettings, MODEL_DEFAULTS, MODEL_LIMITS,
)

router = APIRouter(prefix="/api/lab/model-settings", tags=["lab-model-settings"])

_db: LabNewDB | None = None


def _get_db() -> LabNewDB:
    global _db
    if _db is None:
        _db = LabNewDB()
    return _db


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ModelSettingsUpsert(BaseModel):
    paradigm_id: str = ""
    role_id: str = ""
    model_id: str
    context_window: Optional[int] = None
    max_tokens: Optional[int] = None
    thinking_enabled: Optional[bool] = None
    thinking_budget: Optional[int] = None
    interleaved_thinking: Optional[bool] = None
    temperature: Optional[float] = None


class ModelSettingsResponse(BaseModel):
    id: str
    paradigm_id: str
    role_id: str
    model_id: str
    context_window: int
    max_tokens: int
    thinking_enabled: bool
    thinking_budget: int
    interleaved_thinking: bool
    temperature: float
    created_at: str
    updated_at: str


class ResolvedSettingsResponse(BaseModel):
    context_window: int
    max_tokens: int
    thinking_enabled: bool
    thinking_budget: int
    interleaved_thinking: bool
    temperature: float
    resolved_from: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/limits")
async def get_limits():
    """Return static MODEL_LIMITS (hardware caps & pricing per model)."""
    return MODEL_LIMITS


@router.get("/defaults")
async def get_defaults():
    """Return static MODEL_DEFAULTS (factory default settings per model)."""
    return MODEL_DEFAULTS


@router.get("/resolve", response_model=ResolvedSettingsResponse)
async def resolve_settings(
    paradigm_id: str = Query(default="", description="Paradigm scope"),
    role_id: str = Query(default="", description="Role scope"),
    model_id: str = Query(..., description="Model ID"),
):
    """Cascade-resolve settings: paradigm+role → paradigm → global → defaults."""
    db = _get_db()
    resolved = db.resolve_model_settings(paradigm_id, role_id, model_id)
    return resolved


@router.get("", response_model=list[ModelSettingsResponse])
async def list_settings(
    paradigm_id: Optional[str] = Query(default=None),
    model_id: Optional[str] = Query(default=None),
):
    """List saved model settings with optional filters."""
    db = _get_db()
    items = db.list_model_settings(paradigm_id=paradigm_id, model_id=model_id)
    return [_to_response(s) for s in items]


@router.put("", response_model=ModelSettingsResponse)
async def upsert_settings(body: ModelSettingsUpsert):
    """Upsert model settings at a given scope (paradigm+role+model)."""
    db = _get_db()
    limits = MODEL_LIMITS.get(body.model_id)
    defaults = MODEL_DEFAULTS.get(body.model_id, {})

    # Build ModelSettings, merging provided values with defaults
    s = ModelSettings(
        paradigm_id=body.paradigm_id,
        role_id=body.role_id,
        model_id=body.model_id,
        context_window=body.context_window if body.context_window is not None else defaults.get("context_window", 0),
        max_tokens=body.max_tokens if body.max_tokens is not None else defaults.get("max_tokens", 0),
        thinking_enabled=body.thinking_enabled if body.thinking_enabled is not None else defaults.get("thinking_enabled", True),
        thinking_budget=body.thinking_budget if body.thinking_budget is not None else defaults.get("thinking_budget", 0),
        interleaved_thinking=body.interleaved_thinking if body.interleaved_thinking is not None else defaults.get("interleaved_thinking", False),
        temperature=body.temperature if body.temperature is not None else defaults.get("temperature", 1.0),
    )

    # Check if an existing row exists for this unique key
    existing = db.get_model_settings(s.paradigm_id, s.role_id, s.model_id)
    if existing:
        s.id = existing.id
        s.created_at = existing.created_at

    # Validation
    if limits:
        if s.max_tokens > limits["maxOutput"]:
            raise HTTPException(
                status_code=422,
                detail=f"max_tokens ({s.max_tokens}) exceeds model limit ({limits['maxOutput']})",
            )
        if s.context_window > limits["maxContext"]:
            raise HTTPException(
                status_code=422,
                detail=f"context_window ({s.context_window}) exceeds model limit ({limits['maxContext']})",
            )
    if s.thinking_enabled and s.thinking_budget > 0 and s.thinking_budget < 1024:
        raise HTTPException(
            status_code=422,
            detail=f"thinking_budget ({s.thinking_budget}) must be >= 1024 when thinking is enabled",
        )
    if s.thinking_enabled and not s.interleaved_thinking and s.thinking_budget >= s.max_tokens:
        raise HTTPException(
            status_code=422,
            detail=f"thinking_budget ({s.thinking_budget}) must be < max_tokens ({s.max_tokens}) unless interleaved thinking is enabled",
        )

    saved = db.upsert_model_settings(s)
    return _to_response(saved)


@router.delete("/{settings_id}")
async def delete_settings(settings_id: str):
    """Delete a model settings override."""
    db = _get_db()
    deleted = db.delete_model_settings(settings_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Settings not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(s: ModelSettings) -> ModelSettingsResponse:
    return ModelSettingsResponse(
        id=s.id,
        paradigm_id=s.paradigm_id,
        role_id=s.role_id,
        model_id=s.model_id,
        context_window=s.context_window,
        max_tokens=s.max_tokens,
        thinking_enabled=s.thinking_enabled,
        thinking_budget=s.thinking_budget,
        interleaved_thinking=s.interleaved_thinking,
        temperature=s.temperature,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )
