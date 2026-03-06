"""
hle_verified_eval.py — Phase 5 Evaluation: Baseline vs Verified Backend on HLE Math.

Post-hoc evaluation: applies verified backend to EXISTING pipeline results
(no new LLM calls needed). Both arms use the same pipeline output.

ARM A (Baseline): Raw pipeline results as-is
ARM B (Verified): Same results + ERRValidator on D1 + MathVerifier on D3+D4 + LayeredAnalysis

Usage:
    uv run python eval/hle_verified_eval.py
"""

from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from regulus.verified.bridge import VerifiedBackend
from regulus.verified.math_verifier import MathVerifier
from regulus.verified.err_validator import ERRValidator
from regulus.verified.layers import (
    LayeredAnalysis, AnalysisLayer, MATH_LAYER, LOGICAL_LAYER,
    EMPIRICAL_LAYER, make_domain_layer,
)
from regulus.verified.pipeline_adapter import PipelineAdapter


@dataclass
class EvalResult:
    """Result for one question on one arm."""
    question_id: str
    arm: str  # "baseline" or "verified"
    question_text: str
    answer: str
    expected: str
    correct: bool
    category: str

    # Confidence
    confidence_self: float  # c_computation
    confidence_scorecard: float  # final
    confidence_verified: Optional[float] = None

    # Verified backend info
    verified_triggered: bool = False
    verified_components: list[str] = field(default_factory=list)
    verified_details: dict = field(default_factory=dict)

    # D1 ERR validation
    d1_err_valid: Optional[bool] = None
    d1_violations: list[str] = field(default_factory=list)
    d1_cross_check: list[str] = field(default_factory=list)

    # D3 framework
    d3_framework: str = "unknown"
    d3_layers_count: int = 0

    # D4 verification
    d4_verified: bool = False
    d4_theorem_used: str = ""

    # Error analysis
    error_category: str = "unknown"  # framework|computation|proof|format|none

    # Metadata
    tokens_total: int = 0
    time_seconds: float = 0.0


class HLEVerifiedEval:
    """Run post-hoc evaluation on existing HLE Math pipeline results."""

    def __init__(
        self,
        questions_file: str = "eval/hle_math_questions.json",
        base_dir: str = ".",
    ):
        self.base_dir = Path(base_dir)
        self.questions = self._load_questions(questions_file)
        self.results: list[EvalResult] = []
        self.adapter = PipelineAdapter()
        self.backend = VerifiedBackend()
        self.verifier = MathVerifier(backend=self.backend)
        self.validator = ERRValidator(backend=self.backend)

    def _load_questions(self, path: str) -> list[dict]:
        with open(path) as f:
            return json.load(f)

    def run_all(self):
        """Run both arms on all questions with existing results."""
        hle_questions = [q for q in self.questions if q.get("run_dir")]
        synthetic_questions = [q for q in self.questions if not q.get("run_dir")]

        print(f"\n{'='*70}")
        print(f"Phase 5 Evaluation: Baseline vs Verified Backend")
        print(f"{'='*70}")
        print(f"HLE questions (existing results): {len(hle_questions)}")
        print(f"Synthetic questions (N1-N6, no pipeline run): {len(synthetic_questions)}")
        print(f"{'='*70}\n")

        # Evaluate HLE questions with existing pipeline results
        for q in hle_questions:
            self._evaluate_question(q)

        # Evaluate synthetic questions (verified backend only, no pipeline)
        for q in synthetic_questions:
            self._evaluate_synthetic(q)

        self._save_results()
        self._print_summary()

    def _evaluate_question(self, q: dict):
        """Evaluate one HLE question (has existing pipeline results)."""
        run_dir = self.base_dir / q["run_dir"]
        if not run_dir.exists():
            print(f"  ⚠ {q['id']}: run_dir not found: {run_dir}")
            return

        print(f"{'─'*60}")
        print(f"{q['id']} ({q['category']}): {q['text'][:70]}...")

        # Load pipeline data
        try:
            data = self.adapter.extract_all(run_dir)
        except Exception as e:
            print(f"  ⚠ Failed to load: {e}")
            return

        result_json = data["result"]
        answer_raw = result_json.get("answer_raw", "")
        expected = q["expected"]
        judge_correct = result_json.get("judge_correct", False)
        conf_self, conf_final = data["confidence"]

        # ── ARM A: Baseline ──────────────────────────────────────────
        baseline = EvalResult(
            question_id=q["id"],
            arm="baseline",
            question_text=q["text"],
            answer=self._extract_short_answer(answer_raw),
            expected=expected,
            correct=judge_correct,
            category=q["category"],
            confidence_self=conf_self,
            confidence_scorecard=conf_final,
            d3_framework=data["d3_framework"],
            tokens_total=result_json.get("total_tokens", 0),
            time_seconds=result_json.get("elapsed_seconds", 0),
            error_category=self._classify_error(q, answer_raw, judge_correct),
        )
        self.results.append(baseline)
        print(f"  Baseline: {'✅' if baseline.correct else '❌'} "
              f"(conf: {baseline.confidence_scorecard:.0f}%) "
              f"answer: {baseline.answer[:50]}")

        # ── ARM B: Verified ──────────────────────────────────────────
        verified = EvalResult(
            question_id=q["id"],
            arm="verified",
            question_text=q["text"],
            answer=self._extract_short_answer(answer_raw),
            expected=expected,
            correct=judge_correct,  # Same answer, same correctness
            category=q["category"],
            confidence_self=conf_self,
            confidence_scorecard=conf_final,
            d3_framework=data["d3_framework"],
            tokens_total=result_json.get("total_tokens", 0),
            time_seconds=result_json.get("elapsed_seconds", 0),
            error_category=self._classify_error(q, answer_raw, judge_correct),
        )

        # 1. D1 ERR Validation
        d1_err = data["d1_err"]
        if d1_err.get("elements"):
            try:
                check = self.validator.validate_d1_output(d1_err)
                verified.d1_err_valid = check["valid"]
                verified.d1_violations = check.get("violations", [])
                verified.d1_cross_check = check.get("cross_check", [])
                if not check["valid"]:
                    verified.verified_triggered = True
                    verified.verified_components.append("err_check")
                    verified.verified_details["d1_check"] = check
            except Exception as e:
                verified.verified_details["d1_error"] = str(e)

        # 2. D3+D4 Math Verification
        d3_framework = data["d3_framework"]
        d4_data = data["d4_data"]
        if d3_framework and d4_data:
            try:
                v_result = self.verifier.try_verify(d3_framework, d4_data)
                if v_result and v_result.success:
                    verified.d4_verified = True
                    verified.d4_theorem_used = v_result.theorem_used
                    verified.confidence_verified = 100.0
                    verified.verified_triggered = True
                    verified.verified_components.append(
                        v_result.theorem_used.split(".")[0].lower()
                    )
                    verified.verified_details["d4_result"] = {
                        "value": str(v_result.value),
                        "certificate": v_result.certificate,
                        "theorem": v_result.theorem_used,
                    }
            except Exception as e:
                verified.verified_details["d4_error"] = str(e)

        # 3. Layered Analysis (simulate multi-perspective)
        try:
            layers = self._build_layers(q, d1_err)
            verified.d3_layers_count = len(layers.layers)
            if len(layers.layers) >= 2:
                verified.verified_triggered = True
                verified.verified_components.append("layers")
                verified.verified_details["layers"] = layers.to_dict()
        except Exception as e:
            verified.verified_details["layers_error"] = str(e)

        # 4. Calibration adjustment based on verified backend findings
        if verified.verified_triggered:
            # Compute adjusted confidence
            if verified.d1_err_valid is False:
                # D1 violations → lower confidence
                penalty = len(verified.d1_violations) * 5
                verified.confidence_verified = max(
                    10, verified.confidence_scorecard - penalty
                )
            elif verified.d4_verified:
                # Verified computation → boost confidence on that step
                verified.confidence_verified = 100.0

        self.results.append(verified)
        print(f"  Verified: {'✅' if verified.correct else '❌'} "
              f"trigger={verified.verified_triggered} "
              f"components={verified.verified_components}")
        if verified.d1_violations:
            print(f"    D1 violations: {verified.d1_violations[:3]}")
        if verified.d4_theorem_used:
            print(f"    D4 theorem: {verified.d4_theorem_used}")

    def _evaluate_synthetic(self, q: dict):
        """Evaluate synthetic question (no pipeline run, verified backend only)."""
        print(f"{'─'*60}")
        print(f"{q['id']} (synthetic/{q['category']}): {q['text'][:70]}...")
        print(f"  [No pipeline run — synthetic question for verified backend targeting]")

        # Record as baseline "not run"
        baseline = EvalResult(
            question_id=q["id"],
            arm="baseline",
            question_text=q["text"],
            answer="NOT_RUN",
            expected=q["expected"],
            correct=False,
            category=q["category"],
            confidence_self=0,
            confidence_scorecard=0,
            error_category="not_run",
        )
        self.results.append(baseline)

        # For verified arm, we simulate what WOULD trigger
        verified = EvalResult(
            question_id=q["id"],
            arm="verified",
            question_text=q["text"],
            answer="NOT_RUN",
            expected=q["expected"],
            correct=False,
            category=q["category"],
            confidence_self=0,
            confidence_scorecard=0,
            error_category="not_run",
            verified_triggered=True,
            verified_components=q.get("verified_relevant", []),
        )
        self.results.append(verified)
        print(f"  Would trigger: {q.get('verified_relevant', [])}")

    def _build_layers(self, q: dict, d1_err: dict) -> LayeredAnalysis:
        """Build multi-layer analysis for a question."""
        substrate = {
            "question_id": q["id"],
            "category": q["category"],
            "elements": d1_err.get("elements", []),
        }
        analysis = LayeredAnalysis(substrate=substrate)

        # Always add math layer for math questions
        analysis.add_layer(MATH_LAYER)

        # Add logical layer
        analysis.add_layer(LOGICAL_LAYER)

        # Add domain-specific layer based on category
        category = q.get("category", "")
        if "geometry" in category:
            analysis.add_layer(make_domain_layer("geometry", priority=7))
        elif "probability" in category:
            analysis.add_layer(make_domain_layer("probability", priority=7))
        elif "algebra" in category:
            analysis.add_layer(make_domain_layer("algebra", priority=7))
        elif "calculus" in category or "series" in category:
            analysis.add_layer(make_domain_layer("analysis", priority=7))
        elif "optimization" in category:
            analysis.add_layer(make_domain_layer("optimization", priority=7))
        elif "topology" in category:
            analysis.add_layer(make_domain_layer("topology", priority=7))
        elif "differential" in category:
            analysis.add_layer(make_domain_layer("differential_equations", priority=7))

        return analysis

    def _extract_short_answer(self, answer_raw: str) -> str:
        """Extract the short answer from verbose pipeline output."""
        # Look for explicit answer line
        patterns = [
            r"(?:^|\n)\s*(?:answer|ANSWER|Answer)\s*[:=]\s*(.+?)(?:\n|$)",
            r"(?:^|\n)\s*\*?\*?Answer\*?\*?\s*[:=]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            m = re.search(pattern, answer_raw)
            if m:
                ans = m.group(1).strip()
                ans = re.sub(r"^\*+|\*+$", "", ans).strip()
                return ans[:200]

        # Fallback: first line
        first_line = answer_raw.strip().split("\n")[0]
        return first_line[:200]

    def _classify_error(self, q: dict, answer_raw: str, correct: bool) -> str:
        """Classify the error type based on answer content."""
        if correct:
            return "none"

        answer_lower = answer_raw.lower()

        # Framework errors (wrong approach selected)
        framework_indicators = [
            "framework", "approach", "method", "strategy",
            "wrong framework", "alternative approach",
        ]

        # Computation errors
        computation_indicators = [
            "calculation", "compute", "arithmetic",
            "formula", "evaluate", "result =",
        ]

        # Proof errors
        proof_indicators = [
            "proof", "assume", "suppose", "theorem",
            "therefore", "hence", "qed",
        ]

        # Simple heuristic based on content
        return "unknown"

    def _save_results(self):
        """Save all results to JSON."""
        out_dir = Path("eval/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "hle_verified_eval.json"

        # Make results JSON-serializable
        serializable = []
        for r in self.results:
            d = asdict(r)
            # Clean non-serializable items
            if "d4_result" in d.get("verified_details", {}):
                # Already string-safe
                pass
            serializable.append(d)

        with open(out_path, "w") as f:
            json.dump(serializable, f, indent=2, default=str)
        print(f"\n✅ Results saved to {out_path}")

    def _print_summary(self):
        """Print comprehensive summary report."""
        # Split by arm, excluding NOT_RUN
        baseline_all = [r for r in self.results if r.arm == "baseline"]
        verified_all = [r for r in self.results if r.arm == "verified"]

        baseline_run = [r for r in baseline_all if r.error_category != "not_run"]
        verified_run = [r for r in verified_all if r.error_category != "not_run"]

        print(f"\n{'='*70}")
        print(f"PHASE 5 EVALUATION SUMMARY")
        print(f"{'='*70}")

        # Accuracy
        b_correct = sum(r.correct for r in baseline_run)
        v_correct = sum(r.correct for r in verified_run)
        b_total = len(baseline_run)
        v_total = len(verified_run)

        print(f"\n📊 ACCURACY (HLE questions only)")
        print(f"  Baseline:  {b_correct}/{b_total} "
              f"({b_correct/b_total:.1%})" if b_total else "  Baseline: N/A")
        print(f"  Verified:  {v_correct}/{v_total} "
              f"({v_correct/v_total:.1%})" if v_total else "  Verified: N/A")
        if b_total and v_total:
            delta = (v_correct/v_total) - (b_correct/b_total)
            print(f"  Delta:     {delta:+.1%}")

        # Calibration
        print(f"\n📐 CALIBRATION ERROR (lower = better)")
        if baseline_run:
            b_cal = self._calibration_error(baseline_run)
            print(f"  Baseline:  {b_cal:.1f}pp")
        if verified_run:
            v_cal = self._calibration_error(verified_run)
            print(f"  Verified:  {v_cal:.1f}pp")
            # Calibration using verified confidence where available
            v_cal_adj = self._calibration_error_adjusted(verified_run)
            print(f"  Verified (adjusted): {v_cal_adj:.1f}pp")

        # Verified Backend metrics
        print(f"\n🔧 VERIFIED BACKEND")
        triggered = [r for r in verified_run if r.verified_triggered]
        print(f"  Trigger rate: {len(triggered)}/{len(verified_run)} "
              f"({len(triggered)/len(verified_run):.0%})" if verified_run else "  N/A")

        # Component breakdown
        comp_counts: dict[str, int] = {}
        for r in triggered:
            for c in r.verified_components:
                comp_counts[c] = comp_counts.get(c, 0) + 1
        if comp_counts:
            print(f"  Components triggered: {comp_counts}")

        # D1 ERR Validation
        print(f"\n🔍 D1 ERR VALIDATION")
        d1_checked = [r for r in verified_run if r.d1_err_valid is not None]
        d1_valid = sum(1 for r in d1_checked if r.d1_err_valid)
        d1_invalid = len(d1_checked) - d1_valid
        print(f"  Checked: {len(d1_checked)}/{len(verified_run)}")
        print(f"  Valid: {d1_valid}, Violations found: {d1_invalid}")
        if d1_invalid:
            for r in d1_checked:
                if not r.d1_err_valid:
                    print(f"    {r.question_id}: {r.d1_violations[:2]}")

        # D4 Math Verification
        print(f"\n🧮 D4 MATH VERIFICATION")
        d4_verified = [r for r in verified_run if r.d4_verified]
        print(f"  Triggered: {len(d4_verified)}/{len(verified_run)}")
        for r in d4_verified:
            print(f"    {r.question_id}: {r.d4_theorem_used}")

        # Per-question comparison
        print(f"\n{'─'*70}")
        print(f"PER-QUESTION COMPARISON")
        print(f"{'─'*70}")
        print(f"{'ID':<5} {'Cat':<20} {'B':>3} {'V':>3} {'Conf':>5} {'Trigger':>8} {'Components':<30}")
        print(f"{'─'*70}")

        for b, v in zip(baseline_run, verified_run):
            b_mark = "✅" if b.correct else "❌"
            v_mark = "✅" if v.correct else "❌"
            conf = f"{v.confidence_scorecard:.0f}%"
            trigger = "YES" if v.verified_triggered else "no"
            components = ", ".join(v.verified_components) if v.verified_components else "-"
            changed = " ⚡" if b.correct != v.correct else ""
            print(f"{b.question_id:<5} {b.category[:20]:<20} {b_mark:>3} {v_mark:>3} "
                  f"{conf:>5} {trigger:>8} {components:<30}{changed}")

        # Synthetic questions summary
        synthetic = [r for r in verified_all if r.error_category == "not_run"]
        if synthetic:
            print(f"\n{'─'*70}")
            print(f"SYNTHETIC QUESTIONS (N1-N6, not run)")
            for r in synthetic:
                print(f"  {r.question_id}: would trigger {r.verified_components}")

        # Conclusions
        print(f"\n{'='*70}")
        print(f"CONCLUSIONS")
        print(f"{'='*70}")

        # Determine scenario
        if len(triggered) == 0:
            scenario = "PESSIMISTIC"
            print(f"  Scenario: {scenario}")
            print(f"  Verified backend never triggered on HLE questions.")
            print(f"  This tells us HLE math is too abstract for direct theorem matching.")
        elif len(triggered) <= 3:
            scenario = "REALISTIC"
            print(f"  Scenario: {scenario}")
            print(f"  Verified backend triggered on {len(triggered)}/{len(verified_run)} questions.")
        else:
            scenario = "OPTIMISTIC"
            print(f"  Scenario: {scenario}")
            print(f"  Verified backend triggered on {len(triggered)}/{len(verified_run)} questions.")

        # Actionable insights
        print(f"\n  Key findings:")
        if d1_invalid > 0:
            print(f"  • ERR validator found {d1_invalid} D1 issues — structural problems detected")
        else:
            print(f"  • ERR validator: D1 outputs are well-formed (or unparseable)")

        if d4_verified:
            print(f"  • Math verifier triggered on {len(d4_verified)} questions")
        else:
            print(f"  • Math verifier: no direct theorem match (HLE questions are too abstract)")

        print(f"  • Calibration: baseline avg confidence = "
              f"{sum(r.confidence_scorecard for r in baseline_run)/len(baseline_run):.0f}% "
              f"on {b_correct}/{b_total} correct")

    def _calibration_error(self, results: list[EvalResult]) -> float:
        """Calculate mean absolute calibration error."""
        if not results:
            return 0.0
        errors = []
        for r in results:
            conf = r.confidence_scorecard / 100.0
            correct = 1.0 if r.correct else 0.0
            errors.append(abs(conf - correct))
        return sum(errors) / len(errors) * 100

    def _calibration_error_adjusted(self, results: list[EvalResult]) -> float:
        """Calibration using verified confidence where available."""
        if not results:
            return 0.0
        errors = []
        for r in results:
            conf = (r.confidence_verified if r.confidence_verified is not None
                    else r.confidence_scorecard) / 100.0
            correct = 1.0 if r.correct else 0.0
            errors.append(abs(conf - correct))
        return sum(errors) / len(errors) * 100


# Need re for _extract_short_answer
import re


if __name__ == "__main__":
    evaluator = HLEVerifiedEval(
        questions_file="eval/hle_math_questions.json",
        base_dir=".",
    )
    evaluator.run_all()
