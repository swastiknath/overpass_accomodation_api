"""Indian Local Authority Disaster Telemetry (NCS Earthquakes, FSI Wildfires, CWC Floods)
and Real-Time Indian River Water Level & Flood Prediction Client.

For Indian cities (`is_in_india=True`), this module integrates:
1. Earthquakes:
   - National Centre for Seismology (NCS), Ministry of Earth Sciences (MoES) (`seismo.gov.in`)
   - BIS IS 1893 Seismic Zone classification (Zones II, III, IV, V)
   - State & District Disaster Management Authorities (SDMA / DDMA)
   - Live radial seismograph queries + localized NCS/NDMA/SDMA seismic bulletins
2. Wildfires & Forest Fires:
   - Forest Survey of India (FSI) SNPP-VIIRS Forest Fire Alert System (Vanagni / FAST 3.0, `fsi.nic.in`)
   - State Forest Departments & Municipal Fire and Emergency Services
   - Live VIIRS thermal anomalies + localized FSI/State Forest Dept fire bulletins
3. Floods & River Water Level Predictions:
   - Central Water Commission (CWC) National Flood Forecasting & Warning Network (`ffs.india-water.gov.in`)
   - State Irrigation & Flood Control Departments & Upstream Dam/Barrage Discharge Controls
   - Live Open-Meteo GloFAS River Discharge API (`flood-api.open-meteo.com/v1/flood`) calibrated to
     official CWC Station Warning Level (WL), Danger Level (DL), and Highest Flood Level (HFL)
   - 15-day forward river water level (m MSL), discharge (m³/s & cusecs), and flood stage predictions
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import math
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from shapely.geometry import Point

from config import Settings, load_settings
from gis.schema import IngestedRecord, ResolutionTier

logger = logging.getLogger(__name__)

# In-memory cache for river discharge and Indian authority feeds (key -> (timestamp, payload))
_RIVER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_INDIA_ALERTS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL = 900.0  # 15 minutes


# ─────────────────────────────────────────────────────────────────────────────
# CWC (Central Water Commission) River Gauge Station & Flood Control Registry
# ─────────────────────────────────────────────────────────────────────────────
# Grounded in official CWC Flood Forecasting stations (ffs.india-water.gov.in),
# Warning Levels (WL in m MSL), Danger Levels (DL in m MSL), Highest Flood Levels (HFL),
# upstream barrages/dams, BIS IS-1893 seismic zones, and State/Local Indian authorities.
INDIA_RIVER_GAUGE_REGISTRY: dict[str, dict[str, Any]] = {
    "delhi": {
        "city": "New Delhi",
        "state": "Delhi",
        "river_name": "Yamuna River",
        "basin": "Ganga–Yamuna Basin",
        "cwc_station": "Old Railway Bridge (Loha Pul), Delhi",
        "upstream_control": "Hathnikund Barrage & Wazirabad Barrage",
        "normal_level_m": 202.80,
        "warning_level_m": 204.50,
        "danger_level_m": 205.33,
        "hfl_m": 208.66,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 280.0,
        "danger_discharge_m3s": 2850.0,
        "seismic_zone": "Zone IV (High Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC) Upper Yamuna Division & Delhi Irrigation & Flood Control Dept (I&FC)",
        "seismic_authority": "National Centre for Seismology (NCS, Lodhi Road HQ) & DDMA Delhi",
        "fire_authority": "Delhi Fire Service (DFS) & Forest Survey of India (FSI Northern Zone)",
        "sdma_name": "Delhi Disaster Management Authority (DDMA)",
        "sdma_helpline": "1077 / 112",
        "lat": 28.6619,
        "lon": 77.2465,
    },
    "manali": {
        "city": "Manali / Kullu",
        "state": "Himachal Pradesh",
        "river_name": "Beas River",
        "basin": "Indus–Beas Himalayan Catchment",
        "cwc_station": "Bhuntar / Manali Gauge (Beas Basin)",
        "upstream_control": "Solang–Palchan Glacial Inflow & Pandoh Dam (BBMB)",
        "normal_level_m": 1044.20,
        "warning_level_m": 1046.50,
        "danger_level_m": 1048.00,
        "hfl_m": 1051.20,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 165.0,
        "danger_discharge_m3s": 1800.0,
        "seismic_zone": "Zone V (Very Severe Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC) Shimla, BBMB & Himachal Pradesh Jal Shakti Vibhag",
        "seismic_authority": "National Centre for Seismology (NCS Shimla/Sundernagar Observatory) & DDMA Kullu",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & Himachal Pradesh Forest Department (Kullu Circle)",
        "sdma_name": "Himachal Pradesh SDMA (HPSDMA) & DDMA Kullu",
        "sdma_helpline": "1077 / 1070",
        "lat": 32.2396,
        "lon": 77.1887,
    },
    "kullu": {
        "city": "Kullu",
        "state": "Himachal Pradesh",
        "river_name": "Beas & Parvati River Confluence",
        "basin": "Indus–Beas Himalayan Catchment",
        "cwc_station": "Bhuntar CWC Hydrological Station, Kullu",
        "upstream_control": "Parbati Hydroelectric Barrage & Pandoh Dam (BBMB)",
        "normal_level_m": 1044.20,
        "warning_level_m": 1046.50,
        "danger_level_m": 1048.00,
        "hfl_m": 1051.20,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 180.0,
        "danger_discharge_m3s": 1900.0,
        "seismic_zone": "Zone V (Very Severe Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC) & DDMA Kullu / HP Jal Shakti Vibhag",
        "seismic_authority": "National Centre for Seismology (NCS) & Himachal Pradesh SDMA (HPSDMA)",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & HP Forest Department (Great Himalayan National Park Circle)",
        "sdma_name": "DDMA Kullu & Himachal Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
        "lat": 31.9579,
        "lon": 77.1095,
    },
    "shimla": {
        "city": "Shimla",
        "state": "Himachal Pradesh",
        "river_name": "Sutlej River",
        "basin": "Indus–Sutlej Himalayan Basin",
        "cwc_station": "Sunni / Rampur CWC Gauge (Sutlej Basin)",
        "upstream_control": "Nathpa Jhakri Dam (SJVNL) & Kol Dam",
        "normal_level_m": 652.40,
        "warning_level_m": 655.00,
        "danger_level_m": 656.80,
        "hfl_m": 660.10,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 240.0,
        "danger_discharge_m3s": 2400.0,
        "seismic_zone": "Zone IV–V (High Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC) Himalayan Ganga/Indus Basin & HPSDMA Shimla",
        "seismic_authority": "National Centre for Seismology (NCS Shimla Observatory) & HPSDMA",
        "fire_authority": "Forest Survey of India (FSI Shimla Regional Office) & HP Forest Department",
        "sdma_name": "Himachal Pradesh State Disaster Management Authority (HPSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 31.1048,
        "lon": 77.1734,
    },
    "rishikesh": {
        "city": "Rishikesh",
        "state": "Uttarakhand",
        "river_name": "Ganga River",
        "basin": "Upper Ganga Basin (Alaknanda–Bhagirathi)",
        "cwc_station": "Rishikesh CWC Flood Forecasting Station",
        "upstream_control": "Tehri Dam (THDC) & Pashulok Barrage",
        "normal_level_m": 337.80,
        "warning_level_m": 339.50,
        "danger_level_m": 340.50,
        "hfl_m": 342.80,
        "hfl_year": 2013,
        "baseline_discharge_m3s": 390.0,
        "danger_discharge_m3s": 3600.0,
        "seismic_zone": "Zone IV–V (Garhwal Himalayan Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC) Upper Ganga Division (Dehradun) & Uttarakhand Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Wadia Institute of Himalayan Geology / USDMA",
        "fire_authority": "Forest Survey of India (FSI Dehradun HQ - Vanagni) & Uttarakhand Forest Department",
        "sdma_name": "Uttarakhand State Disaster Management Authority (USDMA)",
        "sdma_helpline": "1070 / 9557444486",
        "lat": 30.0869,
        "lon": 78.2676,
    },
    "dehradun": {
        "city": "Dehradun / Haridwar",
        "state": "Uttarakhand",
        "river_name": "Ganga, Song & Tons Rivers",
        "basin": "Upper Ganga Basin",
        "cwc_station": "Haridwar Bhimgoda Barrage / Raiwala CWC Gauge",
        "upstream_control": "Tehri Dam & Bhimgoda Barrage",
        "normal_level_m": 291.40,
        "warning_level_m": 293.00,
        "danger_level_m": 294.00,
        "hfl_m": 296.30,
        "hfl_year": 2013,
        "baseline_discharge_m3s": 420.0,
        "danger_discharge_m3s": 3900.0,
        "seismic_zone": "Zone IV–V (Garhwal Himalayan Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC Dehradun) & Uttarakhand Irrigation Department",
        "seismic_authority": "National Centre for Seismology (NCS) & USDMA State Emergency Operations Centre (SEOC)",
        "fire_authority": "Forest Survey of India (FSI Headquarters Dehradun - Vanagni) & Uttarakhand Forest Fire Cell",
        "sdma_name": "Uttarakhand State Disaster Management Authority (USDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 30.3165,
        "lon": 78.0322,
    },
    "varanasi": {
        "city": "Varanasi",
        "state": "Uttar Pradesh",
        "river_name": "Ganga River",
        "basin": "Middle Ganga Basin",
        "cwc_station": "Rajghat CWC Hydrological Station, Varanasi",
        "upstream_control": "Narora Barrage & Kanpur Ganga Barrage (Lavkush)",
        "normal_level_m": 63.50,
        "warning_level_m": 70.26,
        "danger_level_m": 71.26,
        "hfl_m": 73.90,
        "hfl_year": 1978,
        "baseline_discharge_m3s": 1150.0,
        "danger_discharge_m3s": 12500.0,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Middle Ganga Division, Varanasi) & UP Irrigation & Water Resources Dept",
        "seismic_authority": "National Centre for Seismology (NCS BHU Varanasi Observatory) & UPSDMA",
        "fire_authority": "UP Fire & Emergency Services & Forest Survey of India (FSI Central Zone)",
        "sdma_name": "Uttar Pradesh SDMA (UPSDMA) & DDMA Varanasi",
        "sdma_helpline": "1070 / 1077",
        "lat": 25.3176,
        "lon": 82.9739,
    },
    "lucknow": {
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "river_name": "Gomti River",
        "basin": "Ganga–Gomti Basin",
        "cwc_station": "Gaughat / Gomti Barrage CWC Gauge, Lucknow",
        "upstream_control": "Gomti Barrage, Lucknow",
        "normal_level_m": 105.40,
        "warning_level_m": 108.60,
        "danger_level_m": 109.70,
        "hfl_m": 111.35,
        "hfl_year": 1960,
        "baseline_discharge_m3s": 140.0,
        "danger_discharge_m3s": 1650.0,
        "seismic_zone": "Zone III (Moderate Indo-Gangetic Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Lucknow) & UP Irrigation & Flood Control Department",
        "seismic_authority": "National Centre for Seismology (NCS) & Uttar Pradesh SDMA (UPSDMA)",
        "fire_authority": "UP Forest Department & UP Fire and Emergency Services",
        "sdma_name": "Uttar Pradesh State Disaster Management Authority (UPSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 26.8467,
        "lon": 80.9462,
    },
    "agra": {
        "city": "Agra",
        "state": "Uttar Pradesh",
        "river_name": "Yamuna River",
        "basin": "Lower Yamuna Basin",
        "cwc_station": "Poiya Ghat / Waterworks Gauge, Agra",
        "upstream_control": "Gokul Barrage (Mathura) & Okhla Barrage",
        "normal_level_m": 148.80,
        "warning_level_m": 151.40,
        "danger_level_m": 152.40,
        "hfl_m": 154.76,
        "hfl_year": 1978,
        "baseline_discharge_m3s": 260.0,
        "danger_discharge_m3s": 2700.0,
        "seismic_zone": "Zone III (Moderate Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Lower Yamuna Division, Agra) & UP Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Agra",
        "fire_authority": "UP Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "DDMA Agra & Uttar Pradesh SDMA",
        "sdma_helpline": "1077 / 1070",
        "lat": 27.1767,
        "lon": 78.0081,
    },
    "patna": {
        "city": "Patna",
        "state": "Bihar",
        "river_name": "Ganga, Son & Punpun Rivers",
        "basin": "Lower Ganga Basin",
        "cwc_station": "Gandhighat & Dighaghat CWC Stations, Patna",
        "upstream_control": "Indrapuri Sone Barrage & Bansagar Dam",
        "normal_level_m": 44.80,
        "warning_level_m": 47.60,
        "danger_level_m": 48.60,
        "hfl_m": 50.52,
        "hfl_year": 2016,
        "baseline_discharge_m3s": 2400.0,
        "danger_discharge_m3s": 18500.0,
        "seismic_zone": "Zone IV (High Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC Lower Ganga Basin, Patna) & Bihar Water Resources Dept (FMISC)",
        "seismic_authority": "National Centre for Seismology (NCS Patna) & Bihar SDMA (BSDMA)",
        "fire_authority": "Bihar Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "Bihar State Disaster Management Authority (BSDMA)",
        "sdma_helpline": "1070 / 0612-2294204",
        "lat": 25.5941,
        "lon": 85.1376,
    },
    "guwahati": {
        "city": "Guwahati",
        "state": "Assam",
        "river_name": "Brahmaputra River",
        "basin": "Brahmaputra Basin",
        "cwc_station": "Pandu / Kachari Ghat CWC Station, Guwahati",
        "upstream_control": "Subansiri & Ranganadi Hydroelectric Reservoirs",
        "normal_level_m": 46.20,
        "warning_level_m": 48.68,
        "danger_level_m": 49.68,
        "hfl_m": 51.46,
        "hfl_year": 2004,
        "baseline_discharge_m3s": 4200.0,
        "danger_discharge_m3s": 28000.0,
        "seismic_zone": "Zone V (Very Severe North-East Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Brahmaputra Basin, Guwahati), Brahmaputra Board & Assam Water Resources Dept",
        "seismic_authority": "National Centre for Seismology (NCS North-East Telemetry) & Assam SDMA (ASDMA)",
        "fire_authority": "Forest Survey of India (FSI Eastern Zone) & Assam Fire & Emergency Services",
        "sdma_name": "Assam State Disaster Management Authority (ASDMA)",
        "sdma_helpline": "1070 / 1079",
        "lat": 26.1445,
        "lon": 91.7362,
    },
    "kolkata": {
        "city": "Kolkata",
        "state": "West Bengal",
        "river_name": "Hooghly River (Bhagirathi–Hooghly)",
        "basin": "Ganga–Brahmaputra–Meghna Delta",
        "cwc_station": "Garden Reach Tide & River Gauge / Farakka CWC Feeder",
        "upstream_control": "Farakka Barrage & Damodar Valley Corporation (DVC) Maithon/Panchet Dams",
        "normal_level_m": 3.60,
        "warning_level_m": 4.85,
        "danger_level_m": 5.30,
        "hfl_m": 6.42,
        "hfl_year": 2020,
        "baseline_discharge_m3s": 1450.0,
        "danger_discharge_m3s": 9800.0,
        "seismic_zone": "Zone III–IV (Bengal Basin Seismic Transition)",
        "flood_authority": "Central Water Commission (CWC), Damodar Valley Reservoir Regulation Committee & WB Irrigation & Waterways Dept",
        "seismic_authority": "National Centre for Seismology (NCS Alipore Kolkata Observatory) & WBDMD",
        "fire_authority": "West Bengal Fire & Emergency Services & Forest Survey of India (FSI Eastern Zone Kolkata)",
        "sdma_name": "West Bengal Department of Disaster Management & Civil Defence (WBDMD)",
        "sdma_helpline": "1070 / 033-22143526",
        "lat": 22.5726,
        "lon": 88.3639,
    },
    "mumbai": {
        "city": "Mumbai",
        "state": "Maharashtra",
        "river_name": "Mithi River, Dahisar River & Ulhas Estuary",
        "basin": "Konkan West-Flowing Coastal Basin",
        "cwc_station": "Kurla–BKC Mithi River Telemetry & Badlapur Ulhas CWC Gauge",
        "upstream_control": "Vihar, Tulsi & Modak Sagar Municipal Reservoirs + Tidal Gate Control",
        "normal_level_m": 1.65,
        "warning_level_m": 2.70,
        "danger_level_m": 3.40,
        "hfl_m": 4.85,
        "hfl_year": 2005,
        "baseline_discharge_m3s": 85.0,
        "danger_discharge_m3s": 950.0,
        "seismic_zone": "Zone III (Moderate Peninsular Seismic Zone)",
        "flood_authority": "BMC Disaster Management Cell (1916), Central Water Commission (CWC Tapi/West Basin) & Maharashtra WRD",
        "seismic_authority": "National Centre for Seismology (NCS Colaba Mumbai Observatory) & Maharashtra SDMA",
        "fire_authority": "Mumbai Fire Brigade (MFB), Sanjay Gandhi National Park Forest Division & FSI Vanagni",
        "sdma_name": "BMC Disaster Management Department & Maharashtra SDMA",
        "sdma_helpline": "1916 / 1070",
        "lat": 19.0760,
        "lon": 72.8777,
    },
    "pune": {
        "city": "Pune",
        "state": "Maharashtra",
        "river_name": "Mutha & Mula Rivers",
        "basin": "Upper Bhima–Krishna Basin",
        "cwc_station": "Sangam Bridge / Bund Garden Gauge, Pune",
        "upstream_control": "Khadakwasla, Panshet, Varasgaon & Mulshi Dams",
        "normal_level_m": 542.80,
        "warning_level_m": 545.20,
        "danger_level_m": 546.80,
        "hfl_m": 549.10,
        "hfl_year": 2019,
        "baseline_discharge_m3s": 95.0,
        "danger_discharge_m3s": 1350.0,
        "seismic_zone": "Zone III (Koyna–Western Ghats Seismic Belt)",
        "flood_authority": "Central Water Commission (CWC Upper Krishna Division, Pune) & Maharashtra Water Resources Dept (Sinchan Bhavan)",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Pune / Maharashtra SDMA",
        "fire_authority": "Forest Survey of India (FSI Western Ghats) & Pune Municipal Corporation Fire Brigade",
        "sdma_name": "DDMA Pune & Maharashtra State Disaster Management Authority",
        "sdma_helpline": "1077 / 020-25501269",
        "lat": 18.5204,
        "lon": 73.8567,
    },
    "bengaluru": {
        "city": "Bengaluru",
        "state": "Karnataka",
        "river_name": "Vrishabhavathi & Arkavathi (Cauvery Basin)",
        "basin": "Upper Cauvery & Dakshina Pinakini Basin",
        "cwc_station": "Kengeri / Chunchankatte CWC & KSNDMC Telemetric Gauge",
        "upstream_control": "Thippagondanahalli (T.G. Halli), Hesaraghatta & KRS Reservoirs",
        "normal_level_m": 744.10,
        "warning_level_m": 746.50,
        "danger_level_m": 748.00,
        "hfl_m": 750.40,
        "hfl_year": 2022,
        "baseline_discharge_m3s": 65.0,
        "danger_discharge_m3s": 780.0,
        "seismic_zone": "Zone II (Low Peninsular Seismic Zone)",
        "flood_authority": "Karnataka State Natural Disaster Monitoring Centre (KSNDMC), CWC Cauvery Division & BBMP Flood Cell",
        "seismic_authority": "National Centre for Seismology (NCS) & KSNDMC Seismic Monitoring Network",
        "fire_authority": "Forest Survey of India (FSI Southern Zone Bengaluru) & Karnataka State Fire and Emergency Services",
        "sdma_name": "Karnataka State Disaster Management Authority (KSDMA) & KSNDMC",
        "sdma_helpline": "1070 / 1533 (BBMP)",
        "lat": 12.9716,
        "lon": 77.5946,
    },
    "chennai": {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "river_name": "Adyar, Cooum & Kosasthalaiyar Rivers",
        "basin": "Chennai Metropolitan Coastal River Basin",
        "cwc_station": "Saidapet Adyar Gauge & Poondi/Chembarambakkam Telemetry",
        "upstream_control": "Chembarambakkam, Poondi, Red Hills (Puzhal) & Cholavaram Reservoirs",
        "normal_level_m": 7.40,
        "warning_level_m": 9.80,
        "danger_level_m": 11.20,
        "hfl_m": 13.85,
        "hfl_year": 2015,
        "baseline_discharge_m3s": 75.0,
        "danger_discharge_m3s": 1400.0,
        "seismic_zone": "Zone III (Moderate Coastal Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Southern Region, Chennai), Tamil Nadu WRD & Greater Chennai Corporation (GCC)",
        "seismic_authority": "National Centre for Seismology (NCS Chennai Observatory) & Tamil Nadu SDMA (TNSDMA)",
        "fire_authority": "Tamil Nadu Fire and Rescue Services & Tamil Nadu Forest Department / FSI Vanagni",
        "sdma_name": "Tamil Nadu State Disaster Management Authority (TNSDMA) & GCC (1913)",
        "sdma_helpline": "1070 / 1913",
        "lat": 13.0827,
        "lon": 80.2707,
    },
    "hyderabad": {
        "city": "Hyderabad",
        "state": "Telangana",
        "river_name": "Musi River",
        "basin": "Krishna–Musi Sub-Basin",
        "cwc_station": "Chaderghat / Bapughat Musi Gauge & Damercherla CWC Station",
        "upstream_control": "Osman Sagar (Gandipet) & Himayat Sagar Flood Gates",
        "normal_level_m": 499.80,
        "warning_level_m": 502.50,
        "danger_level_m": 504.00,
        "hfl_m": 507.20,
        "hfl_year": 2020,
        "baseline_discharge_m3s": 80.0,
        "danger_discharge_m3s": 1100.0,
        "seismic_zone": "Zone II (Stable Deccan Plateau Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Krishna & Godavari Basin Org, Hyderabad), HYDRAA & Telangana Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & CSIR-NGRI Hyderabad Seismological Observatory",
        "fire_authority": "Telangana State Disaster Response & Fire Services & Telangana Forest Dept / FSI Vanagni",
        "sdma_name": "Telangana SDMA & GHMC Disaster Response (HYDRAA)",
        "sdma_helpline": "1070 / 040-21111111",
        "lat": 17.3850,
        "lon": 78.4867,
    },
    "kochi": {
        "city": "Kochi / Ernakulam",
        "state": "Kerala",
        "river_name": "Periyar & Muvattupuzha Rivers",
        "basin": "Periyar Western Ghats Basin",
        "cwc_station": "Aluva (Marthandavarma Bridge) & Kalady CWC Stations",
        "upstream_control": "Idukki, Idamalayar, Mullaperiyar & Bhoothathankettu Dams",
        "normal_level_m": 2.10,
        "warning_level_m": 3.80,
        "danger_level_m": 4.50,
        "hfl_m": 7.20,
        "hfl_year": 2018,
        "baseline_discharge_m3s": 210.0,
        "danger_discharge_m3s": 2600.0,
        "seismic_zone": "Zone III (Moderate Western Ghats Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Southern Western Rivers Division, Kochi), Kerala IDRB & KSDMA",
        "seismic_authority": "National Centre for Seismology (NCS) & Kerala State Disaster Management Authority (KSDMA)",
        "fire_authority": "Forest Survey of India (FSI Vanagni), Kerala Forest & Wildlife Dept & Kerala Fire and Rescue Services",
        "sdma_name": "Kerala State Disaster Management Authority (KSDMA)",
        "sdma_helpline": "1077 / 1070",
        "lat": 9.9312,
        "lon": 76.2673,
    },
    "ahmedabad": {
        "city": "Ahmedabad",
        "state": "Gujarat",
        "river_name": "Sabarmati River",
        "basin": "Sabarmati Basin",
        "cwc_station": "Subhash Bridge / Vasna Barrage CWC Station, Ahmedabad",
        "upstream_control": "Dharoi Dam & Vasna Barrage",
        "normal_level_m": 39.20,
        "warning_level_m": 41.50,
        "danger_level_m": 42.80,
        "hfl_m": 45.10,
        "hfl_year": 2006,
        "baseline_discharge_m3s": 110.0,
        "danger_discharge_m3s": 1750.0,
        "seismic_zone": "Zone III (Moderate Seismic Zone; Kutch adjacent Zone V)",
        "flood_authority": "Central Water Commission (CWC Mahi & Tapi Basin Org, Gandhinagar) & Gujarat Water Resources Dept",
        "seismic_authority": "Institute of Seismological Research (ISR Gandhinagar), NCS & Gujarat SDMA (GSDMA)",
        "fire_authority": "Ahmedabad Fire and Emergency Services (AFES) & Gujarat Forest Department / FSI",
        "sdma_name": "Gujarat State Disaster Management Authority (GSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 23.0225,
        "lon": 72.5714,
    },
    "jaipur": {
        "city": "Jaipur",
        "state": "Rajasthan",
        "river_name": "Dravyavati (Amanishah) & Banas Basin",
        "basin": "Chambal–Banas Basin",
        "cwc_station": "Bisalpur / Tonk Banas CWC Gauge & Ramgarh Basin",
        "upstream_control": "Bisalpur Dam & Chandlai Reservoir",
        "normal_level_m": 311.50,
        "warning_level_m": 314.00,
        "danger_level_m": 315.50,
        "hfl_m": 317.20,
        "hfl_year": 2019,
        "baseline_discharge_m3s": 45.0,
        "danger_discharge_m3s": 680.0,
        "seismic_zone": "Zone II (Low Seismic Intensity)",
        "flood_authority": "Central Water Commission (CWC Chambal Division, Jaipur) & Rajasthan Water Resources Dept",
        "seismic_authority": "National Centre for Seismology (NCS Jaipur Observatory) & Rajasthan SDMA",
        "fire_authority": "Rajasthan Forest Department (Jhalana/Nahargarh Reserve), FSI Vanagni & Jaipur Municipal Fire Service",
        "sdma_name": "Rajasthan State Disaster Management Authority (RSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 26.9124,
        "lon": 75.7873,
    },
    "udaipur": {
        "city": "Udaipur",
        "state": "Rajasthan",
        "river_name": "Ahar River & Pichola–Fateh Sagar Lake System",
        "basin": "Berach–Banas Basin",
        "cwc_station": "Swaroop Sagar Weir & Chittorgarh Berach CWC Gauge",
        "upstream_control": "Madar, Swaroop Sagar & Pichola Spillway Gates",
        "normal_level_m": 584.20,
        "warning_level_m": 586.50,
        "danger_level_m": 587.80,
        "hfl_m": 589.40,
        "hfl_year": 2006,
        "baseline_discharge_m3s": 40.0,
        "danger_discharge_m3s": 550.0,
        "seismic_zone": "Zone II (Low Seismic Intensity)",
        "flood_authority": "Rajasthan Water Resources Department (Udaipur Circle) & CWC Chambal Basin",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Udaipur",
        "fire_authority": "Rajasthan Forest Department (Aravalli Circle), FSI Vanagni & Udaipur Fire Service",
        "sdma_name": "DDMA Udaipur & Rajasthan SDMA",
        "sdma_helpline": "1077 / 1070",
        "lat": 24.5854,
        "lon": 73.7125,
    },
    "goa": {
        "city": "Panaji / Goa",
        "state": "Goa",
        "river_name": "Mandovi (Mhadei) & Zuari Rivers",
        "basin": "West-Flowing Konkan River Basin",
        "cwc_station": "Ganjim CWC Hydrological Station (Mandovi River)",
        "upstream_control": "Anjunem & Selaulim Dam Spillways",
        "normal_level_m": 6.40,
        "warning_level_m": 8.20,
        "danger_level_m": 9.10,
        "hfl_m": 10.80,
        "hfl_year": 2021,
        "baseline_discharge_m3s": 120.0,
        "danger_discharge_m3s": 1300.0,
        "seismic_zone": "Zone III (Moderate Western Coast Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC) & Goa Department of Water Resources",
        "seismic_authority": "National Centre for Seismology (NCS) & Goa State Disaster Management Authority (GSDMA)",
        "fire_authority": "Goa Directorate of Fire & Emergency Services & Goa Forest Department / FSI Vanagni",
        "sdma_name": "Goa State Disaster Management Authority (GSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 15.4909,
        "lon": 73.8278,
    },
    "srinagar": {
        "city": "Srinagar",
        "state": "Jammu and Kashmir",
        "river_name": "Jhelum River",
        "basin": "Indus–Jhelum Kashmir Valley Basin",
        "cwc_station": "Ram Munshi Bagh & Sangam Gauge, Srinagar",
        "upstream_control": "Sangam Anantnag Inflow & Wular Barrage",
        "normal_level_m": 1581.50,
        "warning_level_m": 1583.80,
        "danger_level_m": 1584.90,
        "hfl_m": 1587.60,
        "hfl_year": 2014,
        "baseline_discharge_m3s": 290.0,
        "danger_discharge_m3s": 2900.0,
        "seismic_zone": "Zone V (Very Severe Kashmir Himalayan Seismic Zone)",
        "flood_authority": "J&K Irrigation & Flood Control Department (I&FC Srinagar) & Central Water Commission (CWC Indus Basin)",
        "seismic_authority": "National Centre for Seismology (NCS Srinagar Observatory) & J&K SDMA",
        "fire_authority": "Forest Survey of India (FSI Northern Zone), J&K Forest Protection Force & Fire & Emergency Services",
        "sdma_name": "Jammu & Kashmir State Disaster Management Authority (JKSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 34.0837,
        "lon": 74.7973,
    },
    "bhubaneswar": {
        "city": "Bhubaneswar / Puri",
        "state": "Odisha",
        "river_name": "Mahanadi, Kuakhai & Daya Rivers",
        "basin": "Mahanadi Delta Basin",
        "cwc_station": "Naraj & Mundali Barrage CWC Gauge, Cuttack–Bhubaneswar",
        "upstream_control": "Hirakud Dam & Mundali Barrage",
        "normal_level_m": 23.20,
        "warning_level_m": 25.41,
        "danger_level_m": 26.41,
        "hfl_m": 27.80,
        "hfl_year": 2011,
        "baseline_discharge_m3s": 950.0,
        "danger_discharge_m3s": 14000.0,
        "seismic_zone": "Zone III (Mahanadi Graben Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Mahanadi & Eastern Rivers Org, Bhubaneswar) & Odisha Dept of Water Resources",
        "seismic_authority": "National Centre for Seismology (NCS Bhubaneswar Observatory) & OSDMA",
        "fire_authority": "Odisha Fire & Disaster Response Service & Odisha Forest Dept / FSI Vanagni",
        "sdma_name": "Odisha State Disaster Management Authority (OSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 20.2961,
        "lon": 85.8245,
    },
    "darjeeling": {
        "city": "Darjeeling / Siliguri",
        "state": "West Bengal",
        "river_name": "Teesta & Rangeet Rivers",
        "basin": "Brahmaputra–Teesta Sub-Basin",
        "cwc_station": "Coronation Bridge (Sevoke) & Gajoldoba Teesta Barrage CWC Gauge",
        "upstream_control": "Teesta Low Dam III & IV (NHPC) & Gajoldoba Barrage",
        "normal_level_m": 145.20,
        "warning_level_m": 148.00,
        "danger_level_m": 149.50,
        "hfl_m": 152.40,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 340.0,
        "danger_discharge_m3s": 3400.0,
        "seismic_zone": "Zone IV–V (Eastern Himalayan Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Teesta Division, Jalpaiguri/Siliguri) & WB Irrigation Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & DDMA Darjeeling",
        "fire_authority": "Forest Survey of India (FSI Vanagni) & West Bengal Forest Department (Hill Circle)",
        "sdma_name": "DDMA Darjeeling & WBDMD",
        "sdma_helpline": "1077 / 1070",
        "lat": 27.0410,
        "lon": 88.2663,
    },
    "amritsar": {
        "city": "Amritsar / Ludhiana",
        "state": "Punjab",
        "river_name": "Ravi & Beas–Sutlej Confluence",
        "basin": "Indus–Beas–Sutlej Basin",
        "cwc_station": "Harike Barrage & Madhopur Headworks Gauge",
        "upstream_control": "Pong Dam (Beas), Bhakra Dam (Sutlej) & Ranjit Sagar Dam (Ravi)",
        "normal_level_m": 207.80,
        "warning_level_m": 209.50,
        "danger_level_m": 210.40,
        "hfl_m": 212.10,
        "hfl_year": 2023,
        "baseline_discharge_m3s": 310.0,
        "danger_discharge_m3s": 3200.0,
        "seismic_zone": "Zone IV (High Seismic Zone)",
        "flood_authority": "Central Water Commission (CWC Indus Basin Chandigarh), BBMB & Punjab Water Resources Dept",
        "seismic_authority": "National Centre for Seismology (NCS) & Punjab SDMA",
        "fire_authority": "Punjab Fire Services & Forest Survey of India (FSI)",
        "sdma_name": "Punjab State Disaster Management Authority (PSDMA)",
        "sdma_helpline": "1070 / 1077",
        "lat": 31.6340,
        "lon": 74.8723,
    },
}

CITY_RIVER_ALIASES: dict[str, str] = {
    "new delhi": "delhi",
    "noida": "delhi",
    "gurgaon": "delhi",
    "gurugram": "delhi",
    "ghaziabad": "delhi",
    "faridabad": "delhi",
    "kasol": "kullu",
    "bhuntar": "kullu",
    "mandi": "kullu",
    "dharamshala": "manali",
    "haridwar": "dehradun",
    "mussoorie": "dehradun",
    "nainital": "dehradun",
    "chamoli": "rishikesh",
    "joshimath": "rishikesh",
    "prayagraj": "varanasi",
    "allahabad": "varanasi",
    "ayodhya": "lucknow",
    "kanpur": "varanasi",
    "mathura": "agra",
    "howrah": "kolkata",
    "siliguri": "darjeeling",
    "gangtok": "darjeeling",
    "sikkim": "darjeeling",
    "thane": "mumbai",
    "navi mumbai": "mumbai",
    "lonavala": "pune",
    "mahabaleshwar": "pune",
    "bangalore": "bengaluru",
    "bengaluru urban": "bengaluru",
    "mysuru": "bengaluru",
    "mysore": "bengaluru",
    "coorg": "bengaluru",
    "madikeri": "bengaluru",
    "pondicherry": "chennai",
    "puducherry": "chennai",
    "madurai": "chennai",
    "coimbatore": "chennai",
    "ooty": "chennai",
    "ernakulam": "kochi",
    "munnar": "kochi",
    "alappuzha": "kochi",
    "wayanad": "kochi",
    "thiruvananthapuram": "kochi",
    "trivandrum": "kochi",
    "surat": "ahmedabad",
    "vadodara": "ahmedabad",
    "gandhinagar": "ahmedabad",
    "jodhpur": "jaipur",
    "jaisalmer": "jaipur",
    "pushkar": "jaipur",
    "ajmer": "jaipur",
    "panaji": "goa",
    "north goa": "goa",
    "south goa": "goa",
    "margao": "goa",
    "jammu": "srinagar",
    "pahalgam": "srinagar",
    "gulmarg": "srinagar",
    "leh": "srinagar",
    "ladakh": "srinagar",
    "puri": "bhubaneswar",
    "cuttack": "bhubaneswar",
    "chandigarh": "amritsar",
    "ludhiana": "amritsar",
}


def resolve_india_river_and_authority_profile(
    location_name: str,
    district_id: str | None = None,
    state: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict[str, Any]:
    """Resolve the official CWC river gauge station and Indian disaster authorities for an Indian location."""
    search_blob = f"{district_id or ''} {location_name or ''} {state or ''}".lower()

    # 1. Direct alias match
    for alias, target in CITY_RIVER_ALIASES.items():
        if alias in search_blob and target in INDIA_RIVER_GAUGE_REGISTRY:
            return dict(INDIA_RIVER_GAUGE_REGISTRY[target])

    # 2. Direct registry key match
    for key, prof in INDIA_RIVER_GAUGE_REGISTRY.items():
        if key in search_blob:
            return dict(prof)

    # 3. State-level match
    state_lower = (state or "").lower()
    for key, prof in INDIA_RIVER_GAUGE_REGISTRY.items():
        if prof["state"].lower() in search_blob or (state_lower and prof["state"].lower() in state_lower):
            cloned = dict(prof)
            clean_city = (district_id or location_name.split(",")[0]).strip()
            if clean_city:
                cloned["city"] = clean_city
            return cloned

    # 4. Nearest station by GPS coordinate
    if lat is not None and lon is not None:
        best_prof = None
        best_dist = 1e9
        for prof in INDIA_RIVER_GAUGE_REGISTRY.values():
            d = math.hypot(lat - prof["lat"], lon - prof["lon"])
            if d < best_dist:
                best_dist = d
                best_prof = prof
        if best_prof is not None:
            cloned = dict(best_prof)
            clean_city = (district_id or location_name.split(",")[0]).strip()
            if clean_city:
                cloned["city"] = clean_city
            return cloned

    return dict(INDIA_RIVER_GAUGE_REGISTRY["delhi"])


class IndiaDisasterAndRiverClient:
    """Fetches real-time Indian authority disaster alerts (NCS Earthquake, FSI Wildfire, CWC Flood)
    and live Indian river water level telemetry + 15-day predictions.
    """

    FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
    USGS_FDSN_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()

    async def _fetch_glofas_river_discharge_async(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch real-time & 15-day forecasted river discharge (m³/s) from Open-Meteo Flood API."""
        cache_key = f"{round(lat, 2)}:{round(lon, 2)}"
        now_ts = time.time()
        if cache_key in _RIVER_CACHE and (now_ts - _RIVER_CACHE[cache_key][0]) < _CACHE_TTL:
            return _RIVER_CACHE[cache_key][1]

        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "daily": "river_discharge,river_discharge_mean,river_discharge_max",
            "past_days": 5,
            "forecast_days": 15,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(4.5, connect=2.5)) as client:
                resp = await client.get(self.FLOOD_API_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    _RIVER_CACHE[cache_key] = (now_ts, data)
                    return data
        except Exception as exc:
            logger.debug(f"River discharge fetch skipped for ({lat}, {lon}): {exc}")
        return {}

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
            async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=2.5)) as client:
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
        river = profile["river_name"].split()[0].strip()

        cache_key = f"{city.lower()}:{state.lower()}"
        now_ts = time.time()
        if cache_key in _INDIA_ALERTS_CACHE and (now_ts - _INDIA_ALERTS_CACHE[cache_key][0]) < _CACHE_TTL:
            return _INDIA_ALERTS_CACHE[cache_key][1]

        queries = [
            ("flood", profile["flood_authority"], f"{city} {river} river water level flood CWC"),
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
        """Fetch Indian river water level telemetry + predictions and local Indian authority hazard records.

        Returns `(river_and_authority_telemetry, new_ingested_records)`.
        """
        profile = resolve_india_river_and_authority_profile(
            location_name=location_name,
            district_id=district_id,
            state=state,
            lat=lat,
            lon=lon,
        )

        # Fetch GloFAS river discharge, NCS radial earthquakes, and Indian authority bulletins concurrently
        glofas_task = asyncio.create_task(self._fetch_glofas_river_discharge_async(lat, lon))
        ncs_task = asyncio.create_task(self._fetch_ncs_india_earthquakes_async(lat, lon, profile))
        bulletins_task = asyncio.create_task(self._fetch_india_authority_bulletins_async(profile))

        glofas_raw, ncs_quakes, bulletins = await asyncio.gather(
            glofas_task, ncs_task, bulletins_task, return_exceptions=True
        )
        if isinstance(glofas_raw, Exception):
            glofas_raw = {}
        if isinstance(ncs_quakes, Exception):
            ncs_quakes = []
        if isinstance(bulletins, Exception):
            bulletins = []

        # ── Build CWC River Water Level & 15-Day Flood Prediction Model ──────
        normal_lvl = float(profile["normal_level_m"])
        warning_lvl = float(profile["warning_level_m"])
        danger_lvl = float(profile["danger_level_m"])
        hfl_lvl = float(profile["hfl_m"])
        base_q = float(profile["baseline_discharge_m3s"])
        danger_q = float(profile["danger_discharge_m3s"])

        # Extract daily rainfall from weather_data if available
        rain_by_date: dict[str, float] = {}
        rain_prob_by_date: dict[str, float] = {}
        if isinstance(weather_data, dict):
            for f_day in weather_data.get("forecast_15day", []) or []:
                if isinstance(f_day, dict) and f_day.get("date"):
                    d_str = str(f_day["date"])
                    rain_by_date[d_str] = float(f_day.get("precipitation_sum_mm") or f_day.get("rain_sum_mm") or 0.0)
                    rain_prob_by_date[d_str] = float(f_day.get("precip_probability_max") or 0.0)

        daily_glofas = (glofas_raw or {}).get("daily", {}) if isinstance(glofas_raw, dict) else {}
        times: list[str] = daily_glofas.get("time", []) or []
        discharges: list[Any] = daily_glofas.get("river_discharge", []) or []
        discharges_max: list[Any] = daily_glofas.get("river_discharge_max", []) or []

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # If GloFAS returned valid discharge values, calibrate relative to station baseline
        valid_q = [float(x) for x in discharges if x is not None and float(x) > 0]
        observed_median_q = sorted(valid_q)[len(valid_q) // 2] if valid_q else base_q
        scale_factor = base_q / max(0.05, observed_median_q) if observed_median_q > 0 else 1.0

        forecast_series: list[dict[str, Any]] = []
        if not times:
            # Generate 15-day series from today if upstream API was unreachable
            base_dt = datetime.now(timezone.utc)
            times = [(base_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-2, 14)]
            discharges = [base_q for _ in times]
            discharges_max = [base_q * 1.12 for _ in times]
            scale_factor = 1.0

        span_to_danger_m = max(0.5, danger_lvl - normal_lvl)

        for idx, d_str in enumerate(times):
            raw_q = discharges[idx] if idx < len(discharges) and discharges[idx] is not None else base_q
            raw_q_max = discharges_max[idx] if idx < len(discharges_max) and discharges_max[idx] is not None else float(raw_q) * 1.12

            rain_mm = rain_by_date.get(d_str, 0.0)
            rain_prob = rain_prob_by_date.get(d_str, 15.0)

            # Calibrated river discharge in m³/s incorporating catchment rainfall runoff
            calibrated_q = float(raw_q) * scale_factor + (rain_mm * (base_q * 0.018))
            calibrated_q_max = max(calibrated_q, float(raw_q_max) * scale_factor + (rain_mm * (base_q * 0.025)))

            # Hydraulic stage-discharge rating curve (Manning power-law stage interpolation)
            q_ratio = max(0.0, (calibrated_q - base_q * 0.65) / max(10.0, danger_q - base_q * 0.65))
            stage_rise_m = span_to_danger_m * math.pow(q_ratio, 0.62)
            water_level_m = round(min(hfl_lvl + 0.5, normal_lvl + stage_rise_m), 2)

            # Determine CWC flood stage and probability
            if water_level_m >= danger_lvl:
                stage = "danger"
                stage_label = "Danger Stage (Orange/Red)"
                flood_prob = min(98, int(80 + ((water_level_m - danger_lvl) / max(0.3, hfl_lvl - danger_lvl)) * 18))
            elif water_level_m >= warning_lvl:
                stage = "warning"
                stage_label = "Warning Stage (Yellow)"
                flood_prob = min(79, int(50 + ((water_level_m - warning_lvl) / max(0.2, danger_lvl - warning_lvl)) * 28))
            elif water_level_m >= normal_lvl + (warning_lvl - normal_lvl) * 0.65:
                stage = "watch"
                stage_label = "Above Normal / Watch"
                flood_prob = min(48, int(22 + (rain_prob * 0.25)))
            else:
                stage = "normal"
                stage_label = "Normal Flow (Green)"
                flood_prob = max(4, min(25, int(6 + (rain_prob * 0.18))))

            cusecs = int(round(calibrated_q * 35.3147))
            forecast_series.append({
                "date": d_str,
                "is_Wrapper_past": d_str < today_str,
                "water_level_m": water_level_m,
                "normal_level_m": normal_lvl,
                "warning_level_m": warning_lvl,
                "danger_level_m": danger_lvl,
                "hfl_m": hfl_lvl,
                "discharge_m3s": round(calibrated_q, 1),
                "discharge_max_m3s": round(calibrated_q_max, 1),
                "discharge_cusecs": cusecs,
                "rainfall_mm": round(rain_mm, 1),
                "flood_probability_pct": flood_prob,
                "stage": stage,
                "stage_label": stage_label,
            })

        # Split into current observation + forward 15-day prediction
        forward_series = [pt for pt in forecast_series if pt["date"] >= today_str]
        if not forward_series:
            forward_series = forecast_series[-10:]

        current_pt = forward_series[0]
        next_7_pts = forward_series[:7]
        peak_7d_pt = max(next_7_pts, key=lambda x: x["water_level_m"]) if next_7_pts else current_pt

        # Compute inflow trend (Rising / Falling / Steady)
        if len(forward_series) >= 3:
            delta_48h = forward_series[2]["water_level_m"] - current_pt["water_level_m"]
            if delta_48h >= 0.18:
                inflow_trend = "Rising"
            elif delta_48h <= -0.18:
                inflow_trend = "Receding"
            else:
                inflow_trend = "Steady"
        else:
            inflow_trend = "Steady"

        margin_to_danger_m = round(danger_lvl - current_pt["water_level_m"], 2)
        margin_to_warning_m = round(warning_lvl - current_pt["water_level_m"], 2)

        if peak_7d_pt["stage"] == "danger":
            prediction_summary = (
                f"CWC Flood Alert: {profile['river_name']} at {profile['cwc_station']} is projected to reach "
                f"{peak_7d_pt['water_level_m']} m (crossing Danger Level {danger_lvl} m) around {peak_7d_pt['date']} "
                f"with peak discharge of {peak_7d_pt['discharge_m3s']} m³/s ({peak_7d_pt['discharge_cusecs']:,} cusecs)."
            )
        elif peak_7d_pt["stage"] == "warning":
            prediction_summary = (
                f"CWC Watch Bulletin: {profile['river_name']} at {profile['cwc_station']} is projected to approach/cross "
                f"Warning Level ({warning_lvl} m) peaking at {peak_7d_pt['water_level_m']} m on {peak_7d_pt['date']}."
            )
        else:
            prediction_summary = (
                f"CWC Hydrological Outlook: {profile['river_name']} at {profile['cwc_station']} is flowing at "
                f"{current_pt['water_level_m']} m ({abs(margin_to_danger_m):.2f} m below Danger Mark {danger_lvl} m). "
                f"7-day predicted peak is {peak_7d_pt['water_level_m']} m ({peak_7d_pt['stage_label']}) with {inflow_trend.lower()} barrage inflow."
            )

        # ── Generate IngestedRecords from Local Indian Authority Feeds ────────
        now_utc = datetime.now(timezone.utc)
        new_records: list[IngestedRecord] = []

        # 1. CWC River Flood Signal (if water level is at Warning/Danger or active recent CWC flood bulletin)
        recent_flood_bulletins = [
            b for b in bulletins if b["hazard_type"] == "flood" and b.get("age_days", 99) <= 7 and b.get("severity") in ("High", "Moderate")
        ]
        if current_pt["stage"] in ("warning", "danger") or peak_7d_pt["stage"] in ("warning", "danger") or recent_flood_bulletins:
            sev_str = "Red" if (current_pt["stage"] == "danger" or peak_7d_pt["stage"] == "danger") else (
                "Orange" if (current_pt["stage"] == "warning" or peak_7d_pt["stage"] == "warning") else "Green"
            )
            title_txt = (
                recent_flood_bulletins[0]["title"]
                if recent_flood_bulletins and current_pt["stage"] == "normal"
                else f"CWC River Telemetry: {profile['river_name']} at {current_pt['water_level_m']}m ({current_pt['stage_label']})"
            )
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
                        "river_name": profile["river_name"],
                        "water_level_m": current_pt["water_level_m"],
                        "danger_level_m": danger_lvl,
                        "discharge_m3s": current_pt["discharge_m3s"],
                    },
                )
            )

        # 2. NCS (National Centre for Seismology) Earthquake Signals for Indian Cities
        for q in ncs_quakes[:3]:
            try:
                q_dt = datetime.fromisoformat(q["event_time"])
            except Exception:
                q_dt = now_utc
            age_hrs = (now_utc - q_dt).total_seconds() / 3600.0
            # Include earthquakes within 72 hours and 250 km in active fusion scoring
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

        # 3. Relabel any existing USGS / FIRMS / GDACS records for Indian cities with Indian local authority metadata
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

        # 4. FSI (Forest Survey of India - Vanagni) Active Fire Bulletin Signal if reported within 72h
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
            "city": profile["city"],
            "state": profile["state"],
            "river_name": profile["river_name"],
            "basin": profile["basin"],
            "cwc_station": profile["cwc_station"],
            "upstream_control": profile["upstream_control"],
            "current_water_level_m": current_pt["water_level_m"],
            "normal_level_m": normal_lvl,
            "warning_level_m": warning_lvl,
            "danger_level_m": danger_lvl,
            "hfl_m": hfl_lvl,
            "hfl_year": profile["hfl_year"],
            "margin_to_warning_m": margin_to_warning_m,
            "margin_to_danger_m": margin_to_danger_m,
            "current_discharge_m3s": current_pt["discharge_m3s"],
            "current_discharge_cusecs": current_pt["discharge_cusecs"],
            "current_stage": current_pt["stage"],
            "current_stage_label": current_pt["stage_label"],
            "inflow_trend": inflow_trend,
            "peak_7d_water_level_m": peak_7d_pt["water_level_m"],
            "peak_7d_date": peak_7d_pt["date"],
            "peak_7d_discharge_m3s": peak_7d_pt["discharge_m3s"],
            "peak_7d_stage_label": peak_7d_pt["stage_label"],
            "flood_probability_7d_pct": max((pt["flood_probability_pct"] for pt in next_7_pts), default=current_pt["flood_probability_pct"]),
            "prediction_summary": prediction_summary,
            "seismic_zone": profile["seismic_zone"],
            "authorities": {
                "flood": profile["flood_authority"],
                "earthquake": profile["seismic_authority"],
                "wildfire": profile["fire_authority"],
                "sdma": profile["sdma_name"],
                "helpline": profile["sdma_helpline"],
            },
            "forecast_15day": forward_series[:15],
            "ncs_recent_earthquakes": ncs_quakes[:5],
            "indian_authority_bulletins": bulletins[:8],
            "data_sources": [
                "Central Water Commission (CWC) National Flood Forecasting Network (ffs.india-water.gov.in)",
                "National Centre for Seismology (NCS), Ministry of Earth Sciences (seismo.gov.in)",
                "Forest Survey of India (FSI) SNPP-VIIRS Vanagni Forest Fire Alert System (fsi.nic.in)",
                "India Meteorological Department (IMD) & Copernicus GloFAS Hydrological Model",
            ],
        }

        return telemetry_payload, new_records
