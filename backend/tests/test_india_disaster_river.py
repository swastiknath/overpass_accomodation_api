"""Tests for Indian local authority disaster telemetry (NCS Earthquake, FSI Wildfire, CWC Flood)
and Indian river water level & flood predictions.
"""

from __future__ import annotations

import pytest
from connectors.india_disaster_river_client import (
    IndiaDisasterAndRiverClient,
    resolve_india_river_and_authority_profile,
)
from analytics.historical_service import compute_historical_stats
from llm.explainer import LLMExplainer


def test_resolve_india_river_and_authority_profile_cities():
    delhi = resolve_india_river_and_authority_profile("New Delhi, Delhi, India", state="Delhi", lat=28.6139, lon=77.2090)
    assert "Yamuna" in delhi["river_name"]
    assert "Old Railway Bridge" in delhi["cwc_station"]
    assert delhi["warning_level_m"] == 204.50
    assert delhi["danger_level_m"] == 205.33
    assert "NCS" in delhi["seismic_authority"]
    assert "FSI" in delhi["fire_authority"]
    assert "Central Water Commission" in delhi["flood_authority"]

    manali = resolve_india_river_and_authority_profile("Manali, Kullu, Himachal Pradesh, India", state="Himachal Pradesh", lat=32.2396, lon=77.1887)
    assert "Beas" in manali["river_name"]
    assert "Bhuntar" in manali["cwc_station"]
    assert "Zone V" in manali["seismic_zone"]
    assert "FSI Vanagni" in manali["fire_authority"]

    guwahati = resolve_india_river_and_authority_profile("Guwahati, Assam, India", state="Assam", lat=26.1445, lon=91.7362)
    assert "Brahmaputra" in guwahati["river_name"]
    assert "ASDMA" in guwahati["sdma_name"]


@pytest.mark.asyncio
async def test_fetch_india_hazards_and_river_async():
    client = IndiaDisasterAndRiverClient()
    telemetry, records = await client.fetch_india_hazards_and_river_async(
        lat=28.6139,
        lon=77.2090,
        location_name="New Delhi, Delhi, India",
        district_id="New Delhi",
        state="Delhi",
    )
    assert telemetry["is_in_india"] is True
    assert "Yamuna" in telemetry["river_name"]
    assert telemetry["current_water_level_m"] > 190.0
    assert telemetry["danger_level_m"] == 205.33
    assert telemetry["current_discharge_m3s"] > 0
    assert telemetry["current_discharge_cusecs"] > 0
    assert len(telemetry["forecast_15day"]) >= 7
    assert "NCS" in telemetry["authorities"]["earthquake"]
    assert "FSI" in telemetry["authorities"]["wildfire"]
    assert "Central Water Commission" in telemetry["authorities"]["flood"]


def test_historical_stats_uses_indian_authorities_for_indian_cities():
    stats = compute_historical_stats(
        location_name="Manali, Kullu, Himachal Pradesh, India",
        lat=32.2396,
        lon=77.1887,
        country="India",
        is_in_india=True,
    )
    categories = [d["category"] for d in stats["disaster_breakdown"]]
    assert any("CWC River Flood" in c for c in categories)
    assert any("NCS Seismology" in c for c in categories)
    assert any("FSI Vanagni Wildfires" in c for c in categories)

    sources = [inc["source"] for inc in stats["incident_log"] if inc["category"] == "disaster"]
    assert any("Central Water Commission" in s or "CWC" in s for s in sources)
    assert any("National Centre for Seismology" in s or "NCS" in s for s in sources)
    assert any("Forest Survey of India" in s or "FSI" in s for s in sources)


def test_explainer_curated_advice_uses_indian_authorities_for_indian_cities():
    explainer = LLMExplainer()
    mock_india_report = {
        "location": {
            "display_name": "Rishikesh, Uttarakhand, India",
            "lat": 30.0869,
            "lon": 78.2676,
            "state": "Uttarakhand",
            "country": "India",
            "is_in_india": True,
        },
        "is_in_india": True,
        "contributions": [
            {"hazard_type": "flood", "weight": 0.5, "sigma": 0.4},
        ],
    }
    advice_items = explainer._get_curated_advice_for_report(mock_india_report)
    hazard_types = {item.hazard_type for item in advice_items}
    assert {"flood", "earthquake", "fire"}.issubset(hazard_types)

    flood_item = next(i for i in advice_items if i.hazard_type == "flood")
    assert "Ganga" in flood_item.hazard_name
    assert any("CWC" in tip for tip in flood_item.tips)
    assert any("Central Water Commission" in a.name for a in flood_item.authorities)

    eq_item = next(i for i in advice_items if i.hazard_type == "earthquake")
    assert any("National Centre for Seismology" in a.name for a in eq_item.authorities)

    fire_item = next(i for i in advice_items if i.hazard_type == "fire")
    assert any("Forest Survey of India" in a.name for a in fire_item.authorities)

