"""FastAPI REST API for Bhuvan Geo-Hazard Ingestion & 6,670+ Layer Analytics.

Provides interactive OpenAPI documentation (/docs), search, categorization,
spatial travel safety analysis, live GeoJSON generation, and tile fetching.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from gis.bhuvan_client import BhuvanClient
from gis.catalogue import BhuvanCatalogue, get_catalogue
from gis.config import INDIA_BBOX, load_settings
from gis.harmonize import to_geojson

app = FastAPI(
    title="India Travel Safety — Bhuvan / ISRO Geo-Hazard API",
    description="""
API for indexing, analyzing, and querying **6,670+ Bhuvan / NRSC (ISRO) geospatial layers**
and real-time hazard data for India-specific travel safety applications.

### Key Capabilities:
- **Comprehensive Catalogue Analytics**: Real-time statistical analysis across 6,670+ layers spanning all 36 Indian States/UTs.
- **Thematic Categorization**: Automated categorization across 10 domains (Disasters/Hazards, Transport/Mobility, Administrative Boundaries, Tourism, Water/Hydrology, Land/Terrain, Urban Planning, Rural Decentralized Planning, Infrastructure/Utilities).
- **Spatial Travel Safety Analysis**: Point & bounding box corridor risk profiling for active hazards and road infrastructure.
- **Direct GeoJSON Export**: Vector feature extraction from live Bhuvan WFS, WMS GetFeatureInfo, and local spatial datasets.
- **High-Performance In-Memory Index**: Sub-millisecond search & spatial filtering over thousands of layers.
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend mapping clients (Leaflet, MapLibre, OpenLayers, Mapbox)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas for Request & Response validation
class PointAnalysisRequest(BaseModel):
    lon: float = Field(..., ge=68.0, le=97.5, description="Longitude in EPSG:4326 (e.g. 77.2090 for Delhi)")
    lat: float = Field(..., ge=6.0, le=37.0, description="Latitude in EPSG:4326 (e.g. 28.6139 for Delhi)")
    radius_deg: float = Field(0.05, gt=0, le=1.0, description="Search radius buffer in degrees (~5 km at 0.05)")


class BBoxAnalysisRequest(BaseModel):
    min_lon: float = Field(..., ge=60.0, le=100.0)
    min_lat: float = Field(..., ge=5.0, le=40.0)
    max_lon: float = Field(..., ge=60.0, le=100.0)
    max_lat: float = Field(..., ge=5.0, le=40.0)


@app.get("/", tags=["System"])
def root() -> dict[str, Any]:
    """Root landing endpoint with system summary and documentation links."""
    cat = get_catalogue()
    return {
        "service": "India Travel Safety — Bhuvan Geo-Hazard API",
        "version": "1.0.0",
        "status": "operational",
        "total_layers_indexed": len(cat.layers),
        "docs_url": "/docs",
        "endpoints": {
            "summary": "/api/v1/summary",
            "categories": "/api/v1/categories",
            "states": "/api/v1/states",
            "layers": "/api/v1/layers",
            "point_safety_analysis": "/api/v1/analytics/point",
            "bbox_safety_analysis": "/api/v1/analytics/bbox",
            "catalogue_geojson": "/api/v1/catalogue/geojson",
        },
    }


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Health check for load balancers and container orchestrators."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/status", tags=["System"])
def system_status() -> dict[str, Any]:
    """Detailed operational status including live Bhuvan endpoint and memory index status."""
    cat = get_catalogue()
    settings = load_settings()
    return {
        "status": "online",
        "total_layers": len(cat.layers),
        "wms_endpoint": cat.wms_base_url,
        "wfs_endpoint": settings.bhuvan_wfs_base_url,
        "landing_zone": str(settings.gis_landing_zone),
        "cache_loaded_at": cat.loaded_at.isoformat() if cat.loaded_at else None,
    }


@app.get("/api/v1/summary", tags=["Analytics"])
def catalogue_summary() -> dict[str, Any]:
    """Comprehensive statistical breakdown across all 6,670+ indexed Bhuvan layers."""
    cat = get_catalogue()
    return cat.get_summary()


@app.get("/api/v1/categories", tags=["Analytics"])
def list_categories() -> list[dict[str, Any]]:
    """List all thematic categories with layer counts and descriptions."""
    cat = get_catalogue()
    summary = cat.get_summary()
    return summary["categories"]


@app.get("/api/v1/states", tags=["Analytics"])
def list_states() -> list[dict[str, Any]]:
    """Breakdown of layers across Indian States and Union Territories."""
    cat = get_catalogue()
    summary = cat.get_summary()
    return summary["top_states"]


@app.get("/api/v1/workspaces", tags=["Analytics"])
def list_workspaces() -> list[dict[str, Any]]:
    """Breakdown of layers across Bhuvan workspaces (nuis, sisdp, tour, mmi, sdv, etc.)."""
    cat = get_catalogue()
    summary = cat.get_summary()
    return summary["workspaces"]


@app.get("/api/v1/layers", tags=["Layers"])
def search_layers(
    q: str | None = Query(None, description="Keyword text search in layer name, title, or abstract"),
    category: str | None = Query(None, description="Thematic category (e.g. disasters_hazards, transport_mobility, admin_boundaries)"),
    state: str | None = Query(None, description="Indian State/UT name (e.g. Assam, Uttarakhand, Odisha, Kerala)"),
    workspace: str | None = Query(None, description="Bhuvan workspace prefix (e.g. nuis, sisdp, tour, mmi, sdv)"),
    min_lon: float | None = Query(None, description="Filter by bounding box min longitude"),
    min_lat: float | None = Query(None, description="Filter by bounding box min latitude"),
    max_lon: float | None = Query(None, description="Filter by bounding box max longitude"),
    max_lat: float | None = Query(None, description="Filter by bounding box max latitude"),
    limit: int = Query(50, ge=1, le=500, description="Pagination page size"),
    offset: int = Query(0, ge=0, description="Pagination offset index"),
) -> dict[str, Any]:
    """Search and filter through all 6,670+ layers with multi-attribute and spatial filtering."""
    cat = get_catalogue()
    bbox = (min_lon, min_lat, max_lon, max_lat) if None not in (min_lon, min_lat, max_lon, max_lat) else None

    return cat.search(
        query=q,
        category=category,
        state=state,
        workspace=workspace,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/layers/{layer_name:path}", tags=["Layers"])
def get_layer_details(layer_name: str) -> dict[str, Any]:
    """Get complete metadata, bounding box, CRS list, and tile URL template for a specific layer."""
    cat = get_catalogue()
    layer = cat.get_layer(layer_name)
    if not layer:
        raise HTTPException(status_code=404, detail=f"Layer {layer_name!r} not found in Bhuvan catalogue")
    return layer.to_dict()


@app.post("/api/v1/analytics/point", tags=["Spatial Safety Analytics"])
def point_safety_analysis(req: PointAnalysisRequest) -> dict[str, Any]:
    """Analyze travel hazard risks, road connectivity, and administrative context for a GPS point."""
    cat = get_catalogue()
    return cat.analyze_point_safety(lon=req.lon, lat=req.lat, radius_deg=req.radius_deg)


@app.post("/api/v1/analytics/bbox", tags=["Spatial Safety Analytics"])
def bbox_corridor_analysis(req: BBoxAnalysisRequest) -> dict[str, Any]:
    """Analyze travel hazard risks, road connectivity, and administrative context for a bounding box / route corridor."""
    cat = get_catalogue()
    return cat.analyze_bbox_safety(
        min_lon=req.min_lon,
        min_lat=req.min_lat,
        max_lon=req.max_lon,
        max_lat=req.max_lat,
    )


@app.get("/api/v1/catalogue/geojson", tags=["GeoJSON"])
def export_catalogue_geojson(
    category: str | None = Query(None, description="Optional category filter"),
    state: str | None = Query(None, description="Optional state filter"),
    limit: int = Query(200, ge=1, le=1000, description="Max number of bounding box features to export"),
) -> dict[str, Any]:
    """Export layer bounding boxes as a GeoJSON FeatureCollection for interactive map visualization."""
    cat = get_catalogue()
    return cat.to_geojson(category=category, state=state, limit=limit)


@app.get("/api/v1/layers/{layer_name:path}/geojson", tags=["GeoJSON"])
def fetch_layer_geojson(
    layer_name: str,
    min_lon: float = Query(68.0),
    min_lat: float = Query(6.0),
    max_lon: float = Query(97.5),
    max_lat: float = Query(37.0),
) -> dict[str, Any]:
    """Fetch live vector features or GetFeatureInfo for a layer directly as GeoJSON."""
    client = BhuvanClient()
    bbox = (min_lon, min_lat, max_lon, max_lat)

    try:
        # First attempt GetFeatureInfo GeoJSON from WMS
        return client.get_feature_info_geojson(layer_name, bbox=bbox)
    except Exception:
        pass

    try:
        # Fallback to WFS vector query
        return client.get_features_geojson(layer_name, bbox=bbox)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve GeoJSON for layer {layer_name!r}: {exc}",
        ) from exc


@app.get("/api/v1/layers/{layer_name:path}/tile", tags=["Layers"])
def fetch_layer_tile(
    layer_name: str,
    min_lon: float = Query(68.0),
    min_lat: float = Query(6.0),
    max_lon: float = Query(97.5),
    max_lat: float = Query(37.0),
    width: int = Query(512, ge=64, le=2048),
    height: int = Query(512, ge=64, le=2048),
    format: str = Query("image/png", description="Raster format (image/png, image/tiff)"),
) -> Response:
    """Fetch/proxy WMS GetMap raster tile for a layer."""
    client = BhuvanClient()
    bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        raw_bytes = client.get_layer(
            layer_name,
            bbox=bbox,
            output_format=format,
            width=width,
            height=height,
        )
        return Response(content=raw_bytes, media_type=format)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch tile for {layer_name!r}: {exc}",
        ) from exc


@app.post("/api/v1/catalogue/refresh", tags=["System"])
def refresh_catalogue_endpoint(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger background refresh of the 6,670+ layer catalogue from live Bhuvan GetCapabilities."""
    cat = get_catalogue()
    background_tasks.add_task(cat.refresh)
    return {
        "status": "refresh_initiated",
        "message": "Downloading live Capabilities XML from Bhuvan and updating in-memory index in the background.",
    }
