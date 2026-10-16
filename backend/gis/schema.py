"""Common ingested-record schema for all geo (and later GDELT/ACLED) sources."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry.base import BaseGeometry


class ResolutionTier(str, Enum):
    POINT = "point"
    POLYGON = "polygon"
    DISTRICT = "district"


class IngestedRecord(BaseModel):
    """One normalized hazard observation.

    Bhuvan WMS rasters are not GDELT-style point events. Emit one record per
    `(layer, bbox tile, effective_date)` and put the private landing-zone path
    in `raw_payload` — never embed raster bytes in this model.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_id: str
    source: str
    hazard_type: str
    geometry: BaseGeometry
    h3_cell: str | list[str] | None = None
    district_id: str | None = None
    event_time: datetime
    ingest_time: datetime
    severity_raw: str | float | int | None = None
    severity_normalized: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    resolution_tier: ResolutionTier
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("severity_normalized", "confidence")
    @classmethod
    def _nan_not_allowed(cls, value: float | None) -> float | None:
        if value is not None and value != value:  # NaN
            raise ValueError("NaN is not allowed")
        return value


def raster_tile_event_id(
    layer_name: str,
    bbox: tuple[float, float, float, float],
    effective_date: datetime,
) -> str:
    """Stable id for a WMS tile: hash(layer + bbox + date)."""

    material = f"{layer_name}|{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}|{effective_date.date().isoformat()}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"bhuvan:{layer_name}:{digest}"
