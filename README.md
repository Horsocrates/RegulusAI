# Regulus AI

**Deterministic reasoning verification for LLMs.**

Regulus is a structured multi-agent system that decomposes LLM reasoning into verifiable steps, checks structural integrity through a formal gate mechanism, and forces correction when hallucination is detected. The core principle: make dishonesty **structurally impossible** through `Gtotal`.

Built on the **Theory of Systems** (ToS) framework with properties formally verified in Coq.

```
Input Question
     |
     v
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
     v
 Verified Answer (with confidence trace)
```

## Architecture

Regulus uses a **two-agent dialogue** architecture:

| Agent | Role | Level |
|-------|------|-------|
| **Team Lead** | Plans, evaluates, assembles. Never solves directly. | L3 (meta-operator) |
| **Worker** | Executes domain tasks, computes, verifies. | L2 (operator) |

The Team Lead guides the Worker through domains D1-D5 sequentially. After each domain, the TL evaluates output quality via a **confidence gate** (minimum 60%). If confidence is below the gate, the system iterates: targeted feedback, then paradigm shift if stagnant.

### Zero-Gate Mechanism

Every reasoning step passes through a three-component binary gate:

| Gate | Checks | Failure means |
|------|--------|---------------|
| `gERR` | Elements, Roles, Rules all present | Missing structural component |
| `gLevels` | L1-L3 hierarchy valid | Self-reference loop |
| `gOrder` | Domain sequence D1-D6 respected | Domain skipped or out of order |

```
Gtotal = gERR AND gLevels AND gOrder

If Gtotal = 0:
  Weight = 0          # Annihilation, not penalty
  Status = Invalid    # Cannot become PrimaryMax
```

This is not a soft penalty. If any gate fails, the weight is forced to zero. This property is **formally proven in Coq** (see `ToS-StatusMachine/`).

### Status Machine

After gate verification, exactly one reasoning path is selected:

| Status | Meaning |
|--------|---------|
| **PrimaryMax** | Unique winner (gate=1, highest weight, tie-broken by legacy index) |
| SecondaryMax | Valid alternative with equal max weight |
| HistoricalMax | Was Primary, now superseded |
| Candidate | Valid but lower weight |
| Invalid | Gate=0, weight forced to 0 |

**Three Coq-proven invariants** enforced at runtime:
1. **Zero-Gate Law:** `G = 0 => W = 0`
2. **Uniqueness:** At most one PrimaryMax
3. **Stability:** Invalid cannot become PrimaryMax

## Pipeline v5

The current production pipeline implements a **framework-first** architecture:

```
D1 (Recognition)
 |
D2 (Clarification + Assumption Register + Hypothesis Completeness Check)
 |
D3 (Multi-step: Enumerate -> Analyze -> Theory Derive -> Select)
 |  [iterates until confidence >= 60%]
 |
D4 (Multi-framework Computation + Python exec verification)
 |
D5 (Cross-verification + Assumption Audit + Sufficient Reason)
 |
Confidence Reconciliation (C_computation vs C_approach)
 |  [if gap > 35pp: return to weakest domain]
 |
Answer Extraction
```

Key features:
- **Adaptive iteration**: each domain iterates until confidence >= 60%, with 3-stage escalation (normal -> feedback -> paradigm shift)
- **Python execution**: Worker has access to a sandboxed Python environment for numerical verification
- **Two-level confidence**: `C_computation` (Worker's numerical result) vs `C_approach` (TL's structural assessment)
- **Gap detection**: if the two confidence levels diverge by >35pp, the system returns to an earlier domain

## Repository Structure

```
RegulusAI/
|
|-- regulus/                    # Core package
|   |-- core/                  # Formal verification layer
|   |   |-- types.py           # Domain, Status, Entity, GateSignals
|   |   |-- zero_gate.py       # Three-component gate check
|   |   |-- weight.py          # W(e) = Gtotal * (struct + domain scores)
|   |   |-- status_machine.py  # L5-Resolution: deterministic winner
|   |   |-- engine.py          # LogicGuardEngine orchestration
|   |   |-- domains.py         # Domain definitions and prompts
|   |   |-- optimizer.py       # Parameter optimization
|   |   +-- gamerules.py       # Game-theoretic rules
|   |
|   |-- llm/                   # LLM integration layer
|   |   |-- client.py          # Base LLM client interface
|   |   |-- claude.py          # Anthropic Claude client
|   |   |-- openai.py          # OpenAI client
|   |   |-- deepseek.py        # DeepSeek client
|   |   |-- sensor.py          # Signal extraction (heuristic + LLM)
|   |   +-- source_verifier.py # Source verification
|   |
|   |-- instructions/          # Domain instruction sets
|   |   |-- default/           # Standard D1-D6 instructions
|   |   +-- _skill/            # Skill-specific variants
|   |
|   |-- orchestrator.py        # Main verification loop
|   |-- cli.py                 # Typer CLI (ask, verify, example)
|   +-- judge.py               # Answer comparison and judging
|
|-- ToS-StatusMachine/         # Formal verification (Coq)
|   |-- ToS_Status_Machine_v8.v    # 492 lines, 14 theorems, 0 admitted
|   |-- tos_status_machine.ml      # OCaml extraction
|   +-- STATUS_MACHINE_SUMMARY.md
|
|-- skills/                    # Domain instruction files (v2/v3)
|   |-- analyze-v2.md          # Team Lead system prompt
|   |-- d1-recognize.md        # D1: Recognition
|   |-- d2-clarify.md          # D2: Clarification
|   |-- d3-framework.md        # D3: Framework Selection
|   |-- d4-compare.md          # D4: Computation & Comparison
|   |-- d5-infer.md            # D5: Inference & Cross-verification
|   |-- d6-ask.md              # D6: Questioning Intelligence
|   |-- d6-reflect.md          # D6: Reflective Intelligence
|   +-- README.md              # Detailed instruction documentation
|
|-- tests/                     # Test suite
|   |-- test_core.py           # Core engine tests (22+)
|   |-- test_v2_pipeline.py    # Full pipeline integration tests
|   |-- test_llm_worker.py     # LLM worker tests
|   |-- test_mas_phase1.py     # Multi-agent system tests
|   +-- HLE/                   # Humanity's Last Exam evaluation
|
|-- web/                       # Regulus Lab (Next.js frontend)
|-- api/                       # FastAPI backend
|-- scripts/                   # Utility scripts
+-- pyproject.toml             # Project configuration
```

## Quick Start

```bash
# Clone
git clone https://github.com/YourOrg/RegulusAI.git
cd RegulusAI

# Install dependencies
uv sync

# Set API key
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Run tests
uv run pytest tests/test_core.py -v

# CLI usage
uv run regulus ask "What is 2+2?" --provider claude -v
uv run regulus verify path/to/reasoning.json
uv run regulus example
```

## HLE Pilot (Research)

The `hle_pilot.py` in the worktree implements the full Pipeline v5 for evaluation on [Humanity's Last Exam](https://arxiv.org/abs/2501.14249):

```bash
# Run on a seed file
uv run python hle_pilot.py hle_seed_math_10q.json

# Debug mode: stop after D3
REGULUS_STOP_AFTER=D3 uv run python hle_pilot.py seed.json
```

Each run produces:
- `dialogue.jsonl` — full agent dialogue with thinking traces
- `conspectus.md` — Team Lead's running analysis
- `report.json` — structured results with timing and token counts

## Six Domains

| Domain | Question | Gate Trigger on Skip |
|--------|----------|---------------------|
| **D1: Recognition** | What is actually here? | Object hallucination |
| **D2: Clarification** | What exactly is this? | Equivocation |
| **D3: Framework** | How do we model this? | Category error |
| **D4: Computation** | What does the math say? | Internal contradiction |
| **D5: Inference** | What follows from this? | Non-sequitur |
| **D6: Reflection** | Where does this break? | Dogmatism |

See [`skills/README.md`](skills/README.md) for detailed documentation of each domain's instruction set.

## Formal Guarantees

The status machine properties are proven in Coq (`ToS-StatusMachine/ToS_Status_Machine_v8.v`):

| Theorem | Statement |
|---------|-----------|
| `zero_gate_law` | If any gate component is false, weight = 0 |
| `primary_unique` | At most one entity has PrimaryMax status |
| `invalid_stable` | An Invalid entity cannot transition to PrimaryMax |
| `weight_positive` | Valid gate implies weight > 0 (given positive scores) |
| `compare_deterministic` | For any two entities, comparison yields a unique winner |

14 theorems, 0 admitted. Full mechanical verification with no axioms beyond Coq's kernel.

## Technology

- **Python 3.11+** with full type hints
- **Anthropic Claude** (primary), OpenAI, DeepSeek (supported)
- **Coq 8.18+** for formal proofs
- **Rich** for terminal UI, **Typer** for CLI
- **FastAPI** + **Next.js** for Lab web interface
- **pytest** for testing

## License

MIT

## Citation

If you use Regulus in research, please cite:

```bibtex
@software{regulus2026,
  title={Regulus AI: Deterministic Reasoning Verification for LLMs},
  author={Horsocrates},
  year={2026},
  url={https://github.com/YourOrg/RegulusAI}
}
```
