"""
layers.py — Information Layers in the Regulus Pipeline.

Formalizes the paradigm_shift mechanism as principled layer switching.
One question (substrate) can be analyzed through multiple layers (criteria).
Each layer = different E/R/R configuration on the same elements.

Corresponds to InfoLayer.v (17 Qed, 0 Admitted) in theory-of-systems-coq.

Key insight (P3 Intensional Identity):
  Same substrate + different criterion = different system.
  This is NOT a bug — it's the foundation of multi-perspective analysis.

Pipeline integration:
  D1+D2 = substrate (shared across layers)
  D3 = layer selection (which criterion to apply)
  D4+D5 = layer-specific computation and inference
  D6 = cross-layer comparison
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AnalysisLayer:
    """An Information Layer for reasoning.

    Corresponds to InfoLayer.v: criterion over fixed substrate.
    Different layers = different criteria on same elements = different systems (P3).

    Attributes:
        id: Unique identifier for this layer
        name: Human-readable layer name
        criterion_type: Category of criterion (mathematical, logical, empirical, etc.)
        focus_predicate: What this layer examines
        reason: L4 justification — why this layer exists
        priority: L5 ordering — higher priority = applied first when resolving ties
    """

    id: str
    name: str
    criterion_type: str
    focus_predicate: str
    reason: str
    priority: int = 0


@dataclass
class LayeredAnalysis:
    """Multi-layer analysis of a single question.

    Substrate = D1+D2 output (elements, roles, rules — shared across layers)
    Layers = different D3 frameworks, each producing different D4 comparisons

    Replaces ad-hoc paradigm_shift with principled layer switching.

    Attributes:
        substrate: D1+D2 output (shared across all layers)
        layers: List of analysis layers
        active_layer: Currently active layer ID
        layer_results: Results from each layer (layer_id → D4+D5 output)
    """

    substrate: dict
    layers: list[AnalysisLayer] = field(default_factory=list)
    active_layer: Optional[str] = None
    layer_results: dict[str, dict] = field(default_factory=dict)

    def add_layer(self, layer: AnalysisLayer) -> bool:
        """Add a layer. P3: different criterion = different system.

        Returns True if layer was added, False if duplicate (same criterion+predicate).
        """
        for existing in self.layers:
            if (
                existing.criterion_type == layer.criterion_type
                and existing.focus_predicate == layer.focus_predicate
            ):
                return False  # Same criterion = same layer, skip (P3)
        self.layers.append(layer)
        if self.active_layer is None:
            self.active_layer = layer.id
        return True

    def switch_layer(self, layer_id: str) -> Optional[AnalysisLayer]:
        """Switch active layer. Substrate stays, criterion changes.

        This IS the paradigm shift — formalized as layer switching.
        D1+D2 preserved, D3+D4+D5 re-run with new layer's criterion.

        Returns the activated layer, or None if not found.
        """
        for layer in self.layers:
            if layer.id == layer_id:
                self.active_layer = layer_id
                return layer
        return None

    def get_active_layer(self) -> Optional[AnalysisLayer]:
        """Get the currently active layer."""
        if self.active_layer:
            for layer in self.layers:
                if layer.id == self.active_layer:
                    return layer
        return None

    def get_active_criterion(self) -> Optional[str]:
        """What criterion is currently applied to the substrate?"""
        active = self.get_active_layer()
        return active.focus_predicate if active else None

    def store_result(self, layer_id: str, result: dict) -> None:
        """Store D4+D5 result for a specific layer."""
        self.layer_results[layer_id] = result

    def get_layers_by_priority(self) -> list[AnalysisLayer]:
        """Get layers sorted by priority (highest first, L5 ordering)."""
        return sorted(self.layers, key=lambda l: l.priority, reverse=True)

    def compare_across_layers(self) -> dict:
        """D6-level: compare results from different layers.

        Same substrate, different criteria → different conclusions possible.
        Agreement across layers = high confidence.
        Disagreement = structural insight (different aspects reveal different truths).

        Returns comparison summary.
        """
        if len(self.layer_results) < 2:
            return {
                "comparison": "insufficient_layers",
                "layer_count": len(self.layer_results),
            }

        answers: dict[str, object] = {}
        confidences: dict[str, float] = {}
        for lid, result in self.layer_results.items():
            answers[lid] = result.get("d5_answer")
            confidences[lid] = result.get("confidence", 0.0)

        unique_answers = set(str(a) for a in answers.values() if a is not None)
        agreement = len(unique_answers) <= 1

        # Find the layer with highest confidence
        if confidences:
            best_layer = max(confidences, key=lambda k: confidences[k])
        else:
            best_layer = None

        return {
            "layer_count": len(self.layer_results),
            "answers_by_layer": answers,
            "confidences_by_layer": confidences,
            "agreement": agreement,
            "unique_answers": len(unique_answers),
            "best_layer": best_layer,
            "insight": (
                "All layers converge → high structural confidence"
                if agreement
                else (
                    f"Layers diverge ({len(unique_answers)} distinct answers) → "
                    "examine which criterion is most appropriate"
                )
            ),
        }

    def to_dict(self) -> dict:
        """Serialize for pipeline transport."""
        return {
            "substrate": self.substrate,
            "layers": [
                {
                    "id": l.id,
                    "name": l.name,
                    "criterion_type": l.criterion_type,
                    "focus_predicate": l.focus_predicate,
                    "reason": l.reason,
                    "priority": l.priority,
                }
                for l in self.layers
            ],
            "active_layer": self.active_layer,
            "layer_results": self.layer_results,
        }


# ── Predefined layer templates ────────────────────────────────────────

MATH_LAYER = AnalysisLayer(
    id="math",
    name="Mathematical Analysis",
    criterion_type="mathematical",
    focus_predicate="formal derivation and computation",
    reason="Establish mathematical truth through proof",
    priority=10,
)

EMPIRICAL_LAYER = AnalysisLayer(
    id="empirical",
    name="Empirical Verification",
    criterion_type="empirical",
    focus_predicate="observable evidence and measurement",
    reason="Ground claims in verifiable observations",
    priority=5,
)

LOGICAL_LAYER = AnalysisLayer(
    id="logical",
    name="Logical Structure",
    criterion_type="logical",
    focus_predicate="validity of inference chain",
    reason="Verify argument structure independent of content",
    priority=8,
)

ETHICAL_LAYER = AnalysisLayer(
    id="ethical",
    name="Ethical Analysis",
    criterion_type="ethical",
    focus_predicate="moral implications and value alignment",
    reason="Evaluate normative dimensions of the question",
    priority=3,
)


def make_domain_layer(domain: str, priority: int = 3) -> AnalysisLayer:
    """Create a domain-specific analysis layer.

    Args:
        domain: The domain name (e.g., "physics", "law", "medicine")
        priority: L5 priority for this layer
    """
    return AnalysisLayer(
        id=f"domain_{domain}",
        name=f"{domain.title()} Domain Knowledge",
        criterion_type="domain_specific",
        focus_predicate=f"established principles of {domain}",
        reason=f"Apply {domain}-specific expertise",
        priority=priority,
    )
