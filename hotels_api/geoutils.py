"""
Geospatial utilities for hotel calculations: distances, geohashing, bounding boxes, and projections.
"""

import math
from typing import Tuple, List, Dict

EARTH_RADIUS_M = 6_371_000.0

# Base32 map for standard Geohash encoding
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BASE32_MAP = {c: i for i, c in enumerate(_BASE32)}


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


def encode_geohash(lat: float, lon: float, precision: int = 7) -> str:
    """Encode latitude and longitude into a standard geohash string."""
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True

    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2.0
            if lon > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2.0
            if lat > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid

        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def bbox_contains(lat: float, lon: float, south: float, west: float, north: float, east: float) -> bool:
    """Check whether a point is within the specified bounding box."""
    return south <= lat <= north and west <= lon <= east


# Predefined bounding boxes for major tourism & hospitality regions across India, Nepal, and Global hubs
# Format: region_name: (south_lat, west_lon, north_lat, east_lon)
DEFAULT_REGIONS: Dict[str, Tuple[float, float, float, float]] = {

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: NORTH & HIMALAYAS
    # ═══════════════════════════════════════════════════════════════════════
    "rishikesh_haridwar": (29.85, 78.10, 30.20, 78.40),
    "manali_kasol": (32.00, 77.05, 32.35, 77.40),
    "shimla_kufri": (31.05, 77.10, 31.18, 77.28),
    "dharamshala_mcleodganj": (32.18, 76.28, 32.28, 76.38),
    "ladakh_leh": (34.10, 77.50, 34.20, 77.62),
    "srinagar_kashmir": (33.98, 74.75, 34.15, 74.92),
    "gulmarg": (34.02, 74.35, 34.08, 74.42),
    "pahalgam": (33.98, 75.28, 34.05, 75.36),
    "dehradun_mussoorie": (30.25, 78.00, 30.50, 78.15),
    "nainital_corbett": (29.28, 78.95, 29.42, 79.52),
    "delhi_ncr": (28.40, 76.85, 28.88, 77.38),
    "amritsar": (31.58, 74.82, 31.68, 74.94),
    "chandigarh": (30.68, 76.72, 30.80, 76.85),
    "varanasi": (25.24, 82.90, 25.35, 83.05),
    "agra": (27.12, 77.95, 27.24, 78.08),
    "ayodhya": (26.76, 82.16, 26.82, 82.24),
    "lucknow": (26.80, 80.88, 26.92, 81.02),
    # --- Additional North India ---
    "auli_uttarakhand": (30.50, 79.55, 30.56, 79.60),
    "lansdowne": (29.82, 78.66, 29.88, 78.72),
    "almora": (29.56, 79.62, 29.62, 79.68),
    "ranikhet": (29.62, 79.42, 29.68, 79.48),
    "dalhousie_khajjiar": (32.50, 75.92, 32.58, 76.02),
    "kasol": (32.00, 77.28, 32.04, 77.34),
    "spiti_valley_kaza": (32.20, 78.05, 32.25, 78.10),
    "bir_billing": (32.02, 76.68, 32.06, 76.74),
    "chamba_hp": (32.53, 76.10, 32.58, 76.16),
    "mathura_vrindavan": (27.46, 77.64, 27.56, 77.72),
    "allahabad_prayagraj": (25.38, 81.80, 25.50, 81.92),
    "kanpur": (26.40, 80.28, 26.52, 80.42),
    "gorakhpur": (26.72, 83.32, 26.82, 83.42),
    "bareilly": (28.32, 79.38, 28.42, 79.48),
    "meerut": (28.94, 77.68, 29.04, 77.78),
    "noida_greater_noida": (28.48, 77.28, 28.62, 77.42),
    "gurgaon_gurugram": (28.40, 77.00, 28.52, 77.10),
    "sonipat_panipat": (29.08, 76.90, 29.20, 77.02),
    "jalandhar_ludhiana": (30.88, 75.82, 31.38, 76.00),
    "pathankot": (32.26, 75.60, 32.32, 75.68),
    "kullu": (31.94, 77.08, 32.00, 77.14),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: WEST & RAJASTHAN
    # ═══════════════════════════════════════════════════════════════════════
    "jaipur": (26.80, 75.70, 27.02, 75.92),
    "udaipur": (24.52, 73.64, 24.65, 73.76),
    "jodhpur": (26.24, 72.98, 26.34, 73.08),
    "jaisalmer": (26.88, 70.85, 26.96, 71.00),
    "pushkar_ajmer": (26.42, 74.52, 26.52, 74.68),
    "mount_abu": (24.57, 72.69, 24.63, 72.75),
    "mumbai": (18.88, 72.75, 19.30, 73.05),
    "goa": (14.90, 73.65, 15.85, 74.35),
    "pune": (18.45, 73.78, 18.62, 73.95),
    "lonavala_khandala": (18.72, 73.38, 18.78, 73.46),
    "alibaug": (18.62, 72.84, 18.70, 72.90),
    "ahmedabad": (22.98, 72.50, 23.08, 72.65),
    # --- Additional West India & Rajasthan ---
    "bikaner": (28.00, 73.28, 28.08, 73.38),
    "chittorgarh": (24.86, 74.60, 24.92, 74.68),
    "ranthambore_sawai_madhopur": (26.00, 76.32, 26.06, 76.42),
    "alwar_neemrana": (27.28, 76.58, 27.38, 76.68),
    "bundi": (25.42, 75.60, 25.48, 75.66),
    "kota_rajasthan": (25.15, 75.80, 25.22, 75.88),
    "bharatpur": (27.18, 77.46, 27.24, 77.52),
    "nashik": (19.95, 73.75, 20.05, 73.85),
    "mahabaleshwar_panchgani": (17.90, 73.62, 17.96, 73.68),
    "shirdi": (19.75, 74.46, 19.80, 74.52),
    "aurangabad_ajanta_ellora": (19.85, 75.30, 19.92, 75.38),
    "nagpur": (21.10, 79.02, 21.20, 79.12),
    "surat": (21.15, 72.78, 21.25, 72.88),
    "vadodara_baroda": (22.28, 73.15, 22.38, 73.25),
    "rajkot": (22.26, 70.76, 22.34, 70.84),
    "dwarka": (22.22, 68.94, 22.28, 69.00),
    "somnath": (20.86, 70.38, 20.92, 70.42),
    "kutch_bhuj": (23.22, 69.62, 23.30, 69.72),
    "daman_diu": (20.38, 72.82, 20.44, 72.88),
    "silvassa": (20.26, 73.00, 20.30, 73.04),
    "kolhapur": (16.68, 74.20, 16.74, 74.28),
    "tarkarli_malvan": (16.00, 73.44, 16.08, 73.52),
    "ganpatipule": (17.14, 73.26, 17.18, 73.30),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: SOUTH
    # ═══════════════════════════════════════════════════════════════════════
    "bengaluru": (12.83, 77.48, 13.15, 77.75),
    "mysuru": (12.26, 76.60, 12.35, 76.70),
    "coorg_madikeri": (12.38, 75.70, 12.45, 75.78),
    "chikmagalur": (13.28, 75.74, 13.35, 75.82),
    "hampi": (15.30, 76.44, 15.38, 76.50),
    "gokarna": (14.52, 74.30, 14.56, 74.34),
    "hyderabad": (17.32, 78.34, 17.50, 78.55),
    "chennai": (12.92, 80.12, 13.18, 80.32),
    "puducherry": (11.90, 79.78, 12.00, 79.85),
    "ooty_nilgiris": (11.38, 76.67, 11.45, 76.74),
    "kodaikanal": (10.21, 77.46, 10.26, 77.52),
    "kerala_kochi": (9.88, 76.20, 10.05, 76.35),
    "munnar": (10.05, 77.03, 10.12, 77.09),
    "alappuzha_alleppey": (9.46, 76.30, 9.53, 76.36),
    "wayanad_kalpetta": (11.58, 76.05, 11.64, 76.12),
    "varkala": (8.71, 76.68, 8.76, 76.73),
    "kovalam_trivandrum": (8.37, 76.95, 8.52, 77.00),
    # --- Additional South India ---
    "mangaluru": (12.84, 74.82, 12.92, 74.90),
    "udupi_manipal": (13.28, 74.72, 13.38, 74.80),
    "badami_aihole_pattadakal": (15.90, 75.66, 15.96, 75.72),
    "hubli_dharwad": (15.32, 75.08, 15.42, 75.18),
    "belgaum_belagavi": (15.82, 74.48, 15.90, 74.56),
    "visakhapatnam_vizag": (17.68, 83.28, 17.78, 83.38),
    "tirupati_tirumala": (13.62, 79.38, 13.70, 79.44),
    "vijayawada": (16.48, 80.58, 16.56, 80.68),
    "madurai": (9.88, 78.08, 9.98, 78.18),
    "rameswaram": (9.26, 79.28, 9.30, 79.34),
    "kanyakumari": (8.06, 77.52, 8.10, 77.56),
    "thanjavur": (10.76, 79.12, 10.82, 79.18),
    "mahabalipuram_mamallapuram": (12.60, 80.18, 12.64, 80.22),
    "coimbatore": (11.00, 76.92, 11.08, 77.02),
    "coonoor": (11.34, 76.78, 11.38, 76.82),
    "yercaud": (11.76, 78.18, 11.80, 78.22),
    "thekkady_periyar": (9.58, 77.14, 9.62, 77.18),
    "kumarakom": (9.58, 76.40, 9.64, 76.46),
    "kannur_kerala": (11.84, 75.34, 11.90, 75.40),
    "bekal_kasaragod": (12.38, 75.02, 12.42, 75.06),
    "kozhikode_calicut": (11.22, 75.76, 11.30, 75.82),
    "thrissur": (10.50, 76.18, 10.56, 76.24),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: EAST & NORTHEAST
    # ═══════════════════════════════════════════════════════════════════════
    "kolkata": (22.45, 88.26, 22.65, 88.45),
    "darjeeling": (26.98, 88.22, 27.08, 88.30),
    "gangtok_sikkim": (27.30, 88.59, 27.36, 88.64),
    "puri": (19.78, 85.80, 19.84, 85.86),
    "bhubaneswar": (20.24, 85.78, 20.35, 85.86),
    "shillong_meghalaya": (25.55, 91.86, 25.60, 91.92),
    "guwahati": (26.12, 91.70, 26.20, 91.82),
    "khajuraho": (24.83, 79.90, 24.87, 79.95),
    "bhopal": (23.20, 77.36, 23.30, 77.46),
    "indore": (22.68, 75.82, 22.76, 75.92),
    "bodhgaya": (24.68, 84.97, 24.72, 85.01),
    # --- Additional East & Central India ---
    "kalimpong": (27.04, 88.44, 27.10, 88.50),
    "siliguri_new_jalpaiguri": (26.68, 88.38, 26.76, 88.46),
    "digha_mandarmani": (21.60, 87.50, 21.68, 87.58),
    "sundarbans": (21.80, 88.78, 21.92, 88.90),
    "konark": (19.86, 86.08, 19.90, 86.12),
    "gopalpur_on_sea": (19.24, 84.88, 19.28, 84.92),
    "cuttack": (20.44, 85.86, 20.52, 85.94),
    "ranchi": (23.32, 85.28, 23.42, 85.38),
    "jamshedpur": (22.76, 86.18, 22.84, 86.28),
    "patna": (25.58, 85.10, 25.68, 85.22),
    "rajgir_nalanda": (25.00, 85.38, 25.06, 85.44),
    "raipur": (21.22, 81.60, 21.32, 81.70),
    "jabalpur_marble_rocks": (23.12, 79.92, 23.22, 80.02),
    "pachmarhi": (22.44, 78.42, 22.50, 78.48),
    "ujjain": (23.16, 75.74, 23.22, 75.80),
    "sanchi": (23.46, 77.72, 23.50, 77.76),
    # --- Northeast India ---
    "tawang_arunachal": (27.56, 91.84, 27.60, 91.88),
    "kaziranga_assam": (26.56, 93.34, 26.60, 93.42),
    "majuli_island": (26.92, 93.98, 27.00, 94.12),
    "jorhat_assam": (26.74, 94.18, 26.80, 94.24),
    "tezpur_assam": (26.62, 92.78, 26.68, 92.84),
    "dimapur_nagaland": (25.88, 93.70, 25.94, 93.76),
    "kohima_nagaland": (25.64, 94.08, 25.70, 94.14),
    "imphal_manipur": (24.78, 93.92, 24.84, 93.98),
    "aizawl_mizoram": (23.72, 92.70, 23.78, 92.76),
    "agartala_tripura": (23.82, 91.26, 23.88, 91.32),
    "itanagar_arunachal": (27.08, 93.58, 27.14, 93.64),
    "cherrapunji_sohra": (25.26, 91.68, 25.30, 91.72),
    "dawki_meghalaya": (25.18, 92.00, 25.22, 92.04),
    "pelling_sikkim": (27.28, 88.22, 27.32, 88.26),
    "namchi_sikkim": (27.14, 88.34, 27.18, 88.38),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: PILGRIMAGE & HERITAGE CIRCUITS
    # ═══════════════════════════════════════════════════════════════════════
    "haridwar": (29.92, 78.12, 29.98, 78.18),
    "ujjain_mahakaleshwar": (23.16, 75.74, 23.22, 75.80),
    "dwarka_somnath": (22.22, 68.94, 22.28, 69.00),
    "tiruvannamalai": (12.22, 79.04, 12.26, 79.10),
    "shirdi_nasik": (19.75, 74.46, 19.80, 74.52),
    "amarnath_base": (34.22, 75.48, 34.28, 75.54),
    "kedarnath_gaurikund": (30.72, 79.04, 30.76, 79.10),
    "badrinath_joshimath": (30.72, 79.48, 30.78, 79.54),
    "gangotri_uttarkashi": (30.96, 78.92, 31.02, 78.98),
    "deoghar_jharkhand": (24.46, 86.68, 24.52, 86.74),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: WILDLIFE & NATURE RESERVES
    # ═══════════════════════════════════════════════════════════════════════
    "jim_corbett_ramnagar": (29.38, 79.04, 29.44, 79.12),
    "ranthambore_national_park": (26.00, 76.32, 26.06, 76.42),
    "kanha_national_park": (22.32, 80.60, 22.38, 80.68),
    "bandhavgarh": (23.70, 80.92, 23.76, 80.98),
    "pench_national_park": (21.68, 79.28, 21.74, 79.34),
    "tadoba_national_park": (20.22, 79.36, 20.28, 79.42),
    "kabini_nagarhole": (11.90, 76.10, 11.96, 76.16),
    "bandipur_national_park": (11.66, 76.22, 11.72, 76.28),
    "gir_forest_sasan": (21.10, 70.54, 21.16, 70.60),
    "periyar_thekkady_wildlife": (9.58, 77.14, 9.62, 77.18),
    "sundarbans_tiger_reserve": (21.78, 88.68, 21.86, 88.82),

    # ═══════════════════════════════════════════════════════════════════════
    # INDIA: COASTAL & BEACH DESTINATIONS
    # ═══════════════════════════════════════════════════════════════════════
    "andaman_port_blair": (11.62, 92.70, 11.68, 92.76),
    "havelock_island_andaman": (12.00, 93.00, 12.04, 93.04),
    "lakshadweep_kavaratti": (10.54, 72.62, 10.58, 72.66),
    "diu_island": (20.70, 70.88, 20.76, 70.94),
    "gopalpur_beach": (19.24, 84.88, 19.28, 84.92),

    # ═══════════════════════════════════════════════════════════════════════
    # NEPAL: COMPREHENSIVE COVERAGE
    # ═══════════════════════════════════════════════════════════════════════
    "kathmandu_thamel": (27.68, 85.28, 27.74, 85.34),
    "kathmandu_patankirtipur": (27.64, 85.27, 27.70, 85.35),
    "kathmandu_boudhanath": (27.70, 85.34, 27.74, 85.39),
    "bhaktapur_nepal": (27.66, 85.40, 27.70, 85.45),
    "pokhara_lakeside": (28.18, 83.92, 28.26, 84.05),
    "pokhara_sarangkot": (28.22, 83.92, 28.28, 83.98),
    "chitwan_sauraha": (27.55, 84.42, 27.60, 84.52),
    "lumbini_nepal": (27.46, 83.26, 27.52, 83.30),
    "nagarkot_nepal": (27.69, 85.50, 27.73, 85.54),
    "dhulikhel_nepal": (27.60, 85.53, 27.64, 85.57),
    "bandipur_nepal": (27.91, 84.40, 27.95, 84.44),
    "namche_bazaar_everest": (27.79, 86.70, 27.83, 86.73),
    "lukla_everest": (27.67, 86.71, 27.71, 86.74),
    "janakpur_nepal": (26.71, 85.91, 26.75, 85.94),
    "dharan_nepal": (26.80, 87.26, 26.84, 87.30),
    "biratnagar_nepal": (26.44, 87.26, 26.50, 87.30),
    # --- Additional Nepal Regions ---
    "kathmandu_durbar_square": (27.70, 85.30, 27.72, 85.33),
    "kathmandu_lazimpat": (27.72, 85.31, 27.74, 85.34),
    "patan_lalitpur": (27.66, 85.30, 27.68, 85.34),
    "kirtipur_nepal": (27.66, 85.26, 27.68, 85.30),
    "bhaktapur_old_city": (27.67, 85.42, 27.69, 85.44),
    "pokhara_damside": (28.20, 83.94, 28.22, 83.98),
    "pokhara_phewa": (28.20, 83.92, 28.24, 83.96),
    "besisahar_lamjung": (28.22, 84.38, 28.26, 84.42),
    "jomsom_mustang": (28.76, 83.72, 28.80, 83.76),
    "manang_nepal": (28.66, 84.00, 28.70, 84.04),
    "tatopani_nepal": (28.48, 83.64, 28.52, 83.68),
    "ghandruk_nepal": (28.36, 83.78, 28.40, 83.82),
    "tansen_palpa": (27.86, 83.52, 27.90, 83.56),
    "butwal_nepal": (27.68, 83.44, 27.72, 83.48),
    "bharatpur_chitwan": (27.66, 84.42, 27.70, 84.46),
    "hetauda_nepal": (27.40, 85.02, 27.44, 85.06),
    "nepalganj_nepal": (28.04, 81.60, 28.08, 81.64),
    "surkhet_nepal": (28.58, 81.60, 28.62, 81.64),
    "dhangadhi_nepal": (28.68, 80.56, 28.72, 80.60),
    "ilam_nepal": (26.90, 87.92, 26.94, 87.96),
    "taplejung_nepal": (27.34, 87.66, 27.38, 87.70),
    "birgunj_nepal": (27.00, 84.86, 27.04, 84.90),
    "kakarbhitta_nepal": (26.64, 88.12, 26.68, 88.16),
    "gorkha_nepal": (28.00, 84.62, 28.04, 84.66),
    "muktinath_nepal": (28.80, 83.86, 28.84, 83.90),
    "bardiya_national_park": (28.36, 81.48, 28.42, 81.56),
    "phaplu_solukhumbu": (27.50, 86.56, 27.54, 86.60),
    "tengboche_nepal": (27.82, 86.76, 27.86, 86.80),

    # ═══════════════════════════════════════════════════════════════════════
    # SOUTHEAST ASIA & GLOBAL HUBS
    # ═══════════════════════════════════════════════════════════════════════
    "bali_ubud_seminyak": (-8.75, 115.10, -8.45, 115.30),
    "bangkok": (13.65, 100.40, 13.85, 100.65),
    "phuket": (7.75, 98.25, 8.20, 98.45),
    "singapore": (1.20, 103.60, 1.48, 104.05),
    "dubai": (25.00, 55.10, 25.35, 55.45),
    "paris": (48.81, 2.22, 48.91, 2.47),
    "london": (51.45, -0.25, 51.58, 0.05),
    "new_york_manhattan": (40.70, -74.02, 40.85, -73.92),
    "tokyo_central": (35.62, 139.65, 35.75, 139.85),
}
