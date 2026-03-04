"""
Tests for LLM Fallacy Extractor (Week 1).

Tests cover:
  1. JSON parsing (valid, code-fenced, embedded, malformed)
  2. Signal parsing from dict → Signals dataclass
  3. Mock LLM → known JSON → verify classification
  4. Regex fallback on LLM error
  5. detect_llm() with high-confidence LLM classification
  6. detect_llm() with low-confidence → cascading to signal engine
  7. Cache behavior
  8. Taxonomy summary generation
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from regulus.fallacies.detector import (
    DetectionResult,
    Signals,
    detect,
    detect_llm,
    _detect_from_signals,
)
from regulus.fallacies.llm_extractor import (
    LLMExtractionResult,
    LLMFallacyExtractor,
    _parse_json_response,
    _parse_signals,
)
from regulus.fallacies.taxonomy import (
    FALLACIES,
    get_fallacy,
    get_taxonomy_summary,
)


# =============================================================================
#                           HELPERS
# =============================================================================

def _make_mock_client(response: str) -> MagicMock:
    """Create a mock LLMClient returning a fixed response."""
    client = MagicMock()
    client.generate = AsyncMock(return_value=response)
    return client


def _make_llm_response(
    primary_id: str | None = None,
    confidence: float = 0.0,
    reasoning: str = "",
    **signal_overrides,
) -> str:
    """Build a JSON LLM response string."""
    signals = {
        "attacks_person": False,
        "addresses_argument": False,
        "uses_tradition": False,
        "considers_counter": False,
        "self_reference": False,
        "uses_emotion": False,
        "false_authority": False,
        "false_dilemma": False,
        "post_hoc_pattern": False,
        "slippery_slope": False,
        "overgeneralizes": False,
        "cherry_picks": False,
        "whataboutism": False,
        "circular": False,
        "bandwagon": False,
        "passive_hiding": False,
        "moving_goalposts": False,
        "sunk_cost": False,
    }
    signals.update(signal_overrides)
    return json.dumps({
        "signals": signals,
        "primary_fallacy_id": primary_id,
        "confidence": confidence,
        "reasoning": reasoning,
    })


# =============================================================================
#                           JSON PARSING TESTS
# =============================================================================

class TestParseJsonResponse:
    """Test _parse_json_response with various formats."""

    def test_clean_json(self):
        raw = '{"foo": 42, "bar": true}'
        assert _parse_json_response(raw) == {"foo": 42, "bar": True}

    def test_code_fenced_json(self):
        raw = '```json\n{"foo": 42}\n```'
        assert _parse_json_response(raw) == {"foo": 42}

    def test_code_fenced_no_lang(self):
        raw = '```\n{"foo": 42}\n```'
        assert _parse_json_response(raw) == {"foo": 42}

    def test_embedded_json(self):
        raw = 'Here is the result:\n{"foo": 42}\nDone.'
        assert _parse_json_response(raw) == {"foo": 42}

    def test_malformed_raises(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            _parse_json_response("not json at all")

    def test_whitespace_padded(self):
        raw = '  \n  {"x": 1}  \n  '
        assert _parse_json_response(raw) == {"x": 1}


# =============================================================================
#                           SIGNAL PARSING TESTS
# =============================================================================

class TestParseSignals:
    """Test _parse_signals dict → Signals conversion."""

    def test_all_false(self):
        sig = _parse_signals({})
        assert sig.attacks_person is False
        assert sig.considers_counter is False
        assert sig.sunk_cost is False

    def test_some_true(self):
        sig = _parse_signals({
            "attacks_person": True,
            "whataboutism": True,
        })
        assert sig.attacks_person is True
        assert sig.whataboutism is True
        assert sig.false_dilemma is False

    def test_truthy_values(self):
        sig = _parse_signals({
            "attacks_person": 1,
            "circular": "yes",
        })
        assert sig.attacks_person is True
        assert sig.circular is True

    def test_falsy_values(self):
        sig = _parse_signals({
            "attacks_person": 0,
            "circular": "",
            "sunk_cost": None,
        })
        assert sig.attacks_person is False
        assert sig.circular is False
        assert sig.sunk_cost is False


# =============================================================================
#                           EXTRACTOR TESTS (with mock LLM)
# =============================================================================

class TestLLMFallacyExtractor:
    """Test LLMFallacyExtractor with mocked LLM client."""

    def test_extract_ad_hominem(self):
        """LLM identifies ad hominem correctly."""
        response = _make_llm_response(
            primary_id="D1_AD_HOMINEM",
            confidence=0.9,
            reasoning="Text attacks the person.",
            attacks_person=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(extractor.extract("You're an idiot."))
        assert result.used_llm is True
        assert result.primary_fallacy_id == "D1_AD_HOMINEM"
        assert result.confidence == 0.9
        assert result.signals.attacks_person is True

    def test_extract_valid_reasoning(self):
        """LLM correctly identifies valid reasoning."""
        response = _make_llm_response(
            primary_id=None,
            confidence=0.0,
            reasoning="Well-structured argument with counter-evidence.",
            addresses_argument=True,
            considers_counter=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(extractor.extract("A is true because B. However, C."))
        assert result.primary_fallacy_id is None
        assert result.confidence == 0.0
        assert result.signals.addresses_argument is True
        assert result.signals.considers_counter is True

    def test_extract_sunk_cost(self):
        """LLM identifies sunk cost fallacy."""
        response = _make_llm_response(
            primary_id="D6_SUNK_COST",
            confidence=0.85,
            sunk_cost=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(extractor.extract("We invested too much to quit."))
        assert result.primary_fallacy_id == "D6_SUNK_COST"
        assert result.signals.sunk_cost is True

    def test_fallback_on_error(self):
        """Falls back to regex when LLM fails."""
        client = MagicMock()
        client.generate = AsyncMock(side_effect=RuntimeError("API error"))
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(extractor.extract("You're an idiot."))
        assert result.used_llm is False
        assert result.signals.attacks_person is True
        assert result.reasoning == "Regex fallback (LLM unavailable)"

    def test_fallback_on_bad_json(self):
        """Falls back to regex when LLM returns unparseable response."""
        client = _make_mock_client("I don't know how to do JSON")
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(extractor.extract("You're an idiot."))
        assert result.used_llm is False
        assert result.signals.attacks_person is True

    def test_cache_hit(self):
        """Cache returns same result without calling LLM again."""
        response = _make_llm_response(primary_id="D1_AD_HOMINEM", confidence=0.9)
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=True)

        text = "You're an idiot."
        r1 = asyncio.run(extractor.extract(text))
        r2 = asyncio.run(extractor.extract(text))

        assert r1.primary_fallacy_id == r2.primary_fallacy_id
        # LLM called only once
        assert client.generate.call_count == 1

    def test_clear_cache(self):
        """Cache can be cleared."""
        response = _make_llm_response(primary_id="D1_AD_HOMINEM", confidence=0.9)
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=True)

        asyncio.run(extractor.extract("test"))
        assert extractor.clear_cache() == 1
        asyncio.run(extractor.extract("test"))
        assert client.generate.call_count == 2


# =============================================================================
#                           detect_llm() TESTS
# =============================================================================

class TestDetectLLM:
    """Test detect_llm() integration with LLMFallacyExtractor."""

    def test_high_confidence_direct(self):
        """High confidence LLM → use LLM's fallacy ID directly."""
        response = _make_llm_response(
            primary_id="D5_SLIPPERY_SLOPE",
            confidence=0.85,
            slippery_slope=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(detect_llm("If we allow X, then Y, then Z!", extractor))
        assert not result.valid
        assert result.fallacy is not None
        assert result.fallacy.id == "D5_SLIPPERY_SLOPE"
        assert result.confidence == 0.85

    def test_low_confidence_uses_cascade(self):
        """Low confidence LLM → use signals through detection cascade."""
        response = _make_llm_response(
            primary_id="D5_POST_HOC",
            confidence=0.4,  # Below 0.7 threshold
            attacks_person=True,  # Signal says ad hominem
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(detect_llm("You're stupid", extractor))
        assert not result.valid
        # Cascade should pick D1_AD_HOMINEM from signal, not D5_POST_HOC
        assert result.fallacy is not None
        assert result.fallacy.id == "D1_AD_HOMINEM"

    def test_valid_text_llm(self):
        """LLM says valid + signals confirm → valid result."""
        response = _make_llm_response(
            primary_id=None,
            confidence=0.0,
            addresses_argument=True,
            considers_counter=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(detect_llm("A, therefore B. However, C.", extractor))
        assert result.valid

    def test_invalid_fallacy_id_uses_cascade(self):
        """LLM returns non-existent ID → falls to cascade."""
        response = _make_llm_response(
            primary_id="NONEXISTENT_FALLACY",
            confidence=0.95,
            sunk_cost=True,
        )
        client = _make_mock_client(response)
        extractor = LLMFallacyExtractor(client, cache_enabled=False)

        result = asyncio.run(detect_llm("Too much invested to quit", extractor))
        assert not result.valid
        # Cascade should use sunk_cost signal
        assert result.fallacy is not None
        assert result.fallacy.id == "D6_SUNK_COST"


# =============================================================================
#                           _detect_from_signals() TESTS
# =============================================================================

class TestDetectFromSignals:
    """Test the shared cascade logic directly."""

    def test_self_reference_highest_priority(self):
        sig = Signals(self_reference=True, attacks_person=True)
        r = _detect_from_signals(sig)
        assert r.fallacy.id == "T3_CIRCULAR_REASONING"

    def test_ad_hominem(self):
        sig = Signals(attacks_person=True, addresses_argument=False)
        r = _detect_from_signals(sig)
        assert r.fallacy.id == "D1_AD_HOMINEM"

    def test_sunk_cost(self):
        sig = Signals(sunk_cost=True, considers_counter=True)
        r = _detect_from_signals(sig)
        assert r.fallacy.id == "D6_SUNK_COST"

    def test_valid_when_counter_present(self):
        sig = Signals(addresses_argument=True, considers_counter=True)
        r = _detect_from_signals(sig)
        assert r.valid

    def test_confirmation_bias_fallback(self):
        sig = Signals(addresses_argument=True, considers_counter=False)
        r = _detect_from_signals(sig)
        assert r.fallacy.id == "T4_CONFIRMATION_BIAS"


# =============================================================================
#                           TAXONOMY SUMMARY TESTS
# =============================================================================

class TestTaxonomySummary:
    """Test get_taxonomy_summary() for LLM prompts."""

    def test_summary_nonempty(self):
        s = get_taxonomy_summary()
        assert len(s) > 1000

    def test_summary_has_all_domains(self):
        s = get_taxonomy_summary()
        for domain in ["D1 Recognition", "D2 Clarification", "D3 Framework",
                       "D4 Comparison", "D5 Inference", "D6 Reflection"]:
            assert domain in s, f"Missing domain: {domain}"

    def test_summary_has_types(self):
        s = get_taxonomy_summary()
        for t in ["Type 1:", "Type 3:", "Type 4:", "Type 5:"]:
            assert t in s, f"Missing type header: {t}"

    def test_summary_has_fallacy_ids(self):
        s = get_taxonomy_summary()
        # Check some well-known IDs are present
        for fid in ["D1_AD_HOMINEM", "D2_EITHER_OR", "D5_POST_HOC",
                     "D6_SUNK_COST", "T3_CIRCULAR_REASONING"]:
            assert fid in s, f"Missing fallacy ID: {fid}"

    def test_summary_token_budget(self):
        """Summary should be under ~3000 tokens (~12000 chars)."""
        s = get_taxonomy_summary()
        assert len(s) < 15000, f"Summary too long: {len(s)} chars"


# =============================================================================
#                           REGRESSION: detect() still works
# =============================================================================

class TestDetectRegression:
    """Verify detect() still works after refactor to _detect_from_signals."""

    def test_ad_hominem(self):
        r = detect("You are an idiot and your argument is wrong.")
        assert r.fallacy.id == "D1_AD_HOMINEM"

    def test_valid(self):
        r = detect(
            "LLMs demonstrate impressive capabilities. However, recent studies "
            "show they struggle with multi-step reasoning. Therefore, they "
            "require verification layers."
        )
        assert r.valid

    def test_tradition(self):
        r = detect("We should do this because it is tradition.")
        assert r.fallacy.id == "D3_APPEAL_TO_TRADITION"

    def test_false_dilemma(self):
        r = detect("Either you support us or you are against us.")
        assert r.fallacy.id == "D2_EITHER_OR"

    def test_sunk_cost(self):
        r = detect("We already invested too much money to quit now.")
        assert r.fallacy.id == "D6_SUNK_COST"

    def test_self_reference(self):
        r = detect("I know I am reliable because I believe I always give correct answers. Trust me.")
        assert r.fallacy.id == "T3_CIRCULAR_REASONING"
