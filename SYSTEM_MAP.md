# Regulus AI — System Map & Project Status (March 2026)

## 1. Current State: Two Repositories

### A. theory-of-systems-coq (Formal Core)
```
~470-510 theorems  |  ~12K lines Coq  |  14 Admitted  |  97% proven
```

| Block | Files | Theorems | Axioms | Status |
|-------|-------|----------|--------|--------|
| Mathematical core (src/) | 11 unique | ~350 | classic + epsilon | 97% proven |
| Architecture of Reasoning | 6 | 124 | **0** | **100% proven** |
| **TOTAL** | **17 unique** | **~474** | **classic + epsilon** | **97%** |

Note: ShrinkingIntervals_ERR.v and ShrinkingIntervals_uncountable_ERR.v are duplicates (byte-identical). Real unique file count = 16.

### B. RegulusAI (Python Implementation)
```
~40K lines Python  |  188 tests passing  |  61 Coq theorems (local)  |  4 LLM providers
```

| Component | Size | Status | Description |
|-----------|------|--------|-------------|
| **Core Engine** | 98 KB | Production | Zero-Gate, Weight, Status Machine |
| **LLM Integration** | 85 KB | Production | Claude, OpenAI, DeepSeek, Moonshot |
| **Multi-Agent (MAS)** | 56 KB | Production | P3 pipeline: Team Lead + D1-D5 workers |
| **Fallacy Detection** | 250 KB | Production | 156 fallacies, 4-mode LLM extractor, 50+ patterns |
| **Interval Arithmetic** | 35 KB | Production | composition, softmax, EVT, trisection (Coq-verified) |
| **NN Verification** | 240 KB | Experimental | IBP + CROWN, ResNet (61%/11% best clean/cert) |
| **Adversarial Generation** | 5 KB | New | Certified diagonal trisection |
| **Lab Framework** | 212 KB | Production | Batch runs, grading, archival |
| **REST API** | 148 KB | Partial | FastAPI, CRUD ready, auth pending |
| **Benchmarks** | 90 KB | Production | LOGIC, MAFALDA, integration suite |
| **Demo Scripts** | 30 KB | New | MNIST, depth study, breast cancer reliability |
| **Skills/Prompts** | 356 KB | Production | D1-D6 v3 instructions, scorecards |
| **CLI/UI** | 28 KB | Partial | Typer + Rich, expanded commands |

---

## 2. Local Coq Theorems (ToS-Coq/ in RegulusAI)

| File | Theorems | Axioms | Status |
|------|----------|--------|--------|
| PInterval.v | 11 | 0 | Base arithmetic |
| PInterval_Linear.v | 8 | 0 | Linear layers, width bounds |
| PInterval_Conv.v | 13 | 0 | Conv2d + BatchNorm chain |
| PInterval_Composition.v | 9 | 0 | **NEW** Reanchor, MaxPool, ResBlock, chain width |
| PInterval_Softmax.v | 6 | 0 | **NEW** Sound softmax bounds (cross-multiplication) |
| ToS_Status_Machine_v8.v | 14 | 0 | Status machine, zero-gate, uniqueness |
| **TOTAL** | **61** | **0** | All axiom-free |

---

## 3. New Modules (added March 2026) & Integration Status

### Integration into NN Verification Pipeline:

| Module | What it does | CIFAR-10 integration | Gap |
|--------|-------------|---------------------|-----|
| **composition.py** | Depth-independent width bounds via reanchoring | Referenced in reanchor.py for DIAGNOSTICS ONLY | NOT used for adaptive control |
| **softmax.py** | Verified softmax output bounds | IntervalSoftmax exists in layers.py | CIFAR models use Linear output, not Softmax |
| **evt.py** | Certified argmax with grid refinement | STANDALONE | Not connected to verification pipeline |
| **trisection.py** | Diagonal construction with certified gaps | STANDALONE | Not connected to benchmark |
| **adversarial.py** | Adversarial inputs via trisection | STANDALONE | Not in CIFAR benchmark |
| **llm_extractor.py** | 4-mode LLM fallacy classification | STANDALONE (benchmarks only) | Not in orchestrator correction loop |
| **detector.py** (enhanced) | 50+ regex patterns | Connected to CLI | Not in automated pipeline |

### Expected CIFAR-10 Improvement from Integration:

| Integration Task | Expected Gain | Complexity |
|-----------------|---------------|------------|
| Composition-aware adaptive reanchoring | +3-5pp cert | Medium |
| Softmax output layer + verified bounds | +2-3pp cert | Medium |
| EVT certified argmax at output | +1-2pp cert | Low |
| Adversarial test suite generation | robustness analysis (no direct gain) | Low |
| **Total theoretical max** | **+7-10pp** certified | — |

Current best: M4 (52% clean, 21% cert), M3 (61% clean, 11% cert).
After integration: potentially 28-31% cert at 52% clean.

---

## 4. Three Subsystems

### Subsystem 1: Logic Censor (Fallacy Detection)
```
Input: LLM reasoning text
Process: Signal extraction → Fallacy detection → Fix prompt
Output: Verdict + Explanation + Correction

Maturity: ██████████░ 90%
Key files: fallacies/, core/, mas/
Formal base: 124 theorems (AI + Fallacies + Paradoxes)
```

### Subsystem 2: Interval Verifier (NN Verification)
```
Input: Trained PyTorch model + epsilon
Process: IBP propagation → CROWN refinement → Certification
Output: % certified robustness + traceable uncertainty

Maturity: ████████░░ 75%
Key files: nn/, interval/
Formal base: 61 theorems (PInterval + Conv/BN/Linear/Composition/Softmax)
```

### Subsystem 3: MAS Pipeline (Multi-Agent Solver)
```
Input: Complex question
Process: D1→D2→D3→D4→D5→D6 sequential domain analysis
Output: Structured answer + confidence

Maturity: ████████░░ 80%
Key files: mas/, lab/, skills/
Formal base: Architecture_of_Reasoning.v (17 theorems)
```

---

## 5. TODO: Two Tracks

### Track 1: Integration & Benchmarking (Testing new modules in infrastructure)

#### T1.1 — Composition-Aware Adaptive Reanchoring [HIGH PRIORITY]
- **What**: Modify `reanchor.py` to use `chain_width_product` for dynamic eps control
- **Why**: Currently reanchor eps is fixed; composition theorem predicts width per layer
- **Expected**: +3-5pp CIFAR-10 certified accuracy
- **Files**: `regulus/nn/reanchor.py`, `regulus/interval/composition.py`

#### T1.2 — Softmax Output Layer for CIFAR-10 [MEDIUM]
- **What**: Add optional softmax to ResNetCIFAR; use `IntervalSoftmax` for verified output bounds
- **Why**: Current models use Linear output → no probability bounds
- **Expected**: +2-3pp cert; enables probability-level uncertainty statements
- **Files**: `regulus/nn/architectures.py`, `regulus/nn/layers.py`

#### T1.3 — EVT-Enhanced Status Machine [LOW]
- **What**: Replace standard argmax with EVT `argmax_idx` in verification pipeline
- **Why**: Certified tie-breaking on boundary cases
- **Expected**: +1-2pp on close-call images
- **Files**: `regulus/nn/verifier.py`, `regulus/interval/evt.py`

#### T1.4 — Adversarial Test Suite for CIFAR-10 [RESEARCH]
- **What**: Use `adversarial.py` to generate certified-gap adversarial inputs
- **Why**: Systematic robustness analysis beyond clean test set
- **Files**: `regulus/nn/adversarial.py`, `benchmarks/integration_benchmark.py`

#### T1.5 — LLM Extractor → Orchestrator Integration [MEDIUM]
- **What**: Wire `llm_extractor.py` into orchestrator correction loop
- **Why**: Currently standalone; orchestrator uses heuristic detector
- **Files**: `regulus/orchestrator.py`, `regulus/fallacies/llm_extractor.py`

#### T1.6 — MAFALDA Benchmark Full Run [LOW]
- **What**: Run MAFALDA benchmark with all 4 modes (regex/err/cascade/multigate)
- **Why**: First benchmark with false positive analysis; validates detector quality
- **Files**: `benchmarks/mafalda_benchmark.py`

### Track 2: Formal System Development

#### T2.1 — Close Admitted in theory-of-systems-coq [HIGH PRIORITY]
- **What**: Prove 8-10 of 14 Admitted lemmas
- **Targets**:
  - `diagonal_differs_at_n` (DiagonalArgument_ERR.v) — technique from EVT_idx.v
  - `enum_surjective` (Countability_Q.v) — induction on Calkin-Wilf tree path
  - `path_cw_node_roundtrip` (Countability_Q.v) — prerequisite for surjectivity
  - Mark EVT_ERR.v as deprecated (replaced by EVT_idx.v, 0 Admitted)
  - `extracted_equals_floor` + `diagonal_Q_separation` (TernaryRepresentation_ERR.v)
- **Expected**: 14 → 4-6 Admitted (only fundamentally unprovable over Q)
- **Repo**: theory-of-systems-coq

#### T2.2 — CI/CD for theory-of-systems-coq [HIGH PRIORITY]
- **What**: _CoqProject + Makefile + GitHub Actions with Coq Docker image
- **Why**: Reproducibility; automated verification on push
- **Repo**: theory-of-systems-coq

#### T2.3 — Cleanup: Remove Duplicate File [TRIVIAL]
- **What**: Delete ShrinkingIntervals_uncountable_ERR.v (duplicate of ShrinkingIntervals_ERR.v)
- **Repo**: theory-of-systems-coq

#### T2.4 — Mechanical Coq Extraction [MEDIUM]
- **What**: Add `Extraction` commands for EVT_idx.v → evt_verified.ml, ShrinkingIntervals_ERR.v → trisection_verified.ml
- **Why**: Replace hand-written OCaml with mechanically extracted code → guaranteed Coq=Python
- **Repo**: theory-of-systems-coq + RegulusAI/ToS-Coq/

#### T2.5 — CROWN Soundness in Coq [MEDIUM]
- **What**: New file `PInterval_CROWN.v` — soundness of linear relaxation for ReLU
- **Key theorem**: `crown_tighter_ibp: width_crown ≤ width_ibp` (proven from slope optimization)
- **Why**: Formal guarantee that CROWN is sound (currently only empirically validated)
- **Repo**: RegulusAI/ToS-Coq/

#### T2.6 — NN ↔ LogicGuard Bridge in Coq [MEDIUM]
- **What**: Formalize `nn_certified → D5_NoViolation` and `width > threshold → D6_Violation`
- **Why**: All three external reviewers (GPT-5.2, Grok, Gemini) recommend this integration
- **Repo**: theory-of-systems-coq (Architecture_of_Reasoning/)

### Track 3: Mathematical Foundations (Long-Term)

#### T3.1 — Complete ℝ (Cauchy + Dedekind via P4) [STRATEGIC]
**Current state**: Only ε-versions of theorems + nested rational intervals.

**What it gives our architecture:**
- Full IVT, EVT, Heine-Borel, completeness — not just ε-approximations
- Verified floating-point rounding in ToS-reals: prove that IEEE 754 rounding never breaks convergence
- Direct application: guaranteed stability of IBP training loss convergence
- Extraction: Coq-verified numerical routines for PyTorch integration

**Concrete deliverables:**
1. `RealNumber.v` — Cauchy completion of Q via P4-processes
2. `IVT_Complete.v` — Full IVT (not ε-IVT) using completed reals
3. `Training_Convergence.v` — Prove: under conditions C, IBP loss decreases monotonically
4. Extraction → `verified_numerics.py` for production use

**Gap from current state**: We have ε-IVT (works for any ε>0 but never reaches exact zero). Full ℝ gives exact statements: "there EXISTS a root" not "for any ε there exists x with |f(x)| < ε".

#### T3.2 — Probability / Measure Theory [STRATEGIC]
**Current state**: 0 files in either repository.

**What it gives our architecture:**
- Bayesian network verification: prove posterior is structurally correct (no hallucinated probabilities)
- Probabilistic fallacy detection: formalize base-rate fallacy, gambler's fallacy, conjunction fallacy
- Uncertainty quantification: `P([lo, hi] contains true value) ≥ 1-δ` (soft guarantees)
- Stochastic process convergence: prove "policy converges with probability 1"

**Concrete deliverables:**
1. `Measure.v` — Constructive Lebesgue measure on [0,1] via P4-processes
2. `Probability.v` — Probability space, conditional probability, Bayes' theorem
3. `ProbabilisticFallacies.v` — Formalize 8-10 probabilistic fallacies from taxonomy
4. `SoftmaxProbability.v` — Bridge: interval softmax bounds → probability statements
5. Python port → `regulus/interval/probability.py`

**Gap from current state**: Our softmax.py gives [P_lo, P_hi] bounds but can't say "the confidence level of this bound is 95%". Measure theory enables statements about the DISTRIBUTION of outputs, not just worst-case intervals.

#### T3.3 — Optimization Theory [FUTURE]
- Convergence proofs for GD, SGD, Adam
- Verified RL: "policy converges with probability 1"
- Extraction → verified optimizers for production

---

## 6. NN Verification Best Results (CIFAR-10, ε=0.005)

| Exp | Architecture | λ | Warmup | Epochs | Clean | Cert | Notes |
|-----|-------------|---|--------|--------|-------|------|-------|
| M3 | ResNetCIFAR_FC2 | 0.14 | 0.50 | 150 | **61%** | 11% | Best clean |
| M4 | ResNetCIFAR_FC2 | 0.12 | 0.45 | 200 | 52% | **21%** | Best balance |
| H3 | ResNetCIFAR | 0.20 | — | — | 46% | 29% IBP | No FC ReLU for CROWN |

**Key insight**: No config achieved BOTH clean≥40% AND cert≥40%. Gap = integration of composition-aware reanchoring + longer training + architecture search.

---

## 7. Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| test_core.py | 22 | Passing |
| test_interval.py | 37 | Passing |
| test_socratic_trisection.py | 19 | Passing |
| test_optimizer.py | 14 | Passing |
| test_composition.py | 17 | Passing (new) |
| test_evt.py | 18 | Passing (new) |
| test_softmax_verified.py | 11 | Passing (new) |
| test_trisection_interval.py | 19 | Passing (new) |
| test_adversarial.py | 9 | Passing (new) |
| test_llm_fallacy_extractor.py | ~5 | Passing (new) |
| **TOTAL** | **188** | **All passing** |

Note: test_diagnostics.py, test_interval_properties.py, test_verifier.py require torch (broken on Windows/Python 3.14).
