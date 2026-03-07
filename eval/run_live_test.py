"""
run_live_test.py — Live test of the Verified D1-D6 Pipeline v2.

Runs a real math question through the full pipeline:
  D6-ASK → [D1→gate→D2→gate→D3→gate→D4→gate→D5→gate] → D6-REFLECT FULL

Uses simulated Worker outputs (no LLM needed) but all validation checks
and certificate generation are REAL — backed by 82 Coq theorems.

Question: How many integers n with 1 ≤ n ≤ 2025 have the property that
the sum of the digits of n is a perfect square?
Answer: 293
"""

import json
import sys
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from regulus.verified.verified_pipeline import (
    D6AskOutput,
    D6ReflectFull,
    ERRChainCheck,
    GateVerdict,
    QuickGate,
    ReturnAssessment,
    ReturnType,
    BoundaryAudit,
    CertaintyDegree,
    VerifiedPipeline,
    VerifiedPipelineConfig,
    validate_ask,
    validate_gate,
    validate_reflect,
)


# ═══════════════════════════════════
# SECTION A: SIMULATED WORKER OUTPUTS
# ═══════════════════════════════════

QUESTION = (
    "How many integers n with 1 ≤ n ≤ 2025 have the property that "
    "the sum of the digits of n is a perfect square?"
)
CORRECT_ANSWER = 293


def ask_runner(question: str) -> D6AskOutput:
    """D6-ASK: Decompose the question using Heidegger's 3 moments."""
    return D6AskOutput(
        gefragte="counting integers by digit-sum property",
        befragte="number theory / combinatorics",
        erfragte="exact integer count",
        sub_questions=[
            "What is the range of possible digit sums for n in [1, 2025]?",
            "Which digit sums are perfect squares?",
            "For each perfect-square digit sum, how many n have that digit sum?",
            "What is the total count?"
        ],
        serves_root=[
            ("digit sum range", True),
            ("perfect square identification", True),
            ("counting per digit sum", True),
            ("total", True),
        ],
        composition_test=True,
        traps=[
            "Off-by-one: range is [1, 2025] not [0, 2025]",
            "Upper bound: 2025 is NOT 10^k, careful with last bucket",
            "Digit sum 0 is NOT a perfect square (n=0 excluded anyway)",
        ],
        format_required="single integer",
        complexity=1,  # medium
        task_type="computation",
    )


def domain_runner(domain_num: int, question: str,
                  prev: dict | None, ask: D6AskOutput) -> dict:
    """Simulated Worker output for each domain."""

    if domain_num == 1:
        # D1: Recognition — identify E/R/R
        return {
            "domain": 1,
            "elements": [
                {"id": 1, "desc": "integers n", "level": "object"},
                {"id": 2, "desc": "range [1, 2025]", "level": "object"},
                {"id": 3, "desc": "digit sum function S(n)", "level": "property"},
                {"id": 4, "desc": "perfect square predicate", "level": "property"},
                {"id": 5, "desc": "count of qualifying n", "level": "object"},
            ],
            "roles": [
                {"element_id": 1, "tag": "subject"},
                {"element_id": 2, "tag": "constraint"},
                {"element_id": 3, "tag": "operation"},
                {"element_id": 4, "tag": "filter"},
                {"element_id": 5, "tag": "target"},
            ],
            "rules": [
                {"id": 1, "desc": "1 ≤ n ≤ 2025"},
                {"id": 2, "desc": "S(n) = sum of decimal digits"},
                {"id": 3, "desc": "S(n) must equal k² for some k ∈ ℕ"},
            ],
            "key_challenge": "systematic counting across digit-sum buckets",
            "status": "unknown",
            "confidence": 60,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
            "answer": "E/R/R identified: 5 elements, 5 roles, 3 rules",
        }

    elif domain_num == 2:
        # D2: Clarification — define terms precisely
        return {
            "domain": 2,
            "definitions": {
                "digit_sum": "S(n) = Σ dᵢ where n = Σ dᵢ · 10^i, 0 ≤ dᵢ ≤ 9",
                "perfect_square": "m is a perfect square ⟺ ∃k∈ℕ: m = k²",
                "range": "[1, 2025] — 2025 integers total",
            },
            "equivocation_check": True,
            "depth_levels": {
                "digit_sum": 2,
                "perfect_square": 1,
            },
            "analysis": (
                "Max digit sum for n ∈ [1,2025]: S(1999)=28. "
                "Perfect squares ≤ 28: {1, 4, 9, 16, 25}. "
                "Need count of n with S(n) ∈ {1, 4, 9, 16, 25}."
            ),
            "confidence": 75,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
            "answer": "Digit sums range [1,28]; target set {1,4,9,16,25}",
        }

    elif domain_num == 3:
        # D3: Framework — choose approach
        return {
            "domain": 3,
            "framework": "direct enumeration (programmatic counting)",
            "objectivity_test": True,
            "criteria": [
                "Enumerate all n in [1, 2025]",
                "Compute S(n) for each",
                "Check if S(n) is a perfect square",
                "Count matches",
            ],
            "alternatives_considered": [
                "Stars-and-bars combinatorics (complex due to upper bound 2025)",
                "Generating functions (overkill for bounded range)",
                "Direct enumeration (simple, exact, verifiable)",
            ],
            "hierarchy_check": True,
            "confidence": 80,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
            "answer": "Framework: direct enumeration over [1, 2025]",
        }

    elif domain_num == 4:
        # D4: Comparison — actual computation
        return {
            "domain": 4,
            "comparisons": [
                "S(n)=1: {1, 10, 100, 1000} → 4 numbers",
                "S(n)=4: {4, 13, 22, 31, 40, 103, ...} → 28 numbers",
                "S(n)=9: {9, 18, 27, 36, 45, ...} → 103 numbers",
                "S(n)=16: {79, 88, 97, 169, ...} → 142 numbers",
                "S(n)=25: {799, 889, 898, ...} → 16 numbers",
            ],
            "computation_trace": [
                "digit_sum=1: count=4",
                "digit_sum=4: count=28",
                "digit_sum=9: count=103",
                "digit_sum=16: count=142",
                "digit_sum=25: count=16",
                "Total: 4+28+103+142+16 = 293",
            ],
            "confidence": 90,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
            "answer": "293 (breakdown: 4+28+103+142+16)",
        }

    elif domain_num == 5:
        # D5: Inference — extract final answer
        return {
            "domain": 5,
            "inference_chain": [
                "Range [1,2025] contains 2025 integers",
                "Possible digit sums: 1 through 28",
                "Perfect square digit sums: {1, 4, 9, 16, 25}",
                "Count per bucket: 4+28+103+142+16",
                "Total: 293",
            ],
            "l5_direction": "premises → conclusion (deductive)",
            "cross_verification": "Verified by enumeration: sum matches",
            "honesty_requirements": [
                "No unstated assumptions",
                "Range boundary 2025 correctly handled",
                "All digit sums exhaustively checked",
                "Addition verified: 4+28=32, 32+103=135, 135+142=277, 277+16=293",
            ],
            "certainty_degree": "necessary",
            "confidence": 95,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
            "answer": "293",
        }

    return {"domain": domain_num, "answer": "unknown", "confidence": 0}


def reflect_runner(outputs: list[dict], gates: list[QuickGate],
                   ask: D6AskOutput) -> D6ReflectFull:
    """D6-REFLECT FULL: Post-pipeline reflection."""
    return D6ReflectFull(
        # Class I: Conclusive
        class_i_conclusive=(
            "The count is 293. Verified by exhaustive enumeration over [1,2025]. "
            "Each digit-sum bucket independently counted and totaled."
        ),
        # Class II: ≥2 required
        perceptive=(
            "The problem decomposes naturally by digit-sum value. "
            "Only 5 perfect-square values matter (1,4,9,16,25)."
        ),
        procedural=(
            "Direct enumeration is the most reliable approach for bounded ranges. "
            "Combinatorial methods risk off-by-one at the 2025 boundary."
        ),
        perspectival=(
            "From a number theory view, digit sums follow well-known distributions. "
            "The irregular upper bound 2025 makes analytic formulas fragile."
        ),
        fundamental=None,  # not needed for this problem
        # ERR chain
        err_chain=ERRChainCheck(
            elements_consistent=True,
            dependencies_acyclic=True,
            status_transitions_justified=True,
            no_level_violations=True,
        ),
        # Domain qualities
        domain_qualities=[
            {"domain": i + 1, "quality": d.get("confidence", 50)}
            for i, d in enumerate(outputs)
        ],
        # Boundary audit (D5 claims Necessary certainty)
        boundary_audit=BoundaryAudit(
            required=True,
            proof_type_valid=True,
            no_unstated_assumptions=True,
            counterexample_addressed=True,
        ),
        # Limitations
        scope_fails_when=(
            "Fails if range extends beyond 4-digit numbers (would need "
            "stars-and-bars for efficiency). Also assumes base-10 digits."
        ),
        adjustment_reason=(
            "High confidence warranted: exhaustive enumeration with independent "
            "verification of addition. No approximations used."
        ),
        adjusted_confidence=95.0,
        # Return decision
        return_assessment=ReturnAssessment(type=ReturnType.NONE),
        # D5 certainty
        d5_certainty=CertaintyDegree.NECESSARY,
    )


# ═══════════════════════════════════
# SECTION B: MAIN
# ═══════════════════════════════════

def main():
    print("═" * 60)
    print("LIVE TEST: VERIFIED D1-D6 PIPELINE v2")
    print("═" * 60)
    print(f"\nQuestion: {QUESTION}")
    print(f"Expected answer: {CORRECT_ANSWER}")
    print()

    # ─── Run pipeline ───
    config = VerifiedPipelineConfig(max_fuel=3, max_shifts=1, epsilon=5.0)
    pipeline = VerifiedPipeline(config)

    result = pipeline.run_sync(
        question=QUESTION,
        domain_runner=domain_runner,
        ask_runner=ask_runner,
        reflect_runner=reflect_runner,
    )

    # ─── Validate each layer independently ───
    print("─" * 60)
    print("VALIDATION CHECKS")
    print("─" * 60)

    # D6-ASK
    ask_valid, ask_viols = validate_ask(result.ask)
    status = "✅" if ask_valid else "❌"
    print(f"\n  D6-ASK:           {status}")
    if not ask_valid:
        for v in ask_viols:
            print(f"    ⚠ {v}")
    else:
        print(f"    erfragte: \"{result.ask.erfragte}\"")
        print(f"    sub-questions: {len(result.ask.sub_questions)}")
        print(f"    traps: {len(result.ask.traps)}")

    # D1-D5 + Gates
    for i, (d, g) in enumerate(zip(result.domain_outputs, result.gates)):
        domain_num = d.get("domain", i + 1)
        g_valid, g_viols = validate_gate(g)
        g_icon = "✅" if g.verdict == GateVerdict.PASS else (
            "🔄" if g.verdict == GateVerdict.ITERATE else "⛔"
        )
        d_conf = d.get("confidence", "?")
        print(f"\n  D{domain_num} → Gate{domain_num}:   {g_icon}  "
              f"conf={d_conf}%  verdict={g.verdict.value}")
        if not g_valid:
            for v in g_viols:
                print(f"    ⚠ {v}")
        # Show gate details
        checks = []
        if g.alignment: checks.append("align✓")
        if g.coverage: checks.append("cover✓")
        if g.consistency: checks.append("consist✓")
        if g.confidence_matches: checks.append("conf✓")
        print(f"    checks: {' '.join(checks)}")
        answer_preview = str(d.get("answer", ""))[:60]
        print(f"    output: {answer_preview}")

    # D6-REFLECT FULL
    if result.reflect is not None:
        rf_valid, rf_viols = validate_reflect(result.reflect)
        rf_status = "✅" if rf_valid else "❌"
        print(f"\n  D6-REFLECT FULL:  {rf_status}")
        if not rf_valid:
            for v in rf_viols:
                print(f"    ⚠ {v}")
        print(f"    Class I:  {'✅' if result.reflect.class_i_conclusive else '❌'}")
        print(f"    Class II: {result.reflect.class_ii_count}/4 present "
              f"({'✅' if result.reflect.class_ii_count >= 2 else '❌'} need ≥2)")
        print(f"    ERR chain: {'✅' if result.reflect.err_chain.all_passed else '❌'}")
        if result.reflect.boundary_audit:
            ba = result.reflect.boundary_audit
            print(f"    Boundary audit: {'✅' if ba.passed else '❌'} "
                  f"(required={ba.required})")
        print(f"    Return: {result.reflect.return_assessment.type.value}")
        print(f"    Adjusted conf: {result.reflect.adjusted_confidence}%")
    else:
        print(f"\n  D6-REFLECT FULL:  ❌ (None)")

    # ─── Certificate ───
    cert = result.certificate
    print()
    print("─" * 60)
    print("CERTIFICATE")
    print("─" * 60)
    print(f"  ASK validated:        {'✅' if cert.ask_validated else '❌'}")
    print(f"  Erfragte specified:   {'✅' if cert.erfragte_specified else '❌'}")
    print(f"  Domains traversed:    {cert.domains_traversed}")
    print(f"  All domains valid:    {'✅' if cert.all_domains_valid else '❌'}")
    print(f"  Gates all passed:     {'✅' if cert.gates_all_passed else '❌'}")
    print(f"  D2→D3 ready:          {'✅' if cert.d2_d3_ready else '❌'}")
    print(f"  D4→D5 ready:          {'✅' if cert.d4_d5_ready else '❌'}")
    print(f"  Answer earned:        {'✅' if cert.answer_earned else '❌'}")
    print(f"  REFLECT valid:        {'✅' if cert.reflect_valid else '❌'}")
    print(f"  ERR chain verified:   {'✅' if cert.err_chain_verified else '❌'}")
    if cert.boundary_audit_passed is not None:
        print(f"  Boundary audit:       {'✅' if cert.boundary_audit_passed else '❌'}")
    print(f"  Return type:          {cert.return_type}")
    print(f"  Iterations used:      {cert.iterations_used}")
    print(f"  Paradigm shifts:      {cert.paradigm_shifts}")
    print(f"  Convergence method:   {cert.convergence_method}")

    print(f"\n  Backing theorems ({len(cert.backing_theorems)}):")
    for t in cert.backing_theorems:
        print(f"    • {t}")

    # ─── Final answer ───
    print()
    print("═" * 60)
    print("RESULT")
    print("═" * 60)
    correct = result.answer.strip() == str(CORRECT_ANSWER)
    print(f"  Answer:     {result.answer}")
    print(f"  Expected:   {CORRECT_ANSWER}")
    print(f"  Correct:    {'✅ YES' if correct else '❌ NO'}")
    print(f"  Confidence: {result.confidence}%")

    all_valid = (
        cert.ask_validated
        and cert.all_domains_valid
        and cert.gates_all_passed
        and cert.answer_earned
        and cert.reflect_valid
        and cert.err_chain_verified
    )
    print(f"  Certificate valid: {'✅ ALL CHECKS PASSED' if all_valid else '❌ SOME CHECKS FAILED'}")
    print()

    # ─── Save result ───
    result_data = {
        "question": QUESTION,
        "answer": result.answer,
        "expected_answer": CORRECT_ANSWER,
        "correct": correct,
        "confidence": result.confidence,
        "certificate": {
            "ask_validated": cert.ask_validated,
            "erfragte_specified": cert.erfragte_specified,
            "domains_traversed": cert.domains_traversed,
            "all_domains_valid": cert.all_domains_valid,
            "gates_all_passed": cert.gates_all_passed,
            "d2_d3_ready": cert.d2_d3_ready,
            "d4_d5_ready": cert.d4_d5_ready,
            "answer_earned": cert.answer_earned,
            "reflect_valid": cert.reflect_valid,
            "err_chain_verified": cert.err_chain_verified,
            "boundary_audit_passed": cert.boundary_audit_passed,
            "return_type": cert.return_type,
            "iterations_used": cert.iterations_used,
            "paradigm_shifts": cert.paradigm_shifts,
            "convergence_method": cert.convergence_method,
            "backing_theorems": cert.backing_theorems,
        },
        "gate_details": [
            {
                "domain": g.domain,
                "verdict": g.verdict.value,
                "alignment": g.alignment,
                "coverage": g.coverage,
                "consistency": g.consistency,
                "confidence_matches": g.confidence_matches,
            }
            for g in result.gates
        ],
        "domain_confidences": [
            d.get("confidence", 0) for d in result.domain_outputs
        ],
    }

    output_path = Path(__file__).parent / "results" / "live_test_result.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result_data, f, indent=2)
    print(f"  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
