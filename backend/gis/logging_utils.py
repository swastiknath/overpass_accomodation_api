"""Structured audit logging for every raw geo fetch."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


AUDIT_LOGGER_NAME = "gis.audit"


class JsonAuditFormatter(logging.Formatter):
    """One JSON object per line: timestamp, URL, params, status, attempt."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "event",
            "url",
            "params",
            "status",
            "attempt",
            "elapsed_ms",
            "source",
            "layer",
            "error_type",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def get_audit_logger() -> logging.Logger:
    """Return the shared audit logger.

    Callers should pass `extra={...}` on every raw fetch. A JSON handler is
    attached once if the logger has no handlers yet so importing the package
    does not duplicate lines under pytest.
    """

    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonAuditFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_raw_fetch(
    *,
    url: str,
    params: dict[str, Any] | None,
    status: str | int | None,
    attempt: int,
    source: str,
    layer: str | None = None,
    elapsed_ms: float | None = None,
    error_type: str | None = None,
    message: str = "raw_fetch",
) -> None:
    get_audit_logger().info(
        message,
        extra={
            "event": "raw_fetch",
            "url": url,
            "params": params or {},
            "status": status,
            "attempt": attempt,
            "source": source,
            "layer": layer,
            "elapsed_ms": elapsed_ms,
            "error_type": error_type,
        },
    )
