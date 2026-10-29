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
    assert "Delhi Railway Bridge" in delhi["cwc_station"]
    assert delhi["cwc_station_code"] == "015-UYDDEL"
    assert delhi["warning_level_m"] == 204.50
    assert delhi["danger_level_m"] == 205.33
    assert "NCS" in delhi["seismic_authority"]
    assert "FSI" in delhi["fire_authority"]
    assert "Central Water Commission" in delhi["flood_authority"]

    manali = resolve_india_river_and_authority_profile("Manali, Kullu, Himachal Pradesh, India", state="Himachal Pradesh", lat=32.2396, lon=77.1887)
    assert "Beas" in manali["river_name"]
    assert "Manali" in manali["cwc_station"] or "Kullu" in manali["cwc_station"]
    assert manali["cwc_station_code"] == "SHD00001"
    assert "Zone V" in manali["seismic_zone"]
    assert "FSI Vanagni" in manali["fire_authority"]
    assert manali["has_river_in_city"] is True
    assert "Beas River" in manali["rivers_in_city"]

    # Test city with no river situated within municipal limits (e.g., ridge town Shimla)
    shimla = resolve_india_river_and_authority_profile("Shimla, Himachal Pradesh, India", state="Himachal Pradesh", lat=31.1048, lon=77.1734)
    assert shimla["has_river_in_city"] is False
    assert len(shimla["rivers_in_city"]) == 0
    assert shimla["cwc_station_code"] is None

    guwahati = resolve_india_river_and_authority_profile("Guwahati, Assam, India", state="Assam", lat=26.1445, lon=91.7362)
    assert "Brahmaputra" in guwahati["river_name"]
    assert guwahati["cwc_station_code"] == "001-MBDGHY"
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
    assert telemetry["cwc_station_code"] == "015-UYDDEL"
    assert telemetry["current_water_level_m"] > 190.0
    assert telemetry["danger_level_m"] == 205.33
    assert telemetry["current_discharge_m3s"] > 0
    assert telemetry["current_discharge_cusecs"] > 0
    assert len(telemetry["forecast_15day"]) >= 7
    assert "floodwatch_india" in telemetry
    fw = telemetry["floodwatch_india"]
    assert fw["source_portal"] == "https://ffs.india-water.gov.in"
    assert fw["station_code"] == "015-UYDDEL"
    if fw["live_cwc_telemetry"]:
        assert fw["observed_water_level_m"] is not None
        assert abs(telemetry["current_water_level_m"] - fw["observed_water_level_m"]) < 0.05
        assert len(fw["hourly_readings"]) >= 1
    assert "NCS" in telemetry["authorities"]["earthquake"]
    assert "FSI" in telemetry["authorities"]["wildfire"]
    assert "Central Water Commission" in telemetry["authorities"]["flood"]
    assert any(r.source == "cwc_ffs" for r in records)
    cwc_rec = next(r for r in records if r.source == "cwc_ffs")
    assert cwc_rec.raw_payload.get("cwc_station_code") == "015-UYDDEL"


def test_historical_stats_uses_indian_authorities_for_indian_cities():
    mock_river_telemetry = {
        "is_in_india": True,
        "has_river_in_city": True,
        "rivers_in_city": ["Beas River", "Manalsu River"],
        "river_name": "Beas River, Manalsu River",
        "cwc_station": "Kullu–Manali Beas CWC Hydrological Station",
        "cwc_station_code": "SHD00001",
        "current_water_level_m": 1174.34,
        "danger_level_m": 1176.5,
        "current_discharge_m3s": 128.4,
        "current_stage": "normal",
        "historical_flow_stats": {
            "timeframe": "2021 – 2026",
            "total_observed_days": 2128,
            "mean_discharge_m3s": 84.5,
            "peak_discharge_m3s": 420.0,
            "p90_watch_discharge_m3s": 150.0,
            "p98_danger_discharge_m3s": 290.0,
            "peak_date": "2023-07-09",
            "flow_anomaly_pct": 51.9,
            "yearly_flow_trends": [
                {"year": "2021", "peak_discharge_m3s": 280.0, "high_flow_days": 3},
                {"year": "2022", "peak_discharge_m3s": 310.0, "high_flow_days": 4},
                {"year": "2023", "peak_discharge_m3s": 420.0, "high_flow_days": 8},
                {"year": "2024", "peak_discharge_m3s": 240.0, "high_flow_days": 2},
                {"year": "2025", "peak_discharge_m3s": 260.0, "high_flow_days": 3},
                {"year": "2026", "peak_discharge_m3s": 190.0, "high_flow_days": 1},
            ],
        },
        "indian_authority_bulletins": [
            {
                "id": "cwc-b-1",
                "hazard_type": "flood",
                "title": "Central Water Commission Special Advisory: High Inflow Monitored in Beas Basin",
                "authority": "Central Water Commission (CWC)",
                "date": "2026-10-25",
                "severity": "Moderate",
                "url": "https://ffs.india-water.gov.in",
            },
            {
                "id": "fsi-b-1",
                "hazard_type": "fire",
                "title": "Forest Survey of India: Vanagni FAST Fire Precaution Alert for Kullu Circle",
                "authority": "Forest Survey of India (FSI Vanagni)",
                "date": "2026-10-24",
                "severity": "Low",
                "url": "https://fsi.nic.in",
            },
        ],
        "ncs_recent_earthquakes": [
            {
                "id": "ncs-2026-001",
                "magnitude": 4.2,
                "depth_km": 10.0,
                "place": "Kullu, Himachal Pradesh",
                "distance_km": 28.0,
                "event_time": "2026-10-26T04:12:00",
                "authority": "National Centre for Seismology (NCS, MoES)",
            }
        ],
    }

    mock_cyclone = {
        "active_alert_status": "NO ACTIVE CYCLONE",
        "historical_archive": {
            "timeframe": "2021 – 2026",
            "total_archived_days": 2126,
            "max_historical_wind_gust_kmh": 68.4,
            "max_historical_wind_date": "2023-07-09",
            "yearly_trends": [
                {"year": "2021", "cyclonic_storm_days": 0, "max_wind_gust_kmh": 54.0},
                {"year": "2022", "cyclonic_storm_days": 0, "max_wind_gust_kmh": 58.2},
                {"year": "2023", "cyclonic_storm_days": 1, "max_wind_gust_kmh": 68.4},
                {"year": "2024", "cyclonic_storm_days": 0, "max_wind_gust_kmh": 52.1},
                {"year": "2025", "cyclonic_storm_days": 0, "max_wind_gust_kmh": 49.0},
                {"year": "2026", "cyclonic_storm_days": 0, "max_wind_gust_kmh": 46.5},
            ],
            "notable_events": [
                {
                    "date": "2023-07-09",
                    "peak_wind_gust_kmh": 68.4,
                    "max_sustained_wind_kmh": 44.0,
                    "min_pressure_hpa": 988.2,
                    "rainfall_mm": 112.5,
                    "imd_category": "Deep Depression",
                }
            ],
        },
    }

    stats = compute_historical_stats(
        location_name="Manali, Kullu, Himachal Pradesh, India",
        lat=32.2396,
        lon=77.1887,
        country="India",
        is_in_india=True,
        river_flood_telemetry=mock_river_telemetry,
        cyclone_telemetry=mock_cyclone,
    )
    categories = [d["category"] for d in stats["disaster_breakdown"]]
    assert any("River High-Flow Episodes" in c or "Beas" in c for c in categories)
    assert any("USGS / NCS Earthquakes" in c for c in categories)
    assert any("Cyclonic Storms" in c or "ERA5" in c for c in categories)

    sources = [inc["source"] for inc in stats["incident_log"] if inc["category"] == "disaster"]
    assert any("Central Water Commission" in s or "CWC" in s or "GloFAS" in s for s in sources)
    assert any("National Centre for Seismology" in s or "NCS" in s for s in sources)
    assert any("Forest Survey of India" in s or "FSI" in s for s in sources)


@pytest.mark.asyncio
async def test_cyclone_telemetry_client():
    from connectors.cyclone_client import CycloneTelemetryClient

    client = CycloneTelemetryClient()
    # Test for coastal Indian city with active Bay of Bengal / Arabian Sea cyclone tracking
    telemetry, records = await client.fetch_cyclone_telemetry_async(
        lat=17.6868,
        lon=83.2185,
        location_name="Visakhapatnam, Andhra Pradesh, India",
        is_in_india=True,
    )
    assert telemetry["is_in_india"] is True
    assert "realtime_conditions" in telemetry
    curr = telemetry["realtime_conditions"]
    assert curr["wind_gust_kmh"] >= 0
    assert curr["sea_level_pressure_hpa"] > 950.0
    assert "imminent_outlook" in telemetry
    outlook = telemetry["imminent_outlook"]
    assert len(outlook["forecast_15day"]) >= 10
    assert "historical_archive" in telemetry
    hist = telemetry["historical_archive"]
    assert hist["total_archived_days"] > 1000
    assert len(hist["yearly_trends"]) >= 5
    assert "India Meteorological Department" in telemetry["monitoring_authority"]



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

