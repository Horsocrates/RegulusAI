"""
LogicGuard MVP - Core Types
===========================

Based on Article 8: Structural Guardrail and ToS_Status_Machine_v8.v

The Structural Trinity (ERR):
- Element (E): The body of thought - concrete identifiable object
- Role (R): The vector of thought - functional purpose  
- Rule: The law of connection - logical operator binding roles

Six Domains (D1-D6):
- D1: Recognition - What is actually here?
- D2: Clarification - What exactly is this?
- D3: Modeling - How do we connect this?
- D4: Calculation - How does the process work?
- D5: Inference - What follows from this?
- D6: Reflection - Where does this not work?

Five Statuses:
- PrimaryMax: The unique winner
- SecondaryMax: Valid alternative with equal weight
- HistoricalMax: Was Primary, now superseded
- Candidate: Valid but not maximum
- Invalid: Gate = 0 (hallucination)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class Domain(Enum):
    """Six Domains of Reasoning (D1-D6)"""
    D1_RECOGNITION = 1      # What is actually here?
    D2_CLARIFICATION = 2    # What exactly is this?
    D3_MODELING = 3         # How do we connect this?
    D4_CALCULATION = 4      # How does the process work?
    D5_INFERENCE = 5        # What follows from this?
    D6_REFLECTION = 6       # Where does this not work?
    
    @property
    def question(self) -> str:
        """Return the guiding question for this domain"""
        questions = {
            Domain.D1_RECOGNITION: "What is actually here?",
            Domain.D2_CLARIFICATION: "What exactly is this?",
            Domain.D3_MODELING: "How do we connect this?",
            Domain.D4_CALCULATION: "How does the process work?",
            Domain.D5_INFERENCE: "What follows from this?",
            Domain.D6_REFLECTION: "Where does this not work?"
        }
        return questions[self]
    
    @property
    def zero_gate_trigger(self) -> str:
        """Return the Zero-Gate trigger condition for this domain"""
        triggers = {
            Domain.D1_RECOGNITION: "Object hallucination, context ignored",
            Domain.D2_CLARIFICATION: "Equivocation, blurred boundaries",
            Domain.D3_MODELING: "Categorical error, incompatible model",
            Domain.D4_CALCULATION: "Internal contradiction within step",
            Domain.D5_INFERENCE: "Non-sequitur, logical jump",
            Domain.D6_REFLECTION: "Dogmatism, ignoring limits"
        }
        return triggers[self]


class Status(Enum):
    """Entity status in the Status Machine"""
    PRIMARY_MAX = auto()    # The unique winner
    SECONDARY_MAX = auto()  # Valid alternative with equal weight
    HISTORICAL_MAX = auto() # Was Primary, now superseded
    CANDIDATE = auto()      # Valid but not maximum
    INVALID = auto()        # Gate = 0 (structural violation)


class Policy(Enum):
    """Tie-breaking policy for L5-Resolution"""
    LEGACY_PRIORITY = auto()   # Earlier wins ties (default L5)
    RECENCY_PRIORITY = auto()  # Later wins ties


@dataclass
class GateSignals:
    """
    Input signals for Zero-Gate verification.
    These are provided by external NLP/classification layer.
    
    ERR Components:
    - e_exists: Element is present and identifiable
    - r_exists: Role is defined and functional
    - rule_exists: Rule connecting roles is specified
    
    Level Hierarchy (L1-L3):
    - l1_l3_ok: No hierarchical loops, levels respected
    
    Law of Order (L5):
    - l5_ok: Sequence D1→D6 respected, no logical jumps
    """
    e_exists: bool = False
    r_exists: bool = False
    rule_exists: bool = False
    l1_l3_ok: bool = True
    l5_ok: bool = True
    
    def to_dict(self) -> Dict[str, bool]:
        return {
            "e_exists": self.e_exists,
            "r_exists": self.r_exists,
            "rule_exists": self.rule_exists,
            "l1_l3_ok": self.l1_l3_ok,
            "l5_ok": self.l5_ok
        }


@dataclass
class RawScores:
    """
    Raw scoring inputs for weight calculation.
    
    struct_points: Points for E/R/R completeness (sum of component scores)
    domain_points: Quality score within current domain
    current_domain: Which domain (1-6) this node operates in
    """
    struct_points: int = 0
    domain_points: int = 0
    current_domain: int = 1
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "struct_points": self.struct_points,
            "domain_points": self.domain_points,
            "current_domain": self.current_domain
        }


@dataclass
class IntegrityGate:
    """
    The Zero-Gate: G(e) = ⟨g_ERR, g_Levels, g_Order⟩
    
    If ANY gate is False, total weight = 0 (annihilation, not penalty)
    """
    err_complete: bool = False   # E/R/R structure complete
    levels_valid: bool = False   # L1-L3: No hierarchical loops
    order_valid: bool = False    # L5: Law of Order respected
    
    @property
    def is_valid(self) -> bool:
        """G_total = g_ERR ∧ g_Levels ∧ g_Order"""
        return self.err_complete and self.levels_valid and self.order_valid
    
    def to_vector(self) -> List[bool]:
        """Return gate as boolean vector [g1, g2, g3]"""
        return [self.err_complete, self.levels_valid, self.order_valid]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ERR": "OK" if self.err_complete else "FAIL",
            "Levels": "OK" if self.levels_valid else "FAIL", 
            "Order": "OK" if self.order_valid else "FAIL",
            "G_total": self.is_valid
        }


@dataclass
class Node:
    """
    A reasoning node in the tree.
    
    Attributes:
        node_id: Unique identifier for this node
        parent_id: ID of parent node (None for root)
        entity_id: Logical entity this node represents (for refinement tracking)
        content: Human-readable description of the reasoning step
        legacy_idx: Order of creation (for L5 tie-breaking)
        gate_signals: Input signals for Zero-Gate
        raw_scores: Input scores for weight calculation
    """
    node_id: str
    parent_id: Optional[str]
    entity_id: str
    content: str
    legacy_idx: int
    gate_signals: GateSignals
    raw_scores: RawScores
    
    # Computed fields (set by engine)
    gate: Optional[IntegrityGate] = None
    final_weight: int = 0
    status: Status = Status.INVALID
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """Create Node from JSON dictionary"""
        gate_signals = GateSignals(**data.get("gate_signals", {}))
        raw_scores = RawScores(**data.get("raw_scores", {}))
        
        return cls(
            node_id=data["node_id"],
            parent_id=data.get("parent_id"),
            entity_id=data["entity_id"],
            content=data.get("content", ""),
            legacy_idx=data.get("legacy_idx", 0),
            gate_signals=gate_signals,
            raw_scores=raw_scores
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary"""
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "entity_id": self.entity_id,
            "content": self.content,
            "legacy_idx": self.legacy_idx,
            "gate_signals": self.gate_signals.to_dict(),
            "raw_scores": self.raw_scores.to_dict(),
            "gate": self.gate.to_dict() if self.gate else None,
            "final_weight": self.final_weight,
            "status": self.status.name
        }


@dataclass
class Diagnostic:
    """
    Diagnostic Map for a node - the system's verdict with explanation.
    
    Provides:
    - Status verdict
    - Gate vector (which gates passed/failed)
    - Diagnostic code (e.g., ERR_D2 = failure at clarification)
    - Human-readable reason
    """
    node_id: str
    entity_id: str
    status: Status
    gate_vector: Dict[str, str]  # {"ERR": "OK/FAIL", "Levels": "OK/FAIL", "Order": "OK/FAIL"}
    final_weight: int
    diagnostic_code: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "entity_id": self.entity_id,
            "status": self.status.name,
            "gate_vector": self.gate_vector,
            "final_weight": self.final_weight,
            "diagnostic_code": self.diagnostic_code,
            "reason": self.reason
        }
    
    def __str__(self) -> str:
        status_icon = "✓" if self.status != Status.INVALID else "✗"
        return (
            f"[{status_icon}] {self.node_id} ({self.entity_id})\n"
            f"    Status: {self.status.name}\n"
            f"    Gate: {self.gate_vector}\n"
            f"    Weight: {self.final_weight}\n"
            f"    Code: {self.diagnostic_code or 'N/A'}\n"
            f"    Reason: {self.reason or 'N/A'}"
        )


@dataclass
class VerificationResult:
    """
    Complete result of reasoning tree verification.
    """
    nodes: List[Node]
    diagnostics: List[Diagnostic]
    primary_max: Optional[Node] = None
    secondary_max: List[Node] = field(default_factory=list)
    historical_max: List[Node] = field(default_factory=list)
    invalid_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_max": self.primary_max.node_id if self.primary_max else None,
            "secondary_max": [n.node_id for n in self.secondary_max],
            "historical_max": [n.node_id for n in self.historical_max],
            "invalid_count": self.invalid_count,
            "diagnostics": [d.to_dict() for d in self.diagnostics]
        }
    
    def summary(self) -> str:
        """Human-readable summary"""
        lines = [
            "=" * 50,
            "LOGICGUARD VERIFICATION RESULT",
            "=" * 50,
            f"Total nodes: {len(self.nodes)}",
            f"Invalid: {self.invalid_count}",
            f"Primary: {self.primary_max.node_id if self.primary_max else 'None'}",
            f"Secondary: {[n.node_id for n in self.secondary_max]}",
            f"Historical: {[n.node_id for n in self.historical_max]}",
            "-" * 50,
            "DIAGNOSTICS:",
        ]
        for d in self.diagnostics:
            lines.append(str(d))
            lines.append("-" * 30)
        return "\n".join(lines)
