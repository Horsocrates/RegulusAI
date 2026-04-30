# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Regulus AI is a deterministic reasoning verification system for LLMs implementing the Theory of Systems (ToS) framework. It combines:
- **LogicGuard** -- multi-agent reasoning verification with Zero-Gate mechanism
- **Process Mathematics** -- complete mathematical foundation (`RealProcess := nat -> Q`) with 21,901 Rocq theorems
- **Verified Interval Propagation** -- Rocq-verified neural network uncertainty quantification
- **Data Compression** -- ToS-derived compression pipeline (`compress() = simulate_physics()`)
- **E/R/R Framework** -- Elements/Roles/Rules structural decomposition + 156-fallacy taxonomy

Companion formal library: [theory-of-systems-coq](https://github.com/Horsocrates/theory-of-systems-coq) (21,901 Qed, 0 Admitted, 1497 files).

## Repository Layout

```
RegulusAI/
├── CLAUDE.md                        # This file
├── README.md                        # Project overview
├── REGULUS_CLI_SPEC.md              # Full PRD specification
├── SYSTEM_MAP.md                    # Architecture map
├── UNIFIED_ARCHITECTURE.md          # Full stack diagram
├── regulus/                         # Core Python package
│   ├── core/                        # LogicGuard engine (types, zero_gate, weight, status_machine)
│   ├── verified/                    # Verified backend (bridge.py, math_verifier.py, err_validator.py)
│   ├── llm/                         # LLM clients (Claude, OpenAI, DeepSeek, ZhipuAI)
│   ├── nn/                          # Interval neural network layers
│   ├── interval/                    # Pure interval arithmetic (Rocq mirror)
│   ├── fallacies/                   # 156-fallacy taxonomy + detector
│   ├── orchestrator.py              # Main verification loop
│   └── cli.py                       # Typer CLI
├── _tos_coq_clone/                  # Companion Rocq library (21,901 Qed, 1497 files)
│   ├── src/                         # 33 subdirectories (foundation, process, physics, lattice, ...)
│   └── Architecture_of_Reasoning/   # E/R/R laws correspondence
├── ToS-Coq/                         # Local Rocq proofs (intervals, 320 Qed)
├── ToS-StatusMachine/               # Status machine proofs (14 Qed)
├── LogicGuard/                      # Original MVP (Phase 1)
├── papers/process_math_v2/          # Academic paper (10 pages)
├── tests/                           # 1745 tests
│   ├── compression/                 # ToS compression pipeline + benchmarks
│   ├── experimental/                # Physics predictions, Higgs corrections
│   └── HLE/                         # HLE evaluation harness
├── skills/                          # Domain instruction files (D1-D6, v3)
└── GoLeo/                           # Go AI project (gitignored, separate)
```

## Commands

```bash
# Run all tests (MUST use uv run on this machine, plain python fails)
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_core.py -v

# Run a single test
uv run pytest tests/test_core.py -v -k "test_name"

# Interval tests (37 tests)
uv run pytest tests/test_interval.py -v

# Compression tests
uv run pytest tests/compression/ -v

# CLI
uv run regulus ask "query" --provider claude -v
uv run regulus demo --quick

# Fallacy detection
uv run regulus fallacy-detect "text to analyze"

# Compile Rocq proofs (companion library)
cd _tos_coq_clone
ROCQLIB="C:\\Coq\\Rocq-Platform~9.0~2025.08\\lib\\coq" "C:\\Coq\\Rocq-Platform~9.0~2025.08\\bin\\coqc.exe" -Q src ToS -Q Architecture_of_Reasoning ToS_Arch src/<FILE>.v

# Compile LaTeX paper
cd papers/process_math_v2
export PATH="$PATH:/c/Users/aleks/AppData/Local/Programs/MiKTeX/miktex/bin/x64"
pdflatex -interaction=nonstopmode main.tex
```

## Architecture

### Verification Pipeline
```
Input Question → D1-D6 Domains → Zero-Gate → Weight Calc → Status Machine → Answer
                                    ↓
                  G(e) = gERR ∧ gLevels ∧ gOrder
                                    ↓
                    Gtotal = 0 ⟹ W = 0 (annihilation)
                                    ↓
                         L5-Resolution → PrimaryMax
```

### Process Mathematics Pipeline
```
A = exists → Laws of Logic (L1-L5) → Principles (P1-P4) → RealProcess := nat → Q
    ↓
Classical Analysis (IVT, EVT, Calculus, ODEs, Measure Theory)
    ↓
Physics (Quantum, Gauge Theory, Gravity, Standard Model, Navier-Stokes)
    ↓
Experimental Predictions (sin²θ_W = 3/13, Born = Parseval)
```

## Zero-Gate: The Three Gates

| Gate | Checks | Failure = |
|------|--------|-----------|
| `gERR` | Elements/Roles/Rules all present | Missing structural component |
| `gLevels` | L1-L3 hierarchy valid | Self-reference loop |
| `gOrder` | L5 domain sequence D1→D6 | Domain skipped or out of order |

## Status Machine (Five Statuses)

| Status | Meaning |
|--------|---------|
| PrimaryMax | Unique winner (Gate=1, highest weight, tie-broken by legacy_idx) |
| SecondaryMax | Valid alternative with equal max weight |
| HistoricalMax | Was Primary, now superseded |
| Candidate | Valid but lower weight |
| Invalid | Gate=0, weight forced to 0 |

## Rocq-Proven Invariants (Must Preserve in Python)

1. **Zero-Gate Law:** `G = 0 ⇒ W = 0` — enforced in `apply_zero_gate()`
2. **Uniqueness:** At most one PrimaryMax — enforced in `compare_entities()` with policy tie-break
3. **Stability:** Invalid cannot become PrimaryMax — enforced by gate check before status assignment

## Six Domains (D1→D6, must be traversed in order)

| Domain | Question | Gate Trigger on Skip |
|--------|----------|---------------------|
| D1: Recognition | What is actually here? | Object hallucination |
| D2: Clarification | What exactly is this? | Equivocation |
| D3: Framework | How do we connect? | Category error |
| D4: Comparison | How does it process? | Internal contradiction |
| D5: Inference | What follows? | Non-sequitur |
| D6: Reflection | Where doesn't it work? | Dogmatism |

## Rocq/Coq Conventions

- Rocq 9.0.1 (Coq rebrand) installed at `C:\Coq\Rocq-Platform~9.0~2025.08`
- All .v files use `From ToS Require Import` (not bare `Require Import`)
- NEVER use `[x; y]` list notation with Q values — use `((x:Q) :: (y:Q) :: nil)` or `Qmake`
- `vm_compute. reflexivity.` for concrete Q equalities (not `lra`)
- For True statements: `Proof. exact I. Qed.`
- `repeat split` can consume Qlt goals — use explicit `split. { exact ... }` chains
- Shell is cmd.exe despite "bash" label in tool

## Code Conventions

- Python 3.11+, full type hints, dataclasses for models
- Async/await for LLM calls
- Rich for terminal UI, Typer for CLI
- pytest for testing
- Plain `python` fails with exit code 49 — always use `uv run`

## Development Phases (Complete)

- **Phase 1:** LogicGuard MVP — core types, zero-gate, status machine, engine
- **Phase 2:** LLM integration — Claude/OpenAI clients, sensor, orchestrator
- **Phase 3:** Orchestration — merged into Phase 2
- **Phase 4:** Verified Backend — bridge.py, math_verifier.py, err_validator.py, layers.py
- **Phase 5:** HLE Evaluation — post-hoc eval on 10 HLE Math questions
- **Phase 6:** Fixed-Point Convergence — ReasoningConvergence.v, convergence_advisor.py
- **ToS Phases 1-3:** Extraction, Interval, L5Resolution, SystemMorphism, InfoLayer
- **ToS-Lang Phases A-D:** Type system, operational semantics, verified compiler
- **Physics Phases:** Quantum, lattice gauge, Navier-Stokes, Riemann Hypothesis, Standard Model
- **Process Mathematics (P4):** Analysis, algebra, topology, category theory, measure theory, ODEs

## P3 Agent Pipeline — STRICT PROTOCOL (HLE Evaluation)

> Full details: `tests/HLE/RUN_INSTRUCTIONS.md`. Rules below are **mandatory**.

### Session sizing: MAX 3 questions per session
- At 3 questions (~75-90K tokens) the protocol stays in live context.
- At 5+ questions context compaction starts and Team Lead forgets rules.

### 6 Inviolable Rules

1. **ONE question per pipeline.** Never bundle questions into one subagent.
2. **ONE domain per subagent (SEQUENTIAL).** D1→D2→D3→D4→D5 each a separate subagent. D6 by Team Lead. NEVER combine (e.g. "D1-D5 together" is FORBIDDEN).
3. **Team Lead does NOT pre-solve.** Subagent prompt = domain instruction + question + prior domain outputs ONLY. No reasoning, no candidate answers, no "Actually, I think...".
4. **Wait for output.** D2 cannot start before D1 finishes. Parallel = different questions only.
5. **Gate verification.** After each domain: PASS → next, RETRY → re-run, FAIL → mark LOW_CONFIDENCE.
6. **No contamination.** NEVER read `.judge_only/` or answer files. Every subagent prompt must include: "Do NOT read .judge_only/ or answers/".

### Anti-patterns (cause batch invalidation)
```
BAD: "You are a D1-D6 domain worker. Answer..." → all domains in one call
BAD: "Q01:... Q02:... Q03:..." → multiple questions bundled
BAD: prompt contains "ANSWER: X" → pre-solved by Team Lead
BAD: launching D1,D2,D3 in parallel for same question → sequential dependency
```

## Latest Work: E/R/R Three Formulas Re-derivation (April 2026)

14 new files in `_tos_coq_clone/src/foundation/` totaling **304 Qed**:
- Single systems: SHO, Qubit, Photon, Acoustic chain (4 files, 85 Qed)
- Atomic composition: H, H structure, He, Li, C (5 files, 120 Qed)
- Numerical predictions: Anharmonic, Planck, Apéry zeta(3) (4 files, 66 Qed)
- ThreeFormulasBridge.v: 6 bridges to existing library (33 Qed)

Verifiable predictions (machine-checked rationals):
- sin²θ_W = 3/13 = 0.23077 (PDG: 0.23122, 0.19% match)
- H₂ fundamental 4159 cm⁻¹ (0.05% from 4161)
- Lyman/Balmer = 27/5 (exact rational, 0.06% from 5.397)
- Apéry: 1202/1000 < a₃(zeta3) < 1203/1000
- Periodic table 2, 8, 18, 32 = 2n² (exact from Pauli + SO(4))

## Project Statistics (April 2026)

| Metric | Value |
|--------|-------|
| Rocq theorems (companion) | 21,901 Qed |
| Rocq theorems (local ToS-Coq) | 320 Qed |
| Admitted | 0 |
| Custom axioms | 2 (classic, L4_witness) |
| Rocq files | 1497 |
| Python tests | 1745 |
| Fallacy taxonomy | 156 fallacies |
| LLM providers | 4 (Claude, OpenAI, DeepSeek, ZhipuAI) |
