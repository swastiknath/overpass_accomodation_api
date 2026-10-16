"""API integration tests for geocoding, search-report, explanation, and error handling."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config import Settings, load_settings


@pytest.fixture
def client():
    # Force DEMO_MODE=True for API integration testing
    s = load_settings()
    s.demo_mode = True
    return TestClient(app)


def test_health_endpoint(client):
    """GET /v1/health returns healthy status."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "config_version" in data


def test_sources_endpoint(client):
    """GET /v1/sources returns data catalog and licensing information."""
    resp = client.get("/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    assert any(s["id"] == "gdacs" for s in data["sources"])
    assert any(s["id"] == "acled" for s in data["sources"])


def test_geocode_success(client):
    """GET /v1/geocode returns Indian location candidates."""
    resp = client.get("/v1/geocode?q=Manali")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    first = data[0]
    assert "Manali" in first["display_name"]
    assert first["is_in_india"] is True
    assert first["bbox"] is not None


def test_geocode_no_results(client):
    """GET /v1/geocode with an obscure query returns an empty list gracefully."""
    # When geocoder returns empty list
    resp = client.get("/v1/geocode?q=xyz999999notaplace")
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_report_out_of_india(client):
    """GET /v1/search-report with coordinates outside India returns HTTP 400 out_of_coverage."""
    # Paris, France coordinates (48.8566, 2.3522)
    resp = client.get("/v1/search-report?lat=48.8566&lon=2.3522")
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "out_of_coverage"
    assert data["is_in_india"] is False


def test_search_report_full_success_demo_mode(client):
    """GET /v1/search-report in DEMO_MODE returns complete deterministic report."""
    resp = client.get("/v1/search-report?q=Manali&radius_km=5&alpha=0.7&max_hotels=10")
    assert resp.status_code == 200
    data = resp.json()

    assert data["demo"] is True
    assert "report_id" in data
    assert "area_score" in data
    assert 0 <= data["area_score"]["safety_score"] <= 100
    assert "band" in data["area_score"]
    assert "label" in data["area_score"]["band"]

    assert "contributions" in data
    assert "coverage" in data
    assert "sources" in data

    # GeoJSON FeatureCollection
    assert data["geojson"]["type"] == "FeatureCollection"
    assert len(data["geojson"]["features"]) > 0

    # Hotels
    assert "hotels_ranked" in data
    assert len(data["hotels_ranked"]) > 0
    first_hotel = data["hotels_ranked"][0]
    assert "rank_score" in first_hotel
    assert "access_to_help" in first_hotel
    assert "disclaimer" in data


def test_explanation_endpoint_success(client):
    """POST /v1/explanation on cached report returns verified narrative and curated advice."""
    # 1. Generate search report first to populate cache
    rep_resp = client.get("/v1/search-report?q=Manali")
    assert rep_resp.status_code == 200
    report_id = rep_resp.json()["report_id"]

    # 2. Call explanation endpoint
    exp_resp = client.post("/v1/explanation", json={"report_id": report_id})
    assert exp_resp.status_code == 200
    data = exp_resp.json()

    assert "narrative_status" in data
    assert data["narrative_status"] in ("verified", "fallback_template")
    assert "narrative" in data
    assert "headline" in data["narrative"]
    assert "summary" in data["narrative"]
    assert "curated_advice" in data
    assert len(data["curated_advice"]) > 0
