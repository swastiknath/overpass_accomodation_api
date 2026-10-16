"""Ingest portal-driven bulk files (Landslide Atlas, Bhukosh, Bhoonidhi orders).

These sources are not query APIs. The operator supplies a download URL or a
local path after exporting from the portal. This module validates the payload
is a real spatial file (not an HTML error page saved with a .shp/.tif
extension) and copies it into the private landing zone with sidecar metadata.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gis.config import Settings, load_settings
from gis.exceptions import (
    AuthFailure,
    MalformedResponse,
    NetworkTimeout,
    ServerUnavailable,
    UnsupportedDataset,
)
from gis.logging_utils import log_raw_fetch
from gis.storage import assert_private_destination, resolve_landing_zone

SHAPEFILE_MAGIC = 9994  # big-endian file code at byte 0 of .shp
TIFF_LE = b"II*\x00"
TIFF_BE = b"MM\x00*"
GPKG_HEADER = b"SQLite format 3"
ZIP_MAGIC = b"PK\x03\x04"
HTML_PREFIXES = (b"<!doctype html", b"<html", b"<head", b"<body")

SUPPORTED_KINDS = ("shapefile", "geotiff", "gpkg", "shapefile_zip")


class BulkDownloader:
    def __init__(self, settings: Settings | None = None, *, sleep=time.sleep) -> None:
        self.settings = settings or load_settings()
        self._sleep = sleep

    def ingest(
        self,
        source: str | Path,
        *,
        effective_date: date | datetime,
        source_url: str,
        dest_name: str | None = None,
    ) -> Path:
        """Copy a local file or download a URL into the private landing zone.

        Latency/reliability: portal downloads (Bhuvan Disaster, NFVAS, FEWS,
        Bhoonidhi, Bhukosh) are slow, often wrap the file in a session cookie,
        and commonly return an HTML "login / quota / try again" page. Retry
        policy for HTTP URLs: exponential backoff on timeout and 5xx only
        (`BHUVAN_MAX_RETRIES` / `BHUVAN_RETRY_BASE_SECONDS`). Auth pages and
        HTML-masquerading-as-data are not retried.

        `effective_date` and `source_url` are required and written to a
        `.meta.json` sidecar next to the stored file.
        """

        if isinstance(effective_date, datetime):
            effective = effective_date.date()
        else:
            effective = effective_date

        raw, origin = self._load_bytes(source)
        kind = classify_spatial_payload(raw, source_hint=str(source))
        landing = resolve_landing_zone(self.settings)
        filename = dest_name or _default_filename(source, kind)
        dest = landing / "bulk" / filename
        dest = assert_private_destination(dest, settings=self.settings)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)

        sidecar = dest.with_suffix(dest.suffix + ".meta.json")
        metadata = {
            "effective_date": effective.isoformat(),
            "source_url": source_url,
            "origin": origin,
            "kind": kind,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "path": str(dest),
        }
        sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return dest

    def ingest_directory(
        self,
        directory: str | Path,
        *,
        effective_date: date | datetime,
        source_url: str,
    ) -> Path:
        """Ingest a shapefile *set* (.shp + .shx + .dbf) from a local folder."""

        directory = Path(directory)
        shp = _find_shp(directory)
        raw = shp.read_bytes()
        classify_spatial_payload(raw, source_hint=str(shp))
        _assert_sidecar_components(shp)

        landing = resolve_landing_zone(self.settings)
        dest_dir = landing / "bulk" / directory.name
        dest_dir = assert_private_destination(dest_dir / ".keep", settings=self.settings).parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        for member in directory.iterdir():
            if member.suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"}:
                shutil.copy2(member, dest_dir / member.name)

        if isinstance(effective_date, datetime):
            effective = effective_date.date()
        else:
            effective = effective_date
        sidecar = dest_dir / f"{shp.stem}.meta.json"
        sidecar.write_text(
            json.dumps(
                {
                    "effective_date": effective.isoformat(),
                    "source_url": source_url,
                    "origin": str(directory),
                    "kind": "shapefile",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "path": str(dest_dir / shp.name),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return dest_dir / shp.name

    def _load_bytes(self, source: str | Path) -> tuple[bytes, str]:
        text = str(source)
        if text.startswith(("http://", "https://")):
            return self._download(text), text
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Bulk source is not a file: {path}")
        return path.read_bytes(), str(path.resolve())

    def _download(self, url: str) -> bytes:
        """HTTP GET with backoff. See `ingest` docstring for retry policy."""

        total = self.settings.bhuvan_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, total + 1):
            started = time.perf_counter()
            request = Request(url, headers={"User-Agent": "india-travel-safety-gis/0.1 (research; internal)"})
            if self.settings.bhuvan_username and "nrsc.gov.in" in url:
                # Basic auth only for NRSC hosts when creds are configured.
                import base64

                token = base64.b64encode(
                    f"{self.settings.bhuvan_username}:{self.settings.bhuvan_password or ''}".encode()
                ).decode("ascii")
                request.add_header("Authorization", f"Basic {token}")
            try:
                with urlopen(request, timeout=self.settings.bhuvan_timeout_seconds) as response:
                    payload = response.read()
                    status = getattr(response, "status", 200)
                log_raw_fetch(
                    url=url,
                    params={},
                    status=status,
                    attempt=attempt,
                    source="bulk_downloader",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                )
                return payload
            except Exception as exc:
                classified = _classify_download_error(exc, url)
                log_raw_fetch(
                    url=url,
                    params={},
                    status=getattr(exc, "code", None),
                    attempt=attempt,
                    source="bulk_downloader",
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                if isinstance(classified, (NetworkTimeout, ServerUnavailable)) and attempt < total:
                    last_error = classified
                    delay = self.settings.bhuvan_retry_base_seconds * (2 ** (attempt - 1))
                    self._sleep(delay)
                    continue
                raise classified from exc
        assert last_error is not None
        raise last_error


def classify_spatial_payload(payload: bytes, *, source_hint: str = "") -> str:
    """Return kind or raise if this looks like an HTML error page / non-spatial blob."""

    if not payload:
        raise UnsupportedDataset("Empty download")

    head = payload[:64]
    lowered = payload.lstrip().lower()
    if lowered.startswith(HTML_PREFIXES) or b"<html" in payload[:512].lower():
        raise UnsupportedDataset(
            f"Payload from {source_hint!r} is HTML, not spatial data "
            "(typical when a portal session expired or the 'download' was an error page)."
        )

    if head.startswith(TIFF_LE) or head.startswith(TIFF_BE):
        return "geotiff"
    if head.startswith(GPKG_HEADER) or payload[:16].startswith(GPKG_HEADER):
        return "gpkg"
    if head.startswith(ZIP_MAGIC):
        return _classify_zip(payload, source_hint=source_hint)
    if _looks_like_shp(payload):
        return "shapefile"

    suffix = Path(source_hint).suffix.lower()
    raise UnsupportedDataset(
        f"Payload from {source_hint!r} is not a shapefile, GeoTIFF, GeoPackage, or "
        f"zipped shapefile (suffix={suffix!r}, first_bytes={head[:16]!r})."
    )


def _classify_zip(payload: bytes, *, source_hint: str) -> str:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as zf:
            names = [n.lower() for n in zf.namelist()]
    except zipfile.BadZipFile as exc:
        raise UnsupportedDataset(f"Zip from {source_hint!r} is corrupt: {exc}") from exc
    if any(name.endswith(".shp") for name in names):
        return "shapefile_zip"
    if any(name.endswith((".tif", ".tiff")) for name in names):
        return "geotiff"
    if any(name.endswith(".gpkg") for name in names):
        return "gpkg"
    raise UnsupportedDataset(
        f"Zip from {source_hint!r} has no .shp/.tif/.gpkg members: {names[:20]}"
    )


def _looks_like_shp(payload: bytes) -> bool:
    if len(payload) < 100:
        return False
    code = int.from_bytes(payload[0:4], "big")
    return code == SHAPEFILE_MAGIC


def _find_shp(directory: Path) -> Path:
    matches = list(directory.glob("*.shp"))
    if not matches:
        raise UnsupportedDataset(f"No .shp in {directory}")
    return matches[0]


def _assert_sidecar_components(shp: Path) -> None:
    missing = [ext for ext in (".shx", ".dbf") if not shp.with_suffix(ext).exists()]
    if missing:
        raise UnsupportedDataset(f"Shapefile {shp} is missing required sidecars: {missing}")


def _default_filename(source: str | Path, kind: str) -> str:
    name = Path(str(source).split("?")[0]).name
    if name and name not in {"", "/", "."}:
        return name
    ext = {"shapefile": ".shp", "geotiff": ".tif", "gpkg": ".gpkg", "shapefile_zip": ".zip"}[kind]
    return f"bulk_download{ext}"


def _classify_download_error(exc: Exception, url: str) -> Exception:
    if isinstance(exc, HTTPError):
        if exc.code in (401, 403):
            return AuthFailure(f"HTTP {exc.code} downloading {url}")
        if exc.code >= 500:
            return ServerUnavailable(f"HTTP {exc.code} downloading {url}")
        return MalformedResponse(f"HTTP {exc.code} downloading {url}")
    if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
        return NetworkTimeout(f"Timeout downloading {url}: {exc}")
    if isinstance(exc, URLError):
        if "timed out" in str(exc).lower():
            return NetworkTimeout(f"Timeout downloading {url}: {exc}")
        return ServerUnavailable(f"Connection error downloading {url}: {exc}")
    return ServerUnavailable(f"Download failed for {url}: {exc}")
