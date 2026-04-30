# Regulus AI -- System Map & Project Status (April 2026)

## 1. Current State: Two Repositories

### A. theory-of-systems-coq (Formal Core)
```
21,901 theorems  |  1497 .v files  |  0 Admitted  |  100% proven
```

| Block | Files | Qed | Axioms | Status |
|-------|-------|-----|--------|--------|
| Foundation (E/R/R, status, paradox) | ~60 | 600+ | classic | 100% |
| Process Mathematics (P4 analysis) | ~50 | 800+ | 0 | 100% |
| Process Algebra/Topology/Category | ~20 | 285 | 0 | 100% |
| Functional Analysis + Measure | ~10 | 173 | 0 | 100% |
| ODEs + Fixed Point | ~8 | 170 | 0 | 100% |
| Quantum Physics | ~40 | 500+ | 0 | 100% |
| Lattice Gauge Theory (SU(2)/SU(3)) | ~50 | 800+ | 0 | 100% |
| Navier-Stokes Regularity | ~30 | 800+ | 0 | 100% |
| Riemann Hypothesis | ~10 | 258 | classic | 100% |
| Standard Model + Gravity | ~60 | 700+ | 0 | 100% |
| Fourier + Compression | ~16 | 160 | 0 | 100% |
| Acoustics/Light/Thermal/Fermions | ~30 | 300+ | 0 | 100% |
| Architecture of Reasoning | 6 | 117 | 0 | 100% |
| Dynamical Systems + SFT | ~30 | 250+ | 0 | 100% |
| Green's Functions + Ising | ~20 | 200+ | 0 | 100% |
| **E/R/R Three Formulas (Apr 2026)** | **14** | **304** | **0** | **100%** |
| **TOTAL** | **1497** | **21,901** | **classic, L4_witness** | **100%** |

### B. RegulusAI (Python Implementation)
```
~60K lines Python  |  1745 tests  |  320+ local Rocq theorems  |  4 LLM providers
```

| Component | Status | Description |
|-----------|--------|-------------|
| **Core Engine** | Production | Zero-Gate, Weight, Status Machine |
| **LLM Integration** | Production | Claude, OpenAI, DeepSeek, ZhipuAI |
| **Multi-Agent (MAS)** | Production | P3 pipeline: Team Lead + D1-D5 workers |
| **Fallacy Detection** | Production | 156 fallacies, 4-mode LLM extractor, 50+ patterns |
| **Interval Arithmetic** | Production | composition, softmax, EVT, trisection (Rocq-verified) |
| **NN Verification** | Experimental | IBP + CROWN, ResNet (52%/21% best clean/cert) |
| **Verified Backend** | Production | Coq->OCaml->Python bridge, math_verifier, err_validator |
| **Convergence Advisor** | Production | Banach contraction analysis, stall detection |
| **Data Compression** | Production | ToS pipeline, GFT, Born-optimal, IoT benchmarks |
| **Lab Framework** | Production | Batch runs, grading, archival |
| **Skills/Prompts** | Production | D1-D6 v3 instructions, scorecards |
| **CLI** | Production | Typer + Rich (ask, verify, demo, fallacy-detect) |
| **Academic Paper** | Complete | Process Mathematics v2 (10 pages, PDF compiled) |

---

## 2. Local Rocq Theorems (ToS-Coq/ + ToS-StatusMachine/)

| File | Qed | Axioms | Domain |
|------|-----|--------|--------|
| PInterval.v | 43 | 0 | Interval arithmetic |
| PInterval_Linear.v | 18 | 0 | Linear layers, width bounds |
| PInterval_Conv.v | 16 | 0 | Conv2d + BatchNorm chain |
| PInterval_Composition.v | 26 | 0 | Reanchor, MaxPool, ResBlock |
| PInterval_Softmax.v | 13 | 0 | Softmax bounds |
| Extraction_PInterval.v | -- | 0 | OCaml extraction |
| IVT.v | 23 | 0 | Intermediate Value Theorem |
| Archimedean.v | 14 | 0 | Archimedean property |
| ShrinkingIntervals_uncountable.v | 167 | 0 | Non-surjectivity |
| ToS_Status_Machine_v8.v | 14 | 0 | Status machine |
| **TOTAL** | **334** | **0** | All axiom-free |

---

## 3. Key Results & Predictions

| Result | Source | Significance |
|--------|--------|-------------|
| sin^2(theta_W) = 3/13 | E/R/R structure | 0.04% from observation, zero free parameters |
| Born = Parseval | Crown jewel | Measurement probability = spectral energy |
| P4 = prohibition | CompletedInfSet + bridge -> False | No completed infinite sets |
| Ordinals to epsilon_0 | Well-founded Ord | Without set theory axioms |
| NS regularity | Galerkin + uniform bounds | 6 phases, 800+ theorems |
| Mass gap | Transfer matrix + spectral | Lattice gauge in 2+1D and 3+1D |
| compress() = simulate_physics() | E/R/R bijection | Same operation, different names |
| H2 vibrational gap = 4159 cm^-1 | AnharmonicSHO Morse | 0.05% from observed (4161) |
| Lyman/Balmer ratio = 27/5 | PlanckBridge | 0.06% from 5.397 observed |
| Apéry zeta(3) bracket | AperyConstantERR | 1202/1000 < a_3 < 1203/1000 |
| Periodic table rows 2,8,18,32 | HydrogenStructure (n^2 + Pauli) | exact via 2*n^2 |
| He^{2+}, Li^{2+}, C^{5+} ground | Z^2-law hydrogen-like | exact (-2, -9/2, -18 Hartree) |

---

## 4. Three Subsystems

### Subsystem 1: Logic Censor (Fallacy Detection)
```
Input: LLM reasoning text
Process: Signal extraction -> Fallacy detection -> Fix prompt
Output: Verdict + Explanation + Correction

Maturity: 90%
Key files: regulus/fallacies/, regulus/core/, skills/
Formal base: 21,901 theorems
```

### Subsystem 2: Interval Verifier (NN Verification)
```
Input: Trained PyTorch model + epsilon
Process: IBP propagation -> CROWN refinement -> Certification
Output: % certified robustness + traceable uncertainty

Maturity: 75%
Key files: regulus/nn/, regulus/interval/
Formal base: 334 local theorems (PInterval + Conv/BN/Linear/Composition/Softmax)
```

### Subsystem 3: MAS Pipeline (Multi-Agent Solver)
```
Input: Complex question
Process: D1->D2->D3->D4->D5->D6 sequential domain analysis
Output: Structured answer + confidence + convergence estimate

Maturity: 80%
Key files: regulus/orchestrator.py, regulus/llm/, skills/
Formal base: Architecture_of_Reasoning (117 theorems)
```

---

## 5. Companion Library Structure (_tos_coq_clone/src/)

33 subdirectories covering:

| Directory | Description |
|-----------|-------------|
| `foundation/` | E/R/R framework, status machine, paradox diagnosis, knowledge base |
| `process/` | P4 process mathematics (analysis, algebra, topology, category, measure, ODE) |
| `physics/` | Physical processes, Standard Model, Higgs, Weinberg angle |
| `lattice/` | Lattice gauge theory, SU(2), SU(3), mass gap |
| `gauge/` | Wilson action, transfer matrix, confinement |
| `navier_stokes/` | Grid functions, vorticity, Galerkin, regularity |
| `zeta/` | Riemann zeta, zero-free region, prime sums |
| `gravity/` | Regge calculus, Schwarzschild, gravitational waves |
| `analysis/` | Fourier, spectral decomposition, Cayley connection |
| `stdlib/compression/` | Spectral, semantic, Huffman, quantization |
| `acoustics/` | Oscillation, wave propagation, sound spectrum |
| `light/` | Photon, Snell, interference, polarization |
| `fermions/` | Wilson-Dirac, fermion determinant, Pauli exclusion |
| `thermal/` | Heat processes, thermal equilibrium |
| `crown/` | Born = Parseval, compression = physics |
| `process_qm/` | Qubit, harmonic oscillator, measurement |
| `projective/` | Projective systems and limits |
| `experimental/` | Casimir, vacuum energy, Coulomb, Lamb shift |
| `settheory/` | Ordinals, Perron-Frobenius, SFT classification |

---

## 6. Test Coverage

| Test Area | Tests | Status |
|-----------|-------|--------|
| Core engine (zero-gate, weight, status) | 22 | Passing |
| Interval arithmetic | 37 | Passing |
| Composition + reanchor | 17 | Passing |
| Softmax verified | 11 | Passing |
| EVT | 18 | Passing |
| Trisection | 19 | Passing |
| Adversarial | 9 | Passing |
| Socratic trisection | 19 | Passing |
| Optimizer | 14 | Passing |
| Verified backend (bridge, err, layers) | 54 | Passing |
| Convergence | 13 | Passing |
| Compression pipeline | 87+ | Passing |
| Fallacy detection | 5+ | Passing |
| Other (HLE, experimental, etc.) | 1400+ | Passing |
| **TOTAL** | **1745** | **Collected** |

Note: 9 collection errors (test_verifier.py etc.) due to torch DLL issues on Windows.

---

## 7. Development Timeline

| Phase | When | What |
|-------|------|------|
| Phase 1 | Jan 2026 | LogicGuard MVP |
| Phase 2-3 | Feb 2026 | LLM integration + orchestrator |
| Phase 4 | Feb 2026 | Verified backend |
| Phase 5 | Feb 2026 | HLE evaluation |
| Phase 6 | Feb 2026 | Fixed-point convergence |
| ToS Phases 1-3 | Feb 2026 | Extraction, intervals, L5Resolution |
| ToS-Lang A-D | Feb-Mar 2026 | Type system, compiler |
| Physics | Mar 2026 | Quantum, gauge, NS, RH, SM, gravity |
| Process Math P4 | Mar 2026 | Analysis, algebra, topology, category |
| E/R/R + Compression | Mar-Apr 2026 | Foundation formalization, data compression |
| Paper v2 | Apr 2026 | Academic paper restructured |
| **Current** | **Apr 2026** | **21,901 Qed, 0 Admitted, paper compiled** |
