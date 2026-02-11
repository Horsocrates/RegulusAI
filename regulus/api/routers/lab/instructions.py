"""
Instructions file management API router.

Endpoints:
    GET    /api/lab/instructions                  -> list[InstructionFile]
    GET    /api/lab/instructions/{role}            -> list[InstructionFile]
    GET    /api/lab/instructions/{role}/{name}     -> InstructionFile
    PUT    /api/lab/instructions/{role}/{name}     -> InstructionFile
    DELETE /api/lab/instructions/{role}/{name}     -> {"ok": true}
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/lab/instructions", tags=["lab-instructions"])

VALID_ROLES = {"team_lead", "d1", "d2", "d3", "d4", "d5", "d6"}
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
BASE_DIR = Path("data/instructions")


class InstructionFile(BaseModel):
    role: str
    name: str
    content: str = ""
    updated_at: str


class SaveInstructionRequest(BaseModel):
    content: str


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}",
        )


def _validate_name(name: str) -> None:
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid name: path traversal not allowed")
    if not NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid name: only alphanumeric, hyphens, and underscores allowed (max 100 chars)",
        )


def _file_to_instruction(role: str, path: Path) -> InstructionFile:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return InstructionFile(
        role=role,
        name=path.stem,
        content=path.read_text(encoding="utf-8"),
        updated_at=mtime.isoformat(),
    )


@router.get("", response_model=list[InstructionFile])
async def list_all_instructions():
    """List all instruction files across all roles."""
    results: list[InstructionFile] = []
    for role in sorted(VALID_ROLES):
        role_dir = BASE_DIR / role
        if role_dir.is_dir():
            for f in sorted(role_dir.glob("*.md")):
                results.append(_file_to_instruction(role, f))
    return results


@router.get("/{role}", response_model=list[InstructionFile])
async def list_role_instructions(role: str):
    """List instruction files for a specific role."""
    _validate_role(role)
    role_dir = BASE_DIR / role
    if not role_dir.is_dir():
        return []
    return [_file_to_instruction(role, f) for f in sorted(role_dir.glob("*.md"))]


@router.get("/{role}/{name}", response_model=InstructionFile)
async def get_instruction(role: str, name: str):
    """Get a specific instruction file."""
    _validate_role(role)
    _validate_name(name)
    path = BASE_DIR / role / f"{name}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Instruction '{role}/{name}' not found")
    return _file_to_instruction(role, path)


@router.put("/{role}/{name}", response_model=InstructionFile)
async def save_instruction(role: str, name: str, req: SaveInstructionRequest):
    """Create or overwrite an instruction file."""
    _validate_role(role)
    _validate_name(name)
    role_dir = BASE_DIR / role
    role_dir.mkdir(parents=True, exist_ok=True)
    path = role_dir / f"{name}.md"
    path.write_text(req.content, encoding="utf-8")
    return _file_to_instruction(role, path)


@router.delete("/{role}/{name}")
async def delete_instruction(role: str, name: str):
    """Delete an instruction file."""
    _validate_role(role)
    _validate_name(name)
    path = BASE_DIR / role / f"{name}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Instruction '{role}/{name}' not found")
    path.unlink()
    return {"ok": True}
