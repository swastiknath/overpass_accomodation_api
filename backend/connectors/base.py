"""Shared retry / backoff / logging base for all data connectors.

Mirrors the retry logic and structured-logging pattern established in
`gis.bhuvan_client.BhuvanClient._with_retry` — same backoff curve,
same exception classification boundary, same audit log shape.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

from gis.config import Settings, load_settings
from gis.exceptions import (
    AuthFailure,
    ConfigError,
    ConnectorError,
    MalformedResponse,
    NetworkTimeout,
    ServerUnavailable,
)
from gis.logging_utils import log_raw_fetch

T = TypeVar("T")


class BaseConnector:
    """Common infrastructure for every external-data connector.

    Subclasses get:
    - `_with_retry(operation)` — exponential backoff on NetworkTimeout / ServerUnavailable
    - `_classify_http_error(exc, url)` — maps httpx/transport errors to typed exceptions
    - `_log_fetch(...)` — delegates to the shared JSON audit logger
    - `_http_client` property — a lazily-created httpx.Client with configured timeout

    Retry policy: exponential backoff on timeouts and 5xx only.
    Auth failures, config errors, and malformed responses are not retried.
    """

    SOURCE_NAME: str = "base"  # override in subclass

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings or load_settings()
        self._sleep = sleep
        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None
        self._last_successful_fetch: str | None = None

    @property
    def max_retries(self) -> int:
        return self._settings.connector_max_retries

    @property
    def retry_base_seconds(self) -> float:
        return self._settings.connector_retry_base_seconds

    @property
    def timeout_seconds(self) -> float:
        return self._settings.connector_timeout_seconds

    @property
    def last_successful_fetch(self) -> str | None:
        """ISO timestamp of the last successful fetch, or None."""
        return self._last_successful_fetch

    # ── Sync HTTP client ──────────────────────────────────────────────────

    @property
    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
            )
        return self._client

    # ── Async HTTP client ─────────────────────────────────────────────────

    @property
    def _http_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
            )
        return self._async_client

    # ── Retry with exponential backoff ────────────────────────────────────

    def _with_retry(self, operation: Callable[[int], T]) -> T:
        """Execute `operation(attempt)` with retry on transient failures.

        Same semantics as BhuvanClient._with_retry:
        - Retries on NetworkTimeout, ServerUnavailable
        - Does NOT retry AuthFailure, ConfigError, MalformedResponse, ConnectorError
        """
        last: Exception | None = None
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return operation(attempt)
            except (AuthFailure, ConfigError, MalformedResponse, ConnectorError):
                raise
            except (NetworkTimeout, ServerUnavailable) as exc:
                last = exc
                if attempt >= total_attempts:
                    raise
                delay = self.retry_base_seconds * (2 ** (attempt - 1))
                self._sleep(delay)
        assert last is not None
        raise last

    async def _with_retry_async(self, operation: Callable[[int], Any]) -> Any:
        """Async variant of _with_retry — operation must be an async callable."""
        import asyncio

        last: Exception | None = None
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return await operation(attempt)
            except (AuthFailure, ConfigError, MalformedResponse, ConnectorError):
                raise
            except (NetworkTimeout, ServerUnavailable) as exc:
                last = exc
                if attempt >= total_attempts:
                    raise
                delay = self.retry_base_seconds * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
        assert last is not None
        raise last

    # ── Error classification ──────────────────────────────────────────────

    def _classify_http_error(self, exc: Exception, *, url: str) -> Exception:
        """Map httpx / transport errors to typed GIS exceptions."""
        if isinstance(exc, (AuthFailure, ConfigError, MalformedResponse,
                            NetworkTimeout, ServerUnavailable, ConnectorError)):
            return exc

        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            if code in (401, 403):
                return AuthFailure(f"HTTP {code} from {url}")
            if code == 404:
                return ConnectorError(f"HTTP 404 from {url} — resource not found")
            if code >= 500:
                return ServerUnavailable(f"HTTP {code} from {url}")
            return MalformedResponse(f"HTTP {code} from {url}: {exc}")

        if isinstance(exc, httpx.TimeoutException):
            return NetworkTimeout(f"Timeout talking to {url}: {exc}")

        if isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
            return ServerUnavailable(f"Connection error talking to {url}: {exc}")

        text = str(exc).lower()
        if "timeout" in text or "timed out" in text:
            return NetworkTimeout(f"Timeout talking to {url}: {exc}")
        return ServerUnavailable(f"Request failed for {url}: {exc}")

    # ── Structured audit logging ──────────────────────────────────────────

    def _log_fetch(
        self,
        *,
        url: str,
        params: dict[str, Any] | None = None,
        status: str | int | None = None,
        attempt: int = 1,
        layer: str | None = None,
        elapsed_ms: float | None = None,
        error_type: str | None = None,
        message: str = "raw_fetch",
    ) -> None:
        log_raw_fetch(
            url=url,
            params=params,
            status=status,
            attempt=attempt,
            source=self.SOURCE_NAME,
            layer=layer,
            elapsed_ms=elapsed_ms,
            error_type=error_type,
            message=message,
        )

    def _record_success(self) -> None:
        """Record the current UTC time as the last successful fetch."""
        from datetime import datetime, timezone
        self._last_successful_fetch = datetime.now(timezone.utc).isoformat()
