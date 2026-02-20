"""
Regulus AI - MAS Domain Contracts
==================================

Input/output type definitions for D1-D6 domain workers.
Phase 2: types match what LLM prompts produce and consume.
"""

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Base Input
# ============================================================

@dataclass
class DomainInput:
    """Base input for all domain workers."""
    query: str = ""
    goal: str = ""
    component_id: str = ""
    component_description: str = ""
    prior_domains: dict = field(default_factory=dict)


# ============================================================
# D1: Recognition
# ============================================================

@dataclass
class D1Input(DomainInput):
    pass


@dataclass
class D1Output:
    components: list = field(default_factory=list)  # list of component dicts
    task_type: str = ""  # factual | analytical | evaluative | creative | procedural
    skill_type: str = ""  # decomposition | verification | recall | computation | conceptual
    skill_confidence: float = 0.0
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# D2: Clarification
# ============================================================

@dataclass
class D2Input(DomainInput):
    components: list = field(default_factory=list)  # from D1Output.components


@dataclass
class D2Output:
    components: list = field(default_factory=list)  # enriched with definitions
    hidden_assumptions: list = field(default_factory=list)
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# D3: Framework Selection
# ============================================================

@dataclass
class D3Input(DomainInput):
    components: list = field(default_factory=list)  # from D2Output.components


@dataclass
class D3Output:
    framework: dict = field(default_factory=dict)
    objectivity: dict = field(default_factory=dict)
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# D4: Comparison / Calculation
# ============================================================

@dataclass
class D4Input(DomainInput):
    components: list = field(default_factory=list)
    framework: dict = field(default_factory=dict)  # from D3Output.framework


@dataclass
class D4Output:
    comparisons: list = field(default_factory=list)
    aristotle_check: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# D5: Inference
# ============================================================

@dataclass
class D5Input(DomainInput):
    comparisons: list = field(default_factory=list)  # from D4Output.comparisons
    framework: dict = field(default_factory=dict)  # from D3Output.framework


@dataclass
class D5Output:
    conclusion: dict = field(default_factory=dict)
    answer: str = ""
    certainty_type: str = ""  # necessary | probabilistic | evaluative
    logical_form: str = ""
    overreach_check: str = ""
    avoidance_check: str = ""
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# D6: Reflection
# ============================================================

@dataclass
class D6Input(DomainInput):
    conclusion: dict = field(default_factory=dict)  # from D5Output.conclusion
    table_summary: str = ""


@dataclass
class D6Output:
    scope: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    new_questions: list = field(default_factory=list)
    return_assessment: dict = field(default_factory=dict)
    content: str = ""
    internal_log: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ============================================================
# Type Mappings
# ============================================================

DOMAIN_INPUT_TYPES = {
    "D1": D1Input,
    "D2": D2Input,
    "D3": D3Input,
    "D4": D4Input,
    "D5": D5Input,
    "D6": D6Input,
}

DOMAIN_OUTPUT_TYPES = {
    "D1": D1Output,
    "D2": D2Output,
    "D3": D3Output,
    "D4": D4Output,
    "D5": D5Output,
    "D6": D6Output,
}
