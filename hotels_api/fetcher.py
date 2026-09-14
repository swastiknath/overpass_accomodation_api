"""
Real-time client for Overpass API and OSM Geocoding services with automatic failover and retries.
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple, Dict, Any
import httpx
import requests

from hotels_api.models import HotelProperty, TourismType
from hotels_api.tag_parser import parse_osm_element

logger = logging.getLogger("hotels_api.fetcher")
logging.basicConfig(level=logging.INFO)

OVERPASS_MIRRORS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

TOURISM_REGEX = "^(hotel|hostel|guest_house|resort|motel|apartment|chalet|bed_and_breakfast|camp_site)$"


class OverpassFetcher:
    """
    High-performance Overpass API fetcher with multi-mirror failover, query generation,
    and normalized HotelProperty output.
    """

    def __init__(self, mirrors: Optional[List[str]] = None, timeout_seconds: int = 40):
        self.mirrors = mirrors or OVERPASS_MIRRORS
        self.timeout_seconds = timeout_seconds
        self._current_mirror_idx = 0

    def _get_mirror(self) -> str:
        return self.mirrors[self._current_mirror_idx % len(self.mirrors)]

    def _rotate_mirror(self):
        self._current_mirror_idx = (self._current_mirror_idx + 1) % len(self.mirrors)
        logger.info(f"Rotating Overpass mirror to: {self._get_mirror()}")

    def build_bbox_query(self, south: float, west: float, north: float, east: float, timeout: int = 90) -> str:
        """Construct Overpass QL query for a bounding box."""
        return f"""
        [out:json][timeout:{timeout}];
        (
          node["tourism"~"{TOURISM_REGEX}"]({south},{west},{north},{east});
          way["tourism"~"{TOURISM_REGEX}"]({south},{west},{north},{east});
        );
        out center tags;
        """

    def build_radius_query(self, lat: float, lon: float, radius_meters: float, timeout: int = 45) -> str:
        """Construct Overpass QL query around a coordinate radius."""
        return f"""
        [out:json][timeout:{timeout}];
        (
          node["tourism"~"{TOURISM_REGEX}"](around:{radius_meters},{lat},{lon});
          way["tourism"~"{TOURISM_REGEX}"](around:{radius_meters},{lat},{lon});
        );
        out center tags;
        """

    def build_id_query(self, osm_type: str, osm_id: int) -> str:
        """Construct query for single specific OSM element."""
        return f"""
        [out:json][timeout:25];
        {osm_type}({osm_id});
        out center tags;
        """

    def fetch_bbox(self, south: float, west: float, north: float, east: float, region: Optional[str] = None, max_retries: int = 6) -> List[HotelProperty]:
        """Synchronously fetch all accommodation POIs within a bounding box."""
        query = self.build_bbox_query(south, west, north, east, timeout=self.timeout_seconds)
        elements = self._execute_query_sync(query, max_retries=max_retries)
        
        properties = []
        for el in elements:
            prop = parse_osm_element(el, default_region=region)
            if prop:
                properties.append(prop)
        return properties

    async def fetch_bbox_async(self, south: float, west: float, north: float, east: float, region: Optional[str] = None, max_retries: int = 6) -> List[HotelProperty]:
        """Asynchronously fetch all accommodation POIs within a bounding box."""
        query = self.build_bbox_query(south, west, north, east, timeout=self.timeout_seconds)
        elements = await self._execute_query_async(query, max_retries=max_retries)
        
        properties = []
        for el in elements:
            prop = parse_osm_element(el, default_region=region)
            if prop:
                properties.append(prop)
        return properties

    async def fetch_radius_async(self, lat: float, lon: float, radius_meters: float = 5000.0, region: Optional[str] = None, max_retries: int = 6) -> List[HotelProperty]:
        """Asynchronously fetch accommodation POIs within a circle of radius meters."""
        query = self.build_radius_query(lat, lon, radius_meters, timeout=30)
        elements = await self._execute_query_async(query, max_retries=max_retries)
        
        properties = []
        for el in elements:
            prop = parse_osm_element(el, default_region=region)
            if prop:
                properties.append(prop)
        return properties

    def _execute_query_sync(self, query: str, max_retries: int = 6) -> List[Dict[str, Any]]:
        """Synchronous query runner with mirror rotation and backoff."""
        for attempt in range(max_retries):
            mirror = self._get_mirror()
            try:
                resp = requests.post(
                    mirror,
                    data={"data": query},
                    headers={"User-Agent": "HotelsAPI-DataPipeline/1.0"},
                    timeout=self.timeout_seconds,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("elements", [])
                elif resp.status_code in (429, 504, 502, 503):
                    logger.warning(f"Mirror {mirror} returned {resp.status_code}, rotating...")
                    self._rotate_mirror()
                    time.sleep(1.5 * (attempt + 1))
            except Exception as e:
                logger.warning(f"Error querying {mirror}: {e}. Retrying...")
                self._rotate_mirror()
                time.sleep(1.0 * (attempt + 1))

        return []

    async def _execute_query_async(self, query: str, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Asynchronous query runner with mirror rotation and backoff."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for attempt in range(max_retries):
                mirror = self._get_mirror()
                try:
                    resp = await client.post(
                        mirror,
                        data={"data": query},
                        headers={"User-Agent": "HotelsAPI-DataPipeline/1.0"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("elements", [])
                    elif resp.status_code in (429, 504, 502, 503):
                        logger.warning(f"Mirror {mirror} returned {resp.status_code}, rotating...")
                        self._rotate_mirror()
                        await asyncio.sleep(2 * (attempt + 1))
                except Exception as e:
                    logger.warning(f"Async error querying {mirror}: {e}. Retrying...")
                    self._rotate_mirror()
                    await asyncio.sleep(1.5 * (attempt + 1))
        return []


class GeocodingClient:
    """
    Client for resolving place names to coordinates and bounding boxes (Nominatim / Photon).
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

    @classmethod
    async def geocode_city_async(cls, query: str) -> Optional[Tuple[float, float, Tuple[float, float, float, float]]]:
        """
        Geocode a city or place name to (lat, lon, (south, west, north, east)).
        """
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "HotelsAPI-DataPipeline/1.0"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(cls.NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    results = resp.json()
                    if results:
                        item = results[0]
                        lat = float(item["lat"])
                        lon = float(item["lon"])
                        bb = item.get("boundingbox") # ["south", "north", "west", "east"]
                        if bb and len(bb) == 4:
                            bbox = (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3]))
                        else:
                            bbox = (lat - 0.08, lon - 0.08, lat + 0.08, lon + 0.08)
                        return lat, lon, bbox
        except Exception as e:
            logger.error(f"Geocoding failed for '{query}': {e}")
        return None
