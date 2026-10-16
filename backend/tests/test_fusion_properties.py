"""Property tests for the deterministic fusion scoring module.

Verifies:
1. Score is always in [0, 100]
2. Adding a signal never lowers risk (monotonicity)
3. A strong signal is not diluted by adding weak ones (noisy-OR non-dilution)
4. A missing source is excluded and appears in coverage (not treated as zero)
5. Contributions sum to 1 (when active hazards exist)
6. Empty signal set returns a valid 'no hazards found' response with score 100
7. Unknown hazard type raises ValueError
8. config_version is always present
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
import pytest
from shapely.geometry import Point

from gis.schema import IngestedRecord, ResolutionTier
from fusion.config import load_fusion_config
from fusion.normalizers import normalize_signal
from fusion.engine import compute_fusion_at_location, evaluate_signal_at_location
from fusion.aggregation import aggregate_signals


@pytest.fixture
def fusion_cfg():
    return load_fusion_config()


@pytest.fixture
def now_utc():
    return datetime.now(timezone.utc)


def make_record(
    event_id: str,
    hazard_type: str,
    source: str,
    lat: float = 28.6139,
    lon: float = 77.2090,
    severity_raw: float | str | int | None = 0.5,
    confidence: float | None = 0.9,
    resolution_tier: ResolutionTier = ResolutionTier.POINT,
    event_time: datetime | None = None,
    raw_payload: dict | None = None,
) -> IngestedRecord:
    now = datetime.now(timezone.utc)
    # If dict passed as severity_raw, move it to raw_payload
    payload = raw_payload or {}
    s_raw = severity_raw
    if isinstance(severity_raw, dict):
        payload = {**payload, **severity_raw}
        s_raw = None

    return IngestedRecord(
        event_id=event_id,
        source=source,
        hazard_type=hazard_type,
        geometry=Point(lon, lat),
        event_time=event_time or now,
        ingest_time=now,
        severity_raw=s_raw,
        confidence=confidence,
        resolution_tier=resolution_tier,
        raw_payload=payload,
    )


def test_config_version_present(fusion_cfg):
    """Config version must be present and non-empty."""
    assert fusion_cfg.config_version is not None
    assert len(fusion_cfg.config_version) > 0


def test_unknown_hazard_type_raises(fusion_cfg):
    """Unknown hazard type must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown hazard_type"):
        normalize_signal("alien_invasion", 0.9, fusion_cfg)


def test_empty_signal_set_returns_valid_response(fusion_cfg):
    """Empty signal set returns score 100, no division error, and no_active_hazards=True."""
    coverage = {"landslide": "no_signal_found", "flood": "no_signal_found", "crime": "no_signal_found"}
    result, evaluated = compute_fusion_at_location(
        records=[],
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id="New Delhi",
        coverage=coverage,
        config=fusion_cfg,
    )
    assert result.safety_score == 100
    assert result.no_active_hazards is True
    assert result.top_contributions == []
    assert result.S_static == 0.0
    assert result.S_dynamic == 0.0
    assert result.S_total == 0.0
    assert result.config_version == fusion_cfg.config_version
    assert result.confidence_label == "high"


def test_score_always_in_bounds(fusion_cfg):
    """Check score is strictly clamped to [0, 100] across a spectrum of inputs."""
    records = [
        make_record("r1", "flood", "gdacs", severity_raw="Red", confidence=1.0),
        make_record("r2", "cyclone", "gdacs", severity_raw="Red", confidence=1.0),
        make_record("r3", "earthquake", "usgs", severity_raw=7.5, confidence=1.0),
        make_record("r4", "conflict", "acled", severity_raw={"fatalities": 50, "event_type": "armed_clash"}),
        make_record("r5", "landslide", "bhuvan", severity_raw=0.95),
    ]
    coverage = {"flood": "contributing", "cyclone": "contributing", "earthquake": "contributing"}
    result, _ = compute_fusion_at_location(
        records=records,
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id="New Delhi",
        coverage=coverage,
        config=fusion_cfg,
    )
    assert 0 <= result.safety_score <= 100
    assert 0.0 <= result.S_static <= 1.0
    assert 0.0 <= result.S_dynamic <= 1.0
    assert 0.0 <= result.S_total <= 1.0


def test_adding_signal_never_lowers_risk(fusion_cfg):
    """Monotonicity: Adding an additional hazard signal must never lower risk (never increase safety score)."""
    base_records = [
        make_record("r1", "weather", "open_meteo", severity_raw={"rainfall_mm_24h": 40.0, "wind_speed_kmh": 30.0}),
    ]
    coverage = {"weather": "contributing", "earthquake": "contributing"}
    res1, _ = compute_fusion_at_location(
        records=base_records,
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )

    # Add an earthquake record
    additional_record = make_record("r2", "earthquake", "usgs", severity_raw=6.0)
    res2, _ = compute_fusion_at_location(
        records=base_records + [additional_record],
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )

    # Safety score with 2 hazards must be <= safety score with 1 hazard
    assert res2.safety_score <= res1.safety_score
    # Total risk S_total must be >=
    assert res2.S_total >= res1.S_total


def test_strong_signal_not_diluted_by_adding_weak_ones(fusion_cfg):
    """Noisy-OR property: A strong signal is not diluted by adding multiple weak signals."""
    strong_record = make_record("strong1", "flood", "gdacs", severity_raw="Red", confidence=0.95)
    coverage = {"flood": "contributing", "news": "contributing"}

    res_strong_only, _ = compute_fusion_at_location(
        records=[strong_record],
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )

    # In weighted average, adding 10 very weak signals (e.g. 0.05) would drag a 0.90 down.
    # In Noisy-OR, S_total must remain AT LEAST as high as S_total of the strong signal.
    weak_records = [
        make_record(f"weak_{i}", "news", "gdelt", severity_raw={"count": 1, "tone_severity": 0.05, "confidence": 0.5})
        for i in range(10)
    ]

    res_combined, _ = compute_fusion_at_location(
        records=[strong_record] + weak_records,
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )

    assert res_combined.S_total >= res_strong_only.S_total
    assert res_combined.safety_score <= res_strong_only.safety_score


def test_missing_source_excluded_and_appears_in_coverage(fusion_cfg):
    """Missing or failed data sources are excluded from calculation and reported in coverage."""
    # When gdacs failed, it is in coverage as "source_failed" and not treated as sigma=0 safe
    coverage = {
        "flood": "source_failed",
        "earthquake": "source_failed",
        "landslide": "not_available_for_region",
        "weather": "no_signal_found",
    }
    # No records for failed sources
    result, _ = compute_fusion_at_location(
        records=[],
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )
    assert result.coverage["flood"] == "source_failed"
    assert result.coverage["earthquake"] == "source_failed"
    assert result.coverage["landslide"] == "not_available_for_region"
    # Because most major sources failed, confidence label should drop to "low"
    assert result.confidence_label == "low"


def test_contributions_sum_to_one(fusion_cfg):
    """Contributions must sum to 1.0 (within 1e-2 rounding) when active hazards exist."""
    records = [
        make_record("r1", "earthquake", "usgs", severity_raw=5.8),
        make_record("r2", "conflict", "acled", severity_raw={"fatalities": 3, "event_type": "protest"}),
        make_record("r3", "weather", "open_meteo", severity_raw={"rainfall_mm_24h": 70.0, "wind_speed_kmh": 50.0}),
    ]
    coverage = {"earthquake": "contributing", "conflict": "contributing", "weather": "contributing"}
    result, _ = compute_fusion_at_location(
        records=records,
        target_lat=28.6139,
        target_lon=77.2090,
        target_district_id=None,
        coverage=coverage,
        config=fusion_cfg,
    )

    assert len(result.top_contributions) == 3
    contrib_sum = sum(c.contribution for c in result.top_contributions)
    assert math.isclose(contrib_sum, 1.0, abs_tol=0.01)
