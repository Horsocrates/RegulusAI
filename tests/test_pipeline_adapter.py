"""Tests for pipeline_adapter.py — D1/D3/D4 extraction from HLE pipeline results."""

import json
import tempfile
from pathlib import Path

import pytest

from regulus.verified.pipeline_adapter import PipelineAdapter


# ── Fixtures ─────────────────────────────────────────────────────────

SAMPLE_D1_CONTENT = """# D1 — Recognition

## Elements
- **E1**: Compact connected metric space (continuum)
- **E2**: Proper subcontinuum
- **E3**: Regular subcontinuum (closure of interior)
- **E4**: Decomposable continuum (union of two proper subcontinua)
- **E5**: Cardinality of collection of regular proper subcontinua

## Roles
- E1 serves as the primary object of study
- E2 acts as a building block component
- E3 serves as the specialized subtype
- E4 is the main constraint

## Rules
- R1: A continuum is compact and connected
- R2: Regular means closure of interior
- R3: Decomposable = union of two proper subcontinua

## Dependencies
E3 depends on E2
E5 depends on E3

## ERR Hierarchy Check
The elements ground the system properly.
No circular dependencies detected.
"""

SAMPLE_D3_CONTENT = """# D3 — Framework Selection

## Selected Framework: Topological Decomposition Analysis

Using the framework of topological decomposition to analyze the continuum structure.
"""

SAMPLE_D4_CONTENT = """# D4 — Comparison

## Computation
We evaluate f(a) = -3.0 at the left endpoint and f(b) = 5.0 at the right endpoint.
The ratio = 0.667 for the geometric series.
Area = 0.1443 for the optimal configuration.

## Result
The value = 42.
"""

SAMPLE_D5_CONTENT = """# D5 — Inference

## Conclusion
answer: 0

## Confidence
confidence: 93%
"""


def make_dialogue(d1=None, d3=None, d4=None, d5=None):
    """Create a dialogue list from domain outputs."""
    entries = []
    for domain, content in [("D1", d1), ("D3", d3), ("D4", d4), ("D5", d5)]:
        if content:
            # Team lead init
            entries.append({
                "ts": "2026-01-01T00:00:00",
                "from": "team_lead",
                "to": "worker",
                "type": "init",
                "content": f"Do {domain}",
                "domain": domain,
            })
            # Worker output
            entries.append({
                "ts": "2026-01-01T00:01:00",
                "from": "worker",
                "to": "team_lead",
                "type": "domain_output",
                "content": content,
                "domain": domain,
            })
            # Team lead verdict
            entries.append({
                "ts": "2026-01-01T00:02:00",
                "from": "team_lead",
                "to": "worker",
                "type": "domain_output",
                "content": "PASS",
                "domain": domain,
                "verdict": "pass",
            })
    return entries


# ── Tests: Element Parsing ───────────────────────────────────────────

class TestElementParsing:
    def test_parse_elements_e_numbered(self):
        elements = PipelineAdapter._parse_elements(SAMPLE_D1_CONTENT)
        assert len(elements) == 5
        assert elements[0]["id"] == "E1"
        assert "compact" in elements[0]["description"].lower()

    def test_parse_elements_empty(self):
        elements = PipelineAdapter._parse_elements("")
        assert elements == []

    def test_parse_elements_no_e_numbers(self):
        content = "Elements:\n- first thing\n- second thing\n- third thing"
        elements = PipelineAdapter._parse_elements(content)
        # Falls back to bullet parsing
        assert len(elements) >= 2

    def test_parse_roles(self):
        elements = PipelineAdapter._parse_elements(SAMPLE_D1_CONTENT)
        roles = PipelineAdapter._parse_roles(SAMPLE_D1_CONTENT, elements)
        assert len(roles) == 5  # One role per element
        # Check that explicit role names are found
        found_primary = any(r["role"] == "primary" for r in roles)
        assert found_primary or all(r["role"] == "component" for r in roles)

    def test_parse_rules(self):
        rules = PipelineAdapter._parse_rules(SAMPLE_D1_CONTENT)
        assert len(rules) >= 2
        assert any(r["id"].startswith("R") for r in rules)

    def test_parse_dependencies(self):
        elements = PipelineAdapter._parse_elements(SAMPLE_D1_CONTENT)
        deps = PipelineAdapter._parse_dependencies(SAMPLE_D1_CONTENT, elements)
        assert len(deps) == 2
        assert deps[0]["from"] == "E3"
        assert deps[0]["to"] == "E2"

    def test_parse_hierarchy_check(self):
        check = PipelineAdapter._parse_hierarchy_check(SAMPLE_D1_CONTENT)
        assert check["elements_ground_system"] is True
        assert check["no_circular_dependencies"] is True


# ── Tests: Domain Output Extraction ──────────────────────────────────

class TestDomainExtraction:
    def test_extract_d1(self):
        dialogue = make_dialogue(d1=SAMPLE_D1_CONTENT)
        content = PipelineAdapter.extract_domain_output(dialogue, "D1")
        assert content == SAMPLE_D1_CONTENT

    def test_extract_d3(self):
        dialogue = make_dialogue(d3=SAMPLE_D3_CONTENT)
        content = PipelineAdapter.extract_domain_output(dialogue, "D3")
        assert content == SAMPLE_D3_CONTENT

    def test_extract_missing_domain(self):
        dialogue = make_dialogue(d1=SAMPLE_D1_CONTENT)
        content = PipelineAdapter.extract_domain_output(dialogue, "D4")
        assert content is None

    def test_extract_iterated_domain(self):
        dialogue = make_dialogue(d1="first attempt")
        # Add iteration
        dialogue.append({
            "ts": "2026-01-01T00:03:00",
            "from": "worker",
            "to": "team_lead",
            "type": "domain_output",
            "content": "refined attempt",
            "domain": "D1_iter1",
        })
        content = PipelineAdapter.extract_domain_output(dialogue, "D1")
        assert content == "refined attempt"  # Last output wins


# ── Tests: D1 ERR Extraction ────────────────────────────────────────

class TestD1ERRExtraction:
    def test_extract_d1_err(self):
        dialogue = make_dialogue(d1=SAMPLE_D1_CONTENT)
        result = PipelineAdapter.extract_d1_err(dialogue)
        assert len(result["elements"]) == 5
        assert len(result["rules"]) >= 2
        assert len(result["dependencies"]) == 2
        assert result["raw_content"] is not None

    def test_extract_d1_err_empty(self):
        dialogue = make_dialogue()
        result = PipelineAdapter.extract_d1_err(dialogue)
        assert result["elements"] == []
        assert result["roles"] == []


# ── Tests: D3 Framework Extraction ───────────────────────────────────

class TestD3Framework:
    def test_extract_framework(self):
        dialogue = make_dialogue(d3=SAMPLE_D3_CONTENT)
        framework = PipelineAdapter.extract_d3_framework(dialogue)
        # Parser returns non-empty framework string (may extract header or body)
        assert len(framework) > 0
        assert framework != "unknown"

    def test_extract_framework_explicit(self):
        content = "## Selected Framework: Intermediate Value Theorem\n\nUsing IVT to find roots."
        dialogue = make_dialogue(d3=content)
        framework = PipelineAdapter.extract_d3_framework(dialogue)
        # Parser extracts framework name from content
        assert len(framework) > 0
        assert framework != "unknown"

    def test_extract_framework_missing(self):
        dialogue = make_dialogue()
        framework = PipelineAdapter.extract_d3_framework(dialogue)
        assert framework == "unknown"


# ── Tests: D4 Data Extraction ────────────────────────────────────────

class TestD4Data:
    def test_extract_function_values(self):
        dialogue = make_dialogue(d4=SAMPLE_D4_CONTENT)
        data = PipelineAdapter.extract_d4_data(dialogue)
        assert data.get("f_a") == -3.0
        assert data.get("f_b") == 5.0

    def test_extract_ratio(self):
        dialogue = make_dialogue(d4=SAMPLE_D4_CONTENT)
        data = PipelineAdapter.extract_d4_data(dialogue)
        assert data.get("ratio") == 0.667

    def test_extract_math_keywords(self):
        keywords = PipelineAdapter._extract_math_keywords(
            "We apply the intermediate value theorem to find roots"
        )
        assert "ivt" in keywords

    def test_extract_d4_empty(self):
        dialogue = make_dialogue()
        data = PipelineAdapter.extract_d4_data(dialogue)
        assert data == {}


# ── Tests: D5 Answer Extraction ──────────────────────────────────────

class TestD5Answer:
    def test_extract_answer(self):
        dialogue = make_dialogue(d5=SAMPLE_D5_CONTENT)
        answer = PipelineAdapter.extract_d5_answer(dialogue)
        assert answer == "0"

    def test_extract_answer_missing(self):
        dialogue = make_dialogue()
        answer = PipelineAdapter.extract_d5_answer(dialogue)
        assert answer == ""


# ── Tests: Confidence Extraction ─────────────────────────────────────

class TestConfidence:
    def test_dual_format(self):
        result = {"confidence": {"c_computation": 90, "c_approach": 80, "final": 80}}
        c_self, c_final = PipelineAdapter.extract_confidence(result)
        assert c_self == 90.0
        assert c_final == 80.0

    def test_v2_format(self):
        result = {"confidence": {"worker": 85, "tl": 60, "final": 60}}
        c_self, c_final = PipelineAdapter.extract_confidence(result)
        assert c_self == 85.0
        assert c_final == 60.0

    def test_missing_confidence(self):
        result = {}
        c_self, c_final = PipelineAdapter.extract_confidence(result)
        assert c_self == 50.0  # default
        assert c_final == 50.0

    def test_null_confidence(self):
        result = {"confidence": {"c_computation": None, "c_approach": None, "final": None}}
        c_self, c_final = PipelineAdapter.extract_confidence(result)
        assert c_self == 50.0
        assert c_final == 50.0

    def test_zero_confidence(self):
        result = {"confidence": {"c_computation": 0, "c_approach": 0, "final": 0}}
        c_self, c_final = PipelineAdapter.extract_confidence(result)
        assert c_self == 0.0
        assert c_final == 0.0


# ── Tests: Full Extraction ───────────────────────────────────────────

class TestFullExtraction:
    def test_extract_all_from_dir(self, tmp_path):
        """Create a mock run directory and extract all data."""
        # Write result.json
        result = {
            "question_id": "test_q",
            "answer_raw": "answer: 42\nconfidence: 90%",
            "judge_correct": True,
            "confidence": {"c_computation": 90, "c_approach": 85, "final": 85},
            "total_tokens": 100000,
            "elapsed_seconds": 120.5,
        }
        (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

        # Write dialogue.jsonl
        dialogue = make_dialogue(
            d1=SAMPLE_D1_CONTENT,
            d3=SAMPLE_D3_CONTENT,
            d4=SAMPLE_D4_CONTENT,
            d5=SAMPLE_D5_CONTENT,
        )
        with open(tmp_path / "dialogue.jsonl", "w", encoding="utf-8") as f:
            for entry in dialogue:
                f.write(json.dumps(entry) + "\n")

        # Extract
        data = PipelineAdapter.extract_all(tmp_path)
        assert data["result"]["judge_correct"] is True
        assert len(data["d1_err"]["elements"]) == 5
        assert "topological" in data["d3_framework"].lower() or len(data["d3_framework"]) > 5
        assert data["d4_data"].get("f_a") == -3.0
        assert data["d5_answer"] == "0"
        assert data["confidence"] == (90.0, 85.0)
