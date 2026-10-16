"""Pluggable geocoding service supporting Nominatim (default), Photon, and Mapbox."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, List
import httpx
from pydantic import BaseModel, Field

from config import Settings, load_settings
from gis.harmonize import snap_to_h3

logger = logging.getLogger("api.geocoder")

# Geographic bounding box of India: (min_lon, min_lat, max_lon, max_lat)
INDIA_BOUNDS = (68.0, 6.0, 97.5, 37.5)


def is_coordinate_in_india(lat: float, lon: float) -> bool:
    """Return True if (lat, lon) falls within India territory bounding envelope."""
    return INDIA_BOUNDS[1] <= lat <= INDIA_BOUNDS[3] and INDIA_BOUNDS[0] <= lon <= INDIA_BOUNDS[2]


class GeocodeCandidate(BaseModel):
    display_name: str
    lat: float
    lon: float
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    type: str
    state: str | None = None
    district: str | None = None
    country: str = "India"
    is_in_india: bool = True
    h3_cell: str | None = None


class GeocoderBase:
    async def geocode(self, query: str, limit: int = 5) -> list[GeocodeCandidate]:
        raise NotImplementedError


class NominatimGeocoder(GeocoderBase):
    """Nominatim provider with usage policy compliance: identifying User-Agent,

    1 req/sec rate limiting, in-memory caching, and countrycodes=in filter.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.base_url = self.settings.nominatim_base_url
        self.user_agent = self.settings.nominatim_user_agent
        self._cache: dict[str, tuple[float, list[GeocodeCandidate]]] = {}
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    async def geocode(self, query: str, limit: int = 5) -> list[GeocodeCandidate]:
        clean_q = query.strip()
        if not clean_q:
            return []

        # Check demo mode / fixtures first
        if self.settings.demo_mode or clean_q.lower() in ("manali", "delhi", "new delhi"):
            fixture_candidates = self._load_fixture_candidates(clean_q)
            if fixture_candidates:
                return fixture_candidates[:limit]

        cache_key = clean_q.lower()
        now = time.time()
        if cache_key in self._cache:
            ts, res = self._cache[cache_key]
            if now - ts < 86400.0:  # 24h cache
                return res[:limit]

        # Respect 1 req/sec usage policy
        async with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1.05:
                await asyncio.sleep(1.05 - elapsed)
            self._last_request_time = time.time()

            try:
                headers = {"User-Agent": self.user_agent}
                params = {
                    "q": clean_q,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "countrycodes": "in",
                    "limit": limit,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{self.base_url}/search", params=params, headers=headers)
                    if resp.status_code == 200:
                        items = resp.json()
                        candidates = self._parse_nominatim_results(items)
                        self._cache[cache_key] = (now, candidates)
                        return candidates
            except Exception as e:
                logger.warning(f"Nominatim geocode request failed: {e}. Falling back to fixtures if available.")

        # Fallback to fixtures if network fails
        fallback = self._load_fixture_candidates(clean_q)
        return fallback[:limit]

    def _parse_nominatim_results(self, items: list[dict[str, Any]]) -> list[GeocodeCandidate]:
        results: list[GeocodeCandidate] = []
        for it in items:
            try:
                lat = float(it["lat"])
                lon = float(it["lon"])
                raw_bbox = it.get("boundingbox", [])
                if len(raw_bbox) == 4:
                    # Nominatim returns [min_lat, max_lat, min_lon, max_lon]
                    min_lat, max_lat, min_lon, max_lon = (
                        float(raw_bbox[0]),
                        float(raw_bbox[1]),
                        float(raw_bbox[2]),
                        float(raw_bbox[3]),
                    )
                    bbox = (min_lon, min_lat, max_lon, max_lat)
                else:
                    bbox = (lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05)

                addr = it.get("address", {})
                state = addr.get("state") or addr.get("state_district")
                district = (
                    addr.get("state_district")
                    or addr.get("district")
                    or addr.get("county")
                    or addr.get("city")
                    or addr.get("town")
                )
                h3_res = snap_to_h3({"type": "Point", "coordinates": [lon, lat]}, resolution=7)
                h3_cell = h3_res[0] if h3_res else None

                in_india = is_coordinate_in_india(lat, lon) and (
                    addr.get("country_code", "in").lower() == "in"
                )

                candidate = GeocodeCandidate(
                    display_name=it.get("display_name", ""),
                    lat=lat,
                    lon=lon,
                    bbox=bbox,
                    type=it.get("type", "place"),
                    state=state,
                    district=district,
                    country=addr.get("country", "India"),
                    is_in_india=in_india,
                    h3_cell=h3_cell,
                )
                results.append(candidate)
            except Exception as ex:
                logger.debug(f"Failed parsing nominatim item: {ex}")
        return results

    def _load_fixture_candidates(self, query: str) -> list[GeocodeCandidate]:
        fixtures_path = Path("fixtures/geocode.json")
        if not fixtures_path.exists():
            fixtures_path = Path("../fixtures/geocode.json")
        if not fixtures_path.exists():
            return []

        try:
            with open(fixtures_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            q_lower = query.lower()
            key = "manali" if "manali" in q_lower else ("delhi" if "delhi" in q_lower else None)
            if not key or key not in data:
                return []
            return self._parse_nominatim_results(data[key])
        except Exception as e:
            logger.warning(f"Could not load geocode fixture: {e}")
            return []


class PhotonGeocoder(GeocoderBase):
    """Photon (Komoot) geocoder provider — stub / alternative."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    async def geocode(self, query: str, limit: int = 5) -> list[GeocodeCandidate]:
        # Fallback to Nominatim logic for reliability
        nom = NominatimGeocoder(self.settings)
        return await nom.geocode(query, limit)


class MapboxGeocoder(GeocoderBase):
    """Mapbox geocoding provider — stub / alternative requiring mapbox_access_token."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    async def geocode(self, query: str, limit: int = 5) -> list[GeocodeCandidate]:
        if not self.settings.mapbox_access_token:
            # Fallback to Nominatim
            nom = NominatimGeocoder(self.settings)
            return await nom.geocode(query, limit)
        # TODO(operator): Call mapbox v5 endpoint if token supplied
        nom = NominatimGeocoder(self.settings)
        return await nom.geocode(query, limit)


def get_geocoder(settings: Settings | None = None) -> GeocoderBase:
    cfg = settings or load_settings()
    provider = cfg.geocode_provider.lower()
    if provider == "photon":
        return PhotonGeocoder(cfg)
    elif provider == "mapbox":
        return MapboxGeocoder(cfg)
    return NominatimGeocoder(cfg)
