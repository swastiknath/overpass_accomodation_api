# Real-Time Hotel Data Listing API & Large-Scale Ingestion Pipeline

A production-grade, asynchronous REST API and high-throughput data pipeline for fetching comprehensive hotel & accommodation data across any global region or bounding box with coordinates, detailed property metadata, spatial indexing, and multi-format exports.

---

##  Key Features

- **Sub-millisecond Spatial Indexing**: 3D Cartesian `cKDTree` spatial index for lightning-fast radius (`/nearby`) and bounding-box (`/bbox`) searches.
- **Real-Time OSM / Overpass Engine**: Live querying across multiple Overpass mirrors (`overpass-api.de`, `lz4.overpass-api.de`, `kumi.systems`, `mail.ru`) with automatic failover and backoff.
- **Comprehensive Property Metadata (54 Attributes)**:
  - **Identifiers**: `hotel_id`, `osm_id`, `osm_type`, `xotelo_key`, `wikidata_id`
  - **Core Attributes**: `name`, `brand`, `operator`, `property_type` (*hotel, hostel, resort, guest house, motel, apartment, chalet, camp site*), `description`
  - **Geospatial**: `latitude`, `longitude`, `elevation_m`, `geohash`, `region`, `distance_meters`
  - **Address Breakdown**: `formatted_address`, `street`, `house_number`, `neighborhood`, `city`, `state`, `country`, `postal_code`
  - **Ratings & Pricing**: `stars`, `user_rating`, `review_count`, `price_min`, `price_max`, `currency`, `price_tier`
  - **Amenities**: `has_wifi`, `has_pool`, `has_parking`, `has_air_conditioning`, `has_restaurant`, `has_bar`, `has_spa`, `has_gym`, `is_pet_friendly`, `is_wheelchair_accessible`, `smoking_allowed`
  - **Capacity & Timings**: `rooms_count`, `beds_count`, `checkin_time`, `checkout_time`, `opening_hours`
  - **Contact & Media**: `phone`, `email`, `website`, `booking_url`, `image_url`
-  **Large-Scale Data Pipeline**: Capable of ingesting tens of thousands of properties across custom or 29+ pre-configured global tourist corridors.
-  **Multi-Format Large DataFrame Exports**: Instant export to **CSV**, **Apache Parquet**, **SQLite**, and **JSON**.
- **Interactive Web Dashboard**: Embedded Leaflet map, live search filters, real-time property details, and visual pipeline runner.

---

## Quick Start

### 1. Setup Environment
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the REST API & Dashboard
```bash
PYTHONPATH=. uvicorn hotels_api.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Map Dashboard**: Open [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: Open [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## CLI Pipeline Runner

Fetch real-time data across multiple destinations and generate master datasets directly from the command line:

```bash
# Run pipeline across specific regions
PYTHONPATH=. python pipeline_runner.py --regions goa,rishikesh_haridwar,manali_kasol,kathmandu_thamel

# Run pipeline over all 29+ pre-configured global regions
PYTHONPATH=. python pipeline_runner.py --all

# List available pre-configured regions
PYTHONPATH=. python pipeline_runner.py --list-regions
```

### Generated Files in `./data/`:
- `hotels_master.csv` (Flat CSV for Excel / Pandas)
- `hotels_master.parquet` (Columnar Apache Parquet for high-speed Big Data queries)
- `hotels.db` (SQLite relational database for SQL queries)

---

## REST API Reference

### 1. Search Hotels
`GET /api/v1/hotels/search`

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Search keyword (matches name, brand, or address) |
| `city` | string | Filter by city name |
| `region` | string | Filter by region identifier |
| `property_type` | string | `hotel`, `hostel`, `guest_house`, `resort`, `apartment`, `motel` |
| `min_stars` / `max_stars` | float | Star rating filter (1.0 to 5.0) |
| `has_wifi`, `has_pool`, `has_ac` | bool | Amenity flags |
| `has_restaurant`, `has_parking` | bool | Amenity flags |
| `is_pet_friendly`, `is_wheelchair` | bool | Amenity flags |
| `page` / `page_size` | int | Pagination parameters |
| `sort_by` / `sort_desc` | string/bool | Sort by `name`, `stars`, `price_min`, `user_rating` |

**Example**:
```bash
curl "http://localhost:8000/api/v1/hotels/search?q=Resort&min_stars=4&has_pool=true"
```

---

### 2. Nearby Proximity Search (Coordinates + Radius)
`GET /api/v1/hotels/nearby`

| Parameter | Type | Description |
|---|---|---|
| `latitude` | float | Anchor latitude |
| `longitude` | float | Anchor longitude |
| `radius_km` | float | Search radius in km (default: 5.0) |
| `realtime` | bool | If `true`, queries live Overpass in real-time if missing |
| `limit` | int | Max results (default: 50) |

**Example**:
```bash
curl "http://localhost:8000/api/v1/hotels/nearby?latitude=15.53&longitude=73.76&radius_km=3"
```

---

### 3. Bounding Box Search
`GET /api/v1/hotels/bbox`

| Parameter | Type | Description |
|---|---|---|
| `south`, `west`, `north`, `east` | float | Bounding box coordinates |
| `realtime` | bool | Live Overpass query flag |
| `limit` | int | Max results |

**Example**:
```bash
curl "http://localhost:8000/api/v1/hotels/bbox?south=15.2&west=73.8&north=15.6&east=74.2"
```

---

### 4. Single Property Profile
`GET /api/v1/hotels/{hotel_id}`

**Example**:
```bash
curl "http://localhost:8000/api/v1/hotels/osm_node_12098612531"
```

---

### 5. Trigger Background Ingestion Pipeline
`POST /api/v1/pipeline/run`

```json
{
  "regions": ["goa", "rishikesh_haridwar", "bali_ubud_seminyak"],
  "enrich_synthetic_rates": true,
  "output_dir": "./data"
}
```

---

### 6. Pipeline Progress & Status
`GET /api/v1/pipeline/status`

Returns live completion percentage, currently active region step, and processed records count.

---

### 7. Dataset Summary & Statistical Breakdown
`GET /api/v1/dataframe/summary`

Returns total record counts, memory footprint, breakdown by accommodation category, star ratings, and amenity coverage percentages.

---

### 8. Export Large DataFrame
`GET /api/v1/dataframe/export?format={csv|parquet|sqlite|json}`

---

##  Testing

Run unit tests and API integration suite:
```bash
PYTHONPATH=. pytest tests/
```
