"""FastAPI application for India Travel Safety & Hotel Intelligence Service."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import Settings, load_settings
from api.geocoder import GeocodeCandidate, get_geocoder, is_coordinate_in_india
from api.orchestrator import REPORT_CACHE, SignalOrchestrator
from llm.explainer import LLMExplainer, NarrativeResult

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("api.main")

settings = load_settings()

app = FastAPI(
    title="India Travel Safety Intelligence API",
    description="Deterministic fusion hazard scoring, OSM accommodation ranking, and verified AI explanation layer.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate-limiting state
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


@app.middleware("http")
async def rate_limiting_and_logging_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()

    # Rate limiting (per minute)
    window = _RATE_LIMIT_BUCKETS.setdefault(client_ip, [])
    # Filter timestamps older than 60 seconds
    _RATE_LIMIT_BUCKETS[client_ip] = [ts for ts in window if now - ts < 60.0]

    if len(_RATE_LIMIT_BUCKETS[client_ip]) >= settings.api_rate_limit_per_minute:
        logger.warning(f"Rate limit exceeded for client IP: {client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "rate_limit_exceeded", "message": "Too many requests. Please slow down."},
        )

    _RATE_LIMIT_BUCKETS[client_ip].append(now)

    # Process request and log
    start_time = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    logger.info(
        f'{request.method} {request.url.path} {response.status_code} in {elapsed_ms}ms (IP: {client_ip})'
    )
    return response


# Shared instances
_orchestrator: SignalOrchestrator | None = None
_explainer: LLMExplainer | None = None


def get_orchestrator() -> SignalOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SignalOrchestrator(settings=settings)
    return _orchestrator


def get_explainer() -> LLMExplainer:
    global _explainer
    if _explainer is None:
        _explainer = LLMExplainer(settings=settings)
    return _explainer


# ── Schemas ─────────────────────────────────────────────────────────────────


class ExplanationRequest(BaseModel):
    report_id: str = Field(..., description="Stable ID of the pre-computed deterministic report")
    models: Optional[dict[str, str]] = Field(default=None, description="Optional override model IDs")


# ── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/v1/health", tags=["System"])
async def get_health():
    """Health check endpoint returning system status and operating modes."""
    return {
        "status": "healthy",
        "demo_mode": settings.demo_mode,
        "config_version": get_orchestrator().fusion_cfg.config_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "geocoder": settings.geocode_provider,
            "fusion": "ready",
            "hotels": "osm_overpass",
            "llm": "openrouter" if settings.openrouter_api_key else "fallback_template_mode",
        },
    }


@app.get("/v1/sources", tags=["System"])
async def get_sources_directory():
    """Metadata catalog of all connected hazard and spatial data sources."""
    return {
        "sources": [
            {
                "id": "gdacs",
                "name": "Global Disaster Alert and Coordination System (GDACS)",
                "type": "Natural Hazard Alerts (Flood, Cyclone, EQ, Volcano)",
                "cadence": "15-30 minutes",
                "licensing": "Open access, United Nations / European Commission",
                "redistribution": "Permitted",
            },
            {
                "id": "usgs",
                "name": "United States Geological Survey (USGS)",
                "type": "Real-time Earthquake GeoJSON Feed",
                "cadence": "5-15 minutes",
                "licensing": "Public domain (US Government)",
                "redistribution": "Permitted",
            },
            {
                "id": "firms",
                "name": "NASA FIRMS (VIIRS/MODIS)",
                "type": "Active Thermal Fire Anomalies",
                "cadence": "3 hours (NRT)",
                "licensing": "NASA Earth Science Data Systems policy",
                "redistribution": "Permitted with attribution",
            },
            {
                "id": "acled",
                "name": "Armed Conflict Location & Event Data Project (ACLED)",
                "type": "Political Violence, Demonstrations & Civil Unrest",
                "cadence": "Weekly / Real-time updates",
                "licensing": "Academic/Research license. Commercial redistribution requires written permission.",
                "redistribution": "Aggregated / Derived only if redistribution_allowed=False",
            },
            {
                "id": "crime_ncrb",
                "name": "National Crime Records Bureau / data.gov.in",
                "type": "District-level IPC Crime Rates & Percentiles",
                "cadence": "Annual Official Statistics",
                "licensing": "National Data Sharing and Accessibility Policy (NDSAP), India",
                "redistribution": "Permitted with attribution",
            },
            {
                "id": "open_meteo",
                "name": "Open-Meteo & IMD (India Meteorological Department)",
                "type": "Atmospheric conditions, 24h Rainfall, Wind & Forecasts",
                "cadence": "Hourly / Real-time",
                "licensing": "Non-commercial free tier / CC BY 4.0",
                "redistribution": "Permitted",
            },
            {
                "id": "gdelt",
                "name": "GDELT Project (DOC 2.0 API)",
                "type": "Real-time Local Incident News & Civil Signals",
                "cadence": "15 minutes",
                "licensing": "Open data initiative",
                "redistribution": "Permitted",
            },
            {
                "id": "bhuvan",
                "name": "Bhuvan / NRSC (ISRO)",
                "type": "Geological & Landslide Susceptibility Atlas",
                "cadence": "Static seasonal / periodic atlas updates",
                "licensing": "ISRO / Government of India open data guidelines",
                "redistribution": "Derived layers",
            },
            {
                "id": "osm",
                "name": "OpenStreetMap Contributors",
                "type": "Accommodations, Points of Interest, and Emergency Services",
                "cadence": "Real-time Overpass API",
                "licensing": "Open Database License (ODbL)",
                "redistribution": "Permitted with attribution (c) OpenStreetMap contributors",
            },
        ],
        "config_version": get_orchestrator().fusion_cfg.config_version,
    }


@app.get("/v1/geocode", tags=["Location"], response_model=list[GeocodeCandidate])
async def search_places(
    q: str = Query(..., min_length=2, description="Place search query (e.g. Manali, Shimla, Paharganj)"),
    limit: int = Query(5, ge=1, le=10, description="Maximum number of candidates"),
):
    """Geocode an Indian location query using Nominatim with countrycodes=in policy.

    NO per-keystroke querying; call on Enter or search button click.
    """
    geocoder = get_geocoder(settings=settings)
    candidates = await geocoder.geocode(q, limit=limit)
    if not candidates:
        return []
    return candidates


@app.get("/v1/search-report", tags=["Scoring & Hotels"])
async def get_search_report(
    q: Optional[str] = Query(None, description="Location search query (e.g. 'Manali')"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Target Latitude (WGS84)"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Target Longitude (WGS84)"),
    radius_km: float = Query(5.0, ge=1.0, le=50.0, description="Search radius in kilometers"),
    alpha: float = Query(0.7, ge=0.0, le=1.0, description="Ranking weight: 1.0=Safety only, 0.0=Quality only"),
    max_hotels: int = Query(30, ge=1, le=100, description="Max hotels to return"),
    price_preference: Optional[str] = Query(None, description="Preferred price tier: budget, mid_range, luxury"),
):
    """Comprehensive, deterministic travel safety and hotel intelligence report.

    NO LLM calculation in this endpoint. Always returns deterministic score,
    decomposed contributions, coverage report, and transparently ranked hotels.
    """
    target_lat: float
    target_lon: float
    location_name: str
    district_id: str | None = None
    state_name: str | None = None
    disambiguation: list[GeocodeCandidate] = []

    # 1. Resolve coordinates from q or lat/lon
    if lat is not None and lon is not None:
        target_lat = lat
        target_lon = lon
        location_name = q or f"Location ({round(lat, 4)}, {round(lon, 4)})"
    elif q:
        geocoder = get_geocoder(settings=settings)
        candidates = await geocoder.geocode(q, limit=5)
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not locate any place in India matching query '{q}'. Please check spelling.",
            )
        best = candidates[0]
        target_lat = best.lat
        target_lon = best.lon
        location_name = best.display_name
        district_id = best.district
        state_name = best.state
        if len(candidates) > 1:
            disambiguation = candidates[1:]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'q' or both 'lat' and 'lon' parameters must be provided.",
        )

    # 2. Scope Check: India territory only
    if not is_coordinate_in_india(target_lat, target_lon):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "out_of_coverage",
                "message": (
                    f"Coordinates ({target_lat}, {target_lon}) fall outside India territorial coverage. "
                    "This system operates exclusively for India travel safety."
                ),
                "is_in_india": False,
            },
        )

    # 3. Gather signals and execute fusion orchestration
    orchestrator = get_orchestrator()
    report = await orchestrator.gather_signals_and_score(
        lat=target_lat,
        lon=target_lon,
        location_name=location_name,
        district_id=district_id,
        state_name=state_name,
        radius_km=radius_km,
        alpha=alpha,
        max_hotels=max_hotels,
        price_preference=price_preference,
    )

    if disambiguation:
        report["disambiguation_candidates"] = [c.model_dump() for c in disambiguation]

    return report


@app.post("/v1/explanation", tags=["LLM Explanation Layer"])
async def generate_explanation(body: ExplanationRequest = Body(...)):
    """Generate verified, plain-language narrative explanation from a pre-computed report.

    Runs OpenRouter LLM narrator and verifier models against the deterministic JSON.
    Never alters or computes scores. Returns fallback template if models fail or fabricate numbers.
    """
    report_id = body.report_id
    if report_id not in REPORT_CACHE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report ID '{report_id}' not found or expired. Please run /v1/search-report first.",
        )

    _, cached_report = REPORT_CACHE[report_id]
    explainer = get_explainer()
    narrative_res: NarrativeResult = await explainer.generate_and_verify_narrative(
        report=cached_report,
        model_override=body.models,
    )

    return narrative_res.model_dump()
