# Regulus AI

**Deterministic reasoning verification for LLMs + Coq-verified interval arithmetic for neural networks.**

Regulus is two interconnected systems:

1. **LogicGuard** -- a structured multi-agent system that decomposes LLM reasoning into verifiable steps, checks structural integrity through a formal gate mechanism, and forces correction when hallucination is detected. Core principle: make dishonesty **structurally impossible** through `Gtotal`.

2. **Verified Interval Propagation** -- a Coq-verified interval arithmetic library for neural network uncertainty quantification. Propagates `[lo, hi]` bounds through Conv2d, BatchNorm, ReLU, and Dense layers with **machine-checked correctness proofs** and **zero axioms**.

Built on the **Theory of Systems** (ToS) framework.

---

## Verified Interval Arithmetic (Steps 7-11)

The `regulus/nn/` and `ToS-Coq/` directories implement a complete pipeline for neural network uncertainty quantification with formal guarantees.

### The Idea

Given a trained neural network and an input `x`, we ask: *"If the input were perturbed by at most eps, how much could the output change?"* We propagate `[x - eps, x + eps]` intervals through every layer and get guaranteed output bounds. If those bounds span multiple classes, the prediction is **unreliable**.

### Coq Verification (0 Axioms)

Every interval operation is formally verified in Coq (Rocq 9.0.1). All theorems are axiom-free -- `Print Assumptions` returns "Closed under the global context" for every theorem.

```
ToS-Coq/
  PInterval.v          -- 11 base theorems (add, mul, relu, dot, abs, div, ...)
  PInterval_Linear.v   -- 8 theorems (pi_scale, pi_wdot, width bounds, relu bound)
  PInterval_Conv.v     -- 13 theorems (Conv2d, BatchNorm, Conv-BN-ReLU chain)
```

**Key theorems (PInterval_Conv.v):**

| Theorem | Statement |
|---------|-----------|
| `pi_affine_correct` | `x in I => scale*x+shift in BN(I)` |
| `pi_affine_width` | `width(BN(x)) = |scale| * width(x)` |
| `pi_conv_pixel_correct` | `dot(W, patch) + bias in Conv(patch)` |
| `pi_conv_pixel_width_uniform_bound` | `width(Conv(x)) <= eps * \|\|W\|\|_1` |
| **`pi_conv_bn_relu_width_bound`** | **`width(ReLU(BN(Conv(x)))) <= \|s\| * eps * \|\|W\|\|_1`** |

The punchline theorem chains Conv2d, BatchNorm, and ReLU into a single verified width bound -- the first (to our knowledge) Coq-verified interval arithmetic for convolutional neural networks.

### Python Implementation

```
regulus/nn/
  interval_tensor.py   -- IntervalTensor: [lo, hi] pairs with arithmetic
  layers.py            -- IntervalLinear, IntervalConv2d, IntervalBatchNorm,
                          IntervalReLU, IntervalMaxPool2d, IntervalSoftmax
  model.py             -- convert_model(): PyTorch model -> interval model
  reanchor.py          -- Re-Anchoring strategies (midpoint, adaptive, hybrid)
  architectures.py     -- MLP, CNN+BN, ResNet+BN, CIFAR variants
```

### Benchmark Results

**MNIST** (Step 9: Architecture Benchmark):

| Method | MLP AUROC | CNN+BN AUROC | ResNet+BN AUROC | Cost |
|--------|-----------|--------------|-----------------|------|
| **RA-Margin** | **0.835** | **0.957** | **0.983** | **1x** |
| TempScaling | 0.777 | 0.959 | 0.968 | 1x |
| MC Dropout (N=50) | 0.670 | 0.738 | 0.701 | 50x |
| Naive IBP | 0.586 | 0.548 | 0.500 | 1x |

**CIFAR-10** (Step 10):

| Method | CNN+BN AUROC | ResNet+BN AUROC | Cost |
|--------|--------------|-----------------|------|
| **RA-Margin** | **0.829** | 0.686 | **1x** |
| TempScaling | 0.850 | 0.830 | 1x |
| MC Dropout (N=50) | 0.667 | 0.686 | 50x |

RA-Margin achieves competitive error detection at 1x cost (single forward pass) vs 50x for MC Dropout.

### Traceable Uncertainty (Step 10)

Beyond a single confidence score, Regulus shows **which block** caused unreliability:

```
Block 0 [stem ]: margin = 2.31  (safe)
Block 1 [res1 ]: margin = 1.85  (safe)
Block 2 [pool ]: margin = 0.92  (marginal)
Block 3 [res2 ]: margin = 0.12  << CRITICAL
Block 4 [fc   ]: margin = 0.45  (weak)
```

The critical block (argmin of margins) pinpoints where the network's internal representation becomes ambiguous under perturbation.

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
|   |-- llm/                   # LLM clients (Claude, OpenAI, DeepSeek)
|   |-- nn/                    # Interval neural network layers
|   |-- analysis/              # Reliability analysis + traceable uncertainty
|   |-- benchmark/             # Datasets, metrics, methods
|   |-- experiments/           # Benchmark scripts (architecture, CIFAR-10)
|   |-- paper/                 # Figure generation for publication
|   |-- interval/              # Pure interval arithmetic (Python mirror of Coq)
|   |-- orchestrator.py        # Main verification loop
|   +-- cli.py                 # Typer CLI
|
|-- ToS-Coq/                   # Coq formalization (32 theorems, 0 axioms)
|   |-- PInterval.v            # Base interval arithmetic (11 theorems)
|   |-- PInterval_Linear.v     # Linear layer verification (8 theorems)
|   |-- PInterval_Conv.v       # Conv2d + BatchNorm verification (13 theorems)
|   |-- Extraction_PInterval.v # OCaml extraction
|   |-- Archimedean.v          # Archimedean property
|   |-- IVT.v                  # Intermediate Value Theorem
|   +-- ShrinkingIntervals_uncountable.v
|
|-- ToS-StatusMachine/          # Status machine proofs (14 theorems)
|-- tests/                     # 131 tests
|-- skills/                    # Domain instruction files (v3)
|-- benchmark_results/         # Saved benchmark outputs
+-- paper/                     # Publication figures (PDF)
```

## Quick Start

```bash
# Clone
git clone https://github.com/anthropics/RegulusAI.git
cd RegulusAI

# Install
uv sync

# Run tests (131 tests)
.venv313\Scripts\python.exe -m pytest tests/ regulus/nn/test_*.py -v

# Run interval benchmark (quick mode)
.venv313\Scripts\python.exe -u -m regulus.experiments.architecture_benchmark --quick

# Compile Coq proofs (requires Rocq 9.0)
cd ToS-Coq
coqc -Q . ToS PInterval.v
coqc -Q . ToS PInterval_Linear.v
coqc -Q . ToS PInterval_Conv.v
```

## Formal Guarantees Summary

| File | Theorems | Axioms | Domain |
|------|----------|--------|--------|
| `PInterval.v` | 11 | 0 | Interval arithmetic (add, mul, relu, dot, ...) |
| `PInterval_Linear.v` | 8 | 0 | Linear layers, width bounds, L1-norm bound |
| `PInterval_Conv.v` | 13 | 0 | Conv2d, BatchNorm, Conv-BN-ReLU chain |
| `ToS_Status_Machine_v8.v` | 14 | 0 | Status machine, zero-gate law, uniqueness |
| **Total** | **46** | **0** | |

## Technology

- **Python 3.11+** with full type hints
- **PyTorch 2.6+** for neural network training
- **Rocq 9.0.1** (Coq) for formal proofs -- fully constructive, extraction-compatible
- **Anthropic Claude** (primary), OpenAI, DeepSeek (LLM backends)
- **Rich** + **Typer** for CLI
- **pytest** -- 131 tests

## License

MIT

## Citation

```bibtex
@software{regulus2026,
  title={Regulus AI: Verified Interval Propagation for Neural Network Uncertainty},
  author={Horsocrates},
  year={2026},
  url={https://github.com/anthropics/RegulusAI}
}
```
