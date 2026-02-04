"""
Regulus AI - Correction Prompts
================================

Fix prompt templates for each gate failure type.
Used by the orchestrator to request LLM corrections.
"""

# Fix prompt templates keyed by diagnostic code
FIX_PROMPTS = {
    "ERR_E": (
        "Your reasoning step lacks a concrete Element. "
        "Please identify the specific object, claim, or entity being reasoned about."
    ),
    "ERR_R": (
        "Your reasoning step has an Element but no defined Role. "
        "Please specify the functional purpose or relationship of this element."
    ),
    "ERR_RULE": (
        "Your reasoning step has Element and Role but no connecting Rule. "
        "Please provide the logical rule or principle that connects the premises to the conclusion."
    ),
    "LEVELS_LOOP": (
        "Your reasoning contains a self-referential loop (L1-L3 violation). "
        "A statement cannot evaluate its own truth value. "
        "Please reformulate without self-reference."
    ),
}


def get_fix_prompt(diagnostic_code: str) -> str:
    """Get the fix prompt for a given diagnostic code."""
    if diagnostic_code in FIX_PROMPTS:
        return FIX_PROMPTS[diagnostic_code]

    if diagnostic_code and diagnostic_code.startswith("ORDER"):
        return (
            "Your reasoning violates the domain sequence (L5 Law of Order). "
            "Domains must be traversed D1→D6 in order. "
            "Please fill in the missing intermediate reasoning steps."
        )

    return "Your reasoning step failed structural verification. Please review and reformulate."
