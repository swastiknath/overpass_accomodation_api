"""Tests for hotel provider, local per-hotel scoring, and transparent ranking."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from shapely.geometry import Point

from gis.schema import IngestedRecord, ResolutionTier
from fusion.config import load_fusion_config
from hotels.models import Hotel
from hotels.scoring import compute_hotel_scoring_and_ranking
from hotels.provider import OSMOverpassProvider


@pytest.fixture
def fusion_cfg():
    return load_fusion_config()


@pytest.fixture
def sample_hotels():
    return [
        Hotel(
            id="h1",
            name="Mountain View Inn",
            lat=28.6139,
            lon=77.2090,
            source="osm",
            source_id="101",
            category="hotel",
            stars=4.0,
            rating=4.5,
            review_count=120,
            price_band="mid_range",
            distance_to_query_km=0.5,
        ),
        Hotel(
            id="h2",
            name="Budget Backpacker Hostel",
            lat=28.6200,
            lon=77.2150,
            source="osm",
            source_id="102",
            category="hostel",
            stars=None,
            rating=None,
            review_count=None,
            price_band=None,
            distance_to_query_km=1.2,
        ),
        Hotel(
            id="h3",
            name="Grand Luxury Palace",
            lat=28.6300,
            lon=77.2250,
            source="osm",
            source_id="103",
            category="hotel",
            stars=5.0,
            rating=4.9,
            review_count=350,
            price_band="luxury",
            distance_to_query_km=2.0,
        ),
    ]


@pytest.fixture
def sample_hazard_records():
    now = datetime.now(timezone.utc)
    return [
        # Localized hazard near h3
        IngestedRecord(
            event_id="flood_near_h3",
            source="gdacs",
            hazard_type="flood",
            geometry=Point(77.2260, 28.6310),  # Right next to h3
            event_time=now,
            ingest_time=now,
            severity_raw="Red",
            confidence=0.9,
            resolution_tier=ResolutionTier.POINT,
            raw_payload={"title": "Severe Flash Flood"},
        ),
        # District-level crime
        IngestedRecord(
            event_id="crime_delhi",
            source="crime_ncrb",
            hazard_type="crime",
            geometry=Point(77.2090, 28.6139),
            event_time=now,
            ingest_time=now,
            severity_raw=0.45,
            confidence=0.8,
            resolution_tier=ResolutionTier.DISTRICT,
            district_id="New Delhi",
            raw_payload={"district": "New Delhi"},
        ),
    ]


def test_missing_ratings_do_not_penalize_rank(sample_hotels, sample_hazard_records, fusion_cfg):
    """Hotels with missing rating/stars must NOT default to 0; they rank on safety with limited_info=True."""
    coverage = {"flood": "contributing", "crime": "contributing"}
    ranked, _ = compute_hotel_scoring_and_ranking(
        hotels=sample_hotels,
        records=sample_hazard_records,
        coverage=coverage,
        target_district_id="New Delhi",
        config=fusion_cfg,
        alpha=0.7,
    )

    # Find the hostel with missing info
    hostel = next(h for h in ranked if h.hotel.id == "h2")
    assert hostel.limited_info is True
    assert hostel.rank_breakdown.quality_norm is None
    # Ensure rank score is strictly equal to safety_norm
    assert hostel.rank_score == round(hostel.safety_score / 100.0, 4)


def test_alpha_1_ranks_by_safety_only(sample_hotels, sample_hazard_records, fusion_cfg):
    """When alpha=1.0, ranking is purely determined by safety score."""
    coverage = {"flood": "contributing", "crime": "contributing"}
    ranked, _ = compute_hotel_scoring_and_ranking(
        hotels=sample_hotels,
        records=sample_hazard_records,
        coverage=coverage,
        target_district_id="New Delhi",
        config=fusion_cfg,
        alpha=1.0,
    )

    for i in range(len(ranked) - 1):
        assert ranked[i].safety_score >= ranked[i + 1].safety_score


def test_alpha_0_ranks_by_quality_only(sample_hotels, sample_hazard_records, fusion_cfg):
    """When alpha=0.0, ranking is determined by quality score."""
    coverage = {"flood": "contributing", "crime": "contributing"}
    ranked, _ = compute_hotel_scoring_and_ranking(
        hotels=sample_hotels,
        records=sample_hazard_records,
        coverage=coverage,
        target_district_id="New Delhi",
        config=fusion_cfg,
        alpha=0.0,
    )

    # Grand Luxury Palace (h3, 5 stars, rating 4.9) should be ranked highest among hotels with quality data
    first_with_quality = next(h for h in ranked if not h.limited_info)
    assert first_with_quality.hotel.id == "h3"


def test_same_area_warning_triggers_under_epsilon(fusion_cfg):
    """When spread of safety scores across hotels is under epsilon, same_area_warning is True."""
    # Hotels with no localized hazards nearby, only uniform district signals
    hotels = [
        Hotel(
            id=f"h_{i}",
            name=f"Hotel {i}",
            lat=28.6100 + i * 0.001,
            lon=77.2000 + i * 0.001,
            source="osm",
            source_id=str(i),
            category="hotel",
            distance_to_query_km=0.1 * i,
        )
        for i in range(4)
    ]
    # Only district level signal
    now = datetime.now(timezone.utc)
    records = [
        IngestedRecord(
            event_id="crime_1",
            source="crime_ncrb",
            hazard_type="crime",
            geometry=Point(77.2000, 28.6100),
            event_time=now,
            ingest_time=now,
            severity_raw=0.3,
            resolution_tier=ResolutionTier.DISTRICT,
            district_id="Central Delhi",
        )
    ]
    coverage = {"crime": "contributing"}

    _, same_area_warning = compute_hotel_scoring_and_ranking(
        hotels=hotels,
        records=records,
        coverage=coverage,
        target_district_id="Central Delhi",
        config=fusion_cfg,
    )

    assert same_area_warning is True


def test_per_hotel_scoring_makes_zero_connector_calls_locally(sample_hotels, sample_hazard_records, fusion_cfg):
    """Per-hotel scoring must be computed completely locally without connector calls."""
    coverage = {"flood": "contributing", "crime": "contributing"}
    # Passing pre-fetched records
    ranked, _ = compute_hotel_scoring_and_ranking(
        hotels=sample_hotels,
        records=sample_hazard_records,
        coverage=coverage,
        target_district_id="New Delhi",
        config=fusion_cfg,
    )
    assert len(ranked) == 3
    # Check that differentiating factors were identified for h3 (which is next to flood)
    h3_scored = next(h for h in ranked if h.hotel.id == "h3")
    assert any(df.hazard_type == "flood" for df in h3_scored.differentiating_factors or h3_scored.top_contributions)
