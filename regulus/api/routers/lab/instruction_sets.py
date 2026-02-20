"""
Instruction Sets API router — file-based instruction set management.

Scans regulus/instructions/ for subdirectories, each being an instruction set.
The "default" set is always present and cannot be deleted.
Other sets can inherit from default (missing files fall back to default/).

Endpoints:
    GET    /api/lab/instruction-sets                        -> list of sets
    GET    /api/lab/instruction-sets/{id}                   -> set detail + file contents
    POST   /api/lab/instruction-sets                        -> create new set
    PUT    /api/lab/instruction-sets/{id}/files/{filename}  -> update a file
    DELETE /api/lab/instruction-sets/{id}/files/{filename}  -> delete a file (reverts to default)
    DELETE /api/lab/instruction-sets/{id}                   -> delete entire set
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lab/instruction-sets", tags=["lab-instruction-sets"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTRUCTIONS_DIR = Path(__file__).parent.parent.parent.parent / "instructions"

# Standard files that can exist in a set
KNOWN_FILES = [
    "analyze.md",
    "d1-recognize.md",
    "d2-clarify.md",
    "d3-framework.md",
    "d4-compare.md",
    "d5-infer.md",
    "d6-reflect.md",
]


def _ensure_dir():
    """Ensure instructions/ and instructions/default/ exist."""
    INSTRUCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    default_dir = INSTRUCTIONS_DIR / "default"
    default_dir.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class InstructionSetSummary(BaseModel):
    id: str
    name: str
    path: str
    files: list[str]
    file_count: int
    modified: str


class InstructionSetDetail(BaseModel):
    id: str
    name: str
    files: dict[str, str]  # {filename: content}
    inherited_files: list[str]  # files not in this set, falling back to default
    own_files: list[str]  # files actually present in this set's dir


class CreateInstructionSetRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    name: str = Field(default="", max_length=200)
    clone_from: Optional[str] = None
    files: Optional[dict[str, str]] = None


class UpdateFileRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_id_to_name(set_id: str) -> str:
    """Convert set_id to human-readable name."""
    return set_id.replace("_", " ").title()


def _scan_set(set_dir: Path) -> InstructionSetSummary:
    """Build summary for a single instruction set directory."""
    set_id = set_dir.name
    files = sorted(f.name for f in set_dir.iterdir() if f.is_file() and f.suffix == ".md")

    # Latest modification time
    mtime = max(
        (f.stat().st_mtime for f in set_dir.iterdir() if f.is_file()),
        default=set_dir.stat().st_mtime,
    )
    modified = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # Check for a .name file for custom naming
    name_file = set_dir / ".name"
    if name_file.exists():
        name = name_file.read_text(encoding="utf-8").strip()
    else:
        name = _set_id_to_name(set_id)

    return InstructionSetSummary(
        id=set_id,
        name=name,
        path=f"instructions/{set_id}",
        files=files,
        file_count=len(files),
        modified=modified,
    )


def _read_set_files(set_id: str) -> tuple[dict[str, str], list[str], list[str]]:
    """
    Read all resolved files for a set.
    Returns (files_dict, inherited_files, own_files).
    """
    set_dir = INSTRUCTIONS_DIR / set_id
    default_dir = INSTRUCTIONS_DIR / "default"

    own_files: list[str] = []
    inherited_files: list[str] = []
    files: dict[str, str] = {}

    # Collect all possible filenames from both default and this set
    all_filenames: set[str] = set()
    if default_dir.exists():
        all_filenames.update(f.name for f in default_dir.iterdir() if f.is_file() and f.suffix == ".md")
    if set_dir.exists():
        all_filenames.update(f.name for f in set_dir.iterdir() if f.is_file() and f.suffix == ".md")

    for fname in sorted(all_filenames):
        own_path = set_dir / fname
        default_path = default_dir / fname

        if own_path.exists():
            files[fname] = own_path.read_text(encoding="utf-8")
            own_files.append(fname)
        elif default_path.exists() and set_id != "default":
            files[fname] = default_path.read_text(encoding="utf-8")
            inherited_files.append(fname)

    return files, inherited_files, own_files


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[InstructionSetSummary])
async def list_instruction_sets():
    """List all instruction sets (each subdirectory in instructions/)."""
    _ensure_dir()
    sets: list[InstructionSetSummary] = []

    for entry in sorted(INSTRUCTIONS_DIR.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            sets.append(_scan_set(entry))

    # Ensure "default" is first
    sets.sort(key=lambda s: (0 if s.id == "default" else 1, s.id))
    return sets


@router.get("/resolve-preview")
async def resolve_preview(
    set_id: str = "default",
    skill_type: Optional[str] = None,
    paradigm_id: Optional[str] = None,
):
    """
    Preview instruction resolution for all roles.

    Shows how the 6-level fallback chain resolves for each D1-D6 role
    given a specific instruction set, skill type, and paradigm.
    """
    results = {}
    for role, filename in ROLE_TO_FILE.items():
        content, trace = resolve_instruction(
            set_id=set_id,
            role=role,
            skill_type=skill_type,
            paradigm_id=paradigm_id,
        )
        resolved_level = "none"
        for step in trace:
            if step["hit"]:
                resolved_level = step["level"]
                break
        results[role] = {
            "filename": filename,
            "resolved_level": resolved_level,
            "has_content": bool(content),
            "content_length": len(content),
            "trace": trace,
        }
    return {
        "set_id": set_id,
        "skill_type": skill_type,
        "paradigm_id": paradigm_id,
        "roles": results,
        "levels": RESOLUTION_LEVELS,
    }


@router.get("/{set_id}", response_model=InstructionSetDetail)
async def get_instruction_set(set_id: str):
    """Get full detail of an instruction set with resolved file contents."""
    _ensure_dir()
    set_dir = INSTRUCTIONS_DIR / set_id

    if not set_dir.exists() or not set_dir.is_dir():
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    files, inherited_files, own_files = _read_set_files(set_id)

    # Read name
    name_file = set_dir / ".name"
    name = name_file.read_text(encoding="utf-8").strip() if name_file.exists() else _set_id_to_name(set_id)

    return InstructionSetDetail(
        id=set_id,
        name=name,
        files=files,
        inherited_files=inherited_files,
        own_files=own_files,
    )


@router.post("", response_model=InstructionSetSummary, status_code=201)
async def create_instruction_set(body: CreateInstructionSetRequest):
    """Create a new instruction set. Optionally clone from an existing one."""
    _ensure_dir()
    set_dir = INSTRUCTIONS_DIR / body.id

    if set_dir.exists():
        from regulus.api.errors import lab_error
        raise lab_error(
            "LAB_014",
            status_code=409,
            version=body.id,
            paradigm="instruction-sets",
        )

    set_dir.mkdir(parents=True)

    # Clone from existing set
    if body.clone_from:
        source_dir = INSTRUCTIONS_DIR / body.clone_from
        if source_dir.exists():
            for f in source_dir.iterdir():
                if f.is_file() and f.suffix == ".md":
                    shutil.copy2(f, set_dir / f.name)

    # Write any provided files (overwriting cloned ones if needed)
    if body.files:
        for fname, content in body.files.items():
            (set_dir / fname).write_text(content, encoding="utf-8")

    # Write .name if provided
    if body.name:
        (set_dir / ".name").write_text(body.name, encoding="utf-8")

    return _scan_set(set_dir)


@router.put("/{set_id}/files/{filename}")
async def update_file(set_id: str, filename: str, body: UpdateFileRequest):
    """Update (or create) a single file in an instruction set."""
    _ensure_dir()
    set_dir = INSTRUCTIONS_DIR / set_id

    if not set_dir.exists():
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    # Validate filename (prevent path traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        from regulus.api.errors import lab_error
        raise lab_error("LAB_008", status_code=400, detail="Invalid filename")

    filepath = set_dir / filename
    filepath.write_text(body.content, encoding="utf-8")

    return {"ok": True, "file": filename, "size": len(body.content)}


@router.delete("/{set_id}/files/{filename}")
async def delete_file(set_id: str, filename: str):
    """Delete a file from an instruction set (it will fall back to default)."""
    if set_id == "default":
        from regulus.api.errors import lab_error
        raise lab_error("LAB_008", status_code=400, detail="Cannot delete files from default set")

    _ensure_dir()
    set_dir = INSTRUCTIONS_DIR / set_id
    filepath = set_dir / filename

    if not filepath.exists():
        return {"ok": True, "note": "File did not exist"}

    filepath.unlink()
    return {"ok": True, "file": filename}


@router.delete("/{set_id}")
async def delete_instruction_set(set_id: str):
    """Delete an entire instruction set. Cannot delete 'default'."""
    if set_id == "default":
        from regulus.api.errors import lab_error
        raise lab_error("LAB_008", status_code=400, detail="Cannot delete the default instruction set")

    _ensure_dir()
    set_dir = INSTRUCTIONS_DIR / set_id

    if not set_dir.exists():
        from regulus.api.errors import LabErrorCode, lab_error
        raise lab_error(LabErrorCode.INSTRUCTION_SET_NOT_FOUND, id=set_id)

    shutil.rmtree(set_dir)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Runtime helper — used by Team Lead at test execution time
# ---------------------------------------------------------------------------

# Role → filename mapping
ROLE_TO_FILE = {
    "team_lead": "analyze.md",
    "d1": "d1-recognize.md",
    "d2": "d2-clarify.md",
    "d3": "d3-framework.md",
    "d4": "d4-compare.md",
    "d5": "d5-infer.md",
    "d6": "d6-reflect.md",
}

# 6-level resolution chain (most specific → least specific)
RESOLUTION_LEVELS = [
    "specialist",       # L1: _specialist/{paradigm}_{skill}/{filename}
    "paradigm_skill",   # L2: {set_id}/_skill/{skill}/{filename}
    "paradigm_domain",  # L3: {set_id}/{filename}
    "skill",            # L4: _skill/{skill}/{filename}
    "default_skill",    # L5: default/_skill/{skill}/{filename}
    "default",          # L6: default/{filename}
]


def resolve_instruction(
    set_id: str,
    role: str,
    skill_type: str | None = None,
    paradigm_id: str | None = None,
    override_file: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Resolve instruction markdown for a role using 3D fallback chain.

    Dimensions: Paradigm (instruction set) × Skill Type × Domain (role).

    6-level fallback (most specific → least specific):
        L1 specialist:      _specialist/{paradigm}_{skill}/{filename}
        L2 paradigm_skill:  {set_id}/_skill/{skill}/{filename}
        L3 paradigm_domain: {set_id}/{filename}
        L4 skill:           _skill/{skill}/{filename}
        L5 default_skill:   default/_skill/{skill}/{filename}
        L6 default:         default/{filename}

    Args:
        set_id: The instruction set ID (directory name).
        role: One of 'team_lead', 'd1', ..., 'd6', or subprocess IDs.
        skill_type: Cognitive skill type (decomposition/verification/recall/
                    computation/conceptual). Optional.
        paradigm_id: Paradigm config ID used for specialist lookup. Optional.
        override_file: Explicit filename override.

    Returns:
        (content, trace) where trace is a list of
        {"level": str, "path": str, "hit": bool} dicts.
    """
    filename = override_file or ROLE_TO_FILE.get(role)
    if not filename:
        filename = f"subprocess_{role}.md"

    skill = skill_type.lower().strip() if skill_type else None
    paradigm = paradigm_id.lower().strip() if paradigm_id else None

    # Build candidate paths
    candidates: list[tuple[str, Path]] = []

    # L1: specialist — paradigm × skill × domain
    if paradigm and skill:
        candidates.append((
            "specialist",
            INSTRUCTIONS_DIR / "_specialist" / f"{paradigm}_{skill}" / filename,
        ))

    # L2: paradigm_skill — instruction set's skill overlay
    if set_id and set_id != "default" and skill:
        candidates.append((
            "paradigm_skill",
            INSTRUCTIONS_DIR / set_id / "_skill" / skill / filename,
        ))

    # L3: paradigm_domain — instruction set's own domain file
    if set_id and set_id != "default":
        candidates.append((
            "paradigm_domain",
            INSTRUCTIONS_DIR / set_id / filename,
        ))

    # L4: skill — global skill overlay
    if skill:
        candidates.append((
            "skill",
            INSTRUCTIONS_DIR / "_skill" / skill / filename,
        ))

    # L5: default_skill — default set's skill overlay
    if skill:
        candidates.append((
            "default_skill",
            INSTRUCTIONS_DIR / "default" / "_skill" / skill / filename,
        ))

    # L6: default
    candidates.append((
        "default",
        INSTRUCTIONS_DIR / "default" / filename,
    ))

    # Walk the chain
    trace: list[dict] = []
    content = ""

    for level, path in candidates:
        try:
            rel_path = str(path.relative_to(INSTRUCTIONS_DIR))
        except ValueError:
            rel_path = str(path)
        hit = path.exists()
        trace.append({"level": level, "path": rel_path, "hit": hit})
        if hit:
            content = path.read_text(encoding="utf-8")
            logger.info(
                "Instruction resolved: role=%s level=%s path=%s",
                role, level, rel_path,
            )
            break

    if not content:
        logger.warning(
            "Instruction not found: role=%s set_id=%s skill=%s paradigm=%s",
            role, set_id, skill_type, paradigm_id,
        )

    return content, trace


def load_instructions(
    set_id: str,
    role: str,
    override_file: str | None = None,
) -> str:
    """
    Load instruction markdown for a role from a set, with default fallback.

    Backward-compatible wrapper around resolve_instruction().
    """
    content, _ = resolve_instruction(
        set_id=set_id,
        role=role,
        override_file=override_file,
    )
    return content
