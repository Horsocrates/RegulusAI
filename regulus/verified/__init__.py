"""
Verified computation backend — bridge from Coq-extracted OCaml to Python.

Provides:
- VerifiedBackend: call OCaml-extracted functions or Python fallbacks
- MathVerifier: D4 verified computation integration
- ERRValidator: D1 E/R/R structural validation
- LayeredAnalysis: Information Layers for multi-perspective reasoning

Every result carries `theorem_used` — full traceability to Coq proofs.
"""

from regulus.verified.bridge import VerifiedBackend, VerifiedResult
from regulus.verified.math_verifier import MathVerifier
from regulus.verified.err_validator import ERRValidator
from regulus.verified.layers import AnalysisLayer, LayeredAnalysis

__all__ = [
    "VerifiedBackend",
    "VerifiedResult",
    "MathVerifier",
    "ERRValidator",
    "AnalysisLayer",
    "LayeredAnalysis",
]
