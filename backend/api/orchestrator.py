"""Orchestrator for gathering hazard signals concurrently, computing fusion, and caching."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple

from shapely.geometry import Point, box, mapping

from config import Settings, load_settings
from gis.schema import IngestedRecord, ResolutionTier
from gis.harmonize import snap_to_admin_boundary, snap_to_h3
from connectors.acled_client import ACLEDClient
from connectors.crime_client import CrimeClient
from connectors.disaster_alerts_client import DisasterAlertsClient
from connectors.news_client import NewsClient
from connectors.weather_client import WeatherClient
from fusion.config import FusionConfig, load_fusion_config
from fusion.engine import compute_fusion_at_location
from hotels.models import AccessToHelp, Hotel, HotelScored
from hotels.provider import OSMOverpassProvider
from hotels.scoring import compute_hotel_scoring_and_ranking

logger = logging.getLogger("api.orchestrator")

DISCLAIMER_TEXT = (
    "This platform is an automated research intelligence and situational awareness tool "
    "aggregating public and satellite data. It is NOT an official disaster alert or travel "
    "advisory and must not replace official guidance from NDMA, IMD, or local state authorities."
)

# Global report cache (report_id -> report_dict)
REPORT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 300.0  # 5 minutes


class SignalOrchestrator:
    def __init__(self, settings: Settings | None = None, fusion_cfg: FusionConfig | None = None):
        self.settings = settings or load_settings()
        self.fusion_cfg = fusion_cfg or load_fusion_config(self.settings.fusion_config_path)

        # Clients
        self.disaster_client = DisasterAlertsClient(settings=self.settings)
        self.acled_client = ACLEDClient(settings=self.settings)
        self.weather_client = WeatherClient(settings=self.settings)
        self.crime_client = CrimeClient(settings=self.settings)
        self.news_client = NewsClient(settings=self.settings)
        self.hotel_provider = OSMOverpassProvider(settings=self.settings)

    async def gather_signals_and_score(
        self,
        lat: float,
        lon: float,
        location_name: str,
        district_id: str | None,
        state_name: str | None,
        radius_km: float = 5.0,
        alpha: float = 0.7,
        max_hotels: int = 30,
        price_preference: str | None = None,
    ) -> dict[str, Any]:
        """Fetch all signals concurrently, perform area and per-hotel fusion, and return report."""
        now_utc = datetime.now(timezone.utc)
        demo_mode = self.settings.demo_mode

        # Calculate bounding box for area queries (with margin for spatial kernel)
        lat_margin = (radius_km + 15.0) / 111.32
        lon_margin = (radius_km + 15.0) / (111.32 * max(0.01, math.cos(math.radians(lat))))
        bbox = (
            round(lon - lon_margin, 4),
            round(lat - lat_margin, 4),
            round(lon + lon_margin, 4),
            round(lat + lat_margin, 4),
        )

        all_records: list[IngestedRecord] = []
        coverage: dict[str, str] = {
            "landslide": "not_available_for_region",
            "flood": "no_signal_found",
            "cyclone": "no_signal_found",
            "earthquake": "no_signal_found",
            "fire": "no_signal_found",
            "conflict": "no_signal_found",
            "crime": "no_signal_found",
            "weather": "no_signal_found",
            "news": "no_signal_found",
        }
        sources_meta: dict[str, dict[str, Any]] = {}

        # ── 1. Concurrent Fetching ──────────────────────────────────────────
        if demo_mode:
            logger.info("DEMO_MODE=True: Loading fixture responses for all connectors.")
            demo_records, demo_coverage, demo_sources = self._load_fixtures(lat, lon, district_id, now_utc)
            all_records.extend(demo_records)
            coverage.update(demo_coverage)
            sources_meta.update(demo_sources)

            # Load hotels fixture
            hotels = self._load_hotels_fixture(lat, lon)
            help_map = {h.id: AccessToHelp() for h in hotels}
        else:
            # Live concurrent queries with circuit breakers / per-connector timeout
            disaster_task = asyncio.wait_for(self.disaster_client.get_all_active_async(bbox), timeout=15.0)
            acled_task = asyncio.wait_for(self.acled_client.get_events_async(bbox_or_country=bbox), timeout=15.0)
            weather_task = asyncio.wait_for(self.weather_client.get_conditions_async(lat, lon), timeout=15.0)
            crime_target = district_id or location_name
            crime_task = asyncio.wait_for(self.crime_client.get_district_crime_rate_async(crime_target), timeout=15.0)
            news_task = asyncio.wait_for(self.news_client.fetch_local_news_async(lat, lon, radius_km), timeout=15.0)
            hotel_task = asyncio.wait_for(self.hotel_provider.search(lat, lon, radius_km, limit=max_hotels), timeout=25.0)

            results = await asyncio.gather(
                disaster_task, acled_task, weather_task, crime_task, news_task, hotel_task,
                return_exceptions=True,
            )
            disaster_res, acled_res, weather_res, crime_res, news_res, hotels_res = results

            # Process Disaster alerts
            if isinstance(disaster_res, Exception):
                logger.warning(f"Disaster alerts connector failed: {disaster_res}")
                coverage["flood"] = "source_failed"
                coverage["earthquake"] = "source_failed"
                coverage["fire"] = "source_failed"
                sources_meta["disaster_alerts"] = {"status": "failed", "error": str(disaster_res)}
            else:
                sources_meta["disaster_alerts"] = {"status": "active", "last_fetched": now_utc.isoformat()}
                for rec in disaster_res:
                    all_records.append(rec)
                    coverage[rec.hazard_type] = "contributing"

            # Process ACLED
            if isinstance(acled_res, Exception):
                logger.warning(f"ACLED connector failed: {acled_res}")
                coverage["conflict"] = "source_failed"
                sources_meta["acled"] = {"status": "failed", "error": str(acled_res)}
            else:
                sources_meta["acled"] = {"status": "active", "last_fetched": now_utc.isoformat()}
                if acled_res:
                    coverage["conflict"] = "contributing"
                    for rec in acled_res:
                        all_records.append(rec)

            # Process Weather
            if isinstance(weather_res, Exception):
                logger.warning(f"Weather connector failed: {weather_res}")
                coverage["weather"] = "source_failed"
                sources_meta["weather"] = {"status": "failed", "error": str(weather_res)}
            else:
                sources_meta["weather"] = {"status": "active", "last_fetched": now_utc.isoformat()}
                rain_mm = weather_res.get("rainfall_mm_24h", 0.0)
                wind_speed = weather_res.get("current_conditions", {}).get("windspeed", 0.0)
                if rain_mm > 10.0 or wind_speed > 25.0:
                    coverage["weather"] = "contributing"
                w_rec = IngestedRecord(
                    event_id=f"weather:{round(lat, 2)}:{round(lon, 2)}",
                    source="open_meteo",
                    hazard_type="weather",
                    geometry=Point(lon, lat),
                    event_time=now_utc,
                    ingest_time=now_utc,
                    resolution_tier=ResolutionTier.POINT,
                    severity_raw=None,
                    confidence=0.85,
                    raw_payload={"rainfall_mm_24h": rain_mm, "wind_speed_kmh": wind_speed},
                )
                all_records.append(w_rec)

            # Process Crime
            if isinstance(crime_res, Exception):
                logger.warning(f"Crime connector failed: {crime_res}")
                coverage["crime"] = "source_failed"
                sources_meta["crime_datagov"] = {"status": "failed", "error": str(crime_res)}
            else:
                sources_meta["crime_datagov"] = {"status": "active", "last_fetched": now_utc.isoformat()}
                c_rate = crime_res.get("percentile_rank", 0.35)
                coverage["crime"] = "contributing"
                c_rec = IngestedRecord(
                    event_id=f"crime:{district_id or 'unknown'}",
                    source="crime_ncrb",
                    hazard_type="crime",
                    geometry=Point(lon, lat),
                    event_time=now_utc,
                    ingest_time=now_utc,
                    resolution_tier=ResolutionTier.DISTRICT,
                    district_id=district_id,
                    severity_raw=c_rate,
                    confidence=0.80,
                    raw_payload={"district": district_id, "year": crime_res.get("data_year")},
                )
                all_records.append(c_rec)

            # Process News
            if isinstance(news_res, Exception):
                logger.warning(f"News connector failed: {news_res}")
                coverage["news"] = "source_failed"
                sources_meta["news_gdelt"] = {"status": "failed", "error": str(news_res)}
            else:
                sources_meta["news_gdelt"] = {"status": "active", "last_fetched": now_utc.isoformat()}
                news_records = self.news_client.analyze_articles(news_res)
                if news_records:
                    coverage["news"] = "contributing"
                    all_records.extend(news_records)

            # Process Hotels
            if isinstance(hotels_res, Exception):
                logger.warning(f"Hotel provider search failed: {hotels_res}")
                hotels = []
                help_map = {}
            else:
                hotels = hotels_res
                help_map = await self.hotel_provider.get_access_to_help(lat, lon, hotels, radius_km=radius_km)

        # ── 2. Area Fusion Scoring ──────────────────────────────────────────
        area_result, area_eval = compute_fusion_at_location(
            records=all_records,
            target_lat=lat,
            target_lon=lon,
            target_district_id=district_id,
            coverage=coverage,
            config=self.fusion_cfg,
        )

        # ── 3. Local Per-Hotel Scoring & Ranking ─────────────────────────────
        ranked_hotels, same_area_warning = compute_hotel_scoring_and_ranking(
            hotels=hotels,
            records=all_records,
            coverage=coverage,
            target_district_id=district_id,
            config=self.fusion_cfg,
            access_to_help_map=help_map,
            alpha=alpha,
            price_preference=price_preference,
        )

        # ── 4. Spatial GeoJSON Generation ───────────────────────────────────
        # Licensing boundary enforcement:
        # If redistribution_allowed is False, do not expose raw coordinates or sensitive text from ACLED
        geojson = self._build_geojson_features(
            lat=lat,
            lon=lon,
            district_id=district_id,
            records=all_records,
            hotels=ranked_hotels,
            redistribution_allowed=self.settings.redistribution_allowed,
        )

        # ── 5. Assemble Stable Report ID ────────────────────────────────────
        h_str = f"{round(lat, 3)}:{round(lon, 3)}:{round(alpha, 2)}:{radius_km}:{self.fusion_cfg.config_version}"
        report_id = f"rep_{hashlib.sha256(h_str.encode('utf-8')).hexdigest()[:16]}"

        report = {
            "report_id": report_id,
            "demo": demo_mode,
            "config_version": self.fusion_cfg.config_version,
            "timestamp": now_utc.isoformat(),
            "location": {
                "display_name": location_name,
                "lat": lat,
                "lon": lon,
                "radius_km": radius_km,
                "district": district_id,
                "state": state_name,
                "bbox": bbox,
            },
            "area_score": {
                "safety_score": area_result.safety_score,
                "band": area_result.score_band.model_dump(),
                "confidence": area_result.confidence_label,
                "S_static": area_result.S_static,
                "S_dynamic": area_result.S_dynamic,
                "S_total": area_result.S_total,
                "no_active_hazards": area_result.no_active_hazards,
            },
            "contributions": [c.model_dump() for c in area_result.top_contributions],
            "coverage": area_result.coverage,
            "sources": sources_meta,
            "geojson": geojson,
            "hotels_ranked": [h.model_dump() for h in ranked_hotels[:max_hotels]],
            "same_area_warning": same_area_warning,
            "disclaimer": DISCLAIMER_TEXT,
        }

        # Cache report
        REPORT_CACHE[report_id] = (time.time(), report)
        return report

    def _build_geojson_features(
        self,
        lat: float,
        lon: float,
        district_id: str | None,
        records: list[IngestedRecord],
        hotels: list[HotelScored],
        redistribution_allowed: bool,
    ) -> dict[str, Any]:
        """Generate GeoJSON FeatureCollection containing anchor point, hazard features, and hotel markers."""
        features: list[dict[str, Any]] = []

        # Anchor search point
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "feature_type": "query_anchor",
                "label": "Search Location",
            },
        })

        # Hazards
        for r in records:
            # Licensing Boundary: For sources with restricted redistribution (e.g. ACLED),
            # if redistribution_allowed is False, strip raw coordinates / raw payloads and expose cell/aggregated
            if not redistribution_allowed and r.source == "acled":
                # Expose only at H3 cell resolution or general district geometry
                continue

            geom = mapping(r.geometry)
            props = {
                "feature_type": "hazard",
                "hazard_type": r.hazard_type,
                "source": r.source,
                "event_id": r.event_id,
                "resolution_tier": r.resolution_tier.value,
                "confidence": r.confidence,
                "event_time": r.event_time.isoformat() if hasattr(r.event_time, "isoformat") else str(r.event_time),
            }
            if r.raw_payload:
                props["title"] = r.raw_payload.get("title") or r.raw_payload.get("event_type")
            features.append({"type": "Feature", "geometry": geom, "properties": props})

        # Hotels
        for h in hotels:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [h.hotel.lon, h.hotel.lat]},
                "properties": {
                    "feature_type": "hotel",
                    "hotel_id": h.hotel.id,
                    "name": h.hotel.name,
                    "category": h.hotel.category,
                    "safety_score": h.safety_score,
                    "score_band": h.score_band.label,
                    "band_code": h.score_band.code,
                    "rank_score": h.rank_score,
                    "distance_km": h.hotel.distance_to_query_km,
                    "stars": h.hotel.stars,
                    "rating": h.hotel.rating,
                    "hospital_distance_km": h.access_to_help.hospital_distance_km,
                    "police_distance_km": h.access_to_help.police_distance_km,
                },
            })

        return {"type": "FeatureCollection", "features": features}

    def _load_fixtures(
        self, lat: float, lon: float, district_id: str | None, now_utc: datetime
    ) -> tuple[list[IngestedRecord], dict[str, str], dict[str, Any]]:
        """Load canned fixture records for DEMO_MODE."""
        records: list[IngestedRecord] = []
        coverage: dict[str, str] = {
            "landslide": "contributing",
            "flood": "contributing",
            "cyclone": "no_signal_found",
            "earthquake": "contributing",
            "fire": "contributing",
            "conflict": "contributing",
            "crime": "contributing",
            "weather": "contributing",
            "news": "contributing",
        }
        sources: dict[str, Any] = {
            "gdacs": {"status": "fixture", "data_effective_date": "2026-10-15"},
            "usgs": {"status": "fixture", "data_effective_date": "2026-10-15"},
            "firms": {"status": "fixture", "data_effective_date": "2026-10-15"},
            "acled": {"status": "fixture", "data_effective_date": "2026-10-14"},
            "weather": {"status": "fixture", "data_effective_date": "2026-10-16"},
            "crime": {"status": "fixture", "data_effective_date": "2022-NCRB"},
            "news": {"status": "fixture", "data_effective_date": "2026-10-15"},
            "bhuvan": {"status": "fixture", "data_effective_date": "2025-Atlas"},
        }

        # 1. GDACS flood fixture
        gdacs_path = Path("fixtures/gdacs.json")
        if gdacs_path.exists():
            with open(gdacs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    coords = feat["geometry"]["coordinates"]
                    props = feat["properties"]
                    records.append(
                        IngestedRecord(
                            event_id=props.get("eventid", "gdacs_1"),
                            source="gdacs",
                            hazard_type="flood",
                            geometry=Point(coords[0], coords[1]),
                            event_time=now_utc,
                            ingest_time=now_utc,
                            resolution_tier=ResolutionTier.POINT,
                            severity_raw=props.get("alertlevel", "Orange"),
                            confidence=0.90,
                            raw_payload={"title": props.get("eventname")},
                        )
                    )

        # 2. USGS earthquake fixture
        usgs_path = Path("fixtures/usgs.json")
        if usgs_path.exists():
            with open(usgs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    coords = feat["geometry"]["coordinates"]
                    props = feat["properties"]
                    records.append(
                        IngestedRecord(
                            event_id=feat.get("id", "usgs_1"),
                            source="usgs",
                            hazard_type="earthquake",
                            geometry=Point(coords[0], coords[1]),
                            event_time=now_utc,
                            ingest_time=now_utc,
                            resolution_tier=ResolutionTier.POINT,
                            severity_raw=props.get("mag", 3.8),
                            confidence=0.95,
                            raw_payload={"title": props.get("title")},
                        )
                    )

        # 3. FIRMS fire fixture
        firms_path = Path("fixtures/firms.csv")
        if firms_path.exists():
            with open(firms_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    f_lat = float(row["latitude"])
                    f_lon = float(row["longitude"])
                    records.append(
                        IngestedRecord(
                            event_id=f"firms:{f_lat}:{f_lon}",
                            source="firms",
                            hazard_type="fire",
                            geometry=Point(f_lon, f_lat),
                            event_time=now_utc,
                            ingest_time=now_utc,
                            resolution_tier=ResolutionTier.POINT,
                            severity_raw=float(row.get("confidence", 75)) / 100.0,
                            confidence=0.80,
                            raw_payload={"satellite": row.get("satellite"), "title": "Thermal Fire Anomaly"},
                        )
                    )

        # 4. ACLED conflict fixture
        acled_path = Path("fixtures/acled.json")
        if acled_path.exists():
            with open(acled_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("data", []):
                    c_lat = float(item["latitude"])
                    c_lon = float(item["longitude"])
                    records.append(
                        IngestedRecord(
                            event_id=f"acled:{item['data_id']}",
                            source="acled",
                            hazard_type="conflict",
                            geometry=Point(c_lon, c_lat),
                            event_time=now_utc,
                            ingest_time=now_utc,
                            resolution_tier=ResolutionTier.POINT,
                            severity_raw=None,
                            confidence=0.90,
                            raw_payload={
                                "event_type": item.get("event_type", "Protests"),
                                "fatalities": int(item.get("fatalities", 0)),
                                "title": item.get("notes", "Civil Protest"),
                            },
                        )
                    )

        # 5. Crime fixture
        crime_path = Path("fixtures/crime.json")
        if crime_path.exists():
            with open(crime_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
                records.append(
                    IngestedRecord(
                        event_id=f"crime:{c_data.get('district', 'Kullu')}",
                        source="crime_ncrb",
                        hazard_type="crime",
                        geometry=Point(lon, lat),
                        event_time=now_utc,
                        ingest_time=now_utc,
                        resolution_tier=ResolutionTier.DISTRICT,
                        district_id=district_id or c_data.get("district", "Kullu"),
                        severity_raw=c_data.get("percentile_rank", 0.28),
                        confidence=0.80,
                        raw_payload={"district": c_data.get("district"), "year": c_data.get("year", 2022)},
                    )
                )

        # 6. Landslide susceptibility baseline (for Himachal/mountainous region)
        records.append(
            IngestedRecord(
                event_id="bhuvan:landslide_susceptibility",
                source="bhuvan",
                hazard_type="landslide",
                geometry=Point(lon, lat),
                event_time=now_utc,
                ingest_time=now_utc,
                resolution_tier=ResolutionTier.POINT,
                severity_raw=0.35,  # Moderate landslide terrain susceptibility
                confidence=0.85,
                raw_payload={"title": "Landslide Susceptibility Atlas (NRSC)"},
            )
        )

        return records, coverage, sources

    def _load_hotels_fixture(self, lat: float, lon: float) -> list[Hotel]:
        hotels_path = Path("fixtures/hotels.json")
        if not hotels_path.exists():
            return []
        try:
            with open(hotels_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            hotels = [Hotel.model_validate(h) for h in data]
            return hotels
        except Exception as e:
            logger.warning(f"Failed loading hotels fixture: {e}")
            return []
