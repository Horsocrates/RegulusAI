# PATCH 10: Assumption Independence Audit
# SCORECARD v2: Fixes for shared-blindspot problem
#
# Root cause: Q7 — TL gave E=1.0 (cross-verification) because "two methods
# agree". But both methods shared the same false assumption (120° angles
# from Steiner problem). Agreement between dependent methods is worthless.
#
# Theory of Systems grounding:
# - L1 (Identity): A = A. An assumption imported from problem B is NOT
#   proven in problem A just because it was proven in B. The identity of
#   the problem matters — same property, different context = different claim.
# - L3 (Excluded Middle): Either 120° IS optimal for this problem, or it
#   IS NOT. "It was optimal in Steiner" is not evidence for either.
# - P2 (Criterion Precedence): The criterion (120° optimality) must be
#   established IN THIS PROBLEM before being applied.
#
# Date: 2026-02-18
# Triggered by: Q7 (false axiom transfer from Steiner → area maximization)


# ════════════════════════════════════════════════════════════════
# PART 1: ASSUMPTION REGISTER (D2 addition)
# ════════════════════════════════════════════════════════════════
#
# Every assumption entering the reasoning must be registered with its SOURCE.
# Three categories:
#
# PROVEN:    Derived within this problem's D1-D4 chain.
#            Example: "triangle inequality holds" (axiom of metric space,
#            stated in problem)
#
# IMPORTED:  Taken from a different problem/theorem and applied here.
#            Example: "120° angles are optimal" (from Steiner tree problem)
#            REQUIRES: explicit justification why it applies HERE.
#            WITHOUT justification → status = UNVERIFIED_IMPORT
#
# ASSUMED:   Neither proven nor imported — just taken as given.
#            Example: "the optimal structure is connected"
#            Lower risk than IMPORTED (at least it's honest)
#
# FORMAT (Worker fills at D2, TL verifies):
#
# assumption_register:
#   - id: A1
#     content: "Junction angles of 120° maximize enclosed area per unit length"
#     source: IMPORTED
#     origin: "Steiner tree problem — 120° minimizes total edge length"
#     transfer_justified: false
#     justification: null  # or "because [reason it applies here]"
#     impact_if_wrong: "Optimal shape changes entirely — angles become free variables"
#
#   - id: A2
#     content: "Optimal cut structure is a tree (no cycles)"
#     source: PROVEN
#     origin: "D4 step 2 — cycle would waste length on shared boundary"
#     transfer_justified: true
#     justification: "Proven by contradiction in D4"
#     impact_if_wrong: "Low — would need to check cyclic structures"
#
# RULES:
# - Every IMPORTED assumption with transfer_justified=false is an
#   UNVERIFIED_IMPORT → automatic flag for D5/D6
# - Count of unverified imports directly caps confidence (see Part 3)
# - TL MUST check: "Is this proven HERE or just borrowed?"


# ════════════════════════════════════════════════════════════════
# PART 2: CROSS-VERIFICATION INDEPENDENCE CHECK (Scorecard E fix)
# ════════════════════════════════════════════════════════════════
#
# Current problem: E=1.0 if "two methods agree", but agreement is
# meaningless if both methods share assumptions.
#
# FIX: Before scoring E, TL must verify METHOD INDEPENDENCE.
#
# Two methods are INDEPENDENT if:
#   1. They use different mathematical frameworks (not just different
#      calculations within the same framework)
#   2. They do NOT share unverified assumptions
#   3. If assumption A is used in method 1, method 2 either:
#      a) Does not use A, OR
#      b) Independently verifies A
#
# SCORING:
#   Methods independent + agree → E = 1.0
#   Methods share 1+ assumptions but agree → E = 0.5 max
#     (agreement on shared foundation proves nothing)
#   Methods independent + disagree → E = 0.3, but FLAG is valuable
#   Only one method → E = 0.3 max
#   No cross-verification attempted → E = 0.0
#
# Q7 retroactive:
#   Method 1: Y-shape enumeration with 120° angles → A (equilateral)
#   Method 2: Area computation with 120° angles → confirms A
#   Shared assumption: "120° angles are optimal" (UNVERIFIED_IMPORT)
#   → Methods NOT independent → E = 0.5 max (not 1.0)
#   → With 1 unverified import → additional cap
#   → TL confidence would drop from 99% to ~55%


# ════════════════════════════════════════════════════════════════
# PART 3: SCORECARD v2 — UPDATED HARD CAPS
# ════════════════════════════════════════════════════════════════
#
# Add to existing hard caps:
#
# NEW HARD CAPS:
#
# | Condition                                    | Max Confidence |
# |----------------------------------------------|:--------------:|
# | 1+ UNVERIFIED_IMPORT in assumption register  | 60%            |
# | 2+ UNVERIFIED_IMPORTS                        | 45%            |
# | Cross-verification methods share assumptions | 55%            |
# | Key result depends on IMPORTED theorem       | 50%            |
# |   without proof it applies to THIS problem   |                |
# | D3 framework chosen by analogy to different  | 50%            |
# |   problem without proving analogy is valid   |                |
#
# UPDATED CHECKPOINT E SCORING:
#
# | Situation                              | E score |
# |----------------------------------------|:-------:|
# | Independent methods agree              | 1.0     |
# | Independent methods disagree           | 0.3     |
# | Dependent methods agree (shared assumptions) | 0.5 max |
# | Dependent methods disagree             | 0.2     |
# | One method only                        | 0.3 max |
# | No cross-verification                  | 0.0     |
#
# NEW CHECKPOINT H (added, weight redistributed):
#
# | Checkpoint                        | OLD Weight | NEW Weight |
# |-----------------------------------|:----------:|:----------:|
# | A. Recognition completeness       | 0.10       | 0.10       |
# | B. Definition depth               | 0.10       | 0.08       |
# | C. Framework selection             | 0.15       | 0.12       |
# | D. Computation completeness        | 0.15       | 0.12       |
# | E. Cross-verification             | 0.20       | 0.18       |
# | F. Proof integrity                 | 0.15       | 0.12       |
# | G. Answer format & magnitude       | 0.15       | 0.13       |
# | **H. Assumption independence**     | —          | **0.15**   |
# |                                    | 1.00       | 1.00       |
#
# CHECKPOINT H SCORING:
#   1.0 = All assumptions PROVEN within this problem
#   0.8 = Imports exist but all transfer_justified=true with proof
#   0.5 = 1 unverified import, non-critical
#   0.3 = 1 unverified import that affects the answer
#   0.1 = 2+ unverified imports
#   0.0 = Key result entirely depends on imported theorem


# ════════════════════════════════════════════════════════════════
# PART 4: ORCHESTRATOR ENFORCEMENT (hle_pilot.py)
# ════════════════════════════════════════════════════════════════
#
# Add to D2 Worker instruction:
#
#   "List ALL assumptions you are making. For each, mark:
#    PROVEN (derived here), IMPORTED (from another context), or ASSUMED.
#    For IMPORTED: state the origin and justify why it applies HERE.
#    If you cannot justify → mark as UNVERIFIED_IMPORT."
#
# Add to D5 Worker instruction (existing cross-verification block):
#
#   "5. **ASSUMPTION AUDIT**:
#    - List assumptions from D2 assumption register
#    - For each IMPORTED assumption: is it proven for THIS problem?
#    - If your cross-verification uses the same assumptions as primary method,
#      the methods are NOT independent — state this explicitly."
#
# Add to D5 TL reflection (existing scorecard block):
#
#   Add row H:
#   "| H. Assumption independence (unverified imports?) | ?/1.0 | |"
#
#   Add hard cap check:
#   "- UNVERIFIED_IMPORT in assumption register → max 60%
#    - Cross-verification methods share assumptions → max 55%"


# ════════════════════════════════════════════════════════════════
# PART 5: RETROACTIVE ANALYSIS
# ════════════════════════════════════════════════════════════════
#
# Q7 with Patch 10:
#   D2: "120° angles optimal" → IMPORTED from Steiner → transfer_justified: false
#       (no proof that Steiner angles optimize area-per-length)
#   D5: Cross-verification methods both use 120° → NOT independent → E=0.5 max
#   H: 1 UNVERIFIED_IMPORT affecting answer → H=0.3
#   Hard cap: unverified_import → max 60%
#   Hard cap: methods share assumptions → max 55%
#   → TL confidence: min(55%, computed) ≈ 45-50%
#   → Gap with Worker (90%): ~40pp → ITERATE
#   → TL asks: "Prove that 120° angles are optimal for area maximization,
#     not just for Steiner trees. Or try optimization without this constraint."
#   → Possible: Worker optimizes with free angles → finds isosceles → C
#
# B01 with Patch 10:
#   D4: "metrically convex ⟺ strictly convex" → IMPORTED (false iff)
#       Actually not even properly imported — it was GENERATED from 2 examples
#       But if it were treated as import: transfer_justified: false
#   H: 1 UNVERIFIED_IMPORT → H=0.3
#   Hard cap: 60% + iff_not_proven cap 35% → min = 35%
#   Already caught by existing caps, but H adds another layer
#
# Summary of new pattern caught:
# | Q   | Error type           | Caught by existing? | Caught by Patch 10? |
# |-----|---------------------|:-------------------:|:-------------------:|
# | Q1  | Proof gap           | Patch 8 (boundary)  | —                   |
# | Q3  | Wrong model         | Patch 7 (sanity)    | —                   |
# | Q6  | Wrong formula       | Patch 7 (small case)| —                   |
# | Q7  | False axiom transfer| ❌ NOT CAUGHT       | ✅ H + independence |
# | B01 | False iff           | Patch 8 (boundary)  | ✅ H (additional)   |
# | B02 | Over-restrictive    | Patch 7 (magnitude) | —                   |
