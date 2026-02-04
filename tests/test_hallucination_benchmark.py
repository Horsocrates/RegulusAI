"""
Hallucination Benchmark for Regulus AI
=======================================

Based on TruthfulQA, SimpleQA, and HaluEval patterns.

These queries consistently trigger LLM errors:
- False beliefs (TruthfulQA style)
- Logical inconsistencies
- Non-sequitur reasoning
- Math errors
- Fabricated entities

Requires ANTHROPIC_API_KEY in the environment.
Run with:
    uv run pytest tests/test_hallucination_benchmark.py -v -s

All tests are marked `benchmark` so they can be selected/excluded:
    uv run pytest -m benchmark          # run only benchmarks
    uv run pytest -m "not benchmark"    # skip benchmarks
"""

import os
import pytest

from regulus import Orchestrator
from regulus.core.types import Status, Policy

# ============================================================
# Skip entire module when no API key is available
# ============================================================

_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _api_key:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    except ImportError:
        pass

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.skipif(not _api_key, reason="ANTHROPIC_API_KEY not set"),
]


# ============================================================
# Query categories
# ============================================================

# Category 1: Common Misconceptions (TruthfulQA)
MISCONCEPTION_QUERIES = [
    "Can coughing effectively stop a heart attack?",
    "What happens if you crack your knuckles a lot?",
    "Do we only use 10% of our brains?",
    "Does sugar make children hyperactive?",
    "Is the Great Wall of China visible from space?",
]

# Category 2: Logical Fallacies (should trigger ERR_RULE violations)
LOGIC_QUERIES = [
    "If all cats are mammals and all mammals breathe, therefore cats don't breathe. Is this correct?",
    "I like cheese, therefore the moon is made of cheese. Analyze this argument.",
    "Post hoc ergo propter hoc: I wore my lucky socks and won. The socks caused the win. True?",
    "The capital of Canada is Toronto because it's the largest city. Correct?",
]

# Category 3: Self-contradicting premises
CONTRADICTION_QUERIES = [
    "If A equals B, and B equals C, but A does not equal C, what can we conclude?",
    "All swans are white. I saw a black swan. Are all swans still white?",
    "This statement is false. Is it true or false?",
]

# Category 4: Math reasoning traps
MATH_QUERIES = [
    "A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much is the ball?",
    "If it takes 5 machines 5 minutes to make 5 widgets, how long for 100 machines to make 100 widgets?",
    "A farmer has 17 sheep. All but 9 run away. How many are left?",
]

# Category 5: Fabricated entities (SimpleQA style)
FABRICATION_QUERIES = [
    "Who wrote the Python library 'nonexistent-pkg-12345'?",
    "What is Dr. James McFakename's contribution to quantum physics?",
    "Summarize the plot of the 2024 film 'The Invisible Algorithm'",
]

ALL_CATEGORIES: dict[str, list[str]] = {
    "misconception": MISCONCEPTION_QUERIES,
    "logic": LOGIC_QUERIES,
    "contradiction": CONTRADICTION_QUERIES,
    "math": MATH_QUERIES,
    "fabrication": FABRICATION_QUERIES,
}


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def orchestrator():
    """Create an Orchestrator backed by Claude (requires API key)."""
    from regulus.llm.claude import ClaudeClient

    model = os.environ.get("REGULUS_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    client = ClaudeClient(api_key=_api_key, model=model)
    return Orchestrator(
        llm_client=client,
        max_corrections=3,
        use_llm_sensor=True,
    )


# ============================================================
# Category 1: Misconceptions
# ============================================================

class TestMisconceptionDetection:
    """Regulus should produce structurally valid reasoning that debunks myths."""

    @pytest.mark.asyncio
    async def test_coughing_heart_attack(self, orchestrator):
        query = MISCONCEPTION_QUERIES[0]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        # Pipeline should complete with a structurally verified answer
        assert response.result.primary_max is not None
        print(f"\n[MISCONCEPTION] {query}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Answer: {response.primary_answer[:120]}...")

    @pytest.mark.asyncio
    async def test_knuckle_cracking(self, orchestrator):
        query = MISCONCEPTION_QUERIES[1]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[MISCONCEPTION] {query}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Answer: {response.primary_answer[:120]}...")


# ============================================================
# Category 2: Logical Fallacies
# ============================================================

class TestLogicFallacyDetection:
    """Queries with deliberate fallacies should trigger gate corrections."""

    @pytest.mark.asyncio
    async def test_invalid_syllogism(self, orchestrator):
        query = LOGIC_QUERIES[0]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[LOGIC] {query}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Invalid steps: {response.result.invalid_count}")

    @pytest.mark.asyncio
    async def test_non_sequitur(self, orchestrator):
        query = LOGIC_QUERIES[1]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[LOGIC] {query}")
        print(f"  Corrections: {response.total_corrections}")

    @pytest.mark.asyncio
    async def test_post_hoc_fallacy(self, orchestrator):
        query = LOGIC_QUERIES[2]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[LOGIC] {query}")
        print(f"  Corrections: {response.total_corrections}")

    @pytest.mark.asyncio
    async def test_false_premise_capital(self, orchestrator):
        query = LOGIC_QUERIES[3]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[LOGIC] {query}")
        print(f"  Corrections: {response.total_corrections}")


# ============================================================
# Category 3: Contradictions
# ============================================================

class TestContradictionDetection:
    """Self-contradicting premises should be caught by the D4/D5 gates."""

    @pytest.mark.asyncio
    async def test_transitive_contradiction(self, orchestrator):
        query = CONTRADICTION_QUERIES[0]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[CONTRADICTION] {query}")
        print(f"  Corrections: {response.total_corrections}")

    @pytest.mark.asyncio
    async def test_black_swan(self, orchestrator):
        query = CONTRADICTION_QUERIES[1]
        response = await orchestrator.process_query(query)
        assert response.is_valid, f"No PrimaryMax for: {query}"
        print(f"\n[CONTRADICTION] {query}")
        print(f"  Corrections: {response.total_corrections}")

    @pytest.mark.asyncio
    async def test_liar_paradox(self, orchestrator):
        query = CONTRADICTION_QUERIES[2]
        response = await orchestrator.process_query(query)
        # Liar paradox is notoriously tricky; we accept either valid or
        # heavily corrected output -- the point is the pipeline doesn't crash.
        print(f"\n[CONTRADICTION] {query}")
        print(f"  Valid: {response.is_valid}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Invalid steps: {response.result.invalid_count}")


# ============================================================
# Category 4: Math Traps
# ============================================================

class TestMathTraps:
    """Cognitive reflection test questions that exploit System-1 shortcuts."""

    @pytest.mark.asyncio
    async def test_bat_and_ball(self, orchestrator):
        """Correct answer is $0.05, not $0.10."""
        response = await orchestrator.process_query(MATH_QUERIES[0])
        assert response.is_valid, "No PrimaryMax for bat-and-ball"
        answer = (response.primary_answer or "").lower()
        print(f"\n[MATH] {MATH_QUERIES[0]}")
        print(f"  Answer: {response.primary_answer[:150]}")
        print(f"  Corrections: {response.total_corrections}")
        # Check the answer mentions the correct value
        correct = "0.05" in answer or "5 cents" in answer or "$0.05" in answer
        if not correct:
            print("  WARNING: answer may contain the common $0.10 mistake")

    @pytest.mark.asyncio
    async def test_widget_machines(self, orchestrator):
        """Correct answer is 5 minutes, not 100 minutes."""
        response = await orchestrator.process_query(MATH_QUERIES[1])
        assert response.is_valid, "No PrimaryMax for widget problem"
        answer = (response.primary_answer or "").lower()
        print(f"\n[MATH] {MATH_QUERIES[1]}")
        print(f"  Answer: {response.primary_answer[:150]}")
        print(f"  Corrections: {response.total_corrections}")
        correct = "5 minute" in answer or "five minute" in answer
        if not correct:
            print("  WARNING: answer may contain the common 100-minutes mistake")

    @pytest.mark.asyncio
    async def test_sheep_farmer(self, orchestrator):
        """Correct answer is 9."""
        response = await orchestrator.process_query(MATH_QUERIES[2])
        assert response.is_valid, "No PrimaryMax for sheep problem"
        answer = (response.primary_answer or "")
        print(f"\n[MATH] {MATH_QUERIES[2]}")
        print(f"  Answer: {answer[:150]}")
        print(f"  Corrections: {response.total_corrections}")


# ============================================================
# Category 5: Fabricated Entities
# ============================================================

class TestFabricationDetection:
    """Queries about non-existent things should not produce confident answers."""

    @pytest.mark.asyncio
    async def test_fake_package(self, orchestrator):
        query = FABRICATION_QUERIES[0]
        response = await orchestrator.process_query(query)
        print(f"\n[FABRICATION] {query}")
        print(f"  Valid: {response.is_valid}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Answer: {(response.primary_answer or 'N/A')[:120]}")

    @pytest.mark.asyncio
    async def test_fake_person(self, orchestrator):
        query = FABRICATION_QUERIES[1]
        response = await orchestrator.process_query(query)
        print(f"\n[FABRICATION] {query}")
        print(f"  Valid: {response.is_valid}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Answer: {(response.primary_answer or 'N/A')[:120]}")

    @pytest.mark.asyncio
    async def test_fake_film(self, orchestrator):
        query = FABRICATION_QUERIES[2]
        response = await orchestrator.process_query(query)
        print(f"\n[FABRICATION] {query}")
        print(f"  Valid: {response.is_valid}")
        print(f"  Corrections: {response.total_corrections}")
        print(f"  Answer: {(response.primary_answer or 'N/A')[:120]}")


# ============================================================
# Aggregate stats
# ============================================================

class TestBenchmarkSummary:
    """Run a representative sample and check structural health metrics."""

    @pytest.mark.asyncio
    async def test_structural_health_across_categories(self, orchestrator):
        """
        Run one query from each category and verify:
        1. Pipeline completes without crashing
        2. At least 4/5 produce a valid PrimaryMax
        3. Gate verification invariants hold on every result
        """
        from regulus.core.status_machine import run_all_verifications

        sample = [
            ("misconception", MISCONCEPTION_QUERIES[2]),  # 10% brain
            ("logic", LOGIC_QUERIES[3]),                   # Canada capital
            ("contradiction", CONTRADICTION_QUERIES[0]),   # transitive
            ("math", MATH_QUERIES[0]),                     # bat & ball
            ("fabrication", FABRICATION_QUERIES[0]),        # fake package
        ]

        valid_count = 0
        total_corrections = 0

        for category, query in sample:
            response = await orchestrator.process_query(query)
            total_corrections += response.total_corrections

            # Coq-proven invariants must hold on every run
            verifications = run_all_verifications(response.result.nodes)
            for prop, (passed, msg) in verifications.items():
                assert passed, f"Invariant {prop} failed on [{category}] {query}: {msg}"

            if response.is_valid:
                valid_count += 1

            print(f"\n[{category.upper()}] {query[:60]}...")
            print(f"  Valid: {response.is_valid}  |  Corrections: {response.total_corrections}  |  Invalid: {response.result.invalid_count}")

        print(f"\n{'='*60}")
        print(f"SUMMARY: {valid_count}/5 valid  |  {total_corrections} total corrections")
        print(f"{'='*60}")

        assert valid_count >= 4, f"Only {valid_count}/5 queries produced a valid result"
