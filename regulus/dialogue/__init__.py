"""
Regulus AI - Two-Agent Dialogue Pipeline
=========================================

Implements the Regulus two-agent architecture:
- Team Lead: meta-cognition (D6-ASK + D6-REFLECT), maintains conspectus
- Worker: domain reasoning (D1-D5), one domain at a time

The agents conduct a continuous multi-turn conversation, bridged by
the DialogueOrchestrator which manages convergence, worker replacement,
and the dialogue audit trail.
"""

from regulus.dialogue.agent import Agent, AgentConfig
from regulus.dialogue.channel import DialogueChannel
from regulus.dialogue.conspectus import Conspectus
from regulus.dialogue.state import RunState
from regulus.dialogue.orchestrator import DialogueOrchestrator

__all__ = [
    "Agent",
    "AgentConfig",
    "DialogueChannel",
    "Conspectus",
    "RunState",
    "DialogueOrchestrator",
]
