from __future__ import annotations

from math import exp


def apply_adaptive_decay(
    *,
    source_confidence: float,
    age_days: int,
    volatility_score: float,
    unused_weeks: int,
) -> float:
    ttl_days = max(7.0, 120.0 * (1.0 - min(max(volatility_score, 0.0), 0.95)))
    age_factor = exp(-(age_days / ttl_days))
    usage_factor = 1.0 if unused_weeks == 0 else max(0.5, 1.0 - (unused_weeks * 0.05))
    return max(0.0, min(1.0, source_confidence * age_factor * usage_factor))
