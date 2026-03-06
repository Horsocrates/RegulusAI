# Regulus AI

**Deterministic reasoning verification for LLMs + Coq-verified interval arithmetic for neural networks.**

Regulus is four interconnected systems:

1. **LogicGuard** -- a structured multi-agent system that decomposes LLM reasoning into verifiable steps, checks structural integrity through a formal gate mechanism, and forces correction when hallucination is detected. Core principle: make dishonesty **structurally impossible** through `Gtotal`.

2. **Verified Interval Propagation** -- a Coq-verified interval arithmetic library for neural network uncertainty quantification. Propagates `[lo, hi]` bounds through Conv2d, BatchNorm, ReLU, Softmax, and Dense layers with **machine-checked correctness proofs** and **zero axioms**.

3. **Fallacy Detection** -- a 156-fallacy taxonomy derived from the Theory of Systems, with regex-based signal extraction and LLM-powered classification via cascading gates (ERR/cascade/multigate modes).

4. **Verified Computation Backend** -- a Coq→OCaml→Python bridge that integrates 1045 machine-checked theorems into the reasoning pipeline. D1 outputs are validated against formal E/R/R well-formedness (Roles.v, 30 Qed). D4 computations are checked against verified theorems (IVT, EVT, CROWN, Series, Contraction) with **confidence = 100%** when a theorem applies. Information Layers enable principled multi-perspective analysis (P3 Intensional Identity). **Convergence analysis** models the pipeline as a Banach contraction on [0, 100] confidence space (ReasoningConvergence.v, 19 Qed) with stall detection, paradigm shift, and iteration bounds.

Built on the **Theory of Systems** (ToS) framework. Companion formal library: [theory-of-systems-coq](https://github.com/Horsocrates/theory-of-systems-coq) (1064 theorems, 8 Admitted, 0 custom axioms).

---

## Verified Interval Arithmetic

The `regulus/nn/`, `regulus/interval/`, and `ToS-Coq/` directories implement a complete pipeline for neural network uncertainty quantification with formal guarantees.

### The Idea

Given a trained neural network and an input `x`, we ask: *"If the input were perturbed by at most eps, how much could the output change?"* We propagate `[x - eps, x + eps]` intervals through every layer and get guaranteed output bounds. If those bounds span multiple classes, the prediction is **unreliable**.

### Coq Verification (0 Axioms)

Every interval operation is formally verified in Coq (Rocq 9.0.1). All theorems are axiom-free -- `Print Assumptions` returns "Closed under the global context" for every theorem.

```
ToS-Coq/                            # 320 Qed, 0 Admitted, 0 axioms
  PInterval.v                        -- Interval arithmetic (add, mul, relu, dot, abs, div, ...)
  PInterval_Linear.v                 -- Linear layer (scale, wdot, width bounds, relu bound)
  PInterval_Conv.v                   -- Conv2d, BatchNorm, Conv-BN-ReLU chain
  PInterval_Composition.v            -- Reanchor, MaxPool, ResBlock, chain width
  PInterval_Softmax.v                -- Sound softmax bounds (cross-multiplication, parametric)
  Extraction_PInterval.v             -- OCaml extraction
  IVT.v                              -- Intermediate Value Theorem
  Archimedean.v                      -- Archimedean property
  ShrinkingIntervals_uncountable.v   -- Non-surjectivity via diagonal trisection (167 lemmas)
```

**Key theorems:**

| File | Theorem | Statement |
|------|---------|-----------|
| Conv | `pi_conv_bn_relu_width_bound` | `width(ReLU(BN(Conv(x)))) <= \|s\| * eps * \|\|W\|\|_1` |
| Composition | `reanchored_final_width` | `final_width <= last_factor * 2*eps` (depth-independent) |
| Composition | `pi_max_pair_width` | `width(MaxPool(I,J)) <= max(width(I), width(J))` |
| Composition | `pi_resblock_width_bound` | `width(relu(x+f(x))) <= w(x) + w(f(x))` |
| Softmax | `interval_softmax_correct` | Sound bounds for all points in `[lo,hi]` |
| Softmax | `softmax_lower_bound` | `f(lo_i)*D_x <= f(x_i)*D_lo` (cross-mul, no division) |

### Python Implementation

```
regulus/nn/                          # Neural network verification
  interval_tensor.py                 -- IntervalTensor: [lo, hi] pairs with arithmetic
  layers.py                          -- IntervalLinear, Conv2d, BatchNorm, ReLU, MaxPool, Softmax
  model.py                           -- convert_model(): PyTorch model -> interval model
  reanchor.py                        -- Re-Anchoring (depth-independent width bounds)
  adversarial.py                     -- Adversarial input generation via diagonal trisection
  architectures.py                   -- MLP, CNN+BN, ResNet+BN, CIFAR variants

regulus/interval/                    # Pure interval arithmetic (mirrors Coq)
  interval.py                        -- Interval class (add, mul, relu, sigmoid, tanh, elu, gelu)
  composition.py                     -- Reanchor, MaxPool, ResBlock, chain width (PInterval_Composition.v)
  softmax.py                         -- Sound softmax bounds (PInterval_Softmax.v)
  evt.py                             -- Extreme Value Theorem with verified argmax (EVT_idx.v)
  trisection.py                      -- Diagonal trisection with certified gaps
  cauchy_real.py                     -- Cauchy reals + IEEE 754 rounding safety (CauchyReal.v, RoundingSafety.v)
```

### Benchmark Results

**MNIST** (Architecture Benchmark):

| Method | MLP AUROC | CNN+BN AUROC | ResNet+BN AUROC | Cost |
|--------|-----------|--------------|-----------------|------|
| **RA-Margin** | **0.835** | **0.957** | **0.983** | **1x** |
| TempScaling | 0.777 | 0.959 | 0.968 | 1x |
| MC Dropout (N=50) | 0.670 | 0.738 | 0.701 | 50x |
| Naive IBP | 0.586 | 0.548 | 0.500 | 1x |

**CIFAR-10**:

| Method | CNN+BN AUROC | ResNet+BN AUROC | Cost |
|--------|--------------|-----------------|------|
| **RA-Margin** | **0.829** | 0.686 | **1x** |
| TempScaling | 0.850 | 0.830 | 1x |
| MC Dropout (N=50) | 0.667 | 0.686 | 50x |

RA-Margin achieves competitive error detection at 1x cost (single forward pass) vs 50x for MC Dropout.

### Traceable Uncertainty

Beyond a single confidence score, Regulus shows **which block** caused unreliability:

```
Block 0 [stem ]: margin = 2.31  (safe)
Block 1 [res1 ]: margin = 1.85  (safe)
Block 2 [pool ]: margin = 0.92  (marginal)
Block 3 [res2 ]: margin = 0.12  << CRITICAL
Block 4 [fc   ]: margin = 0.45  (weak)
```

---

## Fallacy Detection (156 Fallacies)

The `regulus/fallacies/` module implements the full Theory of Systems fallacy taxonomy.

### Taxonomy Structure

| Type | Description | Count |
|------|-------------|-------|
| Type 1 | Pre-reasoning failures (reasoning never started) | 36 |
| Type 2 | Domain violations (D1-D6 structural errors) | 105 |
| Type 3 | Sequence violations (domain order broken) | 3 |
| Type 4 | Systemic patterns (multi-domain corruption) | 6 |
| Type 5 | Context-dependent failures | 6 |
| **Total** | | **156** |

### Detection Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| `regex` | 50+ signal patterns, no LLM needed | Fast screening |
| `err` | Full ERR+D1-D6 framework in single LLM call | Detailed analysis |
| `cascade` | Step 1: Type classification, Step 2: Domain+ID | Accuracy |
| `multigate` | G1-G5 binary elimination gates before classification | Preventing force-fitting |

### Benchmarks

**LOGIC dataset** (150 texts, 13 fallacy types): Binary recall 90%, Type-level F1 6.2%

**MAFALDA dataset** (200 texts, 23 types + clean): Binary detection + fine-grained classification with false positive analysis

---

## Verified Computation Backend

The `regulus/verified/` module bridges 1045 Coq-proven theorems into the Python pipeline. Three integration points:

### D1 Gate: E/R/R Structural Validator

After D1 produces E/R/R output, `ERRValidator` checks 4 formal well-formedness conditions (from `Roles.v`, 30 Qed):

| Condition | Description | Violation = |
|-----------|-------------|-------------|
| C1 | Category exclusivity | Duplicate components |
| C2 | No cross-category self-reference | Element = Rule identity |
| C3 | No cross-level role occupation | Level mismatch |
| C4 | Acyclic dependencies | Circular status (paradox) |

```python
from regulus.verified import ERRValidator

validator = ERRValidator()
gate = validator.gate_d1_to_d2(d1_output)
# gate["action"] = "proceed_to_d2" or "retry_d1" with guidance
```

### D4 Hook: Machine-Checked Computation

When D4 performs computation, `MathVerifier` checks if a verified theorem applies:

| Theorem | Trigger Keywords | Coq Source | Qed |
|---------|-----------------|------------|-----|
| IVT | "intermediate value", "root finding" | IVT_ERR.v | 23 |
| EVT | "extreme value", "maximum" | EVT_idx.v | 26 |
| CROWN | "crown", "interval bound" | PInterval_CROWN.v | 25 |
| Series Convergence | "convergence", "ratio test" | SeriesConvergence.v | 22 |
| Fixed Point | "contraction", "banach" | FixedPoint.v | 20 |
| L5 Resolution | (always available for tie-breaking) | L5Resolution.v | 18 |

When a theorem applies → `confidence_override = 100%` (machine-checked certainty).

```python
from regulus.verified import MathVerifier

verifier = MathVerifier()
result = verifier.try_verify("Extreme Value Theorem", {"values": [1, 5, 5, 3]})
# result.value = {"max_value": 5.0, "max_index": 1, "l5_resolved": True}
# result.theorem_used = "EVT_idx.argmax_idx_maximizes"
```

### Information Layers: Multi-Perspective Analysis

Same question analyzed through multiple criteria (P3 Intensional Identity: same substrate + different criterion = different system):

```python
from regulus.verified import LayeredAnalysis
from regulus.verified.layers import MATH_LAYER, EMPIRICAL_LAYER

analysis = LayeredAnalysis(substrate=d1_d2_output)
analysis.add_layer(MATH_LAYER)
analysis.add_layer(EMPIRICAL_LAYER)

# D6 cross-layer comparison
comparison = analysis.compare_across_layers()
# Agreement → high structural confidence
# Divergence → examine which criterion is most appropriate
```

Every result carries `theorem_used` — full traceability from Python output to the Coq theorem that guarantees correctness. See [UNIFIED_ARCHITECTURE.md](UNIFIED_ARCHITECTURE.md) for the full stack diagram.

### Convergence Analysis (Banach Fixed-Point)

Models the pipeline iteration as a contraction mapping on [0, 100] confidence space. Backed by `ReasoningConvergence.v` (19 Qed, 0 Admitted) in the companion library.

```python
from regulus.verified import ConvergenceAdvisor

advisor = ConvergenceAdvisor()
advisor.record(50.0)   # iteration 1
advisor.record(75.0)   # iteration 2
advisor.record(87.5)   # iteration 3
print(advisor.advise())
# [ACTION] CONTINUE
# [REASON] Contractive (c=0.500). Estimated 3 more iteration(s) to converge.
# [ESTIMATE] c = 0.500, iterations remaining = 3, predicted final confidence = 96.9%
# [THEOREM] FixedPoint.v: Banach_contraction_principle
```

Key capabilities:
- **Contraction estimation** — median gap ratio from confidence history
- **Iteration bounds** — `n >= log(eps*(1-c)/d0) / log(c)` (Banach bound)
- **Stall detection** — if |T(s) - s| is small, s is near the fixed point (stall_means_near_fixpoint)
- **Paradigm shift** — non-contractive sequences or 3+ stalls trigger strategy change (paradigm_shift_resets)

### Phase 5 Evaluation: Verified Backend on HLE Math

Post-hoc evaluation of the verified backend on 10 HLE Mathematics questions (GLM-5):

| Metric | Baseline | Verified | Delta |
|--------|:--------:|:--------:|:-----:|
| Accuracy | 0/10 | 0/10 | 0 |
| Calibration Error | 68.4pp | 68.4pp | 0 |
| D4 Math Verifier triggers | -- | 0/10 | -- |
| D1 ERR Validator parsed | -- | 4/10 valid | -- |

**Key finding:** HLE-level math (algebraic geometry, topology, stochastic processes) is too abstract for direct theorem matching (IVT, EVT, convergence). The theorem library targets calculus-level problems. Post-hoc verification cannot change answers -- inline integration is needed. See [eval/results/PHASE5_REPORT.md](eval/results/PHASE5_REPORT.md).

---

## LogicGuard: Reasoning Verification

### Architecture

```
Input Question
     |
  D1: Recognition --- "What is actually here?"
     |
  D2: Clarification - "What exactly is this?"
     |
  D3: Framework ----- "How do we model this?"
     |
  D4: Computation --- "What does the math say?"
     |
  D5: Inference ----- "What follows from this?"
     |
  D6: Reflection ---- "Where does this break?"
     |
 Verified Answer (with confidence trace)
```

Two-agent dialogue:

| Agent | Role | Level |
|-------|------|-------|
| **Team Lead** | Plans, evaluates, assembles. Never solves directly. | L3 (meta-operator) |
| **Worker** | Executes domain tasks, computes, verifies. | L2 (operator) |

### Zero-Gate Mechanism

Every reasoning step passes through a three-component binary gate:

| Gate | Checks | Failure means |
|------|--------|---------------|
| `gERR` | Elements, Roles, Rules all present | Missing structural component |
| `gLevels` | L1-L3 hierarchy valid | Self-reference loop |
| `gOrder` | Domain sequence D1-D6 respected | Domain skipped |

```
Gtotal = gERR AND gLevels AND gOrder

If Gtotal = 0:
  Weight = 0          # Annihilation, not penalty
  Status = Invalid    # Cannot become PrimaryMax
```

### Status Machine (Coq-proven)

14 theorems, 0 admitted (`ToS-StatusMachine/ToS_Status_Machine_v8.v`):

| Status | Meaning |
|--------|---------|
| **PrimaryMax** | Unique winner (gate=1, highest weight) |
| SecondaryMax | Valid alternative, equal weight |
| HistoricalMax | Was Primary, now superseded |
| Candidate | Valid but lower weight |
| Invalid | Gate=0, weight forced to 0 |

Invariants:
1. **Zero-Gate Law:** `G = 0 => W = 0`
2. **Uniqueness:** At most one PrimaryMax
3. **Stability:** Invalid cannot become PrimaryMax

---

## Repository Structure

```
RegulusAI/
|-- regulus/                    # Core package
|   |-- core/                  # LogicGuard verification engine
|   |-- verified/              # Verified computation backend (Coq->OCaml->Python bridge)
|   |   |-- bridge.py          #   VerifiedBackend: IVT, EVT, CROWN, L5, ERR checks
|   |   |-- math_verifier.py   #   D4 theorem detection + confidence_override=100%
|   |   |-- err_validator.py   #   D1 E/R/R gate (4 well-formedness conditions)
|   |   |-- layers.py          #   Information Layers (P3 multi-perspective analysis)
|   |   |-- convergence.py     #   Banach contraction convergence analyzer
|   |   |-- convergence_advisor.py # Human-readable convergence advice
|   |   +-- pipeline_adapter.py #  Extract D1/D3/D4 from HLE pipeline results
|   |-- llm/                   # LLM clients (Claude, OpenAI, DeepSeek, ZhipuAI)
|   |-- nn/                    # Interval neural network layers + adversarial generation
|   |-- interval/              # Pure interval arithmetic (Coq mirror)
|   |-- fallacies/             # 156-fallacy taxonomy + detector + LLM extractor
|   |-- demo/                  # Demo scripts (Logic Censor showcase, MNIST, depth study)
|   |-- analysis/              # Reliability analysis + traceable uncertainty
|   |-- benchmark/             # Datasets, metrics, methods
|   |-- experiments/           # Benchmark scripts (architecture, CIFAR-10)
|   |-- orchestrator.py        # Main verification loop
|   +-- cli.py                 # Typer CLI
|
|-- ToS-Coq/                   # Coq formalization (320 Qed, 0 Admitted, 0 axioms)
|   |-- PInterval.v            # Base interval arithmetic
|   |-- PInterval_Linear.v     # Linear layer verification
|   |-- PInterval_Conv.v       # Conv2d + BatchNorm verification
|   |-- PInterval_Composition.v # Reanchor, MaxPool, ResBlock, chain
|   |-- PInterval_Softmax.v    # Softmax bounds
|   |-- Extraction_PInterval.v # OCaml extraction
|   |-- IVT.v                  # Intermediate Value Theorem
|   |-- Archimedean.v          # Archimedean property
|   +-- ShrinkingIntervals_uncountable.v  # Non-surjectivity (167 lemmas)
|
|-- ToS-StatusMachine/          # Status machine proofs (14 Qed, 0 axioms)
|-- benchmarks/                # LOGIC, MAFALDA, FML benchmarks + integration suite
|-- eval/                      # Evaluation harnesses + results
|-- tests/                     # 925+ tests (non-torch)
|-- skills/                    # Domain instruction files (v3)
|-- UNIFIED_ARCHITECTURE.md    # Full stack: Coq→OCaml→Python→Pipeline
+-- scripts/                   # Experiment scripts (IBP training, CIFAR-10)
```

## Quick Start

```bash
# Clone
git clone https://github.com/Horsocrates/RegulusAI.git
cd RegulusAI

# Install
uv sync

# Run offline demo (no API keys needed)
uv run regulus demo --quick       # 5 scenarios: syllogism, ad hominem, liar paradox, domain skip, slippery slope
uv run regulus demo --list        # List available scenarios
uv run regulus demo --pick 1 3    # Run specific scenarios

# Run tests (880+ non-torch tests)
uv run pytest tests/ -v

# Fallacy detection
uv run regulus fallacy-detect "If evolution were true, we'd see dogs turning into cats"

# Compile Coq proofs (requires Rocq 9.0)
cd ToS-Coq
coqc -Q . ToS PInterval.v
coqc -Q . ToS PInterval_Linear.v
coqc -Q . ToS PInterval_Conv.v
coqc -Q . ToS PInterval_Composition.v
coqc -Q . ToS PInterval_Softmax.v
```

## Formal Guarantees Summary

### Local Coq Proofs (ToS-Coq/ + ToS-StatusMachine/)

| File | Qed | Axioms | Domain |
|------|-----|--------|--------|
| `PInterval.v` | 43 | 0 | Interval arithmetic (add, mul, relu, dot, ...) |
| `PInterval_Linear.v` | 18 | 0 | Linear layers, width bounds, L1-norm bound |
| `PInterval_Conv.v` | 16 | 0 | Conv2d, BatchNorm, Conv-BN-ReLU chain |
| `PInterval_Composition.v` | 26 | 0 | Reanchor, MaxPool, ResBlock, chain width |
| `PInterval_Softmax.v` | 13 | 0 | Softmax bounds (cross-multiplication) |
| `IVT.v` | 23 | 0 | Intermediate Value Theorem |
| `Archimedean.v` | 14 | 0 | Archimedean property |
| `ShrinkingIntervals_uncountable.v` | 167 | 0 | Non-surjectivity via trisection |
| `ToS_Status_Machine_v8.v` | 14 | 0 | Status machine, zero-gate law, uniqueness |
| **Local Total** | **334** | **0** | |

### Companion Library ([theory-of-systems-coq](https://github.com/Horsocrates/theory-of-systems-coq))

| Category | Qed | Admitted | Axioms |
|----------|-----|----------|--------|
| Core Mathematics (40 files) | 947 | 8 | `classic` (LEM) only |
| Architecture of Reasoning (6 files) | 117 | 0 | None |
| **Companion Total** | **1064** | **8** | |

**Grand Total: 1398 proven theorems across both repositories.**

## Technology

- **Python 3.11+** with full type hints
- **PyTorch 2.6+** for neural network training
- **Rocq 9.0.1** (Coq) for formal proofs — fully constructive, extraction-compatible
- **Anthropic Claude** (primary), OpenAI, DeepSeek, ZhipuAI (LLM backends)
- **Rich** + **Typer** for CLI
- **pytest** — 925+ tests (non-torch)

## License

MIT

## Citation

```bibtex
@software{regulus2026,
  title={Regulus AI: Verified Interval Propagation for Neural Network Uncertainty},
  author={Horsocrates},
  year={2026},
  url={https://github.com/Horsocrates/RegulusAI}
}
```
