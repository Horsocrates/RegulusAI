# Domain Instruction Files

This directory contains the instruction sets (system prompts) for each agent in the Regulus reasoning pipeline. These files define **what each domain does**, **what principles govern it**, and **what failure modes to watch for**.

## Architecture Overview

Regulus uses a two-agent dialogue:

```
Team Lead (analyze-v2.md)
    |
    |--- sends instruction ---> Worker
    |<-- receives output ------/
    |
    |--- evaluates via D6-REFLECT
    |--- decides: PASS | ITERATE | PARADIGM_SHIFT
    |
    +--- next domain or re-run
```

The **Team Lead** (L3 meta-operator) guides the **Worker** (L2 operator) through five domains sequentially. The Team Lead never solves the problem directly — it plans, evaluates, and assembles. D6 is not a separate domain but the Team Lead's own cognitive toolkit (D6-ASK + D6-REFLECT).

## File Index

| File | Agent | Role |
|------|-------|------|
| `analyze-v2.md` | Team Lead | L3 meta-operator: plan, verify, assemble |
| `d1-recognize.md` | Worker | D1: Recognition |
| `d2-clarify.md` | Worker | D2: Clarification |
| `d3-framework.md` | Worker | D3: Framework Selection |
| `d4-compare.md` | Worker | D4: Computation & Comparison |
| `d5-infer.md` | Worker | D5: Inference & Cross-verification |
| `d6-ask.md` | Team Lead | D6-ASK: Questioning Intelligence |
| `d6-reflect.md` | Team Lead | D6-REFLECT: Reflective Intelligence |
| `PIPELINE_v5_SPEC.md` | Reference | Pipeline v5 architecture spec |
| `TL_CONFIDENCE_SCORECARD.md` | Reference | Two-level confidence system |

---

## Domain Details

### D1: Recognition

**File:** `d1-recognize.md`

**Function:** Identify what is PRESENT in the query. Decompose into E/R/R structure.

**Principle:** Principle of Presence (L1 Identity) — register only what IS given.

**Core method — E/R/R Decomposition:**

| Component | Question | Grounding |
|-----------|----------|-----------|
| **Elements** | What things/objects/values are mentioned? | L1 (Identity): each element is itself |
| **Roles** | What function does each element serve? | L4 (Sufficient Reason): nothing is present without purpose |
| **Rules** | What equations/laws/constraints connect them? | L5 (Order): structure has hierarchy |
| **Status** | What state does each element have? | Derived from Rules + Elements |
| **Dependencies** | What must be determined before what? | Must be ACYCLIC |

**Key features:**
- E/R/R hierarchy check: Rules determine Roles, Roles distinguish Elements, Elements ground the system
- Process ordering rule (L5): when a question describes a sequence, the ordering is a structural fact
- Direction flags: forward vs reverse provenance detection
- Key challenge identification for downstream domains

**Gate trigger on skip:** Object hallucination — the system reasons about elements that were never present.

---

### D2: Clarification

**File:** `d2-clarify.md`

**Function:** Transform D1's components from NOTICED to DEFINED. Fill in meaning with sufficient depth.

**Principle:** Principle of Questioning (L4 Sufficient Reason) — clarification has no natural stopping point; stop is determined by sufficiency for reasoning.

**Depth levels:**

| Level | Name | Indicator |
|-------|------|-----------|
| 1 | Nominal | Can point to examples |
| 2 | Dictionary | Can define, distinguish X from Y |
| 3 | Functional | Understand mechanism, can predict |
| 4 | Essential | Grasp the nature at the level of principle |

HLE-level questions typically require Level 3-4.

**Key features:**
- Seven clarification tools (genus+differentia, examples/counterexamples, extreme cases, usage analysis, operational definition, analysis of opposite, comparison with similar)
- ERR consumption and extension — D2 extends D1's structure without replacing it
- Assumption Register: every assumption tagged as PROVEN / IMPORTED / ASSUMED
- Hypothesis completeness check (CHECK 4): verify hypothesis set covers all structurally distinct possibilities

**Failure modes:**
- Equivocation — term changes meaning during reasoning
- Premature closure — choosing simpler reading without testing alternatives
- Definitional circularity — X defined through X
- Depth mismatch — Level 1-2 when task requires 3-4

**Gate trigger on skip:** Equivocation — the system uses a term with two different meanings without noticing.

---

### D3: Framework Selection

**File:** `d3-framework.md`

**Function:** Choose the evaluation framework BEFORE evaluating. Determine the coordinate system for comparison.

**Principle:** Principle of Hierarchy (L5 Order) — framework must be selected before computation. If you already "know" the answer before selecting a framework, that's confirmation bias.

**Multi-step algorithm (Pipeline v5):**

```
D3.1 — ENUMERATE (Worker)
  List ALL plausible frameworks. Do not select yet.
  For each: why it might apply, why it might not, key assumptions.
      |
D3.2 — ANALYZE & DISTRIBUTE (Worker)
  Score fit (0-100), classify assumptions, assign probability weights.
  Weights must sum to 100%. No single framework > 70%.
      |
D3.3 — THEORY DERIVATION (Worker)
  For the top framework(s), derive the theoretical prediction.
      |
D3.4 — SELECT (Team Lead)
  Review distribution, select which frameworks to compute in D4.
  | Weight   | Action                    |
  |----------|---------------------------|
  | >= 70%   | Compute top-1 only        |
  | 50-69%   | Compute top-2             |
  | < 50%    | Compute top-3             |
  | All <30% | RED FLAG: return to D2     |
```

**Critical safeguards:**
- L2 Objectivity Test: "Am I ready to accept ANY answer this framework produces?"
- Dual criterion: framework must match both the phenomenon's nature AND the inquiry's purpose
- Four levels of selection complexity (obvious, competing, creating new, meta-frame)

**Gate trigger on skip:** Category error — applying the wrong type of analysis entirely.

---

### D4: Computation & Comparison

**File:** `d4-compare.md`

**Function:** Systematically apply D3's framework to D1/D2's components. This is where the actual analytical work happens.

**Principle:** Principle of Systematicity — apply the framework to ALL elements without exception.

**Aristotle's Three Rules (mandatory for every comparison):**

| Rule | Question | Violation |
|------|----------|-----------|
| Same relation | Comparing in the same respect? | Price of A vs quality of B |
| Same criterion | One standard applied to all? | Stricter standard for one option |
| Same time/state | Comparable conditions? | Peak of A vs average of B |

**Key features:**
- L4 Sufficient Reason for empirical claims: every claim must state source, impact if wrong, and confidence
- Empirically dependent status: caps D5 confidence at 60% (binary) or 75% (multi-choice) when claims are unverified
- Python execution: Worker has access to sandboxed Python for numerical verification
- Multi-framework computation: when D3 selected multiple frameworks, D4 computes all of them

**Gate trigger on skip:** Internal contradiction — the computation contradicts its own premises.

---

### D5: Inference & Cross-verification

**File:** `d5-infer.md`

**Function:** Draw conclusions EARNED by D4's evidence. Nothing more, nothing less.

**Principle:** Sufficient Reason (L4) — every conclusion must have sufficient grounds. Direction (L5) — reasoning flows premises to conclusion, never the reverse.

**The L5 Direction Check:** "Did I arrive at this answer FROM the evidence, or did I select evidence FOR this answer?"

**Key features:**
- Structural constraints: D4 findings grounded in L1/L5 cannot be overridden by interpretive arguments
- Assumption audit: final check of all assumptions in the chain (PROVEN/IMPORTED/ASSUMED)
- Cross-verification: compare result against independent method
- Sufficient Reason Protocol: for each claim in the answer chain, state its basis
- Confidence calibration: explicit certainty type (NECESSARY / CONDITIONAL / EMPIRICAL / HEURISTIC)

**Gate trigger on skip:** Non-sequitur — the conclusion does not follow from the premises.

---

### D6-ASK: Questioning Intelligence

**File:** `d6-ask.md`

**Function:** Generate questions for the reasoning pipeline. D1-D5 answer questions; D6-ASK creates them.

**Two activation contexts:**

| Context | Input | Output |
|---------|-------|--------|
| INITIAL | Raw question | Structured question set with domain routing |
| ITERATE | Diagnostic from D6-REFLECT | Refined questions targeting specific gaps |

**Question structure (Gefragte / Befragte / Erfragte):**
- **Gefragte** (about what): the object of the question
- **Befragte** (addressed to): the domain of knowledge required
- **Erfragte** (what is sought): the specific form of the answer

**Key features:**
- Honesty analysis: is the question open? loaded? biased?
- Sub-question decomposition with composition test: do sub-answers compose back to root answer?
- Trap anticipation: likely error sources, ambiguities, confusions
- Pipeline depth calibration: how much process does this question need?

---

### D6-REFLECT: Reflective Intelligence

**File:** `d6-reflect.md`

**Function:** Evaluate every domain's output, validate reasoning quality, produce diagnostics when answers are insufficient.

**Two depths:**

| Depth | When Used | Checks |
|-------|-----------|--------|
| **QUICK** | Between domains, no red flags | Alignment, Coverage, Consistency, Confidence signal |
| **FULL** | Confidence < threshold, anomaly detected, after D5 | All instruments: 10 traps, 3 classes, 8 components |

**The 10 Reasoning Traps (FULL depth):**

1. Confirmation bias — seeking evidence that confirms, ignoring disconfirmation
2. Anchoring — first number/estimate dominates all subsequent reasoning
3. Availability — overweighting vivid or recent examples
4. Representativeness — pattern-matching overrides base rates
5. Dunning-Kruger — low competence, high confidence
6. Sunk cost — continuing because of effort invested, not because of prospects
7. Framing — answer changes with problem presentation
8. Authority bias — accepting claims because of source, not evidence
9. Bandwagon — "everyone does it this way"
10. Hindsight — "I knew it all along" after seeing the answer

**Convergence control:**
- Monotonic improvement required: each iteration must improve confidence
- Stagnation detection: if delta < threshold, escalate strategy
- Three-stage escalation: normal iteration -> targeted feedback -> paradigm shift
- Hard stop: after paradigm shift exhausted, accept with LOW_CONFIDENCE flag

---

## Team Lead (analyze-v2.md)

**Function:** L3 meta-operator that orchestrates the entire pipeline.

**Anti-Pre-Solving Rule:** The Team Lead MUST NOT compute, derive, or state candidate answers in reflect messages for D1-D3. If TL writes a candidate answer early, it enters the conspectus, and the Worker confirmation-biases all verification toward that answer.

**The Conspectus:** The Team Lead maintains a running record of all findings across domains — the single source of truth that accumulates and evolves as domains execute.

**Confidence system (two levels):**

| Level | Source | Measures |
|-------|--------|----------|
| C_computation | Worker's D4/D5 output | Numerical correctness, verification |
| C_approach | TL's structural assessment | Framework choice, assumption quality, completeness |

When the gap between C_computation and C_approach exceeds 35 percentage points, the system returns to an earlier domain for re-examination.

---

## Pipeline Support Files

### PIPELINE_v5_SPEC.md

Architecture specification for Pipeline v5 (framework-first). Defines:
- D3 multi-step algorithm (enumerate -> analyze -> derive -> select)
- D4 multi-framework computation rules
- Two-level confidence reconciliation
- Gap-triggered return logic

### TL_CONFIDENCE_SCORECARD.md

Defines the Team Lead's 8-checkpoint evaluation system:

| Checkpoint | What it evaluates |
|------------|-------------------|
| A (Alignment) | Does answer match the erfragte? |
| B (Definition depth) | Are key terms at sufficient depth? |
| C (Reasoning direction) | Premises -> conclusion (not reversed)? |
| D (Alternative consideration) | Were competing hypotheses tested? |
| E (Evidence completeness) | Is evidence sufficient for the claim? |
| F (Consistency) | No internal contradictions? |
| G (Scope match) | Answer matches question scope? |
| H (Assumption independence) | Are assumptions independent and tagged? |

### PATCH_10_ASSUMPTION_INDEPENDENCE.md

Documents the assumption independence audit — ensuring that assumptions A1, A2, ... in the reasoning chain are truly independent and not secretly derived from each other.

---

## Theoretical Foundation

All domain instructions are grounded in the **Theory of Systems** (ToS) logical framework:

| Law | Name | Domain Connection |
|-----|------|-------------------|
| **L1** | Identity | D1 (things are what they are), D2 (terms preserve meaning) |
| **L2** | Non-contradiction | D4 (no internal contradictions in comparison) |
| **L3** | Excluded middle | D3 (either framework A is correct or it isn't) |
| **L4** | Sufficient reason | D2 (depth calibration), D5 (conclusion needs grounds) |
| **L5** | Order | D1 (process ordering), D3 (framework before conclusion) |

The formal properties of the status machine (uniqueness, stability, zero-gate annihilation) are proven in Coq in `ToS-StatusMachine/ToS_Status_Machine_v8.v`.
