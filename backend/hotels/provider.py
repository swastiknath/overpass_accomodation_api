"""Hotel providers interface, OSM Overpass implementation, and third-party stubs."""

from __future__ import annotations

import abc
import asyncio
import hashlib
import logging
import math
import time
from typing import Any, List

import httpx

from config import Settings, load_settings
from hotels.models import AccessToHelp, Hotel

logger = logging.getLogger("hotels.provider")

TOURISM_REGEX = "^(hotel|guest_house|hostel|motel|apartment)$"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in kilometers between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return 6371.0 * c


class HotelProvider(abc.ABC):
    """Abstract interface for accommodation data providers."""

    @abc.abstractmethod
    async def search(
        self, lat: float, lon: float, radius_km: float, limit: int = 30
    ) -> list[Hotel]:
        """Search hotels around a center coordinate within radius_km."""
        pass

    @abc.abstractmethod
    async def get_access_to_help(
        self, lat: float, lon: float, hotels: list[Hotel], radius_km: float = 10.0
    ) -> dict[str, AccessToHelp]:
        """Calculate distance to nearest hospital, police, and fire station for each hotel."""
        pass


class OSMOverpassProvider(HotelProvider):
    """Default free provider using OpenStreetMap Overpass API.

    Queries tourism in (hotel, guest_house, hostel, motel, apartment).
    Parses stars, name, website, phone, and addr:* tags.
    Missing attributes stay None and are never defaulted to 0.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.endpoint = self.settings.overpass_url
        self.timeout = self.settings.overpass_timeout_seconds
        self._cache: dict[str, tuple[float, list[Hotel], dict[str, AccessToHelp]]] = {}
        self._ttl_seconds = 600.0  # 10 minutes cache

    def _build_cache_key(self, lat: float, lon: float, radius_km: float) -> str:
        rounded_lat = round(lat, 3)
        rounded_lon = round(lon, 3)
        rounded_rad = round(radius_km, 1)
        return f"{rounded_lat}:{rounded_lon}:{rounded_rad}"

    async def search(
        self, lat: float, lon: float, radius_km: float, limit: int = 30
    ) -> list[Hotel]:
        hotels, _ = await self._fetch_hotels_and_help(lat, lon, radius_km, limit)
        return hotels

    async def get_access_to_help(
        self, lat: float, lon: float, hotels: list[Hotel], radius_km: float = 10.0
    ) -> dict[str, AccessToHelp]:
        _, help_map = await self._fetch_hotels_and_help(lat, lon, radius_km, len(hotels))
        return help_map

    async def _fetch_hotels_and_help(
        self, lat: float, lon: float, radius_km: float, limit: int
    ) -> tuple[list[Hotel], dict[str, AccessToHelp]]:
        key = self._build_cache_key(lat, lon, radius_km)
        now = time.time()

        if key in self._cache:
            ts, cached_hotels, cached_help = self._cache[key]
            if now - ts < self._ttl_seconds:
                return cached_hotels[:limit], cached_help

        radius_meters = int(radius_km * 1000)
        # Combined query for accommodations and emergency services
        ql_query = f"""
        [out:json][timeout:{int(self.timeout)}];
        (
          node["tourism"~"{TOURISM_REGEX}"](around:{radius_meters},{lat},{lon});
          way["tourism"~"{TOURISM_REGEX}"](around:{radius_meters},{lat},{lon});
          node["amenity"~"^(hospital|police|fire_station)$"](around:{max(radius_meters, 8000)},{lat},{lon});
          way["amenity"~"^(hospital|police|fire_station)$"](around:{max(radius_meters, 8000)},{lat},{lon});
        );
        out center tags;
        """

        elements = await self._execute_overpass_query(ql_query)

        hotels: list[Hotel] = []
        hospitals: list[dict[str, Any]] = []
        police_stations: list[dict[str, Any]] = []
        fire_stations: list[dict[str, Any]] = []

        for el in elements:
            tags = el.get("tags", {})
            el_lat = el.get("lat") or el.get("center", {}).get("lat")
            el_lon = el.get("lon") or el.get("center", {}).get("lon")
            if el_lat is None or el_lon is None:
                continue

            # Check amenity first
            amenity = tags.get("amenity")
            if amenity == "hospital":
                hospitals.append({"name": tags.get("name"), "lat": el_lat, "lon": el_lon})
            elif amenity == "police":
                police_stations.append({"name": tags.get("name"), "lat": el_lat, "lon": el_lon})
            elif amenity == "fire_station":
                fire_stations.append({"name": tags.get("name"), "lat": el_lat, "lon": el_lon})

            # Check tourism
            tourism = tags.get("tourism")
            if tourism and tourism in ("hotel", "guest_house", "hostel", "motel", "apartment"):
                name = tags.get("name") or tags.get("name:en") or f"Unnamed {tourism.replace('_', ' ').title()}"
                osm_id = f"osm_{el.get('type', 'node')}_{el.get('id')}"

                # Parse stars if present
                stars_val = None
                raw_stars = tags.get("stars")
                if raw_stars:
                    try:
                        stars_val = float(raw_stars.strip().split(";")[0])
                    except (ValueError, TypeError):
                        pass

                # Compose address
                addr_parts = [
                    tags.get("addr:housenumber"),
                    tags.get("addr:street"),
                    tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
                    tags.get("addr:city"),
                    tags.get("addr:postcode"),
                ]
                formatted_addr = ", ".join([p for p in addr_parts if p]) or None

                dist = haversine_km(lat, lon, el_lat, el_lon)

                # Amenities
                amenities = []
                if tags.get("internet_access") in ("yes", "wlan", "wifi"):
                    amenities.append("WiFi")
                if tags.get("swimming_pool") == "yes":
                    amenities.append("Pool")
                if tags.get("air_conditioning") == "yes":
                    amenities.append("AC")
                if tags.get("wheelchair") == "yes":
                    amenities.append("Wheelchair Accessible")

                hotel = Hotel(
                    id=osm_id,
                    name=name,
                    lat=el_lat,
                    lon=el_lon,
                    source="osm",
                    source_id=str(el.get("id")),
                    category=tourism,
                    stars=stars_val,
                    rating=None,  # OSM does not have verified review ratings
                    review_count=None,
                    price_band=None,
                    amenities=amenities,
                    address=formatted_addr,
                    website=tags.get("website") or tags.get("contact:website"),
                    phone=tags.get("phone") or tags.get("contact:phone"),
                    distance_to_query_km=round(dist, 2),
                )
                hotels.append(hotel)

        if not hotels:
            logger.info("Overpass elements empty or failed; invoking live OpenStreetMap Nominatim provider fallback.")
            hotels, help_map = await self._fetch_from_nominatim(lat, lon, radius_km, limit)
            if hotels:
                self._cache[key] = (now, hotels, help_map)
                return hotels[:limit], help_map

        # Sort hotels by distance to anchor
        hotels.sort(key=lambda h: h.distance_to_query_km)

        # Compute nearest emergency facilities for each hotel
        help_map: dict[str, AccessToHelp] = {}
        for h in hotels:
            h_dist, h_name = self._find_nearest(h.lat, h.lon, hospitals)
            p_dist, p_name = self._find_nearest(h.lat, h.lon, police_stations)
            f_dist, f_name = self._find_nearest(h.lat, h.lon, fire_stations)

            help_map[h.id] = AccessToHelp(
                hospital_distance_km=round(h_dist, 2) if h_dist is not None else None,
                hospital_name=h_name,
                police_distance_km=round(p_dist, 2) if p_dist is not None else None,
                police_name=p_name,
                fire_station_distance_km=round(f_dist, 2) if f_dist is not None else None,
                fire_station_name=f_name,
            )

        self._cache[key] = (now, hotels, help_map)
        return hotels[:limit], help_map

    async def _fetch_from_nominatim(
        self, lat: float, lon: float, radius_km: float, limit: int
    ) -> tuple[list[Hotel], dict[str, AccessToHelp]]:
        """Direct live query to OpenStreetMap Nominatim for accommodations and emergency services."""
        lat_margin = radius_km / 111.32
        lon_margin = radius_km / (111.32 * max(0.01, math.cos(math.radians(lat))))
        min_lon = round(lon - lon_margin, 4)
        min_lat = round(lat - lat_margin, 4)
        max_lon = round(lon + lon_margin, 4)
        max_lat = round(lat + lat_margin, 4)

        base_url = self.settings.nominatim_base_url
        headers = {"User-Agent": self.settings.nominatim_user_agent}

        hotels: list[Hotel] = []
        hospitals: list[dict[str, Any]] = []
        police_stations: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
                # Query live hotels
                url = (
                    f"{base_url}/search?format=json&q=hotel"
                    f"&viewbox={min_lon},{max_lat},{max_lon},{min_lat}&bounded=1&limit={max(limit, 20)}"
                    f"&extratags=1&addressdetails=1"
                )
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    items = resp.json()
                    for it in items:
                        try:
                            h_lat = float(it["lat"])
                            h_lon = float(it["lon"])
                            h_name = it.get("name") or it.get("display_name", "").split(",")[0]
                            osm_id = f"osm_{it.get('osm_type', 'node')}_{it.get('osm_id', it.get('place_id'))}"
                            if any(existing.id == osm_id for existing in hotels):
                                continue
                            dist = haversine_km(lat, lon, h_lat, h_lon)
                            addr = it.get("display_name")
                            extratags = it.get("extratags", {})
                            stars_val = None
                            if "stars" in extratags:
                                try:
                                    stars_val = float(extratags["stars"].split(";")[0])
                                except Exception:
                                    pass

                            amenities = []
                            if "internet_access" in extratags:
                                amenities.append("WiFi")
                            if "swimming_pool" in extratags:
                                amenities.append("Pool")
                            if "air_conditioning" in extratags:
                                amenities.append("AC")

                            hotels.append(
                                Hotel(
                                    id=osm_id,
                                    name=h_name,
                                    lat=h_lat,
                                    lon=h_lon,
                                    source="osm",
                                    source_id=str(it.get("osm_id", "")),
                                    category=it.get("type", "hotel"),
                                    stars=stars_val,
                                    rating=None,
                                    review_count=None,
                                    price_band=None,
                                    amenities=amenities,
                                    address=addr,
                                    website=extratags.get("website"),
                                    phone=extratags.get("phone"),
                                    distance_to_query_km=round(dist, 2),
                                )
                            )
                        except Exception:
                            continue

                # Query emergency services
                try:
                    hosp_url = f"{base_url}/search?format=json&q=hospital&viewbox={min_lon},{max_lat},{max_lon},{min_lat}&bounded=1&limit=5"
                    police_url = f"{base_url}/search?format=json&q=police&viewbox={min_lon},{max_lat},{max_lon},{min_lat}&bounded=1&limit=5"
                    h_res, p_res = await asyncio.gather(
                        client.get(hosp_url, headers=headers),
                        client.get(police_url, headers=headers),
                        return_exceptions=True,
                    )
                    if not isinstance(h_res, Exception) and h_res.status_code == 200:
                        for it in h_res.json():
                            hospitals.append({
                                "name": it.get("name") or it.get("display_name", "").split(",")[0],
                                "lat": float(it["lat"]),
                                "lon": float(it["lon"]),
                            })
                    if not isinstance(p_res, Exception) and p_res.status_code == 200:
                        for it in p_res.json():
                            police_stations.append({
                                "name": it.get("name") or it.get("display_name", "").split(",")[0],
                                "lat": float(it["lat"]),
                                "lon": float(it["lon"]),
                            })
                except Exception as e:
                    logger.warning(f"Live emergency points query failed: {e}")

        except Exception as e:
            logger.warning(f"Nominatim fallback failed: {e}")

        hotels.sort(key=lambda h: h.distance_to_query_km)

        help_map: dict[str, AccessToHelp] = {}
        for h in hotels:
            h_dist, h_name = self._find_nearest(h.lat, h.lon, hospitals)
            p_dist, p_name = self._find_nearest(h.lat, h.lon, police_stations)
            help_map[h.id] = AccessToHelp(
                hospital_distance_km=round(h_dist, 2) if h_dist is not None else None,
                hospital_name=h_name,
                police_distance_km=round(p_dist, 2) if p_dist is not None else None,
                police_name=p_name,
            )

        return hotels[:limit], help_map

    def _find_nearest(
        self, lat: float, lon: float, facilities: list[dict[str, Any]]
    ) -> tuple[float | None, str | None]:
        if not facilities:
            return None, None
        best_d = float("inf")
        best_name = None
        for fac in facilities:
            d = haversine_km(lat, lon, fac["lat"], fac["lon"])
            if d < best_d:
                best_d = d
                best_name = fac["name"]
        return best_d, best_name

    OVERPASS_MIRRORS = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    async def _execute_overpass_query(self, query: str, max_retries: int = 2) -> list[dict[str, Any]]:
        mirrors = [self.endpoint] + [m for m in self.OVERPASS_MIRRORS if m != self.endpoint]
        # Fast rotation with short timeout per mirror to failover quickly
        for attempt in range(max_retries):
            mirror = mirrors[attempt % len(mirrors)]
            try:
                headers = {"User-Agent": "HotelsAPI-IndiaTravelSafety/2.0"}
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.5)) as client:
                    resp = await client.post(mirror, data={"data": query}, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        elements = data.get("elements", [])
                        if elements:
                            return elements
                    if resp.status_code in (429, 504, 502, 503):
                        logger.warning(f"Overpass mirror {mirror} returned HTTP {resp.status_code}, rotating...")
                        continue
                    logger.warning(f"Overpass mirror {mirror} returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Overpass request to {mirror} failed: {e}, rotating...")
        return []


# ── STUBS for commercial providers (marked STUB as requested) ─────────────


class GooglePlacesProvider(HotelProvider):
    """STUB: Google Places API hotel provider.

    TODO(operator): Implement when Google Maps Platform API key with Places API (New)
    is provisioned. Requires TextSearch / NearbySearch with includedType 'lodging'.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    async def search(
        self, lat: float, lon: float, radius_km: float, limit: int = 30
    ) -> list[Hotel]:
        # STUB implementation
        logger.info("STUB: GooglePlacesProvider.search called — returning empty list.")
        return []

    async def get_access_to_help(
        self, lat: float, lon: float, hotels: list[Hotel], radius_km: float = 10.0
    ) -> dict[str, AccessToHelp]:
        # STUB implementation
        return {h.id: AccessToHelp() for h in hotels}


class FoursquareProvider(HotelProvider):
    """STUB: Foursquare Places API provider.

    TODO(operator): Implement when Foursquare Places API v3 key is provisioned.
    Category ID for Hotel is 19014.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    async def search(
        self, lat: float, lon: float, radius_km: float, limit: int = 30
    ) -> list[Hotel]:
        # STUB implementation
        logger.info("STUB: FoursquareProvider.search called — returning empty list.")
        return []

    async def get_access_to_help(
        self, lat: float, lon: float, hotels: list[Hotel], radius_km: float = 10.0
    ) -> dict[str, AccessToHelp]:
        # STUB implementation
        return {h.id: AccessToHelp() for h in hotels}


class AmadeusProvider(HotelProvider):
    """STUB: Amadeus Hospitality API provider.

    TODO(operator): Implement when Amadeus Self-Service API credentials are provisioned.
    Requires OAuth2 token exchange and Hotel List / Hotel Search by Geocode endpoints.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    async def search(
        self, lat: float, lon: float, radius_km: float, limit: int = 30
    ) -> list[Hotel]:
        # STUB implementation
        logger.info("STUB: AmadeusProvider.search called — returning empty list.")
        return []

    async def get_access_to_help(
        self, lat: float, lon: float, hotels: list[Hotel], radius_km: float = 10.0
    ) -> dict[str, AccessToHelp]:
        # STUB implementation
        return {h.id: AccessToHelp() for h in hotels}
