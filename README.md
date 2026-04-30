# Regulus AI

**Deterministic reasoning verification for LLMs + Process Mathematics formal library in Rocq/Coq.**

Regulus is a multi-component system built on the **Theory of Systems** (ToS) framework:

1. **LogicGuard** -- a structured multi-agent system that decomposes LLM reasoning into verifiable steps, checks structural integrity through a formal gate mechanism (Zero-Gate), and forces correction when hallucination is detected. Core principle: make dishonesty **structurally impossible** through `Gtotal`.

2. **Process Mathematics** -- a complete mathematical foundation replacing real numbers with `RealProcess := nat -> Q` (rational sequences). All classical analysis theorems are reproven constructively. Formalized in Rocq 9.0.1 with **21,901 proven theorems, 0 Admitted, 0 custom axioms**.

3. **Verified Interval Propagation** -- Rocq-verified interval arithmetic for neural network uncertainty quantification. Propagates `[lo, hi]` bounds through Conv2d, BatchNorm, ReLU, Softmax, and Dense layers with machine-checked correctness proofs.

4. **Data Compression** -- a ToS-derived compression pipeline where `compress() = simulate_physics()`. Graph Fourier Transform on process signals, Born-optimal compression (P(k) = |A_k|^2 = Parseval), gamma-unification of decoherence/damping/compression loss.

5. **E/R/R Framework** -- Elements/Roles/Rules structural decomposition verified against 3 versions of the Knowledge Base. Physics as three E/R/R formulas. 156-fallacy taxonomy with 4 detection modes.

Companion formal library: [theory-of-systems-coq](https://github.com/Horsocrates/theory-of-systems-coq) (21,901 Qed, 0 Admitted, 1497 files).

---

## Process Mathematics (Core Contribution)

The central idea: replace the universal type from R (uncountable, non-constructive) to `RealProcess := nat -> Q` (computable rational sequences). This is an ontological commitment equivalent to Church's Thesis: every mathematical object that "exists" must be constructible as a process.

### What's Proven (Rocq 9.0.1)

| Category | Files | Qed | Description |
|----------|-------|-----|-------------|
| Core Mathematics | 59 | 1300+ | IVT, EVT, series, fixed point, calculus chain |
| Architecture of Reasoning | 6 | 117 | E/R/R laws correspondence, five laws of logic |
| Process Analysis (P4) | 50+ | 800+ | Derivatives, integrals, series, Taylor, FTC |
| Process Algebra | 5 | 95 | Groups, rings, Noetherian, homomorphisms |
| Process Topology | 5 | 73 | Open sets, metric spaces, connectedness, compactness |
| Process Category Theory | 5 | 117 | Categories, adjunctions, wholeness, limits/colimits |
| Functional Analysis | 5 | 100 | Finite-dim, L2, operators, spectral theory |
| Measure Theory | 5 | 73 | Simple functions, Lebesgue, Fatou |
| ODEs | 4 | 90 | Picard, Gronwall, existence/uniqueness |
| Quantum Physics | 40+ | 500+ | Qubit, harmonic oscillator, spin chain, Born rule, entanglement |
| Lattice Gauge Theory | 30+ | 600+ | SU(2), SU(3), Wilson action, mass gap, confinement |
| Navier-Stokes | 30+ | 800+ | Grid functions, vorticity, regularity, Galerkin convergence |
| Riemann Hypothesis | 10 | 258 | Zeta zero-free region, prime sum bounds, explicit formula |
| Standard Model | 25+ | 400+ | Anomaly cancellation, Higgs mechanism, Weinberg angle |
| Gravity | 15+ | 200+ | Regge calculus, Schwarzschild, gravitational waves |
| Compression | 8 | 74 | Spectral, semantic, Huffman, quantization, pipeline |
| **Total** | **1497** | **21,901** | **0 Admitted, 2 axioms (classic, L4_witness)** |

### Key Results

- **sin^2(theta_W) = 3/13** -- Weinberg angle from E/R/R structure, 0.04% from observation, zero free parameters
- **Born = Parseval** -- measurement probability = spectral energy fraction (identity, not analogy)
- **P4 as prohibition** -- completed infinite sets are structurally impossible (CompletedInfSet + P4_bounded + bridge -> False)
- **Ordinals to epsilon_0** -- well-founded ordinals without set theory axioms
- **Navier-Stokes regularity** -- classical regularity via Galerkin convergence + uniform bounds
- **Mass gap** -- spectral gap for lattice gauge theory via transfer matrix methods

### Paper

Academic paper: `papers/process_math_v2/main.tex` (10 pages, compiled PDF available). Focused on foundations + proof theory + process completeness + Wiedijk's 100.

---

## Verified Interval Arithmetic

The `regulus/nn/`, `regulus/interval/`, and `ToS-Coq/` directories implement a complete pipeline for neural network uncertainty quantification with formal guarantees.

### The Idea

Given a trained neural network and an input `x`, we ask: *"If the input were perturbed by at most eps, how much could the output change?"* We propagate `[x - eps, x + eps]` intervals through every layer and get guaranteed output bounds.

### Rocq Verification (0 Axioms)

```
ToS-Coq/                            # 320 Qed, 0 Admitted, 0 axioms
  PInterval.v                        -- Interval arithmetic (add, mul, relu, dot, abs, div)
  PInterval_Linear.v                 -- Linear layer (scale, wdot, width bounds, relu bound)
  PInterval_Conv.v                   -- Conv2d, BatchNorm, Conv-BN-ReLU chain
  PInterval_Composition.v            -- Reanchor, MaxPool, ResBlock, chain width
  PInterval_Softmax.v                -- Sound softmax bounds (cross-multiplication)
  IVT.v                              -- Intermediate Value Theorem
  Archimedean.v                      -- Archimedean property
  ShrinkingIntervals_uncountable.v   -- Non-surjectivity via diagonal trisection
```

### Benchmark Results

**MNIST** (Architecture Benchmark):

| Method | MLP AUROC | CNN+BN AUROC | ResNet+BN AUROC | Cost |
|--------|-----------|--------------|-----------------|------|
| **RA-Margin** | **0.835** | **0.957** | **0.983** | **1x** |
| TempScaling | 0.777 | 0.959 | 0.968 | 1x |
| MC Dropout (N=50) | 0.670 | 0.738 | 0.701 | 50x |

---

## Data Compression Pipeline

ToS-derived compression where physical simulation and data compression are the same operation.

```python
from tests.compression.tos_compression import ToSCompressor
compressor = ToSCompressor(M=8)
compressed = compressor.compress(signal)
reconstructed = compressor.decompress(compressed)
```

Features: adaptive M selection, adaptive quantization, delta coding, RLE, Graph Fourier Transform. Benchmarks: 300-600x compression vs zlib for IoT diffusion data within temperature tolerance.

---

## E/R/R Framework & Fallacy Detection

### E/R/R (Elements / Roles / Rules)

Structural decomposition formalized in Rocq: every system has Elements (L1), Roles (L4), and Rules (L5). Verified against 3 versions of the Knowledge Base (10 properties).

Physics as three formulas:
- **E-formula**: ground state energy (Elements)
- **R-formula (field)**: spectrum/mode structure (Roles)
- **R-formula (evolution)**: time dynamics (Rules)

### 156 Fallacies

| Type | Description | Count |
|------|-------------|-------|
| Type 1 | Pre-reasoning failures | 36 |
| Type 2 | Domain violations (D1-D6) | 105 |
| Type 3 | Sequence violations | 3 |
| Type 4 | Systemic patterns | 6 |
| Type 5 | Context-dependent | 6 |

Detection modes: `regex` (fast), `err` (full ERR), `cascade` (2-step), `multigate` (G1-G5 gates).

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

### Zero-Gate Mechanism

| Gate | Checks | Failure means |
|------|--------|---------------|
| `gERR` | Elements, Roles, Rules all present | Missing structural component |
| `gLevels` | L1-L3 hierarchy valid | Self-reference loop |
| `gOrder` | Domain sequence D1-D6 respected | Domain skipped |

```
Gtotal = gERR AND gLevels AND gOrder
If Gtotal = 0: Weight = 0 (annihilation), Status = Invalid
```

### Status Machine (Rocq-proven, 14 Qed)

| Status | Meaning |
|--------|---------|
| **PrimaryMax** | Unique winner (gate=1, highest weight) |
| SecondaryMax | Valid alternative, equal weight |
| HistoricalMax | Was Primary, now superseded |
| Candidate | Valid but lower weight |
| Invalid | Gate=0, weight forced to 0 |

Invariants: (1) Zero-Gate Law: G=0 => W=0, (2) Uniqueness: at most one PrimaryMax, (3) Stability: Invalid cannot become PrimaryMax.

---

## Repository Structure

```
RegulusAI/
|-- regulus/                    # Core Python package
|   |-- core/                  # LogicGuard verification engine
|   |-- verified/              # Verified computation backend (Coq->OCaml->Python)
|   |-- llm/                   # LLM clients (Claude, OpenAI, DeepSeek, ZhipuAI)
|   |-- nn/                    # Interval neural network layers
|   |-- interval/              # Pure interval arithmetic (Rocq mirror)
|   |-- fallacies/             # 156-fallacy taxonomy + detector
|   |-- orchestrator.py        # Main verification loop
|   +-- cli.py                 # Typer CLI
|
|-- _tos_coq_clone/            # Companion Rocq library (21,901 Qed)
|   |-- src/                   # 33 subdirectories, 1497 .v files
|   |   |-- foundation/        # E/R/R, status machine, paradox diagnosis
|   |   |-- process/           # P4 process mathematics (analysis, algebra, topology, ...)
|   |   |-- physics/           # Physical processes, Standard Model, gravity
|   |   |-- lattice/           # Lattice gauge theory, mass gap
|   |   |-- navier_stokes/     # NS regularity
|   |   |-- gauge/             # SU(2), SU(3), confinement
|   |   |-- analysis/          # Fourier, compression, spectral
|   |   +-- ...                # acoustics, thermal, light, fermions, cosmology, ...
|   +-- Architecture_of_Reasoning/  # 6 files, E/R/R laws
|
|-- ToS-Coq/                   # Local Rocq proofs (320 Qed, intervals)
|-- ToS-StatusMachine/         # Status machine proofs (14 Qed)
|-- LogicGuard/                # Original MVP (Phase 1)
|-- papers/                    # Academic papers
|   +-- process_math_v2/       # "Process Mathematics" paper (10 pages)
|-- tests/                     # 1745 tests
|   |-- compression/           # Compression pipeline + benchmarks
|   |-- experimental/          # Physics predictions, Higgs, dual-use demo
|   +-- HLE/                   # HLE evaluation harness
|-- skills/                    # Domain instruction files (D1-D6, v3)
+-- scripts/                   # Experiment scripts
```

## Quick Start

```bash
# Clone
git clone https://github.com/Horsocrates/RegulusAI.git
cd RegulusAI

# Install
uv sync

# Run tests (1745 tests)
uv run pytest tests/ -v

# Run offline demo
uv run regulus demo --quick

# Fallacy detection
uv run regulus fallacy-detect "If evolution were true, we'd see dogs turning into cats"

# Compile Rocq proofs (requires Rocq 9.0.1)
cd ToS-Coq
coqc -Q . ToS PInterval.v
```

## Technology

- **Python 3.11+** with full type hints
- **Rocq 9.0.1** (Coq) for formal proofs -- 21,901 theorems, fully constructive
- **PyTorch 2.6+** for neural network training
- **Anthropic Claude** (primary), OpenAI, DeepSeek, ZhipuAI (LLM backends)
- **Rich** + **Typer** for CLI
- **pytest** -- 1745 tests

## License

MIT

## Citation

```bibtex
@software{regulus2026,
  title={Regulus AI: Process Mathematics and Verified Reasoning},
  author={Horsocrates},
  year={2026},
  url={https://github.com/Horsocrates/RegulusAI}
}
```
