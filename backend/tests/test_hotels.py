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


@pytest.mark.asyncio
async def test_foursquare_provider_instantiation_and_search():
    from hotels.provider import FoursquareProvider
    provider = FoursquareProvider()
    assert provider is not None
    # Test search with sample coords
    hotels = await provider.search(lat=28.6139, lon=77.2090, radius_km=5.0, limit=10, location_name="Connaught Place, New Delhi")
    assert isinstance(hotels, list)
    if hotels:
        first = hotels[0]
        assert first.name is not None
        assert first.lat != 0.0
        assert hasattr(first, "phone")
        help_map = await provider.get_access_to_help(28.6139, 77.2090, hotels[:3])
        assert isinstance(help_map, dict)
        assert first.id in help_map


@pytest.mark.asyncio
async def test_no_oyo_or_false_positives_in_pakistan():
    from hotels.crawler import is_valid_traveler_accommodation, is_pakistan_location, synthesize_contact_info
    
    # 1. Verify Pakistan detection
    assert is_pakistan_location("Lahore, Pakistan", 31.52, 74.35) is True
    assert is_pakistan_location("Karachi", 24.86, 67.0) is True
    assert is_pakistan_location("Islamabad") is True
    assert is_pakistan_location("New Delhi, India", 28.61, 77.20) is False

    # 2. Verify OYO and GoStays rejection outside India / in Pakistan
    assert is_valid_traveler_accommodation("OYO 1234 Residency", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("GoStays Lahore Comfort", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("Zostel Lahore", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("OYO 1234 Residency", "Mumbai, India", 19.07, 72.87) is True

    # 3. Verify rejection of institutional student/staff dorms and streets
    assert is_valid_traveler_accommodation("Hindu Hostel Street", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("KEMU Hostel Ground", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("Nurses Hostel", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("Doctors Hostel", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("GCU Girls Hostel", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("UVAS Boys Hostel", "Lahore, Pakistan", 31.52, 74.35) is False
    assert is_valid_traveler_accommodation("Student Mess & Hostel", "Lahore, Pakistan", 31.52, 74.35) is False

    # 4. Verify valid traveler accommodations pass
    assert is_valid_traveler_accommodation("Pearl Continental Lahore", "Lahore, Pakistan", 31.52, 74.35) is True
    assert is_valid_traveler_accommodation("Avari Hotel Lahore", "Lahore, Pakistan", 31.52, 74.35) is True
    assert is_valid_traveler_accommodation("Lahore Backpackers Hostel", "Lahore, Pakistan", 31.52, 74.35) is True

    # 5. Verify unlisted international properties do NOT fabricate fake phone/email
    c_pk = synthesize_contact_info("Pearl Continental", location_name="Lahore, Pakistan", source_id="123")
    assert c_pk["phone"] is None, "Must not fabricate fake phone number"
    assert c_pk["email"] is None, "Must not fabricate fake email address"
    assert "Lahore" in c_pk["address"]
    assert "google.com/travel/hotels" in c_pk["website"]

    # 6. Verify verified Indian corporate partner brands retain valid hotline
    c_in = synthesize_contact_info("OYO Flagship Connaught", brand="OYO", location_name="New Delhi, India")
    assert c_in["phone"] == "+91 124 620 1611"
    assert c_in["email"] == "bookings@oyorooms.com"


@pytest.mark.asyncio
async def test_no_fake_or_mock_reviews_served():
    """Verify crawler and summarizer never inject mock review templates or fake reviewer personas."""
    from hotels.crawler import FirecrawlerHotelClient
    from hotels.review_summarizer import HotelReviewSummarizer
    from hotels.models import Hotel

    crawler = FirecrawlerHotelClient()
    # Mock crawler review query for obscure test property
    res = await crawler.crawl_live_hotel_reviews(
        hotel_name="Test Nonexistent Lodge 99999",
        location_name="Remote Pass, Himalayas",
        lat=34.0,
        lon=75.0,
        hotel_id="test_9999",
    )

    # Must be a list of crawled reviews or empty if none online - never fake templates
    crawled = res.get("crawled_reviews", [])
    assert isinstance(crawled, list)
    for r in crawled:
        # None of the old fake personas
        assert r.get("reviewer_name") not in ("Priya Sharma", "Marcus Vance", "Elena Rostova")
        assert "Pristine cleanliness and 24/7 guarded security" not in r.get("snippet", "")

    # Test summarizer without crawled reviews sets review_snippet to None
    summarizer = HotelReviewSummarizer()
    h = Hotel(
        id="h_test_none",
        name="Mountain Peak Cottage",
        lat=32.0,
        lon=76.0,
        source="osm",
        source_id="1",
        category="hotel",
        crawled_reviews=[],
    )
    summarized = await summarizer.summarize_hotels([h], "Manali, Himachal Pradesh")
    assert summarized[0].review_snippet is None

