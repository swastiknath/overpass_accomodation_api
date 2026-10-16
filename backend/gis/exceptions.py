"""Typed failures so orchestration can retry, alert, or skip without parsing strings.

Hierarchy (post-refactor):
    GisError
    ├── ConfigError          — bad config, missing URL/keys
    ├── AuthFailure          — 401/403 / OAuth token failure (any source)
    ├── NetworkTimeout       — socket/read timeout (safe to retry)
    ├── ServerUnavailable    — 5xx / connection reset (safe to retry)
    ├── MalformedResponse    — body not what was advertised
    ├── StoragePolicyError   — write outside private landing zone
    ├── UnsupportedDataset   — unrecognised file format
    ├── ConnectorError       — base for source-specific connector errors
    └── BhuvanError          — backwards compat (Bhuvan-specific code can still catch this)
          └── LayerNotFound  — OGC layer absent from GetCapabilities
"""


class GisError(Exception):
    """Base error for the entire India travel-safety pipeline."""


class ConfigError(GisError):
    """Missing or invalid client configuration (URL, credentials, storage path)."""


class AuthFailure(GisError):
    """HTTP 401/403, OGC auth challenge, or OAuth token failure. Do not retry without new credentials."""


class NetworkTimeout(GisError):
    """Socket/read timeout talking to an external service. Safe to retry with backoff."""


class ServerUnavailable(GisError):
    """HTTP 5xx or connection reset from a remote service. Safe to retry with backoff."""


class MalformedResponse(GisError):
    """Body is not the advertised format (HTML instead of raster, truncated XML, OGC exception)."""


class StoragePolicyError(GisError):
    """Attempt to write license-restricted raw data outside the private landing zone."""


class UnsupportedDataset(GisError):
    """File is not a shapefile, GeoTIFF, or GeoPackage, or is an HTML error page."""


class ConnectorError(GisError):
    """Base error for data-connector-specific failures (ACLED, GDACS, FIRMS, etc.)."""


# ---------------------------------------------------------------------------
# Backwards compatibility — existing BhuvanClient code catches BhuvanError
# ---------------------------------------------------------------------------

class BhuvanError(GisError):
    """Base error for Bhuvan/NRSC OGC clients (backwards compat)."""


class LayerNotFound(BhuvanError):
    """Requested layer is absent from GetCapabilities. Skip or fix config; do not retry."""
