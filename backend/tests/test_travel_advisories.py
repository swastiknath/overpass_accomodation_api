import pytest
from connectors.travel_advisory_client import TravelAdvisoryClient

def test_travel_advisory_mea_israel():
    client = TravelAdvisoryClient()
    advisory = client.get_advisory_for_location("Tel Aviv, Israel")
    
    assert advisory is not None
    assert advisory["country"] == "Israel"
    assert advisory["level"] >= 3
    assert advisory["active_warning"] is True
    
    # Must contain MEA, US State Dept, and UK FCDO
    sources = advisory.get("sources", {})
    assert "india_mea" in sources
    assert "us_state_dept" in sources
    assert "uk_fcdo" in sources
    
    mea = sources["india_mea"]
    assert mea["country_code"] == "IN"
    assert "Ministry of External Affairs" in mea["authority"]
    assert mea["helpline"] is not None
    assert "972" in mea["helpline"]  # Tel Aviv helpline code
    assert mea["registration_url"] is not None

def test_travel_advisory_list_structure():
    client = TravelAdvisoryClient()
    advisory = client.get_advisory_for_location("Beirut, Lebanon")
    
    assert advisory is not None
    advisories_list = advisory.get("advisories_list", [])
    assert len(advisories_list) >= 3
    
    authorities = [a["authority"] for a in advisories_list]
    assert any("Ministry of External Affairs" in auth for auth in authorities)
    assert any("U.S. Department of State" in auth for auth in authorities)
    assert any("Foreign, Commonwealth & Development Office" in auth for auth in authorities)

def test_travel_advisory_safe_country():
    client = TravelAdvisoryClient()
    advisory = client.get_advisory_for_location("Tokyo, Japan")
    
    assert advisory is not None
    assert advisory["level"] == 1
    assert advisory["active_warning"] is False


def test_travel_advisory_influence_levels():
    client = TravelAdvisoryClient()

    # 1. Level 3 (Israel) - must have high influence factor
    israel_adv = client.get_advisory_for_location("Tel Aviv, Israel")
    rec_israel = client.to_ingested_record(israel_adv, lat=32.08, lon=34.78)
    assert rec_israel is not None
    assert rec_israel.severity_raw >= 0.85
    assert rec_israel.confidence >= 0.95

    # 2. Level 2 (India) - routine caution must have minimal influence factor
    india_adv = client.get_advisory_for_location("Visakhapatnam, India")
    rec_india = client.to_ingested_record(india_adv, lat=17.68, lon=83.21)
    assert rec_india is not None
    assert rec_india.severity_raw <= 0.06
    assert rec_india.confidence <= 0.30

    # 3. Level 1 (Japan) - must not be factored
    japan_adv = client.get_advisory_for_location("Tokyo, Japan")
    rec_japan = client.to_ingested_record(japan_adv, lat=35.67, lon=139.65)
    assert rec_japan is None


def test_mea_expanded_places():
    client = TravelAdvisoryClient()

    # Syria
    syria_adv = client.get_advisory_for_location("Damascus, Syria")
    assert syria_adv is not None
    assert syria_adv["sources"]["india_mea"]["level"] == 4
    assert "Damascus" in syria_adv["sources"]["india_mea"]["helpline"]

    # Russia
    russia_adv = client.get_advisory_for_location("Moscow")
    assert russia_adv is not None
    assert russia_adv["sources"]["india_mea"]["level"] == 3
    assert "Moscow" in russia_adv["sources"]["india_mea"]["helpline"]

    # Canada
    canada_adv = client.get_advisory_for_location("Toronto, Canada")
    assert canada_adv is not None
    assert canada_adv["sources"]["india_mea"]["level"] == 2
    assert "Ottawa" in canada_adv["sources"]["india_mea"]["helpline"]

    # West Asia
    west_asia_adv = client.get_advisory_for_location("West Asia")
    assert west_asia_adv is not None
    assert west_asia_adv["sources"]["india_mea"]["level"] == 3
    assert "1800118797" in west_asia_adv["sources"]["india_mea"]["helpline"]


def test_mea_india_subregions():
    client = TravelAdvisoryClient()

    # Jammu
    jammu_adv = client.get_advisory_for_location("Jammu")
    assert jammu_adv is not None
    assert "Jammu & Kashmir" in jammu_adv["sources"]["india_mea"]["country"]
    assert "112" in jammu_adv["sources"]["india_mea"]["helpline"]

    # Coordinate fallback for India
    coord_adv = client.get_advisory_for_location("Unknown Place", lat=32.72, lon=74.85)
    assert coord_adv is not None
    assert "Jammu & Kashmir" in coord_adv["sources"]["india_mea"]["country"]


def test_pakistan_severe_warning_not_safe():
    client = TravelAdvisoryClient()
    pak_adv = client.get_advisory_for_location("Lahore, Pakistan")
    assert pak_adv is not None
    assert pak_adv["level"] == 4
    assert pak_adv["status_color"] == "rose"
    assert pak_adv["active_warning"] is True
    assert "not going to be safe" in pak_adv["summary"].lower() or "not safe" in pak_adv["summary"].lower()
    assert pak_adv["sources"]["india_mea"]["level"] == 4


def test_india_domestic_green_safe():
    client = TravelAdvisoryClient()
    # Mumbai, Bengaluru, Goa
    mum_adv = client.get_advisory_for_location("Mumbai, India")
    assert mum_adv is not None
    assert mum_adv["level"] == 1
    assert mum_adv["status_color"] == "emerald"
    assert mum_adv["is_domestic_safe"] is True
    assert mum_adv["active_warning"] is True
    assert "standard domestic" in mum_adv["summary"].lower()




