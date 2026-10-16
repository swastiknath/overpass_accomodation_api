"""Fusion scoring engine: transforms IngestedRecord items into EvaluatedSignal and aggregates."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from gis.schema import IngestedRecord, ResolutionTier
from fusion.config import FusionConfig
from fusion.normalizers import normalize_signal
from fusion.weights import compute_effective_weight
from fusion.aggregation import (
    EvaluatedSignal,
    FusionAggregationResult,
    aggregate_signals,
)


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return 6371.0 * c


def _distance_to_geometry_km(target_lat: float, target_lon: float, geom: BaseGeometry) -> float:
    """Calculate distance in kilometers from target point to geometry."""
    pt = Point(target_lon, target_lat)
    if geom.contains(pt) or geom.covers(pt):
        return 0.0

    if geom.geom_type == "Point":
        return _haversine_distance_km(target_lat, target_lon, geom.y, geom.x)

    # For general polygons/lines, find nearest point on geom or representative point
    rep = geom.representative_point()
    return _haversine_distance_km(target_lat, target_lon, rep.y, rep.x)


def evaluate_signal_at_location(
    record: IngestedRecord,
    target_lat: float,
    target_lon: float,
    target_district_id: str | None,
    config: FusionConfig,
    reference_time: datetime | None = None,
) -> EvaluatedSignal:
    """Evaluate a single IngestedRecord for a specific target location."""
    now = reference_time or datetime.now(timezone.utc)

    # Calculate distance
    distance_km = _distance_to_geometry_km(target_lat, target_lon, record.geometry)

    # District containment check
    is_in_district = True
    if record.resolution_tier == ResolutionTier.DISTRICT:
        if record.district_id and target_district_id:
            is_in_district = record.district_id.strip().lower() == target_district_id.strip().lower()
        else:
            # If district unknown, approximate by distance <= 25km
            is_in_district = distance_km <= 25.0

    # Calculate age in hours
    ev_time = record.event_time
    if ev_time.tzinfo is None:
        ev_time = ev_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (now - ev_time).total_seconds())
    age_hours = age_seconds / 3600.0

    # Normalization -> sigma in [0, 1]
    raw_val = record.severity_raw if record.severity_raw is not None else record.severity_normalized
    if raw_val is None:
        raw_val = record.raw_payload
    sigma = normalize_signal(record.hazard_type, raw_val, config)

    # Event type for conflict
    event_type = None
    if record.hazard_type == "conflict":
        event_type = record.raw_payload.get("event_type")

    # Weight calculation
    w_i, breakdown = compute_effective_weight(
        hazard_type=record.hazard_type,
        source=record.source,
        resolution_tier=record.resolution_tier.value,
        confidence=record.confidence,
        distance_km=distance_km,
        age_hours=age_hours,
        config=config,
        is_in_district=is_in_district,
        event_type=event_type,
    )

    risk_product = max(0.0, min(1.0, w_i * sigma))
    layer_type = config.hazard_layers.get(record.hazard_type, "dynamic")

    # Generate human label
    human_label = f"{record.hazard_type.replace('_', ' ').title()} ({record.source.upper()})"
    if "title" in record.raw_payload:
        human_label = f"{record.raw_payload['title']}"
    elif "event_type" in record.raw_payload:
        human_label = f"{record.raw_payload['event_type']} - {record.source.upper()}"

    return EvaluatedSignal(
        evidence_ref=record.event_id,
        hazard_type=record.hazard_type,
        source=record.source,
        human_label=human_label,
        resolution_tier=record.resolution_tier.value,
        sigma=round(sigma, 4),
        effective_weight=round(w_i, 4),
        risk_product=round(risk_product, 4),
        event_time=record.event_time.isoformat() if hasattr(record.event_time, "isoformat") else str(record.event_time),
        age_hours=round(age_hours, 2),
        distance_km=round(distance_km, 2),
        layer_type=layer_type,
        weight_breakdown=breakdown,
        raw_payload=record.raw_payload,
    )


def compute_fusion_at_location(
    records: list[IngestedRecord],
    target_lat: float,
    target_lon: float,
    target_district_id: str | None,
    coverage: dict[str, str],
    config: FusionConfig,
    reference_time: datetime | None = None,
) -> tuple[FusionAggregationResult, list[EvaluatedSignal]]:
    """Compute complete deterministic fusion scoring for a target location.

    Returns (FusionAggregationResult, list[EvaluatedSignal]).
    """
    evaluated: list[EvaluatedSignal] = []
    for r in records:
        ev = evaluate_signal_at_location(
            record=r,
            target_lat=target_lat,
            target_lon=target_lon,
            target_district_id=target_district_id,
            config=config,
            reference_time=reference_time,
        )
        evaluated.append(ev)

    result = aggregate_signals(evaluated_signals=evaluated, coverage=coverage, config=config)
    return result, evaluated
