"""Bhuvan / NRSC (ISRO) OGC WMS/WFS client.

Do not hardcode thematic layer names. Call `list_available_layers()` against a
real GetCapabilities document and copy names into your config after inspection.

Network characteristics (applies to every method that talks to Bhuvan):
    Expected latency: often 5–30s for GetCapabilities; GetMap of an India-wide
    bbox can exceed 60s or fail outright. Endpoints drop connections and return
    5xx regularly. Treat this as a flaky government geoportal, not a REST API.
    Retry policy: exponential backoff on timeouts and 5xx only
    (`BHUVAN_MAX_RETRIES`, `BHUVAN_RETRY_BASE_SECONDS`). Auth failures,
    unknown layers, and malformed bodies are not retried.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError

import geopandas as gpd
from owslib.util import ServiceException as OwsServiceException
from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from shapely.geometry import box

from gis.config import INDIA_BBOX, Settings, load_settings
from gis.exceptions import (
    AuthFailure,
    ConfigError,
    LayerNotFound,
    MalformedResponse,
    NetworkTimeout,
    ServerUnavailable,
)
from gis.logging_utils import log_raw_fetch
from gis.schema import IngestedRecord, ResolutionTier, raster_tile_event_id
from gis.storage import assert_private_destination, write_private_bytes

ServiceKind = Literal["wms", "wfs"]


@dataclass(frozen=True)
class BhuvanClientConfig:
    """Per-service OGC connection parameters (Bhuvan hosts several WMS/WFS roots).

    TODO(confirm-against-GetCapabilities): the exact GetCapabilities URL and
    version string for each Bhuvan product you care about (thematic WMS vs
    disaster-management WMS vs WFS). Portal homepages such as
    https://bhuvan-app1.nrsc.gov.in/bhuvandisaster/ are NOT OGC endpoints.
    Copy the real `...?service=WMS&request=GetCapabilities` URL from the
    layer's metadata panel or network tab, then put it here.
    """

    wms_base_url: str
    wfs_base_url: str
    wms_version: str = "1.3.0"
    wfs_version: str = "2.0.0"
    username: str | None = None
    password: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 4
    retry_base_seconds: float = 1.5
    default_width: int = 1024
    default_height: int = 1024

    @classmethod
    def from_mapping(cls, data: dict[str, Any], settings: Settings | None = None) -> BhuvanClientConfig:
        cfg = settings or load_settings()
        wms = data.get("wms") or {}
        wfs = data.get("wfs") or {}
        return cls(
            wms_base_url=wms.get("base_url", data.get("wms_base_url", cfg.bhuvan_wms_base_url)),
            wfs_base_url=wfs.get("base_url", data.get("wfs_base_url", cfg.bhuvan_wfs_base_url)),
            wms_version=str(wms.get("version", data.get("wms_version", cfg.bhuvan_wms_version))),
            wfs_version=str(wfs.get("version", data.get("wfs_version", cfg.bhuvan_wfs_version))),
            username=data.get("username", cfg.bhuvan_username),
            password=data.get("password", cfg.bhuvan_password),
            timeout_seconds=float(data.get("timeout_seconds", cfg.bhuvan_timeout_seconds)),
            max_retries=int(data.get("max_retries", cfg.bhuvan_max_retries)),
            retry_base_seconds=float(data.get("retry_base_seconds", cfg.bhuvan_retry_base_seconds)),
            default_width=int(data.get("default_width", cfg.bhuvan_default_width)),
            default_height=int(data.get("default_height", cfg.bhuvan_default_height)),
        )

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> BhuvanClientConfig:
        return cls.from_mapping({}, settings=settings)


class BhuvanClient:
    """Thin typed wrapper around owslib WMS/WFS for Bhuvan endpoints."""

    def __init__(
        self,
        config: BhuvanClientConfig | dict[str, Any] | None = None,
        settings: Settings | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        wms_factory: Callable[..., Any] = WebMapService,
        wfs_factory: Callable[..., Any] = WebFeatureService,
    ) -> None:
        self._settings = settings or load_settings()
        if config is None:
            self.config = BhuvanClientConfig.from_settings(self._settings)
        elif isinstance(config, dict):
            self.config = BhuvanClientConfig.from_mapping(config, settings=self._settings)
        else:
            self.config = config
        self._sleep = sleep
        self._wms_factory = wms_factory
        self._wfs_factory = wfs_factory
        self._wms: Any | None = None
        self._wfs: Any | None = None

    def list_available_layers(self, service: ServiceKind = "wms") -> list[dict[str, str]]:
        """Return layer names advertised by GetCapabilities.

        Latency/reliability: GetCapabilities is a network call; expect multi-second
        responses and occasional 5xx/timeouts. Retry policy: exponential backoff
        on timeout/5xx only (see module docstring).

        Use this to discover real layer identifiers before wiring `get_layer` /
        `get_features`. Do not assume names from blogs or older Bhuvan docs.
        """

        svc = self._connect(service)
        layers: list[dict[str, str]] = []
        contents = getattr(svc, "contents", {}) or {}
        for name, meta in contents.items():
            layers.append(
                {
                    "name": str(name),
                    "title": str(getattr(meta, "title", "") or ""),
                    "abstract": str(getattr(meta, "abstract", "") or ""),
                }
            )
        return layers

    def get_layer(
        self,
        layer_name: str,
        bbox: tuple[float, float, float, float] | None = None,
        crs: str = "EPSG:4326",
        output_format: str = "image/tiff",
        *,
        width: int | None = None,
        height: int | None = None,
        styles: list[str] | None = None,
    ) -> bytes:
        """WMS GetMap → raw raster bytes.

        Latency/reliability: GetMap for a national bbox is often slow or fails.
        Retry policy: exponential backoff on timeout/5xx; not on 401/403,
        unknown layer, or OGC exception XML.

        TODO(confirm-against-GetCapabilities):
          - Exact `Name` of each disaster/thematic layer (flood, cyclone,
            landslide risk) on the chosen WMS root.
          - Whether this endpoint is WMS 1.1.1 or 1.3.0. Version 1.3.0 +
            EPSG:4326 commonly swaps axis order (lat,lon vs lon,lat); confirm
            from the Capabilities CRS and a known coastal tile before treating
            pixels as georeferenced.
          - Advertised GetMap formats (image/tiff vs image/geotiff vs png).
          - Maximum Width/Height the server accepts (national 1024² may 400).
          - Style names; many Bhuvan layers require a non-empty style.
        """

        bbox = bbox or INDIA_BBOX
        width = width or self.config.default_width
        height = height or self.config.default_height
        url = self._require_url("wms")

        def operation(attempt: int) -> bytes:
            wms = self._connect("wms")
            self._assert_layer_present(wms, layer_name, service="wms")
            params = {
                "layers": [layer_name],
                "srs": crs,
                "bbox": bbox,
                "format": output_format,
                "size": (width, height),
                "styles": styles or [""],
            }
            started = time.perf_counter()
            try:
                response = wms.getmap(**params)
                payload = response.read() if hasattr(response, "read") else bytes(response)
                status = getattr(response, "_response", None)
                status_code = getattr(status, "status", "ok") if status is not None else "ok"
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                classified = self._classify(exc, url=url, layer=layer_name)
                log_raw_fetch(
                    url=url,
                    params={**params, "bbox": list(bbox)},
                    status=getattr(exc, "code", None),
                    attempt=attempt,
                    source="bhuvan_wms",
                    layer=layer_name,
                    elapsed_ms=elapsed_ms,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed_ms = (time.perf_counter() - started) * 1000
            log_raw_fetch(
                url=url,
                params={**params, "bbox": list(bbox)},
                status=status_code,
                attempt=attempt,
                source="bhuvan_wms",
                layer=layer_name,
                elapsed_ms=elapsed_ms,
            )
            return self._ensure_raster_bytes(payload, layer_name=layer_name)

        return self._with_retry(operation)

    def get_features(
        self,
        layer_name: str,
        bbox: tuple[float, float, float, float] | None = None,
        crs: str = "EPSG:4326",
    ) -> gpd.GeoDataFrame:
        """WFS GetFeature → GeoDataFrame.

        Latency/reliability: GetFeature over a large bbox can time out or
        return truncated GML. Retry policy: exponential backoff on timeout/5xx
        only.

        TODO(confirm-against-GetCapabilities):
          - Exact WFS `Name` / `TypeName` (often prefixed, e.g. workspace:layer).
          - Advertised outputFormats. GeoJSON is NOT assumed; this client reads
            whatever owslib returns (typically GML) via GeoPandas.
          - MaxFeatures / paging. A national bbox may need WFS 2.0 startIndex
            paging — confirm before ingesting Landslide/flood polygons this way.
            The Landslide Atlas of India is a bulk shapefile, not a live WFS.
        """

        bbox = bbox or INDIA_BBOX
        url = self._require_url("wfs")

        def operation(attempt: int) -> gpd.GeoDataFrame:
            wfs = self._connect("wfs")
            self._assert_layer_present(wfs, layer_name, service="wfs")
            params = {
                "typename": layer_name,
                "bbox": bbox,
                "srsname": crs,
            }
            started = time.perf_counter()
            try:
                response = wfs.getfeature(**params)
                payload = response.read() if hasattr(response, "read") else bytes(response)
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                classified = self._classify(exc, url=url, layer=layer_name)
                log_raw_fetch(
                    url=url,
                    params={**params, "bbox": list(bbox)},
                    status=getattr(exc, "code", None),
                    attempt=attempt,
                    source="bhuvan_wfs",
                    layer=layer_name,
                    elapsed_ms=elapsed_ms,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed_ms = (time.perf_counter() - started) * 1000
            log_raw_fetch(
                url=url,
                params={**params, "bbox": list(bbox)},
                status="ok",
                attempt=attempt,
                source="bhuvan_wfs",
                layer=layer_name,
                elapsed_ms=elapsed_ms,
            )
            return self._gdf_from_wfs_bytes(payload, layer_name=layer_name)

        return self._with_retry(operation)

    def get_features_geojson(
        self,
        layer_name: str,
        bbox: tuple[float, float, float, float] | None = None,
        crs: str = "EPSG:4326",
    ) -> dict[str, Any]:
        """Fetch WFS features and return them directly as a GeoJSON FeatureCollection dict."""
        import json

        gdf = self.get_features(layer_name, bbox=bbox, crs=crs)
        return json.loads(gdf.to_json())

    def get_feature_info_geojson(
        self,
        layer_name: str,
        bbox: tuple[float, float, float, float] | None = None,
        *,
        x: int = 128,
        y: int = 128,
        width: int = 256,
        height: int = 256,
        crs: str = "EPSG:4326",
        info_format: str = "application/json",
        feature_count: int = 50,
    ) -> dict[str, Any]:
        """WMS GetFeatureInfo → GeoJSON dict.

        Useful when standard WFS is disabled on a GeoServer root but WMS
        GetFeatureInfo is active and supports GeoJSON/GML.
        """
        import json

        bbox = bbox or INDIA_BBOX
        url = self._require_url("wms")

        def operation(attempt: int) -> dict[str, Any]:
            wms = self._connect("wms")
            self._assert_layer_present(wms, layer_name, service="wms")
            params = {
                "layers": [layer_name],
                "query_layers": [layer_name],
                "srs": crs,
                "bbox": bbox,
                "size": (width, height),
                "xy": (x, y),
                "info_format": info_format,
                "feature_count": feature_count,
            }
            started = time.perf_counter()
            try:
                if hasattr(wms, "getfeatureinfo"):
                    response = wms.getfeatureinfo(**params)
                    payload = response.read() if hasattr(response, "read") else bytes(response)
                else:
                    raise MalformedResponse("Underlying WMS client does not support getfeatureinfo")
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                classified = self._classify(exc, url=url, layer=layer_name)
                log_raw_fetch(
                    url=url,
                    params={**params, "bbox": list(bbox)},
                    status=getattr(exc, "code", None),
                    attempt=attempt,
                    source="bhuvan_wms_featureinfo",
                    layer=layer_name,
                    elapsed_ms=elapsed_ms,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed_ms = (time.perf_counter() - started) * 1000
            log_raw_fetch(
                url=url,
                params={**params, "bbox": list(bbox)},
                status="ok",
                attempt=attempt,
                source="bhuvan_wms_featureinfo",
                layer=layer_name,
                elapsed_ms=elapsed_ms,
            )
            trimmed = payload.lstrip()
            if trimmed.startswith(b"{"):
                try:
                    return json.loads(payload.decode("utf-8"))
                except Exception as exc:
                    raise MalformedResponse(f"Could not parse JSON from GetFeatureInfo: {exc}") from exc
            if trimmed.startswith((b"<?xml", b"<serviceexception", b"<html", b"<!doctype")):
                snippet = payload[:500].decode("utf-8", errors="replace")
                if any(token in snippet.lower() for token in ("unauthor", "login", "forbidden")):
                    raise AuthFailure(f"GetFeatureInfo auth error: {snippet}")
                try:
                    gdf = gpd.read_file(BytesIO(payload))
                    return json.loads(gdf.to_json())
                except Exception as exc:
                    raise MalformedResponse(f"GetFeatureInfo returned non-JSON error body: {snippet}") from exc
            raise MalformedResponse(f"Unexpected response format from GetFeatureInfo: {payload[:200]!r}")

        return self._with_retry(operation)

    def persist_layer_bytes(
        self,
        payload: bytes,
        *,
        layer_name: str,
        bbox: tuple[float, float, float, float],
        effective_date: datetime,
        relative_name: str | None = None,
    ) -> IngestedRecord:
        """Write GetMap bytes into the private landing zone and return a tile record.

        WMS rasters are not point events: one record per (layer, bbox, date).
        `raw_payload` stores the private file path, never the raster bytes.
        """

        landing = self._settings.gis_landing_zone
        safe_layer = layer_name.replace("/", "_").replace(":", "_")
        date_stamp = effective_date.date().isoformat()
        filename = relative_name or f"{safe_layer}_{date_stamp}.tif"
        dest = Path(landing) / "bhuvan" / filename
        stored = write_private_bytes(dest, payload, settings=self._settings)
        geom = box(*bbox)
        ingest_time = datetime.now(timezone.utc)
        return IngestedRecord(
            event_id=raster_tile_event_id(layer_name, bbox, effective_date),
            source="bhuvan_wms",
            hazard_type=layer_name,
            geometry=geom,
            h3_cell=None,
            district_id=None,
            event_time=effective_date,
            ingest_time=ingest_time,
            severity_raw=None,
            severity_normalized=None,
            confidence=None,
            resolution_tier=ResolutionTier.POLYGON,
            raw_payload={"path": str(stored), "kind": "raster", "layer": layer_name, "bbox": list(bbox)},
        )

    def persist_features_geojson(
        self,
        gdf_or_geojson: gpd.GeoDataFrame | dict[str, Any],
        *,
        layer_name: str,
        effective_date: datetime,
        relative_name: str | None = None,
    ) -> IngestedRecord:
        """Write GeoJSON features into the private landing zone and return a record."""
        import json

        landing = self._settings.gis_landing_zone
        safe_layer = layer_name.replace("/", "_").replace(":", "_")
        date_stamp = effective_date.date().isoformat()
        filename = relative_name or f"{safe_layer}_{date_stamp}.geojson"
        dest = Path(landing) / "bhuvan" / filename
        dest = assert_private_destination(dest, settings=self._settings)

        if isinstance(gdf_or_geojson, gpd.GeoDataFrame):
            geojson_dict = json.loads(gdf_or_geojson.to_json())
            geom = gdf_or_geojson.unary_union if not gdf_or_geojson.empty else box(*INDIA_BBOX)
        else:
            geojson_dict = gdf_or_geojson
            geom = box(*INDIA_BBOX)

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(geojson_dict, indent=2) + "\n", encoding="utf-8")
        ingest_time = datetime.now(timezone.utc)
        return IngestedRecord(
            event_id=raster_tile_event_id(layer_name, INDIA_BBOX, effective_date),
            source="bhuvan_vector",
            hazard_type=layer_name,
            geometry=geom,
            h3_cell=None,
            district_id=None,
            event_time=effective_date,
            ingest_time=ingest_time,
            severity_raw=None,
            severity_normalized=None,
            confidence=None,
            resolution_tier=ResolutionTier.POLYGON,
            raw_payload={"path": str(dest), "kind": "geojson", "layer": layer_name},
        )

    def _connect(self, service: ServiceKind) -> Any:
        url = self._require_url(service)
        if service == "wms" and self._wms is not None:
            return self._wms
        if service == "wfs" and self._wfs is not None:
            return self._wfs

        def operation(attempt: int) -> Any:
            started = time.perf_counter()
            factory = self._wms_factory if service == "wms" else self._wfs_factory
            version = self.config.wms_version if service == "wms" else self.config.wfs_version
            kwargs: dict[str, Any] = {
                "version": version,
                "timeout": self.config.timeout_seconds,
            }
            if self.config.username:
                kwargs["username"] = self.config.username
            if self.config.password:
                kwargs["password"] = self.config.password
            try:
                client = factory(url, **kwargs)
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                classified = self._classify(exc, url=url, layer=None)
                log_raw_fetch(
                    url=url,
                    params={"request": "GetCapabilities", "version": version},
                    status=getattr(exc, "code", None),
                    attempt=attempt,
                    source=f"bhuvan_{service}",
                    elapsed_ms=elapsed_ms,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed_ms = (time.perf_counter() - started) * 1000
            log_raw_fetch(
                url=url,
                params={"request": "GetCapabilities", "version": version},
                status="ok",
                attempt=attempt,
                source=f"bhuvan_{service}",
                elapsed_ms=elapsed_ms,
            )
            return client

        client = self._with_retry(operation)
        if service == "wms":
            self._wms = client
        else:
            self._wfs = client
        return client

    def _require_url(self, service: ServiceKind) -> str:
        url = self.config.wms_base_url if service == "wms" else self.config.wfs_base_url
        if not url or not url.startswith(("http://", "https://")):
            raise ConfigError(
                f"Bhuvan {service.upper()} base URL is not set. Put the real "
                f"GetCapabilities URL in config/BHUVAN_{service.upper()}_BASE_URL "
                f"(portal homepages are not OGC endpoints)."
            )
        return url

    def _assert_layer_present(self, svc: Any, layer_name: str, *, service: ServiceKind) -> None:
        contents = getattr(svc, "contents", None)
        if contents is None:
            return
        if layer_name not in contents:
            raise LayerNotFound(
                f"{service.upper()} layer {layer_name!r} is not in GetCapabilities. "
                f"Call list_available_layers({service!r}) and use an advertised name."
            )

    def _with_retry(self, operation: Callable[[int], Any]) -> Any:
        last: Exception | None = None
        total_attempts = self.config.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return operation(attempt)
            except (AuthFailure, LayerNotFound, MalformedResponse, ConfigError):
                raise
            except (NetworkTimeout, ServerUnavailable) as exc:
                last = exc
                if attempt >= total_attempts:
                    raise
                delay = self.config.retry_base_seconds * (2 ** (attempt - 1))
                self._sleep(delay)
        assert last is not None
        raise last

    def _classify(self, exc: Exception, *, url: str, layer: str | None) -> Exception:
        if isinstance(
            exc,
            (AuthFailure, LayerNotFound, MalformedResponse, NetworkTimeout, ServerUnavailable, ConfigError),
        ):
            return exc

        if isinstance(exc, OwsServiceException):
            text = str(exc).lower()
            if any(token in text for token in ("unauthor", "forbidden", "not authenticated", "login")):
                return AuthFailure(f"Bhuvan auth failed for {url}: {exc}")
            if any(token in text for token in ("layer not defined", "invalid layer", "unknown layer", "not found")):
                return LayerNotFound(f"Bhuvan layer {layer!r} rejected by server: {exc}")
            return MalformedResponse(f"Bhuvan OGC exception for {layer!r}: {exc}")

        if isinstance(exc, HTTPError):
            if exc.code in (401, 403):
                return AuthFailure(f"HTTP {exc.code} from {url} (check BHUVAN_USERNAME/PASSWORD)")
            if exc.code == 404:
                return LayerNotFound(f"HTTP 404 from {url} for layer {layer!r}")
            if exc.code >= 500:
                return ServerUnavailable(f"HTTP {exc.code} from {url}")
            return MalformedResponse(f"HTTP {exc.code} from {url}: {exc}")

        if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError):
            return NetworkTimeout(f"Timeout talking to {url}: {exc}")

        if isinstance(exc, URLError):
            reason = exc.reason
            if isinstance(reason, socket.timeout) or isinstance(reason, TimeoutError):
                return NetworkTimeout(f"Timeout talking to {url}: {exc}")
            if "timed out" in str(exc).lower() or "timeout" in str(reason).lower():
                return NetworkTimeout(f"Timeout talking to {url}: {exc}")
            return ServerUnavailable(f"Connection error talking to {url}: {exc}")

        if isinstance(exc, socket.timeout):
            return NetworkTimeout(f"Timeout talking to {url}: {exc}")

        if isinstance(exc, ParseError):
            return MalformedResponse(f"Malformed XML from {url}: {exc}")

        text = str(exc).lower()
        if "timed out" in text or "timeout" in text:
            return NetworkTimeout(f"Timeout talking to {url}: {exc}")
        if "unauthor" in text or "forbidden" in text:
            return AuthFailure(f"Auth failed for {url}: {exc}")
        return ServerUnavailable(f"Bhuvan request failed for {url}: {exc}")

    def _ensure_raster_bytes(self, payload: bytes, *, layer_name: str) -> bytes:
        if not payload:
            raise MalformedResponse(f"Empty GetMap body for layer {layer_name!r}")
        head = payload.lstrip().lower()
        if head.startswith(
            (
                b"<?xml",
                b"<serviceexception",
                b"<ows:exception",
                b"<exceptionreport",
                b"<html",
                b"<!doctype",
                b"<?",
                b"<soap",
            )
        ):
            snippet = payload[:500].decode("utf-8", errors="replace")
            lowered = snippet.lower()
            if any(token in lowered for token in ("unauthor", "login", "forbidden", "access denied", "credential")):
                raise AuthFailure(f"GetMap returned an auth/HTML body for {layer_name!r}: {snippet}")
            if any(
                token in lowered
                for token in ("layer not defined", "unknown layer", "invalid layer", "layer does not exist", "not found")
            ):
                raise LayerNotFound(f"GetMap OGC exception for {layer_name!r}: {snippet}")
            raise MalformedResponse(
                f"GetMap for {layer_name!r} returned XML/HTML instead of a raster: {snippet}"
            )
        return payload

    def _gdf_from_wfs_bytes(self, payload: bytes, *, layer_name: str) -> gpd.GeoDataFrame:
        if not payload:
            raise MalformedResponse(f"Empty GetFeature body for layer {layer_name!r}")
        head = payload.lstrip().lower()
        if head.startswith(
            (b"<html", b"<!doctype", b"<serviceexception", b"<ows:exception", b"<exceptionreport")
        ):
            snippet = payload[:500].decode("utf-8", errors="replace")
            lowered = snippet.lower()
            if any(token in lowered for token in ("unauthor", "login", "forbidden", "access denied", "credential")):
                raise AuthFailure(f"WFS returned an auth/login page for {layer_name!r}: {snippet}")
            if any(
                token in lowered
                for token in ("typenamenotfound", "unknown type", "invalid layer", "not defined", "not found")
            ):
                raise LayerNotFound(f"WFS layer {layer_name!r} not found: {snippet}")
            if head.startswith((b"<html", b"<!doctype")):
                raise MalformedResponse(f"WFS returned HTML instead of GML/GeoJSON for {layer_name!r}: {snippet}")
        try:
            gdf = gpd.read_file(BytesIO(payload))
        except Exception as exc:
            snippet = payload[:500].decode("utf-8", errors="replace")
            lowered = snippet.lower()
            if any(token in lowered for token in ("unauthor", "login", "forbidden", "access denied")):
                raise AuthFailure(f"WFS auth error for {layer_name!r}: {snippet}") from exc
            if any(
                token in lowered
                for token in ("typenamenotfound", "unknown type", "invalid layer", "not defined", "not found")
            ):
                raise LayerNotFound(f"WFS layer {layer_name!r} not found: {snippet}") from exc
            raise MalformedResponse(
                f"Could not parse WFS payload for {layer_name!r} as vector data: {exc}; body starts: {snippet}"
            ) from exc
        return gdf
