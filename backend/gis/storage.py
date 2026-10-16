"""Private landing-zone writes for license-restricted geo payloads.

LICENSING / REDISTRIBUTION BOUNDARY
-----------------------------------
Several Bhuvan/NRSC (ISRO) thematic and disaster layers restrict redistribution
of raw tiles and vector extracts. Raw fetched bytes and portal downloads MUST
be written only to the internal/private landing zone configured via
`GIS_LANDING_ZONE`. Never write raw Bhuvan rasters, WFS extracts, or atlas
shapefiles under `GIS_PUBLIC_ZONE` or any other path that could be served by
a CDN, static site, or public object-store prefix.
"""

from __future__ import annotations

from pathlib import Path

from gis.config import Settings, load_settings
from gis.exceptions import StoragePolicyError


def resolve_landing_zone(settings: Settings | None = None) -> Path:
    cfg = settings or load_settings()
    zone = Path(cfg.gis_landing_zone).expanduser().resolve()
    zone.mkdir(parents=True, exist_ok=True)
    return zone


def assert_private_destination(path: Path, settings: Settings | None = None) -> Path:
    """Refuse writes whose resolved path is not inside the private landing zone.

    This is the storage-boundary check. Call it immediately before any write
    of raw Bhuvan/NRSC bytes.
    """

    cfg = settings or load_settings()
    dest = path.expanduser().resolve()
    landing = Path(cfg.gis_landing_zone).expanduser().resolve()
    public = Path(cfg.gis_public_zone).expanduser().resolve()

    try:
        dest.relative_to(landing)
    except ValueError as exc:
        raise StoragePolicyError(
            f"Refusing to write raw geo data outside the private landing zone. "
            f"destination={dest} landing_zone={landing}"
        ) from exc

    try:
        dest.relative_to(public)
        raise StoragePolicyError(
            f"Refusing to write raw Bhuvan/NRSC data into the public zone. "
            f"destination={dest} public_zone={public}"
        )
    except ValueError:
        pass

    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def write_private_bytes(path: Path, payload: bytes, settings: Settings | None = None) -> Path:
    """Write raw fetched bytes into the private landing zone only."""

    dest = assert_private_destination(path, settings=settings)
    dest.write_bytes(payload)
    return dest
