"""Domain prompts registry."""

from . import d1_recognition, d2_clarification, d3_framework
from . import d4_comparison, d5_inference, d6_reflection
from . import orchestrator

DOMAIN_PROMPTS = {
    "D1": d1_recognition,
    "D2": d2_clarification,
    "D3": d3_framework,
    "D4": d4_comparison,
    "D5": d5_inference,
    "D6": d6_reflection,
    "orchestrator": orchestrator,
}
