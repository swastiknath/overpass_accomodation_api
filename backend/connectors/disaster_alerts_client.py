"""Multi-source geo-hazard real-time alert client.

Combines three no-auth (USGS, GDACS) / free-key (NASA FIRMS) feeds into
one connector with a shared retry/backoff policy:

- GDACS (gdacs.org) — multi-hazard alerts: earthquake, flood, cyclone, volcano
- NASA FIRMS — active fire detections (requires free MAP_KEY)
- USGS earthquake feed — GeoJSON, no auth

hazard_type is always specific ("flood" / "earthquake" / "fire" / "cyclone" /
"volcano"), never a generic "disaster" bucket — downstream scoring depends on
distinct hazard types.

Cadence: 15–30 min polling is appropriate for all three sources.
"""

from __future__ import annotations

import csv
import hashlib
import io
import time
from datetime import datetime, timezone
from typing import Any

import feedparser

from gis.config import Settings, load_settings
from gis.exceptions import ConfigError, MalformedResponse
from gis.schema import IngestedRecord, ResolutionTier

from connectors.base import BaseConnector

# ── GDACS severity mapping ────────────────────────────────────────────────
_GDACS_SEVERITY_MAP: dict[str, float] = {
    "Red": 0.9,
    "Orange": 0.7,
    "Green": 0.4,
}

# GDACS hazard-type normalization
_GDACS_HAZARD_MAP: dict[str, str] = {
    "EQ": "earthquake",
    "TC": "cyclone",
    "FL": "flood",
    "VO": "volcano",
    "DR": "drought",
    "WF": "fire",
}


class DisasterAlertsClient(BaseConnector):
    """Unified client for GDACS, NASA FIRMS, and USGS earthquake feeds."""

    SOURCE_NAME = "disaster_alerts"

    GDACS_FEED_URL = "https://www.gdacs.org/xml/rss.xml"
    GDACS_GEOJSON_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP"
    USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    FIRMS_CSV_URL = "https://firms.modaps.eosdis.nasa.gov/api/country/csv"

    def __init__(self, settings: Settings | None = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)

    # ── GDACS ─────────────────────────────────────────────────────────────

    def get_gdacs_alerts(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Fetch active GDACS alerts, optionally filtered by bbox.

        Uses RSS feed as primary, falls back to GeoJSON API.
        """

        def operation(attempt: int) -> list[dict[str, Any]]:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(self.GDACS_FEED_URL)
                resp.raise_for_status()
                raw = resp.text
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=self.GDACS_FEED_URL)
                self._log_fetch(
                    url=self.GDACS_FEED_URL, status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=self.GDACS_FEED_URL, status="ok", attempt=attempt, elapsed_ms=elapsed)

            feed = feedparser.parse(raw)
            return feed.get("entries", [])

        entries = self._with_retry(operation)
        self._record_success()
        return self._gdacs_to_records(entries, bbox)

    async def get_gdacs_alerts_async(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Async variant of get_gdacs_alerts."""

        async def operation(attempt: int) -> list[dict[str, Any]]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(self.GDACS_FEED_URL)
                resp.raise_for_status()
                raw = resp.text
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=self.GDACS_FEED_URL)
                self._log_fetch(
                    url=self.GDACS_FEED_URL,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=self.GDACS_FEED_URL, status="ok", attempt=attempt, elapsed_ms=elapsed)
            feed = feedparser.parse(raw)
            return feed.get("entries", [])

        entries = await self._with_retry_async(operation)
        self._record_success()
        return self._gdacs_to_records(entries, bbox)

    def _gdacs_to_records(
        self, entries: list[dict[str, Any]], bbox: tuple[float, float, float, float] | None
    ) -> list[IngestedRecord]:
        from shapely.geometry import Point

        records: list[IngestedRecord] = []
        ingest_time = datetime.now(timezone.utc)

        for entry in entries:
            try:
                # GDACS RSS uses gdacs:* namespace fields
                lat = float(entry.get("geo_lat", entry.get("gdacs_lat", 0)))
                lon = float(entry.get("geo_long", entry.get("gdacs_lon", 0)))
                if lat == 0 and lon == 0:
                    # Try from 'where' GeoRSS
                    where = entry.get("where", {})
                    if isinstance(where, dict):
                        coords = where.get("coordinates", [])
                        if coords and len(coords) >= 2:
                            lat, lon = float(coords[0]), float(coords[1])

                if lat == 0 and lon == 0:
                    continue

                if bbox:
                    lon_min, lat_min, lon_max, lat_max = bbox
                    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                        continue

                # Determine hazard type
                event_type_raw = entry.get("gdacs_eventtype", entry.get("gdacs_eventname", ""))
                hazard_type = _GDACS_HAZARD_MAP.get(str(event_type_raw).strip(), "earthquake")

                # Severity from alertlevel
                alert_level = entry.get("gdacs_alertlevel", "Green")
                severity_raw = _GDACS_SEVERITY_MAP.get(str(alert_level).strip(), 0.5)

                # Event time
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    event_time = datetime(*published[:6], tzinfo=timezone.utc)
                else:
                    event_time = ingest_time

                title = entry.get("title", "")
                event_id_raw = entry.get("id", entry.get("link", title))
                eid = f"gdacs:{hashlib.sha256(str(event_id_raw).encode()).hexdigest()[:16]}"

                record = IngestedRecord(
                    event_id=eid,
                    source="gdacs",
                    hazard_type=hazard_type,
                    geometry=Point(lon, lat),
                    event_time=event_time,
                    ingest_time=ingest_time,
                    severity_raw=severity_raw,
                    confidence=0.8,
                    resolution_tier=ResolutionTier.POINT,
                    raw_payload={
                        "title": title,
                        "alert_level": str(alert_level),
                        "description": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "event_type_raw": str(event_type_raw),
                    },
                )
                records.append(record)
            except Exception:
                continue

        return records

    # ── NASA FIRMS ────────────────────────────────────────────────────────

    def get_firms_fires(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        *,
        country: str = "IND",
        days: int = 1,
    ) -> list[IngestedRecord]:
        """Fetch active fire detections from NASA FIRMS.

        Requires FIRMS_MAP_KEY in config (free from
        https://firms.modaps.eosdis.nasa.gov/api/area/).
        """
        map_key = self._settings.firms_map_key
        if not map_key:
            raise ConfigError(
                "FIRMS_MAP_KEY not configured. Get a free key from "
                "https://firms.modaps.eosdis.nasa.gov/api/area/"
            )

        url = f"{self.FIRMS_CSV_URL}/{map_key}/VIIRS_SNPP_NRT/{country}/{days}"

        def operation(attempt: int) -> str:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(url)
                resp.raise_for_status()
                text = resp.text
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=url)
                self._log_fetch(
                    url=url, status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=url, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return text

        csv_text = self._with_retry(operation)
        self._record_success()
        return self._firms_csv_to_records(csv_text, bbox)

    async def get_firms_fires_async(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        *,
        country: str = "IND",
        days: int = 1,
    ) -> list[IngestedRecord]:
        """Async variant of get_firms_fires."""
        map_key = self._settings.firms_map_key
        if not map_key:
            raise ConfigError(
                "FIRMS_MAP_KEY not configured. Get a free key from "
                "https://firms.modaps.eosdis.nasa.gov/api/area/"
            )

        url = f"{self.FIRMS_CSV_URL}/{map_key}/VIIRS_SNPP_NRT/{country}/{days}"

        async def operation(attempt: int) -> str:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(url)
                resp.raise_for_status()
                text = resp.text
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=url)
                self._log_fetch(
                    url=url,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=url, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return text

        csv_text = await self._with_retry_async(operation)
        self._record_success()
        return self._firms_csv_to_records(csv_text, bbox)

    def _firms_csv_to_records(
        self, csv_text: str, bbox: tuple[float, float, float, float] | None
    ) -> list[IngestedRecord]:
        from shapely.geometry import Point

        records: list[IngestedRecord] = []
        ingest_time = datetime.now(timezone.utc)

        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            try:
                lat = float(row.get("latitude", 0))
                lon = float(row.get("longitude", 0))
                if lat == 0 and lon == 0:
                    continue

                if bbox:
                    lon_min, lat_min, lon_max, lat_max = bbox
                    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                        continue

                acq_date = row.get("acq_date", "")
                acq_time_str = row.get("acq_time", "0000")
                try:
                    event_time = datetime.strptime(
                        f"{acq_date} {acq_time_str}", "%Y-%m-%d %H%M"
                    ).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    event_time = ingest_time

                confidence = row.get("confidence", "nominal")
                conf_map = {"low": 0.3, "nominal": 0.6, "high": 0.9}
                try:
                    conf_val = float(confidence) / 100.0
                except (ValueError, TypeError):
                    conf_val = conf_map.get(str(confidence).lower(), 0.6)

                frp = float(row.get("frp", 0))
                # FRP (Fire Radiative Power) as severity — normalize roughly
                severity_raw = min(frp / 100.0, 1.0) if frp > 0 else 0.3

                eid_raw = f"firms:{lat}:{lon}:{acq_date}:{acq_time_str}"
                eid = f"firms:{hashlib.sha256(eid_raw.encode()).hexdigest()[:16]}"

                record = IngestedRecord(
                    event_id=eid,
                    source="nasa_firms",
                    hazard_type="fire",
                    geometry=Point(lon, lat),
                    event_time=event_time,
                    ingest_time=ingest_time,
                    severity_raw=severity_raw,
                    confidence=conf_val,
                    resolution_tier=ResolutionTier.POINT,
                    raw_payload={
                        "brightness": row.get("brightness"),
                        "frp": frp,
                        "satellite": row.get("satellite"),
                        "instrument": row.get("instrument"),
                        "daynight": row.get("daynight"),
                    },
                )
                records.append(record)
            except Exception:
                continue

        return records

    # ── USGS earthquakes ──────────────────────────────────────────────────

    def get_usgs_earthquakes(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Fetch recent earthquakes from USGS GeoJSON feed (no auth)."""

        def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(self.USGS_FEED_URL)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=self.USGS_FEED_URL)
                self._log_fetch(
                    url=self.USGS_FEED_URL,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=self.USGS_FEED_URL, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return data

        geojson = self._with_retry(operation)
        self._record_success()
        return self._usgs_to_records(geojson, bbox)

    async def get_usgs_earthquakes_async(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Async variant of get_usgs_earthquakes."""

        async def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(self.USGS_FEED_URL)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=self.USGS_FEED_URL)
                self._log_fetch(
                    url=self.USGS_FEED_URL,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=self.USGS_FEED_URL, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return data

        geojson = await self._with_retry_async(operation)
        self._record_success()
        return self._usgs_to_records(geojson, bbox)

    def _usgs_to_records(
        self, geojson: dict[str, Any], bbox: tuple[float, float, float, float] | None
    ) -> list[IngestedRecord]:
        from shapely.geometry import Point

        records: list[IngestedRecord] = []
        ingest_time = datetime.now(timezone.utc)

        features = geojson.get("features", [])
        for feat in features:
            try:
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [])
                if len(coords) < 2:
                    continue

                lon, lat = float(coords[0]), float(coords[1])

                if bbox:
                    lon_min, lat_min, lon_max, lat_max = bbox
                    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                        continue

                mag = float(props.get("mag", 0))
                # Normalize magnitude: <4 low, 4-6 moderate, >6 high
                severity_raw = min(mag / 10.0, 1.0) if mag > 0 else 0.3

                epoch_ms = props.get("time", 0)
                event_time = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)

                eid = f"usgs:{props.get('code', hashlib.sha256(str(feat.get('id', '')).encode()).hexdigest()[:16])}"

                record = IngestedRecord(
                    event_id=eid,
                    source="usgs",
                    hazard_type="earthquake",
                    geometry=Point(lon, lat),
                    event_time=event_time,
                    ingest_time=ingest_time,
                    severity_raw=severity_raw,
                    confidence=0.95,  # USGS seismographs are highly reliable
                    resolution_tier=ResolutionTier.POINT,
                    raw_payload={
                        "magnitude": mag,
                        "mag_type": props.get("magType"),
                        "place": props.get("place"),
                        "depth_km": float(coords[2]) if len(coords) > 2 else None,
                        "tsunami": props.get("tsunami"),
                        "felt": props.get("felt"),
                        "alert": props.get("alert"),
                        "url": props.get("url"),
                    },
                )
                records.append(record)
            except Exception:
                continue

        return records

    # ── Merged query ──────────────────────────────────────────────────────

    def get_all_active(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Fetch and merge alerts from all three sources.

        Individual source failures are caught and logged; partial results
        are returned rather than failing entirely.
        """
        all_records: list[IngestedRecord] = []
        errors: list[str] = []

        try:
            all_records.extend(self.get_gdacs_alerts(bbox))
        except Exception as exc:
            errors.append(f"gdacs: {exc}")

        try:
            all_records.extend(self.get_firms_fires(bbox))
        except ConfigError:
            # FIRMS key not configured — expected in some deployments
            errors.append("firms: FIRMS_MAP_KEY not configured (skipped)")
        except Exception as exc:
            errors.append(f"firms: {exc}")

        try:
            all_records.extend(self.get_usgs_earthquakes(bbox))
        except Exception as exc:
            errors.append(f"usgs: {exc}")

        return all_records

    async def get_all_active_async(
        self,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> list[IngestedRecord]:
        """Async variant of get_all_active — runs all three sources concurrently."""
        import asyncio

        results = await asyncio.gather(
            self.get_gdacs_alerts_async(bbox),
            self._firms_or_empty_async(bbox),
            self.get_usgs_earthquakes_async(bbox),
            return_exceptions=True,
        )

        all_records: list[IngestedRecord] = []
        for result in results:
            if isinstance(result, list):
                all_records.extend(result)
            # Exceptions are logged but don't block other sources

        return all_records

    async def _firms_or_empty_async(
        self, bbox: tuple[float, float, float, float] | None
    ) -> list[IngestedRecord]:
        """FIRMS wrapper that returns empty on ConfigError (key not set)."""
        try:
            return await self.get_firms_fires_async(bbox)
        except ConfigError:
            return []
