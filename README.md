# Regulus AI

**Deterministic reasoning verification for LLMs + Coq-verified interval arithmetic for neural networks.**

Regulus is three interconnected systems:

1. **LogicGuard** -- a structured multi-agent system that decomposes LLM reasoning into verifiable steps, checks structural integrity through a formal gate mechanism, and forces correction when hallucination is detected. Core principle: make dishonesty **structurally impossible** through `Gtotal`.

2. **Verified Interval Propagation** -- a Coq-verified interval arithmetic library for neural network uncertainty quantification. Propagates `[lo, hi]` bounds through Conv2d, BatchNorm, ReLU, Softmax, and Dense layers with **machine-checked correctness proofs** and **zero axioms**.

3. **Fallacy Detection** -- a 156-fallacy taxonomy derived from the Theory of Systems, with regex-based signal extraction and LLM-powered classification via cascading gates (ERR/cascade/multigate modes).

4. **Verified Numerics** -- Cauchy real arithmetic and IEEE 754 rounding safety analysis, proving that interval bounds remain sound after floating-point rounding.

Built on the **Theory of Systems** (ToS) framework. Companion formal library: [theory-of-systems-coq](https://github.com/Horsocrates/theory-of-systems-coq) (658 theorems, 13 Admitted).

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
|   |-- llm/                   # LLM clients (Claude, OpenAI, DeepSeek, ZhipuAI)
|   |-- nn/                    # Interval neural network layers + adversarial generation
|   |-- interval/              # Pure interval arithmetic (Coq mirror)
|   |-- fallacies/             # 156-fallacy taxonomy + detector + LLM extractor
|   |-- demo/                  # Demo scripts (MNIST, depth study, reliability)
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
|-- tests/                     # 829+ tests (non-torch)
|-- skills/                    # Domain instruction files (v3)
+-- scripts/                   # Experiment scripts (IBP training, CIFAR-10)
```

## Quick Start

```bash
# Clone
git clone https://github.com/Horsocrates/RegulusAI.git
cd RegulusAI

# Install
uv sync

# Run tests (829+ non-torch tests)
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
| Core Mathematics | 541 | 13 | `classic` (LEM) only |
| Architecture of Reasoning | 117 | 0 | None |
| **Companion Total** | **658** | **13** | |

**Grand Total: 992 proven theorems across both repositories.**

## Technology

- **Python 3.11+** with full type hints
- **PyTorch 2.6+** for neural network training
- **Rocq 9.0.1** (Coq) for formal proofs — fully constructive, extraction-compatible
- **Anthropic Claude** (primary), OpenAI, DeepSeek, ZhipuAI (LLM backends)
- **Rich** + **Typer** for CLI
- **pytest** — 829+ tests (non-torch)

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
