"""
Team rotation manager for Lab test execution.

Manages team rotation during benchmark tests — each team gets a fixed number
of questions before a fresh team instance takes over (new context, no memory
bleed between rotations).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TeamInstance:
    """A single team instance in a rotation."""
    index: int                        # Team-0, Team-1, etc.
    team_config_id: str               # Base team configuration ID
    question_range: tuple[int, int]   # (start_idx, end_idx) exclusive
    created_at: str = ""
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "team_config_id": self.team_config_id,
            "question_range": list(self.question_range),
            "created_at": self.created_at,
        }


class TeamRotationManager:
    """Manages team rotation during test execution.

    Each team processes up to `questions_per_team` questions before
    being replaced with a fresh instance. This prevents context degradation
    over long runs (the P3 protocol degradation problem).
    """

    def __init__(
        self,
        base_team_id: str,
        questions_per_team: int,
        total_questions: int,
    ):
        self.base_team_id = base_team_id
        self.questions_per_team = max(1, questions_per_team)
        self.total_questions = total_questions
        self.teams: list[TeamInstance] = []
        self._current_index = -1

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_teams_needed(self) -> int:
        """Total number of team rotations for the full test."""
        return math.ceil(self.total_questions / self.questions_per_team)

    @property
    def current_team(self) -> Optional[TeamInstance]:
        """Currently active team (last created)."""
        return self.teams[-1] if self.teams else None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def get_team_for_question(self, question_index: int) -> TeamInstance:
        """Get or create the team responsible for a given question index."""
        team_index = question_index // self.questions_per_team

        # Create teams as needed (supports non-sequential access)
        while len(self.teams) <= team_index:
            self._create_next_team()

        return self.teams[team_index]

    def should_rotate(self, completed_questions: int) -> bool:
        """Check if team rotation should happen after this question count."""
        if completed_questions <= 0:
            return False
        return completed_questions % self.questions_per_team == 0

    def get_team_index_for_question(self, question_index: int) -> int:
        """Get the team index (0-based) for a question without creating instances."""
        return question_index // self.questions_per_team

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_rotation_summary(self) -> dict:
        """Get summary of all team rotations."""
        return {
            "base_team_id": self.base_team_id,
            "questions_per_team": self.questions_per_team,
            "total_questions": self.total_questions,
            "total_teams_needed": self.total_teams_needed,
            "teams_created": len(self.teams),
            "teams": [t.to_dict() for t in self.teams],
        }

    def get_teams_used(self) -> list[dict]:
        """Return serialisable list of team instances (for DB storage)."""
        return [t.to_dict() for t in self.teams]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_next_team(self) -> TeamInstance:
        """Create a fresh team instance with clean context."""
        index = len(self.teams)
        start = index * self.questions_per_team
        end = min(start + self.questions_per_team, self.total_questions)

        team = TeamInstance(
            index=index,
            team_config_id=self.base_team_id,
            question_range=(start, end),
            created_at=datetime.now(timezone.utc).isoformat(),
            context=self._create_fresh_context(),
        )
        self.teams.append(team)
        return team

    @staticmethod
    def _create_fresh_context() -> dict:
        """Create fresh context for new team (no memory from previous questions)."""
        return {
            "conversation_history": [],
            "accumulated_knowledge": {},
            "error_patterns": [],
        }
