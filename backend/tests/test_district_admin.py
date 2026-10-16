"""Tests for localized district administration & emergency authority resolution."""

import pytest
from connectors.district_admin_client import resolve_district_authorities
from llm.explainer import LLMExplainer


def test_libya_localized_authorities():
    """Verify that searching for Libya returns Libyan authorities and NOT Indian bodies."""
    dist_title, authorities, tips = resolve_district_authorities("Libya", country="Libya")
    
    assert "Libya" in dist_title or "Libyan" in dist_title
    auth_names = [a["name"] for a in authorities]
    auth_helplines = [a["helpline"] for a in authorities]
    
    # Must contain Libyan emergency numbers
    assert any("1515" in h or "193" in h or "190" in h for h in auth_helplines)
    
    # Must NOT contain Indian domestic agencies
    for name in auth_names:
        assert "ERSS" not in name
        assert "State / District Disaster Management" not in name
        assert "National Highway Authority" not in name
        assert "NDMA" not in name


def test_france_localized_authorities():
    """Verify that Paris / France returns European & French authorities."""
    dist_title, authorities, tips = resolve_district_authorities("Paris, Île-de-France, France", country="France")
    auth_names = [a["name"] for a in authorities]
    auth_helplines = [a["helpline"] for a in authorities]

    assert any("15" in h or "17" in h or "112" in h for h in auth_helplines)
    assert not any("ERSS" in n or "NDMA" in n for n in auth_names)


def test_nepal_localized_authorities():
    """Verify that Kathmandu / Nepal returns Nepal authorities."""
    dist_title, authorities, tips = resolve_district_authorities("Kathmandu, Nepal", country="Nepal")
    auth_helplines = [a["helpline"] for a in authorities]
    assert any("100" in h or "1144" in h for h in auth_helplines)


def test_kullu_india_authorities():
    """Verify that domestic Indian locations return their verified Indian DDMA."""
    dist_title, authorities, tips = resolve_district_authorities("Manali, Kullu, Himachal Pradesh, India", country="India")
    assert "Kullu" in dist_title or "Himachal" in dist_title
    auth_helplines = [a["helpline"] for a in authorities]
    assert any("1077" in h or "112" in h for h in auth_helplines)


def test_explainer_curated_advice_for_libya_has_no_indian_agencies():
    """Verify that full curated advice generated for Libya contains zero Indian domestic agencies."""
    explainer = LLMExplainer()
    
    mock_libya_report = {
        "location": {
            "display_name": "Libya",
            "lat": 26.3351,
            "lon": 17.2283,
            "country": "Libya",
            "is_in_india": False,
        },
        "is_in_india": False,
        "contributions": [
            {"hazard_type": "conflict", "weight": 0.6, "sigma": 0.8},
            {"hazard_type": "crime", "weight": 0.4, "sigma": 0.5},
        ],
    }

    advice_items = explainer._get_curated_advice_for_report(mock_libya_report)
    assert len(advice_items) >= 2

    for item in advice_items:
        for auth in item.authorities:
            assert "ERSS" not in auth.name
            assert "1070" not in (auth.helpline or "")
            assert "1033" not in (auth.helpline or "")
            assert "112.gov.in" not in (auth.url or "")
            assert "ndma.gov.in" not in (auth.url or "")
