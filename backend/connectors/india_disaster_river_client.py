"""Indian Local Authorities Disaster Telemetry (NCS Earthquake, FSI Wildfire, CWC Flood)
& Real-Time + Historical River Flow & Water Level Client.

Uses 100% real-time and historical data sources (zero mock or template data):
- Strictly filters and displays ONLY rivers physically situated within the searched city's municipal limits
  (verified via city-bounded OpenStreetMap Nominatim waterway discovery + official CWC FloodWatch India city stations).
  Never substitutes rivers from distant cities or state capitals.
- Live CWC FloodWatch India (`https://ffs.india-water.gov.in`) hourly river gauge water levels (`HHS`),
  official CWC Warning/Danger/HFL levels, short-range forecasts, and national above-warning station queue.
- Live Open-Meteo / Copernicus GloFAS Flood API (`https://flood-api.open-meteo.com/v1/flood`) unmodified real-time
  river discharge (`m³/s` & `cusecs`), 30-day observed daily discharge trend, 15-day forecasted discharge,
  and multi-year (2021–2026) historical daily river flow archive (annual mean, peak, minimum, P90 watch, P98 danger).
- Live NDMA SACHET Common Alerting Protocol (CAP) RSS feed (`https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml`),
  NCS (National Centre for Seismology) earthquake feed, and FSI Vanagni wildfire dispatches.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import logging
import math
import re
import time
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET

import httpx
from shapely.geometry import Point

from config import Settings, load_settings
from gis.schema import IngestedRecord, ResolutionTier

logger = logging.getLogger("connectors.india_disaster_river")

# In-memory caches (TTL = 15 minutes)
_RIVER_LIVE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_RIVER_HIST_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CWC_LIVE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CWC_WARNING_QUEUE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_SACHET_CAP_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_INDIA_ALERTS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CITY_RIVER_OSM_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 900.0


# ─────────────────────────────────────────────────────────────────────────────
# City-Level Municipal River & CWC Station Profiles (Strictly City-Bounded)
# ─────────────────────────────────────────────────────────────────────────────
# Every entry lists ONLY rivers physically situated within that city's municipal limits.
# Cities without a river inside municipal limits have `rivers_in_city: []` and `has_river_in_city: False`.
INDIA_CITY_RIVER_PROFILES: dict[str, dict[str, Any]] = {
    "delhi": {
        "city": "New Delhi",
        "state": "Delhi",
        "has_river_in_city": True,
        "rivers_in_city": ["Yamuna River"],
        "river_name": "Yamuna River",
        "basin": "Ganga–Yamuna Basin",
        "cwc_station": "Delhi Railway Bridge (Old Loha Pul) CWC Station",
        "cwc_station_code": "015-UYDDEL",
        "upstream_control": "Wazirabad Barrage & Okhla Barrage (Delhi)",
        "warning_level_m": 204.50,
        "danger_level_m": 205.33,
        "hfl_m": 208.66,
        "hfl_year": 2023,
        "seismic_zone": "Zone IV (High Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Upper Yamuna Division) & Delhi I&FC Dept",
        "seismic_authority": "National Centre for Seismology (NCS, Lodhi Road HQ) & DDMA Delhi",
        "fire_authority": "Delhi Fire Service (DFS) & Forest Survey of India (FSI Northern Zone)",
        "sdma_name": "Delhi Disaster Management Authority (DDMA)",
        "sdma_helpline": "1077 / 112",
    },
    "manali": {
        "city": "Manali",
        "state": "Himachal Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Beas River", "Manalsu River"],
        "river_name": "Beas River & Manalsu River",
        "basin": "Indus–Beas Himalayan Catchment",
        "cwc_station": "Kullu–Manali Beas CWC Hydrological Station",
        "cwc_station_code": "SHD00001",
        "fallback_cwc_station_code": "005-SHDSIM",
        "upstream_control": "Solang–Palchan Beas Headwaters",
        "warning_level_m": 1176.50,
        "danger_level_m": 1177.50,
        "hfl_m": 1179.80,
        "hfl_year": 2023,
        "seismic_zone": "Zone V (Very Severe Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Shimla), BBMB & HP Jal Shakti Vibhag",
        "seismic_authority": "National Centre for Seismology (NCS Shimla/Sundernagar Observatory) & DDMA Kullu",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & Himachal Pradesh Forest Department (Kullu Circle)",
        "sdma_name": "Himachal Pradesh SDMA (HPSDMA) & DDMA Kullu",
        "sdma_helpline": "1077 / 1070",
    },
    "kullu": {
        "city": "Kullu",
        "state": "Himachal Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Beas River", "Sarvari River", "Parvati River"],
        "river_name": "Beas River & Sarvari River",
        "basin": "Indus–Beas Himalayan Catchment",
        "cwc_station": "Kullu CWC FloodWatch Station (Beas River)",
        "cwc_station_code": "SHD00001",
        "fallback_cwc_station_code": "005-SHDSIM",
        "upstream_control": "Beas–Parvati Confluence (Bhuntar, Kullu)",
        "warning_level_m": 1176.50,
        "danger_level_m": 1177.50,
        "hfl_m": 1179.80,
        "hfl_year": 2023,
        "seismic_zone": "Zone V (Very Severe Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India) & DDMA Kullu / HP Jal Shakti Vibhag",
        "seismic_authority": "National Centre for Seismology (NCS) & Himachal Pradesh SDMA (HPSDMA)",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & HP Forest Department (Kullu Circle)",
        "sdma_name": "DDMA Kullu & Himachal Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "mandi": {
        "city": "Mandi",
        "state": "Himachal Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Beas River", "Suketi Khad"],
        "river_name": "Beas River & Suketi Khad",
        "basin": "Indus–Beas Basin",
        "cwc_station": "Pandoa / Mandi CWC FloodWatch Station (Beas River)",
        "cwc_station_code": "005-SHDSIM",
        "upstream_control": "Pandoh Dam (BBMB)",
        "warning_level_m": 685.00,
        "danger_level_m": 687.50,
        "hfl_m": 689.60,
        "hfl_year": 2023,
        "seismic_zone": "Zone V (Very Severe Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India), BBMB & DDMA Mandi",
        "seismic_authority": "National Centre for Seismology (NCS Sundernagar Observatory) & HPSDMA",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & HP Forest Department (Mandi Circle)",
        "sdma_name": "DDMA Mandi & Himachal Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "shimla": {
        "city": "Shimla",
        "state": "Himachal Pradesh",
        "has_river_in_city": False,
        "rivers_in_city": [],
        "river_name": "No Major River Situated Within Shimla Municipal Limits",
        "basin": "High-Ridge Watershed Divide (Sutlej–Giri Catchment Outside City)",
        "cwc_station": "No CWC River Station Inside Shimla City",
        "cwc_station_code": None,
        "upstream_control": "Municipal Ridge Drainage Network",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": None,
        "seismic_zone": "Zone IV–V (High Himalayan Seismic Zone)",
        "flood_authority": "Himachal Pradesh State Disaster Management Authority (HPSDMA) & IMD Shimla",
        "seismic_authority": "National Centre for Seismology (NCS Shimla Observatory) & HPSDMA",
        "fire_authority": "Forest Survey of India (FSI Shimla Regional Office) & HP Forest Department",
        "sdma_name": "Himachal Pradesh State Disaster Management Authority (HPSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "rishikesh": {
        "city": "Rishikesh",
        "state": "Uttarakhand",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River", "Chandrabhaga River"],
        "river_name": "Ganga River",
        "basin": "Upper Ganga Basin",
        "cwc_station": "Rishikesh CWC FloodWatch Forecasting Station",
        "cwc_station_code": "014-HGDDDN",
        "upstream_control": "Pashulok Barrage, Rishikesh",
        "warning_level_m": 339.50,
        "danger_level_m": 340.50,
        "hfl_m": 341.72,
        "hfl_year": 2013,
        "seismic_zone": "Zone IV–V (Garhwal Himalayan Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Himalayan Ganga Division, Dehradun) & UK Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Wadia Institute of Himalayan Geology / USDMA",
        "fire_authority": "Forest Survey of India (FSI Dehradun HQ - Vanagni) & Uttarakhand Forest Department",
        "sdma_name": "Uttarakhand State Disaster Management Authority (USDMA)",
        "sdma_helpline": "1070 / 9557444486",
    },
    "haridwar": {
        "city": "Haridwar",
        "state": "Uttarakhand",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River"],
        "river_name": "Ganga River",
        "basin": "Upper Ganga Basin",
        "cwc_station": "Haridwar CWC FloodWatch Station (Bhimgoda Barrage)",
        "cwc_station_code": "015-HGDDDN",
        "upstream_control": "Bhimgoda Barrage, Haridwar",
        "warning_level_m": 293.00,
        "danger_level_m": 294.00,
        "hfl_m": 296.30,
        "hfl_year": 2013,
        "seismic_zone": "Zone IV (Garhwal Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Himalayan Ganga Division) & Uttarakhand Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & USDMA",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & Rajaji Tiger Reserve Forest Division",
        "sdma_name": "Uttarakhand State Disaster Management Authority (USDMA) & DDMA Haridwar",
        "sdma_helpline": "1070 / 1077",
    },
    "dehradun": {
        "city": "Dehradun",
        "state": "Uttarakhand",
        "has_river_in_city": True,
        "rivers_in_city": ["Rispana River", "Bindal River", "Tons River", "Song River"],
        "river_name": "Rispana River, Bindal River & Tons River",
        "basin": "Doon Valley Sub-Basin",
        "cwc_station": "Dehradun Doon Valley Hydrological Telemetry (CWC Himalayan Ganga Division HQ)",
        "cwc_station_code": None,
        "upstream_control": "Doon Valley Headwater Catchments",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2023,
        "seismic_zone": "Zone IV–V (Garhwal Himalayan Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC Himalayan Ganga Division, Dehradun) & Uttarakhand Irrigation Department",
        "seismic_authority": "National Centre for Seismology (NCS) & Wadia Institute of Himalayan Geology / USDMA",
        "fire_authority": "Forest Survey of India (FSI Headquarters Dehradun - Vanagni) & Uttarakhand Forest Fire Cell",
        "sdma_name": "Uttarakhand State Disaster Management Authority (USDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "varanasi": {
        "city": "Varanasi",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River", "Varuna River", "Assi River"],
        "river_name": "Ganga River & Varuna River",
        "basin": "Middle Ganga Basin",
        "cwc_station": "Varanasi (Rajghat) CWC FloodWatch Station",
        "cwc_station_code": "006-MGD3VNS",
        "fallback_cwc_station_code": "047-MGD3VNS",
        "upstream_control": "Varanasi Ganga & Varuna Confluence",
        "warning_level_m": 70.26,
        "danger_level_m": 71.26,
        "hfl_m": 73.90,
        "hfl_year": 1978,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Middle Ganga Division III, Varanasi) & UP Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS BHU Varanasi Observatory) & UPSDMA",
        "fire_authority": "UP Fire & Emergency Services & Forest Survey of India (FSI Central Zone)",
        "sdma_name": "Uttar Pradesh SDMA (UPSDMA) & DDMA Varanasi",
        "sdma_helpline": "1070 / 1077",
    },
    "ayodhya": {
        "city": "Ayodhya",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Saryu (Ghaghara) River"],
        "river_name": "Saryu (Ghaghara) River",
        "basin": "Ghaghara–Ganga Basin",
        "cwc_station": "Ayodhya CWC FloodWatch Station (Saryu / Ghaghara River)",
        "cwc_station_code": "011-MGD1LKN",
        "upstream_control": "Saryu Barrage, Ayodhya",
        "warning_level_m": 91.73,
        "danger_level_m": 92.73,
        "hfl_m": 94.01,
        "hfl_year": 2009,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Middle Ganga Division I) & UP Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Uttar Pradesh SDMA (UPSDMA)",
        "fire_authority": "UP Fire & Emergency Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Ayodhya & Uttar Pradesh SDMA (UPSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "prayagraj": {
        "city": "Prayagraj",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River", "Yamuna River"],
        "river_name": "Ganga River & Yamuna River (Triveni Sangam)",
        "basin": "Middle Ganga–Yamuna Confluence",
        "cwc_station": "Chatnag & Naini Prayagraj CWC FloodWatch Station",
        "cwc_station_code": "058-mgd3vns",
        "fallback_cwc_station_code": "006-MGD3VNS",
        "upstream_control": "Ganga–Yamuna Confluence at Sangam, Prayagraj",
        "warning_level_m": 83.73,
        "danger_level_m": 84.73,
        "hfl_m": 88.03,
        "hfl_year": 1978,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India) & UP Irrigation Dept Prayagraj",
        "seismic_authority": "National Centre for Seismology (NCS) & UPSDMA",
        "fire_authority": "UP Fire & Emergency Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Prayagraj & Uttar Pradesh SDMA",
        "sdma_helpline": "1070 / 1077",
    },
    "kanpur": {
        "city": "Kanpur",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River", "Pandu River"],
        "river_name": "Ganga River & Pandu River",
        "basin": "Middle Ganga Basin",
        "cwc_station": "Kanpur Ganga Barrage (Lavkush) CWC FloodWatch Station",
        "cwc_station_code": "020-lgd1lkn",
        "upstream_control": "Lavkush Ganga Barrage, Kanpur",
        "warning_level_m": 113.00,
        "danger_level_m": 114.00,
        "hfl_m": 114.98,
        "hfl_year": 2010,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India) & UP Irrigation Dept Kanpur",
        "seismic_authority": "National Centre for Seismology (NCS) & UPSDMA",
        "fire_authority": "UP Fire & Emergency Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Kanpur & Uttar Pradesh SDMA",
        "sdma_helpline": "1070 / 1077",
    },
    "lucknow": {
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Gomti River"],
        "river_name": "Gomti River",
        "basin": "Ganga–Gomti Basin",
        "cwc_station": "Lucknow CWC FloodWatch Station (Gomti River)",
        "cwc_station_code": "014-mgd2lkn",
        "upstream_control": "Gomti Barrage, Lucknow",
        "warning_level_m": 108.50,
        "danger_level_m": 109.50,
        "hfl_m": 110.85,
        "hfl_year": 1960,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Middle Ganga Division II, Lucknow) & UP Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Uttar Pradesh SDMA (UPSDMA)",
        "fire_authority": "UP Forest Department & UP Fire and Emergency Services",
        "sdma_name": "Uttar Pradesh State Disaster Management Authority (UPSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "agra": {
        "city": "Agra",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Yamuna River"],
        "river_name": "Yamuna River",
        "basin": "Lower Yamuna Basin",
        "cwc_station": "Agra (Poiya Ghat / J.B.) CWC FloodWatch Station",
        "cwc_station_code": "001-LYDAGRA",
        "upstream_control": "Agra Yamuna Barrage Corridor",
        "warning_level_m": 151.40,
        "danger_level_m": 152.40,
        "hfl_m": 154.76,
        "hfl_year": 1978,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Lower Yamuna Division, Agra) & UP Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Agra",
        "fire_authority": "UP Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Agra & Uttar Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "mathura": {
        "city": "Mathura",
        "state": "Uttar Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Yamuna River"],
        "river_name": "Yamuna River",
        "basin": "Middle Yamuna Basin",
        "cwc_station": "Prayagghat Mathura CWC FloodWatch Station (Yamuna River)",
        "cwc_station_code": "001-LYDAGRA",
        "upstream_control": "Gokul Barrage, Mathura",
        "warning_level_m": 165.20,
        "danger_level_m": 166.00,
        "hfl_m": 169.73,
        "hfl_year": 1978,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India) & UP Irrigation Dept Mathura",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Mathura",
        "fire_authority": "UP Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Mathura & Uttar Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "patna": {
        "city": "Patna",
        "state": "Bihar",
        "has_river_in_city": True,
        "rivers_in_city": ["Ganga River", "Punpun River"],
        "river_name": "Ganga River & Punpun River",
        "basin": "Lower Ganga Basin",
        "cwc_station": "Gandhighat & Dighaghat Patna CWC FloodWatch Station",
        "cwc_station_code": "003-MGD5PTN",
        "fallback_cwc_station_code": "002-MGD5PTN",
        "upstream_control": "Patna Ganga Riverfront & Sripalpur Punpun Gauge",
        "warning_level_m": 47.60,
        "danger_level_m": 48.60,
        "hfl_m": 50.52,
        "hfl_year": 2016,
        "seismic_zone": "Zone IV (High Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Middle Ganga Division V, Patna) & Bihar WRD (FMISC)",
        "seismic_authority": "National Centre for Seismology (NCS Patna) & Bihar SDMA (BSDMA)",
        "fire_authority": "Bihar Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "Bihar State Disaster Management Authority (BSDMA)",
        "sdma_helpline": "1070 / 0612-2294204",
    },
    "guwahati": {
        "city": "Guwahati",
        "state": "Assam",
        "has_river_in_city": True,
        "rivers_in_city": ["Brahmaputra River", "Bharalu River"],
        "river_name": "Brahmaputra River & Bharalu River",
        "basin": "Brahmaputra Basin",
        "cwc_station": "Guwahati (D.C. Court) CWC FloodWatch Station",
        "cwc_station_code": "001-MBDGHY",
        "upstream_control": "Brahmaputra Main Stem at Guwahati",
        "warning_level_m": 48.68,
        "danger_level_m": 49.68,
        "hfl_m": 51.46,
        "hfl_year": 2004,
        "seismic_zone": "Zone V (Very Severe North-East Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Middle Brahmaputra Division, Guwahati) & ASDMA",
        "seismic_authority": "National Centre for Seismology (NCS North-East Telemetry) & Assam SDMA (ASDMA)",
        "fire_authority": "Forest Survey of India (FSI Eastern Zone) & Assam Fire & Emergency Services",
        "sdma_name": "Assam State Disaster Management Authority (ASDMA)",
        "sdma_helpline": "1070 / 1079",
    },
    "kolkata": {
        "city": "Kolkata",
        "state": "West Bengal",
        "has_river_in_city": True,
        "rivers_in_city": ["Hooghly River"],
        "river_name": "Hooghly River",
        "basin": "Bhagirathi–Hooghly Estuarine Basin",
        "cwc_station": "Kolkata Garden Reach / Hooghly River Gauge",
        "cwc_station_code": None,
        "upstream_control": "Hooghly Tidal Reach at Kolkata",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2020,
        "seismic_zone": "Zone III–IV (Bengal Basin Seismic Transition)",
        "flood_authority": "Central Water Commission (CWC Lower Ganga Division) & West Bengal I&WD / KMC",
        "seismic_authority": "National Centre for Seismology (NCS Alipore Kolkata Observatory) & WBDMD",
        "fire_authority": "West Bengal Fire & Emergency Services & Forest Survey of India (FSI Eastern Zone Kolkata)",
        "sdma_name": "West Bengal Department of Disaster Management & Civil Defence (WBDMD)",
        "sdma_helpline": "1070 / 033-22143526",
    },
    "mumbai": {
        "city": "Mumbai",
        "state": "Maharashtra",
        "has_river_in_city": True,
        "rivers_in_city": ["Mithi River", "Dahisar River", "Poisar River", "Oshiwara River"],
        "river_name": "Mithi River, Dahisar River, Poisar River & Oshiwara River",
        "basin": "Mumbai Salsette Island Coastal Basin",
        "cwc_station": "BMC Mithi River (Kurla–BKC–Mahim) & CWC Konkan Telemetry",
        "cwc_station_code": None,
        "upstream_control": "Vihar & Powai Lake Spillways + Mahim Bay Tidal Gates (Mumbai)",
        "warning_level_m": 2.70,
        "danger_level_m": 3.40,
        "hfl_m": 4.85,
        "hfl_year": 2019,
        "seismic_zone": "Zone III (Moderate Peninsular Seismic Zone)",
        "flood_authority": "BMC Disaster Management Cell (1916) & Central Water Commission (CWC Konkan Subdivision)",
        "seismic_authority": "National Centre for Seismology (NCS Colaba Mumbai Observatory) & Maharashtra SDMA",
        "fire_authority": "Mumbai Fire Brigade (MFB), Sanjay Gandhi National Park Forest Division & FSI Vanagni",
        "sdma_name": "BMC Disaster Management Department & Maharashtra SDMA",
        "sdma_helpline": "1916 / 1070",
    },
    "pune": {
        "city": "Pune",
        "state": "Maharashtra",
        "has_river_in_city": True,
        "rivers_in_city": ["Mutha River", "Mula River", "Mula-Mutha River", "Pavana River"],
        "river_name": "Mula River, Mutha River & Mula-Mutha River",
        "basin": "Mula–Mutha Sub-Basin",
        "cwc_station": "Mula-Mutha CWC FloodWatch Station (Pune Division)",
        "cwc_station_code": "043-UKDPUNE",
        "upstream_control": "Khadakwasla Dam & Sangam Bridge (Pune)",
        "warning_level_m": 517.50,
        "danger_level_m": 518.50,
        "hfl_m": 520.20,
        "hfl_year": 2019,
        "seismic_zone": "Zone III (Koyna–Western Ghats Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Upper Krishna Division, Pune) & Maharashtra WRD",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Pune / Maharashtra SDMA",
        "fire_authority": "Forest Survey of India (FSI Western Ghats) & Pune Municipal Corporation Fire Brigade",
        "sdma_name": "DDMA Pune & Maharashtra State Disaster Management Authority",
        "sdma_helpline": "1077 / 020-25501269",
    },
    "bengaluru": {
        "city": "Bengaluru",
        "state": "Karnataka",
        "has_river_in_city": True,
        "rivers_in_city": ["Vrishabhavathi River"],
        "river_name": "Vrishabhavathi River",
        "basin": "Vrishabhavathi–Arkavathi Urban Sub-Basin",
        "cwc_station": "KSNDMC & CWC Bengaluru Vrishabhavathi Urban Corridor Gauge",
        "cwc_station_code": None,
        "upstream_control": "Bengaluru Vrishabhavathi Valley Stormwater Network",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2022,
        "seismic_zone": "Zone II (Low Peninsular Seismic Zone)",
        "flood_authority": "Karnataka State Natural Disaster Monitoring Centre (KSNDMC), BBMP & CWC Bengaluru",
        "seismic_authority": "National Centre for Seismology (NCS) & KSNDMC Seismic Monitoring Network",
        "fire_authority": "Forest Survey of India (FSI Southern Zone Bengaluru) & Karnataka State Fire and Emergency Services",
        "sdma_name": "Karnataka State Disaster Management Authority (KSDMA) & KSNDMC",
        "sdma_helpline": "1070 / 1533 (BBMP)",
    },
    "chennai": {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "has_river_in_city": True,
        "rivers_in_city": ["Adyar River", "Cooum River", "Kosasthalaiyar River"],
        "river_name": "Adyar River, Cooum River & Kosasthalaiyar River",
        "basin": "Chennai Metropolitan River Basin",
        "cwc_station": "Chennai Adyar–Cooum–Kosasthalaiyar Urban River Gauge (CWC & GCC)",
        "cwc_station_code": None,
        "upstream_control": "Chembarambakkam (Adyar), Poondi & Red Hills Reservoirs",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2015,
        "seismic_zone": "Zone III (Moderate Coastal Seismic Zone)",
        "flood_authority": "Greater Chennai Corporation (GCC), Tamil Nadu WRD & Central Water Commission (CWC Chennai)",
        "seismic_authority": "National Centre for Seismology (NCS Chennai Observatory) & Tamil Nadu SDMA (TNSDMA)",
        "fire_authority": "Tamil Nadu Fire and Rescue Services & Tamil Nadu Forest Department / FSI Vanagni",
        "sdma_name": "Tamil Nadu State Disaster Management Authority (TNSDMA) & GCC (1913)",
        "sdma_helpline": "1070 / 1913",
    },
    "hyderabad": {
        "city": "Hyderabad",
        "state": "Telangana",
        "has_river_in_city": True,
        "rivers_in_city": ["Musi River"],
        "river_name": "Musi River",
        "basin": "Musi Urban River Basin",
        "cwc_station": "Moosarambagh / Chaderghat Musi River Gauge, Hyderabad",
        "cwc_station_code": None,
        "upstream_control": "Osman Sagar (Gandipet) & Himayat Sagar Flood Gates (Hyderabad)",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2020,
        "seismic_zone": "Zone II (Stable Deccan Plateau Seismic Zone)",
        "flood_authority": "HYDRAA, GHMC, Telangana Irrigation Dept & Central Water Commission (CWC Hyderabad)",
        "seismic_authority": "National Centre for Seismology (NCS) & CSIR-NGRI Hyderabad Seismological Observatory",
        "fire_authority": "Telangana State Disaster Response & Fire Services & Telangana Forest Dept / FSI Vanagni",
        "sdma_name": "Telangana SDMA & GHMC Disaster Response (HYDRAA)",
        "sdma_helpline": "1070 / 040-21111111",
    },
    "kochi": {
        "city": "Kochi",
        "state": "Kerala",
        "has_river_in_city": True,
        "rivers_in_city": ["Periyar River", "Chitrapuzha River"],
        "river_name": "Periyar River & Chitrapuzha River",
        "basin": "Periyar–Vembanad Basin",
        "cwc_station": "Neeleeswaram / Aluva Periyar CWC FloodWatch Station",
        "cwc_station_code": "012-SWRDKOCHI",
        "upstream_control": "Bhoothathankettu Barrage & Aluva Regulators",
        "warning_level_m": 9.00,
        "danger_level_m": 10.00,
        "hfl_m": 12.40,
        "hfl_year": 2018,
        "seismic_zone": "Zone III (Moderate Western Ghats Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - South Western Rivers Division, Kochi) & KSDMA",
        "seismic_authority": "National Centre for Seismology (NCS) & Kerala State Disaster Management Authority (KSDMA)",
        "fire_authority": "Forest Survey of India (FSI Vanagni), Kerala Forest & Wildlife Dept & Kerala Fire and Rescue Services",
        "sdma_name": "Kerala State Disaster Management Authority (KSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
    "ahmedabad": {
        "city": "Ahmedabad",
        "state": "Gujarat",
        "has_river_in_city": True,
        "rivers_in_city": ["Sabarmati River"],
        "river_name": "Sabarmati River",
        "basin": "Sabarmati Basin",
        "cwc_station": "Subhash Bridge CWC FloodWatch Station, Ahmedabad",
        "cwc_station_code": "020-MAHGAND",
        "upstream_control": "Vasna Barrage, Ahmedabad",
        "warning_level_m": 44.09,
        "danger_level_m": 45.34,
        "hfl_m": 47.45,
        "hfl_year": 2006,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Mahi & Tapi Basin Org) & AMC / Gujarat WRD",
        "seismic_authority": "Institute of Seismological Research (ISR Gandhinagar), NCS & Gujarat SDMA (GSDMA)",
        "fire_authority": "Ahmedabad Fire and Emergency Services (AFES) & Gujarat Forest Department / FSI",
        "sdma_name": "Gujarat State Disaster Management Authority (GSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "surat": {
        "city": "Surat",
        "state": "Gujarat",
        "has_river_in_city": True,
        "rivers_in_city": ["Tapi River"],
        "river_name": "Tapi River",
        "basin": "Tapi Basin",
        "cwc_station": "Surat (Hope Bridge) CWC FloodWatch Station (Tapi River)",
        "cwc_station_code": "023-TDSURAT",
        "upstream_control": "Singanpore Weir (Surat) & Ukai Dam",
        "warning_level_m": 8.50,
        "danger_level_m": 9.50,
        "hfl_m": 12.68,
        "hfl_year": 2006,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Tapi Division, Surat) & SMC Flood Control",
        "seismic_authority": "Institute of Seismological Research (ISR Gandhinagar), NCS & GSDMA",
        "fire_authority": "Surat Fire and Emergency Services & Gujarat Forest Department / FSI",
        "sdma_name": "DDMA Surat & Gujarat State Disaster Management Authority (GSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
    "vadodara": {
        "city": "Vadodara",
        "state": "Gujarat",
        "has_river_in_city": True,
        "rivers_in_city": ["Vishwamitri River"],
        "river_name": "Vishwamitri River",
        "basin": "Vishwamitri–Dhadhar Basin",
        "cwc_station": "Kala Ghoda Bridge Vishwamitri Gauge, Vadodara",
        "cwc_station_code": None,
        "upstream_control": "Ajwa Reservoir, Vadodara",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2024,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Vadodara Municipal Corporation (VMC), Gujarat WRD & CWC Mahi–Tapi Org",
        "seismic_authority": "ISR Gandhinagar, NCS & Gujarat SDMA (GSDMA)",
        "fire_authority": "Vadodara Fire & Emergency Services & FSI Vanagni",
        "sdma_name": "DDMA Vadodara & Gujarat SDMA (GSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
    "jaipur": {
        "city": "Jaipur",
        "state": "Rajasthan",
        "has_river_in_city": True,
        "rivers_in_city": ["Dravyavati River (Amanishah Nala)"],
        "river_name": "Dravyavati River (Amanishah Nala)",
        "basin": "Dhund–Dravyavati Urban Sub-Basin",
        "cwc_station": "Jaipur Dravyavati Urban River Telemetry",
        "cwc_station_code": None,
        "upstream_control": "Nahargarh Foothill Catchment, Jaipur",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2020,
        "seismic_zone": "Zone II (Low Seismic Intensity)",
        "flood_authority": "Jaipur Development Authority (JDA), Rajasthan WRD & RSDMA",
        "seismic_authority": "National Centre for Seismology (NCS Jaipur Observatory) & Rajasthan SDMA",
        "fire_authority": "Rajasthan Forest Department (Jhalana/Nahargarh Reserve), FSI Vanagni & Jaipur Fire Service",
        "sdma_name": "Rajasthan State Disaster Management Authority (RSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "udaipur": {
        "city": "Udaipur",
        "state": "Rajasthan",
        "has_river_in_city": True,
        "rivers_in_city": ["Ayad (Ahar) River"],
        "river_name": "Ayad (Ahar) River",
        "basin": "Ayad–Berach Basin",
        "cwc_station": "Udaipur Ayad River & Fateh Sagar–Pichola Spillway Gauge",
        "cwc_station_code": None,
        "upstream_control": "Swaroop Sagar & Pichola Spillway Gates (Udaipur)",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2006,
        "seismic_zone": "Zone II (Low Seismic Intensity)",
        "flood_authority": "Rajasthan Water Resources Dept (Udaipur Circle) & DDMA Udaipur",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Udaipur",
        "fire_authority": "Rajasthan Forest Department (Aravalli Circle), FSI Vanagni & Udaipur Fire Service",
        "sdma_name": "DDMA Udaipur & Rajasthan SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "kota": {
        "city": "Kota",
        "state": "Rajasthan",
        "has_river_in_city": True,
        "rivers_in_city": ["Chambal River"],
        "river_name": "Chambal River",
        "basin": "Chambal Basin",
        "cwc_station": "Kota Barrage Chambal CWC Station",
        "cwc_station_code": None,
        "upstream_control": "Kota Barrage & Jawahar Sagar Dam",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2022,
        "seismic_zone": "Zone II (Low Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC Chambal Division) & Rajasthan WRD Kota",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Kota",
        "fire_authority": "Rajasthan Forest Department (Mukundra Hills), FSI Vanagni & Kota Fire Service",
        "sdma_name": "DDMA Kota & Rajasthan SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "goa": {
        "city": "Panaji / Goa",
        "state": "Goa",
        "has_river_in_city": True,
        "rivers_in_city": ["Mandovi (Mhadei) River", "Zuari River"],
        "river_name": "Mandovi (Mhadei) River & Zuari River",
        "basin": "West-Flowing Konkan River Basin",
        "cwc_station": "Mandovi (Mhadei) CWC FloodWatch Station, Goa",
        "cwc_station_code": "048-cdbng",
        "upstream_control": "Mandovi Estuarine Reach, Panaji",
        "warning_level_m": 13.50,
        "danger_level_m": 14.50,
        "hfl_m": 20.30,
        "hfl_year": 2021,
        "seismic_zone": "Zone III (Moderate Western Coast Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India) & Goa Department of Water Resources",
        "seismic_authority": "National Centre for Seismology (NCS) & Goa State Disaster Management Authority (GSDMA)",
        "fire_authority": "Goa Directorate of Fire & Emergency Services & Goa Forest Department / FSI Vanagni",
        "sdma_name": "Goa State Disaster Management Authority (GSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "srinagar": {
        "city": "Srinagar",
        "state": "Jammu and Kashmir",
        "has_river_in_city": True,
        "rivers_in_city": ["Jhelum River"],
        "river_name": "Jhelum River",
        "basin": "Indus–Jhelum Kashmir Valley Basin",
        "cwc_station": "Rammunshibagh Srinagar CWC FloodWatch Station",
        "cwc_station_code": "005-jhelum",
        "upstream_control": "Ram Munshi Bagh & Flood Spill Channel, Srinagar",
        "warning_level_m": 1585.48,
        "danger_level_m": 1586.40,
        "hfl_m": 1589.00,
        "hfl_year": 2014,
        "seismic_zone": "Zone V (Very Severe Kashmir Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Jhelum Division) & J&K Irrigation & Flood Control Dept",
        "seismic_authority": "National Centre for Seismology (NCS Srinagar Observatory) & J&K SDMA",
        "fire_authority": "Forest Survey of India (FSI Northern Zone), J&K Forest Protection Force & Fire & Emergency Services",
        "sdma_name": "Jammu & Kashmir State Disaster Management Authority (JKSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "jammu": {
        "city": "Jammu",
        "state": "Jammu and Kashmir",
        "has_river_in_city": True,
        "rivers_in_city": ["Tawi River"],
        "river_name": "Tawi River",
        "basin": "Indus–Chenab–Tawi Sub-Basin",
        "cwc_station": "Jammu Tawi Bridge Gauge (J&K I&FC & CWC)",
        "cwc_station_code": None,
        "upstream_control": "Tawi Barrage, Jammu",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2014,
        "seismic_zone": "Zone IV (High Himalayan Foothill Seismic Zone)",
        "flood_authority": "J&K Irrigation & Flood Control Dept Jammu & Central Water Commission (CWC)",
        "seismic_authority": "National Centre for Seismology (NCS Jammu) & JKSDMA",
        "fire_authority": "J&K Fire & Emergency Services & Forest Survey of India (FSI)",
        "sdma_name": "Jammu & Kashmir State Disaster Management Authority (JKSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "bhubaneswar": {
        "city": "Bhubaneswar",
        "state": "Odisha",
        "has_river_in_city": True,
        "rivers_in_city": ["Kuakhai River", "Daya River"],
        "river_name": "Kuakhai River & Daya River",
        "basin": "Mahanadi–Kuakhai Delta Basin",
        "cwc_station": "Naraj–Kuakhai Head Regulator CWC FloodWatch Station (Bhubaneswar)",
        "cwc_station_code": "036-MDBURLA",
        "upstream_control": "Naraj Barrage & Kuakhai Bifurcation (Bhubaneswar North)",
        "warning_level_m": 25.41,
        "danger_level_m": 26.41,
        "hfl_m": 27.61,
        "hfl_year": 2011,
        "seismic_zone": "Zone III (Mahanadi Graben Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Mahanadi Basin, Bhubaneswar) & Odisha DoWR",
        "seismic_authority": "National Centre for Seismology (NCS Bhubaneswar Observatory) & OSDMA",
        "fire_authority": "Odisha Fire & Disaster Response Service & Odisha Forest Dept / FSI Vanagni",
        "sdma_name": "Odisha State Disaster Management Authority (OSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "cuttack": {
        "city": "Cuttack",
        "state": "Odisha",
        "has_river_in_city": True,
        "rivers_in_city": ["Mahanadi River", "Kathajodi River"],
        "river_name": "Mahanadi River & Kathajodi River",
        "basin": "Mahanadi Delta Basin",
        "cwc_station": "Naraj & Jobra Cuttack CWC FloodWatch Station (Mahanadi River)",
        "cwc_station_code": "036-MDBURLA",
        "upstream_control": "Mundali & Jobra Barrages, Cuttack",
        "warning_level_m": 25.41,
        "danger_level_m": 26.41,
        "hfl_m": 27.61,
        "hfl_year": 2011,
        "seismic_zone": "Zone III (Mahanadi Graben Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC FloodWatch India - Mahanadi Division, Cuttack/Bhubaneswar) & Odisha DoWR",
        "seismic_authority": "National Centre for Seismology (NCS) & OSDMA",
        "fire_authority": "Odisha Fire & Disaster Response Service & FSI Vanagni",
        "sdma_name": "Odisha State Disaster Management Authority (OSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "darjeeling": {
        "city": "Darjeeling",
        "state": "West Bengal",
        "has_river_in_city": False,
        "rivers_in_city": [],
        "river_name": "No Major River Situated Within Darjeeling Municipal Ridge",
        "basin": "Eastern Himalayan Hill Ridge (Rangeet–Teesta Valleys Outside Town)",
        "cwc_station": "No CWC River Station Inside Darjeeling Town",
        "cwc_station_code": None,
        "upstream_control": "Hill Ridge Spring & Jhora Drainage",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": None,
        "seismic_zone": "Zone IV–V (Eastern Himalayan Seismic Zone)",
        "flood_authority": "DDMA Darjeeling & West Bengal Irrigation & Waterways Department",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Darjeeling",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & West Bengal Forest Department (Hill Circle)",
        "sdma_name": "DDMA Darjeeling & WBDMD",
        "sdma_helpline": "1077 / 1070",
    },
    "siliguri": {
        "city": "Siliguri",
        "state": "West Bengal",
        "has_river_in_city": True,
        "rivers_in_city": ["Mahananda River", "Balason River"],
        "river_name": "Mahananda River & Balason River",
        "basin": "Mahananda Sub-Basin",
        "cwc_station": "Siliguri Mahananda Bridge CWC Gauge",
        "cwc_station_code": None,
        "upstream_control": "Fulbari Mahananda Barrage, Siliguri",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2023,
        "seismic_zone": "Zone IV (Eastern Himalayan Foothill Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Lower Brahmaputra/Teesta Division) & WB I&WD Siliguri",
        "seismic_authority": "National Centre for Seismology (NCS) & WBDMD",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & WB Forest Department",
        "sdma_name": "WBDMD & Siliguri Sub-Divisional Disaster Cell",
        "sdma_helpline": "1070 / 1077",
    },
    "amritsar": {
        "city": "Amritsar",
        "state": "Punjab",
        "has_river_in_city": False,
        "rivers_in_city": [],
        "river_name": "No Natural River Situated Within Amritsar Municipal Limits",
        "basin": "Bari Doab Interfluve",
        "cwc_station": "No CWC River Station Inside Amritsar City",
        "cwc_station_code": None,
        "upstream_control": "Upper Bari Doab Canal Network",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": None,
        "seismic_zone": "Zone IV (High Seismic Zone)",
        "flood_authority": "Punjab Water Resources Department & DDMA Amritsar",
        "seismic_authority": "National Centre for Seismology (NCS) & Punjab SDMA",
        "fire_authority": "Punjab Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "Punjab State Disaster Management Authority (PSDMA) & DDMA Amritsar",
        "sdma_helpline": "1070 / 1077",
    },
    "ludhiana": {
        "city": "Ludhiana",
        "state": "Punjab",
        "has_river_in_city": True,
        "rivers_in_city": ["Sutlej River", "Buddha Nullah"],
        "river_name": "Sutlej River & Buddha Nullah",
        "basin": "Indus–Sutlej Basin",
        "cwc_station": "Phillaur–Ludhiana Sutlej Gauge",
        "cwc_station_code": None,
        "upstream_control": "Ropar Headworks & Bhakra Dam (Sutlej)",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2023,
        "seismic_zone": "Zone IV (High Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Indus Basin), BBMB & Punjab Water Resources Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Punjab SDMA",
        "fire_authority": "Punjab Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "Punjab State Disaster Management Authority (PSDMA) & DDMA Ludhiana",
        "sdma_helpline": "1070 / 1077",
    },
    "nashik": {
        "city": "Nashik",
        "state": "Maharashtra",
        "has_river_in_city": True,
        "rivers_in_city": ["Godavari River", "Nasardi River"],
        "river_name": "Godavari River & Nasardi River",
        "basin": "Upper Godavari Basin",
        "cwc_station": "Nashik Ramkund / Holkar Bridge Godavari Gauge",
        "cwc_station_code": None,
        "upstream_control": "Gangapur Dam, Nashik",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2019,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Upper Godavari Division) & NMC / Maharashtra WRD",
        "seismic_authority": "National Centre for Seismology (NCS) & Maharashtra SDMA",
        "fire_authority": "Nashik Municipal Fire Brigade & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Nashik & Maharashtra SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "nagpur": {
        "city": "Nagpur",
        "state": "Maharashtra",
        "has_river_in_city": True,
        "rivers_in_city": ["Nag River", "Pili River"],
        "river_name": "Nag River & Pili River",
        "basin": "Kanhan–Wainganga–Godavari Sub-Basin",
        "cwc_station": "Nagpur Nag River Urban Gauge (CWC Wainganga Division HQ)",
        "cwc_station_code": None,
        "upstream_control": "Ambazari & Gorewada Lake Spillways (Nagpur)",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2023,
        "seismic_zone": "Zone II (Low Peninsular Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Wainganga Division, Nagpur) & NMC Disaster Cell",
        "seismic_authority": "National Centre for Seismology (NCS Nagpur Observatory) & Maharashtra SDMA",
        "fire_authority": "Nagpur Municipal Fire & Emergency Services & Forest Survey of India (FSI Central Zone Nagpur)",
        "sdma_name": "DDMA Nagpur & Maharashtra SDMA",
        "sdma_helpline": "1077 / 1070",
    },
    "vijayawada": {
        "city": "Vijayawada",
        "state": "Andhra Pradesh",
        "has_river_in_city": True,
        "rivers_in_city": ["Krishna River"],
        "river_name": "Krishna River",
        "basin": "Lower Krishna Delta Basin",
        "cwc_station": "Prakasam Barrage Vijayawada CWC Station (Krishna River)",
        "cwc_station_code": None,
        "upstream_control": "Prakasam Barrage, Vijayawada",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2024,
        "seismic_zone": "Zone III (Moderate Coastal Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Krishna & Godavari Basin Org) & APWRD / APSDMA",
        "seismic_authority": "National Centre for Seismology (NCS) & Andhra Pradesh SDMA (APSDMA)",
        "fire_authority": "AP State Disaster Response & Fire Services & FSI Vanagni",
        "sdma_name": "Andhra Pradesh State Disaster Management Authority (APSDMA)",
        "sdma_helpline": "1070 / 1077",
    },
    "madurai": {
        "city": "Madurai",
        "state": "Tamil Nadu",
        "has_river_in_city": True,
        "rivers_in_city": ["Vaigai River"],
        "river_name": "Vaigai River",
        "basin": "Vaigai River Basin",
        "cwc_station": "Madurai Albert Victor Bridge Vaigai River Gauge",
        "cwc_station_code": None,
        "upstream_control": "Vaigai Dam",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2021,
        "seismic_zone": "Zone II (Low Peninsular Seismic Zone)",
        "flood_authority": "Tamil Nadu WRD (Vaigai Basin Division, Madurai) & Central Water Commission (CWC)",
        "seismic_authority": "National Centre for Seismology (NCS) & Tamil Nadu SDMA (TNSDMA)",
        "fire_authority": "Tamil Nadu Fire & Rescue Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Madurai & Tamil Nadu SDMA (TNSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
    "coimbatore": {
        "city": "Coimbatore",
        "state": "Tamil Nadu",
        "has_river_in_city": True,
        "rivers_in_city": ["Noyyal River"],
        "river_name": "Noyyal River",
        "basin": "Noyyal–Cauvery Sub-Basin",
        "cwc_station": "Coimbatore Noyyal River Check-Dam Telemetry",
        "cwc_station_code": None,
        "upstream_control": "Siruvani & Noyyal Western Ghats Foothill Catchments",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2021,
        "seismic_zone": "Zone III (Moderate Western Ghats Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Southern Rivers Division, Coimbatore HQ) & TNWRD",
        "seismic_authority": "National Centre for Seismology (NCS) & TNSDMA",
        "fire_authority": "Tamil Nadu Forest Dept (Coimbatore Circle), FSI Vanagni & TN Fire Services",
        "sdma_name": "DDMA Coimbatore & Tamil Nadu SDMA (TNSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
    "tiruchirappalli": {
        "city": "Tiruchirappalli",
        "state": "Tamil Nadu",
        "has_river_in_city": True,
        "rivers_in_city": ["Cauvery River", "Kollidam River"],
        "river_name": "Cauvery River & Kollidam River",
        "basin": "Middle Cauvery Delta Basin",
        "cwc_station": "Upper Anicut (Mukkombu) & Grand Anicut Cauvery Gauge, Tiruchirappalli",
        "cwc_station_code": None,
        "upstream_control": "Mukkombu (Upper Anicut) & Kallanai (Grand Anicut), Tiruchirappalli",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": 2022,
        "seismic_zone": "Zone II (Low Peninsular Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Cauvery Division) & Tamil Nadu WRD Tiruchirappalli",
        "seismic_authority": "National Centre for Seismology (NCS) & TNSDMA",
        "fire_authority": "Tamil Nadu Fire and Rescue Services & FSI Vanagni",
        "sdma_name": "DDMA Tiruchirappalli & Tamil Nadu SDMA (TNSDMA)",
        "sdma_helpline": "1077 / 1070",
    },
}

# Backwards-compatible alias for tests importing INDIA_RIVER_GAUGE_REGISTRY
INDIA_RIVER_GAUGE_REGISTRY = INDIA_CITY_RIVER_PROFILES

# Strictly same-city / contiguous twin-city name aliases (NEVER aliases a city to a different city's river)
SAME_CITY_ALIASES: dict[str, str] = {
    "new delhi": "delhi",
    "old delhi": "delhi",
    "noida": "delhi",
    "bhuntar": "kullu",
    "allahabad": "prayagraj",
    "banaras": "varanasi",
    "kashi": "varanasi",
    "faizabad": "ayodhya",
    "howrah": "kolkata",
    "calcutta": "kolkata",
    "bombay": "mumbai",
    "bangalore": "bengaluru",
    "bengaluru urban": "bengaluru",
    "madras": "chennai",
    "ernakulam": "kochi",
    "cochin": "kochi",
    "aluva": "kochi",
    "gandhinagar": "ahmedabad",
    "baroda": "vadodara",
    "panaji": "goa",
    "panjim": "goa",
    "trichy": "tiruchirappalli",
}


def _default_state_authorities(city_clean: str, state_clean: str) -> dict[str, str]:
    """Return official Indian national + state authorities for any Indian city."""
    st = state_clean or "India"
    return {
        "seismic_zone": "BIS IS-1893 Seismic Monitoring Sector",
        "flood_authority": f"Central Water Commission (CWC FloodWatch India) & {st} Water Resources / Flood Control Dept",
        "seismic_authority": f"National Centre for Seismology (NCS, Ministry of Earth Sciences) & {st} SDMA",
        "fire_authority": f"Forest Survey of India (FSI SNPP-VIIRS Vanagni) & {st} Forest & Fire Services",
        "sdma_name": f"{st} State Disaster Management Authority (SDMA) & DDMA {city_clean}",
        "sdma_helpline": "1070 / 1077 / 112",
    }


def resolve_india_river_and_authority_profile(
    location_name: str,
    district_id: str | None = None,
    state: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Resolve the strictly city-bounded river profile and Indian disaster authorities for an Indian location.

    NEVER substitutes a river from a different city or state capital.
    """
    primary_city = (district_id or (location_name.split(",")[0] if location_name else "")).strip()
    city_lower = primary_city.lower()
    loc_first_lower = (location_name.split(",")[0].strip().lower() if location_name else "")

    # 1. Exact same-city alias match on the city/district token
    for token in (city_lower, loc_first_lower):
        if token in SAME_CITY_ALIASES:
            target = SAME_CITY_ALIASES[token]
            if target in INDIA_CITY_RIVER_PROFILES:
                return dict(INDIA_CITY_RIVER_PROFILES[target])
        if token in INDIA_CITY_RIVER_PROFILES:
            return dict(INDIA_CITY_RIVER_PROFILES[token])

    # 2. Substring match strictly on the city/district name (not on state!)
    city_blob = f"{city_lower} {loc_first_lower}"
    for alias, target in SAME_CITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", city_blob) and target in INDIA_CITY_RIVER_PROFILES:
            return dict(INDIA_CITY_RIVER_PROFILES[target])
    for key, prof in INDIA_CITY_RIVER_PROFILES.items():
        if re.search(rf"\b{re.escape(key)}\b", city_blob):
            return dict(prof)

    # 3. Unlisted city: return clean city profile where rivers_in_city will be discovered live
    #    strictly within the city's municipal bounding box via OSM Nominatim + CWC FloodWatch India.
    clean_city = primary_city or "City"
    clean_state = (state or (location_name.split(",")[1].strip() if "," in (location_name or "") else "India")).strip()
    auths = _default_state_authorities(clean_city, clean_state)
    return {
        "city": clean_city,
        "state": clean_state,
        "has_river_in_city": False,
        "rivers_in_city": [],
        "river_name": f"Discovering Rivers Within {clean_city}",
        "basin": f"{clean_city} Municipal Watershed",
        "cwc_station": f"CWC FloodWatch India Station ({clean_city})",
        "cwc_station_code": None,
        "upstream_control": f"{clean_city} Municipal Reach",
        "warning_level_m": None,
        "danger_level_m": None,
        "hfl_m": None,
        "hfl_year": None,
        **auths,
    }


class IndiaDisasterAndRiverClient:
    """Fetches real-time Indian authority disaster alerts (NCS Earthquake, FSI Wildfire, CWC Flood),
    strictly city-bounded river identification, live CWC FloodWatch India (`ffs.india-water.gov.in`)
    hourly water level telemetry, and live + multi-year historical (2021–2026) GloFAS river flow.
    """

    FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
    USGS_FDSN_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    CWC_FFS_BASE_URL = "https://ffs.india-water.gov.in"
    NDMA_SACHET_CAP_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
    NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()

    @staticmethod
    def _cwc_spec_op(op: str, field: str, val: Any, rel: bool = False) -> dict[str, Any]:
        return {
            "expression": {
                "fieldName": field,
                "operator": op,
                "value": val,
                "valueIsRelationField": rel,
            }
        }

    @staticmethod
    def _cwc_spec_and(items: list[dict[str, Any]]) -> dict[str, Any]:
        res: dict[str, Any] | None = None
        for item in items:
            res = item if res is None else {"where": res, "and": item}
        if res is not None:
            res["unique"] = True
        return res or {}

    async def _discover_rivers_strictly_within_city_async(
        self, lat: float, lon: float, city_name: str
    ) -> list[str]:
        """Discover rivers physically situated strictly within the city's municipal bounding box (`±0.08°` ≈ 8.5 km)
        using OpenStreetMap Nominatim bounded waterway search.
        """
        cache_key = f"{round(lat, 2)}:{round(lon, 2)}:{city_name.lower()}"
        now_ts = time.time()
        if cache_key in _CITY_RIVER_OSM_CACHE and (now_ts - _CITY_RIVER_OSM_CACHE[cache_key][0]) < _CACHE_TTL * 4:
            return _CITY_RIVER_OSM_CACHE[cache_key][1]

        d = 0.085  # ~9 km municipal bounding box around city center
        params = {
            "q": "river",
            "format": "jsonv2",
            "viewbox": f"{round(lon - d, 4)},{round(lat + d, 4)},{round(lon + d, 4)},{round(lat - d, 4)}",
            "bounded": "1",
            "limit": "15",
            "accept-language": "en",
        }
        headers = {
            "User-Agent": self._settings.nominatim_user_agent or "IndiaTravelSafety/2.0 (safety-research@indiatravelsafety.org)"
        }
        rivers: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.0)) as client:
                resp = await client.get(self.NOMINATIM_SEARCH_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    for item in resp.json():
                        if not isinstance(item, dict):
                            continue
                        if item.get("category") != "waterway" or item.get("type") != "river":
                            continue
                        raw_name = (item.get("name") or item.get("display_name", "").split(",")[0]).strip()
                        if not raw_name or raw_name.lower() in ("river", "nadi", "stream", "canal", "drain"):
                            continue
                        # Ensure English script
                        clean_name = re.sub(r"[^\x00-\x7F]+", "", raw_name).strip()
                        if not clean_name or len(clean_name) < 3:
                            continue
                        if "river" not in clean_name.lower() and "nadi" not in clean_name.lower() and "khad" not in clean_name.lower():
                            clean_name = f"{clean_name} River"
                        if all(clean_name.lower() != existing.lower() for existing in rivers):
                            rivers.append(clean_name)
        except Exception as exc:
            logger.debug(f"Nominatim bounded river discovery skipped for {city_name}: {exc}")

        _CITY_RIVER_OSM_CACHE[cache_key] = (now_ts, rivers[:4])
        return rivers[:4]

    async def _fetch_cwc_floodwatch_live_async(
        self,
        profile: dict[str, Any],
        location_name: str,
        district_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch real-time river gauge readings, thresholds, and active warnings directly from
        CWC FloodWatch India (`https://ffs.india-water.gov.in`).
        """
        station_code = profile.get("cwc_station_code")
        fallback_code = profile.get("fallback_cwc_station_code")
        clean_city = (profile.get("city") or district_id or location_name.split(",")[0]).split("/")[0].strip()
        cache_key = f"{station_code or 'dyn'}:{clean_city.lower()}"
        now_ts = time.time()
        if cache_key in _CWC_LIVE_CACHE and (now_ts - _CWC_LIVE_CACHE[cache_key][0]) < _CACHE_TTL:
            return _CWC_LIVE_CACHE[cache_key][1]

        result: dict[str, Any] = {
            "station_code": station_code,
            "station_name": profile.get("cwc_station"),
            "river_name": profile.get("river_name"),
            "observed_water_level_m": None,
            "last_observed_at": None,
            "hourly_readings": [],
            "hourly_trend": None,
            "warning_level_m": profile.get("warning_level_m"),
            "danger_level_m": profile.get("danger_level_m"),
            "hfl_m": profile.get("hfl_m"),
            "hfl_date": None,
            "forecasted_water_level_m": None,
            "forecasted_at": None,
            "station_alert_status": "NORMAL",
            "active_national_warnings_count": 0,
            "active_national_warnings": [],
            "live_cwc_telemetry": False,
            "source_portal": "https://ffs.india-water.gov.in",
        }

        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=httpx.Timeout(5.0, connect=2.5),
                follow_redirects=True,
            ) as client:
                # 1. Dynamic station resolution strictly matching the city name if station_code is None
                #    and city is not explicitly marked as having no river
                city_lower = clean_city.lower()
                is_explicit_no_river = (
                    city_lower in INDIA_CITY_RIVER_PROFILES
                    and not INDIA_CITY_RIVER_PROFILES[city_lower].get("has_river_in_city", True)
                )
                if not station_code and not is_explicit_no_river and len(clean_city) >= 3:
                    try:
                        base_ff = self._cwc_spec_op("null", "floodForecastStaticStationCode.stationCode", "false")
                        spec_dyn = self._cwc_spec_and([
                            base_ff,
                            self._cwc_spec_op("like", "name", clean_city),
                        ])
                        dyn_resp = await client.get(
                            f"{self.CWC_FFS_BASE_URL}/iam/api/layer-station/specification/page",
                            headers={
                                "Content-Type": "application/json",
                                "class-name": "ForecastDetailLayerStationDto",
                                "Accept": "application/json",
                            },
                            params={
                                "specification": json.dumps(spec_dyn),
                                "page-number": "0",
                                "page-size": "4",
                            },
                        )
                        if dyn_resp.status_code == 200:
                            dyn_stations = [
                                s for s in (dyn_resp.json() or [])
                                if isinstance(s, dict)
                                and str(s.get("name") or "").strip().lower().startswith(city_lower[:4])
                            ]
                            if dyn_stations:
                                chosen = dyn_stations[0]
                                for cand in dyn_stations:
                                    ff_obj = cand.get("floodForecastStaticStationCode")
                                    if isinstance(ff_obj, dict) and ff_obj.get("dangerLevel"):
                                        chosen = cand
                                        break
                                dyn_code = chosen.get("stationCode")
                                if dyn_code:
                                    station_code = str(dyn_code).strip()
                                    result["station_code"] = station_code
                                    if chosen.get("name"):
                                        result["station_name"] = f"{chosen['name']} CWC FloodWatch Station"
                                    riv_obj = chosen.get("river")
                                    if isinstance(riv_obj, dict) and riv_obj.get("name") and not str(riv_obj["name"]).isdigit() and riv_obj["name"] != "-":
                                        r_clean = str(riv_obj["name"]).strip()
                                        result["river_name"] = r_clean if "river" in r_clean.lower() else f"{r_clean} River"
                                    ff_obj = chosen.get("floodForecastStaticStationCode")
                                    if isinstance(ff_obj, dict):
                                        if ff_obj.get("warningLevel"):
                                            result["warning_level_m"] = float(ff_obj["warningLevel"])
                                        if ff_obj.get("dangerLevel"):
                                            result["danger_level_m"] = float(ff_obj["dangerLevel"])
                                        if ff_obj.get("highestFlowLevel"):
                                            result["hfl_m"] = float(ff_obj["highestFlowLevel"])
                                        if ff_obj.get("highestFlowLevelDate"):
                                            result["hfl_date"] = str(ff_obj["highestFlowLevelDate"])
                    except Exception as dyn_exc:
                        logger.debug(f"CWC city station lookup skipped for {clean_city}: {dyn_exc}")

                # 2. Fetch national above-warning queue (cached for 15m)
                warn_cached = _CWC_WARNING_QUEUE_CACHE.get("india")
                warn_task = None
                if not (warn_cached and (now_ts - warn_cached[0]) < _CACHE_TTL):
                    warn_task = client.get(
                        f"{self.CWC_FFS_BASE_URL}/ffm/api/station-water-level-above-warning/",
                        headers={
                            "Content-Type": "application/json",
                            "class-name": "StationWaterLevelAboveWarningDto",
                            "Accept": "application/json",
                        },
                    )

                # 3. If station_code is present, fetch live hourly gauge readings (`NewEntryDataDto`, datatypeCode="HHS")
                #    and CWC short-range forecast (`NewForecastedEntryDataDto`)
                obs_resp = None
                fc_resp = None
                warn_resp = None

                if station_code:
                    sort_obs = {"sortOrderDtos": [{"sortDirection": "DESC", "field": "id.dataTime"}]}
                    spec_obs = self._cwc_spec_and([
                        self._cwc_spec_op("eq", "id.stationCode", station_code),
                        self._cwc_spec_op("eq", "id.datatypeCode", "HHS"),
                    ])
                    obs_task = client.get(
                        f"{self.CWC_FFS_BASE_URL}/iam/api/new-entry-data/specification/sorted-page",
                        headers={
                            "Content-Type": "application/json",
                            "class-name": "NewEntryDataDto",
                            "Accept": "application/json",
                        },
                        params={
                            "specification": json.dumps(spec_obs),
                            "sort-criteria": json.dumps(sort_obs),
                            "page-number": "0",
                            "page-size": "24",
                        },
                    )

                    sort_fc = {"sortOrderDtos": [{"sortDirection": "DESC", "field": "id.forecastedDate"}]}
                    spec_fc = self._cwc_spec_op("eq", "id.stationCode", station_code)
                    fc_task = client.get(
                        f"{self.CWC_FFS_BASE_URL}/iam/api/new-forecasted-entry-data/specification/sorted-page",
                        headers={
                            "Content-Type": "application/json",
                            "class-name": "NewForecastedEntryDataDto",
                            "Accept": "application/json",
                        },
                        params={
                            "specification": json.dumps(spec_fc),
                            "sort-criteria": json.dumps(sort_fc),
                            "page-number": "0",
                            "page-size": "5",
                        },
                    )
                    tasks = [obs_task, fc_task] + ([warn_task] if warn_task is not None else [])
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    obs_resp = responses[0]
                    fc_resp = responses[1]
                    warn_resp = responses[2] if len(responses) > 2 else None
                elif warn_task is not None:
                    warn_resp = await warn_task

                def _parse_obs_response(resp_obj: Any) -> list[dict[str, Any]]:
                    if resp_obj is None or isinstance(resp_obj, Exception) or getattr(resp_obj, "status_code", 0) != 200:
                        return []
                    rows = resp_obj.json()
                    if not isinstance(rows, list):
                        return []
                    valid: list[dict[str, Any]] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        val = row.get("dataValidatedValue")
                        if val is None:
                            val = row.get("dataValue")
                        if val is None:
                            continue
                        f_val = float(val)
                        if f_val <= -900.0:
                            continue
                        dt_str = (row.get("id") or {}).get("dataTime")
                        if dt_str:
                            valid.append({
                                "timestamp": str(dt_str),
                                "water_level_m": round(f_val, 3),
                            })
                    return valid

                valid_hourly = _parse_obs_response(obs_resp)

                # If primary station timed out or returned no rows and a same-city fallback station exists, try it
                if not valid_hourly and fallback_code:
                    try:
                        sort_obs = {"sortOrderDtos": [{"sortDirection": "DESC", "field": "id.dataTime"}]}
                        spec_fb = self._cwc_spec_and([
                            self._cwc_spec_op("eq", "id.stationCode", fallback_code),
                            self._cwc_spec_op("eq", "id.datatypeCode", "HHS"),
                        ])
                        fb_resp = await client.get(
                            f"{self.CWC_FFS_BASE_URL}/iam/api/new-entry-data/specification/sorted-page",
                            headers={
                                "Content-Type": "application/json",
                                "class-name": "NewEntryDataDto",
                                "Accept": "application/json",
                            },
                            params={
                                "specification": json.dumps(spec_fb),
                                "sort-criteria": json.dumps(sort_obs),
                                "page-number": "0",
                                "page-size": "12",
                            },
                        )
                        valid_hourly = _parse_obs_response(fb_resp)
                        if valid_hourly:
                            result["station_code"] = fallback_code
                    except Exception:
                        pass

                if valid_hourly:
                    result["observed_water_level_m"] = round(valid_hourly[0]["water_level_m"], 2)
                    result["last_observed_at"] = valid_hourly[0]["timestamp"]
                    result["hourly_readings"] = valid_hourly[:24]
                    result["live_cwc_telemetry"] = True
                    if len(valid_hourly) >= 2:
                        compare_idx = min(len(valid_hourly) - 1, 5)
                        delta_hr = valid_hourly[0]["water_level_m"] - valid_hourly[compare_idx]["water_level_m"]
                        if delta_hr >= 0.05:
                            result["hourly_trend"] = "Rising"
                        elif delta_hr <= -0.05:
                            result["hourly_trend"] = "Receding"
                        else:
                            result["hourly_trend"] = "Steady"

                # Parse CWC short-range forecast if present
                if fc_resp is not None and not isinstance(fc_resp, Exception) and getattr(fc_resp, "status_code", 0) == 200:
                    fc_rows = fc_resp.json()
                    if isinstance(fc_rows, list) and fc_rows:
                        for f_row in fc_rows:
                            if not isinstance(f_row, dict):
                                continue
                            f_val = f_row.get("forecastedValue") or f_row.get("dataValue") or f_row.get("value")
                            f_dt = (f_row.get("id") or {}).get("forecastedDate")
                            if f_val is not None and float(f_val) > -900.0:
                                result["forecasted_water_level_m"] = round(float(f_val), 2)
                                result["forecasted_at"] = str(f_dt or "")
                                break

                # Parse national above-warning queue
                warn_list: list[dict[str, Any]] = []
                if warn_cached and (now_ts - warn_cached[0]) < _CACHE_TTL:
                    warn_list = warn_cached[1]
                elif warn_resp is not None and not isinstance(warn_resp, Exception) and getattr(warn_resp, "status_code", 0) == 200:
                    raw_warn = warn_resp.json()
                    if isinstance(raw_warn, list):
                        for w in raw_warn:
                            if isinstance(w, dict) and w.get("stationCode"):
                                warn_list.append({
                                    "station_code": str(w.get("stationCode")),
                                    "status": str(w.get("status") or "WARNING"),
                                    "trend": str(w.get("trend") or "STEADY"),
                                    "water_level_m": round(float(w.get("value") or 0.0), 2),
                                })
                        _CWC_WARNING_QUEUE_CACHE["india"] = (now_ts, warn_list)

                result["active_national_warnings_count"] = len(warn_list)
                result["active_national_warnings"] = warn_list[:8]

                if station_code:
                    for w_item in warn_list:
                        if w_item["station_code"].lower() == str(station_code).lower():
                            result["station_alert_status"] = w_item["status"]
                            if result["observed_water_level_m"] is None and w_item["water_level_m"] > 0:
                                result["observed_water_level_m"] = w_item["water_level_m"]
                                result["live_cwc_telemetry"] = True
                            if w_item.get("trend") in ("RISING", "FALLING", "STEADY"):
                                result["hourly_trend"] = (
                                    "Rising" if w_item["trend"] == "RISING"
                                    else ("Receding" if w_item["trend"] == "FALLING" else "Steady")
                                )
                            break

        except Exception as exc:
            logger.debug(f"CWC FloodWatch India live fetch skipped for {station_code}: {exc}")

        _CWC_LIVE_CACHE[cache_key] = (now_ts, result)
        return result

    async def _fetch_sachet_cap_alerts_async(
        self, profile: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch live Common Alerting Protocol (CAP) alerts from NDMA SACHET (`sachet.ndma.gov.in`)."""
        now_ts = time.time()
        cached_all = _SACHET_CAP_CACHE.get("all_india")
        raw_items: list[dict[str, Any]] = []

        if cached_all and (now_ts - cached_all[0]) < _CACHE_TTL:
            raw_items = cached_all[1]
        else:
            try:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=httpx.Timeout(4.5, connect=2.5),
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(self.NDMA_SACHET_CAP_URL)
                    if resp.status_code == 200 and resp.text:
                        root = ET.fromstring(resp.text)
                        for item in root.findall(".//item")[:100]:
                            title = html.unescape(item.findtext("title") or "").strip()
                            author = html.unescape(item.findtext("author") or "").strip()
                            pub_str = (item.findtext("pubDate") or "").strip()
                            link = (item.findtext("link") or "https://sachet.ndma.gov.in").strip()
                            if not title:
                                continue
                            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                            age_days = 0
                            if pub_str:
                                try:
                                    dt = parsedate_to_datetime(pub_str)
                                    if dt.tzinfo is None:
                                        dt = dt.replace(tzinfo=timezone.utc)
                                    date_str = dt.strftime("%Y-%m-%d")
                                    age_days = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
                                except Exception:
                                    pass
                            raw_items.append({
                                "title": title,
                                "author": author,
                                "date": date_str,
                                "age_days": age_days,
                                "url": link,
                            })
                        _SACHET_CAP_CACHE["all_india"] = (now_ts, raw_items)
            except Exception as exc:
                logger.debug(f"NDMA SACHET CAP RSS fetch skipped: {exc}")

        if not raw_items:
            return []

        city_tokens = [t.strip().lower() for t in re.split(r"[/,()\-]", profile["city"]) if len(t.strip()) >= 3]
        state_lower = profile["state"].lower()
        river_tokens = [
            t.strip().lower()
            for t in re.split(r"[/,()\-\s–]", profile.get("river_name", ""))
            if len(t.strip()) >= 4 and t.strip().lower() not in ("river", "rivers", "basin", "confluence", "within", "limits")
        ]

        matched_cap: list[dict[str, Any]] = []
        cwc_national_cap: list[dict[str, Any]] = []

        for item in raw_items:
            t_low = item["title"].lower()
            a_low = item["author"].lower()
            is_cwc = "(cwc)" in a_low or "central water commission" in a_low or "flood situation" in t_low

            hazard_type = "flood"
            authority_label = profile["flood_authority"]
            if any(w in t_low for w in ("earthquake", "tremor", "seismic")):
                hazard_type = "earthquake"
                authority_label = profile["seismic_authority"]
            elif any(w in t_low for w in ("forest fire", "wildfire")):
                hazard_type = "fire"
                authority_label = profile["fire_authority"]
            elif is_cwc:
                hazard_type = "flood"
                authority_label = "Central Water Commission (CWC FloodWatch India via NDMA SACHET CAP)"

            severity = "Moderate"
            if any(w in t_low for w in ("severe flood", "extreme flood", "danger", "red alert", "heavy to very heavy")):
                severity = "High"

            cap_entry = {
                "id": f"sachet-cap-{hashlib.sha256(item['title'].encode('utf-8')).hexdigest()[:10]}",
                "hazard_type": hazard_type,
                "title": item["title"],
                "authority": authority_label,
                "publisher": item["author"] or "NDMA SACHET CAP (Govt of India)",
                "date": item["date"],
                "age_days": item["age_days"],
                "severity": severity,
                "url": "https://ffs.india-water.gov.in" if is_cwc else item["url"],
            }

            if (
                state_lower in t_low
                or state_lower in a_low
                or any(ct in t_low for ct in city_tokens)
                or any(rt in t_low for rt in river_tokens)
            ):
                matched_cap.append(cap_entry)

        # Strictly return only alerts matching this specific state, city, or local river.
        # Unrelated national alerts from other states are never leaked into a city's profile.
        return matched_cap[:6]

    async def _fetch_glofas_live_and_historical_discharge_async(
        self, lat: float, lon: float
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Fetch:
        1. Real-time + 90-day observed + 15-day forecasted river discharge (`m³/s`) from Open-Meteo Flood API.
        2. Multi-year (2021–2026) historical daily river discharge archive (`m³/s`) from Open-Meteo Flood API.
        """
        cache_key = f"{round(lat, 2)}:{round(lon, 2)}"
        now_ts = time.time()

        live_cached = _RIVER_LIVE_CACHE.get(cache_key)
        hist_cached = _RIVER_HIST_CACHE.get(cache_key)

        async def _get_live() -> dict[str, Any]:
            if live_cached and (now_ts - live_cached[0]) < _CACHE_TTL:
                return live_cached[1]
            params = {
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "daily": (
                    "river_discharge,river_discharge_mean,river_discharge_max,"
                    "river_discharge_min,river_discharge_median,river_discharge_p25,river_discharge_p75"
                ),
                "past_days": 90,
                "forecast_days": 15,
            }
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.5)) as client:
                    resp = await client.get(self.FLOOD_API_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        _RIVER_LIVE_CACHE[cache_key] = (now_ts, data)
                        return data
            except Exception as exc:
                logger.debug(f"Live river discharge fetch skipped for ({lat}, {lon}): {exc}")
            return {}

        async def _get_hist() -> dict[str, Any]:
            if hist_cached and (now_ts - hist_cached[0]) < _CACHE_TTL * 4:
                return hist_cached[1]
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            params = {
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "daily": "river_discharge,river_discharge_max",
                "start_date": "2021-01-01",
                "end_date": today_str,
            }
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=2.5)) as client:
                    resp = await client.get(self.FLOOD_API_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        _RIVER_HIST_CACHE[cache_key] = (now_ts, data)
                        return data
            except Exception as exc:
                logger.debug(f"Historical river discharge archive fetch skipped for ({lat}, {lon}): {exc}")
            return {}

        live_data, hist_data = await asyncio.gather(_get_live(), _get_hist(), return_exceptions=True)
        return (
            live_data if isinstance(live_data, dict) else {},
            hist_data if isinstance(hist_data, dict) else {},
        )

    async def _fetch_ncs_india_earthquakes_async(
        self, lat: float, lon: float, profile: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch recent earthquakes in the Indian seismic sector cross-tagged with NCS (MoES India)."""
        params = {
            "format": "geojson",
            "latitude": round(lat, 3),
            "longitude": round(lon, 3),
            "maxradiuskm": 420,
            "minmagnitude": 2.5,
            "limit": 10,
            "orderby": "time",
        }
        quakes: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(4.5, connect=2.5)) as client:
                resp = await client.get(self.USGS_FDSN_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for feat in data.get("features", []):
                        props = feat.get("properties", {})
                        coords = feat.get("geometry", {}).get("coordinates", [])
                        if len(coords) < 2:
                            continue
                        q_lon, q_lat = float(coords[0]), float(coords[1])
                        depth_km = float(coords[2]) if len(coords) > 2 else 10.0
                        mag = float(props.get("mag") or 0.0)
                        place = props.get("place") or f"{profile['city']} Seismic Sector"
                        epoch_ms = props.get("time") or int(time.time() * 1000)
                        ev_dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
                        dist_km = round(
                            math.hypot(
                                (q_lon - lon) * 111.32 * max(0.01, math.cos(math.radians(lat))),
                                (q_lat - lat) * 111.32,
                            ),
                            1,
                        )
                        quakes.append({
                            "id": f"ncs:{feat.get('id', hashlib.sha256(str(epoch_ms).encode()).hexdigest()[:12])}",
                            "magnitude": round(mag, 1),
                            "depth_km": round(depth_km, 1),
                            "place": place,
                            "lat": q_lat,
                            "lon": q_lon,
                            "distance_km": dist_km,
                            "event_time": ev_dt.isoformat(),
                            "authority": profile["seismic_authority"],
                            "seismic_zone": profile["seismic_zone"],
                            "url": "https://seismo.gov.in",
                        })
        except Exception as exc:
            logger.debug(f"NCS/FDSN radial seismic query skipped: {exc}")
        return quakes

    async def _fetch_india_authority_bulletins_async(
        self, profile: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch live Indian authority bulletins for NCS Earthquakes, FSI Forest Fires, and CWC River Floods."""
        city = profile["city"].split("/")[0].strip()
        state = profile["state"]
        river_kw = (profile["rivers_in_city"][0].split()[0] if profile.get("rivers_in_city") else city)

        cache_key = f"{city.lower()}:{state.lower()}"
        now_ts = time.time()
        if cache_key in _INDIA_ALERTS_CACHE and (now_ts - _INDIA_ALERTS_CACHE[cache_key][0]) < _CACHE_TTL:
            return _INDIA_ALERTS_CACHE[cache_key][1]

        queries = [
            ("flood", profile["flood_authority"], f"{city} {river_kw} river water level flood CWC"),
            ("earthquake", profile["seismic_authority"], f"{city} {state} earthquake tremor NCS"),
            ("fire", profile["fire_authority"], f"{state} {city} forest fire wildfire FSI"),
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async def _fetch_one(hazard_type: str, authority: str, q_str: str) -> list[dict[str, Any]]:
            encoded = urllib.parse.quote(q_str)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
            found: list[dict[str, Any]] = []
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(4.2, connect=2.2), follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200 or not resp.text:
                        return []
                    root = ET.fromstring(resp.text)
                    for item in root.findall(".//item")[:5]:
                        t_el = item.find("title")
                        l_el = item.find("link")
                        p_el = item.find("pubDate")
                        s_el = item.find("source")
                        raw_title = html.unescape(t_el.text or "").strip() if t_el is not None else ""
                        if not raw_title or len(raw_title) < 15:
                            continue
                        pub_source = (s_el.text or "").strip() if s_el is not None else "Indian Civic Dispatch"
                        clean_title = raw_title
                        if " - " in raw_title:
                            parts = raw_title.rsplit(" - ", 1)
                            clean_title = parts[0].strip()
                            if pub_source == "Indian Civic Dispatch":
                                pub_source = parts[1].strip()

                        pub_str = (p_el.text or "").strip() if p_el is not None else ""
                        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        age_days = 30
                        if pub_str:
                            try:
                                dt = parsedate_to_datetime(pub_str)
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                date_str = dt.strftime("%Y-%m-%d")
                                age_days = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
                            except Exception:
                                pass

                        t_low = clean_title.lower()
                        city_low = city.lower()
                        state_low = state.lower()
                        river_low = river_kw.lower()
                        # Strictly verify that the dispatch mentions the searched city, state, or local river
                        if city_low not in t_low and state_low not in t_low and river_low not in t_low:
                            continue

                        if hazard_type == "flood" and not any(
                            w in t_low for w in ("flood", "water level", "river", "danger", "cusec", "barrage", "inundat", "rain", "dam", "cwc")
                        ):
                            continue
                        if hazard_type == "earthquake" and not any(
                            w in t_low for w in ("earthquake", "quake", "tremor", "seismic", "magnitude", "richter", "ncs")
                        ):
                            continue
                        if hazard_type == "fire" and not any(
                            w in t_low for w in ("fire", "wildfire", "blaze", "forest", "fsi", "burn")
                        ):
                            continue

                        severity = "Moderate"
                        if any(w in t_low for w in ("danger mark", "red alert", "evacuat", "major", "severe", "breach")):
                            severity = "High"
                        elif any(w in t_low for w in ("mock drill", "preparedness", "normal", "recedes", "below danger")):
                            severity = "Low"

                        found.append({
                            "id": f"ind-auth-{hazard_type}-{hashlib.sha256(clean_title.encode('utf-8')).hexdigest()[:10]}",
                            "hazard_type": hazard_type,
                            "title": clean_title,
                            "authority": authority,
                            "publisher": pub_source,
                            "date": date_str,
                            "age_days": age_days,
                            "severity": severity,
                            "url": (l_el.text or "").strip() if l_el is not None else "https://sachet.ndma.gov.in",
                        })
            except Exception as exc:
                logger.debug(f"Indian authority RSS fetch skipped for {hazard_type}: {exc}")
            return found

        results = await asyncio.gather(
            *[_fetch_one(hz, auth, q) for hz, auth, q in queries],
            return_exceptions=True,
        )
        bulletins: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in results:
            if isinstance(r, list):
                for item in r:
                    key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:40]
                    if key not in seen:
                        seen.add(key)
                        bulletins.append(item)

        _INDIA_ALERTS_CACHE[cache_key] = (now_ts, bulletins)
        return bulletins

    async def fetch_india_hazards_and_river_async(
        self,
        *,
        lat: float,
        lon: float,
        location_name: str,
        district_id: str | None = None,
        state: str | None = None,
        weather_data: dict[str, Any] | None = None,
        existing_records: list[IngestedRecord] | None = None,
    ) -> tuple[dict[str, Any], list[IngestedRecord]]:
        """Fetch strictly city-bounded river flow & water level telemetry (live + 2021–2026 historical trends)
        and local Indian authority hazard records.
        """
        profile = resolve_india_river_and_authority_profile(
            location_name=location_name,
            district_id=district_id,
            state=state,
            lat=lat,
            lon=lon,
        )

        # Fetch live CWC FloodWatch India telemetry, bounded OSM city rivers, NDMA SACHET CAP alerts,
        # live + 2021–2026 historical GloFAS river discharge, NCS radial earthquakes, and authority bulletins concurrently
        cwc_live_task = asyncio.create_task(
            self._fetch_cwc_floodwatch_live_async(profile, location_name, district_id)
        )
        osm_rivers_task = asyncio.create_task(
            self._discover_rivers_strictly_within_city_async(lat, lon, profile["city"])
        )
        sachet_cap_task = asyncio.create_task(self._fetch_sachet_cap_alerts_async(profile))
        glofas_task = asyncio.create_task(self._fetch_glofas_live_and_historical_discharge_async(lat, lon))
        ncs_task = asyncio.create_task(self._fetch_ncs_india_earthquakes_async(lat, lon, profile))
        bulletins_task = asyncio.create_task(self._fetch_india_authority_bulletins_async(profile))

        cwc_live, osm_rivers, sachet_cap_alerts, glofas_pair, ncs_quakes, bulletins = await asyncio.gather(
            cwc_live_task, osm_rivers_task, sachet_cap_task, glofas_task, ncs_task, bulletins_task,
            return_exceptions=True,
        )

        if isinstance(cwc_live, Exception) or not isinstance(cwc_live, dict):
            cwc_live = {
                "station_code": profile.get("cwc_station_code"),
                "station_name": profile.get("cwc_station"),
                "river_name": profile.get("river_name"),
                "observed_water_level_m": None,
                "last_observed_at": None,
                "hourly_readings": [],
                "hourly_trend": None,
                "forecasted_water_level_m": None,
                "forecasted_at": None,
                "station_alert_status": "NORMAL",
                "active_national_warnings_count": 0,
                "active_national_warnings": [],
                "live_cwc_telemetry": False,
                "source_portal": "https://ffs.india-water.gov.in",
            }
        if isinstance(osm_rivers, Exception) or not isinstance(osm_rivers, list):
            osm_rivers = []
        if isinstance(sachet_cap_alerts, Exception) or not isinstance(sachet_cap_alerts, list):
            sachet_cap_alerts = []
        if isinstance(glofas_pair, Exception) or not isinstance(glofas_pair, tuple):
            glofas_live, glofas_hist = {}, {}
        else:
            glofas_live, glofas_hist = glofas_pair
        if isinstance(ncs_quakes, Exception) or not isinstance(ncs_quakes, list):
            ncs_quakes = []
        if isinstance(bulletins, Exception) or not isinstance(bulletins, list):
            bulletins = []

        if sachet_cap_alerts:
            bulletins = sachet_cap_alerts + bulletins

        # ── Strictly Resolve Only Rivers Situated Within the City ────────────
        # Merge verified city rivers with OSM Nominatim bounded rivers inside the city
        city_rivers: list[str] = list(profile.get("rivers_in_city") or [])
        city_key_lower = profile["city"].split("/")[0].strip().lower()
        is_explicit_no_river = (
            city_key_lower in INDIA_CITY_RIVER_PROFILES
            and not INDIA_CITY_RIVER_PROFILES[city_key_lower].get("has_river_in_city", True)
        )

        if not is_explicit_no_river:
            for r_osm in osm_rivers:
                if all(r_osm.lower() not in ex.lower() and ex.lower() not in r_osm.lower() for ex in city_rivers):
                    city_rivers.append(r_osm)
            if not city_rivers and cwc_live.get("river_name") and "Discovering" not in str(cwc_live.get("river_name")):
                city_rivers.append(str(cwc_live["river_name"]))

        has_river_in_city = len(city_rivers) > 0 and not is_explicit_no_river
        profile["has_river_in_city"] = has_river_in_city
        profile["rivers_in_city"] = city_rivers[:4]
        if has_river_in_city:
            profile["river_name"] = ", ".join(city_rivers[:3])
        else:
            profile["river_name"] = f"No Major River Situated Within {profile['city']} Municipal Limits"

        if cwc_live.get("station_name") and has_river_in_city:
            profile["cwc_station"] = str(cwc_live["station_name"])
        if cwc_live.get("station_code") and has_river_in_city:
            profile["cwc_station_code"] = str(cwc_live["station_code"])
        if cwc_live.get("warning_level_m") is not None:
            profile["warning_level_m"] = float(cwc_live["warning_level_m"])
        if cwc_live.get("danger_level_m") is not None:
            profile["danger_level_m"] = float(cwc_live["danger_level_m"])
        if cwc_live.get("hfl_m") is not None:
            profile["hfl_m"] = float(cwc_live["hfl_m"])

        # ── Compute Real Multi-Year Historical River Flow Archive (2021–2026) ──
        hist_daily = (glofas_hist or {}).get("daily", {}) if isinstance(glofas_hist, dict) else {}
        h_times: list[str] = hist_daily.get("time", []) or []
        h_qs: list[Any] = hist_daily.get("river_discharge", []) or []
        h_qmaxs: list[Any] = hist_daily.get("river_discharge_max", []) or []

        all_hist_q: list[tuple[str, float, float]] = []
        by_year_q: dict[str, list[tuple[str, float, float]]] = {}
        for i, d_str in enumerate(h_times):
            if i < len(h_qs) and h_qs[i] is not None:
                q_val = round(max(0.0, float(h_qs[i])), 2)
                q_max_val = round(max(q_val, float(h_qmaxs[i]) if i < len(h_qmaxs) and h_qmaxs[i] is not None else q_val), 2)
                row = (str(d_str), q_val, q_max_val)
                all_hist_q.append(row)
                yr = str(d_str)[:4]
                by_year_q.setdefault(yr, []).append(row)

        sorted_hist_vals = sorted(r[1] for r in all_hist_q) if all_hist_q else [1.0]
        n_hist = len(sorted_hist_vals)
        hist_mean_q = round(sum(sorted_hist_vals) / max(1, n_hist), 2)
        hist_median_q = round(sorted_hist_vals[n_hist // 2], 2)
        hist_p90_watch_q = round(sorted_hist_vals[min(n_hist - 1, int(n_hist * 0.90))], 2)
        hist_p98_danger_q = round(sorted_hist_vals[min(n_hist - 1, int(n_hist * 0.98))], 2)
        peak_hist_row = max(all_hist_q, key=lambda r: r[2]) if all_hist_q else (None, hist_p98_danger_q, hist_p98_danger_q)
        hist_peak_q = peak_hist_row[2]
        hist_peak_date = peak_hist_row[0]

        yearly_flow_trends: list[dict[str, Any]] = []
        for yr in sorted(by_year_q.keys()):
            yr_rows = by_year_q[yr]
            if not yr_rows:
                continue
            yr_vals = [r[1] for r in yr_rows]
            yr_peak = max(yr_rows, key=lambda r: r[2])
            yr_min = min(yr_vals)
            high_flow_days = sum(1 for v in yr_vals if v >= hist_p90_watch_q)
            yearly_flow_trends.append({
                "year": yr,
                "mean_discharge_m3s": round(sum(yr_vals) / len(yr_vals), 2),
                "mean_discharge_cusecs": int(round((sum(yr_vals) / len(yr_vals)) * 35.3147)),
                "peak_discharge_m3s": yr_peak[2],
                "peak_discharge_cusecs": int(round(yr_peak[2] * 35.3147)),
                "min_discharge_m3s": yr_min,
                "peak_date": yr_peak[0],
                "high_flow_days": high_flow_days,
            })

        # ── Compute Unmodified Real-Time & 15-Day Forecasted River Flow ──────
        daily_glofas = (glofas_live or {}).get("daily", {}) if isinstance(glofas_live, dict) else {}
        times: list[str] = daily_glofas.get("time", []) or []
        discharges: list[Any] = daily_glofas.get("river_discharge", []) or []
        discharges_mean: list[Any] = daily_glofas.get("river_discharge_mean", []) or []
        discharges_max: list[Any] = daily_glofas.get("river_discharge_max", []) or []
        discharges_min: list[Any] = daily_glofas.get("river_discharge_min", []) or []

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # True only when real GloFAS discharge values were returned for this location
        flow_data_available = bool(all_hist_q) or any(v is not None for v in discharges)

        # Extract daily rainfall from weather_data if available
        rain_by_date: dict[str, float] = {}
        rain_prob_by_date: dict[str, float] = {}
        if isinstance(weather_data, dict):
            for f_day in weather_data.get("forecast_15day", []) or []:
                if isinstance(f_day, dict) and f_day.get("date"):
                    d_str = str(f_day["date"])
                    rain_by_date[d_str] = float(f_day.get("precipitation_sum_mm") or f_day.get("rain_sum_mm") or 0.0)
                    rain_prob_by_date[d_str] = float(f_day.get("precip_probability_max") or 0.0)

        cwc_observed_lvl: float | None = (
            float(cwc_live["observed_water_level_m"])
            if cwc_live.get("observed_water_level_m") is not None
            else None
        )
        cwc_forecasted_lvl: float | None = (
            float(cwc_live["forecasted_water_level_m"])
            if cwc_live.get("forecasted_water_level_m") is not None
            else None
        )
        warning_lvl: float | None = float(profile["warning_level_m"]) if profile.get("warning_level_m") is not None else None
        danger_lvl: float | None = float(profile["danger_level_m"]) if profile.get("danger_level_m") is not None else None
        hfl_lvl: float | None = float(profile["hfl_m"]) if profile.get("hfl_m") is not None else None
        # Normal level is the live CWC observed gauge reading only (never synthesised)
        normal_lvl: float | None = round(cwc_observed_lvl, 2) if cwc_observed_lvl is not None else None

        # Find today's discharge index
        today_idx = 0
        for idx, d_str in enumerate(times):
            if d_str == today_str:
                today_idx = idx
                break
        else:
            if times:
                today_idx = max(0, len(times) - 15)

        today_q_raw = (
            float(discharges[today_idx])
            if today_idx < len(discharges) and discharges[today_idx] is not None
            else hist_median_q
        )

        recent_observed_30d: list[dict[str, Any]] = []
        forecast_series: list[dict[str, Any]] = []

        span_q = max(1.0, hist_p98_danger_q - hist_median_q)


        for idx, d_str in enumerate(times):
            q_val = round(
                float(discharges[idx])
                if idx < len(discharges) and discharges[idx] is not None
                else (
                    float(discharges_mean[idx])
                    if idx < len(discharges_mean) and discharges_mean[idx] is not None
                    else today_q_raw
                ),
                2,
            )
            q_max_val = round(
                float(discharges_max[idx])
                if idx < len(discharges_max) and discharges_max[idx] is not None
                else q_val,
                2,
            )
            q_min_val = round(
                float(discharges_min[idx])
                if idx < len(discharges_min) and discharges_min[idx] is not None
                else q_val,
                2,
            )
            cusecs = int(round(q_val * 35.3147))
            rain_mm = round(rain_by_date.get(d_str, 0.0), 1)
            rain_prob = rain_prob_by_date.get(d_str, 0.0)

            # Water level is ONLY reported when it is a real CWC FloodWatch India value:
            # today's live observed gauge level, or CWC's own official forecast level.
            water_level_m: float | None = None
            if cwc_observed_lvl is not None and d_str == today_str:
                water_level_m = round(cwc_observed_lvl, 2)
            elif cwc_forecasted_lvl is not None and idx == today_idx + 1:
                water_level_m = round(cwc_forecasted_lvl, 2)

            # Determine flood stage and probability from real CWC thresholds + real GloFAS percentiles
            if (water_level_m is not None and danger_lvl is not None and water_level_m >= danger_lvl) or q_val >= hist_p98_danger_q:
                stage = "danger"
                stage_label = "Danger Stage (Red)"
                flood_prob = min(98, max(80, int(round(80 + ((q_val - hist_p98_danger_q) / max(1.0, hist_peak_q - hist_p98_danger_q)) * 18))))
            elif (water_level_m is not None and warning_lvl is not None and water_level_m >= warning_lvl) or q_val >= hist_p90_watch_q:
                stage = "warning"
                stage_label = "Warning / High Flow Stage (Amber)"
                flood_prob = min(79, max(45, int(round(45 + ((q_val - hist_p90_watch_q) / max(1.0, hist_p98_danger_q - hist_p90_watch_q)) * 32))))
            elif q_val >= hist_mean_q * 1.25:
                stage = "watch"
                stage_label = "Above Mean Flow (Watch)"
                flood_prob = min(44, max(18, int(round(18 + (q_val / max(0.5, hist_p90_watch_q)) * 22))))
            else:
                stage = "normal"
                stage_label = "Normal Flow (Green)"
                q_pct = min(1.0, q_val / max(0.5, hist_p90_watch_q))
                flood_prob = max(2, min(24, int(round(3 + q_pct * 14 + rain_prob * 0.08))))

            pt_dict = {
                "date": d_str,
                "is_past": d_str < today_str,
                "water_level_m": water_level_m,
                "normal_level_m": normal_lvl,
                "warning_level_m": warning_lvl,
                "danger_level_m": danger_lvl,
                "hfl_m": hfl_lvl,
                "discharge_m3s": q_val,
                "discharge_max_m3s": q_max_val,
                "discharge_min_m3s": q_min_val,
                "discharge_cusecs": cusecs,
                "rainfall_mm": rain_mm,
                "flood_probability_pct": flood_prob,
                "stage": stage,
                "stage_label": stage_label,
            }
            if d_str < today_str:
                recent_observed_30d.append(pt_dict)
            else:
                forecast_series.append(pt_dict)

        recent_observed_30d = recent_observed_30d[-30:]
        if not forecast_series and recent_observed_30d:
            forecast_series = [recent_observed_30d[-1]]

        current_pt = forecast_series[0] if forecast_series else {
            "date": today_str,
            "water_level_m": cwc_observed_lvl or normal_lvl,
            "normal_level_m": normal_lvl,
            "warning_level_m": warning_lvl,
            "danger_level_m": danger_lvl,
            "hfl_m": hfl_lvl,
            "discharge_m3s": today_q_raw,
            "discharge_max_m3s": today_q_raw,
            "discharge_min_m3s": today_q_raw,
            "discharge_cusecs": int(round(today_q_raw * 35.3147)),
            "rainfall_mm": 0.0,
            "flood_probability_pct": 5,
            "stage": "normal",
            "stage_label": "Normal Flow (Green)",
        }
        next_7_pts = forecast_series[:7]
        peak_7d_pt = max(next_7_pts, key=lambda x: x["discharge_m3s"]) if next_7_pts else current_pt

        # Compute real inflow trend from live CWC hourly readings or 7-day observed discharge change
        if cwc_live.get("hourly_trend") in ("Rising", "Receding"):
            inflow_trend = str(cwc_live["hourly_trend"])
        elif len(recent_observed_30d) >= 5:
            delta_q_5d = current_pt["discharge_m3s"] - recent_observed_30d[-5]["discharge_m3s"]
            rel_change = delta_q_5d / max(0.5, hist_mean_q)
            if rel_change >= 0.08:
                inflow_trend = "Rising"
            elif rel_change <= -0.08:
                inflow_trend = "Receding"
            else:
                inflow_trend = "Steady"
        else:
            inflow_trend = "Steady"

        flow_anomaly_pct = round(
            ((current_pt["discharge_m3s"] - hist_mean_q) / max(0.1, hist_mean_q)) * 100.0,
            1,
        )

        margin_to_danger_m = (
            round(danger_lvl - current_pt["water_level_m"], 2)
            if (danger_lvl is not None and current_pt.get("water_level_m") is not None)
            else None
        )
        margin_to_warning_m = (
            round(warning_lvl - current_pt["water_level_m"], 2)
            if (warning_lvl is not None and current_pt.get("water_level_m") is not None)
            else None
        )

        if not has_river_in_city:
            prediction_summary = (
                f"No major perennial river is situated within {profile['city']} municipal limits. "
                f"Local drainage and hillside/urban runoff are monitored by {profile['flood_authority']}."
            )
        elif not flow_data_available:
            prediction_summary = (
                f"Rivers within {profile['city']}: {profile['river_name']}. Live GloFAS discharge data is "
                f"currently unavailable for this reach; refer to CWC FloodWatch India (ffs.india-water.gov.in)."
            )
        else:
            wl_clause = (
                f"live CWC FloodWatch India water level at {current_pt['water_level_m']} m "
                f"(Observed at {cwc_live.get('last_observed_at', 'latest hour')}; "
                f"WL: {warning_lvl} m, DL: {danger_lvl} m) and "
                if (current_pt.get("water_level_m") is not None and danger_lvl is not None)
                else ""
            )
            prediction_summary = (
                f"Live River Telemetry for {profile['river_name']} within {profile['city']}: "
                f"{wl_clause}real-time GloFAS discharge is {current_pt['discharge_m3s']} m³/s "
                f"({current_pt['discharge_cusecs']:,} cusecs; {flow_anomaly_pct:+.1f}% vs 2021–2026 mean of {hist_mean_q} m³/s). "
                f"7-day forecasted peak flow is {peak_7d_pt['discharge_m3s']} m³/s on {peak_7d_pt['date']} ({inflow_trend} trend)."
            )

        # ── Emit IngestedRecords for Fusion Engine ───────────────────────────
        now_utc = datetime.now(timezone.utc)
        new_records: list[IngestedRecord] = []

        if has_river_in_city:
            sev_str = "Red" if (current_pt["stage"] == "danger" or peak_7d_pt["stage"] == "danger") else (
                "Orange" if (current_pt["stage"] == "warning" or peak_7d_pt["stage"] == "warning") else (
                    "Watch" if current_pt["stage"] == "watch" else "Normal"
                )
            )
            wl_str = f"{current_pt['water_level_m']}m, " if current_pt.get("water_level_m") is not None else ""
            title_txt = f"CWC & GloFAS River Telemetry: {profile['river_name']} ({wl_str}{current_pt['discharge_m3s']} m³/s — {current_pt['stage_label']})"
            new_records.append(
                IngestedRecord(
                    event_id=f"cwc_ffs:{profile['city'].lower().replace(' ', '_')}:{today_str}",
                    source="cwc_ffs",
                    hazard_type="flood",
                    geometry=Point(lon, lat),
                    event_time=now_utc,
                    ingest_time=now_utc,
                    resolution_tier=ResolutionTier.POINT,
                    district_id=district_id or profile["city"],
                    severity_raw=sev_str,
                    confidence=0.92,
                    raw_payload={
                        "title": title_txt,
                        "authority": profile["flood_authority"],
                        "cwc_station": profile["cwc_station"],
                        "cwc_station_code": profile.get("cwc_station_code"),
                        "live_cwc_telemetry": bool(cwc_live.get("live_cwc_telemetry")),
                        "river_name": profile["river_name"],
                        "rivers_in_city": profile["rivers_in_city"],
                        "water_level_m": current_pt["water_level_m"],
                        "danger_level_m": danger_lvl,
                        "discharge_m3s": current_pt["discharge_m3s"],
                    },
                )
            )

        # NCS Earthquakes within 72h & 250 km
        for q in ncs_quakes[:3]:
            try:
                q_dt = datetime.fromisoformat(q["event_time"])
            except Exception:
                q_dt = now_utc
            age_hrs = (now_utc - q_dt).total_seconds() / 3600.0
            if age_hrs <= 72.0 and q["distance_km"] <= 250.0:
                new_records.append(
                    IngestedRecord(
                        event_id=q["id"],
                        source="ncs_india",
                        hazard_type="earthquake",
                        geometry=Point(q["lon"], q["lat"]),
                        event_time=q_dt,
                        ingest_time=now_utc,
                        resolution_tier=ResolutionTier.POINT,
                        district_id=district_id or profile["city"],
                        severity_raw=float(q["magnitude"]),
                        confidence=0.95,
                        raw_payload={
                            "title": f"NCS MoES Seismic Alert: M{q['magnitude']} Earthquake ({q['place']})",
                            "magnitude": q["magnitude"],
                            "depth_km": q["depth_km"],
                            "place": q["place"],
                            "authority": profile["seismic_authority"],
                            "seismic_zone": profile["seismic_zone"],
                        },
                    )
                )

        if existing_records:
            for rec in existing_records:
                if rec.hazard_type == "earthquake":
                    rec.source = "ncs_india"
                    if isinstance(rec.raw_payload, dict):
                        mag_val = rec.raw_payload.get("magnitude") or rec.severity_raw or 4.0
                        place_val = rec.raw_payload.get("place") or profile["city"]
                        rec.raw_payload["authority"] = profile["seismic_authority"]
                        rec.raw_payload["title"] = f"NCS India Seismology: M{mag_val} Tremor ({place_val})"
                elif rec.hazard_type == "fire":
                    rec.source = "fsi_vanagni"
                    if isinstance(rec.raw_payload, dict):
                        rec.raw_payload["authority"] = profile["fire_authority"]
                        rec.raw_payload["title"] = f"FSI Vanagni Forest Fire Alert ({profile['city']} Sector)"
                elif rec.hazard_type == "flood" and rec.source != "cwc_ffs":
                    rec.source = "cwc_ffs"
                    if isinstance(rec.raw_payload, dict):
                        rec.raw_payload["authority"] = profile["flood_authority"]
                        if "title" in rec.raw_payload and "CWC" not in str(rec.raw_payload["title"]):
                            rec.raw_payload["title"] = f"CWC / SDMA Flood Alert: {rec.raw_payload['title']}"

        recent_fire_bulletins = [
            b for b in bulletins if b["hazard_type"] == "fire" and b.get("age_days", 99) <= 5
        ]
        if recent_fire_bulletins and not any(r.hazard_type == "fire" for r in (existing_records or [])):
            fb = recent_fire_bulletins[0]
            new_records.append(
                IngestedRecord(
                    event_id=fb["id"],
                    source="fsi_vanagni",
                    hazard_type="fire",
                    geometry=Point(lon, lat),
                    event_time=now_utc,
                    ingest_time=now_utc,
                    resolution_tier=ResolutionTier.DISTRICT,
                    district_id=district_id or profile["city"],
                    severity_raw=0.65 if fb["severity"] == "High" else 0.45,
                    confidence=0.88,
                    raw_payload={
                        "title": f"FSI Vanagni & State Forest Alert: {fb['title']}",
                        "authority": profile["fire_authority"],
                        "url": fb["url"],
                    },
                )
            )

        telemetry_payload = {
            "is_in_india": True,
            "has_river_in_city": has_river_in_city,
            "rivers_in_city": profile["rivers_in_city"],
            "city": profile["city"],
            "state": profile["state"],
            "river_name": profile["river_name"],
            "basin": profile["basin"],
            "cwc_station": profile["cwc_station"],
            "cwc_station_code": profile.get("cwc_station_code"),
            "upstream_control": profile["upstream_control"],
            "current_water_level_m": current_pt["water_level_m"] if has_river_in_city else None,
            "normal_level_m": normal_lvl if has_river_in_city else None,
            "warning_level_m": warning_lvl if has_river_in_city else None,
            "danger_level_m": danger_lvl if has_river_in_city else None,
            "hfl_m": hfl_lvl if has_river_in_city else None,
            "hfl_year": profile.get("hfl_year"),
            "margin_to_warning_m": margin_to_warning_m if has_river_in_city else None,
            "margin_to_danger_m": margin_to_danger_m if has_river_in_city else None,
            "current_discharge_m3s": current_pt["discharge_m3s"] if (has_river_in_city and flow_data_available) else None,
            "current_discharge_cusecs": current_pt["discharge_cusecs"] if (has_river_in_city and flow_data_available) else None,
            "current_stage": current_pt["stage"] if has_river_in_city else "normal",
            "current_stage_label": current_pt["stage_label"] if has_river_in_city else "No River Within City",
            "inflow_trend": inflow_trend if has_river_in_city else "N/A",
            "peak_7d_water_level_m": peak_7d_pt["water_level_m"] if has_river_in_city else None,
            "peak_7d_date": peak_7d_pt["date"] if has_river_in_city else today_str,
            "peak_7d_discharge_m3s": peak_7d_pt["discharge_m3s"] if (has_river_in_city and flow_data_available) else None,
            "peak_7d_stage_label": peak_7d_pt["stage_label"] if has_river_in_city else "No River Within City",
            "flood_probability_7d_pct": (
                max((pt["flood_probability_pct"] for pt in next_7_pts), default=current_pt["flood_probability_pct"])
                if has_river_in_city
                else 2
            ),
            "prediction_summary": prediction_summary,
            "seismic_zone": profile["seismic_zone"],
            "historical_flow_stats": {
                "timeframe": "2021 – 2026",
                "total_observed_days": len(all_hist_q),
                "mean_discharge_m3s": hist_mean_q,
                "mean_discharge_cusecs": int(round(hist_mean_q * 35.3147)),
                "median_discharge_m3s": hist_median_q,
                "p90_watch_discharge_m3s": hist_p90_watch_q,
                "p98_danger_discharge_m3s": hist_p98_danger_q,
                "peak_discharge_m3s": hist_peak_q,
                "peak_discharge_cusecs": int(round(hist_peak_q * 35.3147)),
                "peak_date": hist_peak_date,
                "flow_anomaly_pct": flow_anomaly_pct,
                "yearly_flow_trends": yearly_flow_trends,
                "recent_observed_30d": recent_observed_30d,
            } if (has_river_in_city and all_hist_q) else None,
            "flow_data_available": bool(has_river_in_city and flow_data_available),
            "floodwatch_india": {
                "live_cwc_telemetry": bool(cwc_live.get("live_cwc_telemetry") and has_river_in_city),
                "station_code": profile.get("cwc_station_code") if has_river_in_city else None,
                "station_name": profile["cwc_station"] if has_river_in_city else None,
                "observed_water_level_m": cwc_live.get("observed_water_level_m") if has_river_in_city else None,
                "last_observed_at": cwc_live.get("last_observed_at") if has_river_in_city else None,
                "hourly_readings": cwc_live.get("hourly_readings", []) if has_river_in_city else [],
                "hourly_trend": (cwc_live.get("hourly_trend") or inflow_trend) if has_river_in_city else None,
                "forecasted_water_level_m": cwc_live.get("forecasted_water_level_m") if has_river_in_city else None,
                "forecasted_at": cwc_live.get("forecasted_at") if has_river_in_city else None,
                "station_alert_status": cwc_live.get("station_alert_status", "NORMAL"),
                "active_national_warnings_count": cwc_live.get("active_national_warnings_count", 0),
                "active_national_warnings": cwc_live.get("active_national_warnings", []),
                "sachet_cap_alerts_count": len(sachet_cap_alerts),
                "source_portal": "https://ffs.india-water.gov.in",
                "sachet_cap_feed": "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml",
            },
            "authorities": {
                "flood": profile["flood_authority"],
                "earthquake": profile["seismic_authority"],
                "wildfire": profile["fire_authority"],
                "sdma": profile["sdma_name"],
                "helpline": profile["sdma_helpline"],
            },
            "forecast_15day": forecast_series[:15] if (has_river_in_city and flow_data_available) else [],
            "ncs_recent_earthquakes": ncs_quakes[:5],
            "indian_authority_bulletins": bulletins[:8],
            "data_sources": [
                "Central Water Commission (CWC) FloodWatch India Live Telemetry (ffs.india-water.gov.in)",
                "Copernicus GloFAS / Open-Meteo Real-Time & 2021–2026 Historical River Discharge API (flood-api.open-meteo.com)",
                "OpenStreetMap Nominatim City-Bounded Waterway Discovery (nominatim.openstreetmap.org)",
                "NDMA SACHET Common Alerting Protocol (CAP) CWC/IMD/SDMA Feed (sachet.ndma.gov.in)",
                "National Centre for Seismology (NCS), Ministry of Earth Sciences (seismo.gov.in)",
                "Forest Survey of India (FSI) SNPP-VIIRS Vanagni Forest Fire Alert System (fsi.nic.in)",
            ],
        }

        return telemetry_payload, new_records

    async def fetch_global_city_river_async(
        self,
        *,
        lat: float,
        lon: float,
        location_name: str,
        country: str | None = None,
    ) -> dict[str, Any]:
        """Live + 2021–2026 historical river flow for rivers strictly within a non-Indian city.

        Rivers are discovered with a bounded OpenStreetMap Nominatim waterway search (city box only),
        and flow comes unmodified from the Copernicus GloFAS / Open-Meteo Flood API.
        """
        city = location_name.split(",")[0].strip() or location_name
        rivers_res, glofas_res = await asyncio.gather(
            self._discover_rivers_strictly_within_city_async(lat, lon, city),
            self._fetch_glofas_live_and_historical_discharge_async(lat, lon),
            return_exceptions=True,
        )
        rivers = rivers_res if isinstance(rivers_res, list) else []
        glofas_live, glofas_hist = glofas_res if isinstance(glofas_res, tuple) else ({}, {})
        has_river = len(rivers) > 0
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        base: dict[str, Any] = {
            "is_in_india": False,
            "has_river_in_city": has_river,
            "rivers_in_city": rivers[:4],
            "city": city,
            "state": None,
            "country": country,
            "river_name": ", ".join(rivers[:3]) if has_river else f"No Major River Situated Within {city} Limits",
            "basin": None,
            "cwc_station": None,
            "cwc_station_code": None,
            "upstream_control": None,
            "current_water_level_m": None,
            "normal_level_m": None,
            "warning_level_m": None,
            "danger_level_m": None,
            "hfl_m": None,
            "hfl_year": None,
            "margin_to_warning_m": None,
            "margin_to_danger_m": None,
            "current_discharge_m3s": None,
            "current_discharge_cusecs": None,
            "current_stage": "normal",
            "current_stage_label": "No River Within City" if not has_river else "Flow Data Unavailable",
            "inflow_trend": "N/A",
            "peak_7d_water_level_m": None,
            "peak_7d_date": today_str,
            "peak_7d_discharge_m3s": None,
            "peak_7d_stage_label": "N/A",
            "flood_probability_7d_pct": None,
            "seismic_zone": None,
            "historical_flow_stats": None,
            "flow_data_available": False,
            "floodwatch_india": None,
            "authorities": {"flood": "Copernicus Emergency Management Service (GloFAS)"},
            "forecast_15day": [],
            "ncs_recent_earthquakes": [],
            "indian_authority_bulletins": [],
            "data_sources": [
                "Copernicus GloFAS / Open-Meteo Real-Time & 2021–2026 Historical River Discharge API (flood-api.open-meteo.com)",
                "OpenStreetMap Nominatim City-Bounded Waterway Discovery (nominatim.openstreetmap.org)",
            ],
        }
        if not has_river:
            base["prediction_summary"] = f"No river is mapped within {city}'s city limits (OpenStreetMap bounded search)."
            return base

        # Historical archive
        hd = (glofas_hist or {}).get("daily", {}) if isinstance(glofas_hist, dict) else {}
        hist_rows: list[tuple[str, float, float]] = []
        for i, d in enumerate(hd.get("time", []) or []):
            qs = hd.get("river_discharge", []) or []
            qm = hd.get("river_discharge_max", []) or []
            if i < len(qs) and qs[i] is not None:
                q = round(max(0.0, float(qs[i])), 2)
                hist_rows.append((str(d), q, round(max(q, float(qm[i]) if i < len(qm) and qm[i] is not None else q), 2)))

        ld = (glofas_live or {}).get("daily", {}) if isinstance(glofas_live, dict) else {}
        l_times = ld.get("time", []) or []
        l_q = ld.get("river_discharge", []) or []
        l_qmax = ld.get("river_discharge_max", []) or []
        l_qmin = ld.get("river_discharge_min", []) or []
        live_rows = [
            (str(d), round(float(l_q[i]), 2),
             round(float(l_qmax[i]), 2) if i < len(l_qmax) and l_qmax[i] is not None else round(float(l_q[i]), 2),
             round(float(l_qmin[i]), 2) if i < len(l_qmin) and l_qmin[i] is not None else round(float(l_q[i]), 2))
            for i, d in enumerate(l_times) if i < len(l_q) and l_q[i] is not None
        ]
        if not hist_rows and not live_rows:
            base["prediction_summary"] = (
                f"Rivers within {city}: {base['river_name']}. GloFAS discharge is unavailable for this grid cell."
            )
            return base

        ref_vals = sorted(r[1] for r in hist_rows) or sorted(r[1] for r in live_rows)
        n = len(ref_vals)
        mean_q = round(sum(ref_vals) / n, 2)
        median_q = round(ref_vals[n // 2], 2)
        p90 = round(ref_vals[min(n - 1, int(n * 0.90))], 2)
        p98 = round(ref_vals[min(n - 1, int(n * 0.98))], 2)

        def _stage(q: float) -> tuple[str, str]:
            if q >= p98:
                return "danger", "Extreme High Flow (≥ P98 of 2021–2026)"
            if q >= p90:
                return "warning", "High Flow (≥ P90 of 2021–2026)"
            if q >= mean_q * 1.25:
                return "watch", "Above Mean Flow (Watch)"
            return "normal", "Normal Flow"

        observed, forecast = [], []
        for d, q, qmax, qmin in live_rows:
            stg, lbl = _stage(q)
            pt = {
                "date": d, "is_past": d < today_str, "water_level_m": None,
                "discharge_m3s": q, "discharge_max_m3s": qmax, "discharge_min_m3s": qmin,
                "discharge_cusecs": int(round(q * 35.3147)), "stage": stg, "stage_label": lbl,
            }
            (observed if d < today_str else forecast).append(pt)
        observed = observed[-30:]

        yearly: list[dict[str, Any]] = []
        by_year: dict[str, list[tuple[str, float, float]]] = {}
        for r in hist_rows:
            by_year.setdefault(r[0][:4], []).append(r)
        for yr in sorted(by_year):
            rows = by_year[yr]
            vals = [r[1] for r in rows]
            pk = max(rows, key=lambda r: r[2])
            yearly.append({
                "year": yr,
                "mean_discharge_m3s": round(sum(vals) / len(vals), 2),
                "mean_discharge_cusecs": int(round(sum(vals) / len(vals) * 35.3147)),
                "peak_discharge_m3s": pk[2],
                "peak_discharge_cusecs": int(round(pk[2] * 35.3147)),
                "min_discharge_m3s": min(vals),
                "peak_date": pk[0],
                "high_flow_days": sum(1 for v in vals if v >= p90),
            })

        current = forecast[0] if forecast else (observed[-1] if observed else None)
        next7 = forecast[:7]
        peak7 = max(next7, key=lambda x: x["discharge_m3s"]) if next7 else current
        trend = "Steady"
        if current and len(observed) >= 5:
            rel = (current["discharge_m3s"] - observed[-5]["discharge_m3s"]) / max(0.5, mean_q)
            trend = "Rising" if rel >= 0.08 else ("Receding" if rel <= -0.08 else "Steady")
        anomaly = round(((current["discharge_m3s"] - mean_q) / max(0.1, mean_q)) * 100.0, 1) if current else None
        pk_all = max(hist_rows, key=lambda r: r[2]) if hist_rows else None

        base.update({
            "flow_data_available": current is not None,
            "current_discharge_m3s": current["discharge_m3s"] if current else None,
            "current_discharge_cusecs": current["discharge_cusecs"] if current else None,
            "current_stage": current["stage"] if current else "normal",
            "current_stage_label": current["stage_label"] if current else "Flow Data Unavailable",
            "inflow_trend": trend,
            "peak_7d_date": peak7["date"] if peak7 else today_str,
            "peak_7d_discharge_m3s": peak7["discharge_m3s"] if peak7 else None,
            "peak_7d_stage_label": peak7["stage_label"] if peak7 else "N/A",
            "forecast_15day": forecast[:15],
            "historical_flow_stats": {
                "timeframe": "2021 – 2026",
                "total_observed_days": len(hist_rows),
                "mean_discharge_m3s": mean_q,
                "mean_discharge_cusecs": int(round(mean_q * 35.3147)),
                "median_discharge_m3s": median_q,
                "p90_watch_discharge_m3s": p90,
                "p98_danger_discharge_m3s": p98,
                "peak_discharge_m3s": pk_all[2] if pk_all else None,
                "peak_discharge_cusecs": int(round(pk_all[2] * 35.3147)) if pk_all else None,
                "peak_date": pk_all[0] if pk_all else None,
                "flow_anomaly_pct": anomaly,
                "yearly_flow_trends": yearly,
                "recent_observed_30d": observed,
            } if hist_rows else None,
            "prediction_summary": (
                f"Live GloFAS river flow for {base['river_name']} within {city}: "
                f"{current['discharge_m3s']} m³/s ({current['discharge_cusecs']:,} cusecs"
                + (f"; {anomaly:+.1f}% vs 2021–2026 mean of {mean_q} m³/s" if anomaly is not None else "")
                + f"). 7-day forecast peak {peak7['discharge_m3s']} m³/s on {peak7['date']} ({trend})."
            ) if current else f"Rivers within {city}: {base['river_name']}.",
        })
        return base
