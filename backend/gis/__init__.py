"""GIS ingestion helpers for the India travel-safety pipeline."""

from gis.bhuvan_client import BhuvanClient, BhuvanClientConfig
from gis.bulk_downloader import BulkDownloader
from gis.config import INDIA_BBOX, Settings, load_settings
from gis.exceptions import (
    AuthFailure,
    BhuvanError,
    LayerNotFound,
    MalformedResponse,
    NetworkTimeout,
    ServerUnavailable,
)
from gis.harmonize import reproject_to_wgs84, snap_to_admin_boundary, snap_to_h3, to_geojson
from gis.schema import IngestedRecord, ResolutionTier

__all__ = [
    "INDIA_BBOX",
    "AuthFailure",
    "BhuvanClient",
    "BhuvanClientConfig",
    "BhuvanError",
    "BulkDownloader",
    "IngestedRecord",
    "LayerNotFound",
    "MalformedResponse",
    "NetworkTimeout",
    "ResolutionTier",
    "ServerUnavailable",
    "Settings",
    "load_settings",
    "reproject_to_wgs84",
    "snap_to_admin_boundary",
    "snap_to_h3",
    "to_geojson",
]
