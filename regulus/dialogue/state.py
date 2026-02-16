"""
Regulus AI - Dialogue Run State
================================

Tracks the state of a dialogue run: per-domain status, convergence,
worker instances, and token usage. Persisted as state.json in the run dir.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class DomainState:
    """State of a single domain within a run."""
    status: str = "pending"         # pending | running | complete | failed
    confidence: Optional[int] = None
    iterations: int = 0


@dataclass
class ConvergenceState:
    """Convergence tracking across the dialogue."""
    iteration: int = 0
    confidence_history: list[int] = field(default_factory=list)
    paradigm_shifts_used: int = 0
    paradigm_history: list[str] = field(default_factory=list)
    stall_count: int = 0


@dataclass
class WorkerState:
    """Worker instance tracking."""
    current_instance: int = 1
    total_spawned: int = 1


@dataclass
class TokenState:
    """Per-agent token usage."""
    team_lead_input: int = 0
    team_lead_output: int = 0
    worker_input: int = 0
    worker_output: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.team_lead_input + self.team_lead_output
            + self.worker_input + self.worker_output
        )


@dataclass
class RunState:
    """Complete state of a dialogue run."""
    run_id: str = ""
    question: str = ""
    profile: str = "standard"
    status: str = "created"     # created | running | completed | failed
    domains: dict[str, DomainState] = field(default_factory=dict)
    convergence: ConvergenceState = field(default_factory=ConvergenceState)
    workers: WorkerState = field(default_factory=WorkerState)
    tokens: TokenState = field(default_factory=TokenState)

    def init_domains(self) -> None:
        """Initialize D1-D5 domain states as pending."""
        for d in ["D1", "D2", "D3", "D4", "D5"]:
            self.domains[d] = DomainState()

    def update_domain(
        self, domain: str, status: str, confidence: Optional[int] = None,
    ) -> None:
        """Update a domain's status and optional confidence."""
        if domain not in self.domains:
            self.domains[domain] = DomainState()
        ds = self.domains[domain]
        ds.status = status
        if confidence is not None:
            ds.confidence = confidence

    def record_iteration(self, confidence: int) -> None:
        """Record a convergence iteration with the given confidence."""
        cs = self.convergence
        cs.iteration += 1
        prev = cs.confidence_history[-1] if cs.confidence_history else 0
        cs.confidence_history.append(confidence)
        delta = confidence - prev
        if delta < 5:  # min_delta default
            cs.stall_count += 1
        else:
            cs.stall_count = 0

    def should_stop(self, profile_config: dict) -> tuple[bool, str]:
        """Check convergence conditions against profile config.

        Returns:
            (should_stop, reason) tuple.
        """
        conv = profile_config.get("convergence", {})
        cost = profile_config.get("cost", {})
        cs = self.convergence

        # Max iterations
        max_iter = conv.get("max_iterations", 5)
        if cs.iteration >= max_iter:
            return True, "max_iterations"

        # Confidence threshold
        threshold = conv.get("confidence_threshold", 85)
        if cs.confidence_history and cs.confidence_history[-1] >= threshold:
            return True, "confidence_threshold"

        # Stall detection
        stall_limit = conv.get("stall_limit", 2)
        if cs.stall_count >= stall_limit:
            return True, "stall"

        # Token budget
        max_tokens = cost.get("max_total_tokens", 500_000)
        if self.tokens.total >= max_tokens:
            return True, "token_budget"

        return False, ""

    def save(self, run_dir: Path) -> None:
        """Persist to state.json."""
        data = {
            "run_id": self.run_id,
            "question": self.question,
            "profile": self.profile,
            "status": self.status,
            "domains": {
                k: asdict(v) for k, v in self.domains.items()
            },
            "convergence": asdict(self.convergence),
            "workers": asdict(self.workers),
            "tokens": asdict(self.tokens),
        }
        path = run_dir / "state.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, run_dir: Path) -> "RunState":
        """Load from state.json."""
        path = run_dir / "state.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        state = cls(
            run_id=data.get("run_id", ""),
            question=data.get("question", ""),
            profile=data.get("profile", "standard"),
            status=data.get("status", "created"),
        )
        for k, v in data.get("domains", {}).items():
            state.domains[k] = DomainState(**v)
        conv = data.get("convergence", {})
        state.convergence = ConvergenceState(**conv)
        wkr = data.get("workers", {})
        state.workers = WorkerState(**wkr)
        tok = data.get("tokens", {})
        state.tokens = TokenState(**tok)
        return state
