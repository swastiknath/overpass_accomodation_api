"""Weight calculation and spatial/temporal decay functions for hazard signals."""

from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel

from fusion.config import FusionConfig


class WeightBreakdown(BaseModel):
    base_weight: float
    confidence: float
    resolution_factor: float
    temporal_decay: float
    spatial_kernel: float
    effective_weight: float


def compute_temporal_decay(
    hazard_type: str,
    age_hours: float | None,
    config: FusionConfig,
    event_type: str | None = None,
) -> float:
    """Calculate temporal decay factor g_hazard(age) = 2^(-age / half_life).

    Static layers return 1.0 (no decay).
    """
    if age_hours is None or age_hours <= 0:
        return 1.0

    half_life: float | None = None

    # Check for event-type specific decay in conflict
    if hazard_type == "conflict" and event_type:
        ev_key = event_type.lower().replace(" ", "_")
        for k, hl in config.conflict_decay_by_event_type.items():
            if k in ev_key:
                half_life = float(hl)
                break

    if half_life is None:
        half_life = config.temporal_decay_half_life_hours.get(hazard_type)

    if half_life is None or half_life <= 0:
        # Static layer or no decay specified
        return 1.0

    decay = math.pow(2.0, -float(age_hours) / float(half_life))
    return max(0.0, min(1.0, decay))


def compute_spatial_kernel(
    hazard_type: str,
    distance_km: float,
    resolution_tier: str,
    config: FusionConfig,
    is_in_district: bool = True,
) -> float:
    """Calculate Gaussian spatial kernel K_hazard(d) = exp(-d^2 / (2 * s^2)).

    For district-tier signals, K = 1.0 if inside district, 0.0 outside.
    """
    tier_norm = resolution_tier.lower()
    if tier_norm == "district":
        return 1.0 if is_in_district else 0.0

    s = float(config.spatial_kernel_sigma_km.get(hazard_type, 15.0))
    if s <= 0:
        return 1.0 if distance_km <= 0.01 else 0.0

    # Gaussian kernel
    exponent = -(distance_km ** 2) / (2.0 * (s ** 2))
    kernel = math.exp(exponent)
    return max(0.0, min(1.0, kernel))


def compute_effective_weight(
    hazard_type: str,
    source: str,
    resolution_tier: str,
    confidence: float | None,
    distance_km: float,
    age_hours: float | None,
    config: FusionConfig,
    is_in_district: bool = True,
    event_type: str | None = None,
) -> tuple[float, WeightBreakdown]:
    """Calculate effective weight w_i = base_weight * c_i * d * g * K.

    Returns (effective_weight, WeightBreakdown).
    """
    base_w = float(config.base_weights.get(hazard_type, 0.5))

    # Confidence c_i
    if confidence is not None:
        c_i = max(0.0, min(1.0, float(confidence)))
    else:
        src_clean = source.lower().replace("-", "_")
        c_i = float(config.source_confidence_defaults.get(src_clean, 0.80))

    # Resolution tier factor d(resolution_tier)
    tier_clean = resolution_tier.lower()
    d_factor = float(config.resolution_multipliers.get(tier_clean, 0.85))

    # Temporal decay g(age)
    g_decay = compute_temporal_decay(hazard_type, age_hours, config, event_type=event_type)

    # Spatial kernel K(distance)
    k_spatial = compute_spatial_kernel(
        hazard_type, distance_km, tier_clean, config, is_in_district=is_in_district
    )

    w_i = base_w * c_i * d_factor * g_decay * k_spatial

    breakdown = WeightBreakdown(
        base_weight=round(base_w, 4),
        confidence=round(c_i, 4),
        resolution_factor=round(d_factor, 4),
        temporal_decay=round(g_decay, 4),
        spatial_kernel=round(k_spatial, 4),
        effective_weight=round(w_i, 4),
    )
    return w_i, breakdown
