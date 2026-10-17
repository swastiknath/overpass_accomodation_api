"""Official International Travel Advisories Connector.

Aggregates official government travel warnings from top diplomatic authorities:
1. India: Ministry of External Affairs (MEA), Government of India
2. United States: U.S. Department of State
3. United Kingdom: Foreign, Commonwealth & Development Office (UK FCDO)

Flags:
- Level 4: Do Not Travel / Advise Against All Travel (Armed Conflict, Active Warfare, Severe Danger)
- Level 3: Reconsider Travel / Avoid All Non-Essential Travel (High Conflict Risk, Civil Unrest)
- Level 2: Exercise Increased Caution / Heightened Vigilance
- Level 1: Exercise Normal Precautions / Standard Consular Registration
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point

from config import Settings, load_settings
from gis.schema import IngestedRecord, ResolutionTier

logger = logging.getLogger(__name__)

ADVISORY_FEED_URL = "https://travel.state.gov/_res/rss/TAsTWs.xml"

# Dedicated curated repository of Ministry of External Affairs (MEA), Government of India advisories
MEA_ADVISORIES_REGISTRY: dict[str, dict[str, Any]] = {
    "israel": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Israel",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Avoid All Non-Essential Travel",
        "status_color": "amber",
        "summary": "In view of the prevailing security situation in the region, all Indian nationals are strongly advised to avoid all non-essential travel to Israel. Indian citizens in Israel are urged to remain calm, observe safety protocols, and register with the Embassy of India in Tel Aviv.",
        "helpline": "+972-547520711 (Tel Aviv 24x7 Control Room) / 1800118797 (MEA New Delhi)",
        "embassy_contact": "Embassy of India, 140 Hayarkon Street, Tel Aviv",
        "registration_url": "https://www.indembtelaviv.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Diplomatic Advisory",
    },
    "lebanon": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Lebanon",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Strongly Advised Against All Travel",
        "status_color": "rose",
        "summary": "In view of recent developments and potential military escalation, Indian nationals are strongly advised against traveling to Lebanon until further notice. Indian citizens in Lebanon are advised to leave at the earliest available commercial flights.",
        "helpline": "+961-76860128 (Emergency Control Room Beirut) / +961-3926748",
        "embassy_contact": "Embassy of India, Beirut",
        "registration_url": "https://www.indianembassybeirut.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Diplomatic Advisory",
    },
    "iran": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Iran",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Avoid Non-Essential Travel",
        "status_color": "amber",
        "summary": "Indian nationals are advised to avoid all non-essential travel to Iran and stay in constant contact with the Indian Embassy in Tehran in view of regional tensions.",
        "helpline": "+98-9128109115 / +98-9128109109",
        "embassy_contact": "Embassy of India, Mir Emad Street, Tehran",
        "registration_url": "https://www.indianembassytehran.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "gaza": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Gaza & Palestinian Territories",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Strictly Do Not Travel (Armed Conflict)",
        "status_color": "rose",
        "summary": "Indian nationals are strictly advised against all travel to Gaza and surrounding conflict zones due to active military hostilities and catastrophic humanitarian emergency.",
        "helpline": "+970-592916418 (Representative Office of India, Ramallah)",
        "embassy_contact": "Representative Office of India, Ramallah",
        "registration_url": "https://roiramallah.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "ukraine": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Ukraine",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "Indian nationals are advised against all travel to Ukraine in view of the ongoing armed conflict, active missile strikes, air-raid sirens, and martial law restrictions.",
        "helpline": "+380-933559958 (Embassy of India, Kyiv)",
        "embassy_contact": "Embassy of India, Kyiv",
        "registration_url": "https://www.eoiukraine.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "myanmar": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Myanmar",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Avoid Non-Essential Travel / Fake Job Scam Warning",
        "status_color": "amber",
        "summary": "Indian nationals are advised to avoid non-essential travel to Myanmar, especially Rakhine State and eastern border areas (Myawaddy) where international cyber crime syndicates lure jobseekers with fraudulent IT offers.",
        "helpline": "+95-1-388412 / +95-95419012 (Embassy of India, Yangon)",
        "embassy_contact": "Embassy of India, Yangon",
        "registration_url": "https://embassyofindiayangon.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "bangladesh": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Bangladesh",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Exercise Extreme Caution",
        "status_color": "amber",
        "summary": "Indian citizens in Bangladesh are advised to exercise extreme caution, restrict their movements, avoid public demonstrations, and remain in close touch with the High Commission in Dhaka.",
        "helpline": "+880-1937400591 (High Commission of India, Dhaka)",
        "embassy_contact": "High Commission of India, Dhaka",
        "registration_url": "https://www.hcidhaka.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "syria": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Syria",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Strictly Advised Against All Travel",
        "status_color": "rose",
        "summary": "In view of the prevailing security situation, terrorism risks, and active armed conflict in Syria, Indian nationals are strictly advised to avoid all travel to Syria until further notice.",
        "helpline": "+963-993385973 / +963-11-6132602 (Embassy of India, Damascus)",
        "embassy_contact": "Embassy of India, Damascus",
        "registration_url": "https://eoidamascus.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Diplomatic Advisory",
    },
    "yemen": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Yemen",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Strictly Do Not Travel (Passport Restricted)",
        "status_color": "rose",
        "summary": "Indian nationals are strictly advised against all travel to Yemen. Travel to Yemen without specific authorization from MEA is restricted under Section 19 of the Passports Act, 1967.",
        "helpline": "+967-733055811 (Camp Office of Embassy of India) / 1800118797",
        "embassy_contact": "Camp Office of Embassy of India accredited to Yemen",
        "registration_url": "https://www.eoiabuja.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Travel Ban",
    },
    "sudan": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Sudan",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel (Operation Kaveri)",
        "status_color": "rose",
        "summary": "In view of fierce armed clashes between the Sudanese Armed Forces and RSF, Indian nationals are strongly advised against traveling to Sudan. Indian citizens in Sudan are urged to stay indoors and contact the Embassy.",
        "helpline": "+249-992120285 / +249-915033785 (Embassy of India, Port Sudan/Khartoum)",
        "embassy_contact": "Embassy of India, Khartoum (Camp Office Port Sudan)",
        "registration_url": "https://www.eoikhartoum.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "afghanistan": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Afghanistan",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "Indian nationals are advised against all travel to Afghanistan in view of ongoing security volatility, civil risk, and absence of full diplomatic services.",
        "helpline": "+93-700108001 (Technical Mission of India, Kabul) / 1800118797",
        "embassy_contact": "Technical Mission of India, Kabul",
        "registration_url": "https://eoi.gov.in/kabul/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "russia": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Russia",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Exercise Extreme Caution / Conflict Zone Employment Alert",
        "status_color": "amber",
        "summary": "Indian nationals are strongly cautioned against seeking employment offers that involve military or support roles in conflict zones. Indian citizens are advised to exercise extreme caution in border regions adjacent to Ukraine (Kursk, Belgorod, Bryansk, Voronezh, Rostov).",
        "helpline": "+7-965-2773414 (Embassy of India, Moscow 24x7 Helpline)",
        "embassy_contact": "Embassy of India, 6-8 Vorontsovo Polye, Moscow",
        "registration_url": "https://indianembassy-moscow.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "canada": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Canada",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 2,
        "level_label": "Exercise Utmost Caution (Anti-India Incidents)",
        "status_color": "yellow",
        "summary": "In view of growing anti-India activities and politically condoned hate crimes in Canada, all Indian nationals and Indian students in Canada are urged to exercise utmost caution, avoid travel to venues where incidents may occur, and register with MADAD.",
        "helpline": "+1-613-744-3751 (High Commission Ottawa) / +1-416-960-0751 (CGI Toronto)",
        "embassy_contact": "High Commission of India, 10 Springfield Road, Ottawa",
        "registration_url": "https://www.hciottawa.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Diplomatic Advisory",
    },
    "thailand": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Thailand",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Verify Employment / Cyber Scam Syndicate Alert",
        "status_color": "amber",
        "summary": "Indian nationals are cautioned against fake job offers for IT/digital marketing roles originating from recruiters offering tourist visas. Jobseekers are lured across the Thai-Myanmar border into scam compounds in Myawaddy. Always verify via eMigrate portal.",
        "helpline": "+66-618819099 (Embassy of India, Bangkok) / 1800118797",
        "embassy_contact": "Embassy of India, Soi 23, Sukhumvit Road, Bangkok",
        "registration_url": "https://embassyofindiabangkok.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "cambodia": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Cambodia",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Verify Job Offers / Cyber Fraud Warning",
        "status_color": "amber",
        "summary": "Indian nationals traveling to Cambodia for employment are strongly cautioned to verify recruiters through authorized MEA recruiting agents. Fraudulent entities in Sihanoukville and Poipet have trapped Indian youth into cyber fraud syndicates.",
        "helpline": "+855-92881676 (Embassy of India, Phnom Penh)",
        "embassy_contact": "Embassy of India, Phnom Penh",
        "registration_url": "https://embassyofindiaphnompenh.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "laos": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Laos",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Cyber Scam Syndicate Alert (Golden Triangle)",
        "status_color": "amber",
        "summary": "Indian nationals are advised to exercise vigilance regarding employment offers in the Golden Triangle Special Economic Zone (SEZ) in Bokeo Province, Laos, where fraudulent crypto/call center compounds operate.",
        "helpline": "+856-2055512876 (Embassy of India, Vientiane)",
        "embassy_contact": "Embassy of India, Vientiane",
        "registration_url": "https://indianembassylaos.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "iraq": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Iraq",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Avoid Non-Essential Travel (Northern Regions)",
        "status_color": "amber",
        "summary": "Indian nationals are advised to avoid non-essential travel to Iraq, particularly governorates of Nineveh, Salahuddin, Diyala, Anbar, and Kirkuk, due to security volatility.",
        "helpline": "+964-7729966553 (Embassy of India, Baghdad) / +964-7503017701 (CGI Erbil)",
        "embassy_contact": "Embassy of India, Baghdad",
        "registration_url": "https://www.eoibaghdad.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "libya": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Libya",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Strictly Advised Against All Travel",
        "status_color": "rose",
        "summary": "Indian nationals are strictly advised against all travel to Libya. An official ban on travel and employment in Libya has been in effect under MEA notifications due to armed militia violence.",
        "helpline": "+216-71787819 (Embassy of India accredited to Libya) / 1800118797",
        "embassy_contact": "Embassy of India Camp Office (Tunis)",
        "registration_url": "https://www.mea.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Travel Ban",
    },
    "pakistan": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Pakistan",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Level 4: Strictly Advised Against All Travel — Not Safe for Indian Nationals",
        "status_color": "rose",
        "summary": "Travel to Pakistan is not going to be safe for Indian nationals. In view of severe bilateral tensions, heightened security risks, state-level monitoring, and restricted consular assistance, Indian citizens are strictly advised that traveling to Pakistan is not safe and strongly advised against.",
        "helpline": "+92-51-2823383 (High Commission of India, Islamabad) / MEA 24x7 Control Room New Delhi: 1800118797",
        "embassy_contact": "High Commission of India, G-5 Diplomatic Enclave, Islamabad",
        "registration_url": "https://www.india.org.pk/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active Severe Diplomatic Warning",
    },
    "somalia": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Somalia",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "Indian nationals are advised against all travel to Somalia due to extreme risks of terrorism, armed conflict, and maritime piracy.",
        "helpline": "+254-202222566 (High Commission of India, Nairobi accredited to Somalia)",
        "embassy_contact": "High Commission of India accredited to Somalia",
        "registration_url": "https://hcinairobi.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "south sudan": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "South Sudan",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "Indian nationals are advised against traveling to South Sudan due to inter-communal violence, armed clashes, and unstable security.",
        "helpline": "+211-922000101 (Embassy of India, Juba)",
        "embassy_contact": "Embassy of India, Juba",
        "registration_url": "https://www.eoijuba.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Advisory",
    },
    "haiti": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Haiti",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 4,
        "level_label": "Advise Against All Travel (Operation Indravati)",
        "status_color": "rose",
        "summary": "Indian nationals are advised against all travel to Haiti in view of ongoing widespread gang violence, breakdown of public law and order, and closure of critical transport links.",
        "helpline": "+1-809-540-1011 (Embassy Santo Domingo) / +1-509-3801-4444 (Haiti Mission)",
        "embassy_contact": "Embassy of India accredited to Haiti",
        "registration_url": "https://www.eoicuba.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active MEA Evacuation Advisory",
    },
    "west asia": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "West Asia / Middle East Region",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Regional Conflict & Airspace Escalation Advisory",
        "status_color": "amber",
        "summary": "In view of active military confrontations and airspace disruptions across West Asia, all Indian nationals in the region are advised to maintain constant vigilance, avoid military installations, and stay in touch with Indian missions.",
        "helpline": "1800118797 (MEA New Delhi 24x7 Control Room) / +91-11-23012113",
        "embassy_contact": "24x7 MEA Situation Room, South Block, New Delhi",
        "registration_url": "https://madad.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active Regional Advisory",
    },
    "middle east": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Middle East / West Asia Region",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 3,
        "level_label": "Regional Conflict & Airspace Escalation Advisory",
        "status_color": "amber",
        "summary": "In view of active military confrontations and airspace disruptions across the Middle East, all Indian nationals in the region are advised to maintain constant vigilance, avoid military installations, and stay in touch with Indian missions.",
        "helpline": "1800118797 (MEA New Delhi 24x7 Control Room) / +91-11-23012113",
        "embassy_contact": "24x7 MEA Situation Room, South Block, New Delhi",
        "registration_url": "https://madad.gov.in/",
        "official_link": "https://www.mea.gov.in/press-releases.htm",
        "issued_date": "Active Regional Advisory",
    },
    "united arab emirates": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "United Arab Emirates",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 1,
        "level_label": "Normal Travel / MADAD Registration",
        "status_color": "emerald",
        "summary": "Standard travel precautions. Indian nationals and tourists in UAE are advised to register on MADAD / Embassy portal and adhere to local UAE immigration and municipal regulations.",
        "helpline": "800-46342 (Pravasi Bharatiya Sahayata Kendra / PBSK UAE Toll Free) / +971-508995588",
        "embassy_contact": "Embassy of India Abu Dhabi / Consulate General Dubai",
        "registration_url": "https://www.indembassyuae.gov.in/",
        "official_link": "https://www.mea.gov.in/",
        "issued_date": "Active Consular Guidelines",
    },
    "saudi arabia": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Saudi Arabia",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 1,
        "level_label": "Normal Travel / Consular Protocol",
        "status_color": "emerald",
        "summary": "Indian pilgrims and travelers are advised to register through Nusuk / MEA portals and abide by local residency and visa guidelines.",
        "helpline": "800-2471234 (PBSK Toll Free Riyadh) / +966-11-4884144",
        "embassy_contact": "Embassy of India Riyadh / CGI Jeddah",
        "registration_url": "https://www.eoiriyadh.gov.in/",
        "official_link": "https://www.mea.gov.in/",
        "issued_date": "Active Consular Guidelines",
    },
    "qatar": {
        "authority": "Ministry of External Affairs (MEA), Government of India",
        "country": "Qatar",
        "country_code": "IN",
        "flag": "🇮🇳",
        "level": 1,
        "level_label": "Normal Travel / ICBF Guidelines",
        "status_color": "emerald",
        "summary": "Standard travel precautions. Indian nationals are encouraged to register with the Embassy and use ICBF support services when needed.",
        "helpline": "+974-44255777 / +974-55513753 (Embassy of India, Doha)",
        "embassy_contact": "Embassy of India, Al Hilal Area, Doha",
        "registration_url": "https://www.indianembassyqatar.gov.in/",
        "official_link": "https://www.mea.gov.in/",
        "issued_date": "Active Consular Guidelines",
    },
}

# Dedicated curated repository of UK Foreign, Commonwealth & Development Office (UK FCDO) advisories
UK_FCDO_REGISTRY: dict[str, dict[str, Any]] = {
    "israel": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Israel",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 3,
        "level_label": "Advise Against All But Essential Travel",
        "status_color": "amber",
        "summary": "FCDO advises against all travel to Gaza and parts of Northern Israel; and advises against all but essential travel to the rest of Israel and the Occupied Palestinian Territories due to the risk of rocket attacks and military escalation.",
        "helpline": "+44 20 7008 5000 (UK Consular Support)",
        "embassy_contact": "British Embassy Tel Aviv, 192 Hayarkon Street",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/israel",
        "official_link": "https://www.gov.uk/foreign-travel-advice/israel",
        "issued_date": "Active FCDO Advisory",
    },
    "lebanon": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Lebanon",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to the whole of Lebanon due to ongoing armed conflict, airstrikes, and rapid border volatility. British nationals are urged to leave immediately.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Beirut",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/lebanon",
        "official_link": "https://www.gov.uk/foreign-travel-advice/lebanon",
        "issued_date": "Active FCDO Advisory",
    },
    "iran": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Iran",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Iran. British and British-Iranian dual nationals are at significant risk of arbitrary arrest and interrogation.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Tehran",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/iran",
        "official_link": "https://www.gov.uk/foreign-travel-advice/iran",
        "issued_date": "Active FCDO Advisory",
    },
    "ukraine": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Ukraine",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Ukraine due to the ongoing Russian invasion and active military warfare across the territory.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Kyiv",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/ukraine",
        "official_link": "https://www.gov.uk/foreign-travel-advice/ukraine",
        "issued_date": "Active FCDO Advisory",
    },
    "syria": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Syria",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Syria. British nationals in Syria should leave by any practical means.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Damascus (Operations Suspended)",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/syria",
        "official_link": "https://www.gov.uk/foreign-travel-advice/syria",
        "issued_date": "Active FCDO Advisory",
    },
    "yemen": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Yemen",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Yemen. Ongoing military strikes and severe regional conflict make consular evacuation impossible.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Sana'a (Operations Suspended)",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/yemen",
        "official_link": "https://www.gov.uk/foreign-travel-advice/yemen",
        "issued_date": "Active FCDO Advisory",
    },
    "sudan": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Sudan",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Sudan due to active intense armed conflict and severe infrastructure breakdown.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Khartoum",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/sudan",
        "official_link": "https://www.gov.uk/foreign-travel-advice/sudan",
        "issued_date": "Active FCDO Advisory",
    },
    "afghanistan": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Afghanistan",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Afghanistan. The security situation remains extremely volatile with significant detention risk.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Kabul",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/afghanistan",
        "official_link": "https://www.gov.uk/foreign-travel-advice/afghanistan",
        "issued_date": "Active FCDO Advisory",
    },
    "russia": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Russia",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Russia due to risks of drone strikes, arbitrary detention, and limited return flight routes.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Moscow",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/russia",
        "official_link": "https://www.gov.uk/foreign-travel-advice/russia",
        "issued_date": "Active FCDO Advisory",
    },
    "myanmar": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Myanmar",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to parts of Myanmar and against all but essential travel elsewhere due to civil war and cyber scam complexes.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Yangon",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/myanmar",
        "official_link": "https://www.gov.uk/foreign-travel-advice/myanmar",
        "issued_date": "Active FCDO Advisory",
    },
    "libya": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Libya",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to Libya due to political instability and fighting between rival armed groups.",
        "helpline": "+44 20 7008 5000",
        "embassy_contact": "British Embassy Tripoli",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/libya",
        "official_link": "https://www.gov.uk/foreign-travel-advice/libya",
        "issued_date": "Active FCDO Advisory",
    },
    "pakistan": {
        "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
        "country": "Pakistan",
        "country_code": "GB",
        "flag": "🇬🇧",
        "level": 4,
        "level_label": "Level 4: Advise Against All Travel",
        "status_color": "rose",
        "summary": "FCDO advises against all travel to the border between Pakistan and India, Balochistan, and Khyber Pakhtunkhwa. Severe terrorism and security risks apply.",
        "helpline": "+44 20 7008 5000 (UK FCDO)",
        "embassy_contact": "British High Commission, Diplomatic Enclave, Islamabad",
        "registration_url": "https://www.gov.uk/foreign-travel-advice/pakistan",
        "official_link": "https://www.gov.uk/foreign-travel-advice/pakistan",
        "issued_date": "Active FCDO Advisory",
    },
}


class TravelAdvisoryClient:
    """Fetches, parses, and harmonizes official travel advisories from India (MEA), US, and UK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self._cached_us_advisories: dict[str, dict[str, Any]] | None = None
        self._last_fetch_time: float = 0.0
        self._cache_ttl_seconds: float = 3600.0  # 1 hour

    async def get_us_advisories_dict_async(self) -> dict[str, dict[str, Any]]:
        """Fetch US State Dept advisories from live XML feed or fixture fallback."""
        now = time.time()
        if self._cached_us_advisories and (now - self._last_fetch_time) < self._cache_ttl_seconds:
            return self._cached_us_advisories

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
                headers = {"User-Agent": "HotelsAPI-TravelSafety/2.0"}
                resp = await client.get(ADVISORY_FEED_URL, headers=headers)
                if resp.status_code == 200:
                    advisories = self._parse_advisories_xml(resp.text)
                    if advisories:
                        self._cached_us_advisories = advisories
                        self._last_fetch_time = now
                        return advisories
        except Exception as e:
            logger.warning(f"Live US State Dept travel advisory feed fetch failed: {e}; attempting fixture fallback.")

        fallback = self._load_fixture_fallback()
        if fallback:
            self._cached_us_advisories = fallback
            self._last_fetch_time = now
            return fallback

        return {}

    def get_us_advisories_dict(self) -> dict[str, dict[str, Any]]:
        """Sync variant of get_us_advisories_dict_async."""
        now = time.time()
        if self._cached_us_advisories and (now - self._last_fetch_time) < self._cache_ttl_seconds:
            return self._cached_us_advisories

        try:
            with httpx.Client(timeout=httpx.Timeout(6.0)) as client:
                headers = {"User-Agent": "HotelsAPI-TravelSafety/2.0"}
                resp = client.get(ADVISORY_FEED_URL, headers=headers)
                if resp.status_code == 200:
                    advisories = self._parse_advisories_xml(resp.text)
                    if advisories:
                        self._cached_us_advisories = advisories
                        self._last_fetch_time = now
                        return advisories
        except Exception as e:
            logger.warning(f"Sync US travel advisory fetch failed: {e}; using fixture.")

        fallback = self._load_fixture_fallback()
        if fallback:
            self._cached_us_advisories = fallback
            self._last_fetch_time = now
            return fallback

        return {}

    def _parse_advisories_xml(self, xml_text: str) -> dict[str, dict[str, Any]]:
        """Parse the US State Dept RSS XML feed."""
        advisories: dict[str, dict[str, Any]] = {}
        try:
            root = ET.fromstring(xml_text)
            items = root.find("channel")
            if items is None:
                return advisories

            for it in items.findall("item"):
                title = (it.find("title").text or "").strip() if it.find("title") is not None else ""
                pub = (it.find("pubDate").text or "").strip() if it.find("pubDate") is not None else ""
                link = (it.find("link").text or "").strip() if it.find("link") is not None else ""
                raw_desc = (it.find("description").text or "").strip() if it.find("description") is not None else ""

                clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

                m = re.search(r"^([^-–]+)\s*[-–]\s*(Level\s*([1-4]))[:\s]*([^-–\n]*)", title, re.IGNORECASE)
                if m:
                    c_name = m.group(1).strip()
                    lvl = int(m.group(3))
                    lvl_label = f"Level {lvl}: {m.group(4).strip()}" if m.group(4).strip() else f"Level {lvl}"
                    advisories[c_name.lower()] = {
                        "authority": "U.S. Department of State",
                        "country": c_name,
                        "country_code": "US",
                        "flag": "🇺🇸",
                        "level": lvl,
                        "level_label": lvl_label,
                        "status_color": "rose" if lvl >= 4 else ("amber" if lvl == 3 else ("yellow" if lvl == 2 else "emerald")),
                        "summary": clean_desc[:320] + ("..." if len(clean_desc) > 320 else ""),
                        "helpline": "+1-888-407-4747 (from US & Canada) / +1-202-501-4444 (from overseas)",
                        "embassy_contact": f"U.S. Embassy & Consulates in {c_name}",
                        "registration_url": "https://step.state.gov/",
                        "link": link,
                        "official_link": link,
                        "pub_date": pub,
                    }
        except Exception as e:
            logger.error(f"Error parsing US travel advisory XML: {e}")
        return advisories

    def _load_fixture_fallback(self) -> dict[str, dict[str, Any]]:
        """Load curated global travel advisories fixture."""
        p = Path("fixtures/travel_advisories.json")
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Harmonize format
                    for k, v in data.items():
                        v.setdefault("authority", "U.S. Department of State")
                        v.setdefault("flag", "🇺🇸")
                        v.setdefault("country_code", "US")
                        lvl = v.get("level", 1)
                        v.setdefault("status_color", "rose" if lvl >= 4 else ("amber" if lvl == 3 else "yellow"))
                    return data
            except Exception as e:
                logger.error(f"Failed to read travel_advisories.json: {e}")
        return {}

    async def get_advisory_for_location_async(
        self,
        location_name: str,
        lat: float = 0.0,
        lon: float = 0.0,
    ) -> dict[str, Any] | None:
        """Find matching multi-government travel advisories (India MEA, US, UK) for a location."""
        us_advisories = await self.get_us_advisories_dict_async()
        return self._assemble_multi_gov_advisories(location_name, lat, lon, us_advisories)

    def get_advisory_for_location(
        self,
        location_name: str,
        lat: float = 0.0,
        lon: float = 0.0,
    ) -> dict[str, Any] | None:
        """Sync match."""
        us_advisories = self.get_us_advisories_dict()
        return self._assemble_multi_gov_advisories(location_name, lat, lon, us_advisories)

    def _match_country_key(self, location_name: str, keys: list[str]) -> str | None:
        loc_lower = location_name.lower()

        specific_regions = [
            # High-conflict / Middle East / West Asia regions & cities
            ("gaza", "gaza"),
            ("west bank", "israel"),
            ("tel aviv", "israel"),
            ("tel-aviv", "israel"),
            ("jerusalem", "israel"),
            ("haifa", "israel"),
            ("beirut", "lebanon"),
            ("kyiv", "ukraine"),
            ("kiev", "ukraine"),
            ("damascus", "syria"),
            ("aleppo", "syria"),
            ("baghdad", "iraq"),
            ("erbil", "iraq"),
            ("basra", "iraq"),
            ("mosul", "iraq"),
            ("tehran", "iran"),
            ("isfahan", "iran"),
            ("sanaa", "yemen"),
            ("aden", "yemen"),
            ("khartoum", "sudan"),
            ("port sudan", "sudan"),
            ("kabul", "afghanistan"),
            ("kandahar", "afghanistan"),
            ("mogadishu", "somalia"),
            ("juba", "south sudan"),
            ("dhaka", "bangladesh"),
            ("chittagong", "bangladesh"),
            ("yangon", "myanmar"),
            ("myawaddy", "myanmar"),
            ("mandalay", "myanmar"),
            ("tripoli", "libya"),
            ("benghazi", "libya"),
            ("moscow", "russia"),
            ("saint petersburg", "russia"),
            ("st petersburg", "russia"),
            ("kursk", "russia"),
            ("belgorod", "russia"),
            ("toronto", "canada"),
            ("vancouver", "canada"),
            ("montreal", "canada"),
            ("ottawa", "canada"),
            ("bangkok", "thailand"),
            ("phuket", "thailand"),
            ("pattaya", "thailand"),
            ("chiang mai", "thailand"),
            ("phnom penh", "cambodia"),
            ("siem reap", "cambodia"),
            ("sihanoukville", "cambodia"),
            ("poipet", "cambodia"),
            ("vientiane", "laos"),
            ("luang prabang", "laos"),
            ("bokeo", "laos"),
            ("dubai", "united arab emirates"),
            ("abu dhabi", "united arab emirates"),
            ("sharjah", "united arab emirates"),
            ("uae", "united arab emirates"),
            ("west asia", "west asia"),
            ("middle east", "middle east"),
            ("islamabad", "pakistan"),
            ("lahore", "pakistan"),
            ("karachi", "pakistan"),
            ("peshawar", "pakistan"),
            ("port-au-prince", "haiti"),
            ("niamey", "niger"),
            ("bamako", "mali"),
            ("ouagadougou", "burkina faso"),
            ("london", "united kingdom"),
            ("edinburgh", "united kingdom"),
            ("paris", "france"),
            ("berlin", "germany"),
            ("tokyo", "japan"),
            ("colombo", "sri lanka"),
            ("kathmandu", "nepal"),
            ("pokhara", "nepal"),
            ("male", "maldives"),
            ("riyadh", "saudi arabia"),
            ("jeddah", "saudi arabia"),
            ("mecca", "saudi arabia"),
            ("medina", "saudi arabia"),
            ("doha", "qatar"),
            ("kuwait city", "kuwait"),
            ("muscat", "oman"),
            ("manama", "bahrain"),

            # Major Indian States, Union Territories & Cities
            ("jammu", "india"),
            ("srinagar", "india"),
            ("kashmir", "india"),
            ("gulmarg", "india"),
            ("pahalgam", "india"),
            ("katra", "india"),
            ("vaishno devi", "india"),
            ("amarnath", "india"),
            ("ladakh", "india"),
            ("leh", "india"),
            ("kargil", "india"),
            ("nubra", "india"),
            ("pangong", "india"),
            ("manali", "india"),
            ("himachal", "india"),
            ("shimla", "india"),
            ("dharamshala", "india"),
            ("kullu", "india"),
            ("spiti", "india"),
            ("kasol", "india"),
            ("rishikesh", "india"),
            ("haridwar", "india"),
            ("dehradun", "india"),
            ("nainital", "india"),
            ("mussoorie", "india"),
            ("kedarnath", "india"),
            ("badrinath", "india"),
            ("uttarakhand", "india"),
            ("delhi", "india"),
            ("new delhi", "india"),
            ("noida", "india"),
            ("gurgaon", "india"),
            ("gurugram", "india"),
            ("mumbai", "india"),
            ("pune", "india"),
            ("nagpur", "india"),
            ("nashik", "india"),
            ("maharashtra", "india"),
            ("goa", "india"),
            ("panaji", "india"),
            ("bengaluru", "india"),
            ("bangalore", "india"),
            ("mysore", "india"),
            ("karnataka", "india"),
            ("hyderabad", "india"),
            ("telangana", "india"),
            ("chennai", "india"),
            ("coimbatore", "india"),
            ("madurai", "india"),
            ("tamil nadu", "india"),
            ("visakhapatnam", "india"),
            ("vizag", "india"),
            ("vijayawada", "india"),
            ("andhra", "india"),
            ("kolkata", "india"),
            ("darjeeling", "india"),
            ("west bengal", "india"),
            ("jaipur", "india"),
            ("udaipur", "india"),
            ("jodhpur", "india"),
            ("jaisalmer", "india"),
            ("rajasthan", "india"),
            ("ahmedabad", "india"),
            ("surat", "india"),
            ("gujarat", "india"),
            ("amritsar", "india"),
            ("chandigarh", "india"),
            ("punjab", "india"),
            ("lucknow", "india"),
            ("varanasi", "india"),
            ("kanpur", "india"),
            ("agra", "india"),
            ("ayodhya", "india"),
            ("uttar pradesh", "india"),
            ("patna", "india"),
            ("bihar", "india"),
            ("bhopal", "india"),
            ("indore", "india"),
            ("madhya pradesh", "india"),
            ("kochi", "india"),
            ("thiruvananthapuram", "india"),
            ("trivandrum", "india"),
            ("kerala", "india"),
            ("bhubaneswar", "india"),
            ("puri", "india"),
            ("odisha", "india"),
            ("guwahati", "india"),
            ("assam", "india"),
            ("shillong", "india"),
            ("meghalaya", "india"),
            ("gangtok", "india"),
            ("sikkim", "india"),
            ("imphal", "india"),
            ("manipur", "india"),
            ("kohima", "india"),
            ("nagaland", "india"),
            ("aizawl", "india"),
            ("mizoram", "india"),
            ("agartala", "india"),
            ("tripura", "india"),
            ("itanagar", "india"),
            ("tawang", "india"),
            ("arunachal", "india"),
            ("port blair", "india"),
            ("andaman", "india"),
        ]
        for term, target_c in specific_regions:
            if term in loc_lower:
                return target_c

        parts = [p.strip() for p in re.split(r"[,;|\-\(\)]", loc_lower) if p.strip()]
        for part in reversed(parts):
            if part in keys:
                return part

        for c_key in keys:
            if len(c_key) >= 4 and c_key in loc_lower:
                return c_key

        return None

    def _assemble_multi_gov_advisories(
        self,
        location_name: str,
        lat: float,
        lon: float,
        us_advisories: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not location_name and (lat == 0.0 and lon == 0.0):
            return None

        all_keys = list(set(list(us_advisories.keys()) + list(MEA_ADVISORIES_REGISTRY.keys()) + list(UK_FCDO_REGISTRY.keys())))
        matched_key = self._match_country_key(location_name or "", all_keys)

        # Coordinate-based fallback if text name lookup did not find a match
        if not matched_key and (lat != 0.0 or lon != 0.0):
            # India national geographic bounds
            if 6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0:
                matched_key = "india"
            # Middle East / West Asia geographic bounds
            elif 12.0 <= lat <= 35.0 and 34.0 <= lon <= 60.0:
                matched_key = "west asia"

        if not matched_key:
            return None

        loc_lower = (location_name or "").lower()

        # 1. India (MEA) Advisory
        india_advisory: dict[str, Any]
        if matched_key in MEA_ADVISORIES_REGISTRY:
            india_advisory = dict(MEA_ADVISORIES_REGISTRY[matched_key])
        elif matched_key == "india":
            # Check for localized Indian destination sub-regions
            is_jk_ladakh = (
                any(k in loc_lower for k in ["jammu", "kashmir", "srinagar", "ladakh", "leh", "kargil", "gulmarg", "pahalgam", "katra", "vaishno devi", "amarnath"])
                or (32.0 <= lat <= 37.5 and 73.0 <= lon <= 80.5)
            )
            is_ne_border = any(k in loc_lower for k in ["manipur", "imphal", "nagaland", "kohima", "mizoram", "aizawl", "arunachal", "tawang", "itanagar"])
            is_himalayan = any(k in loc_lower for k in ["manali", "himachal", "shimla", "dharamshala", "kullu", "spiti", "rishikesh", "uttarakhand", "kedarnath", "badrinath", "dehradun"])

            if is_jk_ladakh:
                india_advisory = {
                    "authority": "Ministry of External Affairs (MEA) & J&K Administration",
                    "country": "India (Jammu & Kashmir & Ladakh)",
                    "country_code": "IN",
                    "flag": "🇮🇳",
                    "level": 2,
                    "level_label": "Level 2: Exercise Increased Caution / Local Security & Route Guidance",
                    "status_color": "yellow",
                    "summary": "Travelers to Jammu & Kashmir and Ladakh should carry valid government ID, check highway status updates (NH-44 Jammu-Srinagar), register for pilgrimage itineraries (Vaishno Devi / Amarnath), and monitor local district administration notices. Mountain passes may experience seasonal weather closures.",
                    "helpline": "J&K Police Emergency: 112 / Tourist Helpline: 1800-103-1070 / National Disaster: 1070",
                    "embassy_contact": "District Administration & J&K Tourism Police",
                    "registration_url": "https://jktourism.jk.gov.in/",
                    "official_link": "https://www.mea.gov.in/",
                    "issued_date": "Active Regional Guidance",
                }
            elif is_ne_border:
                india_advisory = {
                    "authority": "Ministry of External Affairs (MEA) & State Administration",
                    "country": "India (Northeast Border Region)",
                    "country_code": "IN",
                    "flag": "🇮🇳",
                    "level": 2,
                    "level_label": "Level 2: Exercise Caution / Verify Inner Line Permits (ILP)",
                    "status_color": "yellow",
                    "summary": "Travelers to Arunachal Pradesh, Nagaland, Mizoram, and Manipur should verify required Inner Line Permits (ILP) and monitor local district magistrate notices prior to travel.",
                    "helpline": "State Disaster Control: 1070 / Police Control: 112",
                    "embassy_contact": "Local District Administration & Police Control",
                    "registration_url": "https://ndma.gov.in/",
                    "official_link": "https://www.mea.gov.in/",
                    "issued_date": "Active Regional Guidance",
                }
            elif is_himalayan:
                india_advisory = {
                    "authority": "Ministry of External Affairs (MEA) & SDMA, India",
                    "country": "India (Himalayan Tourist Circuit)",
                    "country_code": "IN",
                    "flag": "🇮🇳",
                    "level": 2,
                    "level_label": "Level 2: Seasonal Weather & Mountain Road Guidance",
                    "status_color": "yellow",
                    "summary": "Himalayan road routes are subject to seasonal weather advisories, flash flood alerts, and landslide warnings during heavy rainfall. Consult HP/UK SDMA and Border Roads Organisation (BRO) clearance before traveling.",
                    "helpline": "HP Disaster Management: 1070 / UK SDMA: 1070 / 112 Emergency",
                    "embassy_contact": "Local District Administration & BRO Control",
                    "registration_url": "https://ndma.gov.in/",
                    "official_link": "https://www.mea.gov.in/",
                    "issued_date": "Active Regional Guidance",
                }
            else:
                india_advisory = {
                    "authority": "Ministry of External Affairs (MEA) & NDMA, India",
                    "country": "India",
                    "country_code": "IN",
                    "flag": "🇮🇳",
                    "level": 1,
                    "level_label": "Level 1: Standard Domestic Measures (Safe)",
                    "status_color": "emerald",
                    "is_domestic_safe": True,
                    "summary": "Within India: Ministry of External Affairs (MEA) and NDMA indicate standard domestic safety measures. No elevated travel advisories or regional security restrictions apply.",
                    "helpline": "National Disaster Helpline: 1070 / 112 Emergency",
                    "embassy_contact": "Local District Administration & Police Control",
                    "registration_url": "https://ndma.gov.in/",
                    "official_link": "https://www.mea.gov.in/",
                    "issued_date": "Active Domestic Measures (Normal)",
                }
        else:
            # Generic MEA guidance for international destinations
            c_name = matched_key.title()
            india_advisory = {
                "authority": "Ministry of External Affairs (MEA), Government of India",
                "country": c_name,
                "country_code": "IN",
                "flag": "🇮🇳",
                "level": 1,
                "level_label": "Exercise Normal Precautions",
                "status_color": "emerald",
                "summary": f"Indian citizens traveling to {c_name} are encouraged to register their itinerary on the MADAD / MEA portal and observe local entry/exit laws.",
                "helpline": "+91-11-23860000 / MADAD Portal 1800113090",
                "embassy_contact": f"Embassy / High Commission of India in {c_name}",
                "registration_url": "https://madad.gov.in/",
                "official_link": "https://www.mea.gov.in/",
                "issued_date": "Active MEA Guidelines",
            }

        # 2. US State Department Advisory
        us_advisory: dict[str, Any]
        if matched_key in us_advisories:
            us_advisory = dict(us_advisories[matched_key])
        else:
            us_advisory = {
                "authority": "U.S. Department of State",
                "country": matched_key.title(),
                "country_code": "US",
                "flag": "🇺🇸",
                "level": 1,
                "level_label": "Level 1: Exercise Normal Precautions",
                "status_color": "emerald",
                "summary": f"Exercise normal precautions when traveling to {matched_key.title()}.",
                "helpline": "+1-888-407-4747",
                "embassy_contact": f"U.S. Embassy in {matched_key.title()}",
                "registration_url": "https://step.state.gov/",
                "official_link": "https://travel.state.gov/",
                "issued_date": "Current Bulletin",
            }

        # 3. UK Foreign Office (FCDO) Advisory
        uk_advisory: dict[str, Any]
        if matched_key in UK_FCDO_REGISTRY:
            uk_advisory = dict(UK_FCDO_REGISTRY[matched_key])
        elif matched_key == "india":
            uk_advisory = {
                "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
                "country": "India",
                "country_code": "GB",
                "flag": "🇬🇧",
                "level": 2,
                "level_label": "See Specific Regional Travel Advice",
                "status_color": "yellow",
                "summary": "FCDO advises against all travel to within 20km of the India-Pakistan border, parts of Jammu & Kashmir, and Manipur. Normal tourism corridors elsewhere are stable.",
                "helpline": "+44 20 7008 5000 (UK FCDO)",
                "embassy_contact": "British High Commission, Shantipath, Chanakyapuri, New Delhi",
                "registration_url": "https://www.gov.uk/foreign-travel-advice/india",
                "official_link": "https://www.gov.uk/foreign-travel-advice/india",
                "issued_date": "Active FCDO Advisory",
            }
        else:
            uk_advisory = {
                "authority": "Foreign, Commonwealth & Development Office (UK FCDO)",
                "country": matched_key.title(),
                "country_code": "GB",
                "flag": "🇬🇧",
                "level": 1,
                "level_label": "See Travel Advice Before Travelling",
                "status_color": "emerald",
                "summary": f"FCDO advises travelers to check standard entry requirements, healthcare, and local laws for {matched_key.title()}.",
                "helpline": "+44 20 7008 5000",
                "embassy_contact": f"British Embassy / Consulate in {matched_key.title()}",
                "registration_url": f"https://www.gov.uk/foreign-travel-advice/{matched_key}",
                "official_link": f"https://www.gov.uk/foreign-travel-advice/{matched_key}",
                "issued_date": "Active FCDO Advisory",
            }

        # Compute composite maximum threat level across authorities with special Pakistan & India domestic rules
        is_pakistan = (matched_key == "pakistan" or "pakistan" in (location_name or "").lower())
        is_domestic_safe_india = (matched_key == "india" and india_advisory.get("is_domestic_safe", False))

        if is_pakistan:
            max_level = 4
            active_warning = True
            primary_label = "Severe MEA Alert: Travel to Pakistan is Not Safe for Indian Nationals"
            primary_summary = india_advisory.get("summary")
            primary_link = india_advisory.get("official_link")
            status_color = "rose"
        elif is_domestic_safe_india:
            max_level = 1
            active_warning = True
            primary_label = "Standard Domestic Measures — Safe for Travel"
            primary_summary = india_advisory.get("summary")
            primary_link = india_advisory.get("official_link")
            status_color = "emerald"
        else:
            max_level = max(india_advisory.get("level", 1), us_advisory.get("level", 1), uk_advisory.get("level", 1))
            active_warning = max_level >= 2

            if india_advisory.get("level", 1) >= 3:
                primary_label = f"MEA India Alert: {india_advisory.get('level_label')}"
                primary_summary = india_advisory.get("summary")
                primary_link = india_advisory.get("official_link")
                status_color = "rose" if max_level >= 3 else "yellow"
            else:
                primary_label = us_advisory.get("level_label") or india_advisory.get("level_label")
                primary_summary = us_advisory.get("summary") or india_advisory.get("summary")
                primary_link = us_advisory.get("official_link") or india_advisory.get("official_link")
                status_color = "rose" if max_level >= 3 else ("yellow" if max_level == 2 else "emerald")

        return {
            "country": matched_key.title(),
            "level": max_level,
            "level_label": primary_label,
            "summary": primary_summary,
            "link": primary_link,
            "pub_date": india_advisory.get("issued_date") or us_advisory.get("pub_date"),
            "matched_term": matched_key,
            "active_warning": active_warning,
            "status_color": status_color,
            "is_domestic_safe": is_domestic_safe_india,
            "sources": {
                "india_mea": india_advisory,
                "us_state_dept": us_advisory,
                "uk_fcdo": uk_advisory,
            },
            "advisories_list": [india_advisory, us_advisory, uk_advisory],
        }

    def to_ingested_record(
        self,
        advisory: dict[str, Any],
        lat: float,
        lon: float,
    ) -> IngestedRecord | None:
        """Convert a matched travel advisory into an IngestedRecord for deterministic fusion.

        Advisory Level Influence Policy (specifically calibrated for US Dept of State / International Warnings):
        - Level 4 (Do Not Travel):
            Maximum influence factor. severity = 0.96, confidence = 0.98.
            Severe armed hostilities, full diplomatic evacuation orders.
        - Level 3 (Reconsider Travel / Avoid All Non-Essential Travel):
            High percentage of influence factor. severity = 0.85, confidence = 0.95.
            Active high-conflict, civil unrest, or severe security advisories.
        - Level 2 (Exercise Increased Caution) or below:
            Minimal influence factor. severity = 0.05, confidence = 0.25.
            Generic country-wide vigilance warnings (e.g. US State Dept Level 2 for India or Europe)
            are not factored heavily into localized destination scores.
        - Level 1 (Exercise Normal Precautions):
            Not factored into hazard scoring (returns None).
        """
        level = advisory.get("level", 1)
        is_domestic_safe = advisory.get("is_domestic_safe", False)
        if level < 2 and not is_domestic_safe:
            return None

        # Check US State Dept specific level if available
        sources = advisory.get("sources", {})
        us_src = sources.get("us_state_dept", {})
        us_level = us_src.get("level", level) if isinstance(us_src, dict) else level
        effective_level = max(level, us_level) if not is_domestic_safe else 1

        if effective_level >= 4:
            severity_raw = 0.96
            confidence = 0.98
        elif effective_level == 3:
            severity_raw = 0.85
            confidence = 0.95
        else:
            # Level 2 or below / domestic baseline: minimal influence factor
            severity_raw = 0.05
            confidence = 0.25

        now_utc = datetime.now(timezone.utc)
        c_name = advisory.get("country", "Region")
        slug = re.sub(r"[^a-zA-Z0-9]", "_", c_name.lower())
        event_id = f"travel_advisory:{slug}:{effective_level}"

        title = f"{advisory.get('level_label', f'Level {effective_level} Advisory')} ({c_name} Diplomatic Warning)"

        return IngestedRecord(
            event_id=event_id,
            source="travel_advisory",
            hazard_type="conflict",
            geometry=Point(lon, lat),
            event_time=now_utc,
            ingest_time=now_utc,
            resolution_tier=ResolutionTier.DISTRICT,
            severity_raw=severity_raw,
            severity_normalized=severity_raw,
            confidence=confidence,
            raw_payload={
                "title": title,
                "country": c_name,
                "level": level,
                "level_label": advisory.get("level_label"),
                "summary": advisory.get("summary"),
                "link": advisory.get("link"),
                "pub_date": advisory.get("pub_date"),
                "event_type": "Official Diplomatic Travel Advisory",
                "sources": advisory.get("sources"),
            },
        )
