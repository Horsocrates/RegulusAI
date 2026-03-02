"""
Fallacy Taxonomy — ported from Coq-verified formalization.

Source: theory-of-systems-coq/Architecture_of_Reasoning/
  - CompleteFallacyTaxonomy.v (156 fallacies, 19 theorems)
  - DomainViolations_Complete.v (105 Type 2, 17 theorems)
  - AI_FallacyDetector.v (20 theorems)

509 theorems total in the ToS formalization.
All ported structures mirror Coq types exactly.
"""

from regulus.fallacies.taxonomy import (
    FallacyType,
    Domain,
    FailureMode,
    Fallacy,
    FALLACIES,
    FALLACIES_BY_DOMAIN,
    FALLACIES_BY_TYPE,
    FAILURE_MODES,
    get_fallacy,
    get_domain_fallacies,
    get_failure_mode_fallacies,
)

__all__ = [
    "FallacyType",
    "Domain",
    "FailureMode",
    "Fallacy",
    "FALLACIES",
    "FALLACIES_BY_DOMAIN",
    "FALLACIES_BY_TYPE",
    "FAILURE_MODES",
    "get_fallacy",
    "get_domain_fallacies",
    "get_failure_mode_fallacies",
]
