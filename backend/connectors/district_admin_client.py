"""Localized District Administration & Emergency Services Resolver.

Resolves localized municipal, provincial, district disaster, and emergency
contacts for searched destinations worldwide (Libya, MENA, Europe, Americas, Asia-Pacific, India).
Guarantees that foreign destinations display their authentic localized emergency numbers
and civic administration rather than Indian domestic agencies.
"""

from __future__ import annotations

import re
from typing import Any


# Registry of verified localized district & city emergency authorities
LOCALIZED_ADMIN_REGISTRY: dict[str, dict[str, Any]] = {
    "tripoli": {
        "district_name": "Tripoli Municipal Administration & Civil Emergency Authority (بلدية طرابلس)",
        "country": "Libya",
        "authorities": [
            {
                "name": "Tripoli Central Emergency Police (شرطة النجدة)",
                "helpline": "1515",
                "url": "https://moi.gov.ly",
                "role": "Law Enforcement & Emergency Police Dispatch",
            },
            {
                "name": "Libyan Red Crescent Emergency (الهلال الأحمر الليبي - طرابلس)",
                "helpline": "193",
                "url": "https://lrcs.org.ly",
                "role": "Medical Emergency & First Aid Response",
            },
            {
                "name": "National Civil Protection & Fire Services (هيئة السلامة الوطنية)",
                "helpline": "190",
                "url": "https://moi.gov.ly",
                "role": "Firefighting & Disaster Relief",
            },
            {
                "name": "Diplomatic & Consular Emergency Hotline",
                "helpline": "+218-21-340-2000",
                "url": "https://foreign.gov.ly",
                "role": "Foreign National Crisis Assistance",
            },
        ],
        "local_tips": [
            "Check municipal security checkpoint status before inter-district transit in Greater Tripoli.",
            "Keep valid passport, visa documents, and consular emergency hotline numbers accessible.",
            "Avoid movements outside secure central perimeters after dark and observe local advisory notices.",
        ],
    },
    "benghazi": {
        "district_name": "Benghazi Municipal Governorate & Emergency Directorate (بلدية بنغازي)",
        "country": "Libya",
        "authorities": [
            {
                "name": "Benghazi Police Emergency Dispatch (النجدة بنغازي)",
                "helpline": "1515",
                "url": "https://moi.gov.ly",
                "role": "Security & Emergency Control",
            },
            {
                "name": "Libyan Red Crescent - Benghazi Branch",
                "helpline": "193",
                "url": "https://lrcs.org.ly",
                "role": "Emergency Medical Services",
            },
            {
                "name": "Civil Defense Directorate Benghazi",
                "helpline": "190",
                "url": "https://moi.gov.ly",
                "role": "Civil Protection & Rescue",
            },
        ],
        "local_tips": [
            "Maintain situational awareness and adhere strictly to localized security guidelines.",
            "Use authorized accommodation transfers and avoid unverified private transit services.",
        ],
    },
    "isfahan": {
        "district_name": "Isfahan District & Provincial Governorate",
        "country": "Iran",
        "authorities": [
            {
                "name": "Isfahan Provincial Governorate (استانداری اصفهان)",
                "helpline": "+98-31-32220001",
                "url": "https://ostan-es.ir",
                "role": "District Administration & Civil Coordination",
            },
            {
                "name": "Isfahan Municipality Emergency Operations (137)",
                "helpline": "137",
                "url": "https://isfahan.ir",
                "role": "Municipal Civic Services & Local Inquiries",
            },
            {
                "name": "Iranian Red Crescent Emergency (Isfahan Branch)",
                "helpline": "112",
                "url": "https://rcs.ir",
                "role": "Disaster Response & Search and Rescue",
            },
            {
                "name": "Police Control Room (NAJA)",
                "helpline": "110",
                "url": "https://police.ir",
                "role": "Public Safety & Law Enforcement",
            },
            {
                "name": "National Medical Emergency Services",
                "helpline": "115",
                "url": "https://115.ir",
                "role": "Ambulance & Emergency Medical Response",
            },
        ],
        "local_tips": [
            "Keep government-issued ID and visa documentation accessible at all times during provincial travel.",
            "Contact Isfahan Municipality Control Room (137) for local municipal notices or road access status.",
            "In case of civic disturbances or regional alerts, avoid sensitive governmental zones and consult your embassy.",
        ],
    },
    "tehran": {
        "district_name": "Tehran Metropolitan Governorate",
        "country": "Iran",
        "authorities": [
            {
                "name": "Tehran Governorate (استانداری تهران)",
                "helpline": "+98-21-88880000",
                "url": "https://ostan-th.ir",
                "role": "Provincial Administration",
            },
            {
                "name": "Tehran City Services & District Assistance",
                "helpline": "137",
                "url": "https://tehran.ir",
                "role": "Municipal Control",
            },
            {
                "name": "Police Emergency (110)",
                "helpline": "110",
                "url": "https://police.ir",
                "role": "Law Enforcement",
            },
            {
                "name": "Red Crescent Emergency",
                "helpline": "112",
                "url": "https://rcs.ir",
                "role": "Disaster Rescue",
            },
        ],
        "local_tips": [
            "Observe local guidelines regarding photography near municipal and administrative complexes.",
            "Utilize authorized taxi services and avoid private unregistered transit operators.",
        ],
    },
    "tel aviv": {
        "district_name": "Tel Aviv-Yafo Subdistrict & Municipality",
        "country": "Israel",
        "authorities": [
            {
                "name": "Tel Aviv-Yafo Municipality Emergency Hotline (מוקד 106)",
                "helpline": "106",
                "url": "https://www.tel-aviv.gov.il",
                "role": "Municipal Administration & Shelter Locations",
            },
            {
                "name": "Israel Police (משטרت ישראל)",
                "helpline": "100",
                "url": "https://www.police.gov.il",
                "role": "Law Enforcement & Security Dispatch",
            },
            {
                "name": "Magen David Adom (MDA - Emergency Medical)",
                "helpline": "101",
                "url": "https://www.mdais.org",
                "role": "Emergency Medical Response",
            },
            {
                "name": "Home Front Command (פיקוד העורף)",
                "helpline": "104",
                "url": "https://www.oref.org.il",
                "role": "Civil Defense & Siren Alerts",
            },
        ],
        "local_tips": [
            "Download the official Home Front Command app for real-time localized civil defense sirens.",
            "Locate the nearest protected space (Mamad or public Miklat) upon checking into any accommodation.",
            "Dial 106 from any local line for municipal information on shelters and public transport.",
        ],
    },
    "jerusalem": {
        "district_name": "Jerusalem District & Municipality",
        "country": "Israel",
        "authorities": [
            {
                "name": "Jerusalem Municipality Emergency Center (106)",
                "helpline": "106",
                "url": "https://www.jerusalem.muni.il",
                "role": "Municipal Administration",
            },
            {
                "name": "Israel Police District Command",
                "helpline": "100",
                "url": "https://www.police.gov.il",
                "role": "Public Safety",
            },
            {
                "name": "Magen David Adom Medical Dispatch",
                "helpline": "101",
                "url": "https://www.mdais.org",
                "role": "Paramedic Services",
            },
        ],
        "local_tips": [
            "Be aware of heightened security checkpoints around the Old City and religious quarters.",
            "Monitor municipal updates regarding traffic disruptions and special security measures.",
        ],
    },
    "london": {
        "district_name": "Greater London Authority & Metropolitan District",
        "country": "United Kingdom",
        "authorities": [
            {
                "name": "Metropolitan Police Service (Emergency: 999 / Non-emergency: 101)",
                "helpline": "999",
                "url": "https://www.met.police.uk",
                "role": "Police Dispatch",
            },
            {
                "name": "NHS Urgent Medical Advice",
                "helpline": "111",
                "url": "https://111.nhs.uk",
                "role": "Healthcare Advice & Triage",
            },
            {
                "name": "Greater London Authority (GLA)",
                "helpline": "+44 20 7983 4000",
                "url": "https://www.london.gov.uk",
                "role": "City Administration & Civil Resilience",
            },
        ],
        "local_tips": [
            "Dial 999 for immediate emergency assistance, or 101 for non-urgent crime reporting.",
            "Check Transport for London (TfL) live updates for station disruptions and district safety announcements.",
        ],
    },
    "paris": {
        "district_name": "Préfecture de Police & Mairie de Paris",
        "country": "France",
        "authorities": [
            {
                "name": "SAMU Urgences Médicales (Ambulance)",
                "helpline": "15",
                "url": "https://www.samu-de-france.fr",
                "role": "Urgent Medical Care & Paramedics",
            },
            {
                "name": "Police Nationale & Préfecture de Police",
                "helpline": "17",
                "url": "https://www.prefecturedepolice.interieur.gouv.fr",
                "role": "Law Enforcement & Public Order",
            },
            {
                "name": "Sapeurs-Pompiers de Paris (Fire & Rescue)",
                "helpline": "18",
                "url": "https://pompiersparis.fr",
                "role": "Firefighting & Technical Rescue",
            },
            {
                "name": "European Emergency Call (Numéro d'urgence)",
                "helpline": "112",
                "url": "https://www.service-public.fr",
                "role": "Universal European Emergency Dispatch",
            },
        ],
        "local_tips": [
            "Dial 112 from any mobile phone for multilingual European emergency operators.",
            "Keep belongings secure in crowded metro stations and tourist precincts (Champs-Élysées, Louvre).",
        ],
    },
    "new york": {
        "district_name": "New York City Office of Emergency Management",
        "country": "United States",
        "authorities": [
            {
                "name": "NYC Emergency Dispatch (Police, Fire, EMS)",
                "helpline": "911",
                "url": "https://www1.nyc.gov",
                "role": "Immediate Emergency Dispatch",
            },
            {
                "name": "NYC 311 - District Administration & Civic Information",
                "helpline": "311",
                "url": "https://portal.311.nyc.gov",
                "role": "Municipal & District Services",
            },
            {
                "name": "NYC Emergency Management (Notify NYC)",
                "helpline": "+1-212-639-9675",
                "url": "https://www.nyc.gov/oem",
                "role": "Disaster Preparation & Alerts",
            },
        ],
        "local_tips": [
            "Enroll in Notify NYC or check 311 online for neighborhood weather or civic advisories.",
            "Keep emergency contact details and hotel address saved on offline maps.",
        ],
    },
    "tokyo": {
        "district_name": "Tokyo Metropolitan Government Disaster Prevention Division (東京都防災)",
        "country": "Japan",
        "authorities": [
            {
                "name": "Tokyo Metropolitan Police Department (警視庁)",
                "helpline": "110",
                "url": "https://www.keishicho.metro.tokyo.lg.jp",
                "role": "Police Dispatch & Public Safety",
            },
            {
                "name": "Tokyo Fire Department (Ambulance & Fire)",
                "helpline": "119",
                "url": "https://www.tfd.metro.tokyo.lg.jp",
                "role": "Medical Emergency & Rescue",
            },
            {
                "name": "Japan National Tourism Organization (JNTO) 24h Multilingual Tourist Hotline",
                "helpline": "+81-50-3816-2787",
                "url": "https://www.japan.travel",
                "role": "Tourist Assistance & Disaster Information",
            },
        ],
        "local_tips": [
            "Save emergency numbers: 110 for Police, 119 for Ambulance and Fire.",
            "Download Safety Tips app for real-time earthquake and tsunami warnings across Japan.",
        ],
    },
    "kathmandu": {
        "district_name": "Kathmandu District Administration Office & Tourist Police",
        "country": "Nepal",
        "authorities": [
            {
                "name": "Nepal Police Emergency Control Room",
                "helpline": "100",
                "url": "https://nepalpolice.gov.np",
                "role": "Emergency Police Dispatch",
            },
            {
                "name": "Nepal Tourist Police (Kathmandu Headquarters)",
                "helpline": "1144",
                "url": "https://nepalpolice.gov.np",
                "role": "Tourist Assistance & Trekking Safety",
            },
            {
                "name": "Nepal Red Cross Society Ambulance Service",
                "helpline": "102",
                "url": "https://nrcs.org",
                "role": "Ambulance & Emergency Medical Response",
            },
            {
                "name": "Kathmandu District Disaster Management Committee",
                "helpline": "+977-1-4247041",
                "url": "https://daokathmandu.moha.gov.np",
                "role": "District Administration & Disaster Coordination",
            },
        ],
        "local_tips": [
            "Contact Nepal Tourist Police on 1144 for 24/7 English-speaking tourist assistance.",
            "Verify road and mountain weather conditions before departing the Kathmandu Valley.",
        ],
    },
    "kullu": {
        "district_name": "District Administration Kullu & DDMA",
        "country": "India",
        "authorities": [
            {
                "name": "District Emergency Operation Centre (DEOC Kullu)",
                "helpline": "1077",
                "url": "https://hpkullu.nic.in",
                "role": "District Disaster Management",
            },
            {
                "name": "Deputy Commissioner & District Magistrate Office Kullu",
                "helpline": "+91-1902-222727",
                "url": "https://hpkullu.nic.in",
                "role": "District Administration",
            },
            {
                "name": "Himachal Pradesh Police (Kullu Control Room)",
                "helpline": "112",
                "url": "https://hppolice.gov.in",
                "role": "Law Enforcement & Traffic Control",
            },
            {
                "name": "Manali SDM / Municipal Council",
                "helpline": "+91-1902-252244",
                "url": "https://hpkullu.nic.in",
                "role": "Sub-Divisional Civil Administration",
            },
        ],
        "local_tips": [
            "Check Kullu-Manali highway road conditions before traveling over mountain passes.",
            "In case of landslides or heavy snowfall, contact DEOC Kullu on 1077.",
        ],
    },
    "delhi": {
        "district_name": "Delhi Disaster Management Authority (DDMA)",
        "country": "India",
        "authorities": [
            {
                "name": "Delhi Emergency Control Room",
                "helpline": "112",
                "url": "https://delhipolice.gov.in",
                "role": "Unified Emergency Response",
            },
            {
                "name": "Delhi Disaster Management Authority (DDMA)",
                "helpline": "1077",
                "url": "https://ddma.delhigovt.nic.in",
                "role": "District Disaster Coordination",
            },
            {
                "name": "Delhi Police Women Helpline",
                "helpline": "1091",
                "url": "https://delhipolice.gov.in",
                "role": "24x7 Safety Assistance",
            },
        ],
        "local_tips": [
            "Use verified prepaid taxi counters or licensed ride-hailing apps from major stations.",
            "Save 112 as the single emergency number across the National Capital Region.",
        ],
    },
}


# Comprehensive country-level emergency profiles for international destinations
COUNTRY_EMERGENCY_PROFILES: dict[str, dict[str, Any]] = {
    "libya": {
        "district_name": "Libyan Civil Protection & National Emergency Authority (هيئة السلامة الوطنية)",
        "country": "Libya",
        "authorities": [
            {
                "name": "National Emergency & Police Dispatch (شرطة النجدة)",
                "helpline": "1515",
                "url": "https://moi.gov.ly",
                "role": "Law Enforcement & Emergency Control",
            },
            {
                "name": "Libyan Red Crescent Emergency (الهلال الأحمر الليبي)",
                "helpline": "193",
                "url": "https://lrcs.org.ly",
                "role": "Emergency Medical Services & First Response",
            },
            {
                "name": "National Civil Protection & Fire Services",
                "helpline": "190",
                "url": "https://moi.gov.ly",
                "role": "Firefighting & Disaster Relief",
            },
            {
                "name": "Diplomatic & Consular Emergency Hotline",
                "helpline": "+218-21-340-2000",
                "url": "https://foreign.gov.ly",
                "role": "Foreign National Crisis Assistance",
            },
        ],
        "local_tips": [
            "Check municipal security checkpoint status before inter-district transit.",
            "Keep valid passport, visa documents, and consular emergency hotline numbers accessible.",
            "Avoid movements outside secure central perimeters after dark and observe local advisory notices.",
        ],
    },
    "france": {
        "district_name": "Préfecture & Municipal Emergency Services (France)",
        "country": "France",
        "authorities": [
            {
                "name": "European Emergency Number (Multilingual)",
                "helpline": "112",
                "url": "https://www.service-public.fr",
                "role": "Single European Emergency Call",
            },
            {
                "name": "SAMU Urgences Médicales (Medical Emergency)",
                "helpline": "15",
                "url": "https://www.samu-de-france.fr",
                "role": "Ambulance & Emergency Medical Response",
            },
            {
                "name": "Police Nationale / Gendarmerie",
                "helpline": "17",
                "url": "https://www.police-nationale.interieur.gouv.fr",
                "role": "Law Enforcement & Security Dispatch",
            },
            {
                "name": "Sapeurs-Pompiers (Fire & Rescue)",
                "helpline": "18",
                "url": "https://www.pompiers.fr",
                "role": "Firefighting & Civil Defense",
            },
        ],
        "local_tips": [
            "Dial 112 from any mobile phone for English and multilingual emergency dispatch.",
            "Keep copies of travel documents and monitor local prefecture announcements.",
        ],
    },
    "united kingdom": {
        "district_name": "Local Authority & Emergency Services (UK)",
        "country": "United Kingdom",
        "authorities": [
            {
                "name": "Emergency Services (Police, Fire, Ambulance)",
                "helpline": "999",
                "url": "https://www.gov.uk",
                "role": "Immediate 999 Dispatch",
            },
            {
                "name": "Non-Emergency Police Assistance",
                "helpline": "101",
                "url": "https://www.police.uk",
                "role": "Non-Urgent Reporting & Local Inquiries",
            },
            {
                "name": "NHS 111 Medical Advice",
                "helpline": "111",
                "url": "https://111.nhs.uk",
                "role": "Urgent Medical Assistance",
            },
        ],
        "local_tips": [
            "Dial 999 for immediate danger; use 101 for non-urgent crime reporting.",
            "Consult local council portals for municipal notices and transit alerts.",
        ],
    },
    "united states": {
        "district_name": "County & Municipal Emergency Management (USA)",
        "country": "United States",
        "authorities": [
            {
                "name": "Emergency Dispatch (Police, Fire, EMS)",
                "helpline": "911",
                "url": "https://www.ready.gov",
                "role": "Immediate 911 Emergency Dispatch",
            },
            {
                "name": "Municipal & Civic Non-Emergency Services",
                "helpline": "311",
                "url": "https://www.usa.gov",
                "role": "City Administration & Local Information",
            },
        ],
        "local_tips": [
            "Call 911 for all immediate fire, police, or medical emergencies.",
            "Consult 311 for localized non-emergency administrative services.",
        ],
    },
    "canada": {
        "district_name": "Municipal & Regional Emergency Services (Canada)",
        "country": "Canada",
        "authorities": [
            {
                "name": "Emergency Dispatch (Police, Fire, Paramedics)",
                "helpline": "911",
                "url": "https://www.getprepared.gc.ca",
                "role": "Immediate 911 Emergency Dispatch",
            },
            {
                "name": "City & Municipal Services Hotline",
                "helpline": "311",
                "url": "https://www.canada.ca",
                "role": "Municipal Administration & Civic Services",
            },
        ],
        "local_tips": [
            "Dial 911 for all life-safety emergencies across Canada.",
            "Check Environment Canada for severe weather and highway conditions.",
        ],
    },
    "japan": {
        "district_name": "Prefectural & Municipal Disaster Management (Japan)",
        "country": "Japan",
        "authorities": [
            {
                "name": "Japan Police Emergency (警察庁)",
                "helpline": "110",
                "url": "https://www.npa.go.jp",
                "role": "Police Dispatch & Crime Reporting",
            },
            {
                "name": "Fire & Ambulance Emergency (消防署)",
                "helpline": "119",
                "url": "https://www.fdma.go.jp",
                "role": "Medical Emergency & Rescue",
            },
            {
                "name": "JNTO 24h Multilingual Tourist Hotline",
                "helpline": "+81-50-3816-2787",
                "url": "https://www.japan.travel",
                "role": "Tourist Safety & Multilingual Assistance",
            },
        ],
        "local_tips": [
            "Remember: 110 for Police, 119 for Ambulance and Fire.",
            "The JNTO tourist hotline offers 24/7 English support for travelers.",
        ],
    },
    "nepal": {
        "district_name": "District Administration Office & Tourist Police (Nepal)",
        "country": "Nepal",
        "authorities": [
            {
                "name": "Nepal Police Emergency Control Room",
                "helpline": "100",
                "url": "https://nepalpolice.gov.np",
                "role": "Police Emergency Dispatch",
            },
            {
                "name": "Nepal Tourist Police 24/7 Hotline",
                "helpline": "1144",
                "url": "https://nepalpolice.gov.np",
                "role": "Tourist Assistance & Protection",
            },
            {
                "name": "Nepal Red Cross Society Ambulance",
                "helpline": "102",
                "url": "https://nrcs.org",
                "role": "Ambulance & First Aid Response",
            },
        ],
        "local_tips": [
            "Dial 1144 for Tourist Police anywhere in Nepal.",
            "Verify local mountain transit and monsoon trail conditions before travel.",
        ],
    },
    "thailand": {
        "district_name": "Provincial Administration & Tourist Police Bureau (Thailand)",
        "country": "Thailand",
        "authorities": [
            {
                "name": "Thailand Tourist Police (English 24/7)",
                "helpline": "1155",
                "url": "https://www.touristpolice.go.th",
                "role": "Tourist Protection & English Dispatch",
            },
            {
                "name": "Royal Thai Police Emergency",
                "helpline": "191",
                "url": "https://www.royalthaipolice.go.th",
                "role": "Police Dispatch",
            },
            {
                "name": "National Medical Emergency Center (Ambulance)",
                "helpline": "1669",
                "url": "https://www.niems.go.th",
                "role": "Ambulance & Trauma Care",
            },
        ],
        "local_tips": [
            "Call 1155 for Tourist Police with fluent English-speaking officers 24/7.",
            "Use authorized taxis with working meters or recognized ride-hailing applications.",
        ],
    },
    "united arab emirates": {
        "district_name": "Municipal Authority & Emergency Services (UAE)",
        "country": "United Arab Emirates",
        "authorities": [
            {
                "name": "Police Emergency",
                "helpline": "999",
                "url": "https://u.ae",
                "role": "Police Dispatch",
            },
            {
                "name": "Ambulance Services (National Ambulance)",
                "helpline": "998",
                "url": "https://u.ae",
                "role": "Paramedics & Trauma Response",
            },
            {
                "name": "Civil Defence (Fire & Rescue)",
                "helpline": "997",
                "url": "https://u.ae",
                "role": "Firefighting",
            },
            {
                "name": "Tourist Security & Assistance Hotline",
                "helpline": "901",
                "url": "https://u.ae",
                "role": "Non-Emergency Inquiries & Tourist Police",
            },
        ],
        "local_tips": [
            "Dial 999 for police, 998 for ambulance, and 901 for non-emergency inquiries.",
            "Respect local laws regarding photography and public etiquette.",
        ],
    },
    "saudi arabia": {
        "district_name": "Unified National Security Operations & Civil Defense (Saudi Arabia)",
        "country": "Saudi Arabia",
        "authorities": [
            {
                "name": "Unified Emergency Operations Center (911)",
                "helpline": "911",
                "url": "https://www.moi.gov.sa",
                "role": "Unified Emergency Dispatch (Makkah, Riyadh, Eastern)",
            },
            {
                "name": "Saudi Red Crescent Authority (Ambulance)",
                "helpline": "997",
                "url": "https://www.srca.org.sa",
                "role": "Emergency Medical Response",
            },
            {
                "name": "Traffic Police (Muroor)",
                "helpline": "993",
                "url": "https://www.moi.gov.sa",
                "role": "Highway Traffic Control",
            },
        ],
        "local_tips": [
            "Dial 911 for all emergencies in major provinces.",
            "Observe local cultural guidelines and carry visa and identification at all times.",
        ],
    },
    "germany": {
        "district_name": "Stadtverwaltung & Notfalldienste (Germany)",
        "country": "Germany",
        "authorities": [
            {
                "name": "European Emergency / Feuerwehr & Rettungsdienst",
                "helpline": "112",
                "url": "https://www.feuerwehr.de",
                "role": "Fire, Ambulance & European Emergency",
            },
            {
                "name": "Polizei Notruf (Police Emergency)",
                "helpline": "110",
                "url": "https://www.polizei.de",
                "role": "Law Enforcement",
            },
            {
                "name": "Ärztlicher Bereitschaftsdienst (Medical On-call)",
                "helpline": "116117",
                "url": "https://www.116117.de",
                "role": "Non-emergency Medical Consultation",
            },
        ],
        "local_tips": [
            "Dial 112 for ambulance/fire and 110 for police across Germany.",
            "116 117 provides doctor consultation during nights and weekends.",
        ],
    },
    "italy": {
        "district_name": "Prefettura & Servizi di Emergenza (Italy)",
        "country": "Italy",
        "authorities": [
            {
                "name": "Numero Unico Europeo per le Emergenze (NUE 112)",
                "helpline": "112",
                "url": "https://www.carabinieri.it",
                "role": "Unified European Emergency Call",
            },
            {
                "name": "Polizia di Stato (Emergency Police)",
                "helpline": "113",
                "url": "https://www.poliziadistato.it",
                "role": "Police Dispatch",
            },
            {
                "name": "Emergenza Sanitaria (Ambulance)",
                "helpline": "118",
                "url": "https://www.salute.gov.it",
                "role": "Emergency Medical Care",
            },
            {
                "name": "Vigili del Fuoco (Fire & Rescue)",
                "helpline": "115",
                "url": "https://www.vigilfuoco.it",
                "role": "Firefighting",
            },
        ],
        "local_tips": [
            "Dial 112 for all emergencies in Italy.",
            "Beware of pickpocketing in crowded historical centers and train stations.",
        ],
    },
    "spain": {
        "district_name": "Ayuntamiento & Servicios de Emergencias (Spain)",
        "country": "Spain",
        "authorities": [
            {
                "name": "Centro de Emergencias 112",
                "helpline": "112",
                "url": "https://www.112.es",
                "role": "Unified Emergency Dispatch",
            },
            {
                "name": "Policía Nacional",
                "helpline": "091",
                "url": "https://www.policia.es",
                "role": "National Police",
            },
            {
                "name": "Guardia Civil",
                "helpline": "062",
                "url": "https://www.guardiacivil.es",
                "role": "Rural & Highway Security",
            },
            {
                "name": "Urgencias Sanitarias (Ambulancia)",
                "helpline": "061",
                "url": "https://www.sanidad.gob.es",
                "role": "Medical Emergency",
            },
        ],
        "local_tips": [
            "Dial 112 from any telephone for emergency operators fluent in Spanish and English.",
            "Keep valuables secure in crowded metropolitan areas (Barcelona, Madrid).",
        ],
    },
    "australia": {
        "district_name": "State Emergency Service & Police Directorate (Australia)",
        "country": "Australia",
        "authorities": [
            {
                "name": "Emergency Services (Triple Zero - 000)",
                "helpline": "000",
                "url": "https://www.triplezero.gov.au",
                "role": "Immediate 000 Dispatch (Police, Fire, Ambulance)",
            },
            {
                "name": "State Emergency Service (SES Disaster Hotline)",
                "helpline": "132 500",
                "url": "https://www.ses.nsw.gov.au",
                "role": "Storm & Flood Assistance",
            },
            {
                "name": "Police Assistance Line (Non-urgent)",
                "helpline": "131 444",
                "url": "https://www.police.nsw.gov.au",
                "role": "Non-urgent Crime Assistance",
            },
        ],
        "local_tips": [
            "Dial 000 for all life-threatening emergencies.",
            "Check local bushfire alerts and beach lifeguard flags before outdoor activities.",
        ],
    },
    "russia": {
        "district_name": "Unified Emergency Dispatch & Civil Protection (Russia)",
        "country": "Russia",
        "authorities": [
            {
                "name": "Unified Emergency Services (112)",
                "helpline": "112",
                "url": "https://mchs.gov.ru",
                "role": "Unified Emergency Call",
            },
            {
                "name": "Police Emergency (Полиция)",
                "helpline": "102",
                "url": "https://мвд.рф",
                "role": "Law Enforcement Dispatch",
            },
            {
                "name": "Ambulance & Paramedic Services (Скорая помощь)",
                "helpline": "103",
                "url": "https://minzdrav.gov.ru",
                "role": "Medical Emergency",
            },
        ],
        "local_tips": [
            "Dial 112 from mobile phones for emergency assistance.",
            "Keep registration slips and passport documents available during transit.",
        ],
    },
    "china": {
        "district_name": "Municipal Public Security & Civil Emergency (China)",
        "country": "China",
        "authorities": [
            {
                "name": "Public Security Police (报警电话)",
                "helpline": "110",
                "url": "https://www.mps.gov.cn",
                "role": "Police Dispatch",
            },
            {
                "name": "Emergency Medical Center (急救中心)",
                "helpline": "120",
                "url": "https://www.nhc.gov.cn",
                "role": "Ambulance Dispatch",
            },
            {
                "name": "Fire & Rescue Department (火警)",
                "helpline": "119",
                "url": "https://www.119.gov.cn",
                "role": "Firefighting",
            },
            {
                "name": "Traffic Accident Police (交通事故)",
                "helpline": "122",
                "url": "https://www.mps.gov.cn",
                "role": "Traffic Accidents",
            },
        ],
        "local_tips": [
            "Dial 110 for police and 120 for medical emergency.",
            "Foreign travelers should register accommodation with the local police substation within 24 hours.",
        ],
    },
    "egypt": {
        "district_name": "Egyptian Tourism Police & Emergency Directorate",
        "country": "Egypt",
        "authorities": [
            {
                "name": "Tourist Police (شرطة السياحة)",
                "helpline": "126",
                "url": "https://moi.gov.eg",
                "role": "Tourist Protection & Multilingual Assistance",
            },
            {
                "name": "Emergency Police (شرطة النجدة)",
                "helpline": "122",
                "url": "https://moi.gov.eg",
                "role": "General Police Dispatch",
            },
            {
                "name": "Egyptian Ambulance Authority (الإسعاف)",
                "helpline": "123",
                "url": "https://www.mohp.gov.eg",
                "role": "Emergency Medical Services",
            },
        ],
        "local_tips": [
            "Dial 126 for Tourist Police assistance across Cairo, Luxor, and coastal resorts.",
            "Use licensed metered taxis or established ride-sharing services.",
        ],
    },
    "turkey": {
        "district_name": "İl Afet ve Acil Durum Müdürlüğü & 112 Acil Çağrı (Turkey)",
        "country": "Turkey",
        "authorities": [
            {
                "name": "112 Acil Çağrı Merkezi (Unified Emergency)",
                "helpline": "112",
                "url": "https://www.112.gov.tr",
                "role": "Unified Emergency Dispatch (Police, Medical, Fire)",
            },
            {
                "name": "AFAD - Disaster and Emergency Management Authority",
                "helpline": "122",
                "url": "https://www.afad.gov.tr",
                "role": "Disaster Response & Earthquake Coordination",
            },
        ],
        "local_tips": [
            "Dial 112 as the unified emergency number for police, ambulance, and fire services.",
            "Consult AFAD alerts for seismic activity and weather safety bulletins.",
        ],
    },
    "south africa": {
        "district_name": "Municipal Emergency Management Services (South Africa)",
        "country": "South Africa",
        "authorities": [
            {
                "name": "South African Police Service (SAPS Flying Squad)",
                "helpline": "10111",
                "url": "https://www.saps.gov.za",
                "role": "Police Emergency Dispatch",
            },
            {
                "name": "Ambulance & Emergency Medical Service",
                "helpline": "10177",
                "url": "https://www.health.gov.za",
                "role": "Medical Emergency",
            },
            {
                "name": "Mobile Emergency Call",
                "helpline": "112",
                "url": "https://www.gov.za",
                "role": "Universal Cellular Emergency",
            },
        ],
        "local_tips": [
            "Dial 10111 for police, or 112 from any mobile phone.",
            "Stick to authorized tourist routes and avoid walking alone after sunset.",
        ],
    },
    "switzerland": {
        "district_name": "Kantonale Notfallzentrale & Polizei (Switzerland)",
        "country": "Switzerland",
        "authorities": [
            {
                "name": "European Emergency Number",
                "helpline": "112",
                "url": "https://www.ch.ch",
                "role": "Universal Emergency",
            },
            {
                "name": "Police Emergency (Polizei / Police)",
                "helpline": "117",
                "url": "https://www.polizei.ch",
                "role": "Police Dispatch",
            },
            {
                "name": "Sanitätsnotruf (Ambulance)",
                "helpline": "144",
                "url": "https://www.ch.ch",
                "role": "Medical Emergency & Paramedics",
            },
            {
                "name": "Rega - Swiss Air-Rescue",
                "helpline": "1414",
                "url": "https://www.rega.ch",
                "role": "Alpine Mountain Rescue",
            },
        ],
        "local_tips": [
            "Dial 144 for medical emergencies, 117 for police, and 1414 for mountain rescue.",
            "Download MeteoSwiss app for alpine weather alerts and avalanche warnings.",
        ],
    },
}


def _is_destination_in_india(
    location_name: str,
    country: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> bool:
    """Accurately determine whether a destination is in India."""
    loc_lower = (location_name or "").lower()
    c_lower = (country or "").lower()

    if "india" in c_lower or c_lower == "in":
        return True
    if ", india" in loc_lower or loc_lower.endswith(" india"):
        return True

    if lat is not None and lon is not None:
        # Bounding envelope of India: (6.0 <= lat <= 37.5) and (68.0 <= lon <= 97.5)
        if 6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5:
            # Check if text does NOT mention a neighboring or international country
            foreign_keywords = (
                "libya", "france", "germany", "italy", "spain", "uk", "usa", "japan",
                "nepal", "china", "pakistan", "bangladesh", "sri lanka", "bhutan",
                "russia", "iran", "israel", "uae", "saudi", "thailand", "egypt"
            )
            if not any(f in loc_lower or f in c_lower for f in foreign_keywords):
                return True

    # Indian states and major territories
    indian_states = (
        "himachal", "kullu", "manali", "delhi", "maharashtra", "mumbai", "karnataka",
        "bengaluru", "tamil nadu", "chennai", "kerala", "uttarakhand", "rishikesh",
        "rajasthan", "jaipur", "ladakh", "kashmir", "goa", "punjab", "haryana",
        "gujarat", "uttar pradesh", "west bengal", "kolkata", "assam", "odisha"
    )
    if any(s in loc_lower for s in indian_states):
        return True

    return False


def resolve_district_authorities(
    location_name: str,
    country: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Resolve localized district administration details and verified authorities for a location.

    Returns:
        (district_title, authorities_list, local_tips)
    """
    loc_lower = (location_name or "").lower()
    c_lower = (country or "").lower()

    # Determine if in India
    in_india = _is_destination_in_india(location_name, country=country, lat=lat, lon=lon)

    # 1. Exact city/district match in registry
    for key, data in LOCALIZED_ADMIN_REGISTRY.items():
        if key in loc_lower:
            return data["district_name"], data["authorities"], data["local_tips"]

    # 2. Country-specific profile match
    # Look for country in country parameter or location name
    for c_key, c_data in COUNTRY_EMERGENCY_PROFILES.items():
        if c_key in c_lower or c_key in loc_lower:
            base_name = location_name.split(",")[0].strip()
            district_title = f"{base_name} District & {c_data['district_name']}"
            return district_title, c_data["authorities"], c_data["local_tips"]

    # 3. If in India, use India domestic administration fallback
    if in_india:
        base_name = location_name.split(",")[0].strip()
        return (
            f"{base_name} District Administration & Emergency Contacts",
            [
                {
                    "name": "Unified Emergency Response Support System (ERSS)",
                    "helpline": "112",
                    "url": "https://112.gov.in",
                    "role": "24x7 Emergency Police & Medical Dispatch",
                },
                {
                    "name": "State / District Disaster Management Authority",
                    "helpline": "1070",
                    "url": "https://ndma.gov.in",
                    "role": "Disaster Response Control Room",
                },
                {
                    "name": "National Highway Authority Helpline",
                    "helpline": "1033",
                    "url": "https://nhai.gov.in",
                    "role": "Highway Traffic & Road Assistance",
                },
            ],
            [
                "Dial 112 for any emergency requiring police, fire, or ambulance support.",
                "Verify road and weather conditions with local district administration before travel.",
            ],
        )

    # 4. Universal International Fallback (Abroad / Non-India)
    # NEVER show ERSS, NDMA, or Indian numbers for foreign destinations!
    base_name = location_name.split(",")[0].strip()
    country_display = country.strip() if country else (location_name.split(",")[-1].strip() if "," in location_name else "International")

    return (
        f"{base_name} Municipal Administration & Civil Emergency Authority ({country_display})",
        [
            {
                "name": f"{base_name} Emergency Police Dispatch",
                "helpline": "112 or 911",
                "url": "https://www.interpol.int",
                "role": "Law Enforcement & Immediate Police Dispatch",
            },
            {
                "name": "Emergency Medical Services & Red Cross / Red Crescent",
                "helpline": "112",
                "url": "https://www.ifrc.org",
                "role": "Paramedic Response & First Aid Assistance",
            },
            {
                "name": "Municipal Civil Protection & Emergency Directorate",
                "helpline": "112",
                "url": "https://www.un.org",
                "role": "Civil Defense & Disaster Preparedness",
            },
            {
                "name": "Diplomatic & Consular Crisis Assistance",
                "helpline": "Contact Nearest Embassy",
                "url": "https://www.mea.gov.in",
                "role": "Foreign National Consular Support",
            },
        ],
        [
            "Dial 112 or 911 (universal GSM emergency numbers supported across international mobile roaming networks).",
            "Keep accommodation address, emergency transport lines, and consular crisis contacts saved offline.",
            "Consult local municipal notices, transit alerts, and weather advisories before traveling.",
        ],
    )
