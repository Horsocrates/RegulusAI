# TL CONFIDENCE SCORECARD
# Computed confidence for Team Lead — replaces self-reported confidence
#
# PRINCIPLE: Confidence is NOT a feeling. It is a COMPUTED metric from
# verifiable checkpoints. A model that "feels 99% sure" but checked
# nothing deserves 30%. A model that checked everything and found
# agreement deserves 95%.
#
# Worker confidence = "I believe my computation is correct"
# TL confidence = "I believe this answer will match the expected answer"
# These are DIFFERENT things. Worker can be 100% on a wrong model.
#
# Grounding: L4 (Sufficient Reason) — confidence must have grounds.
# Each ground is a checkpoint. No grounds = no confidence.


# ══════════════════════════════════════════════════════════════
# SECTION A: FRAMEWORK PROBABILITY DISTRIBUTION (from D3)
# ══════════════════════════════════════════════════════════════
#
# When D3 selects a framework, ALL considered frameworks must be
# registered with probability weights that SUM TO 100%.
#
# This is NOT "how confident am I in framework A" — it's
# "what is the probability that framework A is the RIGHT one for
# this problem, given what D1+D2 established."
#
# Example (Q3 Magic Marble):
#   Framework A: Distance-based Markov model     → 45%
#   Framework B: Generating function analysis     → 40%
#   Framework C: Martingale optional stopping     → 15%
#   TOTAL                                         = 100%
#
# Example (B01 Menger Interval):
#   Framework A: Constructive (find norm with L=max)  → 50%
#   Framework B: Impossibility proof (L=0 for all)    → 30%
#   Framework C: Intermediate result (L=specific k)   → 20%
#   TOTAL                                              = 100%
#
# RULES:
# - If only ONE framework considered → it gets max 70% (not 100%)
#   because unconsidered alternatives exist. Remaining 30% = "unknown"
# - If chosen framework gets < 60% → D4 should compute for TOP 2
# - After D4/D5, update weights based on results
# - If D5 answer seems wrong → check: was a 30%+ framework not computed?
#
# FORMAT (TL fills this at D3 and updates at D5):
#
# framework_distribution:
#   - name: "Distance-based Markov"
#     weight_d3: 45       # initial weight at D3
#     weight_d5: 20       # updated after D5 cross-verification
#     computed: true       # was D4/D5 run for this framework?
#     result: "2024/4049"  # answer from this framework (if computed)
#   - name: "Generating function"
#     weight_d3: 40
#     weight_d5: 65
#     computed: true
#     result: "3/10"
#   - name: "Other/Unknown"
#     weight_d3: 15
#     weight_d5: 15
#     computed: false
#     result: null
#   total: 100


# ══════════════════════════════════════════════════════════════
# SECTION B: CONFIDENCE CHECKPOINT SCORECARD
# ══════════════════════════════════════════════════════════════
#
# TL fills each checkpoint with: score (0-1) + brief justification.
# Final TL confidence = weighted product of checkpoint scores.
#
# Checkpoints derived from failure patterns in Q1-B02:
#
# ┌──────────────────────────────────────────────────────────┐
# │ CHECKPOINT                        │ WEIGHT │ SCORE │ WHY │
# ├──────────────────────────────────────────────────────────┤
# │ A. RECOGNITION COMPLETENESS       │  0.10  │  ?/1  │     │
# │    All elements from question      │        │       │     │
# │    registered? No phantoms added?  │        │       │     │
# │    Key challenge at Level 3+?      │        │       │     │
# │                                    │        │       │     │
# │ B. DEFINITION DEPTH               │  0.10  │  ?/1  │     │
# │    All key terms at depth 3+?      │        │       │     │
# │    Ambiguities resolved?           │        │       │     │
# │    Hidden assumptions found?       │        │       │     │
# │                                    │        │       │     │
# │ C. FRAMEWORK SELECTION             │  0.15  │  ?/1  │     │
# │    Multiple frameworks considered? │        │       │     │
# │    Chosen framework weight ≥ 60%?  │        │       │     │
# │    L2 objectivity test passed?     │        │       │     │
# │    (If only 1 framework → max 0.7) │        │       │     │
# │                                    │        │       │     │
# │ D. COMPUTATION COMPLETENESS        │  0.15  │  ?/1  │     │
# │    All criteria applied?           │        │       │     │
# │    Edge cases checked?             │        │       │     │
# │    Disconfirming evidence sought?  │        │       │     │
# │                                    │        │       │     │
# │ E. CROSS-VERIFICATION             │  0.20  │  ?/1  │     │
# │    Sanity checks passed?           │        │       │     │
# │    Alternative method attempted?   │        │       │     │
# │    Small case verified?            │        │       │     │
# │    Methods agree?                  │        │       │     │
# │    (If no cross-verify → max 0.5)  │        │       │     │
# │                                    │        │       │     │
# │ F. PROOF INTEGRITY                 │  0.15  │  ?/1  │     │
# │    Every step has justification?   │        │       │     │
# │    No hasty generalizations?       │        │       │     │
# │    Boundary conditions checked?    │        │       │     │
# │    Cited theorems verifiable?      │        │       │     │
# │    (If "iff" claimed → both dirs   │        │       │     │
# │     proven? Not just illustrated?) │        │       │     │
# │                                    │        │       │     │
# │ G. ANSWER FORMAT & MAGNITUDE       │  0.15  │  ?/1  │     │
# │    Answer in expected format?      │        │       │     │
# │    Magnitude reasonable?           │        │       │     │
# │    Exact form preserved?           │        │       │     │
# │    No simplification artifacts?    │        │       │     │
# └──────────────────────────────────────────────────────────┘
#
# COMPUTATION:
#   raw_score = Σ (weight_i × score_i)   # weighted sum, range [0, 1]
#   tl_confidence = round(raw_score × 100)  # percentage
#
# HARD CAPS (override computed score):
#   - No cross-verification at all → max 50%
#   - Only 1 framework considered → max 65%
#   - Sanity check failed → max 45%
#   - Two methods disagree → max 40%
#   - "iff" theorem with only forward proof → max 35%
#   - Magnitude obviously wrong (P ≈ 10⁻¹¹ for simple problem) → max 25%
#
# These caps are STRUCTURAL — they cannot be overridden by
# "but I feel confident". They encode lessons from Q1-B02.


# ══════════════════════════════════════════════════════════════
# SECTION C: JSON OUTPUT FORMAT
# ══════════════════════════════════════════════════════════════

# TL produces this after D5 (and updates after D6):

"""
"tl_confidence_scorecard": {
  "framework_distribution": [
    {
      "name": "Distance-based Markov model",
      "weight_d3": 45,
      "weight_d5": 20,
      "computed": true,
      "result": "2024/4049"
    },
    {
      "name": "Generating function analysis",
      "weight_d3": 40,
      "weight_d5": 65,
      "computed": true,
      "result": "3/10"
    },
    {
      "name": "Other/Unknown",
      "weight_d3": 15,
      "weight_d5": 15,
      "computed": false,
      "result": null
    }
  ],
  "checkpoints": {
    "A_recognition":       {"score": 0.9, "note": "All elements found, key challenge identified"},
    "B_definition":        {"score": 0.8, "note": "Geometric jumps defined, boundary semantics clarified"},
    "C_framework":         {"score": 0.6, "note": "2 frameworks considered, chosen at 45% — marginal"},
    "D_computation":       {"score": 0.7, "note": "Computation complete but no edge case check"},
    "E_cross_verification":{"score": 0.3, "note": "Two methods DISAGREE (2024/4049 vs 3/10) — unresolved"},
    "F_proof_integrity":   {"score": 0.5, "note": "Model assumption 'walk hits boundary exactly' not verified"},
    "G_answer_format":     {"score": 0.8, "note": "Fraction format correct, magnitude plausible for probability"}
  },
  "raw_score": 0.59,
  "hard_caps_triggered": [
    "two_methods_disagree → max 40%",
    "sanity_check_suspicious → max 45%"
  ],
  "tl_confidence": 40,
  "worker_confidence": 99,
  "confidence_gap": 59,
  "gap_note": "Worker is 99% confident in computation, TL is 40% confident in answer. Gap = 59pp indicates Worker solved wrong model confidently."
}
"""


# ══════════════════════════════════════════════════════════════
# SECTION D: CONFIDENCE GAP ANALYSIS
# ══════════════════════════════════════════════════════════════
#
# confidence_gap = worker_confidence - tl_confidence
#
# | Gap    | Meaning                                    | Action              |
# |--------|--------------------------------------------|---------------------|
# | 0-10   | Normal — Worker and TL agree               | Proceed             |
# | 10-25  | Mild concern — TL sees risk Worker doesn't | Note in conspectus  |
# | 25-50  | Serious — structural issue likely           | Iterate D5 or D4    |
# | 50+    | Critical — Worker on wrong model entirely   | Return to D3, try   |
# |        |                                            | alternative framework|
#
# B02 example: Worker=100%, TL should be ~25% (magnitude absurd)
# Gap = 75pp → CRITICAL → return to D3 → "try less restrictive
# interpretation of dominance condition"
#
# B01 example: Worker=100%, TL should be ~35% (iff not proven)
# Gap = 65pp → CRITICAL → return to D5 → "prove backward direction
# of iff-theorem rigorously, not by illustration"


# ══════════════════════════════════════════════════════════════
# SECTION E: INTEGRATION INTO PIPELINE
# ══════════════════════════════════════════════════════════════
#
# WHERE in the pipeline:
#
# D3 → TL initializes framework_distribution (weights sum to 100%)
#
# D5 → Worker reports worker_confidence (self-assessed)
#     → TL fills checkpoint scorecard (A-G)
#     → TL computes tl_confidence
#     → TL computes confidence_gap
#     → If gap > 25 → iterate or return
#
# D6 → TL updates framework weights based on reflection
#     → If D6 finds proof gap → update F_proof_integrity → recompute
#     → Final tl_confidence goes into result.json
#
# FINAL ANSWER includes:
#   "confidence": {
#     "worker": 99,
#     "tl": 40,
#     "gap": 59,
#     "method": "scorecard_v1",
#     "hard_caps": ["two_methods_disagree"]
#   }


# ══════════════════════════════════════════════════════════════
# SECTION F: RETROACTIVE ANALYSIS (Q1-B02)
# ══════════════════════════════════════════════════════════════
#
# What WOULD the scorecard have produced for each question?
#
# Q1 (Continuum, expected=0, got=1, self-reported=80%):
#   E_cross_verify = 0.3 (no counterexample search)
#   F_proof = 0.4 (hidden assumption: cl(int(A)) proper)
#   C_framework = 0.5 (only standard continua, no exotic)
#   → raw ≈ 0.52, cap: no_cross_verify → max 50%
#   → TL confidence: 50% (vs 80% self-reported)
#   → Gap: 30pp → iterate
#
# Q2 (Cone packing, expected=10, got=10 ✅):
#   All checkpoints high, cross-verify passed
#   → TL confidence: ~85% → correct answer, calibrated
#
# Q3 (Marble, expected=3/10, got=2024/4049, self-reported=99%):
#   E_cross_verify = 0.2 (symmetry suspicious, no alt method)
#   F_proof = 0.4 (model assumption: walk hits boundary exactly)
#   → raw ≈ 0.48, cap: sanity_suspicious → max 45%
#   → TL confidence: 45% (vs 99% self-reported)
#   → Gap: 54pp → CRITICAL → return to D3
#
# Q6 (Triangle grid, expected=84, got=80, self-reported=100%):
#   E_cross_verify = 0.2 (no small case verification)
#   F_proof = 0.5 (formula not verified on concrete triangle)
#   → raw ≈ 0.50, cap: no_cross_verify → max 50%
#   → TL confidence: 50% (vs 100% self-reported)
#   → Gap: 50pp → CRITICAL → iterate D5
#
# B01 (Menger, expected=1, got=0, self-reported=100%):
#   E_cross_verify = 0.2 (no search for intermediate norms)
#   F_proof = 0.2 (iff theorem, backward direction by illustration only)
#   → raw ≈ 0.38, cap: iff_not_proven → max 35%
#   → TL confidence: 35% (vs 100% self-reported)
#   → Gap: 65pp → CRITICAL → return to D3
#
# B02 (Dominance, expected≈0.04, got≈10⁻¹¹, self-reported=100%):
#   E_cross_verify = 0.1 (magnitude absurd, no sanity check)
#   G_magnitude = 0.1 (10⁻¹¹ for simple partition → obviously wrong)
#   → raw ≈ 0.30, cap: magnitude_wrong → max 25%
#   → TL confidence: 25% (vs 100% self-reported)
#   → Gap: 75pp → CRITICAL → return to D2 (reinterpret condition)
#
# CONCLUSION: Scorecard would have prevented ALL high-confidence
# wrong answers. Every ❌ with self-reported >80% would have been
# capped at 25-50%. The gap metric (>50pp) would have triggered
# returns in 4/5 wrong cases.
