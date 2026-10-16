"""Deterministic Noisy-OR aggregation and explainability models for the fusion engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

from fusion.config import FusionConfig, ScoreBand
from fusion.weights import WeightBreakdown


class EvaluatedSignal(BaseModel):
    """An ingested hazard record processed through normalization and weighting."""

    evidence_ref: str
    hazard_type: str
    source: str
    human_label: str
    resolution_tier: str
    sigma: float = Field(..., ge=0.0, le=1.0)
    effective_weight: float = Field(..., ge=0.0, le=1.0)
    risk_product: float = Field(..., ge=0.0, le=1.0)  # clamped w_i * sigma_i
    event_time: datetime | str | None = None
    age_hours: float | None = None
    distance_km: float = 0.0
    layer_type: Literal["static", "dynamic"]
    weight_breakdown: WeightBreakdown
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SignalContribution(BaseModel):
    evidence_ref: str
    hazard_type: str
    source: str
    human_label: str
    sigma: float
    weight: float
    contribution: float
    event_time: datetime | str | None
    age_hours: float | None
    resolution_tier: str
    distance_km: float
    config_parameters: WeightBreakdown


class FusionAggregationResult(BaseModel):
    safety_score: int = Field(..., ge=0, le=100)
    score_band: ScoreBand
    S_static: float = Field(..., ge=0.0, le=1.0)
    S_dynamic: float = Field(..., ge=0.0, le=1.0)
    S_total: float = Field(..., ge=0.0, le=1.0)
    top_contributions: list[SignalContribution]
    no_active_hazards: bool
    coverage: dict[str, str]
    confidence_label: Literal["high", "medium", "low"]
    config_version: str


def compute_band(safety_score: int, config: FusionConfig) -> ScoreBand:
    """Find score band matching the 0-100 deterministic safety score."""
    for band in config.score_bands:
        if band.min <= safety_score <= band.max:
            return band
    # Fallback to last band
    return config.score_bands[-1]


def compute_confidence_label(
    coverage: dict[str, str], config: FusionConfig
) -> Literal["high", "medium", "low"]:
    """Compute confidence label from the weighted fraction of hazard types.

    A successful query returning nothing ('no_signal_found') or results ('contributing')
    counts as evidence; failed/unavailable sources do not.
    """
    total_weight = 0.0
    successful_weight = 0.0

    for hazard, status in coverage.items():
        w = float(config.base_weights.get(hazard, 0.5))
        total_weight += w
        if status in ("contributing", "no_signal_found"):
            successful_weight += w

    if total_weight <= 0:
        return "medium"

    ratio = successful_weight / total_weight
    if ratio >= 0.80:
        return "high"
    elif ratio >= 0.50:
        return "medium"
    return "low"


def aggregate_signals(
    evaluated_signals: list[EvaluatedSignal],
    coverage: dict[str, str],
    config: FusionConfig,
) -> FusionAggregationResult:
    """Perform deterministic Noisy-OR aggregation over evaluated signals.

    S_static  = 1 - prod over static signals (1 - w_i*sigma_i)
    S_dynamic = 1 - prod over dynamic signals (1 - w_i*sigma_i)
    S         = 1 - (1 - S_static) * (1 - S_dynamic)
    safety_score = round(100 * (1 - S)), clamped to [0,100].
    """
    prod_static = 1.0
    prod_dynamic = 1.0

    total_risk_sum = 0.0

    for s in evaluated_signals:
        term = s.risk_product  # clamped w_i * sigma_i in [0, 1]
        factor = 1.0 - term
        if s.layer_type == "static":
            prod_static *= factor
        else:
            prod_dynamic *= factor
        total_risk_sum += term

    S_static = max(0.0, min(1.0, 1.0 - prod_static))
    S_dynamic = max(0.0, min(1.0, 1.0 - prod_dynamic))
    S_total = max(0.0, min(1.0, 1.0 - (1.0 - S_static) * (1.0 - S_dynamic)))

    raw_score = round(100.0 * (1.0 - S_total))
    safety_score = max(0, min(100, int(raw_score)))

    # Explainability contributions
    top_contributions: list[SignalContribution] = []
    no_active = total_risk_sum <= 1e-9 or len(evaluated_signals) == 0

    if not no_active:
        # Calculate normalized contributions
        all_contribs: list[SignalContribution] = []
        for s in evaluated_signals:
            c_val = s.risk_product / total_risk_sum
            all_contribs.append(
                SignalContribution(
                    evidence_ref=s.evidence_ref,
                    hazard_type=s.hazard_type,
                    source=s.source,
                    human_label=s.human_label,
                    sigma=round(s.sigma, 4),
                    weight=round(s.effective_weight, 4),
                    contribution=round(c_val, 4),
                    event_time=s.event_time,
                    age_hours=round(s.age_hours, 1) if s.age_hours is not None else None,
                    resolution_tier=s.resolution_tier,
                    distance_km=round(s.distance_km, 2),
                    config_parameters=s.weight_breakdown,
                )
            )
        # Sort descending by contribution, top 8
        all_contribs.sort(key=lambda x: x.contribution, reverse=True)
        top_contributions = all_contribs[:8]

    band = compute_band(safety_score, config)
    conf_label = compute_confidence_label(coverage, config)

    return FusionAggregationResult(
        safety_score=safety_score,
        score_band=band,
        S_static=round(S_static, 4),
        S_dynamic=round(S_dynamic, 4),
        S_total=round(S_total, 4),
        top_contributions=top_contributions,
        no_active_hazards=no_active,
        coverage=coverage,
        confidence_label=conf_label,
        config_version=config.config_version,
    )
