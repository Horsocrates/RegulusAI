# Regulus Unified Architecture

## From First Principle to Verified AI Reasoning

> **A = exists** → Laws of Logic → Theory of Systems → Coq Proofs → OCaml Extraction → Python Bridge → Regulus Pipeline

---

## 1. The Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                     REGULUS PIPELINE (Python)                    │
│  D1 → D2 → D3 → D4 → D5 → D6 + Team Lead + Correction Loop   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              regulus/verified/ (Python)                    │  │
│  │  bridge.py → math_verifier.py → err_validator.py          │  │
│  │  layers.py (Information Layers)                           │  │
│  │                          ↕ JSON/subprocess                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │         OCaml Extraction (from Coq proofs)          │  │  │
│  │  │  roles.ml  l5Resolution.ml  processGeneral.ml       │  │  │
│  │  │  intensionalIdentity.ml  + stdlib deps              │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Coq Formal Library (1045 Qed)                  ││
│  │  45 .v files — IVT, EVT, CROWN, FixedPoint, Roles, ...    ││
│  │  8 Admitted (documented, with 0-Admitted alternatives)      ││
│  │  0 custom axioms                                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

Every verified result carries `theorem_used` — full traceability from Python output to the specific Coq theorem that guarantees correctness.

---

## 2. Three Integration Points

### Point 1: D1 E/R/R Structural Validator

```
D1 output → ERRValidator.validate_d1_output() → PASS/FAIL
                                                   │
                              PASS → proceed to D2 with certificate
                              FAIL → retry D1 with specific guidance
```

**What it checks (4 conditions from Roles.v, 30 Qed):**

| Condition | Description | Violation = |
|-----------|-------------|-------------|
| C1 | Category exclusivity (unique IDs) | Duplicate components |
| C2 | No cross-category self-reference | Element ≠ Rule identity |
| C3 | No cross-level role occupation | Level consistency |
| C4 | Acyclic dependencies | Circular status (paradox) |
| L4 | Every element has a role | Orphan elements |

**Cross-check feature:** If D1's self-reported `err_hierarchy_check` claims "no circular dependencies" but the formal validator finds a cycle, the discrepancy is flagged — catching LLM hallucination in self-assessment.

**File:** `regulus/verified/err_validator.py`
**Backed by:** `Roles.v` (30 Qed, 0 Admitted)

---

### Point 2: D4 Verified Computation

```
D3 framework → MathVerifier.try_verify() → VerifiedResult or None
                                               │
                         VerifiedResult → confidence_override = 100%
                         None → LLM computation (standard confidence)
```

**Available verified theorems:**

| Theorem | Trigger Keywords | Coq Source | Qed |
|---------|-----------------|------------|-----|
| IVT | "intermediate value", "root finding" | IVT_ERR.v | 23 |
| EVT | "extreme value", "maximum", "optimization" | EVT_idx.v | 26 |
| CROWN | "crown", "interval bound", "neural network" | PInterval_CROWN.v | 25 |
| Series Convergence | "convergence", "ratio test", "geometric" | SeriesConvergence.v | 22 |
| Fixed Point | "contraction", "banach", "iteration" | FixedPoint.v | 20 |
| L5 Resolution | (always available for tie-breaking) | L5Resolution.v | 18 |

When a theorem applies, the D4 output is annotated with:
```json
{
  "verified_result": {
    "value": { "max_value": 5.0, "max_index": 1, "l5_resolved": true },
    "certificate": "Maximum 5.0 at index 1 (L5: leftmost selection)",
    "theorem": "EVT_idx.argmax_idx_maximizes",
    "confidence_override": 100
  }
}
```

**File:** `regulus/verified/math_verifier.py`
**Backed by:** Multiple .v files (134 Qed total across IVT/EVT/CROWN/Series/FixedPoint/L5)

---

### Point 3: Information Layers

```
Question → D1+D2 (shared substrate) → Add layers → Per-layer D3-D5 → D6 cross-compare
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
              MATH_LAYER           EMPIRICAL_LAYER        DOMAIN_LAYER
           (criterion: proof)   (criterion: evidence)  (criterion: expertise)
                    │                     │                     │
               D3→D4→D5             D3→D4→D5             D3→D4→D5
                    │                     │                     │
                    └─────────────────────┼─────────────────────┘
                                          │
                                    D6: compare_across_layers()
                                     Agreement = high confidence
                                     Divergence = structural insight
```

**Key insight (P3 Intensional Identity):** Same substrate + different criterion = different system. This is not a bug — it's the foundation of multi-perspective analysis.

**Layer switching replaces ad-hoc paradigm_shift:**
- Substrate = D1+D2 output (shared, never rebuilt)
- Layer = D3 criterion selection
- Switch = preserve substrate, change criterion, re-run D3-D5
- Compare = D6 cross-layer analysis

**File:** `regulus/verified/layers.py`
**Backed by:** `InfoLayer.v` (17 Qed, 0 Admitted), `IntensionalIdentity.v` (11 Qed, 0 Admitted)

---

## 3. Complete Data Flow

```
Question
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ D1: Recognition                                             │
│   Extract Elements, Roles, Rules, Dependencies              │
│   ─────────────────────────────────────────────────         │
│   ► ERRValidator.gate_d1_to_d2()                            │
│     → FAIL? retry D1 with guidance                          │
│     → PASS? annotate with err_certificate, proceed          │
└──────────────┬──────────────────────────────────────────────┘
               │ (validated E/R/R)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ D2: Clarification                                           │
│   Disambiguate, resolve references                          │
└──────────────┬──────────────────────────────────────────────┘
               │ (substrate = D1+D2 output, shared)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ D3: Framework Selection + Layer Activation                  │
│   Choose analysis framework(s)                              │
│   ─────────────────────────────────────────────────         │
│   ► LayeredAnalysis.add_layer() for each relevant criterion │
│   ► Multi-layer? iterate D3-D5 per layer                    │
└──────────────┬──────────────────────────────────────────────┘
               │ (one or more layers active)
               ▼
┌─────────────────────────────────────────────────────────────┐
│ D4: Comparison / Computation                                │
│   Process data through selected framework                   │
│   ─────────────────────────────────────────────────         │
│   ► MathVerifier.try_verify(d3_framework, d4_data)          │
│     → VerifiedResult? confidence = 100% (machine-checked)   │
│     → None? use LLM computation (standard confidence)       │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ D5: Inference                                               │
│   Draw conclusions from D4 computation                      │
│   Store result: LayeredAnalysis.store_result(layer_id, ...) │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ D6: Reflection                                              │
│   ─────────────────────────────────────────────────         │
│   ► LayeredAnalysis.compare_across_layers()                 │
│     Agreement → high structural confidence                  │
│     Divergence → report which criteria differ and why       │
│   ► Zero-Gate verification: gERR ∧ gLevels ∧ gOrder        │
│   ► Status Machine: assign PrimaryMax via L5-Resolution     │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Confidence Architecture

| Level | Source | Reliability | When |
|-------|--------|-------------|------|
| **Verified** | Coq-backed theorem | **100%** — machine-checked | D4 with applicable theorem |
| **Structural** | Zero-Gate + Status Machine | High — rule-based | D6 gate check |
| **Cross-layer** | Layer agreement | High — multiple perspectives | D6 comparison |
| **LLM** | Self-reported | Variable — may hallucinate | Default D4 |

**How they combine:**
- Verified steps **anchor** the confidence (immovable 100%)
- Structural checks **constrain** it (gate failures → weight = 0)
- Cross-layer agreement **amplifies** it (convergence → structural confidence)
- LLM self-report **floats** between anchors (adjustable, not trusted alone)

```
Final confidence = max(verified_steps) × structural_gate × layer_agreement_factor
```

---

## 5. Graceful Degradation

The system works at three levels of capability:

| Level | OCaml Binaries | Verified Backend | Pipeline |
|-------|---------------|------------------|----------|
| **Full** | Compiled | OCaml computation | Maximum confidence |
| **Fallback** | Not available | Python implementations | Same API, less formal |
| **Minimal** | Not available | Backend not imported | Standard LLM pipeline |

**Key design decision:** Every function in `regulus/verified/` works WITHOUT OCaml binaries. The bridge falls back to pure Python implementations that mirror the Coq-proven algorithms. Tests never require OCaml compilation.

---

## 6. File Map

### Formal Foundations (theory-of-systems-coq)

```
theory-of-systems-coq/
├── src/                              # 39 .v files, 928 Qed
│   ├── TheoryOfSystems_Core_ERR.v   # Laws L1-L5, System, Criterion (34 Qed)
│   ├── Roles.v                      # E/R/R well-formedness (30 Qed) → ERRValidator
│   ├── L5Resolution.v              # Generalized tie-breaking (18 Qed) → l5_resolve
│   ├── InfoLayer.v                 # Information layers (17 Qed) → LayeredAnalysis
│   ├── IntensionalIdentity.v       # P3 separation (11 Qed) → layer justification
│   ├── IVT_ERR.v                   # Intermediate Value Theorem (23 Qed) → check_ivt
│   ├── EVT_idx.v                   # Extreme Value Theorem (26 Qed) → check_evt
│   ├── PInterval_CROWN.v          # CROWN bounds (25 Qed) → check_crown_bounds
│   ├── SeriesConvergence.v         # Ratio test (22 Qed) → check_convergence
│   ├── FixedPoint.v               # Banach contraction (20 Qed) → check_contraction
│   ├── LinearAlgebra.v            # QVec, QMat (20 Qed) → multi-dim verification
│   └── ...                        # 28 more files (calculus, topology, probability)
│
├── Architecture_of_Reasoning/       # 6 files, 117 Qed
│   ├── CompleteFallacyTaxonomy.v   # 156 fallacies
│   ├── ParadoxDissolution.v        # 46 paradoxes
│   └── AI_FallacyDetector.v        # LLM fallacy detection
│
└── extraction/                      # OCaml extraction (30 files)
    ├── roles.ml                    # Level, System, ERR_Category
    ├── l5Resolution.ml             # DecTotalOrder, l5_resolve_gen
    ├── processGeneral.ml           # GenProcess, observe, process_map
    └── ...                         # stdlib deps
```

### Regulus Pipeline (RegulusAI)

```
RegulusAI/
├── regulus/
│   ├── core/                        # Phase 1: verification engine
│   │   ├── types.py                # Entity, Status, Policy, Domain
│   │   ├── zero_gate.py            # Zero-Gate (gERR ∧ gLevels ∧ gOrder)
│   │   ├── weight.py               # W(e) = Gtotal × (struct + domain)
│   │   ├── status_machine.py       # L5-Resolution status assignment
│   │   └── engine.py               # Core engine orchestration
│   │
│   ├── verified/                    # Phase 4: verified computation (NEW)
│   │   ├── __init__.py             # Public API
│   │   ├── bridge.py               # OCaml-Python bridge (VerifiedBackend)
│   │   ├── math_verifier.py        # D4 verified computation (MathVerifier)
│   │   ├── err_validator.py        # D1 E/R/R validation (ERRValidator)
│   │   └── layers.py               # Information Layers (LayeredAnalysis)
│   │
│   ├── llm/                         # LLM clients + sensor
│   │   ├── client.py               # Claude + OpenAI
│   │   └── sensor.py               # ERR/Domain/Level detection
│   │
│   ├── orchestrator.py              # Main D1-D6 pipeline
│   ├── battle.py                    # Battle Mode (raw vs guarded)
│   └── ui/renderer.py              # Rich CLI
│
├── tests/
│   ├── test_verified.py             # 54 tests for verified backend (NEW)
│   ├── test_core.py                 # Core engine tests
│   └── ...                         # Other test files
│
└── UNIFIED_ARCHITECTURE.md          # This document
```

---

## 7. Theorem Coverage

### Currently Integrated (6 theorem families)

| Family | Coq Theorems | Python API | Fallback |
|--------|-------------|------------|----------|
| IVT | `intermediate_value_theorem` | `check_ivt(f_a, f_b)` | Pure Python sign check |
| EVT | `argmax_idx_maximizes` | `check_evt(values)` | Pure Python max + L5 |
| CROWN | `crown_bounds` | `check_crown_bounds(W, b, lo, hi)` | Pure Python intervals |
| Series | `ratio_test_abs` | `check_convergence(ratio)` | Pure Python comparison |
| Contraction | `banach_fixed_point` | `check_contraction(c, x0, x1)` | Pure Python bound |
| L5 | `l5_resolve_gen_minimal` | `l5_resolve(candidates)` | Pure Python min |

### Available but Not Yet Integrated (potential Phase 5)

| Family | Coq Source | Potential Use |
|--------|-----------|---------------|
| Differentiation | `Differentiation.v` (18 Qed) | Derivative-based reasoning |
| Taylor Series | `TaylorSeries.v` (18 Qed) | Approximation bounds |
| MVT | `MeanValueTheorem.v` (18 Qed) | Monotonicity arguments |
| Gradient Descent | `GradientDescent.v` (18 Qed) | Optimization convergence |
| Probability | `Probability.v` (12 Qed) | Bayesian fallacy detection |
| Softmax | `SoftmaxProbability.v` (14 Qed) | NN output verification |
| Rounding | `RoundingSafety.v` (13 Qed) | Floating-point safety |

---

## 8. Usage Examples

### Verify D4 Computation

```python
from regulus.verified import MathVerifier

verifier = MathVerifier()
result = verifier.try_verify(
    d3_framework="Extreme Value Theorem",
    d4_data={"values": [1.0, 5.0, 5.0, 3.0]}
)
# result.value = {"max_value": 5.0, "max_index": 1, "l5_resolved": True}
# result.theorem_used = "EVT_idx.argmax_idx_maximizes"
```

### Validate D1 Output

```python
from regulus.verified import ERRValidator

validator = ERRValidator()
gate = validator.gate_d1_to_d2(d1_output)
if gate["action"] == "retry_d1":
    print(f"Violations: {gate['reason']}")
    print(f"Guidance: {gate['guidance']}")
```

### Multi-Layer Analysis

```python
from regulus.verified import LayeredAnalysis
from regulus.verified.layers import MATH_LAYER, EMPIRICAL_LAYER

analysis = LayeredAnalysis(substrate=d1_d2_output)
analysis.add_layer(MATH_LAYER)
analysis.add_layer(EMPIRICAL_LAYER)

# Run D3-D5 per layer, store results
analysis.store_result("math", {"d5_answer": "42", "confidence": 0.95})
analysis.store_result("empirical", {"d5_answer": "42", "confidence": 0.88})

# D6 cross-layer comparison
comparison = analysis.compare_across_layers()
# {"agreement": True, "insight": "All layers converge → high structural confidence"}
```

---

## 9. Design Principles

1. **Traceability:** Every `VerifiedResult` carries `theorem_used` — a direct pointer to the Coq theorem that guarantees correctness.

2. **Graceful degradation:** Everything works without OCaml binaries. Python fallbacks mirror Coq-proven algorithms. Tests never require compilation.

3. **No core refactoring:** Phase 4 adds `regulus/verified/` as a new module. Existing orchestrator/engine code is untouched. Integration happens via hooks.

4. **Machine-checked > LLM-reported:** When a verified theorem applies, its confidence is 100%. This anchors the pipeline's confidence, with LLM outputs floating between verified anchor points.

5. **P3 drives layers:** Intensional Identity (same elements, different criterion = different system) is the formal justification for multi-perspective analysis. This is proven in Coq, not assumed.

---

*Phase 4 complete. 54 tests passing. 4 new files in `regulus/verified/`.*
