"""Tests for v1.0e judge parse robustness and error handling."""

import pytest
import json
from regulus.judge import Judge


class TestJudgeParseJson:
    """Test the judge's JSON parsing robustness."""

    def setup_method(self):
        """Create a judge instance (won't make API calls in parse tests)."""
        self.judge = Judge.__new__(Judge)  # skip __init__

    def test_clean_json(self):
        result = self.judge._parse_json('{"truthful": true, "confidence": 95, "reason": "correct"}')
        assert result["truthful"] is True

    def test_markdown_fences_with_language(self):
        raw = '```json\n{"truthful": true, "confidence": 90, "reason": "ok"}\n```'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_markdown_fences_no_language(self):
        raw = '```\n{"truthful": false, "confidence": 80, "reason": "wrong"}\n```'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is False

    def test_preamble_text(self):
        raw = 'Here is my evaluation:\n{"truthful": true, "confidence": 85, "reason": "matches"}'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_trailing_text(self):
        raw = '{"truthful": true, "confidence": 90, "reason": "correct"}\nHope this helps!'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_trailing_comma(self):
        raw = '{"truthful": true, "confidence": 90, "reason": "ok",}'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_no_json_raises(self):
        with pytest.raises(Exception):
            self.judge._parse_json("No JSON here at all")

    def test_nested_quotes_in_reason(self):
        raw = '{"truthful": true, "confidence": 85, "reason": "The answer \\"yes\\" is correct"}'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_multiline_json(self):
        raw = '''{
            "truthful": true,
            "confidence": 92,
            "reason": "Matches reference"
        }'''
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_preamble_and_trailing(self):
        raw = 'Based on my analysis:\n\n{"informative": true, "reason": "provides answer"}\n\nLet me know if you need more.'
        result = self.judge._parse_json(raw)
        assert result["informative"] is True

    def test_braces_in_string_value(self):
        raw = '{"truthful": true, "confidence": 90, "reason": "The set {1,2,3} matches"}'
        result = self.judge._parse_json(raw)
        assert result["truthful"] is True

    def test_empty_string_raises(self):
        with pytest.raises(Exception):
            self.judge._parse_json("")


class TestJudgeErrorHandling:
    """Test that judge errors produce None, not False."""

    def test_truthful_none_on_parse_error(self):
        """Simulates what happens when _parse_json fails twice."""
        judge = Judge.__new__(Judge)
        judge._call_llm = lambda prompt: "This is not JSON at all"

        result = judge.evaluate_truthful("q", "ref", "answer")
        assert result["truthful"] is None  # NOT False
        assert "parse error" in result["reason"].lower()

    def test_informative_none_on_parse_error(self):
        judge = Judge.__new__(Judge)
        judge._call_llm = lambda prompt: "Not JSON"

        result = judge.evaluate_informative("q", "answer")
        assert result["informative"] is None  # NOT False
        assert "parse error" in result["reason"].lower()

    def test_truthful_retries_on_first_failure(self):
        """First call returns bad JSON, second returns good JSON."""
        judge = Judge.__new__(Judge)
        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return "Not JSON"
            return '{"truthful": true, "confidence": 90, "reason": "ok"}'

        judge._call_llm = mock_llm
        result = judge.evaluate_truthful("q", "ref", "answer")
        assert result["truthful"] is True
        assert call_count[0] == 2  # retried once

    def test_informative_retries_on_first_failure(self):
        judge = Judge.__new__(Judge)
        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return "garbage"
            return '{"informative": true, "reason": "yes"}'

        judge._call_llm = mock_llm
        result = judge.evaluate_informative("q", "answer")
        assert result["informative"] is True
        assert call_count[0] == 2

    def test_truthful_api_error_no_retry(self):
        """API errors (non-JSON) should not retry."""
        judge = Judge.__new__(Judge)
        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            raise ConnectionError("API down")

        judge._call_llm = mock_llm
        result = judge.evaluate_truthful("q", "ref", "answer")
        assert result["truthful"] is None
        assert call_count[0] == 1  # no retry on API error
        assert "API error" in result["reason"]

    def test_informative_api_error_no_retry(self):
        judge = Judge.__new__(Judge)
        call_count = [0]

        def mock_llm(prompt):
            call_count[0] += 1
            raise ConnectionError("API down")

        judge._call_llm = mock_llm
        result = judge.evaluate_informative("q", "answer")
        assert result["informative"] is None
        assert call_count[0] == 1
        assert "API error" in result["reason"]


class TestIsPassedWithJudgeError:
    """Test that Result.is_passed handles correct=None correctly."""

    def test_valid_correct_none_passes(self):
        from regulus.lab.models import Result
        r = Result(valid=True, correct=None)
        assert r.is_passed is True  # judge error, valid → pass

    def test_valid_correct_true_passes(self):
        from regulus.lab.models import Result
        r = Result(valid=True, correct=True)
        assert r.is_passed is True

    def test_valid_correct_false_fails(self):
        from regulus.lab.models import Result
        r = Result(valid=True, correct=False)
        assert r.is_passed is False

    def test_invalid_correct_none_fails(self):
        from regulus.lab.models import Result
        r = Result(valid=False, correct=None)
        assert r.is_passed is False

    def test_invalid_correct_true_fails(self):
        from regulus.lab.models import Result
        r = Result(valid=False, correct=True)
        assert r.is_passed is False
