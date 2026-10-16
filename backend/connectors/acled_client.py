"""ACLED (Armed Conflict Location & Event Data) client.

Scope: political violence, protests, riots, strategic developments in India.
NOT general crime or natural disasters — those have their own connectors.

Auth: ACLED has migrated to OAuth token-based authentication for programmatic
access. Tokens are acquired via `_get_token()`, cached, and auto-refreshed.
Credentials (email + password) come from config, never hardcoded.

Cadence: weekly batch is sufficient. Do not poll aggressively — ACLED updates
at most daily and prefers bulk-download patterns.

ACLED's own geocoding is generally more reliable than GDELT's — coordinates
are NOT discarded or downweighted.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from gis.config import Settings, load_settings
from gis.exceptions import AuthFailure, ConfigError, ConnectorError
from gis.schema import IngestedRecord, ResolutionTier

from connectors.base import BaseConnector


class ACLEDClient(BaseConnector):
    """Fetch conflict & political violence events from ACLED for India."""

    SOURCE_NAME = "acled"

    # ACLED event-type severity mapping (higher = more severe)
    _SEVERITY_MAP: dict[str, float] = {
        "Battles": 0.9,
        "Violence against civilians": 0.95,
        "Explosions/Remote violence": 0.85,
        "Riots": 0.7,
        "Protests": 0.4,
        "Strategic developments": 0.3,
    }

    def __init__(self, settings: Settings | None = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # ── OAuth token management ────────────────────────────────────────────

    def _get_token(self) -> str:
        """Acquire (or return cached) OAuth access token from ACLED.

        Token is refreshed when it's within 60 seconds of expiry.
        """
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        email = self._settings.acled_email
        password = self._settings.acled_password
        if not email or not password:
            raise ConfigError(
                "ACLED credentials not configured. Set ACLED_EMAIL and "
                "ACLED_PASSWORD in .env (register at acleddata.com)."
            )

        token_url = f"{self._settings.acled_api_url.rstrip('/')}/auth/token"

        def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = self._http_client.post(
                    token_url,
                    data={"email": email, "password": password},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=token_url)
                self._log_fetch(
                    url=token_url,
                    params={"email": email},
                    status=getattr(exc, "response", None) and exc.response.status_code,
                    attempt=attempt,
                    elapsed_ms=elapsed,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(
                url=token_url,
                params={"email": email},
                status="ok",
                attempt=attempt,
                elapsed_ms=elapsed,
            )
            return data

        data = self._with_retry(operation)

        if "access_token" not in data:
            raise AuthFailure(f"ACLED token response missing access_token: {data}")

        self._token = data["access_token"]
        # Default expiry: 1 hour if not provided
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + float(expires_in)
        return self._token

    # ── Async token acquisition ───────────────────────────────────────────

    async def _get_token_async(self) -> str:
        """Async variant of _get_token."""
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        email = self._settings.acled_email
        password = self._settings.acled_password
        if not email or not password:
            raise ConfigError(
                "ACLED credentials not configured. Set ACLED_EMAIL and "
                "ACLED_PASSWORD in .env (register at acleddata.com)."
            )

        token_url = f"{self._settings.acled_api_url.rstrip('/')}/auth/token"

        async def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.post(
                    token_url,
                    data={"email": email, "password": password},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=token_url)
                self._log_fetch(
                    url=token_url,
                    params={"email": email},
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt,
                    elapsed_ms=elapsed,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(
                url=token_url,
                params={"email": email},
                status="ok",
                attempt=attempt,
                elapsed_ms=elapsed,
            )
            return data

        data = await self._with_retry_async(operation)

        if "access_token" not in data:
            raise AuthFailure(f"ACLED token response missing access_token: {data}")

        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + float(expires_in)
        return self._token

    # ── Event fetching ────────────────────────────────────────────────────

    def get_events(
        self,
        bbox_or_country: str | tuple[float, float, float, float] = "India",
        start_date: datetime | str | None = None,
        end_date: datetime | str | None = None,
        event_types: list[str] | None = None,
    ) -> list[IngestedRecord]:
        """Fetch conflict/political-violence events from ACLED.

        Parameters
        ----------
        bbox_or_country : str or (lon_min, lat_min, lon_max, lat_max)
            Country name or bounding box.
        start_date, end_date : datetime or ISO string
            Date range filter.
        event_types : list of str, optional
            Filter by ACLED event_type (e.g. ["Battles", "Protests"]).

        Returns
        -------
        list[IngestedRecord]
            Records in the shared schema with hazard_type="conflict".
        """
        token = self._get_token()
        api_url = f"{self._settings.acled_api_url.rstrip('/')}/acled/read"

        params: dict[str, Any] = {
            "limit": 5000,
        }

        if isinstance(bbox_or_country, str):
            params["country"] = bbox_or_country
        else:
            lon_min, lat_min, lon_max, lat_max = bbox_or_country
            params["latitude"] = f"{lat_min}|{lat_max}"
            params["longitude"] = f"{lon_min}|{lon_max}"

        if start_date:
            d = start_date if isinstance(start_date, str) else start_date.strftime("%Y-%m-%d")
            params["event_date"] = d
            params["event_date_where"] = ">="
        if end_date:
            d = end_date if isinstance(end_date, str) else end_date.strftime("%Y-%m-%d")
            if "event_date" in params:
                params["event_date"] = f"{params['event_date']}|{d}"
                params["event_date_where"] = "BETWEEN"
            else:
                params["event_date"] = d
                params["event_date_where"] = "<="

        if event_types:
            params["event_type"] = "|".join(event_types)

        headers = {"Authorization": f"Bearer {token}"}

        def operation(attempt: int) -> list[dict[str, Any]]:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(api_url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=api_url)
                self._log_fetch(
                    url=api_url,
                    params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt,
                    elapsed_ms=elapsed,
                    error_type=type(classified).__name__,
                    message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(
                url=api_url,
                params=params,
                status="ok",
                attempt=attempt,
                elapsed_ms=elapsed,
            )
            return data.get("data", [])

        raw_events = self._with_retry(operation)
        self._record_success()
        return self._to_records(raw_events)

    async def get_events_async(
        self,
        bbox_or_country: str | tuple[float, float, float, float] = "India",
        start_date: datetime | str | None = None,
        end_date: datetime | str | None = None,
        event_types: list[str] | None = None,
    ) -> list[IngestedRecord]:
        """Async variant of get_events."""
        token = await self._get_token_async()
        api_url = f"{self._settings.acled_api_url.rstrip('/')}/acled/read"

        params: dict[str, Any] = {"limit": 5000}

        if isinstance(bbox_or_country, str):
            params["country"] = bbox_or_country
        else:
            lon_min, lat_min, lon_max, lat_max = bbox_or_country
            params["latitude"] = f"{lat_min}|{lat_max}"
            params["longitude"] = f"{lon_min}|{lon_max}"

        if start_date:
            d = start_date if isinstance(start_date, str) else start_date.strftime("%Y-%m-%d")
            params["event_date"] = d
            params["event_date_where"] = ">="
        if end_date:
            d = end_date if isinstance(end_date, str) else end_date.strftime("%Y-%m-%d")
            if "event_date" in params:
                params["event_date"] = f"{params['event_date']}|{d}"
                params["event_date_where"] = "BETWEEN"
            else:
                params["event_date"] = d
                params["event_date_where"] = "<="

        if event_types:
            params["event_type"] = "|".join(event_types)

        headers = {"Authorization": f"Bearer {token}"}

        async def operation(attempt: int) -> list[dict[str, Any]]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(api_url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=api_url)
                self._log_fetch(
                    url=api_url, params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=api_url, params=params, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return data.get("data", [])

        raw_events = await self._with_retry_async(operation)
        self._record_success()
        return self._to_records(raw_events)

    # ── Record conversion ─────────────────────────────────────────────────

    def _to_records(self, raw_events: list[dict[str, Any]]) -> list[IngestedRecord]:
        """Convert raw ACLED JSON records to IngestedRecord instances.

        LICENSING / REDISTRIBUTION BOUNDARY
        ------------------------------------
        ACLED data is subject to ACLED's Terms of Use & Attribution Requirements.
        Raw ACLED records must NOT be redistributed, published, or exposed via
        public APIs. Only derived/aggregated outputs are API-servable. Store raw
        records in the private landing zone only, same policy as Bhuvan/NRSC data.
        See: https://acleddata.com/terms-of-use/
        """
        from shapely.geometry import Point

        records: list[IngestedRecord] = []
        ingest_time = datetime.now(timezone.utc)

        for event in raw_events:
            try:
                lat = float(event.get("latitude", 0))
                lon = float(event.get("longitude", 0))
                if lat == 0 and lon == 0:
                    continue

                event_type = event.get("event_type", "Unknown")
                fatalities = int(event.get("fatalities", 0))

                # Severity from fatalities when available, else from event-type mapping
                severity_raw: float | int
                if fatalities > 0:
                    severity_raw = fatalities
                else:
                    severity_raw = self._SEVERITY_MAP.get(event_type, 0.5)

                event_date_str = event.get("event_date", "")
                try:
                    event_time = datetime.strptime(event_date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError):
                    event_time = ingest_time

                event_id_raw = event.get("event_id_cnty") or event.get("data_id", "")
                event_id = f"acled:{hashlib.sha256(str(event_id_raw).encode()).hexdigest()[:16]}"

                record = IngestedRecord(
                    event_id=event_id,
                    source="acled",
                    hazard_type="conflict",
                    geometry=Point(lon, lat),
                    event_time=event_time,
                    ingest_time=ingest_time,
                    severity_raw=severity_raw,
                    confidence=0.85,  # ACLED's geocoding is generally reliable
                    resolution_tier=ResolutionTier.POINT,
                    raw_payload={
                        "event_type": event_type,
                        "sub_event_type": event.get("sub_event_type"),
                        "fatalities": fatalities,
                        "actor1": event.get("actor1"),
                        "actor2": event.get("actor2"),
                        "admin1": event.get("admin1"),
                        "admin2": event.get("admin2"),
                        "admin3": event.get("admin3"),
                        "location": event.get("location"),
                        "notes": event.get("notes"),
                        "source": event.get("source"),
                    },
                )
                records.append(record)
            except Exception:
                # Skip malformed individual records, don't fail the whole batch
                continue

        return records
