# LogicGuard MVP

> **Machine-Verified Reasoning Verification for Large Language Models**

Based on Article 8: "The Structural Guardrail" from the Theory of Systems.

## The Central Thesis

```
Hallucination is not a failure of fact-checking.
Hallucination is a failure of structural integrity.

We do not ask AI to be honest.
We make dishonesty physically impossible through G_total.
```

## Quick Start

```python
from logicguard import LogicGuardEngine, verify_reasoning

# Load reasoning tree
tree = {
    "reasoning_tree": [
        {
            "node_id": "root",
            "parent_id": None,
            "entity_id": "E_100",
            "content": "Problem statement",
            "legacy_idx": 0,
            "gate_signals": {
                "e_exists": True, "r_exists": True, "rule_exists": True,
                "l1_l3_ok": True, "l5_ok": True
            },
            "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
        }
    ]
}

# Verify
result = verify_reasoning(tree)
print(result.summary())
```

## Architecture

```
Input JSON → Parse Nodes → Zero-Gate → Weight Calc → Status Machine → Diagnostics
                             ↓
            G(e) = ⟨g_ERR, g_Levels, g_Order⟩
                             ↓
              G_total = g₁ ∧ g₂ ∧ g₃
                             ↓
            W(e) = G_total × (S_struct + S_domain)
                             ↓
                   L5-Resolution → PrimaryMax
```

## Key Components

### Zero-Gate Mechanism

If ANY gate fails, weight is **ANNIHILATED** (not reduced):

| Gate | Check | Trigger |
|------|-------|---------|
| g_ERR | E/R/R complete | Missing Element/Role/Rule |
| g_Levels | L1-L3 valid | Self-reference loop |
| g_Order | L5 respected | D1→D6 sequence violation |

### Status Machine

| Status | Gate | Weight | Meaning |
|--------|------|--------|---------|
| **PrimaryMax** | 1 | Max | The winning reasoning path |
| **SecondaryMax** | 1 | Max | Valid alternative (tie) |
| **HistoricalMax** | 1 | <Max | Superseded version |
| **Candidate** | 1 | <Max | Valid but not maximum |
| **Invalid** | 0 | 0 | Structural violation |

### Verified Properties (from Coq)

All properties are runtime-verified:

- **Zero-Gate Law**: `G = 0 ⇒ W = 0`
- **Uniqueness**: `|{e : PrimaryMax}| ≤ 1`
- **Stability**: Invalid cannot become PrimaryMax

## JSON Input Format

```json
{
  "reasoning_tree": [
    {
      "node_id": "unique_id",
      "parent_id": "parent_node_id_or_null",
      "entity_id": "logical_entity_id",
      "content": "Human-readable description",
      "legacy_idx": 0,
      "gate_signals": {
        "e_exists": true,
        "r_exists": true,
        "rule_exists": true,
        "l1_l3_ok": true,
        "l5_ok": true
      },
      "raw_scores": {
        "struct_points": 10,
        "domain_points": 8,
        "current_domain": 1
      }
    }
  ]
}
```

### Gate Signals

| Signal | Type | Description |
|--------|------|-------------|
| `e_exists` | bool | Element (E) is present and identifiable |
| `r_exists` | bool | Role (R) is defined and functional |
| `rule_exists` | bool | Rule connecting roles is specified |
| `l1_l3_ok` | bool | L1-L3 hierarchy respected |
| `l5_ok` | bool | L5 sequence D1→D6 respected |

### Raw Scores

| Score | Type | Description |
|-------|------|-------------|
| `struct_points` | int | E/R/R completeness points |
| `domain_points` | int | Quality score within domain |
| `current_domain` | int | Domain index (1-6) |

## Weight Formula

```
S_struct = struct_points
S_domain = current_domain × 10 + domain_points
W = G_total × (S_struct + S_domain)
```

## Six Domains (D1-D6)

| Domain | Question | Zero-Gate Trigger |
|--------|----------|-------------------|
| D1 | What is actually here? | Object hallucination |
| D2 | What exactly is this? | Equivocation |
| D3 | How do we connect? | Category error |
| D4 | How does it process? | Internal contradiction |
| D5 | What follows? | Non-sequitur |
| D6 | Where doesn't it work? | Dogmatism |

## Running Tests

```bash
cd /path/to/project
PYTHONPATH=. pytest logicguard/tests/test_engine.py -v
```

## CLI Usage

```bash
# Run built-in example
python -m logicguard.engine --example

# Verify JSON file
python -m logicguard.engine path/to/reasoning.json
```

## Project Structure

```
logicguard/
├── __init__.py           # Package exports
├── engine.py             # Main LogicGuardEngine
├── core/
│   ├── types.py          # Domain, Status, Node, etc.
│   ├── zero_gate.py      # G_total computation
│   ├── weight.py         # S_struct + S_domain
│   └── status_machine.py # L5-Resolution
├── tests/
│   └── test_engine.py    # 22 passing tests
└── examples/
    └── sample_reasoning.json
```

## Philosophical Foundation

From Article 8 "The Structural Guardrail":

> **The Paradigm Shift**: Traditional AI safety asks: "How do we train AI to be honest?"
> 
> The Structural Guardrail asks: "How do we make dishonesty *structurally impossible*?"

This MVP implements that principle through:

1. **Zero-Gate**: Binary structural check (pass/fail, no middle ground)
2. **Status Machine**: Deterministic selection via L5 (Law of Order)
3. **Diagnostic Map**: Pinpoints exactly which gate failed

## License

MIT

## Author

Horsocrates (Theory of Systems project)

---

*"Hallucination is a structural null, not a factual error."*
