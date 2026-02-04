# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Regulus AI is a deterministic reasoning verification system for LLMs implementing the Theory of Systems framework. It acts as a "Logic Censor" — decomposing LLM reasoning into steps, verifying structural integrity through the Zero-Gate mechanism, and forcing correction on hallucination attempts. The core principle: make dishonesty structurally impossible through `Gtotal`.

## Repository Layout

```
RegulusAI/
├── CLAUDE.md                        # This file
├── REGULUS_CLI_SPEC.md              # Full PRD specification (read for detailed module specs)
├── REGULUS_STARTUP_INSTRUCTIONS.md  # Phase roadmap (Russian)
├── ToS-StatusMachine/               # Formal verification sources (reference)
│   ├── ToS_Status_Machine_v8.v      # Coq proofs of status machine properties
│   ├── tos_status_machine.ml        # OCaml extraction (ported to Python in LogicGuard)
│   └── STATUS_MACHINE_SUMMARY.md    # Summary of formal properties
└── LogicGuard/                      # MVP implementation (all source lives here)
    ├── types.py                     # Core data types (Domain, Status, Node, GateSignals, etc.)
    ├── zero_gate.py                 # Zero-Gate verification (3-component gate check)
    ├── status_machine.py            # L5-Resolution: deterministic winner selection
    ├── engine.py                    # Main LogicGuardEngine orchestration
    ├── sensor.py                    # Signal extraction + paradox examples
    ├── visualization.py             # ASCII/Graphviz tree rendering
    ├── paradox_demo.py              # Runnable paradox demonstrations
    ├── test_engine.py               # 22+ tests (pytest)
    └── sample_reasoning.json        # Example verification input
```

## Commands

```bash
# Run tests (from project root)
PYTHONPATH=. pytest LogicGuard/test_engine.py -v

# Run a single test
PYTHONPATH=. pytest LogicGuard/test_engine.py -v -k "test_name"

# Run built-in example
python -m logicguard.engine --example

# Verify a JSON file
python -m logicguard.engine path/to/reasoning.json

# Type check (when regulus/ structure is set up)
uv run mypy regulus/

# Dependencies (for future regulus/ package)
uv add anthropic openai rich typer pydantic httpx python-dotenv
```

## Architecture

```
Input JSON → Parse Nodes → Zero-Gate → Weight Calc → Status Machine → Diagnostics
                             ↓
            G(e) = ⟨gERR, gLevels, gOrder⟩
                             ↓
              Gtotal = gERR ∧ gLevels ∧ gOrder
                             ↓
            W(e) = Gtotal × (S_struct + S_domain)
                             ↓
                   L5-Resolution → PrimaryMax
```

**Verification pipeline:**
1. **Sensor** extracts E/R/R (Elements/Roles/Rules) + domain signals from LLM reasoning
2. **Zero-Gate** checks structural integrity via three binary gates — if ANY gate = 0, weight = 0 (annihilation, not penalty)
3. **Weight calculation:** `W(e) = Gtotal × (struct_points + current_domain × 10 + domain_points)`
4. **Status Machine** assigns exactly one PrimaryMax using weight comparison + legacy_idx tie-breaking
5. On gate failure: correction loop generates fix prompt and retries (max N attempts)

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

## Coq-Proven Properties (Must Preserve in Python)

These three invariants are verified at runtime and must never be broken:

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

## Code Conventions

- Python 3.11+, full type hints, dataclasses for models
- Async/await for LLM calls
- Rich for terminal UI, Typer for CLI
- pytest for testing

## Development Phases

- **Phase 1 (Complete):** LogicGuard MVP — core types, zero-gate, status machine, engine, 22+ tests
- **Phase 2 (Planned):** LLM integration — Claude/OpenAI clients, SensorLLM for real signal extraction
- **Phase 3 (Planned):** Orchestrator — main CLI loop, correction logic, fix prompt generation
- **Phase 4 (Planned):** UI & polish — Rich terminal output, Typer CLI, config management

The target directory structure for the full Regulus package is specified in Section 5 of `REGULUS_CLI_SPEC.md`.
