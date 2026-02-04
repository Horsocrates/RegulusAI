# Regulus AI — Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** 2026-02-04  
**Author:** Horsocrates (via Opus Technical Lead)  
**Target:** Claude Code (Lead Developer)

---

## 1. Executive Summary

**Regulus AI** is a CLI proxy that provides **deterministic verification** of LLM reasoning in real-time. The system acts as a "Logic Censor" — decomposing reasoning into steps, verifying each step through the **Zero-Gate** (Theory of Systems), and forcing correction when the model attempts to hallucinate.

### Key Value Proposition

> We do not ask AI to be honest.  
> We make dishonesty **structurally impossible** through `Gtotal`.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        REGULUS AI CLI                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Query                                                      │
│      │                                                           │
│      ▼                                                           │
│  ┌──────────────────┐                                            │
│  │   ORCHESTRATOR   │ ◄── Main control loop                      │
│  │  (orchestrator.py)│                                           │
│  └────────┬─────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐      ┌──────────────────┐                  │
│  │   LLM ADAPTER    │ ───► │  SENSOR (LLM)    │                  │
│  │  (llm_client.py) │      │  (sensor_llm.py) │                  │
│  │                  │      │                  │                  │
│  │ • Claude API     │      │ • Extract ERR    │                  │
│  │ • OpenAI API     │      │ • Extract D1-D6  │                  │
│  └──────────────────┘      │ • Gate Signals   │                  │
│                            └────────┬─────────┘                  │
│                                     │                            │
│                                     ▼                            │
│                        ┌──────────────────────┐                  │
│                        │     ZERO-GATE        │                  │
│                        │   (zero_gate.py)     │                  │
│                        │                      │                  │
│                        │ G = ⟨gERR, gLevels,  │                  │
│                        │      gOrder⟩         │                  │
│                        │                      │                  │
│                        │ Gtotal = 0 → REJECT  │                  │
│                        └────────┬─────────────┘                  │
│                                 │                                │
│                    ┌────────────┴────────────┐                   │
│                    │                         │                   │
│                    ▼                         ▼                   │
│            ┌─────────────┐          ┌─────────────────┐          │
│            │  Gate = 1   │          │    Gate = 0     │          │
│            │  (VALID)    │          │   (INVALID)     │          │
│            └──────┬──────┘          └────────┬────────┘          │
│                   │                          │                   │
│                   ▼                          ▼                   │
│          ┌───────────────┐         ┌─────────────────┐           │
│          │ STATUS MACHINE│         │ CORRECTION LOOP │           │
│          │(status_machine│         │                 │           │
│          │      .py)     │         │ Generate fix    │           │
│          │               │         │ prompt → retry  │           │
│          │ PrimaryMax    │         │ (max N times)   │           │
│          │ SecondaryMax  │         └─────────────────┘           │
│          │ Candidate     │                                       │
│          │ Invalid       │                                       │
│          └───────┬───────┘                                       │
│                  │                                               │
│                  ▼                                               │
│         ┌────────────────┐                                       │
│         │      UI        │                                       │
│         │    (ui.py)     │                                       │
│         │                │                                       │
│         │ • Rich tree    │                                       │
│         │ • Status color │                                       │
│         │ • Diagnostics  │                                       │
│         └────────────────┘                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Specifications

### 3.1 Orchestrator Module (`regulus/orchestrator.py`)

**Purpose:** Main control loop managing the verification cycle.

**Interface:**
```python
class Orchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        sensor: SensorLLM,
        gate: ZeroGate,
        status_machine: StatusMachine,
        ui: UI,
        max_corrections: int = 3,
        policy: Policy = Policy.LEGACY_PRIORITY
    ): ...
    
    async def process_query(self, user_query: str) -> VerifiedResponse:
        """
        Main loop:
        1. Send query to LLM
        2. For each reasoning step:
           a. Extract signals via Sensor
           b. Check Zero-Gate
           c. If Gate=0: generate fix prompt, retry
           d. If Gate=1: assign Status, continue
        3. Return PrimaryMax path with diagnostics
        """
        ...
    
    def generate_fix_prompt(self, diagnostic: Diagnostic) -> str:
        """Generate targeted correction based on which gate failed."""
        ...
```

**Verification Cycle:**
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   Query → LLM → Step → Sensor → Gate Check          │
│                                    │                │
│                     ┌──────────────┴──────────────┐ │
│                     │                             │ │
│                     ▼                             ▼ │
│              [Gate = 1]                    [Gate = 0]
│                     │                             │ │
│                     ▼                             ▼ │
│             Status Machine              Fix Prompt │ │
│                     │                             │ │
│                     ▼                             │ │
│               Next Step ◄─────────────────────────┘ │
│                     │                               │
│                     ▼                               │
│              Final Output                           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 3.2 LLM Client Module (`regulus/llm_client.py`)

**Purpose:** Unified interface for multiple LLM providers.

**Interface:**
```python
from enum import Enum
from abc import ABC, abstractmethod

class LLMProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """Generate completion from LLM."""
        ...
    
    @abstractmethod
    async def generate_step(
        self,
        prompt: str,
        domain: Domain
    ) -> ReasoningStep:
        """Generate single reasoning step for specified domain."""
        ...

class ClaudeClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        ...

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        ...

def create_client(provider: LLMProvider, api_key: str) -> LLMClient:
    """Factory function for LLM clients."""
    ...
```

**Supported Models:**
| Provider | Models | Notes |
|----------|--------|-------|
| Claude | claude-sonnet-4-20250514, claude-opus-4-20250514 | Primary |
| OpenAI | gpt-4o, gpt-4o-mini, o1, o1-mini | Secondary |

---

### 3.3 Sensor Module (`regulus/sensor_llm.py`)

**Purpose:** Extract E/R/R and D1-D6 signals from LLM text output.

**Core Concept:** The Sensor is a **Referee LLM** that analyzes reasoning steps and extracts structural signals.

**Interface:**
```python
from dataclasses import dataclass
from enum import Enum

class Domain(Enum):
    D1_RECOGNITION = 1
    D2_CLARIFICATION = 2
    D3_FRAMEWORK_SELECTION = 3
    D4_COMPARISON = 4
    D5_INFERENCE = 5
    D6_REFLECTION = 6

@dataclass
class ERRSignals:
    """Elements/Roles/Rules completeness signals."""
    elements_present: bool      # ЧТО — субстрат идентифицирован
    roles_defined: bool         # КАК — отношения определены
    rules_stated: bool          # ПОЧЕМУ — законы указаны
    
    @property
    def is_complete(self) -> bool:
        return self.elements_present and self.roles_defined and self.rules_stated

@dataclass
class DomainSignals:
    """D1-D6 domain coverage signals."""
    d1_recognition: float       # 0.0-1.0: фиксация присутствующего
    d2_clarification: float     # 0.0-1.0: понимание терминов
    d3_framework: float         # 0.0-1.0: выбор критериев
    d4_comparison: float        # 0.0-1.0: применение фреймворка
    d5_inference: float         # 0.0-1.0: извлечение следствий
    d6_reflection: float        # 0.0-1.0: осознание пределов
    
    @property
    def total_score(self) -> float:
        return sum([
            self.d1_recognition,
            self.d2_clarification,
            self.d3_framework,
            self.d4_comparison,
            self.d5_inference,
            self.d6_reflection
        ])

@dataclass
class LevelSignals:
    """L1-L3 hierarchy signals."""
    no_self_reference: bool     # Нет самоприменения
    levels_respected: bool      # L2 операции только над L1
    no_circular_definition: bool # Нет циклических определений
    
    @property
    def is_valid(self) -> bool:
        return self.no_self_reference and self.levels_respected and self.no_circular_definition

@dataclass  
class OrderSignals:
    """L5 Law of Order signals."""
    sequence_valid: bool        # D1→D2→...→D6 не нарушена
    no_domain_skip: bool        # Домены не пропущены
    
    @property
    def is_valid(self) -> bool:
        return self.sequence_valid and self.no_domain_skip

class SensorLLM:
    """Referee LLM for signal extraction."""
    
    def __init__(self, client: LLMClient):
        self.client = client
        self._system_prompt = self._build_system_prompt()
    
    async def extract_signals(self, reasoning_step: str) -> tuple[ERRSignals, DomainSignals, LevelSignals, OrderSignals]:
        """
        Extract all signals from a reasoning step.
        Uses structured prompting to get consistent JSON output.
        """
        ...
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for Referee LLM."""
        return """You are a Logic Referee analyzing reasoning for structural integrity.

For each reasoning step, extract these signals as JSON:

{
  "err": {
    "elements_present": bool,  // Are the objects of reasoning identified?
    "roles_defined": bool,     // Are relationships between elements defined?
    "rules_stated": bool       // Are governing principles stated?
  },
  "domains": {
    "d1_recognition": 0.0-1.0,    // Was the question/claim fixed?
    "d2_clarification": 0.0-1.0,  // Were key terms clarified?
    "d3_framework": 0.0-1.0,      // Were evaluation criteria chosen?
    "d4_comparison": 0.0-1.0,     // Were relevant comparisons made?
    "d5_inference": 0.0-1.0,      // Do conclusions follow from premises?
    "d6_reflection": 0.0-1.0      // Are limitations acknowledged?
  },
  "levels": {
    "no_self_reference": bool,      // No "this statement" paradoxes
    "levels_respected": bool,       // Operations match their level
    "no_circular_definition": bool  // No A defined by B defined by A
  },
  "order": {
    "sequence_valid": bool,  // Domains traversed in order
    "no_domain_skip": bool   // No domains skipped
  }
}

Be strict. Absence of evidence = false/0.0."""
```

---

### 3.4 Zero-Gate Module (`regulus/zero_gate.py`)

**Purpose:** Deterministic integrity check — if ANY gate fails, weight = 0.

**Mathematical Foundation:**
```
G(e) = ⟨gERR, gLevels, gOrder⟩

Gtotal(e) = gERR ∧ gLevels ∧ gOrder

W(e) = Gtotal(e) · (Sstruct + Sdomain)

If Gtotal = 0 → W = 0 (ANNIHILATION, not penalty)
```

**Interface:**
```python
from dataclasses import dataclass

@dataclass
class IntegrityGate:
    """The three-component verification vector."""
    err_complete: bool      # gERR: E/R/R structure complete
    levels_valid: bool      # gLevels: L1-L3 hierarchy respected
    order_valid: bool       # gOrder: L5 Law of Order satisfied
    
    @property
    def is_valid(self) -> bool:
        """Gtotal = gERR ∧ gLevels ∧ gOrder"""
        return self.err_complete and self.levels_valid and self.order_valid
    
    def failed_gate(self) -> int | None:
        """Return which gate failed (1=ERR, 2=Levels, 3=Order) or None."""
        if not self.err_complete:
            return 1
        if not self.levels_valid:
            return 2
        if not self.order_valid:
            return 3
        return None

class ZeroGate:
    """Zero-Gate mechanism: structural annihilation of invalid reasoning."""
    
    def check(
        self,
        err_signals: ERRSignals,
        level_signals: LevelSignals,
        order_signals: OrderSignals
    ) -> IntegrityGate:
        """
        Construct IntegrityGate from signals.
        """
        return IntegrityGate(
            err_complete=err_signals.is_complete,
            levels_valid=level_signals.is_valid,
            order_valid=order_signals.is_valid
        )
    
    def compute_weight(
        self,
        entity: "Entity",
        gate: IntegrityGate
    ) -> int:
        """
        W(e) = Gtotal · (structure_score + domain_score)
        
        If gate fails → 0 (not reduced, ANNIHILATED)
        """
        if not gate.is_valid:
            return 0
        return entity.structure_score + entity.domain_score
```

**Diagnostic Map:**
| g1 | g2 | g3 | Diagnosis | Action |
|----|----|----|-----------|--------|
| 0 | · | · | ERR Incomplete | Identify missing Elements, Roles, or Rules |
| 1 | 0 | · | Level Confusion | Check for self-reference or hierarchy violation |
| 1 | 1 | 0 | Order Violation | Check sequence D1→D6 and L5 compliance |
| 1 | 1 | 1 | VALID | Proceed to weight comparison |

---

### 3.5 Status Machine Module (`regulus/status_machine.py`)

**Purpose:** Deterministic selection of unique winner via L5-Resolution.

**Status Types:**
| Status | Gate | Weight | Rank | Interpretation |
|--------|------|--------|------|----------------|
| PrimaryMax | 1 | Max | 1st | The ruling reasoning path |
| SecondaryMax | 1 | Max | 2nd+ | Valid alternative (Option B) |
| HistoricalMax | 1 | < Max | Was 1st | Superseded, preserved for audit |
| Candidate | 1 | < Max | Never 1st | Valid but not competitive |
| Invalid | 0 | 0 | N/A | Structural violation (hallucination) |

**Interface:**
```python
from enum import Enum
from dataclasses import dataclass

class Status(Enum):
    PRIMARY_MAX = "PrimaryMax"
    SECONDARY_MAX = "SecondaryMax"
    HISTORICAL_MAX = "HistoricalMax"
    CANDIDATE = "Candidate"
    INVALID = "Invalid"

class Policy(Enum):
    LEGACY_PRIORITY = "legacy"    # Earlier wins ties (default, L5-compliant)
    RECENCY_PRIORITY = "recency"  # Later wins ties (for brainstorming)

@dataclass
class Entity:
    """A reasoning unit to be evaluated."""
    entity_id: int
    legacy_idx: int          # Order of appearance
    structure_score: int     # E/R/R completeness (0-6)
    domain_score: int        # D1-D6 coverage (0-6)
    
    def total_weight(self) -> int:
        return self.structure_score + self.domain_score

@dataclass
class Diagnostic:
    """Explains entity status."""
    entity_id: int
    gate: IntegrityGate
    final_weight: int
    status: Status
    reason: int | None       # Which gate failed

class StatusMachine:
    """L5-Resolution for unique PrimaryMax selection."""
    
    def __init__(self, policy: Policy = Policy.LEGACY_PRIORITY):
        self.policy = policy
    
    def assign_status(
        self,
        entities: list[Entity],
        gates: dict[int, IntegrityGate]  # entity_id -> gate
    ) -> dict[int, Status]:
        """
        Assign status to all entities.
        
        Algorithm:
        1. Filter valid entities (Gate=1)
        2. Find max weight
        3. Among max weight, apply tie-breaker (legacy_idx)
        4. Winner = PrimaryMax
        5. Equal weight, different legacy = SecondaryMax
        6. Was max in prefix = HistoricalMax
        7. Others = Candidate
        8. Gate=0 = Invalid
        """
        ...
    
    def find_primary(
        self,
        entities: list[Entity],
        gates: dict[int, IntegrityGate]
    ) -> Entity | None:
        """Find the unique PrimaryMax entity."""
        ...
    
    def diagnose_all(
        self,
        entities: list[Entity],
        gates: dict[int, IntegrityGate]
    ) -> list[Diagnostic]:
        """Generate diagnostics for all entities."""
        ...
```

**L5-Resolution Logic:**
```
1. FinalWeight = structure_score + domain_score (if Gate=1, else 0)
2. Compare by Weight (DESC)
3. Tie-break by legacy_idx:
   - Legacy_Priority: lower index wins (earliest)
   - Recency_Priority: higher index wins (latest)
4. Equal weight but different legacy → SecondaryMax
5. Was Primary in prefix but surpassed → HistoricalMax
```

---

### 3.6 UI Module (`regulus/ui.py`)

**Purpose:** Rich terminal visualization of reasoning tree.

**Interface:**
```python
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table

class UI:
    """Terminal UI for reasoning visualization."""
    
    def __init__(self):
        self.console = Console()
    
    def display_reasoning_tree(
        self,
        steps: list[ReasoningStep],
        diagnostics: list[Diagnostic]
    ) -> None:
        """
        Display reasoning as a tree with status colors:
        - PrimaryMax: green ✓
        - SecondaryMax: blue ○
        - Candidate: yellow ◇
        - Invalid: red ✗
        """
        ...
    
    def display_diagnostic(self, diagnostic: Diagnostic) -> None:
        """Display single diagnostic with gate details."""
        ...
    
    def display_correction_attempt(
        self,
        attempt: int,
        max_attempts: int,
        fix_prompt: str
    ) -> None:
        """Show correction loop progress."""
        ...
    
    def display_final_result(
        self,
        primary: Entity,
        alternatives: list[Entity]
    ) -> None:
        """
        Show final output:
        - Primary conclusion
        - "Alternative B has equal confidence" (if SecondaryMax exists)
        - Gate status summary
        """
        ...
```

**Visual Example:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Regulus AI — Verified Reasoning                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Query: "Is P=NP solvable?"                                     │
│                                                                 │
│  Reasoning Tree:                                                │
│  ├── [D1] Recognition ✓                                         │
│  │   └── "The question asks about decidability of P=NP"         │
│  ├── [D2] Clarification ✓                                       │
│  │   └── "P = problems solvable in polynomial time..."          │
│  ├── [D3] Framework ✓                                           │
│  │   └── "Using computational complexity theory..."             │
│  ├── [D4] Comparison ✓                                          │
│  │   └── "Similar to Halting Problem in undecidability..."      │
│  ├── [D5] Inference ✓                                           │
│  │   └── "Current evidence suggests independence possible"      │
│  └── [D6] Reflection ✓                                          │
│       └── "Limitation: no proof either way exists"              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Status: PrimaryMax                     Weight: 12/12    │    │
│  │ Gate: [ERR: ✓] [Levels: ✓] [Order: ✓]  Gtotal: 1       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  Conclusion: The P=NP problem remains open. Current evidence    │
│  suggests it may be independent of ZFC, similar to CH.          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Models

### 4.1 Core Types (`regulus/models.py`)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime

@dataclass
class ReasoningStep:
    """Single step in reasoning chain."""
    step_id: int
    domain: Domain
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Populated after sensor analysis
    err_signals: Optional[ERRSignals] = None
    domain_signals: Optional[DomainSignals] = None
    level_signals: Optional[LevelSignals] = None
    order_signals: Optional[OrderSignals] = None

@dataclass
class ReasoningChain:
    """Complete reasoning chain with all steps."""
    chain_id: str
    query: str
    steps: list[ReasoningStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class VerifiedResponse:
    """Final verified response with diagnostics."""
    chain: ReasoningChain
    primary: Entity
    alternatives: list[Entity]
    diagnostics: list[Diagnostic]
    total_corrections: int
    
    @property
    def is_valid(self) -> bool:
        return self.primary is not None

@dataclass
class CorrectionAttempt:
    """Record of a correction attempt."""
    attempt_number: int
    original_step: ReasoningStep
    fix_prompt: str
    corrected_step: Optional[ReasoningStep]
    success: bool
```

---

## 5. Project Structure

```
regulus/
├── __init__.py
├── __main__.py              # CLI entry point
├── cli.py                   # Click/Typer CLI commands
│
├── core/
│   ├── __init__.py
│   ├── orchestrator.py      # Main control loop
│   ├── zero_gate.py         # Zero-Gate mechanism
│   ├── status_machine.py    # L5-Resolution
│   └── models.py            # Data models
│
├── llm/
│   ├── __init__.py
│   ├── client.py            # Base LLM client
│   ├── claude.py            # Claude API adapter
│   ├── openai.py            # OpenAI API adapter
│   └── sensor.py            # Referee LLM sensor
│
├── ui/
│   ├── __init__.py
│   ├── console.py           # Rich console UI
│   └── tree.py              # Reasoning tree renderer
│
├── prompts/
│   ├── __init__.py
│   ├── sensor.py            # Sensor system prompts
│   ├── correction.py        # Correction fix prompts
│   └── cot.py               # Chain-of-thought templates
│
└── utils/
    ├── __init__.py
    ├── config.py            # Configuration management
    └── logging.py           # Structured logging

tests/
├── __init__.py
├── test_zero_gate.py
├── test_status_machine.py
├── test_sensor.py
└── test_orchestrator.py

pyproject.toml
README.md
CLAUDE.md                    # Context for Claude Code
```

---

## 6. Dependencies

```toml
[project]
name = "regulus-ai"
version = "0.1.0"
description = "Deterministic LLM reasoning verification"
requires-python = ">=3.11"

dependencies = [
    "anthropic>=0.40.0",      # Claude API
    "openai>=1.50.0",         # OpenAI API
    "rich>=13.0.0",           # Terminal UI
    "typer>=0.12.0",          # CLI framework
    "pydantic>=2.0.0",        # Data validation
    "httpx>=0.27.0",          # Async HTTP
    "python-dotenv>=1.0.0",   # Environment management
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.8.0",
    "ruff>=0.4.0",
]
```

---

## 7. CLI Interface

```bash
# Basic usage
regulus "Is climate change caused by humans?"

# With provider selection
regulus --provider claude "Explain quantum entanglement"
regulus --provider openai "What is the P=NP problem?"

# With policy selection
regulus --policy legacy "Compare Python vs Rust"
regulus --policy recency "Brainstorm startup ideas"

# Verbose mode (show reasoning tree)
regulus -v "Is democracy the best system?"

# Debug mode (show all diagnostics)
regulus --debug "Prove 1+1=2"

# Non-interactive (JSON output)
regulus --json "Summarize this text: ..."
```

---

## 8. Configuration

**Environment Variables:**
```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional
REGULUS_DEFAULT_PROVIDER=claude
REGULUS_DEFAULT_MODEL=claude-sonnet-4-20250514
REGULUS_MAX_CORRECTIONS=3
REGULUS_POLICY=legacy
```

**Config File (`~/.regulus/config.toml`):**
```toml
[llm]
default_provider = "claude"
default_model = "claude-sonnet-4-20250514"
temperature = 0.7
max_tokens = 2048

[verification]
max_corrections = 3
policy = "legacy"

[ui]
show_tree = true
color = true
```

---

## 9. Fix Prompt Templates

When a gate fails, generate targeted correction:

```python
FIX_PROMPTS = {
    1: """Error: Missing E/R/R structure.

Your reasoning lacks complete structure. Please identify:
1. ELEMENTS (What): What objects/concepts are being reasoned about?
2. ROLES (How): How do these elements relate to each other?
3. RULES (Why): What principles govern these relationships?

Restate your reasoning with explicit E/R/R structure.""",

    2: """Error: Level confusion detected.

Your reasoning contains a hierarchical violation:
- L1 = Objects and statements
- L2 = Operations on objects (truth-evaluation, membership)
- L3 = Operations on operations (meta-logic)

Operations at level N can only apply to level N-1.
Check for self-referential statements or circular definitions.

Restate your reasoning with correct level separation.""",

    3: """Error: Domain sequence violation.

Reasoning must traverse domains in order:
D1 (Recognition) → D2 (Clarification) → D3 (Framework) →
D4 (Comparison) → D5 (Inference) → D6 (Reflection)

You appear to have skipped or inverted domains.
Which domain was violated: {violated_domain}

Restate your reasoning following the correct sequence."""
}
```

---

## 10. Verified Properties (from Coq)

The Status Machine guarantees these **machine-proven** properties:

| Theorem | Statement | Coq Status |
|---------|-----------|------------|
| `zero_gate_zero_weight` | Gate=0 → Weight=0 | ✓ Qed |
| `uniqueness_at_most_one_primary` | \|{e : PrimaryMax}\| ≤ 1 | ✓ Qed |
| `stability_invalid_cannot_win` | Invalid ↛ PrimaryMax | ✓ Qed |
| `invalid_means_gate_failed` | Invalid → gate identifiable | ✓ Qed |

These are not conjectures — they are **machine-checked proofs** extractable to production code.

---

## 11. Testing Strategy

### Unit Tests
```python
# test_zero_gate.py
def test_zero_gate_annihilates():
    """Gate=0 → Weight=0, not just reduced."""
    gate = IntegrityGate(err_complete=False, levels_valid=True, order_valid=True)
    entity = Entity(id=1, legacy_idx=0, structure_score=5, domain_score=5)
    
    weight = ZeroGate().compute_weight(entity, gate)
    
    assert weight == 0  # ANNIHILATED, not 10

def test_failed_gate_diagnostic():
    """Correct gate identified when failed."""
    gate = IntegrityGate(err_complete=True, levels_valid=False, order_valid=True)
    
    assert gate.failed_gate() == 2  # Levels failed
```

### Integration Tests
```python
# test_orchestrator.py
async def test_correction_loop():
    """Invalid reasoning triggers correction, not acceptance."""
    orchestrator = Orchestrator(...)
    
    # Query that typically produces D5 violation
    response = await orchestrator.process_query(
        "The moon is made of cheese because I like cheese."
    )
    
    assert response.total_corrections > 0
    assert response.is_valid  # Eventually corrected
```

---

## 12. Development Phases

### Phase 1: Core (Week 1)
- [ ] `models.py` — Data structures
- [ ] `zero_gate.py` — Gate implementation
- [ ] `status_machine.py` — Status assignment
- [ ] Unit tests for core

### Phase 2: LLM Integration (Week 2)
- [ ] `llm/client.py` — Base client
- [ ] `llm/claude.py` — Claude adapter
- [ ] `llm/openai.py` — OpenAI adapter
- [ ] `llm/sensor.py` — Referee LLM

### Phase 3: Orchestration (Week 3)
- [ ] `orchestrator.py` — Main loop
- [ ] Correction loop
- [ ] Fix prompt generation
- [ ] Integration tests

### Phase 4: UI & CLI (Week 4)
- [ ] `ui/console.py` — Rich UI
- [ ] `cli.py` — Typer CLI
- [ ] Configuration
- [ ] Documentation

---

## 13. Success Criteria

1. **Zero-Gate Property:** Any structurally invalid reasoning receives weight=0
2. **Uniqueness:** Exactly one PrimaryMax per query
3. **Correction Loop:** At least 80% of initially-invalid reasoning corrected within 3 attempts
4. **Latency:** < 5s for simple queries, < 15s with corrections
5. **Coverage:** D1-D6 domain signals extracted with > 90% accuracy

---

## 14. CLAUDE.md (For Claude Code)

```markdown
# Regulus AI — Project Context

## What is this?
Regulus AI is a CLI that verifies LLM reasoning through the Theory of Systems.
Core mechanism: Zero-Gate — if structural integrity fails, weight = 0.

## Key Files
- `REGULUS_CLI_SPEC.md` — This specification (READ FIRST)
- `regulus/core/zero_gate.py` — Zero-Gate implementation
- `regulus/core/status_machine.py` — L5-Resolution

## Architecture
1. User query → LLM generates reasoning steps
2. Sensor extracts E/R/R and D1-D6 signals
3. Zero-Gate checks structural integrity
4. Gate=0 → correction loop; Gate=1 → Status Machine
5. PrimaryMax = final output

## Verified Properties (Coq-proven)
- Gate=0 → Weight=0 (annihilation)
- Exactly one PrimaryMax
- Invalid cannot become Primary

## Commands
- `uv run regulus "query"` — Run verification
- `uv run pytest` — Run tests
- `uv run mypy regulus/` — Type check

## Philosophy
We don't ask AI to be honest.
We make dishonesty structurally impossible.
```

---

*Document prepared by Opus (Technical Lead) for Claude Code (Lead Developer)*  
*Theory of Systems — Regulus AI Project*
