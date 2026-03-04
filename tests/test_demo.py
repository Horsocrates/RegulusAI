"""
Tests for regulus demo showcase — offline Logic Censor demo.

Verifies:
  - Scenario construction (5 scenarios, correct fields)
  - Engine verification of each scenario tree
  - Expected gate failures match actual results
  - Fallacy detection matches expectations
  - DemoRunner initializes correctly
"""

import pytest

from regulus.demo.demo_showcase import DemoRunner, DemoScenario, build_scenarios
from regulus.core.engine import LogicGuardEngine
from regulus.core.types import Status, VerificationResult
from regulus.fallacies.detector import detect


# =============================================================================
#  Scenario structure
# =============================================================================

class TestBuildScenarios:
    """Tests for build_scenarios()."""

    def test_returns_five_scenarios(self):
        scenarios = build_scenarios()
        assert len(scenarios) == 5

    def test_scenarios_have_unique_ids(self):
        scenarios = build_scenarios()
        ids = [s.id for s in scenarios]
        assert ids == [1, 2, 3, 4, 5]

    def test_all_scenarios_have_required_fields(self):
        scenarios = build_scenarios()
        for s in scenarios:
            assert isinstance(s, DemoScenario)
            assert s.title
            assert s.category
            assert s.description
            assert s.text
            assert "reasoning_tree" in s.reasoning_tree
            assert len(s.reasoning_tree["reasoning_tree"]) >= 2
            assert s.expected_gate_failure in ("NONE", "ERR", "LEVELS", "ORDER")


# =============================================================================
#  Engine verification
# =============================================================================

class TestEngineVerification:
    """Tests that LogicGuardEngine produces expected results for each scenario."""

    @pytest.fixture
    def engine(self) -> LogicGuardEngine:
        return LogicGuardEngine()

    @pytest.fixture
    def scenarios(self) -> list[DemoScenario]:
        return build_scenarios()

    def test_valid_syllogism_has_primary_max(self, engine, scenarios):
        """Scenario 1: Valid syllogism should produce a PrimaryMax."""
        result = engine.verify(scenarios[0].reasoning_tree)
        assert result.primary_max is not None
        assert result.invalid_count == 0

    def test_ad_hominem_gate_failure(self, engine, scenarios):
        """Scenario 2: Ad hominem should have ERR gate failures."""
        result = engine.verify(scenarios[1].reasoning_tree)
        # At least one node should be INVALID (missing rule_exists)
        assert result.invalid_count > 0

    def test_liar_paradox_all_invalid(self, engine, scenarios):
        """Scenario 3: Liar paradox — all nodes should be INVALID (level violation)."""
        result = engine.verify(scenarios[2].reasoning_tree)
        assert result.primary_max is None
        assert result.invalid_count == len(result.nodes)

    def test_domain_skip_has_invalid(self, engine, scenarios):
        """Scenario 4: Domain skip should have ORDER violation on conclusion."""
        result = engine.verify(scenarios[3].reasoning_tree)
        # The second node (premature_conclusion) should be INVALID
        invalid_nodes = [n for n in result.nodes if n.status == Status.INVALID]
        assert len(invalid_nodes) >= 1
        # First node (observation) should still be valid
        assert result.nodes[0].status != Status.INVALID

    def test_slippery_slope_gate_failure(self, engine, scenarios):
        """Scenario 5: Slippery slope has ERR failures (missing rule)."""
        result = engine.verify(scenarios[4].reasoning_tree)
        assert result.invalid_count > 0


# =============================================================================
#  Fallacy detection
# =============================================================================

class TestFallacyDetection:
    """Tests that regex-mode fallacy detector fires correctly for scenarios."""

    @pytest.fixture
    def scenarios(self) -> list[DemoScenario]:
        return build_scenarios()

    def test_valid_syllogism_passes_detection(self, scenarios):
        result = detect(scenarios[0].text)
        assert result.valid

    def test_ad_hominem_detected(self, scenarios):
        result = detect(scenarios[1].text)
        assert not result.valid
        assert result.fallacy is not None
        assert "AD_HOMINEM" in (result.fallacy.id or "")

    def test_slippery_slope_detected(self, scenarios):
        result = detect(scenarios[4].text)
        assert not result.valid
        assert result.fallacy is not None


# =============================================================================
#  DemoRunner
# =============================================================================

class TestDemoRunner:
    """Tests for DemoRunner initialization."""

    def test_runner_creates_ok(self):
        runner = DemoRunner()
        assert runner.engine is not None
        assert runner.renderer is not None
        assert len(runner.scenarios) == 5

    def test_runner_scenarios_match_build(self):
        runner = DemoRunner()
        built = build_scenarios()
        for a, b in zip(runner.scenarios, built):
            assert a.id == b.id
            assert a.title == b.title
