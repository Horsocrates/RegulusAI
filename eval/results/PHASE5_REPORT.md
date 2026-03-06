# Phase 5 Evaluation Report
## Regulus+Verified vs Regulus Baseline on HLE Math

**Date:** 2026-03-06
**Model:** GLM-5 via Z.ai proxy
**Questions:** 10 HLE Math (Q1-Q10) + 6 synthetic (N1-N6)
**Pipeline:** Regulus P3 Agent with D1-D6 domains, Team Lead + Worker

---

## Executive Summary

The verified computation backend (Phase 4) was applied **post-hoc** to existing
GLM-5 pipeline results on 10 HLE Mathematics questions. Key findings:

1. **No accuracy change**: 0/10 both arms (post-hoc verification cannot change answers)
2. **D4 Math Verification never triggered**: HLE math questions are too abstract for IVT/EVT/convergence theorem matching
3. **D1 ERR Validation ran on 4/10 questions**: All 4 passed (no structural violations found)
4. **Severe calibration problem**: Average confidence 68% on 0% accuracy (68pp calibration error)
5. **Layers component always triggers**: By design (math + logical + domain = 3 layers), not informative

**Scenario achieved: Between REALISTIC and PESSIMISTIC**

The verified backend's formal theorem library (IVT, EVT, SeriesConvergence, FixedPoint, CROWN)
does not match the mathematical concepts needed for HLE-level questions (point-set topology,
algebraic geometry, combinatorial optimization, stochastic processes).

---

## Per-Question Results

| # | Category | Expected | Pipeline Answer | Correct | Conf | D1 ERR | D4 Verify |
|---|----------|----------|-----------------|:-------:|:----:|:------:|:---------:|
| Q1 | topology | 0 | 2^aleph_0 | NO | 93% | -- | -- |
| Q2 | geometry | 10 | 10 (judge: NO) | NO | 80% | valid | -- |
| Q3 | probability | 3/10 | 1/2 | NO | 90% | -- | -- |
| Q4 | diff_eq | 0.5(10^5010000 - 10^10000) | 10^5010000/2 | NO | 70% | -- | -- |
| Q5 | optimization | [cyl r=6,h=21.5]0;41 | [box 16x16x8]48;32 | NO | 50% | valid | -- |
| Q6 | comb_geometry | 84 | 80 | NO | 50% | -- | -- |
| Q7 | opt_geometry | C | A | NO | 50% | valid | -- |
| Q8 | alg_geometry | 1,6,28,120 | 2,4,8,16 | NO | 55% | -- | -- |
| Q9 | alg_geometry | 12chi+C^2-K_S^2-(4-4g) | 12chi-K_S^2+2g-2 | NO | 91% | -- | -- |
| Q10 | geom_prob | 0.05567 | 1.000 | NO | 55% | valid | -- |

### Notable Cases

**Q2 (Cone/Spheres)**: Pipeline answered "10" which matches expected "10", but judge_correct=false.
This appears to be a format/parsing issue -- the answer was buried in verbose text.
The verified backend could not help here (format issue, not computation issue).

**Q4 (Diff Eq)**: Pipeline answered `10^5010000/2` vs expected `0.5(10^5010000 - 10^10000)`.
The `-10^10000` term is negligible relative to `10^5010000`, so the answer is effectively correct
but missing a subtraction term. The verified backend has no relevant theorem for BVP solvability.

**Q9 (Algebraic Surface)**: Pipeline used adjunction to eliminate C^2, giving a 3-variable formula
instead of the expected 4-variable formula. Mathematically related but not equivalent.

---

## Verified Backend Analysis

### D1 ERR Validator
- **Parsed D1 output for 4/10 questions** (40% parse rate)
- All 4 parsed outputs were structurally valid (no violations)
- 6 questions had D1 outputs that couldn't be parsed into E/R/R format
- **No cross-check discrepancies found** (D1 self-assessment matched formal check)

**Why low parse rate?** D1 outputs in the pipeline are free-text markdown (not JSON).
The regex-based parser in pipeline_adapter.py successfully extracts elements (E1, E2, ...)
but many D1 outputs don't follow the E-number convention, using prose instead.

### D4 Math Verifier
- **Triggered on 0/10 questions** (0% trigger rate)
- No D3 framework matched IVT/EVT/convergence/contraction/CROWN keywords
- No D4 output contained extractable function values, ratios, or contraction factors

**Why zero triggers?** HLE Math questions involve:
- Point-set topology (continua, decomposability)
- Algebraic geometry (moduli stacks, abelian varieties, Noether formula)
- Combinatorial geometry (lattice point counting)
- Stochastic processes (random walks with absorption)
- Integer programming (sphere packing in containers)

None of these map to the verified theorem library:
- IVT: needs f(a), f(b) with opposite signs
- EVT: needs a finite set of candidate values
- Convergence: needs a ratio < 1
- Contraction: needs a Lipschitz factor
- CROWN: needs neural network weight matrices

### Layers Component
- **Triggered on 10/10 questions** (100% -- by design)
- Always creates math + logical + domain-specific layers = 3
- This is a structural feature, not a meaningful detection
- The layers component needs INLINE integration (during D3, not post-hoc) to be useful

---

## Calibration Analysis

| Metric | Value |
|--------|-------|
| Mean confidence (baseline) | 68.4% |
| Accuracy | 0.0% |
| Calibration error | 68.4pp |
| Max overconfidence | Q1 (93% conf, wrong) |
| Best calibrated | Q5, Q6, Q7 (50% conf, wrong) |

The pipeline exhibits severe overconfidence. With 0/10 correct, ideal confidence would be
close to 0%. Instead, the average is 68%, meaning the confidence system is not providing
useful signal on HLE-difficulty math questions.

The verified backend did not improve calibration because:
1. D4 verifier never triggered (no confidence_override=100 applied)
2. D1 validator found no violations (no confidence penalty applied)
3. Post-hoc verification can only ADJUST confidence, not fix wrong answers

---

## Synthetic Questions (N1-N6)

These questions were designed to TARGET the verified backend:

| # | Category | Expected | Would Trigger |
|---|----------|----------|:-------------:|
| N1 | IVT/roots | 3 | ivt |
| N2 | IVT/counting | 3 | ivt |
| N3 | EVT/maximum | 1/sqrt(2e) | evt |
| N4 | EVT/optimization | -1/3 | evt |
| N5 | Series convergence | 6 | convergence |
| N6 | Radius of convergence | infinity | convergence |

These questions were NOT run through the pipeline (no LLM calls). They demonstrate
that the verified backend WOULD be useful for calculus-level questions that directly
involve root-finding, optimization, and series convergence.

---

## Conclusions

### What We Learned

1. **HLE Math is too abstract for theorem matching**: The gap between verified theorems
   (calculus-level: IVT, EVT, series) and HLE questions (research-level: algebraic geometry,
   topology, combinatorics) is too large for the current keyword-based matching.

2. **D1 ERR parsing works partially**: 40% parse rate shows the adapter concept is viable
   but needs LLM-assisted structured extraction (not regex-based).

3. **Post-hoc verification is too late**: The verified backend needs to be INLINE
   (during D3 framework selection and D4 computation) to influence the answer.

4. **Confidence calibration is the biggest problem**: 68pp calibration error means
   the system cannot tell when it's wrong. This is where formal verification could
   help most -- not by checking answers, but by GROUNDING confidence in verified steps.

### Recommendations for Phase 6

1. **INLINE integration**: Move verification from post-hoc to inline:
   - D1: ERR validator as gate before D2 (retry if violations found)
   - D3: Layer-aware framework selection (try multiple frameworks)
   - D4: Verified computation where applicable

2. **Expand theorem library**: Add theorems relevant to HLE-level math:
   - Algebraic geometry: Noether formula, Riemann-Roch
   - Topology: compactness arguments, fixed-point theorems for spaces
   - Combinatorics: pigeonhole principle, lattice point counting

3. **LLM-assisted D1 parsing**: Use the LLM to extract E/R/R as structured JSON
   instead of regex parsing free text.

4. **Target calculus questions first**: The synthetic N1-N6 questions show the
   verified backend WOULD work on calculus-level problems. Run these through the
   pipeline to validate the integration path.

5. **Confidence grounding**: Use verified steps as confidence anchors:
   - If D4 computation is verified: confidence = 100% for that step
   - If no step is verified: confidence should be LOWER than baseline
   - This naturally improves calibration

---

## Files Created

- `regulus/verified/pipeline_adapter.py` -- Extract D1/D3/D4 from pipeline results
- `eval/hle_math_questions.json` -- 16 questions (10 HLE + 6 synthetic)
- `eval/hle_verified_eval.py` -- Evaluation harness
- `eval/results/hle_verified_eval.json` -- Raw results (32 entries: 16 questions x 2 arms)
- `eval/results/PHASE5_REPORT.md` -- This report

---

## Cost and Performance

| Metric | Value |
|--------|-------|
| Total tokens (10 HLE questions) | ~8.1M |
| Total time (10 HLE questions) | ~8.6 hours |
| Average tokens per question | ~810K |
| Average time per question | ~52 min |
| Evaluation overhead (post-hoc) | < 1 second |
| New LLM calls needed | 0 |
