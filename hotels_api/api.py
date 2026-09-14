"""
FastAPI route definitions for Hotel Listing, Real-time geospatial queries, Pipeline execution, and Exports.
"""

import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Response
from fastapi.responses import FileResponse

from hotels_api.models import (
    HotelProperty,
    HotelSearchQuery,
    NearbySearchQuery,
    BboxSearchQuery,
    AdhocBboxRequest,
    AdhocCityRequest,
    AdhocFetchResponse,
    PaginatedHotelsResponse,
    PipelineRunRequest,
    PipelineStatus,
    DataFrameSummary,
    TourismType,
)
from hotels_api.storage import storage_instance
from hotels_api.pipeline import pipeline_instance
from hotels_api.fetcher import OverpassFetcher, GeocodingClient
from hotels_api.geoutils import DEFAULT_REGIONS

router = APIRouter(prefix="/api/v1", tags=["Hotels API"])
fetcher = OverpassFetcher()


@router.get("/health", summary="Service Health Check")
def health_check():
    """Returns the operational status and number of indexed hotel properties."""
    return {
        "status": "healthy",
        "service": "Comprehensive Real-time Hotels API",
        "indexed_properties_count": len(storage_instance.df),
        "last_updated": storage_instance.last_updated.isoformat(),
        "default_regions_available": len(DEFAULT_REGIONS)
    }


@router.get("/regions", summary="List Available Pre-configured Regions")
def list_regions():
    """Retrieve the dictionary of all predefined geographic regions and bounding boxes."""
    return {
        "count": len(DEFAULT_REGIONS),
        "regions": [
            {
                "id": key,
                "name": key.replace("_", " ").title(),
                "south": bbox[0],
                "west": bbox[1],
                "north": bbox[2],
                "east": bbox[3],
                "center_lat": round((bbox[0] + bbox[2]) / 2, 4),
                "center_lon": round((bbox[1] + bbox[3]) / 2, 4),
            }
            for key, bbox in DEFAULT_REGIONS.items()
        ]
    }


@router.get("/hotels/search", response_model=PaginatedHotelsResponse, summary="Search Hotels & Accommodations")
def search_hotels(
    q: Optional[str] = Query(None, description="Keyword search matching property name, brand, or address"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    region: Optional[str] = Query(None, description="Filter by region identifier"),
    property_type: Optional[TourismType] = Query(None, description="Accommodation type"),
    min_stars: Optional[float] = Query(None, ge=1.0, le=5.0, description="Minimum star rating"),
    max_stars: Optional[float] = Query(None, ge=1.0, le=5.0, description="Maximum star rating"),
    has_wifi: Optional[bool] = Query(None, description="Filter by WiFi availability"),
    has_pool: Optional[bool] = Query(None, description="Filter by swimming pool"),
    has_parking: Optional[bool] = Query(None, description="Filter by on-site parking"),
    has_ac: Optional[bool] = Query(None, description="Filter by air conditioning"),
    has_restaurant: Optional[bool] = Query(None, description="Filter by restaurant"),
    is_pet_friendly: Optional[bool] = Query(None, description="Filter by pet friendly stays"),
    is_wheelchair: Optional[bool] = Query(None, description="Filter by wheelchair accessibility"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    sort_by: str = Query("name", description="Field to sort by (name, stars, price_min, user_rating)"),
    sort_desc: bool = Query(False, description="Sort in descending order"),
):
    """
    Search indexed hotels and properties using rich attribute filters and pagination.
    """
    offset = (page - 1) * page_size
    items, total = storage_instance.search(
        query=q,
        city=city,
        region=region,
        property_type=property_type.value if property_type else None,
        min_stars=min_stars,
        max_stars=max_stars,
        has_wifi=has_wifi,
        has_pool=has_pool,
        has_parking=has_parking,
        has_ac=has_ac,
        has_restaurant=has_restaurant,
        is_pet_friendly=is_pet_friendly,
        is_wheelchair=is_wheelchair,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=page_size,
        offset=offset,
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedHotelsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/hotels/nearby", response_model=List[HotelProperty], summary="Real-time Proximity / Radius Search")
async def get_nearby_hotels(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude coordinate"),
    radius_km: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers"),
    realtime: bool = Query(False, description="If True, query Overpass API live in real-time"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
):
    """
    Find hotels within a radius from coordinates. If `realtime=true`, queries the live Overpass OSM API
    and adds the newly fetched properties into the master DataFrame.
    """
    radius_meters = radius_km * 1000.0

    if realtime or storage_instance.df.empty:
        # Fetch live from Overpass
        live_props = await fetcher.fetch_radius_async(latitude, longitude, radius_meters=radius_meters)
        if live_props:
            storage_instance.load_from_properties(live_props)

    results = storage_instance.query_radius(latitude, longitude, radius_meters=radius_meters, limit=limit)
    return results


@router.get("/hotels/bbox", response_model=List[HotelProperty], summary="Real-time Bounding Box Query")
async def get_hotels_by_bbox(
    south: float = Query(..., ge=-90.0, le=90.0),
    west: float = Query(..., ge=-180.0, le=180.0),
    north: float = Query(..., ge=-90.0, le=90.0),
    east: float = Query(..., ge=-180.0, le=180.0),
    region_label: str = Query("custom_bbox", description="Label for the queried region"),
    realtime: bool = Query(False, description="If True, execute live Overpass query for this bbox"),
    persist: bool = Query(False, description="If True, persist newly fetched data to disk"),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Fetch all accommodation properties inside any arbitrary bounding box.
    Works with ANY coordinates worldwide — not limited to predefined regions.
    Set `realtime=true` to live-fetch from Overpass API for any bbox.
    Set `persist=true` to save newly fetched data into the master dataset.
    """
    if realtime:
        live_props = await fetcher.fetch_bbox_async(south, west, north, east, region=region_label)
        if live_props:
            storage_instance.load_from_properties(live_props)
            if persist:
                storage_instance.export_all(base_filename="hotels_master")

    return storage_instance.query_bbox(south, west, north, east, limit=limit)


@router.post("/hotels/fetch-bbox", response_model=AdhocFetchResponse, summary="Fetch Hotels from Any Bounding Box")
async def fetch_hotels_adhoc_bbox(req: AdhocBboxRequest):
    """
    **Runtime ad-hoc endpoint**: Fetch hotel data from ANY arbitrary bounding box on the planet.
    Not limited to predefined regions — provide any south/west/north/east coordinates.

    The fetched data is parsed, normalized, and optionally merged into the master DataFrame
    and exported to CSV/Parquet/SQLite.

    Example body:
    ```json
    {
        "south": 26.85, "west": 75.72, "north": 27.00, "east": 75.90,
        "region_label": "jaipur_custom",
        "persist": true
    }
    ```
    """
    try:
        live_props = await fetcher.fetch_bbox_async(
            req.south, req.west, req.north, req.east, region=req.region_label
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Overpass API fetch failed: {str(e)}")

    output_files = {}
    if live_props:
        storage_instance.load_from_properties(live_props)
        if req.persist:
            storage_instance.data_dir = req.output_dir
            output_files = storage_instance.export_all(base_filename="hotels_master")

    return AdhocFetchResponse(
        status="success",
        region_label=req.region_label,
        bbox_used={"south": req.south, "west": req.west, "north": req.north, "east": req.east},
        properties_fetched=len(live_props),
        total_dataset_size=len(storage_instance.df),
        message=f"Fetched {len(live_props)} properties from bbox ({req.south},{req.west},{req.north},{req.east})."
                + (" Data persisted to disk." if req.persist else " Data in memory only."),
        output_files=output_files,
    )


@router.post("/hotels/fetch-city", response_model=AdhocFetchResponse, summary="Fetch Hotels by City/Place Name")
async def fetch_hotels_by_city(req: AdhocCityRequest):
    """
    **Runtime ad-hoc endpoint**: Provide any city or place name (e.g. "Manali", "Pokhara", "Tokyo")
    and this endpoint will:
    1. Geocode it to coordinates and a bounding box
    2. Fetch all hotels from the Overpass API within that area
    3. Optionally persist to the master dataset

    Example body:
    ```json
    {
        "city_name": "Udaipur",
        "buffer_degrees": 0.05,
        "persist": true
    }
    ```
    """
    # Geocode the city name
    geo_result = await GeocodingClient.geocode_city_async(req.city_name)
    if not geo_result:
        raise HTTPException(
            status_code=404,
            detail=f"Could not geocode '{req.city_name}'. Try a more specific place name."
        )

    lat, lon, (south, west, north, east) = geo_result

    # Apply buffer expansion
    south -= req.buffer_degrees
    west -= req.buffer_degrees
    north += req.buffer_degrees
    east += req.buffer_degrees

    region_label = req.region_label or req.city_name.lower().replace(" ", "_")

    try:
        live_props = await fetcher.fetch_bbox_async(south, west, north, east, region=region_label)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Overpass API fetch failed: {str(e)}")

    output_files = {}
    if live_props:
        storage_instance.load_from_properties(live_props)
        if req.persist:
            storage_instance.data_dir = req.output_dir
            output_files = storage_instance.export_all(base_filename="hotels_master")

    return AdhocFetchResponse(
        status="success",
        region_label=region_label,
        bbox_used={"south": round(south, 6), "west": round(west, 6), "north": round(north, 6), "east": round(east, 6)},
        properties_fetched=len(live_props),
        total_dataset_size=len(storage_instance.df),
        message=f"Geocoded '{req.city_name}' → ({lat:.4f}, {lon:.4f}). "
                f"Fetched {len(live_props)} properties."
                + (" Data persisted to disk." if req.persist else " Data in memory only."),
        output_files=output_files,
    )


@router.get("/hotels/{hotel_id}", response_model=HotelProperty, summary="Get Single Hotel Property Details")
def get_hotel_details(hotel_id: str):
    """Fetch complete metadata for a specific hotel by its ID."""
    prop = storage_instance.get_by_id(hotel_id)
    if not prop:
        raise HTTPException(status_code=404, detail=f"Hotel property '{hotel_id}' not found")
    return prop


@router.post("/pipeline/run", summary="Trigger Large-Scale Ingestion Pipeline")
async def trigger_pipeline(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    """
    Initiate the automated pipeline to fetch, clean, enrich, and generate large datasets
    across multiple regions. Runs in the background.
    """
    if pipeline_instance.status.is_running:
        return {
            "status": "already_running",
            "message": "Pipeline is already in progress.",
            "pipeline_status": pipeline_instance.status
        }

    background_tasks.add_task(pipeline_instance.run_async_task, req)
    return {
        "status": "started",
        "message": "Hotel ingestion pipeline started in background.",
        "regions_to_fetch": req.regions or list(DEFAULT_REGIONS.keys()),
        "output_dir": req.output_dir
    }


@router.get("/pipeline/status", response_model=PipelineStatus, summary="Get Pipeline Execution Status")
def get_pipeline_status():
    """Monitor real-time progress, processed counts, and status of running ingestion pipelines."""
    return pipeline_instance.status


@router.get("/dataframe/summary", response_model=DataFrameSummary, summary="Dataset Statistical Summary")
def get_dataframe_summary():
    """Retrieve comprehensive statistical aggregations and metrics for the loaded hotel DataFrame."""
    return storage_instance.get_summary()


@router.get("/dataframe/export", summary="Download Large Dataset File")
def export_dataframe(
    format: str = Query("csv", pattern="^(csv|parquet|sqlite|json)$", description="File format: csv, parquet, sqlite, or json")
):
    """
    Download the generated large hotel dataset in CSV, Parquet, SQLite, or JSON format.
    """
    if storage_instance.df.empty:
        raise HTTPException(status_code=400, detail="DataFrame is empty. Run the pipeline first.")

    export_files = storage_instance.export_all(base_filename="hotels_master")
    
    if format == "csv":
        return FileResponse(
            export_files["csv"],
            media_type="text/csv",
            filename="hotels_master.csv"
        )
    elif format == "parquet":
        return FileResponse(
            export_files["parquet"],
            media_type="application/octet-stream",
            filename="hotels_master.parquet"
        )
    elif format == "sqlite":
        return FileResponse(
            export_files["sqlite"],
            media_type="application/x-sqlite3",
            filename="hotels.db"
        )
    elif format == "json":
        json_str = storage_instance.df.to_json(orient="records", date_format="iso")
        return Response(content=json_str, media_type="application/json")
