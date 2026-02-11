"""Tests for team rotation manager."""

import pytest

from regulus.lab.rotation import TeamRotationManager, TeamInstance


class TestTeamRotationBasic:
    """Basic rotation calculations."""

    def test_total_teams_exact_division(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        assert rm.total_teams_needed == 5

    def test_total_teams_remainder(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=10)
        assert rm.total_teams_needed == 3  # ceil(10/4) = 3

    def test_total_teams_single_question(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=1)
        assert rm.total_teams_needed == 1

    def test_total_teams_one_per_team(self):
        rm = TeamRotationManager("team-1", questions_per_team=1, total_questions=5)
        assert rm.total_teams_needed == 5

    def test_zero_questions_per_team_clamped(self):
        rm = TeamRotationManager("team-1", questions_per_team=0, total_questions=10)
        assert rm.questions_per_team == 1  # clamped to 1


class TestGetTeamForQuestion:
    """Team assignment for questions."""

    def test_first_question_creates_team(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        team = rm.get_team_for_question(0)
        assert isinstance(team, TeamInstance)
        assert team.index == 0
        assert team.team_config_id == "team-1"
        assert team.question_range == (0, 4)

    def test_same_team_for_batch(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        t0 = rm.get_team_for_question(0)
        t1 = rm.get_team_for_question(1)
        t2 = rm.get_team_for_question(2)
        t3 = rm.get_team_for_question(3)
        assert t0 is t1 is t2 is t3

    def test_rotation_at_boundary(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        team_a = rm.get_team_for_question(3)
        team_b = rm.get_team_for_question(4)
        assert team_a.index == 0
        assert team_b.index == 1
        assert team_a is not team_b

    def test_last_team_range_clamped(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=10)
        team = rm.get_team_for_question(8)
        assert team.index == 2
        assert team.question_range == (8, 10)  # only 2 questions

    def test_non_sequential_access(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        team_last = rm.get_team_for_question(19)
        assert team_last.index == 4
        assert len(rm.teams) == 5  # all intermediate teams created

    def test_fresh_context_per_team(self):
        rm = TeamRotationManager("team-1", questions_per_team=2, total_questions=6)
        t0 = rm.get_team_for_question(0)
        t1 = rm.get_team_for_question(2)
        # Contexts should be independent objects
        assert t0.context is not t1.context
        assert t0.context == t1.context  # same structure, different instance


class TestShouldRotate:
    """Rotation trigger checks."""

    def test_no_rotate_at_zero(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        assert rm.should_rotate(0) is False

    def test_rotate_at_boundary(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        assert rm.should_rotate(4) is True
        assert rm.should_rotate(8) is True

    def test_no_rotate_mid_batch(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        assert rm.should_rotate(1) is False
        assert rm.should_rotate(2) is False
        assert rm.should_rotate(3) is False
        assert rm.should_rotate(5) is False


class TestRotationSummary:
    """Summary and serialization."""

    def test_summary_empty(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        summary = rm.get_rotation_summary()
        assert summary["base_team_id"] == "team-1"
        assert summary["total_teams_needed"] == 5
        assert summary["teams_created"] == 0

    def test_summary_after_use(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=8)
        rm.get_team_for_question(0)
        rm.get_team_for_question(4)
        summary = rm.get_rotation_summary()
        assert summary["teams_created"] == 2
        assert len(summary["teams"]) == 2

    def test_teams_used_serializable(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=8)
        rm.get_team_for_question(0)
        rm.get_team_for_question(4)
        teams_used = rm.get_teams_used()
        assert isinstance(teams_used, list)
        assert all(isinstance(t, dict) for t in teams_used)
        assert teams_used[0]["index"] == 0
        assert teams_used[1]["index"] == 1

    def test_current_team_none_initially(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=8)
        assert rm.current_team is None

    def test_current_team_after_access(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=8)
        rm.get_team_for_question(5)
        assert rm.current_team is not None
        assert rm.current_team.index == 1

    def test_get_team_index_for_question_no_create(self):
        rm = TeamRotationManager("team-1", questions_per_team=4, total_questions=20)
        assert rm.get_team_index_for_question(0) == 0
        assert rm.get_team_index_for_question(3) == 0
        assert rm.get_team_index_for_question(4) == 1
        assert rm.get_team_index_for_question(19) == 4
        # No teams should have been created
        assert len(rm.teams) == 0
