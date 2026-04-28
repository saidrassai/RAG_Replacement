from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from lattice_jit.contracts import FeedbackLabel, KnowledgeNode
from lattice_jit.core import utcnow
from lattice_jit.storage import StorageRepository


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_pava(values: list[float], weights: list[float] | None = None) -> list[float]:
    """Pool-adjacent-violators algorithm for isotonic regression.

    Returns a monotonically non-decreasing sequence that minimizes
    the weighted least-squares distance to the input values.
    """
    if not values:
        return []
    if weights is None:
        weights = [1.0] * len(values)
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")

    n = len(values)
    blocks: list[list[int]] = [[i] for i in range(n)]
    block_values = [float(v) for v in values]
    block_weights = [float(w) for w in weights]
    block_sums = [block_values[i] * block_weights[i] for i in range(n)]

    i = 0
    while i < len(blocks) - 1:
        if block_values[i] <= block_values[i + 1]:
            i += 1
            continue

        merged_indices = blocks[i] + blocks[i + 1]
        merged_weight = block_weights[i] + block_weights[i + 1]
        merged_sum = block_sums[i] + block_sums[i + 1]
        merged_value = merged_sum / merged_weight if merged_weight > 0 else 0.0

        blocks[i : i + 2] = [merged_indices]
        block_values[i : i + 2] = [merged_value]
        block_weights[i : i + 2] = [merged_weight]
        block_sums[i : i + 2] = [merged_sum]

        if i > 0:
            i -= 1

    result = [0.0] * n
    for blk, val in zip(blocks, block_values, strict=True):
        for idx in blk:
            result[idx] = val
    return result


def build_calibration_curve(
    predicted: list[float],
    actual: list[float],
) -> list[tuple[float, float]]:
    """Build a calibration curve from (predicted, actual) pairs.

    Returns a list of (confidence_bin, calibrated_value) points sorted by confidence_bin.
    The calibrated_value is the PAVA-smoothed actual value.
    """
    if not predicted or len(predicted) != len(actual):
        return []
    paired = sorted(zip(predicted, actual, strict=True), key=lambda x: x[0])
    sorted_pred = [p for p, _ in paired]
    sorted_actual = [a for _, a in paired]
    calibrated = compute_pava(sorted_actual)
    unique_points: list[tuple[float, float]] = []
    for p, c in zip(sorted_pred, calibrated, strict=True):
        if unique_points and unique_points[-1][0] == p:
            continue
        unique_points.append((p, _clamp(c, 0.0, 1.0)))
    return unique_points


def apply_calibration(
    serving_confidence: float,
    calibration_curve: list[tuple[float, float]],
) -> float:
    """Map a raw confidence through a calibration curve using linear interpolation."""
    if not calibration_curve:
        return serving_confidence
    if serving_confidence <= calibration_curve[0][0]:
        return calibration_curve[0][1]
    if serving_confidence >= calibration_curve[-1][0]:
        return calibration_curve[-1][1]
    for i in range(len(calibration_curve) - 1):
        x0, y0 = calibration_curve[i]
        x1, y1 = calibration_curve[i + 1]
        if x0 <= serving_confidence <= x1:
            if x1 - x0 == 0:
                return y0
            t = (serving_confidence - x0) / (x1 - x0)
            return _clamp(y0 + t * (y1 - y0), 0.0, 1.0)
    return serving_confidence


@dataclass(slots=True)
class CalibrationService:
    repository: StorageRepository

    def record_feedback(
        self,
        *,
        tenant_id: UUID,
        target_type: str,
        target_id: UUID,
        label_type: str,
        label_value: float,
    ) -> FeedbackLabel:
        label = FeedbackLabel(
            tenant_id=tenant_id,
            target_type=target_type,
            target_id=target_id,
            label_type=label_type,
            label_value=label_value,
            labeled_at=utcnow(),
        )
        self.repository.store_feedback_label(
            tenant_id=label.tenant_id,
            target_type=label.target_type,
            target_id=label.target_id,
            label_type=label.label_type,
            label_value=label.label_value,
            labeled_at=label.labeled_at,
        )
        return label

    def list_feedback(self, tenant_id: UUID) -> list[FeedbackLabel]:
        return self.repository.list_feedback_labels(tenant_id)

    def compute_curve_for_tenant(
        self,
        tenant_id: UUID,
        nodes: list[KnowledgeNode],
    ) -> list[tuple[float, float]]:
        """Compute calibration curve from feedback labels and node confidences.

        Maps feedback target_id -> node -> serving_confidence to produce
        (predicted_confidence, actual_label) pairs, then fits via PAVA.
        """
        labels = self.list_feedback(tenant_id)
        if not labels:
            return []
        node_by_id = {node.node_id: node for node in nodes}
        predicted: list[float] = []
        actual: list[float] = []
        for label in labels:
            if label.target_type != "node":
                continue
            node = node_by_id.get(label.target_id)
            if node is None:
                continue
            predicted.append(node.serving_confidence)
            actual.append(label.label_value)
        if len(predicted) < 3:
            return []
        return build_calibration_curve(predicted, actual)
