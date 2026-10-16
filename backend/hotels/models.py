"""Hotel data models, access-to-help context, and ranking breakdown schemas."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from fusion.aggregation import ScoreBand, SignalContribution


class Hotel(BaseModel):
    """Pydantic model representing an accommodation listing.

    Missing values stay None. Never defaulted to 0.
    """

    id: str
    name: str
    lat: float
    lon: float
    source: str
    source_id: str
    category: str  # hotel, guest_house, hostel, motel, apartment, etc.
    stars: float | None = None
    rating: float | None = None
    review_count: int | None = None
    price_band: str | None = None  # budget, mid_range, upscale, luxury
    amenities: list[str] = Field(default_factory=list)
    address: str | None = None
    website: str | None = None
    phone: str | None = None
    distance_to_query_km: float = 0.0


class AccessToHelp(BaseModel):
    """Contextual proximity to essential emergency help from the hotel.

    NOT factored into the risk score in v1.
    """

    hospital_distance_km: float | None = None
    police_distance_km: float | None = None
    fire_station_distance_km: float | None = None
    hospital_name: str | None = None
    police_name: str | None = None
    fire_station_name: str | None = None


class RankBreakdown(BaseModel):
    """Transparent decomposition of how a hotel was ranked."""

    rank_score: float
    safety_norm: float
    quality_norm: float | None
    alpha: float
    quality_weight: float
    attributes_used: list[str]
    limited_info: bool
    explanation: str


class HotelScored(BaseModel):
    """A hotel with deterministic local fusion score, ranking, and context."""

    hotel: Hotel
    safety_score: int
    score_band: ScoreBand
    S_static: float
    S_dynamic: float
    top_contributions: list[SignalContribution]
    differentiating_factors: list[SignalContribution]
    access_to_help: AccessToHelp
    rank_score: float
    rank_breakdown: RankBreakdown
    limited_info: bool
