"""
Paradigm-based instruction sets API router.

Endpoints:
    GET    /api/lab/paradigms                                    -> list[ParadigmInfo]
    GET    /api/lab/paradigms/{paradigm}/sets                    -> list[InstructionSetResponse]
    POST   /api/lab/paradigms/{paradigm}/sets                    -> InstructionSetResponse
    GET    /api/lab/paradigms/{paradigm}/sets/{set_id}           -> InstructionSetResponse
    PUT    /api/lab/paradigms/{paradigm}/sets/{set_id}           -> InstructionSetResponse
    DELETE /api/lab/paradigms/{paradigm}/sets/{set_id}           -> {"ok": true}
    POST   /api/lab/paradigms/{paradigm}/sets/{set_id}/default   -> InstructionSetResponse
    POST   /api/lab/paradigms/{paradigm}/sets/{set_id}/clone     -> InstructionSetResponse
    GET    /api/lab/paradigms/teams/{team_id}/config             -> TeamParadigmConfigResponse
    PUT    /api/lab/paradigms/teams/{team_id}/config             -> TeamParadigmConfigResponse
    PUT    /api/lab/paradigms/teams/{team_id}/config/{paradigm}  -> {"ok": true}
    DELETE /api/lab/paradigms/teams/{team_id}/config/{paradigm}  -> {"ok": true}
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB, ParadigmInstructionSet

router = APIRouter(prefix="/api/lab/paradigms", tags=["lab-paradigms"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARADIGMS = [
    {"id": "default", "name": "Default", "description": "Base instruction set for all paradigms"},
    {"id": "mathematical", "name": "Mathematical", "description": "Formal proofs, calculations, equations"},
    {"id": "logical", "name": "Logical", "description": "Deductive and inductive reasoning, syllogisms"},
    {"id": "causal", "name": "Causal", "description": "Cause-and-effect relationships, mechanisms"},
    {"id": "analogical", "name": "Analogical", "description": "Comparison-based reasoning, metaphors"},
    {"id": "spatial", "name": "Spatial", "description": "Geometric, topological, spatial relationships"},
    {"id": "temporal", "name": "Temporal", "description": "Time-based reasoning, sequences, scheduling"},
    {"id": "probabilistic", "name": "Probabilistic", "description": "Statistical reasoning, uncertainty, Bayesian"},
    {"id": "linguistic", "name": "Linguistic", "description": "Language structure, semantics, pragmatics"},
    {"id": "scientific", "name": "Scientific", "description": "Empirical reasoning, hypothesis testing"},
    {"id": "ethical", "name": "Ethical", "description": "Moral reasoning, value judgments, dilemmas"},
]

VALID_PARADIGM_IDS = {p["id"] for p in PARADIGMS}

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
# Pydantic schemas
# ---------------------------------------------------------------------------


class ParadigmInfo(BaseModel):
    id: str
    name: str
    description: str


class InstructionSetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(..., min_length=1, max_length=50)
    description: str = ""
    is_default: bool = False
    instructions: dict[str, str] = Field(default_factory=dict)


class InstructionSetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    version: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    instructions: Optional[dict[str, str]] = None


class InstructionSetResponse(BaseModel):
    id: str
    paradigm: str
    version: str
    name: str
    description: str
    is_default: bool
    created_at: str
    updated_at: str
    instructions: dict[str, str]


class CloneRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)


class TeamParadigmConfigResponse(BaseModel):
    team_id: str
    paradigm_sets: dict[str, str]


class TeamParadigmAssignment(BaseModel):
    instruction_set_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_paradigm(paradigm: str) -> None:
    if paradigm not in VALID_PARADIGM_IDS:
        raise lab_error(
            LabErrorCode.INSTRUCTION_SET_NOT_FOUND,
            status_code=400,
            id=f"paradigm '{paradigm}'",
        )


def _set_to_response(s: ParadigmInstructionSet) -> InstructionSetResponse:
    return InstructionSetResponse(
        id=s.id,
        paradigm=s.paradigm,
        version=s.version,
        name=s.name,
        description=s.description,
        is_default=s.is_default,
        created_at=s.created_at,
        updated_at=s.updated_at,
        instructions=s.instructions,
    )


# ---------------------------------------------------------------------------
# Paradigm & Instruction Set Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ParadigmInfo])
async def list_paradigms():
    """List all supported paradigms."""
    return [ParadigmInfo(**p) for p in PARADIGMS]


@router.get("/{paradigm}/sets", response_model=list[InstructionSetResponse])
async def list_instruction_sets(paradigm: str):
    """List instruction sets for a paradigm."""
    _validate_paradigm(paradigm)
    db = get_db()
    sets = db.list_instruction_sets(paradigm=paradigm)
    return [_set_to_response(s) for s in sets]


@router.post("/{paradigm}/sets", response_model=InstructionSetResponse, status_code=201)
async def create_instruction_set(paradigm: str, body: InstructionSetCreate):
    """Create a new instruction set for a paradigm."""
    _validate_paradigm(paradigm)
    db = get_db()

    s = ParadigmInstructionSet(
        paradigm=paradigm,
        version=body.version,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        instructions=body.instructions,
    )
    try:
        s = db.create_instruction_set(s)
    except sqlite3.IntegrityError:
        raise lab_error(
            LabErrorCode.PARADIGM_VERSION_CONFLICT,
            version=body.version,
            paradigm=paradigm,
        )

    if body.is_default:
        db.set_default_instruction_set(s.id)

    return _set_to_response(s)


@router.get("/{paradigm}/sets/{set_id}", response_model=InstructionSetResponse)
async def get_instruction_set(paradigm: str, set_id: str):
    """Get a specific instruction set."""
    _validate_paradigm(paradigm)
    db = get_db()
    s = db.get_instruction_set(set_id)
    if not s or s.paradigm != paradigm:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)
    return _set_to_response(s)


@router.put("/{paradigm}/sets/{set_id}", response_model=InstructionSetResponse)
async def update_instruction_set(paradigm: str, set_id: str, body: InstructionSetUpdate):
    """Update an existing instruction set."""
    _validate_paradigm(paradigm)
    db = get_db()
    s = db.get_instruction_set(set_id)
    if not s or s.paradigm != paradigm:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.is_default is not None:
        s.is_default = body.is_default
    if body.instructions is not None:
        s.instructions = body.instructions

    s = db.update_instruction_set(s)

    if body.is_default:
        db.set_default_instruction_set(s.id)

    return _set_to_response(s)


@router.delete("/{paradigm}/sets/{set_id}")
async def delete_instruction_set(paradigm: str, set_id: str):
    """Delete an instruction set."""
    _validate_paradigm(paradigm)
    db = get_db()
    deleted = db.delete_instruction_set(set_id)
    if not deleted:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)
    return {"ok": True}


@router.post("/{paradigm}/sets/{set_id}/default", response_model=InstructionSetResponse)
async def set_default_instruction_set(paradigm: str, set_id: str):
    """Set an instruction set as the default for its paradigm."""
    _validate_paradigm(paradigm)
    db = get_db()
    s = db.get_instruction_set(set_id)
    if not s or s.paradigm != paradigm:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    db.set_default_instruction_set(set_id)
    s = db.get_instruction_set(set_id)  # re-fetch
    return _set_to_response(s)


@router.post("/{paradigm}/sets/{set_id}/clone", response_model=InstructionSetResponse, status_code=201)
async def clone_instruction_set(paradigm: str, set_id: str, body: CloneRequest):
    """Clone an instruction set with a new version and name."""
    _validate_paradigm(paradigm)
    db = get_db()
    s = db.get_instruction_set(set_id)
    if not s or s.paradigm != paradigm:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    try:
        clone = db.clone_instruction_set(set_id, body.version, body.name)
    except sqlite3.IntegrityError:
        raise lab_error(
            LabErrorCode.PARADIGM_VERSION_CONFLICT,
            version=body.version,
            paradigm=paradigm,
        )
    if not clone:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)
    return _set_to_response(clone)


# ---------------------------------------------------------------------------
# Team Paradigm Config Endpoints
# ---------------------------------------------------------------------------


@router.get("/teams/{team_id}/config", response_model=TeamParadigmConfigResponse)
async def get_team_paradigm_config(team_id: str):
    """Get paradigm instruction set assignments for a team."""
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)

    configs = db.get_team_paradigm_configs(team_id)
    return TeamParadigmConfigResponse(team_id=team_id, paradigm_sets=configs)


@router.put("/teams/{team_id}/config", response_model=TeamParadigmConfigResponse)
async def update_team_paradigm_config(team_id: str, body: dict[str, str]):
    """Bulk set paradigm configs for a team (replaces all)."""
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)

    # Validate all paradigms and set IDs
    for paradigm, set_id in body.items():
        if paradigm not in VALID_PARADIGM_IDS:
            raise lab_error(
                LabErrorCode.INSTRUCTION_SET_NOT_FOUND,
                status_code=400,
                id=f"paradigm '{paradigm}'",
            )
        s = db.get_instruction_set(set_id)
        if not s:
            raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    db.set_team_paradigm_configs(team_id, body)
    configs = db.get_team_paradigm_configs(team_id)
    return TeamParadigmConfigResponse(team_id=team_id, paradigm_sets=configs)


@router.put("/teams/{team_id}/config/{paradigm}")
async def set_team_paradigm_single(team_id: str, paradigm: str, body: TeamParadigmAssignment):
    """Set a single paradigm config for a team."""
    _validate_paradigm(paradigm)
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)

    s = db.get_instruction_set(body.instruction_set_id)
    if not s:
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=body.instruction_set_id)

    db.set_team_paradigm_config(team_id, paradigm, body.instruction_set_id)
    return {"ok": True}


@router.delete("/teams/{team_id}/config/{paradigm}")
async def delete_team_paradigm_single(team_id: str, paradigm: str):
    """Remove a single paradigm config from a team."""
    _validate_paradigm(paradigm)
    db = get_db()
    db.delete_team_paradigm_config(team_id, paradigm)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Paradigm Role Instructions (file-based instruction set selection)
# ---------------------------------------------------------------------------


@router.get("/{paradigm}/role-instructions")
async def get_paradigm_role_instructions(paradigm: str):
    """Get per-role instruction set folder selection for a paradigm."""
    _validate_paradigm(paradigm)
    db = get_db()
    configs = db.get_paradigm_role_instructions(paradigm)
    return configs


@router.put("/{paradigm}/role-instructions")
async def update_paradigm_role_instructions(paradigm: str, body: dict[str, str]):
    """Save per-role instruction set folder selection for a paradigm."""
    _validate_paradigm(paradigm)
    db = get_db()
    db.set_paradigm_role_instructions(paradigm, body)
    return body
