"""
Teams CRUD API router.

Endpoints:
    GET    /api/lab/teams              -> list[TeamResponse]
    POST   /api/lab/teams              -> TeamResponse
    GET    /api/lab/teams/{id}         -> TeamResponse
    PUT    /api/lab/teams/{id}         -> TeamResponse
    DELETE /api/lab/teams/{id}         -> {"ok": true}
    POST   /api/lab/teams/{id}/default -> TeamResponse
    POST   /api/lab/teams/{id}/clone   -> TeamResponse
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB, Team

router = APIRouter(prefix="/api/lab/teams", tags=["lab-teams"])

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


class AgentConfigSchema(BaseModel):
    model: str = "gpt-4o-mini"
    instructions: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=64000, ge=1, le=128000)
    enabled: bool = True


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    is_default: bool = False
    team_lead_config: AgentConfigSchema = Field(default_factory=AgentConfigSchema)
    agents: dict[str, AgentConfigSchema] = Field(default_factory=dict)


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_default: Optional[bool] = None
    team_lead_config: Optional[AgentConfigSchema] = None
    agents: Optional[dict[str, AgentConfigSchema]] = None


class CloneRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str
    is_default: bool
    created_at: str
    updated_at: str
    team_lead_config: dict
    agent_configs: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _team_to_response(team: Team) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        is_default=team.is_default,
        created_at=team.created_at,
        updated_at=team.updated_at,
        team_lead_config=team.team_lead_config,
        agent_configs=team.agent_configs,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TeamResponse])
async def list_teams():
    """List all teams."""
    db = get_db()
    teams = db.list_teams()
    return [_team_to_response(t) for t in teams]


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(body: TeamCreate):
    """Create a new team."""
    db = get_db()
    team = Team(
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        team_lead_config=body.team_lead_config.model_dump(),
        agent_configs={k: v.model_dump() for k, v in body.agents.items()},
    )
    team = db.create_team(team)

    if body.is_default:
        db.set_default_team(team.id)

    return _team_to_response(team)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: str):
    """Get team by ID."""
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)
    return _team_to_response(team)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(team_id: str, body: TeamUpdate):
    """Update an existing team."""
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)

    if body.name is not None:
        team.name = body.name
    if body.description is not None:
        team.description = body.description
    if body.is_default is not None:
        team.is_default = body.is_default
    if body.team_lead_config is not None:
        team.team_lead_config = body.team_lead_config.model_dump()
    if body.agents is not None:
        team.agent_configs = {k: v.model_dump() for k, v in body.agents.items()}

    team = db.update_team(team)

    if body.is_default:
        db.set_default_team(team.id)

    return _team_to_response(team)


@router.delete("/{team_id}")
async def delete_team(team_id: str):
    """Delete a team."""
    db = get_db()
    deleted = db.delete_team(team_id)
    if not deleted:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)
    return {"ok": True}


@router.post("/{team_id}/default", response_model=TeamResponse)
async def set_default_team(team_id: str):
    """Set a team as the default."""
    db = get_db()
    team = db.get_team(team_id)
    if not team:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)

    db.set_default_team(team_id)
    team = db.get_team(team_id)  # re-fetch to get updated state
    return _team_to_response(team)


@router.post("/{team_id}/clone", response_model=TeamResponse, status_code=201)
async def clone_team(team_id: str, body: CloneRequest):
    """Clone a team with a new name."""
    db = get_db()
    clone = db.clone_team(team_id, body.name)
    if not clone:
        raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=team_id)
    return _team_to_response(clone)
