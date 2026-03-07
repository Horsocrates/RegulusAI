# HLE Pipeline Evaluation Report
## Verified D1-D6 Pipeline v2 — Thinking Log Analysis

**Date:** 2026-03-07
**Model:** claude-sonnet-4-20250514
**Pipeline:** VerifiedPipeline (regulus.verified.verified_pipeline)
**Questions:** 2 (from HLE Math subset)
**Accuracy:** 0/2 (0%)

---

## 1. Executive Summary

Two HLE (Humanity's Last Exam) questions were run through the full Verified D1-D6 Pipeline with real Claude API calls. Both questions received structurally valid pipeline certificates (all gates passed, REFLECT validated, ERR chain verified) but produced **incorrect final answers with high confidence** (90% and 88%).

**Key finding:** The pipeline successfully verifies *structural integrity* (ERR consistency, domain ordering, gate checks) but has no mechanism to verify *mathematical correctness*. This is by design — the Zero-Gate checks structural properties, not computational accuracy.

---

## 2. Question Details

### Q3 — Probability (Markov Chain Absorption)
- **Question:** Magic marble at bin 0, teleports to bin n+i with probability (1/3)^|i|. Portal at 2025 (escape), torch at 2024 (melt). P(escape | escape ∨ melt)?
- **Expected:** 3/10
- **Got:** 1/2025 (bug: should report 4/9 from iteration 2)
- **Correct answer from neither iteration**

### Q6 — Combinatorial Geometry (Grid Squares)
- **Question:** Isosceles right triangle (18, 18, 18√2), no lattice points on perimeter. Max grid squares intersected?
- **Expected:** 84
- **Got:** 60
- **Off by 24 (28.6% error)**

---

## 3. Thinking Log Trace — Q3 (Probability)

### Iteration 1 (t=0–94.7s, 6 LLM calls)

| Time  | Phase      | Output | Conf |
|-------|------------|--------|------|
| 12.1s | D6-ASK     | Decomposition: Gefragte=escape probability, Erfragte=exact probability value | — |
| 22.1s | D1-Recog   | "Markov chain absorption problem with geometric transition probs" | 95% |
| 36.3s | D2-Clarify | "Random walk, reach 2025 before 2024, (1/3)^|i| transitions" | 95% |
| 46.3s | D3-Frame   | "Absorbing Markov Chain framework" | 92% |
| 65.9s | D4-Compare | **"1/2" (symmetry argument — WRONG)** | 95% |
| 78.0s | D5-Infer   | **"1/2025" (non-sequitur from D4)** | 95% |
| 94.7s | D6-REFLECT | **FAIL** — "ERR chain: elements inconsistent" + "no target domain" | — |

**Answer drift iter 1:** D4 claims "1/2 by symmetry" (incorrect — the walk is NOT symmetric because 2024 and 2025 are adjacent). D5 somehow produces "1/2025" which has no logical connection to D4's "1/2".

**REFLECT caught the inconsistency:** D6-REFLECT correctly identified that elements were inconsistent across domains (D4→D5 jump from 1/2 to 1/2025 is unjustified). This is the pipeline's structural verification working.

### Iteration 2 (t=94.7–178.3s, 7 LLM calls)

| Time   | Phase      | Output | Conf |
|--------|------------|--------|------|
| 105.6s | D1-Recog   | Same recognition (geometric Markov chain) | 95% |
| 122.1s | D2-Clarify | Same clarification | 95% |
| 131.2s | D3-Frame   | **"Harmonic function analysis"** (upgraded from iter 1) | 95% |
| 153.0s | D4-Compare | **"4/9" (harmonic function h(n), boundary h(2024)=0, h(2025)=1)** | 85% |
| 166.2s | D5-Infer   | **"1/3"** | 85% |
| 178.3s | D6-REFLECT | PASS — final_answer="4/9" | — |

**Answer drift iter 2:** D4 switches to harmonic function approach and gets "4/9". D5 then adjusts to "1/3" (closer to correct 3/10 but still wrong). REFLECT accepts "4/9" as final.

**Neither iteration produced 3/10.** The fundamental issue is that the transition kernel is NOT a standard random walk — the (1/3)^|i| distribution has geometric tails, making the harmonic function analysis non-trivial.

### Q3 Bug Found

The runner's `final_answer` extraction (lines 506–509) takes the **first** log entry with a `final_answer` field, which is the **failed** iteration 1 REFLECT ("1/2025"). It should take the last valid one ("4/9"). With the bug fixed, Q3 would report "4/9" (still wrong, but a better answer than "1/2025").

---

## 4. Thinking Log Trace — Q6 (Combinatorial Geometry)

### Single Iteration (t=0–80.6s, 7 LLM calls)

| Time  | Phase      | Output | Conf |
|-------|------------|--------|------|
|  9.6s | D6-ASK     | Decomposition: Gefragte=max grid squares, Erfragte=integer k | — |
| 19.1s | D1-Recog   | "Geometric optimization — avoid lattice points, max grid squares" | 85% |
| 30.8s | D2-Clarify | "Isosceles right triangle, legs 18, hypotenuse 18√2" | 95% |
| 41.8s | D3-Frame   | "Geometric Optimization with Grid Intersection Analysis" | 92% |
| 59.0s | D4-Compare | **"59" — right angle at (0.5, 0.5), legs to (18.5, 0.5) and (0.5, 18.5)** | 85% |
| 68.3s | D5-Infer   | **"60" (adjusted from D4's 59)** | 85% |
| 80.6s | D6-REFLECT | PASS — final_answer="60" | — |

**Answer drift:** D4 computes 59 with a specific placement, D5 adjusts to 60 (adds 1 for a boundary correction). The correct answer is 84, meaning the model undercounts by 24 grid squares.

**Likely error source:** The axis-aligned placement at (0.5, 0.5) is suboptimal — the problem asks for the MAXIMUM over all valid placements, and a tilted or strategically offset triangle can intersect more grid squares. The model assumes axis-alignment without exploring rotated placements.

---

## 5. Pipeline Mechanics Analysis

### 5.1 What Worked

| Feature | Result |
|---------|--------|
| D6-ASK decomposition | ✅ Both questions correctly decomposed |
| Gate consistency checks | ✅ All 10 gates passed (5 per question) |
| D6-REFLECT validation | ✅ Caught ERR inconsistency in Q3 iter 1 |
| Iteration mechanism | ✅ Q3 ran 2 iterations after REFLECT failure |
| Certificate generation | ✅ Both certificates structurally valid |
| Thinking log trace | ✅ Full trace with timestamps, token counts |

### 5.2 What Didn't Work

| Issue | Explanation |
|-------|-------------|
| Mathematical accuracy | 0/2 correct — pipeline verifies structure, not math |
| D5 inference quality | D5 drifts from D4 in both questions (1/2→1/2025, 59→60) |
| Confidence calibration | 90%/88% confidence on 0% accuracy = 89pp calibration gap |
| Gate depth | Gates check alignment/coverage/consistency as booleans self-reported by LLM |
| Single-model limitation | Same model (Sonnet) runs all domains — no diversity of reasoning |

### 5.3 Calibration Error

| Question | Confidence | Correct | Calibration Error |
|----------|-----------|---------|-------------------|
| Q3 | 90% | ✗ | 90pp |
| Q6 | 88% | ✗ | 88pp |
| **Average** | **89%** | **0%** | **89pp** |

This matches Phase 5 findings (68.4pp on 10 questions). The pipeline's confidence adjustment in D6-REFLECT is insufficient — it should lower confidence when:
- The problem is HLE-level difficulty (competition math)
- D4→D5 answer changes significantly
- Multiple approaches yield different answers

---

## 6. Comparison with Phase 5

| Metric | Phase 5 (10 Q, post-hoc) | Phase 6 (2 Q, inline) |
|--------|--------------------------|----------------------|
| Accuracy | 0/10 | 0/2 |
| Avg confidence | 68% | 89% |
| Calibration gap | 68.4pp | 89pp |
| D4 Math Verifier triggered | 0/10 | N/A (no math verifier) |
| REFLECT caught errors | N/A | 1/4 (Q3 iter 1) |
| Iterations used | 1 (fixed) | 1.5 avg |

**Regression:** Inline pipeline has WORSE calibration (89pp vs 68.4pp). The structured domain decomposition gives the model false confidence — it "feels" more rigorous without being more accurate.

---

## 7. Token Usage

| Question | LLM Calls | Est. Input Tokens | Est. Output Tokens | Time |
|----------|-----------|-------------------|-------------------|------|
| Q3 | 13 | ~6,000 | ~8,000 | 178.3s |
| Q6 | 7 | ~3,000 | ~4,000 | 80.6s |
| **Total** | **20** | **~9,000** | **~12,000** | **258.9s** |

Q3 cost ~2x due to the iteration retry.

---

## 8. Bug Report

**File:** `eval/run_hle_pipeline.py`, lines 503–509
**Bug:** `final_answer` extraction iterates through ALL log entries and takes the first one with a `final_answer` field. When iteration 1's REFLECT fails validation but has a `final_answer` in its log data, it's taken instead of iteration 2's valid REFLECT answer.

**Impact:** Q3 reports "1/2025" (iter 1 failed REFLECT) instead of "4/9" (iter 2 valid REFLECT).

**Fix:** Iterate in reverse order, or only consider log entries where validation passed.

---

## 9. Recommendations

### Short-term (Pipeline v2.1)
1. **Fix final_answer bug** — take from last PASSING REFLECT
2. **Add math cross-verification** — compute answer two ways, compare
3. **Lower confidence on hard problems** — if complexity≥2 and answer changes between iterations, cap at 60%
4. **D4-D5 consistency gate** — flag when D5 answer differs from D4 answer

### Medium-term (Pipeline v3)
5. **Multi-model ensemble** — run D4 with multiple models, take consensus
6. **Symbolic verification** — for arithmetic, verify with SymPy/Wolfram
7. **ERR chain depth** — currently checks boolean consistency, should check logical entailment
8. **Calibration training** — learn confidence→accuracy mapping from evaluation data

### Long-term
9. **Expand theorem library** — Phase 5 showed IVT/EVT insufficient for HLE-level math
10. **Formal verification bridge** — connect to Coq proofs where problem matches library theorems

---

## 10. Raw Data Reference

- **Full results:** `eval/results/hle_pipeline_results.json`
- **Pipeline code:** `regulus/verified/verified_pipeline.py`
- **Runner code:** `eval/run_hle_pipeline.py`
- **Coq proofs:** `_tos_coq_clone/src/{DomainTypes,DomainValidation,PipelineSemantics,PipelineExtraction}.v`
- **Phase 5 report:** `eval/results/PHASE5_REPORT.md`
