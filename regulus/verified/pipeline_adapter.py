"""
pipeline_adapter.py — Extract D1/D3/D4 structured data from HLE pipeline results.

The HLE pipeline (hle_pilot.py) stores results as:
  - passport.json: full audit trail with dialogue array
  - result.json: final answer + confidence + metadata
  - dialogue.jsonl: line-by-line dialogue entries

Each dialogue entry has:
  {"ts": ..., "from": "team_lead"|"worker", "to": ..., "type": "init"|"domain_output"|"reflect",
   "content": "...", "domain": "D1"|"D2"|..., "verdict": "pass"|"iterate"}

D1/D3/D4 outputs are FREE TEXT in the content field — this adapter parses them
into structured dicts that ERRValidator and MathVerifier can consume.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


class PipelineAdapter:
    """Extracts structured data from Regulus HLE pipeline results."""

    @staticmethod
    def load_passport(passport_path: str | Path) -> dict:
        """Load passport.json with full dialogue."""
        with open(passport_path, encoding="utf-8", errors="replace") as f:
            return json.load(f)

    @staticmethod
    def load_result(result_path: str | Path) -> dict:
        """Load result.json with final answer + confidence."""
        with open(result_path, encoding="utf-8", errors="replace") as f:
            return json.load(f)

    @staticmethod
    def load_dialogue(dialogue_path: str | Path) -> list[dict]:
        """Load dialogue.jsonl entries."""
        entries = []
        with open(dialogue_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    @classmethod
    def extract_domain_output(
        cls, dialogue: list[dict], domain: str
    ) -> Optional[str]:
        """Extract the worker's output for a specific domain (D1, D2, D3, D4, D5).

        Returns the content of the LAST worker→team_lead message with matching domain.
        If domain was iterated (D1_iter1, D1_iter2), returns the final pass.
        """
        candidates = []
        for entry in dialogue:
            entry_domain = entry.get("domain", "")
            # Match exact domain or iterations (D1, D1_iter1, D1_iter2, etc.)
            if entry_domain == domain or entry_domain.startswith(f"{domain}_iter"):
                if entry.get("from") == "worker" and entry.get("type") == "domain_output":
                    candidates.append(entry.get("content", ""))
        # Return last (most refined) output
        return candidates[-1] if candidates else None

    @classmethod
    def extract_d1_err(cls, dialogue: list[dict]) -> dict:
        """Extract D1 E/R/R output as structured dict for ERRValidator.

        Parses elements (E1, E2, ...), roles, and rules from free text.
        Returns dict compatible with ERRValidator.validate_d1_output().
        """
        content = cls.extract_domain_output(dialogue, "D1")
        if not content:
            return {"elements": [], "roles": [], "rules": [], "dependencies": []}

        elements = cls._parse_elements(content)
        roles = cls._parse_roles(content, elements)
        rules = cls._parse_rules(content)
        dependencies = cls._parse_dependencies(content, elements)
        hierarchy_check = cls._parse_hierarchy_check(content)

        return {
            "elements": elements,
            "roles": roles,
            "rules": rules,
            "dependencies": dependencies,
            "err_hierarchy_check": hierarchy_check,
            "raw_content": content,
        }

    @classmethod
    def extract_d3_framework(cls, dialogue: list[dict]) -> str:
        """Extract the framework name from D3 output."""
        content = cls.extract_domain_output(dialogue, "D3")
        if not content:
            return "unknown"

        # Look for common framework declaration patterns
        patterns = [
            r"(?:Selected |Chosen |Using |Framework[:\s]+)([^\n.]+)",
            r"(?:framework|approach|method)[:\s]+([^\n.]+)",
            r"# D3.*?(?:Framework|Selection)\s*\n+(?:.*?\n)*?.*?(?:Selected|Chosen|Using)[:\s]+([^\n.]+)",
        ]

        for pattern in patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                framework = m.group(1).strip()
                # Clean up common prefixes
                framework = re.sub(r"^\*+|\*+$", "", framework).strip()
                if len(framework) > 5:  # Ignore trivially short matches
                    return framework

        # Fallback: extract first line after "# D3" header
        m = re.search(r"# D3[^\n]*\n+(.+)", content)
        if m:
            return m.group(1).strip()[:200]

        return content[:200]  # Last resort: first 200 chars

    @classmethod
    def extract_d4_data(cls, dialogue: list[dict]) -> dict:
        """Extract computation data from D4 for MathVerifier.

        Parses for:
        - Function values (f(a), f(b) for IVT)
        - Sets of values (for EVT)
        - Ratios (for convergence tests)
        - Contraction factors (for fixed point)
        """
        content = cls.extract_domain_output(dialogue, "D4")
        if not content:
            return {}

        data: dict = {"raw_content": content}

        # Try to extract function values (IVT candidates)
        fa_match = re.search(r"f\(a\)\s*=\s*([+-]?\d+\.?\d*)", content)
        fb_match = re.search(r"f\(b\)\s*=\s*([+-]?\d+\.?\d*)", content)
        if fa_match and fb_match:
            data["f_a"] = float(fa_match.group(1))
            data["f_b"] = float(fb_match.group(1))

        # Try to extract numerical values for EVT
        values_match = re.findall(
            r"(?:value|Area|area|score|result)[:\s]*=?\s*([+-]?\d+\.?\d*(?:e[+-]?\d+)?)",
            content, re.IGNORECASE,
        )
        if len(values_match) >= 2:
            data["values"] = [float(v) for v in values_match]

        # Try to extract ratio for convergence
        ratio_match = re.search(
            r"(?:ratio|r)\s*=\s*([+-]?\d+\.?\d*(?:/\d+)?)", content, re.IGNORECASE
        )
        if ratio_match:
            val = ratio_match.group(1)
            if "/" in val:
                num, den = val.split("/")
                data["ratio"] = float(num) / float(den)
            else:
                data["ratio"] = float(val)

        # Try to extract contraction factor
        factor_match = re.search(
            r"(?:contraction|factor|Lipschitz)\s*(?:constant|factor)?\s*=?\s*([+-]?\d+\.?\d*)",
            content, re.IGNORECASE,
        )
        if factor_match:
            data["factor"] = float(factor_match.group(1))

        # Extract key mathematical keywords for framework detection
        keywords = cls._extract_math_keywords(content)
        if keywords:
            data["detected_keywords"] = keywords

        return data

    @classmethod
    def extract_d5_answer(cls, dialogue: list[dict]) -> str:
        """Extract the final answer from D5 output."""
        content = cls.extract_domain_output(dialogue, "D5")
        if not content:
            return ""

        # Look for explicit answer declaration
        patterns = [
            r"(?:^|\n)\s*(?:answer|ANSWER)[:\s]+(.+?)(?:\n|$)",
            r"(?:^|\n)\s*(?:CONCLUSION|conclusion)[:\s]+(.+?)(?:\n|$)",
            r"Answer:\s*\**([A-G])\**",
        ]

        for pattern in patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return ""

    @classmethod
    def extract_confidence(cls, result: dict) -> tuple[float, float]:
        """Extract (self_confidence, scorecard_confidence) from result.json."""
        conf = result.get("confidence") or {}
        if not isinstance(conf, dict):
            conf = {}

        # Handle both scorecard_v2_dual and scorecard_v2 formats
        # Use explicit None checks — 0 is a valid confidence value
        c_comp = conf.get("c_computation")
        if c_comp is None:
            c_comp = conf.get("worker")
        if c_comp is None:
            c_comp = 50

        c_approach = conf.get("c_approach")
        if c_approach is None:
            c_approach = conf.get("tl")
        if c_approach is None:
            c_approach = 50

        final = conf.get("final")
        if final is None:
            final = min(c_comp, c_approach)

        return (float(c_comp), float(final))

    @classmethod
    def extract_all(cls, run_dir: str | Path) -> dict:
        """Extract all structured data from a single question run.

        Args:
            run_dir: Directory containing result.json, passport.json, dialogue.jsonl

        Returns:
            {
                "result": {...},
                "d1_err": {...},
                "d3_framework": "...",
                "d4_data": {...},
                "d5_answer": "...",
                "confidence": (self, scorecard),
            }
        """
        run_dir = Path(run_dir)
        result = cls.load_result(run_dir / "result.json")

        # Load dialogue from passport.json or dialogue.jsonl
        passport_path = run_dir / "passport.json"
        dialogue_path = run_dir / "dialogue.jsonl"

        if passport_path.exists():
            passport = cls.load_passport(passport_path)
            dialogue = passport.get("dialogue", [])
        elif dialogue_path.exists():
            dialogue = cls.load_dialogue(dialogue_path)
        else:
            dialogue = []

        return {
            "result": result,
            "d1_err": cls.extract_d1_err(dialogue),
            "d3_framework": cls.extract_d3_framework(dialogue),
            "d4_data": cls.extract_d4_data(dialogue),
            "d5_answer": cls.extract_d5_answer(dialogue),
            "confidence": cls.extract_confidence(result),
        }

    # ── Internal parsers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_elements(content: str) -> list[dict]:
        """Parse E1, E2, ... elements from D1 content."""
        elements = []
        # Pattern: **E1**: description or E1: description or - E1: description
        pattern = r"(?:^|\n)\s*[-*]*\s*\*?\*?\s*(E\d+)\s*\*?\*?\s*[:\-–—]+\s*(.+?)(?=\n|$)"
        for m in re.finditer(pattern, content, re.MULTILINE):
            elements.append({
                "id": m.group(1),
                "description": m.group(2).strip(),
            })

        if not elements:
            # Fallback: look for bullet-pointed elements
            pattern2 = r"(?:^|\n)\s*[-•]\s*(.+?)(?:\n|$)"
            for i, m in enumerate(re.finditer(pattern2, content)):
                text = m.group(1).strip()
                if text and not text.startswith("#"):
                    elements.append({
                        "id": f"E{i+1}",
                        "description": text,
                    })
                if len(elements) >= 20:
                    break

        return elements

    @staticmethod
    def _parse_roles(content: str, elements: list[dict]) -> list[dict]:
        """Parse role assignments from D1 content."""
        roles = []
        # Assign default roles for all elements found
        for elem in elements:
            roles.append({
                "element_id": elem["id"],
                "role": "component",  # Default role
            })

        # Look for explicit role mentions
        role_pattern = r"(E\d+)\s*(?:serves as|acts as|is|plays)\s+(?:the\s+)?(\w+)"
        for m in re.finditer(role_pattern, content, re.IGNORECASE):
            eid = m.group(1)
            role_name = m.group(2).lower()
            # Update existing role
            for r in roles:
                if r["element_id"] == eid:
                    r["role"] = role_name
                    break

        return roles

    @staticmethod
    def _parse_rules(content: str) -> list[dict]:
        """Parse rules/constraints from D1 content."""
        rules = []
        # Look for rules section or constraint mentions
        rule_patterns = [
            r"(?:^|\n)\s*[-*]*\s*\*?\*?\s*(R\d+)\s*\*?\*?\s*[:\-–—]+\s*(.+?)(?=\n|$)",
            r"(?:rule|constraint|condition)\s*(\d+)\s*[:\-–—]+\s*(.+?)(?=\n|$)",
        ]

        for pattern in rule_patterns:
            for m in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                rules.append({
                    "id": m.group(1) if m.group(1).startswith("R") else f"R{m.group(1)}",
                    "description": m.group(2).strip(),
                })

        return rules

    @staticmethod
    def _parse_dependencies(content: str, elements: list[dict]) -> list[dict]:
        """Parse dependency relations between elements."""
        deps = []
        # Look for dependency indicators
        dep_pattern = r"(E\d+)\s*(?:depends on|requires|uses|→|->)\s*(E\d+)"
        for m in re.finditer(dep_pattern, content, re.IGNORECASE):
            deps.append({
                "from": m.group(1),
                "to": m.group(2),
            })
        return deps

    @staticmethod
    def _parse_hierarchy_check(content: str) -> dict:
        """Parse D1's self-reported hierarchy check."""
        check = {}
        if re.search(r"no.?circular.?dep", content, re.IGNORECASE):
            check["no_circular_dependencies"] = True
        if re.search(r"elements.?ground", content, re.IGNORECASE):
            check["elements_ground_system"] = True
        if re.search(r"hierarchy.*?valid|valid.*?hierarchy", content, re.IGNORECASE):
            check["hierarchy_valid"] = True
        return check

    @staticmethod
    def _extract_math_keywords(content: str) -> list[str]:
        """Extract mathematical keywords from D4 content for framework detection."""
        keyword_map = {
            "ivt": ["intermediate value", "ivt", "root finding", "zero crossing", "bisection"],
            "evt": ["extreme value", "evt", "maximum", "minimum", "optimization", "argmax", "argmin"],
            "convergence": ["convergence", "series", "ratio test", "geometric series", "radius of convergence"],
            "contraction": ["fixed point", "contraction", "banach", "picard", "iterative"],
            "crown": ["crown", "interval bound", "neural network", "ibp"],
        }
        found = []
        content_lower = content.lower()
        for category, keywords in keyword_map.items():
            if any(kw in content_lower for kw in keywords):
                found.append(category)
        return found
