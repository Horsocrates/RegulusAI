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

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

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


def load_instructions(
    set_id: str,
    role: str,
    override_file: str | None = None,
) -> str:
    """
    Load instruction markdown for a role from a set, with default fallback.

    Args:
        set_id: The instruction set ID (directory name)
        role: One of 'team_lead', 'd1', 'd2', ..., 'd6', or subprocess IDs
        override_file: If provided, use this filename instead of the default
                       role-to-file mapping. Set via paradigm config UI.

    Returns:
        The instruction text (markdown).
    """
    # Map role to filename
    role_to_file = {
        "team_lead": "analyze.md",
        "d1": "d1-recognize.md",
        "d2": "d2-clarify.md",
        "d3": "d3-framework.md",
        "d4": "d4-compare.md",
        "d5": "d5-infer.md",
        "d6": "d6-reflect.md",
    }

    filename = override_file or role_to_file.get(role)
    if not filename:
        # Try subprocess files
        filename = f"subprocess_{role}.md"

    set_dir = INSTRUCTIONS_DIR / set_id
    default_dir = INSTRUCTIONS_DIR / "default"

    # Try set-specific first, then default
    filepath = set_dir / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")

    default_path = default_dir / filename
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")

    return ""
