"""Tests for the robust multi-stage audit JSON parser (v1.0b-fix)."""

import json
import pytest

from regulus.audit.auditor import (
    _extract_json_object,
    _fix_common_json_issues,
    _parse_audit_response,
    _partial_parse_domains,
    _build_audit_result,
)


# ─── Minimal valid audit JSON for reuse ───

def _minimal_audit_json(overrides: dict | None = None) -> dict:
    """Return a minimal valid audit JSON structure."""
    base = {
        "domains": [
            {
                "domain": f"D{i}",
                "present": True,
                "e_exists": True,
                "r_exists": True,
                "rule_exists": True,
                "s_exists": True,
                "deps_declared": True,
                "l1_l3_ok": True,
                "l5_ok": True,
                "weight": 70,
                "issues": [],
                "segment_summary": f"D{i} segment",
            }
            for i in range(1, 7)
        ],
        "violation_patterns": [],
        "overall_issues": [],
        "parse_quality": 0.85,
    }
    # Add domain-specific fields
    base["domains"][0]["d1_depth"] = 3
    base["domains"][1]["d2_depth"] = 3
    base["domains"][2]["d3_objectivity_pass"] = True
    base["domains"][3]["d4_aristotle_ok"] = True
    base["domains"][4]["d5_certainty_type"] = "probabilistic"
    base["domains"][5]["d6_genuine"] = True
    if overrides:
        base.update(overrides)
    return base


# ═══════════════════════════════════════════════════
# TestExtractJsonObject
# ═══════════════════════════════════════════════════

class TestExtractJsonObject:
    """Tests for _extract_json_object bracket-counting extraction."""

    def test_clean_json(self):
        obj = '{"key": "value"}'
        assert _extract_json_object(obj) == obj

    def test_markdown_fences(self):
        raw = '```json\n{"key": "value"}\n```'
        result = _extract_json_object(raw)
        assert result is not None
        assert json.loads(result) == {"key": "value"}

    def test_preamble_text(self):
        raw = 'Here is my analysis:\n\n{"key": "value"}'
        result = _extract_json_object(raw)
        assert result is not None
        assert json.loads(result) == {"key": "value"}

    def test_trailing_text(self):
        raw = '{"key": "value"}\n\nI hope this helps!'
        result = _extract_json_object(raw)
        assert result is not None
        assert json.loads(result) == {"key": "value"}

    def test_no_json(self):
        raw = "This response has no JSON at all."
        assert _extract_json_object(raw) is None

    def test_nested_braces(self):
        raw = '{"outer": {"inner": "val"}, "list": [{"a": 1}]}'
        result = _extract_json_object(raw)
        assert result is not None
        assert json.loads(result)["outer"]["inner"] == "val"

    def test_braces_in_strings(self):
        raw = '{"text": "a { b } c", "ok": true}'
        result = _extract_json_object(raw)
        assert result is not None
        data = json.loads(result)
        assert data["text"] == "a { b } c"
        assert data["ok"] is True

    def test_escaped_quotes(self):
        raw = r'{"text": "say \"hello\"", "n": 1}'
        result = _extract_json_object(raw)
        assert result is not None
        data = json.loads(result)
        assert data["n"] == 1

    def test_unclosed_returns_to_end(self):
        raw = '{"key": "value"'
        result = _extract_json_object(raw)
        # Should return from { to end even if unclosed
        assert result is not None
        assert result.startswith("{")


# ═══════════════════════════════════════════════════
# TestFixCommonJsonIssues
# ═══════════════════════════════════════════════════

class TestFixCommonJsonIssues:
    """Tests for _fix_common_json_issues recovery."""

    def test_trailing_comma_before_brace(self):
        bad = '{"a": 1, "b": 2,}'
        fixed = _fix_common_json_issues(bad)
        assert json.loads(fixed) == {"a": 1, "b": 2}

    def test_trailing_comma_before_bracket(self):
        bad = '{"a": [1, 2, 3,]}'
        fixed = _fix_common_json_issues(bad)
        assert json.loads(fixed) == {"a": [1, 2, 3]}

    def test_unclosed_brace(self):
        bad = '{"a": {"b": 1}'
        fixed = _fix_common_json_issues(bad)
        assert json.loads(fixed) == {"a": {"b": 1}}

    def test_unclosed_bracket(self):
        bad = '{"a": [1, 2'
        fixed = _fix_common_json_issues(bad)
        data = json.loads(fixed)
        assert data["a"] == [1, 2]

    def test_multiple_trailing_commas(self):
        bad = '{"a": [1,], "b": {"c": 2,},}'
        fixed = _fix_common_json_issues(bad)
        data = json.loads(fixed)
        assert data == {"a": [1], "b": {"c": 2}}

    def test_already_valid(self):
        good = '{"a": 1}'
        assert _fix_common_json_issues(good) == good


# ═══════════════════════════════════════════════════
# TestParseAuditResponse
# ═══════════════════════════════════════════════════

class TestParseAuditResponse:
    """Tests for the full _parse_audit_response pipeline."""

    def test_valid_minimal(self):
        data = _minimal_audit_json()
        raw = json.dumps(data)
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6
        assert result.domains[0].domain == "D1"
        assert result.domains[0].d1_depth == 3
        assert result.parse_quality == 0.85

    def test_trailing_comma_recovery(self):
        data = _minimal_audit_json()
        raw = json.dumps(data)
        # Inject trailing comma before last }
        raw = raw[:-1] + ",}"
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6

    def test_preamble_recovery(self):
        data = _minimal_audit_json()
        raw = "Here is my analysis:\n\n" + json.dumps(data)
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6
        assert result.domains[0].present is True

    def test_markdown_fence_recovery(self):
        data = _minimal_audit_json()
        raw = "```json\n" + json.dumps(data) + "\n```"
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6

    def test_d3_objectivity_zero_gate(self):
        data = _minimal_audit_json()
        data["domains"][2]["d3_objectivity_pass"] = False
        data["domains"][2]["weight"] = 70
        raw = json.dumps(data)
        result = _parse_audit_response(raw)
        assert result.domains[2].weight == 0  # Forced to 0 by Zero-Gate

    def test_d1_deps_always_true(self):
        data = _minimal_audit_json()
        data["domains"][0]["deps_declared"] = False  # Should be overridden
        raw = json.dumps(data)
        result = _parse_audit_response(raw)
        assert result.domains[0].deps_declared is True  # D1 is root

    def test_missing_domains_filled(self):
        data = _minimal_audit_json()
        data["domains"] = data["domains"][:3]  # Only D1-D3
        raw = json.dumps(data)
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6
        assert result.domains[3].present is False  # D4 filled in
        assert result.domains[4].present is False
        assert result.domains[5].present is False

    def test_no_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_audit_response("No JSON here at all.")


# ═══════════════════════════════════════════════════
# TestPartialParseDomains
# ═══════════════════════════════════════════════════

class TestPartialParseDomains:
    """Tests for _partial_parse_domains last-resort extraction."""

    def test_individual_domain_extraction(self):
        raw = """
        Some text before
        {"domain": "D1", "present": true, "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true, "weight": 75}
        some text
        {"domain": "D2", "present": true, "e_exists": true, "r_exists": true, "rule_exists": true, "s_exists": true, "weight": 60}
        more text
        """
        result = _partial_parse_domains(raw)
        assert result is not None
        assert len(result.domains) == 6  # 2 found + 4 filled
        d1 = next(d for d in result.domains if d.domain == "D1")
        assert d1.present is True
        assert d1.weight == 75

    def test_no_domains_returns_none(self):
        assert _partial_parse_domains("no domain objects here") is None

    def test_violation_extraction(self):
        raw = '''
        {"domain": "D1", "present": true, "weight": 70}
        {"domain": "D2", "present": true, "weight": 60}
        "violation_patterns": ["PREMATURE_CLOSURE", "ORDER_INVERSION"]
        '''
        result = _partial_parse_domains(raw)
        assert result is not None
        assert "PREMATURE_CLOSURE" in result.violation_patterns
        assert "ORDER_INVERSION" in result.violation_patterns

    def test_parse_quality_is_low(self):
        raw = '{"domain": "D1", "present": true, "weight": 70}'
        result = _partial_parse_domains(raw)
        assert result is not None
        assert result.parse_quality == 0.3  # Low confidence


# ═══════════════════════════════════════════════════
# TestBuildAuditResult
# ═══════════════════════════════════════════════════

class TestBuildAuditResult:
    """Tests for _build_audit_result data → AuditResult conversion."""

    def test_basic_conversion(self):
        data = _minimal_audit_json()
        result = _build_audit_result(data)
        assert len(result.domains) == 6
        assert result.violation_patterns == []
        assert result.parse_quality == 0.85

    def test_domain_specific_fields(self):
        data = _minimal_audit_json()
        result = _build_audit_result(data)
        assert result.domains[0].d1_depth == 3
        assert result.domains[1].d2_depth == 3
        assert result.domains[2].d3_objectivity_pass is True
        assert result.domains[3].d4_aristotle_ok is True
        assert result.domains[4].d5_certainty_type == "probabilistic"
        assert result.domains[5].d6_genuine is True

    def test_violations_preserved(self):
        data = _minimal_audit_json({"violation_patterns": ["PREMATURE_CLOSURE"]})
        result = _build_audit_result(data)
        assert result.violation_patterns == ["PREMATURE_CLOSURE"]
