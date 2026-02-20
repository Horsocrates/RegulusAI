# PIPELINE v5 — Framework-First Architecture
#
# Core changes:
# 1. D3 becomes a MULTI-STEP domain (enumerate → analyze → distribute → select)
# 2. D6-early validates framework list BEFORE D4 computation
# 3. Two-level confidence: C_worker (computation) + C_approach (framework)
# 4. Gap > 20pp → return with diagnostic questions
# 5. D4 may compute multiple frameworks
#
# Grounding in Theory of Systems:
# - P2 (Criterion Precedence): Framework must be validated BEFORE computation
# - L3 (Excluded Middle): Either framework A is correct or it is not.
#   If we cannot exclude alternatives, we must compute them.
# - L4 (Sufficient Reason): Confidence must have sufficient grounds.
#   Two levels because two different things need grounding.


# ════════════════════════════════════════════════════════════════
# SECTION 1: D3 MULTI-STEP ALGORITHM
# ════════════════════════════════════════════════════════════════
#
# OLD D3: Worker picks 1 framework, TL checks, move to D4.
# NEW D3: Three sub-steps + D6-early validation.
#
# D3.1 — ENUMERATE (Worker)
#   "List ALL plausible mathematical frameworks/approaches for this problem.
#    Do NOT select yet. Do NOT filter. Be exhaustive.
#    For each framework, state:
#    - Name and brief description
#    - Why it MIGHT apply (what features of the problem match)
#    - Why it MIGHT NOT apply (what features don't match or are uncertain)
#    - Key assumptions required"
#
#   Output: framework_candidates[] (unranked list)
#
# D3.2 — ANALYZE & DISTRIBUTE (Worker)
#   "For each candidate framework:
#    - Score fit to problem (0-100)
#    - Identify critical assumptions (PROVEN/IMPORTED/ASSUMED)
#    - Estimate tractability (can we actually compute with this?)
#    - Assign probability weight
#
#    Weights MUST sum to 100%. Rules:
#    - No single framework > 70% unless all others explicitly refuted
#    - 'Other/Unknown' category always gets ≥ 5%
#    - If top framework < 50%, this is a HIGH UNCERTAINTY problem"
#
#   Output: framework_distribution[] (ranked, with weights)
#
# D3.3 — SELECT FOR COMPUTATION (TL decides)
#   TL reviews distribution and selects which frameworks to compute in D4:
#
#   | Top framework weight | Action |
#   |---------------------|--------|
#   | ≥ 70%               | Compute top-1 only (strong signal) |
#   | 50-69%              | Compute top-2 (moderate uncertainty) |
#   | < 50%               | Compute top-3 (high uncertainty) |
#   | All < 30%           | RED FLAG — return to D2 for deeper clarification |
#
#   Output: frameworks_to_compute[] (1-3 frameworks for D4)
#
# D3-D6-EARLY — FRAMEWORK VALIDATION (TL sends to Worker as D6-early)
#   BEFORE D4, run a quick D6 check:
#   "Review the framework list. Are important approaches MISSING?
#    Check:
#    - Is there a standard textbook approach not listed?
#    - Is there a computational/numerical approach not listed?
#    - Is there an elementary approach (small cases, direct counting)?
#    - Does the problem have symmetry that suggests a specific framework?
#    - Are the IMPORTED assumptions in each framework justified?"
#
#   If D6-early finds missing framework → add to distribution, re-rank.
#   If D6-early confirms list → proceed to D4.


# ════════════════════════════════════════════════════════════════
# SECTION 2: D4 MULTI-FRAMEWORK COMPUTATION
# ════════════════════════════════════════════════════════════════
#
# D4 receives frameworks_to_compute[] (1-3 frameworks).
# For each framework, Worker executes full D4:
#   - Apply criteria systematically
#   - Show computation trace
#   - Report answer + worker_confidence for THIS framework
#
# If only 1 framework selected: standard D4.
# If 2+ frameworks selected:
#   D4 runs sequentially for each. TL collects results:
#
#   framework_results:
#     - name: "Generating function"
#       answer: "3/10"
#       worker_confidence: 85%
#       assumptions_used: [A1, A3]
#     - name: "Distance-based Markov"
#       answer: "2024/4049"
#       worker_confidence: 92%
#       assumptions_used: [A1, A2, A4]
#
# COMPARISON:
#   If answers AGREE → strong signal, approach confidence boost
#   If answers DISAGREE → disagreement IS information:
#     TL must identify which assumptions differ
#     The framework with FEWER unverified imports is preferred
#     Both answers reported to D5 with full context
#
# COST: ~$0.50-1.00 extra per additional framework on GLM-5.
# Worth it for HLE where 1 wrong answer = wasted $1.50 anyway.


# ════════════════════════════════════════════════════════════════
# SECTION 3: TWO-LEVEL CONFIDENCE SYSTEM
# ════════════════════════════════════════════════════════════════
#
# LEVEL 1: C_computation (Worker-reported)
#   "Given this framework, how confident am I that the COMPUTATION is correct?"
#   Measures: arithmetic accuracy, formula application, edge cases.
#   Source: Worker self-assessment after D4/D5.
#   Range: 0-100%
#
# LEVEL 2: C_approach (TL-computed via scorecard)
#   "How confident am I that we're using the RIGHT APPROACH to this problem?"
#   Measures: framework selection, assumption validity, cross-verification.
#   Source: TL scorecard (8 checkpoints A-H + hard caps).
#   Range: 0-100%
#
# FINAL CONFIDENCE = min(C_computation, C_approach)
#   Rationale: Correct computation on wrong approach = wrong answer.
#              Wrong computation on right approach = wrong answer.
#              Both must be high for answer to be trusted.
#
# EXAMPLE Q3 (Magic Marble):
#   C_computation = 92% (Markov chain solved correctly within its model)
#   C_approach = 45% (model assumption "walk hits boundary exactly" unverified)
#   Final = min(92, 45) = 45%
#   → This is informative! Computation is fine, approach is suspect.
#
# EXAMPLE Q8 (PPAVs):
#   C_computation = 80% (theta subgroup calculation internally consistent)
#   C_approach = 55% (framework may be wrong for this sequence)
#   Final = min(80, 55) = 55%
#
# EXAMPLE Q2 (Cone packing, ✅):
#   C_computation = 90% (systematic case analysis complete)
#   C_approach = 85% (multiple methods checked, assumptions proven)
#   Final = min(90, 85) = 85%
#   → Both high → likely correct


# ════════════════════════════════════════════════════════════════
# SECTION 4: TL CONFIDENCE CONSPECTUS
# ════════════════════════════════════════════════════════════════
#
# TL maintains a CONFIDENCE section in conspectus, updated at each domain.
# Format:
#
# ## CONFIDENCE TRACKER
#
# ### Framework Distribution (from D3)
# | Framework | D3 Weight | D4 Result | D5 Updated Weight |
# |-----------|:---------:|-----------|:-----------------:|
# | Framework A | 55% | answer_a | 30% |
# | Framework B | 30% | answer_b | 60% |
# | Other/Unknown | 15% | — | 10% |
#
# ### C_computation (Worker)
# Worker's confidence in calculation correctness: **X%**
# Basis: [Worker's justification]
#
# ### C_approach (TL Scorecard)
# | Checkpoint | Weight | Score | Note |
# |------------|:------:|:-----:|------|
# | A. Recognition | 0.10 | ?/1 | |
# | B. Definition | 0.08 | ?/1 | |
# | C. Framework selection | 0.12 | ?/1 | |
# | D. Computation | 0.12 | ?/1 | |
# | E. Cross-verification (independence!) | 0.18 | ?/1 | |
# | F. Proof integrity | 0.12 | ?/1 | |
# | G. Format & magnitude | 0.13 | ?/1 | |
# | H. Assumption independence | 0.15 | ?/1 | |
# | **Raw score** | | **Σ** | |
#
# Hard caps triggered: [list or "none"]
# C_approach = min(caps, raw×100) = **Y%**
#
# ### Gap Analysis
# C_computation: X%
# C_approach: Y%
# Gap: |X - Y| = Zpp
# Final confidence: min(X, Y) = **W%**
#
# | Gap | Action |
# |-----|--------|
# | ≤ 10pp | Proceed |
# | 11-20pp | Note concern, continue |
# | 21-35pp | ITERATE — ask diagnostic questions |
# | 36-50pp | RETURN to D3 — try second framework |
# | > 50pp | RETURN to D2 — re-examine problem |


# ════════════════════════════════════════════════════════════════
# SECTION 5: GAP-TRIGGERED RETURN WITH DIAGNOSTIC QUESTIONS
# ════════════════════════════════════════════════════════════════
#
# When gap > 20pp, TL doesn't just say "iterate" — TL generates
# SPECIFIC DIAGNOSTIC QUESTIONS targeting the confidence gap.
#
# Template:
#   "Current C_approach = Y%. To raise it to (Y+N)%, I need answers to:
#    1. [Specific question about framework validity]
#    2. [Specific question about assumption verification]
#    3. [Specific question about missing cross-verification]"
#
# These questions go to Worker as the iteration instruction.
# Worker must ADDRESS each question explicitly.
#
# EXAMPLE (Q7, gap=40pp):
#   C_approach = 55%. To raise to 75%, I need:
#   1. "Prove that 120° junction angles maximize area-per-length,
#      not just minimize total edge length (Steiner). Show the
#      variational calculus for THIS objective function."
#   2. "Try optimizing with FREE angles (θ₁,θ₂,θ₃ as variables).
#      Does the optimum still give equilateral?"
#   3. "Verify on a small case: for a 1-cut problem, what's optimal?"
#
# EXAMPLE (Q8, gap=25pp):
#   C_approach = 55%. To raise to 75%, I need:
#   1. "Verify D_1=2 against known dimension of moduli of elliptic curves
#      (should be 1, not 2). If D_1≠2, the formula D_g=2^g is wrong."
#   2. "Check OEIS or standard references: does 1,6,28,120 or 2,4,8,16
#      appear as a known sequence in algebraic geometry?"
#   3. "Try computing D_2 from scratch using Siegel modular forms
#      (different framework from theta subgroups)."
#
# QUESTION GENERATION RULES:
#   - Each question must target a SPECIFIC checkpoint score
#   - Questions must be ANSWERABLE by the Worker
#   - Answering YES raises the checkpoint score by stated amount
#   - Answering NO lowers it (and may trigger framework switch)
#   - Max 3-5 questions per iteration


# ════════════════════════════════════════════════════════════════
# SECTION 6: D6 FRAMEWORK REVIEW CHECKLIST
# ════════════════════════════════════════════════════════════════
#
# D6 (final reflection) must verify the framework choice was sound.
# This is separate from D6-early (which checks before D4).
# D6-final checks AFTER seeing the answer.
#
# D6 FRAMEWORK REVIEW:
#
# 1. RETROSPECTIVE FIT
#    "Now that we have an answer, does it 'look right' for this problem?"
#    - Does the answer have expected mathematical properties?
#    - Is the answer a known sequence / known constant / expected form?
#    - Does the answer satisfy ALL constraints from D1?
#
# 2. FRAMEWORK ALTERNATIVES
#    "Were there frameworks we didn't compute? Should we have?"
#    - Check D3 distribution: any framework ≥ 20% that wasn't computed?
#    - Did the computation reveal that chosen framework has issues?
#    - Would a simpler/more elementary approach give a different answer?
#
# 3. ASSUMPTION FINAL CHECK
#    "Now that we have the answer, do all assumptions still hold?"
#    - Cross-check answer against assumption register
#    - Does the answer depend on any UNVERIFIED_IMPORT?
#    - If assumption A were false, would the answer change?
#
# 4. CONFIDENCE ADJUSTMENT
#    After D6 review, TL may adjust C_approach up or down:
#    - Framework fits well, answer looks right → +5-10pp
#    - Answer has unexpected properties → -5-10pp
#    - Missed framework found → -15pp, consider return
#    - Assumption invalidated → -20pp, RETURN to D3
#
# D6 CHECKLIST FOR RAISING C_approach:
#
# | Check | If YES → | If NO → |
# |-------|----------|---------|
# | Answer satisfies ALL constraints from D1 | +5 | -10 |
# | Answer is in expected mathematical form | +5 | -5 |
# | No unverified imports affect the answer | +10 | -15 |
# | Cross-verification methods are independent | +10 | -10 |
# | Small case verification matches | +10 | -5 |
# | Framework is standard for this problem type | +5 | -10 |
# | No alternative framework gives different answer | +10 | -15 |
# | All cited theorems are correctly applied HERE | +5 | -20 |


# ════════════════════════════════════════════════════════════════
# SECTION 7: PIPELINE FLOW DIAGRAM
# ════════════════════════════════════════════════════════════════
#
# D1 → D2 (+ Assumption Register)
#  ↓
# D3.1 — Enumerate all frameworks
#  ↓
# D3.2 — Analyze & distribute weights (sum=100%)
#  ↓
# D3.3 — TL selects top-N for computation
#  ↓
# D6-early — Validate framework list (missing any?)
#  ↓ (add missing? re-rank?)
# D4 — Compute each selected framework
#  ↓ (1-3 answers)
# D5 — Infer + Cross-verify + Assumption audit
#  ↓
# D6-final — Framework review + confidence adjustment
#  ↓
# TL: Fill scorecard → C_approach
#     Record C_computation from Worker
#     Gap = |C_computation - C_approach|
#  ↓
# Gap ≤ 20pp? → DONE, output min(C_comp, C_approach)
# Gap > 20pp? → Generate diagnostic questions → iterate
# Gap > 35pp? → Return to D3, try next framework
# Gap > 50pp? → Return to D2, re-examine problem
