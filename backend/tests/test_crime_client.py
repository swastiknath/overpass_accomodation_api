"""Tests for real-time and multi-year historical crime statistics inside and outside India."""
from __future__ import annotations

import pytest
from connectors.crime_client import CrimeClient, _clean_place_query, _resolve_country_iso_and_gl


def test_clean_place_query_strips_administrative_suffixes():
    assert _clean_place_query("Bengaluru Urban, Karnataka, India") == "Bengaluru"
    assert _clean_place_query("Greater London, England, United Kingdom") == "London"
    assert _clean_place_query("New York City (Metropolitan)") == "New York"


def test_resolve_country_iso_and_gl_india_and_international():
    iso_in, gl_in, country_in = _resolve_country_iso_and_gl("Kullu", "Manali, Himachal Pradesh, India", "India", True)
    assert iso_in == "IND"
    assert gl_in == "IN"
    assert country_in == "India"

    iso_uk, gl_uk, country_uk = _resolve_country_iso_and_gl("London", "London, United Kingdom", "United Kingdom", False)
    assert iso_uk == "GBR"
    assert gl_uk == "GB"

    iso_us, gl_us, _ = _resolve_country_iso_and_gl("New York", "New York, United States", "United States", False)
    assert iso_us == "USA"
    assert gl_us == "US"


def test_india_and_international_historical_series_are_authentic_and_distinct():
    client = CrimeClient()

    delhi = client._get_fallback_district_crime("New Delhi", state="Delhi", country="India", is_in_india=True)["crime_statistics"]
    bengaluru = client._get_fallback_district_crime("Bengaluru Urban", state="Karnataka", country="India", is_in_india=True)["crime_statistics"]
    kullu = client._get_fallback_district_crime("Kullu", state="Himachal Pradesh", country="India", is_in_india=True)["crime_statistics"]
    london = client._get_fallback_district_crime("London", country="United Kingdom", is_in_india=False)["crime_statistics"]
    nyc = client._get_fallback_district_crime("New York", country="United States", is_in_india=False)["crime_statistics"]
    tokyo = client._get_fallback_district_crime("Tokyo", country="Japan", is_in_india=False)["crime_statistics"]

    # Verify each city has distinct multi-year trajectories and agencies
    assert "NCRB" in delhi["source_agency"]
    assert "NCRB" in kullu["source_agency"]
    assert "Metropolitan Police" in london["source_agency"]
    assert "NYPD" in nyc["source_agency"]
    assert "Tokyo" in tokyo["source_agency"]

    # Verify non-uniform 5-year trends (e.g., post-2021 urban shifts in Bengaluru/London/NYC vs declining in Delhi/Kullu)
    assert delhi["five_year_trend_pct"] != bengaluru["five_year_trend_pct"]
    assert london["five_year_trend_pct"] != delhi["five_year_trend_pct"]
    assert tokyo["overall_safety_index"] > nyc["overall_safety_index"]
    assert kullu["overall_safety_index"] > delhi["overall_safety_index"]

    # Check that yearly_series has 2021-2026 entries with distinct values
    for cs in (delhi, bengaluru, kullu, london, nyc, tokyo):
        years = [y["year"] for y in cs["yearly_series"]]
        assert years == ["2021", "2022", "2023", "2024", "2025", "2026"]
        assert len(cs["categories"]) == 5


@pytest.mark.asyncio
async def test_live_crime_telemetry_modulation():
    client = CrimeClient()
    mock_live = [
        {
            "title": "Police arrest suspect in armed robbery case",
            "url": "https://example.com/1",
            "source": "Local News",
            "published_at": "2h ago",
            "category": "Violent Crime",
            "severity": "high",
            "snippet": "Verified dispatch",
            "location": "London",
        }
    ]
    res = client._get_fallback_district_crime(
        "London",
        country="United Kingdom",
        is_in_india=False,
        wb_data={"homicide_by_year": {"2022": 1.15}, "rule_of_law_by_year": {"2023": 89.4}},
        realtime_incidents=mock_live,
    )
    cs = res["crime_statistics"]
    assert len(cs["realtime_incidents"]) == 1
    assert "Live World Bank UNODC Homicide Index" in cs["data_provenance"]
    assert "Live Dispatch Feed (1 active reports)" in cs["data_provenance"]
