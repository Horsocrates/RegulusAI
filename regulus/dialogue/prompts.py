"""
Regulus AI - Dialogue Prompt Builder
=====================================

Assembles system prompts for Team Lead and Worker agents from skill files.
Skill files are loaded from .claude/commands/*.md (existing) with a
fallback to workspace/skills/ when available.
"""

import json
from pathlib import Path
from typing import Optional


# Skill file mapping: logical name -> filename in .claude/commands/
TEAM_LEAD_SKILLS = {
    "D6_ASK": "analyze.md",
    "D6_REFLECT": "d6-reflect.md",
}

WORKER_SKILLS = {
    "D1": "d1-recognize.md",
    "D2": "d2-clarify.md",
    "D3": "d3-framework.md",
    "D4": "d4-compare.md",
    "D5": "d5-infer.md",
}

# Default convergence profile (standard)
DEFAULT_PROFILE = {
    "convergence": {
        "max_iterations": 5,
        "min_delta": 5,
        "stall_limit": 2,
        "confidence_threshold": 85,
        "confidence_floor": 40,
        "paradigm_shift_enabled": True,
        "max_paradigm_shifts": 1,
    },
    "worker": {
        "preemptive_replacement": True,
        "preemptive_after_domains": 4,
    },
    "cost": {
        "max_total_tokens": 500_000,
    },
}


def find_skills_dir(start: Optional[Path] = None) -> Path:
    """Find the .claude/commands/ directory by walking up from start."""
    if start is None:
        start = Path.cwd()

    current = start.resolve()
    for _ in range(10):  # max depth
        commands = current / ".claude" / "commands"
        if commands.is_dir():
            return commands
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fallback: try workspace/skills/
    ws_skills = start / "workspace" / "skills"
    if ws_skills.is_dir():
        return ws_skills

    raise FileNotFoundError(
        f"Could not find .claude/commands/ or workspace/skills/ "
        f"starting from {start}"
    )


def _load_skill(skills_dir: Path, filename: str) -> str:
    """Load a skill file's content. Returns empty string if not found."""
    path = skills_dir / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_team_lead_system_prompt(
    skills_dir: Path,
    profile_config: Optional[dict] = None,
) -> str:
    """Assemble the Team Lead's system prompt.

    Structure:
        IDENTITY → D6-ASK skill → D6-REFLECT skill → convergence config → output format
    """
    profile = profile_config or DEFAULT_PROFILE
    parts: list[str] = []

    # Identity
    parts.append(
        "# TEAM LEAD\n"
        "You are the Team Lead of the Regulus reasoning system.\n"
        "You orchestrate a dialogue with a Worker agent, one domain at a time.\n"
        "You ask questions, evaluate answers, maintain the conspectus, "
        "and control convergence.\n"
        "You NEVER reason about domain content — only about reasoning quality.\n"
    )

    # Skills
    for tag, filename in TEAM_LEAD_SKILLS.items():
        content = _load_skill(skills_dir, filename)
        if content:
            parts.append(f"<SKILL_{tag}>\n{content}\n</SKILL_{tag}>\n")

    # Convergence config
    parts.append(
        f"<CONVERGENCE_CONFIG>\n"
        f"{json.dumps(profile, indent=2)}\n"
        f"</CONVERGENCE_CONFIG>\n"
    )

    # Output format
    parts.append(
        "\n## OUTPUT FORMAT\n"
        "Include these XML blocks in EVERY response:\n"
        "  <conspectus>...</conspectus> — REQUIRED. Your running notes "
        "(compressed domain summaries, question statuses, convergence state).\n"
        "  <verdict>...</verdict> — REQUIRED. One of: pass, iterate, "
        "paradigm_shift, threshold_reached, plateau, fundamentally_uncertain.\n"
        "  <worker_instruction>...</worker_instruction> — REQUIRED. "
        "The next instruction for the Worker agent.\n"
    )

    # Conspectus protocol
    parts.append(
        "\n## CONSPECTUS RULES\n"
        "- Extract only key findings, not full output.\n"
        "- Keep summaries under 200 words per domain.\n"
        "- Update after EVERY Worker response.\n"
        "- Never reconstruct from memory — read what you wrote.\n"
        "- The conspectus is THE source of truth, not your recall.\n"
        "- Include: original question, erfragte, root question, "
        "active question set, domain summaries, convergence state, "
        "attention log, open issues.\n"
    )

    return "\n".join(parts)


def build_worker_system_prompt(skills_dir: Path) -> str:
    """Assemble the Worker's system prompt.

    Structure:
        IDENTITY → D1-D5 skill files → output format → context handling
    """
    parts: list[str] = []

    # Identity
    parts.append(
        "# WORKER\n"
        "You are the reasoning engine of the Regulus system.\n"
        "You execute one domain at a time as directed by the Team Lead.\n"
        "Follow domain-specific instructions precisely.\n"
        "Report your output in structured format.\n"
    )

    # Domain skills
    for tag, filename in WORKER_SKILLS.items():
        content = _load_skill(skills_dir, filename)
        if content:
            parts.append(f"<SKILL_{tag}>\n{content}\n</SKILL_{tag}>\n")

    # Output format
    parts.append(
        "\n## OUTPUT FORMAT\n"
        "Include these XML blocks in every response:\n"
        "  <domain_output>...</domain_output> — REQUIRED. "
        "Your structured domain analysis.\n"
        "  <flags>...</flags> — optional. "
        "Contradictions, proposed sub-questions, or concerns for Team Lead.\n"
    )

    # Context handling
    parts.append(
        "\n## CONTEXT HANDLING\n"
        "You may receive a CONSPECTUS from the Team Lead containing "
        "summaries of previous domains. Trust this information — "
        "it was validated.\n"
        "Focus on YOUR current domain assignment.\n"
        "Do not re-derive previous domain results.\n"
        "If you find a contradiction with conspectus data, "
        "FLAG IT explicitly in <flags>.\n"
    )

    return "\n".join(parts)
