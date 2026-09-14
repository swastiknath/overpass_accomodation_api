"""
Data models and schemas for Hotel listings, pipeline execution, and API queries.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class TourismType(str, Enum):
    HOTEL = "hotel"
    HOSTEL = "hostel"
    GUEST_HOUSE = "guest_house"
    RESORT = "resort"
    MOTEL = "motel"
    APARTMENT = "apartment"
    CHALET = "chalet"
    BED_AND_BREAKFAST = "bed_and_breakfast"
    CAMP_SITE = "camp_site"
    OTHER = "other"


class PriceTier(str, Enum):
    BUDGET = "budget"          # $ / <$50
    MID_RANGE = "mid_range"    # $$ / $50-$150
    UPSCALE = "upscale"        # $$$ / $150-$300
    LUXURY = "luxury"          # $$$$ / >$300
    UNKNOWN = "unknown"


class HotelProperty(BaseModel):
    """
    Comprehensive hotel and accommodation property model with rich metadata.
    """
    # Unique Identifiers
    hotel_id: str = Field(..., description="Unique canonical ID (e.g., 'osm_node_1234567')")
    osm_id: Optional[int] = Field(None, description="OpenStreetMap element ID")
    osm_type: Optional[str] = Field(None, description="OSM element type: node, way, or relation")
    xotelo_key: Optional[str] = Field(None, description="TripAdvisor/Xotelo location key if mapped")
    wikidata_id: Optional[str] = Field(None, description="Wikidata entity ID (e.g. Q12345)")
    
    # Core Information
    name: str = Field(..., description="Primary property name")
    name_international: Optional[str] = Field(None, description="English/International name if localized")
    brand: Optional[str] = Field(None, description="Hospitality brand (e.g. Marriott, OYO, Zostel)")
    operator: Optional[str] = Field(None, description="Operating company or hotel group")
    property_type: TourismType = Field(TourismType.HOTEL, description="Accommodation category")
    description: Optional[str] = Field(None, description="Property description or overview")

    # Geospatial Coordinates
    latitude: float = Field(..., description="Latitude coordinate in WGS84")
    longitude: float = Field(..., description="Longitude coordinate in WGS84")
    elevation_m: Optional[float] = Field(None, description="Elevation in meters if available")
    geohash: str = Field(..., description="Calculated standard Geohash")
    region: Optional[str] = Field(None, description="Normalized region/city identifier")
    distance_meters: Optional[float] = Field(None, description="Distance from search anchor if querying nearby")

    # Address & Location Details
    formatted_address: Optional[str] = Field(None, description="Full composed street address")
    house_number: Optional[str] = Field(None, description="Building/house number")
    street: Optional[str] = Field(None, description="Street name")
    neighborhood: Optional[str] = Field(None, description="Neighborhood, suburb, or district")
    city: Optional[str] = Field(None, description="City / Municipality")
    state: Optional[str] = Field(None, description="State, province, or territory")
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country code")
    postal_code: Optional[str] = Field(None, description="Postal / ZIP code")

    # Ratings & Pricing
    stars: Optional[float] = Field(None, description="Official or OSM star rating (1-5)")
    user_rating: Optional[float] = Field(None, description="Aggregated guest rating score (0.0-10.0 or 0-5)")
    review_count: Optional[int] = Field(None, description="Total number of verified guest reviews")
    price_min: Optional[float] = Field(None, description="Estimated minimum nightly price")
    price_max: Optional[float] = Field(None, description="Estimated maximum nightly price")
    currency: Optional[str] = Field("USD", description="Currency code for price estimations")
    price_tier: PriceTier = Field(PriceTier.UNKNOWN, description="Categorical budget tier")

    # Amenities & Property Features
    has_wifi: bool = Field(False, description="Whether free/paid WiFi is available")
    has_pool: bool = Field(False, description="Whether swimming pool is available")
    has_parking: bool = Field(False, description="Whether on-site parking is available")
    has_air_conditioning: bool = Field(False, description="Whether air conditioning is equipped")
    has_restaurant: bool = Field(False, description="Whether an on-site dining restaurant is present")
    has_bar: bool = Field(False, description="Whether bar / pub / lounge is available")
    has_spa: bool = Field(False, description="Whether spa / wellness facilities exist")
    has_gym: bool = Field(False, description="Whether fitness center / gym is equipped")
    is_pet_friendly: bool = Field(False, description="Whether pets are allowed")
    is_wheelchair_accessible: bool = Field(False, description="Wheelchair accessibility compliance")
    smoking_allowed: Optional[bool] = Field(None, description="Whether smoking is allowed")
    
    # Operations & Capacities
    rooms_count: Optional[int] = Field(None, description="Total number of guest rooms")
    beds_count: Optional[int] = Field(None, description="Total number of beds")
    checkin_time: Optional[str] = Field(None, description="Standard check-in time (e.g. 14:00)")
    checkout_time: Optional[str] = Field(None, description="Standard check-out time (e.g. 11:00)")
    opening_hours: Optional[str] = Field(None, description="Operating hours or 24/7 front desk status")

    # Contact & Web
    phone: Optional[str] = Field(None, description="Primary telephone / mobile contact")
    email: Optional[str] = Field(None, description="Contact email address")
    website: Optional[str] = Field(None, description="Official website URL")
    booking_url: Optional[str] = Field(None, description="Direct booking or OTA reservation URL")
    image_url: Optional[str] = Field(None, description="Featured photo or thumbnail URL")

    # Metadata & Data Lineage
    data_sources: List[str] = Field(default_factory=lambda: ["osm"], description="Data source origins")
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    raw_tags: Optional[Dict[str, Any]] = Field(default=None, description="Original source tags")


class HotelSearchQuery(BaseModel):
    query: Optional[str] = Field(None, description="Search keyword matching name, brand, or address")
    city: Optional[str] = Field(None, description="Filter by city name")
    region: Optional[str] = Field(None, description="Filter by region key")
    property_type: Optional[TourismType] = Field(None, description="Filter by property type")
    min_stars: Optional[float] = Field(None, ge=1.0, le=5.0, description="Minimum star rating")
    max_stars: Optional[float] = Field(None, ge=1.0, le=5.0, description="Maximum star rating")
    has_wifi: Optional[bool] = None
    has_pool: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_ac: Optional[bool] = None
    has_restaurant: Optional[bool] = None
    is_pet_friendly: Optional[bool] = None
    is_wheelchair_accessible: Optional[bool] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)
    sort_by: str = Field("name", description="'name', 'stars', 'rating', 'distance', 'price_min'")
    sort_desc: bool = Field(False, description="Sort in descending order")


class NearbySearchQuery(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Anchor latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Anchor longitude")
    radius_km: float = Field(5.0, ge=0.1, le=100.0, description="Search radius in kilometers")
    realtime: bool = Field(False, description="If True, query Overpass live if not found in index")
    property_type: Optional[TourismType] = None
    min_stars: Optional[float] = None
    limit: int = Field(50, ge=1, le=500)


class BboxSearchQuery(BaseModel):
    south: float = Field(..., ge=-90.0, le=90.0)
    west: float = Field(..., ge=-180.0, le=180.0)
    north: float = Field(..., ge=-90.0, le=90.0)
    east: float = Field(..., ge=-180.0, le=180.0)
    realtime: bool = Field(False, description="If True, execute live Overpass query")
    property_type: Optional[TourismType] = None
    limit: int = Field(100, ge=1, le=1000)


class AdhocBboxRequest(BaseModel):
    """Request model for fetching hotels from an arbitrary bounding box at runtime."""
    south: float = Field(..., ge=-90.0, le=90.0, description="Southern latitude boundary")
    west: float = Field(..., ge=-180.0, le=180.0, description="Western longitude boundary")
    north: float = Field(..., ge=-90.0, le=90.0, description="Northern latitude boundary")
    east: float = Field(..., ge=-180.0, le=180.0, description="Eastern longitude boundary")
    region_label: str = Field("custom_region", description="A label/name for this custom region")
    persist: bool = Field(True, description="If True, merge results into the master DataFrame and export")
    output_dir: str = Field("./data", description="Directory to save exported datasets")


class AdhocCityRequest(BaseModel):
    """Request model for geocoding a city/place name and fetching hotels within its bounds."""
    city_name: str = Field(..., description="City or place name to geocode (e.g., 'Jaipur', 'Pokhara')")
    buffer_degrees: float = Field(0.05, ge=0.0, le=1.0, description="Buffer in degrees to expand the geocoded bbox")
    region_label: Optional[str] = Field(None, description="Custom label (defaults to city_name if not set)")
    persist: bool = Field(True, description="If True, merge results into the master DataFrame and export")
    output_dir: str = Field("./data", description="Directory to save exported datasets")


class AdhocFetchResponse(BaseModel):
    """Response for ad-hoc bbox/city fetch operations."""
    status: str
    region_label: str
    bbox_used: Dict[str, float]
    properties_fetched: int
    total_dataset_size: int
    message: str
    output_files: Dict[str, str] = Field(default_factory=dict)


class PipelineRunRequest(BaseModel):
    regions: Optional[List[str]] = Field(None, description="List of region names to fetch. If empty, all default regions.")
    custom_bboxes: Optional[Dict[str, List[float]]] = Field(None, description="Custom {name: [south, west, north, east]}")
    enrich_synthetic_rates: bool = Field(True, description="Enrich missing price and rating signals")
    export_formats: List[str] = Field(default_factory=lambda: ["csv", "parquet", "sqlite"], description="Export file types")
    output_dir: str = Field("./data", description="Directory to save generated datasets")


class PipelineStatus(BaseModel):
    is_running: bool
    current_step: str
    progress_pct: float
    total_regions: int
    completed_regions: int
    total_fetched_raw: int
    unique_properties_processed: int
    errors: List[str]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output_files: Dict[str, str] = Field(default_factory=dict)


class PaginatedHotelsResponse(BaseModel):
    items: List[HotelProperty]
    total: int
    page: int
    page_size: int
    total_pages: int


class DataFrameSummary(BaseModel):
    total_records: int
    columns_count: int
    memory_usage_mb: float
    regions_count: int
    top_regions: Dict[str, int]
    property_types_distribution: Dict[str, int]
    stars_distribution: Dict[str, int]
    amenities_coverage: Dict[str, float]
    price_statistics: Dict[str, Any]
    last_updated: str
