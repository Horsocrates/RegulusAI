# Regulus Unified Architecture (April 2026)

## From First Principle to Verified AI Reasoning

> **A = exists** -> Laws of Logic (L1-L5) -> Principles (P1-P4) -> RealProcess := nat -> Q -> Rocq Proofs (21,901 Qed) -> OCaml Extraction -> Python Bridge -> Regulus Pipeline

---

## 1. The Stack

```
+------------------------------------------------------------------+
|                     REGULUS PIPELINE (Python)                      |
|  D1 -> D2 -> D3 -> D4 -> D5 -> D6 + Team Lead + Correction Loop  |
|                                                                    |
|  +--------------------------------------------------------------+ |
|  |              regulus/verified/ (Python)                        | |
|  |  bridge.py -> math_verifier.py -> err_validator.py            | |
|  |  layers.py (Information Layers)                               | |
|  |  convergence.py + convergence_advisor.py (Banach)             | |
|  |                          JSON/subprocess                      | |
|  |  +----------------------------------------------------------+ | |
|  |  |         OCaml Extraction (from Rocq proofs)               | | |
|  |  |  roles.ml  l5Resolution.ml  processGeneral.ml            | | |
|  |  |  gap_calculator.ml  tos_lang/main.ml                     | | |
|  |  +----------------------------------------------------------+ | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  +--------------------------------------------------------------+ |
|  |              Rocq Formal Library (21,901 Qed)                | |
|  |  1497 .v files -- 0 Admitted -- 2 axioms (classic, L4_witness)| |
|  |  Mathematics + Physics + E/R/R + Standard Model + NS + RH    | |
|  +--------------------------------------------------------------+ |
|                                                                    |
|  +--------------------------------------------------------------+ |
|  |              Data Compression Pipeline                        | |
|  |  tests/compression/ -- ToS-derived: compress() = physics()   | |
|  |  GFT, Born-optimal, gamma-unification, .gft format           | |
|  +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

Every verified result carries `theorem_used` -- full traceability from Python output to the Rocq theorem that guarantees correctness.

---

## 2. Process Mathematics Foundation

The system is built on `RealProcess := nat -> Q` -- every mathematical object is a computable rational sequence. This is an ontological commitment equivalent to Church's Thesis (P4).

```
A = exists
  |
  v
Laws of Logic: L1 (Identity), L2 (Non-contradiction), L3 (Excluded Middle),
               L4 (Sufficient Reason), L5 (Resolution/Determinism)
  |
  v
Principles: P1 (Wholeness), P2 (Complementarity), P3 (Intensional Identity),
            P4 (Finitary Constructibility -- NO completed infinite sets)
  |
  v
RealProcess := nat -> Q (universal type)
  |
  v
Classical Analysis: IVT, EVT, Calculus, ODEs, Measure Theory, Functional Analysis
  |
  v
Physics: Quantum mechanics, Lattice gauge theory, Standard Model, Gravity, NS
  |
  v
Experimental Predictions: sin^2(theta_W) = 3/13, Born = Parseval
```

### Key Formal Results

| Result | Theorem Count | Significance |
|--------|--------------|-------------|
| Process completeness | 800+ Qed | Stagewise completeness for analysis |
| sin^2(theta_W) = 3/13 | 38 Qed | 0.04% from observation, 0 parameters |
| Born = Parseval | 13 Qed | Measurement = spectral energy (identity) |
| P4 prohibition | bridge -> False | No completed infinite sets |
| Navier-Stokes regularity | 800+ Qed | Classical regularity via Galerkin |
| Mass gap | 600+ Qed | Spectral gap via transfer matrix |
| Ordinals to epsilon_0 | wf_ord_lt | Without set theory axioms |

---

## 3. Three Integration Points

### Point 1: D1 E/R/R Structural Validator

```
D1 output -> ERRValidator.validate_d1_output() -> PASS/FAIL
                                                    |
                              PASS -> proceed to D2 with certificate
                              FAIL -> retry D1 with specific guidance
```

**Checks 4 conditions (from Roles.v, 30 Qed + ERRWellFormedness.v, 9 Qed):**

| Condition | Description | Violation = |
|-----------|-------------|-------------|
| C1 | Category exclusivity (unique IDs) | Duplicate components |
| C2 | No cross-category self-reference | Element != Rule identity |
| C3 | No cross-level role occupation | Level consistency |
| C4 | Acyclic dependencies | Circular status (paradox) |

**File:** `regulus/verified/err_validator.py`

### Point 2: D4 Verified Computation

```
D3 framework -> MathVerifier.try_verify() -> VerifiedResult or None
                                                |
                         VerifiedResult -> confidence_override = 100%
                         None -> LLM computation (standard confidence)
```

**Available theorem families:**

| Theorem | Trigger Keywords | Rocq Source | Qed |
|---------|-----------------|-------------|-----|
| IVT | "intermediate value", "root" | IVT_ERR.v | 23 |
| EVT | "extreme value", "maximum" | EVT_idx.v | 26 |
| CROWN | "crown", "interval bound" | PInterval_CROWN.v | 25 |
| Series | "convergence", "ratio test" | SeriesConvergence.v | 22 |
| Contraction | "contraction", "banach" | FixedPoint.v | 20 |
| L5 Resolution | (always available) | L5Resolution.v | 18 |

### Point 3: Information Layers (P3 Intensional Identity)

Same substrate + different criterion = different system.

```
Question -> D1+D2 (shared substrate) -> Add layers -> Per-layer D3-D5 -> D6 cross-compare
                                           |
                  MATH_LAYER          EMPIRICAL_LAYER       DOMAIN_LAYER
                  (proof)             (evidence)            (expertise)
                      |                    |                     |
                 D3->D4->D5           D3->D4->D5           D3->D4->D5
                      |                    |                     |
                      +-------- D6: compare_across_layers() ----+
                                Agreement = high confidence
                                Divergence = structural insight
```

**File:** `regulus/verified/layers.py`
**Backed by:** `InfoLayer.v` (17 Qed), `IntensionalIdentity.v` (11 Qed)

---

## 4. Convergence Analysis (Banach Fixed-Point)

Models the pipeline iteration as a contraction mapping on [0, 100] confidence space.

```python
from regulus.verified import ConvergenceAdvisor

advisor = ConvergenceAdvisor()
advisor.record(50.0)   # iteration 1
advisor.record(75.0)   # iteration 2
advisor.record(87.5)   # iteration 3
print(advisor.advise())
# [ACTION] CONTINUE
# [REASON] Contractive (c=0.500). Estimated 3 more iterations.
# [THEOREM] FixedPoint.v: Banach_contraction_principle
```

**Backed by:** `ReasoningConvergence.v` (19 Qed, 0 Admitted)

---

## 5. Data Compression Pipeline

ToS-derived compression where physical simulation and data compression are the same operation.

```
Signal -> Graph Fourier Transform -> Spectral coefficients -> Quantize -> Encode
                |                           |
                v                           v
         Process evolution          Born rule: P(k) = |A_k|^2
         (Rules)                    (Measurement = compression)
```

**Key bijections (formalized in Rocq):**
- `compression_is_physics` -- same algorithm, different names
- `born_sum_is_parseval` -- Born rule = Parseval identity
- `collapse_is_max_compression` -- quantum collapse = keeping one mode
- `three_are_one` -- decoherence = damping = compression loss (gamma-unification)

**Files:** `tests/compression/` (pipeline, GFT, benchmarks, .gft format)
**Backed by:** `src/crown/`, `src/foundation/`, `src/stdlib/compression/` (74 Qed)

---

## 6. Confidence Architecture

| Level | Source | Reliability | When |
|-------|--------|-------------|------|
| **Verified** | Rocq-backed theorem | **100%** | D4 with applicable theorem |
| **Structural** | Zero-Gate + Status Machine | High (rule-based) | D6 gate check |
| **Cross-layer** | Layer agreement | High (multi-perspective) | D6 comparison |
| **Convergence** | Banach contraction | Estimated | After 3+ iterations |
| **LLM** | Self-reported | Variable | Default D4 |

---

## 7. E/R/R Framework (Formalized)

Every system decomposes into Elements (L1), Roles (L4), Rules (L5).

**Foundation files (Rocq):**
- `ERRProcess.v` (12 Qed) -- GateSignals, RawScores, IntegrityGate, zero_gate_law
- `StatusFromERR.v` (11 Qed) -- compare_entities, uniqueness, stability
- `ERRWellFormedness.v` (9 Qed) -- decidable well-formedness
- `ParadoxDiagnosis.v` (11 Qed) -- 5 paradox types, all_paradoxes_ill_formed
- `ERRKnowledgeBase.v` (35 Qed) -- 10 properties from Knowledge Base v3
- `PhysicsERR.v` (9 Qed) -- three physics formulas
- `GammaUnification.v` (10 Qed) -- decoherence = damping = compression

**Physics as three E/R/R formulas:**
- **E-formula**: ground state energy (Elements)
- **R-formula (field)**: spectrum/mode structure (Roles)
- **R-formula (evolution)**: time dynamics (Rules)

---

## 8. Graceful Degradation

| Level | OCaml Binaries | Verified Backend | Pipeline |
|-------|---------------|------------------|----------|
| **Full** | Compiled | OCaml computation | Maximum confidence |
| **Fallback** | Not available | Python implementations | Same API, less formal |
| **Minimal** | Not available | Backend not imported | Standard LLM pipeline |

Every function in `regulus/verified/` works WITHOUT OCaml binaries. Python fallbacks mirror Rocq-proven algorithms.

---

## 9. Repository Statistics (April 2026)

| Metric | Value |
|--------|-------|
| Rocq theorems (companion library) | 21,901 Qed |
| Rocq theorems (local ToS-Coq) | 320 Qed |
| Admitted | 0 |
| Custom axioms | 2 (classic, L4_witness) |
| Rocq files | 1497 |
| Python tests | 1745 |
| Fallacy taxonomy | 156 fallacies |
| Src subdirectories | 33 |
| LLM providers | 4 |

---

## 10. Design Principles

1. **Traceability:** Every `VerifiedResult` carries `theorem_used` -- a direct pointer to the Rocq theorem.

2. **Graceful degradation:** Everything works without OCaml binaries. Python fallbacks mirror Rocq-proven algorithms.

3. **Machine-checked > LLM-reported:** When a verified theorem applies, confidence is 100%. LLM outputs float between verified anchor points.

4. **P3 drives layers:** Intensional Identity is the formal justification for multi-perspective analysis (proven in Rocq).

5. **P4 drives universality:** RealProcess := nat -> Q replaces R. Everything computable, everything constructive, everything verifiable.

6. **compress() = simulate_physics():** Data compression and physical evolution are the same E/R/R operation (formally proven bijection).
