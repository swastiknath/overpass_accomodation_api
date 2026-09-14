"""
Main application entry point for the Comprehensive Real-Time Hotels API & Ingestion Pipeline.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from hotels_api.api import router as api_router
from hotels_api.storage import storage_instance
from hotels_api.pipeline import pipeline_instance
from hotels_api.geoutils import DEFAULT_REGIONS

logger = logging.getLogger("hotels_api.main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: load existing data or trigger a seed dataset.
    """
    logger.info("Initializing Hotels API service...")
    data_dir = os.path.abspath("./data")
    storage_instance.data_dir = data_dir

    # Check for existing data
    storage_instance.load_from_disk()

    # If dataset is empty, run seed pipeline for top vibrant destinations
    if storage_instance.df.empty:
        logger.info("No existing dataset found. Pre-fetching seed regions (rishikesh_haridwar, goa, manali_kasol)...")
        seed_regions = ["rishikesh_haridwar", "goa", "manali_kasol"]
        pipeline_instance.run_sync(regions=seed_regions, output_dir=data_dir)

    yield
    logger.info("Hotels API service shutdown.")


app = FastAPI(
    title="Real-Time Comprehensive Hotel Data API",
    description="""
    🚀 **Production-grade Real-Time Hotel API & High-Throughput Ingestion Pipeline**.
    
    ### Features:
    * 📍 **Geospatial Proximity & Radius Search** with sub-millisecond KDTree spatial indexing.
    * 🗺️ **Real-Time Overpass / OSM Queries** with multi-mirror automatic failover.
    * 🏢 **Deep Property Attributes**: Coordinates, address, stars, pricing, amenities, room counts, contact, websites, and geohashes.
    * 📊 **Large-scale Ingestion Pipeline**: Extracts thousands of listings across custom or pre-configured worldwide regions into unified DataFrames.
    * 💾 **Multi-Format Export**: One-click download in CSV, Parquet, SQLite, and JSON.
    * 🖥️ **Interactive Live Dashboard**: Built-in map explorer, search bench, and pipeline manager.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for all frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST API routes
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse, summary="Interactive Web Dashboard")
@app.get("/dashboard", response_class=HTMLResponse, summary="Interactive Web Dashboard")
def serve_dashboard():
    """
    Serve the embedded interactive single-page dashboard with Leaflet map,
    live search bench, pipeline controls, and dataset analytics.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotels API & Data Pipeline Dashboard</title>
    <!-- Modern Typography & Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #121826;
            --bg-card: rgba(26, 34, 52, 0.75);
            --bg-card-hover: rgba(35, 46, 70, 0.9);
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-purple: #8b5cf6;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border-color: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(59, 130, 246, 0.3);
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --shadow-glow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
        }

        /* Top Navigation */
        header {
            background: rgba(18, 24, 38, 0.85);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .logo-group {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
        }

        .logo-text h1 {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #ffffff, #93c5fd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-text span {
            font-size: 12px;
            color: var(--text-secondary);
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 9px 16px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            border: 1px solid transparent;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent-blue), #2563eb);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(37, 99, 235, 0.45);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-success {
            background: linear-gradient(135deg, var(--accent-emerald), #059669);
            color: white;
        }

        /* Main Layout */
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px 32px;
            width: 100%;
            display: flex;
            flex-direction: column;
            gap: 24px;
            flex: 1;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 20px;
            backdrop-filter: blur(12px);
            display: flex;
            flex-direction: column;
            gap: 6px;
            position: relative;
            overflow: hidden;
            transition: border 0.3s;
        }

        .stat-card:hover {
            border-color: var(--border-glow);
        }

        .stat-label {
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 800;
            color: #ffffff;
        }

        .stat-sub {
            font-size: 12px;
            color: var(--accent-emerald);
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* App Main Grid: Map & Controls */
        .app-grid {
            display: grid;
            grid-template-columns: 420px 1fr;
            gap: 24px;
            height: 720px;
        }

        @media (max-width: 1100px) {
            .app-grid {
                grid-template-columns: 1fr;
                height: auto;
            }
        }

        /* Sidebar Controls */
        .sidebar-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 20px;
            backdrop-filter: blur(16px);
            display: flex;
            flex-direction: column;
            gap: 16px;
            overflow-y: auto;
            height: 100%;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .card-title {
            font-size: 16px;
            font-weight: 700;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .form-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-input, .form-select {
            background: rgba(10, 14, 23, 0.7);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 10px 12px;
            color: var(--text-primary);
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }

        .form-input:focus, .form-select:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
        }

        .filter-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag-checkbox {
            display: none;
        }

        .tag-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .tag-checkbox:checked + .tag-btn {
            background: rgba(59, 130, 246, 0.2);
            border-color: var(--accent-blue);
            color: #93c5fd;
        }

        /* Map Container */
        .map-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            overflow: hidden;
            position: relative;
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        #map {
            width: 100%;
            height: 100%;
            z-index: 10;
        }

        /* Custom Map Popup Styling */
        .leaflet-popup-content-wrapper {
            background: rgba(18, 24, 38, 0.95) !important;
            backdrop-filter: blur(14px);
            color: var(--text-primary) !important;
            border-radius: 12px !important;
            border: 1px solid var(--border-color);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
        }

        .leaflet-popup-tip {
            background: rgba(18, 24, 38, 0.95) !important;
        }

        .popup-hotel {
            padding: 4px;
            font-size: 13px;
        }

        .popup-title {
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }

        .popup-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(59, 130, 246, 0.25);
            color: #93c5fd;
            margin-bottom: 6px;
        }

        .popup-info {
            color: var(--text-secondary);
            margin-bottom: 4px;
            line-height: 1.4;
        }

        .popup-price {
            font-size: 14px;
            font-weight: 700;
            color: var(--accent-emerald);
            margin-top: 6px;
        }

        /* Pipeline Banner */
        .pipeline-card {
            background: linear-gradient(135deg, rgba(26, 34, 52, 0.9), rgba(18, 24, 38, 0.9));
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .pipeline-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }

        .progress-bar-bg {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
            width: 0%;
            transition: width 0.4s ease;
        }

        /* Results List */
        .results-container {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 10px;
            max-height: 260px;
            overflow-y: auto;
        }

        .hotel-item {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            padding: 10px 12px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .hotel-item:hover {
            background: rgba(59, 130, 246, 0.1);
            border-color: var(--accent-blue);
        }

        .hotel-item-name {
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
        }

        .hotel-item-sub {
            font-size: 11px;
            color: var(--text-muted);
        }

        /* Footer */
        footer {
            border-top: 1px solid var(--border-color);
            padding: 20px 32px;
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            background: var(--bg-secondary);
        }
    </style>
</head>
<body>

    <header>
        <div class="logo-group">
            <div class="logo-icon">🏨</div>
            <div class="logo-text">
                <h1>Hotels Real-Time Data Platform</h1>
                <span>Comprehensive OSM & Overpass Live Pipeline</span>
            </div>
        </div>
        <div class="nav-actions">
            <a href="/docs" target="_blank" class="btn btn-secondary">⚡ Swagger API Docs</a>
            <button onclick="exportData('csv')" class="btn btn-secondary">📥 CSV Export</button>
            <button onclick="exportData('parquet')" class="btn btn-secondary">📦 Parquet</button>
            <button onclick="exportData('json')" class="btn btn-secondary">{} JSON</button>
        </div>
    </header>

    <div class="container">

        <!-- Top Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <span class="stat-label">Total Properties Ingested</span>
                <span class="stat-value" id="stat-total">0</span>
                <span class="stat-sub">🟢 Real-time indexed in Memory</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Active Regions Covered</span>
                <span class="stat-value" id="stat-regions">0</span>
                <span class="stat-sub">🌐 Global & Regional BBoxes</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">WiFi & Amenities Rate</span>
                <span class="stat-value" id="stat-wifi">0%</span>
                <span class="stat-sub">✨ Verified Facilities</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Average Est. Nightly Rate</span>
                <span class="stat-value" id="stat-avg-price">$0</span>
                <span class="stat-sub">🏷️ Budget to Luxury Spectrum</span>
            </div>
        </div>

        <!-- Pipeline Orchestration Banner -->
        <div class="pipeline-card">
            <div class="pipeline-header">
                <div>
                    <h2 style="font-size: 18px; font-weight: 700;">Data Pipeline Orchestrator</h2>
                    <p style="font-size: 13px; color: var(--text-secondary); margin-top: 2px;">
                        Fetch and normalize live accommodations across worldwide bounding boxes into a large unified DataFrame.
                    </p>
                </div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <select id="pipeline-region-select" class="form-select" style="min-width: 200px;">
                        <option value="all">⚡ Fetch All Regions</option>
                    </select>
                    <button id="btn-run-pipeline" onclick="triggerPipelineRun()" class="btn btn-primary">
                        🚀 Run Ingestion Pipeline
                    </button>
                </div>
            </div>

            <div id="pipeline-progress-section" style="display: none; flex-direction: column; gap: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 13px;">
                    <span id="pipeline-step-text" style="color: var(--accent-cyan); font-weight: 600;">Initializing...</span>
                    <span id="pipeline-pct-text" style="font-weight: 700;">0%</span>
                </div>
                <div class="progress-bar-bg">
                    <div id="pipeline-progress-fill" class="progress-bar-fill"></div>
                </div>
            </div>
        </div>

        <!-- Main Workspace Grid: Search Controls & Map -->
        <div class="app-grid">
            
            <!-- Filter Sidebar -->
            <div class="sidebar-card">
                <div class="card-header">
                    <span class="card-title">Search & Live Filtering</span>
                    <button onclick="resetFilters()" class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;">Reset</button>
                </div>

                <div class="form-group">
                    <label class="form-label">Keyword / Property / Brand</label>
                    <input type="text" id="filter-keyword" class="form-input" placeholder="e.g. Zostel, Marriott, Resort..." oninput="debounceSearch()">
                </div>

                <div class="form-group">
                    <label class="form-label">Destination Region</label>
                    <select id="filter-region" class="form-select" onchange="onRegionChange()">
                        <option value="">All Regions</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">Property Type</label>
                    <select id="filter-type" class="form-select" onchange="applyFilters()">
                        <option value="">All Categories</option>
                        <option value="hotel">Hotel</option>
                        <option value="hostel">Hostel</option>
                        <option value="resort">Resort</option>
                        <option value="guest_house">Guest House</option>
                        <option value="apartment">Apartment</option>
                        <option value="motel">Motel</option>
                        <option value="chalet">Chalet</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">Required Amenities</label>
                    <div class="filter-tags">
                        <label>
                            <input type="checkbox" id="amenity-wifi" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">📶 WiFi</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-pool" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">🏊 Pool</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-parking" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">🚗 Parking</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-ac" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">❄️ AC</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-restaurant" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">🍽️ Restaurant</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-pet" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">🐾 Pet Friendly</span>
                        </label>
                        <label>
                            <input type="checkbox" id="amenity-wheelchair" class="tag-checkbox" onchange="applyFilters()">
                            <span class="tag-btn">♿ Wheelchair</span>
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="form-label">Results (<span id="results-count">0</span>)</span>
                    </div>
                    <div id="hotel-list" class="results-container">
                        <!-- Populated by JS -->
                    </div>
                </div>
            </div>

            <!-- Map View -->
            <div class="map-card">
                <div id="map"></div>
            </div>

        </div>

    </div>

    <footer>
        Hotels API & Data Pipeline • OpenStreetMap / Overpass Ground Truth • High Throughput Architecture
    </footer>

    <script>
        // Global Map & State
        let map;
        let markersGroup;
        let debounceTimer;
        let regionsList = [];
        let currentHotels = [];

        // Initialize Map
        function initMap() {
            map = L.map('map', {
                center: [28.6139, 77.2090], // Default center
                zoom: 6,
                zoomControl: true
            });

            // CartoDB Dark Matter tile layer
            L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);

            markersGroup = L.layerGroup().addTo(map);
        }

        // Fetch Regions metadata
        async function loadRegions() {
            try {
                const res = await fetch('/api/v1/regions');
                const data = await res.json();
                regionsList = data.regions;
                
                const filterSelect = document.getElementById('filter-region');
                const pipelineSelect = document.getElementById('pipeline-region-select');

                regionsList.forEach(reg => {
                    const opt1 = document.createElement('option');
                    opt1.value = reg.id;
                    opt1.textContent = reg.name;
                    filterSelect.appendChild(opt1);

                    const opt2 = document.createElement('option');
                    opt2.value = reg.id;
                    opt2.textContent = reg.name;
                    pipelineSelect.appendChild(opt2);
                });
            } catch (err) {
                console.error("Failed to load regions:", err);
            }
        }

        // Fetch dataset summary metrics
        async function loadSummary() {
            try {
                const res = await fetch('/api/v1/dataframe/summary');
                const data = await res.json();
                
                document.getElementById('stat-total').innerText = Number(data.total_records).toLocaleString();
                document.getElementById('stat-regions').innerText = data.regions_count || regionsList.length;
                document.getElementById('stat-wifi').innerText = (data.amenities_coverage.wifi_pct || 0) + '%';
                
                const avgPrice = data.price_statistics.mean ? '$' + Math.round(data.price_statistics.mean) : 'N/A';
                document.getElementById('stat-avg-price').innerText = avgPrice;
            } catch (err) {
                console.error("Failed to load summary:", err);
            }
        }

        // Search and render hotels
        async function applyFilters() {
            const keyword = document.getElementById('filter-keyword').value;
            const region = document.getElementById('filter-region').value;
            const type = document.getElementById('filter-type').value;
            const wifi = document.getElementById('amenity-wifi').checked;
            const pool = document.getElementById('amenity-pool').checked;
            const parking = document.getElementById('amenity-parking').checked;
            const ac = document.getElementById('amenity-ac').checked;
            const restaurant = document.getElementById('amenity-restaurant').checked;
            const pet = document.getElementById('amenity-pet').checked;
            const wheelchair = document.getElementById('amenity-wheelchair').checked;

            const params = new URLSearchParams();
            if (keyword) params.append('q', keyword);
            if (region) params.append('region', region);
            if (type) params.append('property_type', type);
            if (wifi) params.append('has_wifi', 'true');
            if (pool) params.append('has_pool', 'true');
            if (parking) params.append('has_parking', 'true');
            if (ac) params.append('has_ac', 'true');
            if (restaurant) params.append('has_restaurant', 'true');
            if (pet) params.append('is_pet_friendly', 'true');
            if (wheelchair) params.append('is_wheelchair', 'true');
            params.append('page_size', '100');

            try {
                const res = await fetch(`/api/v1/hotels/search?${params.toString()}`);
                const data = await res.json();
                currentHotels = data.items || [];
                document.getElementById('results-count').innerText = data.total;
                renderHotelList(currentHotels);
                renderMapMarkers(currentHotels);
            } catch (err) {
                console.error("Search failed:", err);
            }
        }

        function renderHotelList(hotels) {
            const listEl = document.getElementById('hotel-list');
            listEl.innerHTML = '';
            
            if (hotels.length === 0) {
                listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px;">No properties match current filters.</div>';
                return;
            }

            hotels.forEach(h => {
                const item = document.createElement('div');
                item.className = 'hotel-item';
                item.onclick = () => focusHotel(h);
                
                const stars = h.stars ? '⭐ ' + h.stars : '';
                const price = h.price_min ? `$${h.price_min}/night` : '';

                item.innerHTML = `
                    <div>
                        <div class="hotel-item-name">${h.name}</div>
                        <div class="hotel-item-sub">${h.property_type.toUpperCase()} • ${h.city || h.region || 'Unknown Location'}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: var(--accent-amber); font-size: 11px; font-weight: 600;">${stars}</div>
                        <div style="color: var(--accent-emerald); font-size: 12px; font-weight: 700;">${price}</div>
                    </div>
                `;
                listEl.appendChild(item);
            });
        }

        function renderMapMarkers(hotels) {
            markersGroup.clearLayers();
            if (!hotels || hotels.length === 0) return;

            const bounds = [];

            hotels.forEach(h => {
                if (!h.latitude || !h.longitude) return;

                const latLng = [h.latitude, h.longitude];
                bounds.push(latLng);

                const marker = L.circleMarker(latLng, {
                    radius: 7,
                    fillColor: h.stars >= 4 ? '#f59e0b' : '#3b82f6',
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: 0.85
                });

                const popupContent = `
                    <div class="popup-hotel">
                        <div class="popup-badge">${h.property_type.toUpperCase()}</div>
                        <div class="popup-title">${h.name}</div>
                        <div class="popup-info">📍 ${h.formatted_address || `${h.latitude.toFixed(4)}, ${h.longitude.toFixed(4)}`}</div>
                        ${h.phone ? `<div class="popup-info">📞 ${h.phone}</div>` : ''}
                        ${h.website ? `<div class="popup-info"><a href="${h.website}" target="_blank" style="color: #60a5fa;">🌐 Official Website</a></div>` : ''}
                        <div style="display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap;">
                            ${h.has_wifi ? '<span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">📶 WiFi</span>' : ''}
                            ${h.has_pool ? '<span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">🏊 Pool</span>' : ''}
                            ${h.has_parking ? '<span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">🚗 Parking</span>' : ''}
                            ${h.has_air_conditioning ? '<span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">❄️ AC</span>' : ''}
                        </div>
                        ${h.price_min ? `<div class="popup-price">Est. $${h.price_min} - $${h.price_max} / night</div>` : ''}
                    </div>
                `;

                marker.bindPopup(popupContent);
                markersGroup.addLayer(marker);
            });

            if (bounds.length > 0) {
                map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
            }
        }

        function focusHotel(hotel) {
            if (hotel.latitude && hotel.longitude) {
                map.setView([hotel.latitude, hotel.longitude], 15);
            }
        }

        function onRegionChange() {
            const regId = document.getElementById('filter-region').value;
            if (regId) {
                const found = regionsList.find(r => r.id === regId);
                if (found) {
                    map.setView([found.center_lat, found.center_lon], 11);
                }
            }
            applyFilters();
        }

        function debounceSearch() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(applyFilters, 300);
        }

        function resetFilters() {
            document.getElementById('filter-keyword').value = '';
            document.getElementById('filter-region').value = '';
            document.getElementById('filter-type').value = '';
            ['wifi', 'pool', 'parking', 'ac', 'restaurant', 'pet', 'wheelchair'].forEach(id => {
                document.getElementById('amenity-' + id).checked = false;
            });
            applyFilters();
        }

        // Pipeline Run Trigger
        async function triggerPipelineRun() {
            const selectVal = document.getElementById('pipeline-region-select').value;
            const reqBody = {
                regions: selectVal === 'all' ? null : [selectVal],
                export_formats: ["csv", "parquet", "sqlite"]
            };

            const btn = document.getElementById('btn-run-pipeline');
            btn.disabled = true;
            btn.innerText = '⏳ Ingesting...';

            const progressSection = document.getElementById('pipeline-progress-section');
            progressSection.style.display = 'flex';

            try {
                await fetch('/api/v1/pipeline/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(reqBody)
                });
                pollPipelineStatus();
            } catch (err) {
                console.error("Pipeline trigger error:", err);
                btn.disabled = false;
                btn.innerText = '🚀 Run Ingestion Pipeline';
            }
        }

        // Poll Pipeline Status
        function pollPipelineStatus() {
            const interval = setInterval(async () => {
                try {
                    const res = await fetch('/api/v1/pipeline/status');
                    const status = await res.json();
                    
                    document.getElementById('pipeline-step-text').innerText = status.current_step;
                    document.getElementById('pipeline-pct-text').innerText = status.progress_pct + '%';
                    document.getElementById('pipeline-progress-fill').style.width = status.progress_pct + '%';

                    if (!status.is_running) {
                        clearInterval(interval);
                        document.getElementById('btn-run-pipeline').disabled = false;
                        document.getElementById('btn-run-pipeline').innerText = '🚀 Run Ingestion Pipeline';
                        loadSummary();
                        applyFilters();
                    }
                } catch (e) {
                    clearInterval(interval);
                }
            }, 1000);
        }

        function exportData(format) {
            window.open(`/api/v1/dataframe/export?format=${format}`, '_blank');
        }

        // Boot
        window.addEventListener('DOMContentLoaded', async () => {
            initMap();
            await loadRegions();
            await loadSummary();
            await applyFilters();
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
