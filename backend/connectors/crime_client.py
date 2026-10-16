"""data.gov.in OGD API client for district-wise IPC crime statistics.

Scope: annual crime-rate data from data.gov.in's Open Government Data platform.
This is a SLOW-MOVING, LOW-CADENCE (annual) prior layer, not real-time.

The actual data year is always included in the response so downstream code
never unknowingly treats stale data as current.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from gis.config import Settings, load_settings
from gis.exceptions import ConfigError, ConnectorError
from gis.schema import IngestedRecord, ResolutionTier

from connectors.base import BaseConnector


class CrimeClient(BaseConnector):
    """Fetch district-wise IPC crime statistics from data.gov.in OGD API."""

    SOURCE_NAME = "crime_datagov"

    # data.gov.in OGD API base
    DATAGOV_API_URL = "https://api.data.gov.in/resource"

    # Known resource IDs for IPC crime datasets on data.gov.in
    # These may change if data.gov.in restructures — treat as config candidates.
    _CRIME_RESOURCE_IDS: dict[str, str] = {
        "district_ipc": "cc974b79-504f-45e5-8930-3ae1ad3225d5",
    }

    def __init__(self, settings: Settings | None = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)

    def get_district_crime_rate(
        self,
        district_id: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Fetch crime rate data for a district.

        Parameters
        ----------
        district_id : str
            District name or ID (matched against data.gov.in's district field).
        year : int, optional
            Specific year to query. If None, returns most recent available year.

        Returns
        -------
        dict with keys:
            - district_id: str
            - district_name: str
            - data_year: int  (ALWAYS present — never hide staleness)
            - crime_rate: float (total IPC crimes per 100k population)
            - ipc_categories: dict mapping category → count
            - total_ipc_crimes: int
            - source: str
        """
        api_key = self._settings.datagov_api_key
        if not api_key:
            raise ConfigError(
                "DATAGOV_API_KEY not configured. Get a key from "
                "https://data.gov.in/ (free registration)."
            )

        resource_id = self._CRIME_RESOURCE_IDS.get("district_ipc", "")
        url = f"{self.DATAGOV_API_URL}/{resource_id}"

        params: dict[str, Any] = {
            "api-key": api_key,
            "format": "json",
            "limit": 100,
        }

        # Filter by district
        params["filters[district]"] = district_id

        if year:
            params["filters[year]"] = str(year)

        def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=url)
                self._log_fetch(
                    url=url, params={k: v for k, v in params.items() if k != "api-key"},
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(
                url=url, params={k: v for k, v in params.items() if k != "api-key"},
                status="ok", attempt=attempt, elapsed_ms=elapsed,
            )
            return data

        raw = self._with_retry(operation)
        self._record_success()
        return self._parse_crime_data(raw, district_id, year)

    async def get_district_crime_rate_async(
        self,
        district_id: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Async variant of get_district_crime_rate."""
        api_key = self._settings.datagov_api_key
        if not api_key:
            raise ConfigError(
                "DATAGOV_API_KEY not configured. Get a key from "
                "https://data.gov.in/ (free registration)."
            )

        resource_id = self._CRIME_RESOURCE_IDS.get("district_ipc", "")
        url = f"{self.DATAGOV_API_URL}/{resource_id}"

        params: dict[str, Any] = {
            "api-key": api_key,
            "format": "json",
            "limit": 100,
            "filters[district]": district_id,
        }

        if year:
            params["filters[year]"] = str(year)

        async def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=url)
                self._log_fetch(
                    url=url,
                    params={k: v for k, v in params.items() if k != "api-key"},
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(
                url=url, params={k: v for k, v in params.items() if k != "api-key"},
                status="ok", attempt=attempt, elapsed_ms=elapsed,
            )
            return data

        raw = await self._with_retry_async(operation)
        self._record_success()
        return self._parse_crime_data(raw, district_id, year)

    def _parse_crime_data(
        self,
        raw: dict[str, Any],
        district_id: str,
        requested_year: int | None,
    ) -> dict[str, Any]:
        """Parse data.gov.in response into a structured crime-rate result."""
        records = raw.get("records", [])
        if not records:
            return {
                "district_id": district_id,
                "district_name": district_id,
                "data_year": requested_year,
                "crime_rate": None,
                "ipc_categories": {},
                "total_ipc_crimes": 0,
                "source": "data.gov.in",
                "note": "No crime data found for this district/year",
            }

        # If no year specified, find the most recent available
        if not requested_year:
            years = set()
            for rec in records:
                yr = rec.get("year")
                if yr:
                    try:
                        years.add(int(yr))
                    except (ValueError, TypeError):
                        pass
            if years:
                requested_year = max(years)
                records = [r for r in records if str(r.get("year")) == str(requested_year)]

        # Aggregate IPC categories
        ipc_categories: dict[str, int] = {}
        total_crimes = 0
        district_name = district_id

        for rec in records:
            name = rec.get("district", rec.get("district_name", district_id))
            if name:
                district_name = str(name)

            # Try common data.gov.in field names for crime counts
            for key in ("total_ipc_crimes", "total_cognizable_crimes", "crimes_total"):
                val = rec.get(key)
                if val is not None:
                    try:
                        total_crimes += int(val)
                    except (ValueError, TypeError):
                        pass

            # Extract IPC categories
            for key, val in rec.items():
                if key.startswith(("ipc_", "crimes_")) and val is not None:
                    try:
                        ipc_categories[key] = ipc_categories.get(key, 0) + int(val)
                    except (ValueError, TypeError):
                        pass

        # Crime rate per 100k — approximate if population is not in the dataset
        population = None
        for rec in records:
            pop = rec.get("population") or rec.get("total_population")
            if pop:
                try:
                    population = int(pop)
                    break
                except (ValueError, TypeError):
                    pass

        crime_rate: float | None = None
        if population and population > 0:
            crime_rate = round((total_crimes / population) * 100_000, 2)

        return {
            "district_id": district_id,
            "district_name": district_name,
            "data_year": requested_year,
            "crime_rate": crime_rate,
            "ipc_categories": ipc_categories,
            "total_ipc_crimes": total_crimes,
            "source": "data.gov.in",
        }
