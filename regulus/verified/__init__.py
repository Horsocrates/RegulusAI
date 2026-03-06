"""
Verified computation backend — bridge from Coq-extracted OCaml to Python.

Provides:
- VerifiedBackend: call OCaml-extracted functions or Python fallbacks
- MathVerifier: D4 verified computation integration
- ERRValidator: D1 E/R/R structural validation
- LayeredAnalysis: Information Layers for multi-perspective reasoning
- ContractionEstimate / ConvergenceAnalyzer: Banach contraction convergence
- ConvergenceAdvisor: human-readable convergence advice

Every result carries `theorem_used` — full traceability to Coq proofs.
"""

from regulus.verified.bridge import VerifiedBackend, VerifiedResult
from regulus.verified.math_verifier import MathVerifier
from regulus.verified.err_validator import ERRValidator
from regulus.verified.layers import AnalysisLayer, LayeredAnalysis
from regulus.verified.convergence import ContractionEstimate, ConvergenceAnalyzer
from regulus.verified.convergence_advisor import ConvergenceAdvisor

__all__ = [
    "VerifiedBackend",
    "VerifiedResult",
    "MathVerifier",
    "ERRValidator",
    "AnalysisLayer",
    "LayeredAnalysis",
    "ContractionEstimate",
    "ConvergenceAnalyzer",
    "ConvergenceAdvisor",
]
