"""Tests for Lab v2 Judge — StrictJudge and SemanticJudge."""

import pytest

from regulus.lab.judge_v2 import (
    StrictJudge,
    SemanticJudge,
    JudgmentResult,
    create_judge,
)


# ===================================================================
# StrictJudge
# ===================================================================


class TestStrictJudge:
    def setup_method(self):
        self.judge = StrictJudge()

    def test_exact_match(self):
        result = self.judge.evaluate("42", "42")
        assert result.verdict == "correct"
        assert result.confidence == 1.0
        assert result.judge_model == "exact_match"

    def test_case_insensitive(self):
        result = self.judge.evaluate("True", "true")
        assert result.verdict == "correct"

    def test_whitespace_normalized(self):
        result = self.judge.evaluate("  hello   world  ", "hello world")
        assert result.verdict == "correct"

    def test_prefix_stripped_answer_is(self):
        result = self.judge.evaluate("The answer is 42", "42")
        assert result.verdict == "correct"

    def test_prefix_stripped_final_answer(self):
        result = self.judge.evaluate("Final answer: Paris", "paris")
        assert result.verdict == "correct"

    def test_prefix_stripped_therefore(self):
        result = self.judge.evaluate("Therefore, B", "b")
        assert result.verdict == "correct"

    def test_mismatch(self):
        result = self.judge.evaluate("43", "42")
        assert result.verdict == "wrong"
        assert result.confidence == 1.0

    def test_trailing_period_stripped(self):
        result = self.judge.evaluate("True.", "true")
        assert result.verdict == "correct"

    def test_punctuation_removed(self):
        result = self.judge.evaluate("yes, it is!", "yes it is")
        assert result.verdict == "correct"

    def test_surrounding_quotes_stripped(self):
        result = self.judge.evaluate('"hello"', "hello")
        assert result.verdict == "correct"

    def test_single_quotes_stripped(self):
        result = self.judge.evaluate("'world'", "world")
        assert result.verdict == "correct"

    def test_empty_answer(self):
        result = self.judge.evaluate("", "42")
        assert result.verdict == "wrong"

    def test_none_answer(self):
        result = self.judge.evaluate(None, "42")
        # None is converted to empty string
        assert result.verdict == "wrong"

    def test_judged_at_set(self):
        result = self.judge.evaluate("x", "y")
        assert result.judged_at != ""


# ===================================================================
# JudgmentResult
# ===================================================================


class TestJudgmentResult:
    def test_to_dict(self):
        jr = JudgmentResult(
            verdict="correct",
            confidence=0.95,
            explanation="Match",
            judge_model="exact_match",
            judged_at="2025-01-01T00:00:00",
        )
        d = jr.to_dict()
        assert d["verdict"] == "correct"
        assert d["confidence"] == 0.95
        assert d["judge_model"] == "exact_match"


# ===================================================================
# create_judge factory
# ===================================================================


class TestCreateJudge:
    def test_strict_mode(self):
        judge = create_judge({"strict_mode": True})
        assert isinstance(judge, StrictJudge)

    def test_semantic_mode(self):
        judge = create_judge({"strict_mode": False})
        assert isinstance(judge, SemanticJudge)

    def test_default_semantic(self):
        judge = create_judge({})
        assert isinstance(judge, SemanticJudge)

    def test_empty_config(self):
        judge = create_judge({})
        assert isinstance(judge, SemanticJudge)


# ===================================================================
# StrictJudge normalization edge cases
# ===================================================================


class TestStrictNormalization:
    def setup_method(self):
        self.judge = StrictJudge()

    def test_multiline_answer(self):
        # Only compares normalized content
        result = self.judge.evaluate("The answer is\n42", "42")
        assert result.verdict == "correct"

    def test_numeric_equivalence(self):
        # String comparison — "42.0" != "42"
        result = self.judge.evaluate("42.0", "42")
        assert result.verdict == "wrong"

    def test_boolean_mixed_case(self):
        result = self.judge.evaluate("FALSE", "false")
        assert result.verdict == "correct"

    def test_long_prefix(self):
        result = self.judge.evaluate("The correct answer is XYZ", "xyz")
        assert result.verdict == "correct"
