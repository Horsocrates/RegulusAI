"""Content-level validation based on actual domain instruction requirements.

Structure validation: "does d4_output have computation_trace field?" -> yes/no
Content validation: "does computation_trace show ALL steps?" -> quality score

Maps to REGULUS_CORE.md scorecard:
  D1: 0.10 weight — ERR decomposition, depth, key challenge
  D2: 0.15 weight — proof chains, flag resolution, definition depth
  D3: 0.10 weight — framework named, L2 test, alternatives
  D4: 0.35 weight — computation trace, disconfirming evidence, Aristotle
  D5: 0.30 weight — inference chain, L5 direction, cross-verification

Resolves HLE calibration gap: 89pp -> target <50pp via content scoring + hard caps.
"""

from __future__ import annotations

from typing import Optional


class ContentValidator:
    """Validates domain outputs against actual instruction requirements.

    Each score_dN method returns (score: int 0-100, issues: list[str]).
    Score thresholds:
      0    = Zero-Gate failure (missing essential fields)
      1-39 = Structural failure (gate should ITERATE)
      40-69 = Weak (apply hard caps)
      70-89 = Adequate
      90-100 = Strong
    """

    # REGULUS_CORE.md §5: Domain weights (for weighted aggregation variant)
    WEIGHTS = {1: 0.10, 2: 0.15, 3: 0.10, 4: 0.35, 5: 0.30}

    def score_d1(self, output: dict) -> tuple[int, list[str]]:
        """Score D1 output based on d1-recognize-v3.md requirements.

        Required: ELEMENTS, ROLES, RULES, STATUS, DEPENDENCIES, KEY_CHALLENGE
        Checklist: 12 items (each_component_exactly_once, no_self_reference, etc.)
        """
        score = 100
        issues = []

        # ─── Zero-Gate checks ───
        elements = output.get("ELEMENTS", output.get("elements", {}))
        roles = output.get("ROLES", output.get("roles", {}))
        rules = output.get("RULES", output.get("rules", {}))

        if not elements:
            return 0, ["ZERO-GATE: No elements recognized"]
        if not roles:
            score -= 25
            issues.append("No roles assigned to elements")
        if not rules:
            score -= 20
            issues.append("No rules connecting elements")

        # ─── Content checks (from d1-recognize-v3.md) ───

        # Every element has a role?
        if isinstance(elements, dict) and isinstance(roles, dict):
            orphans = set(elements.keys()) - set(roles.keys())
            if orphans:
                score -= 15
                issues.append(f"L4: elements without roles: {orphans}")

        # Status tracking?
        status = output.get("STATUS", output.get("status", {}))
        if not status:
            score -= 10
            issues.append("No status tracking for elements")
        elif isinstance(status, dict):
            has_unknown = any(
                v in ("unknown", "Unknown") for v in status.values()
            )
            if not has_unknown and len(elements) > 2:
                score -= 10
                issues.append("No unknown elements — what is the problem?")

        # Dependencies?
        deps = output.get("DEPENDENCIES", output.get("dependencies", {}))
        if not deps:
            score -= 10
            issues.append("No dependencies mapped")

        # Key challenge present and Level 3+?
        key_challenge = output.get(
            "KEY_CHALLENGE", output.get("key_challenge", "")
        )
        if not key_challenge:
            score -= 15
            issues.append("No key challenge identified")

        depth = output.get("DEPTH_ACHIEVED", output.get("depth_achieved", 0))
        if isinstance(depth, str):
            depth = {
                "data": 1, "Data": 1,
                "info": 2, "information": 2, "Information": 2,
                "quality": 3, "Quality": 3,
                "character": 4, "characteristic": 4, "Character": 4,
            }.get(depth, 0)
        if isinstance(depth, (int, float)) and depth < 3:
            score -= 15
            issues.append(f"Depth {depth} < 3 — insufficient for HLE-level questions")

        # D1 well-formedness checklist?
        checklist = output.get("D1_CHECKLIST", output.get("d1_checklist", {}))
        if isinstance(checklist, dict):
            failed = [k for k, v in checklist.items()
                      if v in (False, "☐", "FAIL", "fail", "no")]
            if failed:
                score -= len(failed) * 3
                issues.append(f"D1 checklist failures: {failed}")
        elif not checklist:
            score -= 5
            issues.append("No D1 well-formedness checklist")

        # ERR hierarchy check?
        hier = output.get(
            "ERRS_QUALITY", output.get("err_hierarchy_check", {})
        )
        if not hier:
            score -= 5
            issues.append("No ERR quality/hierarchy check")

        return max(0, score), issues

    def score_d2(
        self, output: dict, d1_output: dict
    ) -> tuple[int, list[str]]:
        """Score D2 based on d2-clarify-v3.md requirements.

        Required: CLARIFIED_ELEMENTS, HIDDEN_CONTENT_SURFACED
        """
        score = 100
        issues = []

        # ─── Zero-Gate ───
        definitions = output.get(
            "CLARIFIED_ELEMENTS",
            output.get("clarified_elements", output.get("definitions", {})),
        )
        if not definitions:
            return 0, ["ZERO-GATE: No clarified elements / definitions"]

        # ─── Content checks ───

        # ERR consumed? (D2 must reference D1 elements)
        d1_elements = d1_output.get(
            "ELEMENTS", d1_output.get("elements", {})
        )
        if isinstance(d1_elements, dict):
            d1_count = len(d1_elements)
        elif isinstance(d1_elements, list):
            d1_count = len(d1_elements)
        else:
            d1_count = 0

        def_count = (
            len(definitions) if isinstance(definitions, (dict, list)) else 0
        )
        if d1_count > 0 and def_count < d1_count * 0.5:
            score -= 20
            issues.append(
                f"Only {def_count}/{d1_count} elements clarified — incomplete"
            )

        # Depth levels specified?
        if isinstance(definitions, dict):
            for k, v in definitions.items():
                if isinstance(v, dict):
                    depth = v.get("Depth", v.get("depth_level", ""))
                    if depth in ("nominal", "dictionary", "Nominal", "Dictionary"):
                        score -= 5
                        issues.append(
                            f"Element {k}: depth only '{depth}' (need functional+)"
                        )

        # Hidden assumptions?
        hidden = output.get(
            "HIDDEN_CONTENT_SURFACED",
            output.get("hidden_assumptions", {}),
        )
        if not hidden:
            score -= 10
            issues.append("No hidden content surfaced")

        # Ambiguity resolution?
        ambig = output.get(
            "AMBIGUITIES_RESOLVED",
            output.get("equivocation_check", None),
        )
        if ambig is None:
            score -= 10
            issues.append("No equivocation / ambiguity check (L1)")

        # Premise coherence?
        if isinstance(hidden, dict):
            coherence = hidden.get(
                "Premise_coherence", hidden.get("premise_coherence", "")
            )
            if not coherence:
                score -= 5
                issues.append("No premise coherence check")

        # D2 checklist?
        checklist = output.get("D2_CHECKLIST", output.get("d2_checklist", {}))
        if isinstance(checklist, dict):
            failed = [k for k, v in checklist.items()
                      if v in (False, "☐", "FAIL", "fail", "no")]
            if failed:
                score -= len(failed) * 3
                issues.append(f"D2 checklist failures: {failed}")
        elif not checklist:
            score -= 5
            issues.append("No D2 well-formedness checklist")

        # Critical clarification?
        critical = output.get(
            "CRITICAL_CLARIFICATION",
            output.get("critical_clarification", ""),
        )
        if not critical:
            score -= 5
            issues.append("No critical clarification identified")

        return max(0, score), issues

    def score_d3(self, output: dict) -> tuple[int, list[str]]:
        """Score D3 based on d3-framework-v3.md requirements.

        Required: FRAMEWORK (named), ALTERNATIVES_CONSIDERED, PRE_SELECTION_CHECK
        """
        score = 100
        issues = []

        # ─── Zero-Gate ───
        framework = output.get("FRAMEWORK", output.get("framework", {}))
        if isinstance(framework, dict):
            fname = framework.get("Name", framework.get("name", ""))
        else:
            fname = str(framework) if framework else ""

        if not fname:
            return 0, ["ZERO-GATE: No framework named"]

        # ─── Content checks ───

        # Pre-selection check?
        pre_check = output.get(
            "PRE_SELECTION_CHECK", output.get("pre_selection_check", {})
        )
        if not pre_check:
            score -= 20
            issues.append("No pre-selection check — confirmation bias risk")
        elif isinstance(pre_check, dict):
            permits = pre_check.get("Permits_multiple_outcomes",
                                     pre_check.get("permits_multiple_outcomes"))
            if permits in (False, "N", "No"):
                score -= 15
                issues.append("Framework does NOT permit multiple outcomes")

        # Dual criterion (nature + purpose)?
        if isinstance(framework, dict):
            has_nature = bool(
                framework.get("Match_Nature",
                               framework.get("match_nature", ""))
            )
            has_purpose = bool(
                framework.get("Match_Purpose",
                               framework.get("match_purpose", ""))
            )
            if not has_nature or not has_purpose:
                score -= 15
                issues.append(
                    "Dual criterion not satisfied "
                    f"(nature={has_nature}, purpose={has_purpose})"
                )

        # Alternatives considered?
        alts = output.get(
            "ALTERNATIVES_CONSIDERED",
            output.get("alternatives_considered", {}),
        )
        if not alts:
            score -= 20
            issues.append("Zero alternatives considered (HC9 → cap 70%)")
        elif isinstance(alts, dict) and len(alts) < 1:
            score -= 20
            issues.append("Zero alternatives (need at least 1)")

        # Criteria for D4?
        if isinstance(framework, dict):
            criteria = framework.get(
                "Criteria_for_D4",
                framework.get("criteria", output.get("criteria", {})),
            )
            if not criteria:
                score -= 15
                issues.append("No concrete criteria defined for D4")

        # Hierarchy check?
        hier = output.get("HIERARCHY_CHECK", output.get("hierarchy_check", {}))
        if not hier:
            score -= 5
            issues.append("No hierarchy check (L5: general before specific)")

        # Framework limitations?
        limits = output.get(
            "FRAMEWORK_LIMITATIONS",
            output.get("framework_limitations", ""),
        )
        if not limits:
            score -= 5
            issues.append("No framework limitations acknowledged")

        # D3 checklist?
        checklist = output.get("D3_CHECKLIST", output.get("d3_checklist", {}))
        if isinstance(checklist, dict):
            failed = [k for k, v in checklist.items()
                      if v in (False, "☐", "FAIL", "fail", "no")]
            if failed:
                score -= len(failed) * 3
                issues.append(f"D3 checklist failures: {failed}")

        return max(0, score), issues

    def score_d4(
        self, output: dict, task_type: str = "computation"
    ) -> tuple[int, list[str]]:
        """Score D4 based on d4-compare-v3.md requirements.

        Required: COMPARISONS, COMPUTATION_TRACE (mandatory for quantitative),
                  ARISTOTLE check, DISCONFIRMING_EVIDENCE
        """
        score = 100
        issues = []

        # ─── Zero-Gate ───
        trace = output.get(
            "COMPUTATION_TRACE", output.get("computation_trace", "")
        )
        comparisons = output.get("COMPARISONS", output.get("comparisons", {}))

        if not trace and not comparisons:
            return 0, ["ZERO-GATE: No computation trace AND no comparisons"]

        # ─── Content checks ───

        # Computation trace MANDATORY for quantitative tasks
        if task_type in ("computation", "estimation", "proof"):
            if not trace:
                score -= 30
                issues.append(
                    "MANDATORY: No computation trace for quantitative task"
                )
            elif isinstance(trace, (dict, list)):
                step_count = len(trace)
                if step_count < 3:
                    score -= 15
                    issues.append(
                        f"Trace has only {step_count} steps — likely incomplete"
                    )
            elif isinstance(trace, str):
                step_markers = sum(
                    1 for w in ("step", "Step", "→", "=", "therefore")
                    if w in trace
                )
                if step_markers < 2:
                    score -= 15
                    issues.append("Trace text has minimal step structure")

        # Aristotle's 3 rules?
        aristotle = output.get(
            "COMPARABILITY_CHECK",
            output.get("aristotle_check", {}),
        )
        if not aristotle:
            score -= 15
            issues.append("Aristotle's 3 rules not checked")
        elif isinstance(aristotle, dict):
            rules = aristotle.get("Aristotle_Rules", aristotle)
            if isinstance(rules, dict):
                for rule_name in ("Same_relation", "Same_criterion", "Same_time_state"):
                    val = rules.get(rule_name, rules.get(rule_name.lower(), None))
                    if val in (False, "N", "No"):
                        score -= 10
                        issues.append(f"Aristotle violation: {rule_name}")

        # Disconfirming evidence?
        disconf = output.get(
            "DISCONFIRMING_EVIDENCE",
            output.get("disconfirming_evidence", ""),
        )
        if not disconf:
            score -= 15
            issues.append(
                "No disconfirming evidence sought (confirmation bias risk)"
            )

        # Cross-verification?
        cross = output.get(
            "CROSS_VERIFICATION",
            output.get("cross_verification", ""),
        )
        if not cross or str(cross).lower() in ("n/a", "not applicable", "none", ""):
            score -= 10
            issues.append("No cross-verification attempted (HC4 → cap 75%)")

        # Gaps remaining?
        gaps = output.get(
            "GAPS_REMAINING", output.get("gaps_remaining", "")
        )
        if not gaps:
            score -= 5
            issues.append("No gaps identified (honest admission expected)")

        # D4 checklist?
        checklist = output.get("D4_CHECKLIST", output.get("d4_checklist", {}))
        if isinstance(checklist, dict):
            failed = [k for k, v in checklist.items()
                      if v in (False, "☐", "FAIL", "fail", "no")]
            if failed:
                score -= len(failed) * 3
                issues.append(f"D4 checklist failures: {failed}")

        return max(0, score), issues

    def score_d5(self, output: dict) -> tuple[int, list[str]]:
        """Score D5 based on d5-infer-v3.md requirements.

        Required: ANSWER, CHAIN (inference), CERTAINTY, L5_DIRECTION_CHECK,
                  FOUR_REQUIREMENTS
        """
        score = 100
        issues = []

        # ─── Zero-Gate ───
        chain = output.get("CHAIN", output.get("inference_chain", ""))
        answer = output.get("ANSWER", output.get("answer", ""))

        if not chain and not answer:
            return 0, ["ZERO-GATE: No inference chain AND no answer"]

        # ─── Content checks ───

        # L5 direction check (CRITICAL)?
        l5 = output.get(
            "L5_DIRECTION_CHECK",
            output.get("l5_direction_check", {}),
        )
        if not l5:
            score -= 25
            issues.append(
                "L5 direction not checked — rationalization risk "
                "(premises→conclusion vs conclusion→premises)"
            )
        elif isinstance(l5, dict):
            direction = l5.get("Direction", l5.get("direction", ""))
            if "conclusion" in str(direction).lower() and "premise" not in str(direction).lower():
                score -= 20
                issues.append(
                    "L5 VIOLATION: direction is conclusion→premises (rationalization!)"
                )
            pre_expectation = l5.get(
                "Pre_analysis_expectation",
                l5.get("pre_analysis_expectation", ""),
            )
            if str(pre_expectation).upper() in ("Y", "YES", "TRUE"):
                score -= 10
                issues.append(
                    "L5 WARNING: had answer before D4 — check for rationalization"
                )

        # Certainty type?
        certainty = output.get("CERTAINTY", output.get("certainty", {}))
        if not certainty:
            score -= 15
            issues.append("Certainty type not marked (honesty req #2)")
        elif isinstance(certainty, dict):
            cert_type = certainty.get("Type", certainty.get("type", ""))
            neg_test = certainty.get(
                "Negation_test", certainty.get("negation_test", "")
            )
            if cert_type in ("necessary", "Necessary") and neg_test not in (
                "Y", "Yes", "yes", True
            ):
                score -= 20
                issues.append(
                    "Claims 'necessary' but negation test did not produce contradiction!"
                )

        # Four honesty requirements?
        four_req = output.get(
            "FOUR_REQUIREMENTS",
            output.get("honesty_requirements", {}),
        )
        if isinstance(four_req, dict):
            for req in ("Correspondence", "Marking", "Withhold", "Accept"):
                req_lower = req.lower()
                val = four_req.get(req, four_req.get(req_lower, ""))
                if not val:
                    score -= 5
                    issues.append(f"Honesty req '{req}' not checked")
        elif not four_req:
            score -= 15
            issues.append("Four honesty requirements not checked")

        # Alternatives considered?
        alts = output.get(
            "ALTERNATIVES_CONSIDERED",
            output.get("alternatives_considered", {}),
        )
        if not alts:
            score -= 10
            issues.append("No alternative conclusions considered")

        # Cross-verification?
        cross = output.get(
            "cross_verification", output.get("CROSS_VERIFICATION", "")
        )
        if not cross:
            score -= 5
            issues.append("No cross-verification in D5")

        # Injected premises check?
        injected = output.get(
            "INJECTED_PREMISES",
            output.get("injected_premises", ""),
        )
        if injected and str(injected).lower() not in ("none", "[]", ""):
            score -= 15
            issues.append(f"INJECTED PREMISES detected: {injected}")

        # Refutability?
        refute = output.get("REFUTABILITY", output.get("refutability", ""))
        if not refute:
            score -= 5
            issues.append("No refutability conditions stated")

        # D5 checklist?
        checklist = output.get("D5_CHECKLIST", output.get("d5_checklist", {}))
        if isinstance(checklist, dict):
            failed = [k for k, v in checklist.items()
                      if v in (False, "☐", "FAIL", "fail", "no")]
            if failed:
                score -= len(failed) * 2
                issues.append(f"D5 checklist failures: {failed}")

        return max(0, score), issues

    # ═══════════════════════════════════
    # SCORECARD — min-aggregation + hard caps
    # ═══════════════════════════════════

    def compute_scorecard(
        self,
        d1_score: int,
        d2_score: int,
        d3_score: int,
        d4_score: int,
        d5_score: int,
        hard_caps: Optional[list[tuple[str, int]]] = None,
    ) -> dict:
        """Compute C_final per REGULUS_CORE.md §5.

        C_final = min(D1, D2, D3, D4, D5) — chain as strong as weakest link.
        Hard caps applied AFTER min-aggregation.
        """
        scores = {
            "D1": d1_score,
            "D2": d2_score,
            "D3": d3_score,
            "D4": d4_score,
            "D5": d5_score,
        }

        c_final = min(scores.values())
        weakest = min(scores, key=scores.get)  # type: ignore[arg-type]

        # Apply hard caps
        caps_applied: list[str] = []
        if hard_caps:
            for cap_name, cap_value in hard_caps:
                if c_final > cap_value:
                    c_final = cap_value
                    caps_applied.append(f"{cap_name} → cap {cap_value}%")

        return {
            "c_final": c_final,
            "weakest_domain": weakest,
            "per_domain": scores,
            "hard_caps_applied": caps_applied,
            "method": "min-aggregation per REGULUS_CORE.md §5",
        }

    def detect_hard_caps(
        self,
        d3_output: dict,
        d4_output: dict,
        d5_output: dict,
    ) -> list[tuple[str, int]]:
        """Detect which hard caps from REGULUS_CORE.md apply."""
        caps: list[tuple[str, int]] = []

        # HC3: Two methods disagree → cap 50%
        cross = d5_output.get(
            "cross_verification",
            d5_output.get("CROSS_VERIFICATION", ""),
        )
        if "disagree" in str(cross).lower() or "conflict" in str(cross).lower():
            caps.append(("HC3: methods disagree", 50))

        # HC4: Single method, no cross-verification → cap 75%
        d4_cross = d4_output.get(
            "CROSS_VERIFICATION",
            d4_output.get("cross_verification", ""),
        )
        if not d4_cross or str(d4_cross).lower() in (
            "n/a", "not applicable", "none", ""
        ):
            caps.append(("HC4: no cross-verification", 75))

        # HC5: Sanity check fails → cap 60%
        sanity = d5_output.get(
            "sanity_check",
            d5_output.get("cross_verification_level1", ""),
        )
        if "fail" in str(sanity).lower() or "suspicious" in str(sanity).lower():
            caps.append(("HC5: sanity check fails", 60))

        # HC9: Zero alternatives in D3 → cap 70%
        alts = d3_output.get(
            "ALTERNATIVES_CONSIDERED",
            d3_output.get("alternatives_considered", {}),
        )
        if not alts:
            caps.append(("HC9: zero D3 alternatives", 70))

        # HC10: Injected premise → cap 65%
        injected = d5_output.get(
            "INJECTED_PREMISES",
            d5_output.get("injected_premises", ""),
        )
        if injected and str(injected).lower() not in ("none", "[]", ""):
            caps.append(("HC10: injected premise detected", 65))

        # HC-CERT: Claims "necessary" without negation test → cap 70%
        certainty = d5_output.get("CERTAINTY", d5_output.get("certainty", {}))
        if isinstance(certainty, dict):
            if certainty.get("Type", certainty.get("type", "")) in (
                "necessary", "Necessary"
            ):
                neg = certainty.get(
                    "Negation_test", certainty.get("negation_test", "")
                )
                if neg not in ("Y", "Yes", "yes", True):
                    caps.append(("HC-CERT: 'necessary' without proof", 70))

        return caps

    def score_all(
        self,
        d1: dict,
        d2: dict,
        d3: dict,
        d4: dict,
        d5: dict,
        task_type: str = "computation",
    ) -> dict:
        """Score all domains, detect hard caps, compute scorecard.

        Returns:
            {
                "per_domain": {"D1": (score, issues), ...},
                "hard_caps": [...],
                "scorecard": {...},
            }
        """
        s1, i1 = self.score_d1(d1)
        s2, i2 = self.score_d2(d2, d1)
        s3, i3 = self.score_d3(d3)
        s4, i4 = self.score_d4(d4, task_type)
        s5, i5 = self.score_d5(d5)

        hard_caps = self.detect_hard_caps(d3, d4, d5)

        scorecard = self.compute_scorecard(s1, s2, s3, s4, s5, hard_caps)

        return {
            "per_domain": {
                "D1": {"score": s1, "issues": i1},
                "D2": {"score": s2, "issues": i2},
                "D3": {"score": s3, "issues": i3},
                "D4": {"score": s4, "issues": i4},
                "D5": {"score": s5, "issues": i5},
            },
            "hard_caps": hard_caps,
            "scorecard": scorecard,
        }
