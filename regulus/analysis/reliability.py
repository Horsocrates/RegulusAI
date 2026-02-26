"""
Reliability analysis for interval neural network predictions.

Key metrics:
- overlap: do class intervals overlap?
- gap: distance between intervals (if no overlap)
- spread: width of winning class interval
- confidence_range: [min_confidence, max_confidence]

Width bound (from Coq pi_wdot_width_uniform_bound):
  width(output) <= eps * product(L1_norm(W_layer))
  ReLU does not increase width (pi_relu_width_bound).
"""

from __future__ import annotations

import numpy as np

from regulus.nn.interval_tensor import IntervalTensor


class ReliabilityAnalysis:
    """Analyze reliability of interval model predictions."""

    @staticmethod
    def classify(output: IntervalTensor) -> dict:
        """Analyze a single prediction.

        Returns:
            {
                'predicted_class': int,
                'reliable': bool,
                'confidence_lo': float,
                'confidence_hi': float,
                'max_width': float,
                'overlapping_pairs': list[tuple[int, int]],
                'gap': float  (negative = overlap)
            }
        """
        n_classes = output.lo.shape[0]

        # Predicted class = highest upper bound
        predicted = int(np.argmax(output.hi))

        # Find overlapping pairs
        # Two intervals [a,b] and [c,d] overlap iff a <= d AND c <= b
        # Equivalently: NOT (a > d OR c > b)
        # Gap = max(lo_i - hi_j, lo_j - hi_i): positive = separated
        overlapping = []
        min_gap = float("inf")

        for i in range(n_classes):
            for j in range(i + 1, n_classes):
                # Separation: gap > 0 means separated
                gap = max(
                    output.lo[i] - output.hi[j],
                    output.lo[j] - output.hi[i],
                )
                if gap < 0:
                    overlapping.append((i, j))
                min_gap = min(min_gap, gap)

        # Reliable if predicted class doesn't overlap with any other
        predicted_overlaps = any(predicted in pair for pair in overlapping)
        reliable = not predicted_overlaps

        return {
            "predicted_class": predicted,
            "reliable": reliable,
            "confidence_lo": float(output.lo[predicted]),
            "confidence_hi": float(output.hi[predicted]),
            "max_width": float(output.max_width()),
            "overlapping_pairs": overlapping,
            "gap": float(min_gap),
        }

    @staticmethod
    def batch_analysis(results: list[dict], true_labels: np.ndarray) -> dict:
        """Analyze a batch of predictions.

        Key metrics:
        - flagged_unreliable: marked as unreliable
        - actually_wrong: truly incorrect (by true_labels)
        - caught: wrong AND flagged
        - missed: wrong BUT flagged as reliable
        - false_alarm: correct BUT flagged as unreliable
        - precision: caught / flagged
        - recall: caught / actually_wrong
        """
        total = len(results)
        flagged = sum(1 for r in results if not r["reliable"])

        wrong = 0
        caught = 0
        missed = 0
        false_alarm = 0

        for r, true_label in zip(results, true_labels):
            is_wrong = r["predicted_class"] != true_label
            is_flagged = not r["reliable"]

            if is_wrong:
                wrong += 1
                if is_flagged:
                    caught += 1
                else:
                    missed += 1
            else:
                if is_flagged:
                    false_alarm += 1

        precision = caught / flagged if flagged > 0 else 0.0
        recall = caught / wrong if wrong > 0 else 0.0

        reliable_total = total - flagged
        reliable_correct = reliable_total - missed

        return {
            "total": total,
            "flagged_unreliable": flagged,
            "actually_wrong": wrong,
            "caught": caught,
            "missed": missed,
            "false_alarm": false_alarm,
            "precision": precision,
            "recall": recall,
            "accuracy_standard": (total - wrong) / total,
            "accuracy_after_filtering": reliable_correct / reliable_total if reliable_total > 0 else 0.0,
        }


def predict_max_width(model, input_eps: float) -> dict:
    """PROVEN upper bound on output interval width.

    From pi_wdot_width_uniform_bound (Coq, 0 Admitted, 0 axioms):
        width(W·x) <= eps * ||W||_1

    For a multi-layer network:
        width(output) <= eps * prod(max_row_l1_norm(W_layer))

    ReLU does not increase width (pi_relu_width_bound, proven).
    This allows predicting, BEFORE running the model, how wide
    output intervals will be for a given input uncertainty.

    Returns:
        {
            'input_eps': float,
            'output_width_bound': float,
            'layer_l1_norms': list[float],
            'blowup_factor': float,
        }
    """
    from regulus.nn.layers import IntervalLinear

    bound = 2.0 * input_eps  # input width = 2*eps
    layer_norms = []

    for layer in model.layers:
        if isinstance(layer, IntervalLinear):
            # L1-norm per row, take max (worst-case neuron)
            l1_norm = float(np.sum(np.abs(layer.weight), axis=1).max())
            bound *= l1_norm
            layer_norms.append(l1_norm)
        # ReLU/Sigmoid: width does not increase (pi_relu_width_bound)

    return {
        "input_eps": input_eps,
        "output_width_bound": bound,
        "layer_l1_norms": layer_norms,
        "blowup_factor": bound / (2.0 * input_eps) if input_eps > 0 else float("inf"),
    }
