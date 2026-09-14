"""
Unit and Integration Test Suite for Hotels API and Pipeline.
"""

import pytest
import pandas as pd
from hotels_api.models import HotelProperty, TourismType, PriceTier
from hotels_api.geoutils import haversine_distance_meters, encode_geohash, bbox_contains
from hotels_api.tag_parser import parse_osm_element
from hotels_api.storage import HotelStorage
from hotels_api.fetcher import OverpassFetcher


def test_geoutils():
    # Distance between New Delhi (28.6139, 77.2090) and Mumbai (19.0760, 72.8777) ~ 1150km
    d = haversine_distance_meters(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1_100_000 < d < 1_200_000

    # Geohash test
    gh = encode_geohash(28.6139, 77.2090, precision=6)
    assert isinstance(gh, str)
    assert len(gh) == 6

    # BBox test
    assert bbox_contains(28.5, 77.1, 28.0, 77.0, 29.0, 78.0) is True
    assert bbox_contains(30.5, 77.1, 28.0, 77.0, 29.0, 78.0) is False


def test_tag_parser():
    mock_el = {
        "id": 123456,
        "type": "node",
        "lat": 29.95,
        "lon": 78.15,
        "tags": {
            "name": "Grand Himalayan Resort & Spa",
            "tourism": "resort",
            "stars": "5",
            "addr:street": "Ganga Path",
            "addr:city": "Rishikesh",
            "addr:state": "Uttarakhand",
            "addr:postcode": "249201",
            "phone": "+91 98765 43210",
            "website": "https://grandhimalayan.example.com",
            "internet_access": "wlan",
            "swimming_pool": "yes",
            "parking": "yes",
            "air_conditioning": "yes",
            "restaurant": "yes",
            "spa": "yes",
            "gym": "yes",
            "wheelchair": "yes",
            "dogs": "yes",
            "rooms": "45",
        }
    }

    prop = parse_osm_element(mock_el, default_region="rishikesh_haridwar")
    assert prop is not None
    assert prop.hotel_id == "osm_node_123456"
    assert prop.name == "Grand Himalayan Resort & Spa"
    assert prop.property_type == TourismType.RESORT
    assert prop.stars == 5.0
    assert prop.city == "Rishikesh"
    assert prop.has_wifi is True
    assert prop.has_pool is True
    assert prop.has_parking is True
    assert prop.has_spa is True
    assert prop.has_gym is True
    assert prop.is_pet_friendly is True
    assert prop.is_wheelchair_accessible is True
    assert prop.rooms_count == 45
    assert prop.price_tier == PriceTier.LUXURY


def test_storage_indexing_and_search(tmp_path):
    storage = HotelStorage(data_dir=str(tmp_path))

    # Create dummy properties
    p1 = HotelProperty(
        hotel_id="test_1",
        name="Goa Beach Resort",
        property_type=TourismType.RESORT,
        latitude=15.2993,
        longitude=74.1240,
        geohash="tdyv87u",
        region="goa",
        city="Margao",
        stars=4.0,
        price_min=120.0,
        price_max=220.0,
        price_tier=PriceTier.UPSCALE,
        has_wifi=True,
        has_pool=True,
        has_parking=True,
        has_air_conditioning=True,
    )

    p2 = HotelProperty(
        hotel_id="test_2",
        name="Backpacker Hostel Rishikesh",
        property_type=TourismType.HOSTEL,
        latitude=30.0869,
        longitude=78.2676,
        geohash="ttp5x7z",
        region="rishikesh_haridwar",
        city="Rishikesh",
        stars=2.0,
        price_min=15.0,
        price_max=30.0,
        price_tier=PriceTier.BUDGET,
        has_wifi=True,
        has_pool=False,
        has_parking=False,
        has_air_conditioning=False,
    )

    storage.load_from_properties([p1, p2])
    assert len(storage.df) == 2

    # Test Search
    items, total = storage.search(query="Beach", min_stars=3.0)
    assert total == 1
    assert items[0].name == "Goa Beach Resort"

    # Test Proximity Radius Query (within 50km of Goa)
    nearby = storage.query_radius(15.30, 74.12, radius_meters=50_000)
    assert len(nearby) == 1
    assert nearby[0].hotel_id == "test_1"

    # Test Summary
    summary = storage.get_summary()
    assert summary.total_records == 2
    assert summary.regions_count == 2
    assert summary.amenities_coverage["wifi_pct"] == 100.0

    # Test Export
    exports = storage.export_all(base_filename="test_export")
    assert "csv" in exports
    assert "parquet" in exports
    assert "sqlite" in exports


def test_overpass_query_builder():
    fetcher = OverpassFetcher()
    query = fetcher.build_bbox_query(29.85, 78.10, 30.20, 78.40)
    assert "out center tags;" in query
    assert "tourism" in query
    assert "29.85,78.1,30.2,78.4" in query.replace(" ", "")


def test_api_endpoints():
    from fastapi.testclient import TestClient
    from hotels_api.main import app
    from hotels_api.storage import storage_instance
    from hotels_api.models import HotelProperty, TourismType, PriceTier

    client = TestClient(app)

    # Health check
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

    # Regions check
    res = client.get("/api/v1/regions")
    assert res.status_code == 200
    assert res.json()["count"] > 0

    # Populate storage with sample data for API testing
    sample_prop = HotelProperty(
        hotel_id="osm_node_9999",
        name="Taj Exotica Resort",
        property_type=TourismType.RESORT,
        latitude=15.25,
        longitude=73.95,
        geohash="tdyv123",
        region="goa",
        city="Benaulim",
        stars=5.0,
        price_min=250.0,
        price_max=500.0,
        price_tier=PriceTier.LUXURY,
        has_wifi=True,
        has_pool=True,
        has_spa=True
    )
    storage_instance.load_from_properties([sample_prop])

    # Search API
    res = client.get("/api/v1/hotels/search?q=Taj&min_stars=4")
    assert res.status_code == 200
    search_data = res.json()
    assert search_data["total"] >= 1
    assert search_data["items"][0]["name"] == "Taj Exotica Resort"

    # Get Single Hotel
    res = client.get("/api/v1/hotels/osm_node_9999")
    assert res.status_code == 200
    assert res.json()["name"] == "Taj Exotica Resort"

    # Summary API
    res = client.get("/api/v1/dataframe/summary")
    assert res.status_code == 200
    assert res.json()["total_records"] >= 1

    # Export API (JSON)
    res = client.get("/api/v1/dataframe/export?format=json")
    assert res.status_code == 200
    assert "Taj Exotica Resort" in res.text

