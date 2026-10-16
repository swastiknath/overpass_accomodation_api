"""Weather connector with pluggable backend interface.

IMD (India Meteorological Department) has no stable public REST API — do not
assume one exists. This module provides two backends:

1. IMDScraperBackend — best-effort scraper stub for IMD's public warning pages.
   Marked clearly as fragile: page structure can change silently. Has its own
   retry/alerting. Should NOT be treated as a reliable source.

2. OpenMeteoBackend — clean, reliable API (open-meteo.com, no auth required).
   Used as the PRIMARY source for current conditions, forecasts, and rainfall.
   IMD data is layered as enrichment when available, not a hard dependency.

The `rainfall_mm_24h` field is specifically included — it feeds downstream
landslide/flood trigger logic.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Protocol

from gis.config import Settings, load_settings
from gis.exceptions import ConfigError, MalformedResponse

from connectors.base import BaseConnector


class WeatherBackend(Protocol):
    """Interface for weather data backends."""

    def get_conditions(
        self, lat: float, lon: float
    ) -> dict[str, Any]:
        """Return weather data for a point."""
        ...

    async def get_conditions_async(
        self, lat: float, lon: float
    ) -> dict[str, Any]:
        """Async variant."""
        ...


class OpenMeteoBackend:
    """Primary weather backend using Open-Meteo API (no auth, reliable).

    Open-Meteo provides hourly/daily forecasts with good India coverage.
    Documentation: https://open-meteo.com/en/docs
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, connector: BaseConnector) -> None:
        self._connector = connector

    def get_conditions(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,"
                       "surface_pressure",
            "hourly": "temperature_2m,precipitation_probability,precipitation,rain,"
                      "weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,rain_sum,precipitation_probability_max,"
                     "wind_speed_10m_max",
            "forecast_days": 3,
            "timezone": "Asia/Kolkata",
        }

        def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = self._connector._http_client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._connector._classify_http_error(exc, url=self.BASE_URL)
                self._connector._log_fetch(
                    url=self.BASE_URL, params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._connector._log_fetch(
                url=self.BASE_URL, params=params, status="ok",
                attempt=attempt, elapsed_ms=elapsed,
            )
            return data

        raw = self._connector._with_retry(operation)
        return self._parse_response(raw)

    async def get_conditions_async(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,"
                       "surface_pressure",
            "hourly": "temperature_2m,precipitation_probability,precipitation,rain,"
                      "weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,rain_sum,precipitation_probability_max,"
                     "wind_speed_10m_max",
            "forecast_days": 3,
            "timezone": "Asia/Kolkata",
        }

        async def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = await self._connector._http_async_client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._connector._classify_http_error(exc, url=self.BASE_URL)
                self._connector._log_fetch(
                    url=self.BASE_URL, params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._connector._log_fetch(
                url=self.BASE_URL, params=params, status="ok",
                attempt=attempt, elapsed_ms=elapsed,
            )
            return data

        raw = await self._connector._with_retry_async(operation)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize Open-Meteo response into the shared weather shape."""
        current = raw.get("current", {})
        hourly = raw.get("hourly", {})
        daily = raw.get("daily", {})

        # Calculate 24h rainfall from hourly precipitation
        hourly_precip = hourly.get("precipitation", [])
        rainfall_24h = sum(float(p) for p in hourly_precip[:24] if p is not None)

        # Build 3-day forecast from daily data
        forecast: list[dict[str, Any]] = []
        daily_dates = daily.get("time", [])
        for i, date in enumerate(daily_dates[:3]):
            forecast.append({
                "date": date,
                "temp_max_c": _safe_float(daily.get("temperature_2m_max", []), i),
                "temp_min_c": _safe_float(daily.get("temperature_2m_min", []), i),
                "precipitation_sum_mm": _safe_float(daily.get("precipitation_sum", []), i),
                "rain_sum_mm": _safe_float(daily.get("rain_sum", []), i),
                "precip_probability_max": _safe_float(daily.get("precipitation_probability_max", []), i),
                "wind_speed_max_kmh": _safe_float(daily.get("wind_speed_10m_max", []), i),
                "weather_code": _safe_int(daily.get("weather_code", []), i),
            })

        return {
            "source": "open_meteo",
            "current_conditions": {
                "temperature_c": current.get("temperature_2m"),
                "apparent_temperature_c": current.get("apparent_temperature"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "precipitation_mm": current.get("precipitation"),
                "rain_mm": current.get("rain"),
                "weather_code": current.get("weather_code"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "wind_direction_deg": current.get("wind_direction_10m"),
                "pressure_hpa": current.get("surface_pressure"),
                "observation_time": current.get("time"),
            },
            "forecast_3day": forecast,
            "warnings": [],  # Open-Meteo doesn't provide warning alerts directly
            "rainfall_mm_24h": round(rainfall_24h, 1),
        }


class IMDScraperBackend:
    """BEST-EFFORT stub for IMD (India Meteorological Department) scraping.

    ⚠️  WARNING: IMD has no stable public REST API. This scraper targets
    IMD's public weather warning pages and is LIKELY TO BREAK when IMD
    changes page structure (which happens without notice).

    This backend should NOT be treated as reliable. It enriches the primary
    Open-Meteo data when available; failures are logged and silently skipped.
    The calling code must handle `None` returns gracefully.

    Known fragility points:
    - Page HTML structure changes without versioning or notice
    - Anti-scraping measures may block automated access
    - Warning categorization/formatting is inconsistent across pages
    """

    # IMD public warning pages (subject to change without notice)
    IMD_WARNING_URL = "https://mausam.imd.gov.in/responsive/wardisplay.php"

    def __init__(self, connector: BaseConnector) -> None:
        self._connector = connector

    def get_conditions(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Attempt to scrape IMD warnings. Returns None on any failure.

        This is a stub — full implementation requires HTML parsing logic
        specific to IMD's current page structure, which changes frequently.
        """
        try:
            return self._scrape_warnings(lat, lon)
        except Exception:
            # IMD scraping is best-effort; log and return None
            self._connector._log_fetch(
                url=self.IMD_WARNING_URL,
                status="scraper_failure",
                error_type="IMDScraperError",
                message="imd_scraper_failed",
            )
            return None

    async def get_conditions_async(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Async variant — same best-effort semantics."""
        try:
            return await self._scrape_warnings_async(lat, lon)
        except Exception:
            self._connector._log_fetch(
                url=self.IMD_WARNING_URL,
                status="scraper_failure",
                error_type="IMDScraperError",
                message="imd_scraper_failed",
            )
            return None

    def _scrape_warnings(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Stub: scrape IMD warning page. Returns structured warnings or None.

        TODO: Implement HTML parsing for IMD's current page structure.
        The page uses dynamic content loading and the structure changes
        frequently. A production implementation would need:
        1. Playwright or Selenium for JS-rendered content
        2. Region-to-state mapping for lat/lon → IMD station code
        3. Robust HTML parsing with fallback selectors
        4. Separate alerting when scrape success rate drops below threshold
        """
        started = time.perf_counter()
        try:
            resp = self._connector._http_client.get(
                self.IMD_WARNING_URL,
                headers={"User-Agent": "IndiaTravel-Safety/0.2 (research)"},
            )
            resp.raise_for_status()
        except Exception:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        self._connector._log_fetch(
            url=self.IMD_WARNING_URL, status="ok",
            elapsed_ms=elapsed, message="imd_scrape_attempt",
        )

        # Stub: actual HTML parsing would go here
        # Return empty structure indicating scraper ran but found no parseable data
        return {
            "source": "imd_scraper",
            "warnings": [],
            "scraper_status": "stub_not_implemented",
            "note": "IMD scraper is a best-effort stub. Actual HTML parsing "
                    "requires implementation specific to IMD's current page structure.",
        }

    async def _scrape_warnings_async(self, lat: float, lon: float) -> dict[str, Any] | None:
        """Async stub for IMD scraping."""
        started = time.perf_counter()
        try:
            resp = await self._connector._http_async_client.get(
                self.IMD_WARNING_URL,
                headers={"User-Agent": "IndiaTravel-Safety/0.2 (research)"},
            )
            resp.raise_for_status()
        except Exception:
            return None

        elapsed = (time.perf_counter() - started) * 1000
        self._connector._log_fetch(
            url=self.IMD_WARNING_URL, status="ok",
            elapsed_ms=elapsed, message="imd_scrape_attempt",
        )

        return {
            "source": "imd_scraper",
            "warnings": [],
            "scraper_status": "stub_not_implemented",
        }


class WeatherClient(BaseConnector):
    """Weather data client with pluggable backends.

    Primary: Open-Meteo (reliable, no auth)
    Enrichment: IMD scraper (best-effort, fragile)
    """

    SOURCE_NAME = "weather"

    def __init__(self, settings: Settings | None = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)
        self._open_meteo = OpenMeteoBackend(self)
        self._imd = IMDScraperBackend(self)

    def get_conditions(self, lat: float, lon: float) -> dict[str, Any]:
        """Get current conditions, forecast, warnings, and 24h rainfall.

        Open-Meteo is the primary source. IMD data is merged in as
        enrichment when available (never a hard dependency).
        """
        # Primary source — must succeed
        result = self._open_meteo.get_conditions(lat, lon)
        self._record_success()

        # Enrichment — best-effort, failures silently skipped
        imd_data = self._imd.get_conditions(lat, lon)
        if imd_data and imd_data.get("warnings"):
            result["warnings"].extend(imd_data["warnings"])
            result["imd_enrichment"] = imd_data

        return result

    async def get_conditions_async(self, lat: float, lon: float) -> dict[str, Any]:
        """Async variant of get_conditions."""
        import asyncio

        # Run both in parallel — IMD is enrichment, not blocking
        primary_task = self._open_meteo.get_conditions_async(lat, lon)
        imd_task = self._imd.get_conditions_async(lat, lon)

        results = await asyncio.gather(primary_task, imd_task, return_exceptions=True)

        # Primary must succeed
        if isinstance(results[0], Exception):
            raise results[0]

        result = results[0]
        self._record_success()

        # Merge IMD enrichment if available
        if isinstance(results[1], dict) and results[1] and results[1].get("warnings"):
            result["warnings"].extend(results[1]["warnings"])
            result["imd_enrichment"] = results[1]

        return result


def _safe_float(lst: list, idx: int) -> float | None:
    try:
        v = lst[idx]
        return float(v) if v is not None else None
    except (IndexError, TypeError, ValueError):
        return None


def _safe_int(lst: list, idx: int) -> int | None:
    try:
        v = lst[idx]
        return int(v) if v is not None else None
    except (IndexError, TypeError, ValueError):
        return None
