# India Travel Safety & Accommodation Intelligence Platform

A production-ready, deterministic multi-hazard safety intelligence and hotel ranking system designed for India. The system combines real-time geo-hazard feeds, satellite anomaly detections, conflict statistics, district crime baselines, and OpenStreetMap accommodations with a transparent Noisy-OR fusion engine and a verified OpenRouter LLM narration layer.

---

## Non-Negotiable Design Principles

1. **Deterministic Scoring**: Safety scores (0–100) are computed strictly by mathematical fusion. LLMs **never** compute, adjust, or override risk scores. LLMs only narrate and audit pre-computed results.
2. **Score Decomposition**: Every response decomposes into individual hazard contributions, static vs. dynamic sub-scores, and a coverage audit.
3. **Missing Data is Not Zero Risk**: A failed or empty source is excluded from calculation and flagged in the coverage report, never silently treated as safe ($\sigma \neq 0$).
4. **Resilient Architecture**: Scores and hotel rankings render immediately without LLM dependencies. If OpenRouter is slow, capped, or unconfigured, verified deterministic templates are served.
5. **Freshness & Research Disclaimer**: Every report carries source freshness timestamps, config version, and a disclaimer that this is a research tool, not a replacement for official NDMA/IMD advisories.
6. **India-Only Scope**: Coordinates outside India territory are rejected with a clear out-of-coverage response.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    Next.js 16 (App Router) Frontend    │
                      │  Tailwind CSS • MapLibre GL • Query    │
                      └──────────────────┬─────────────────────┘
                                         │ HTTP
                                         ▼
                      ┌────────────────────────────────────────┐
                      │           FastAPI Gateway              │
                      │  Rate Limiting • CORS • Caching        │
                      └──────┬──────────────────────────┬──────┘
                             │                          │
              ┌──────────────┴──────────────┐           │ POST /v1/explanation
              │ GET /v1/search-report       │           │ (Cached Report ID)
              ▼                             ▼           ▼
┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
│   Geocoding & Spatial    │   │  Concurrent Connectors   │   │ OpenRouter LLM Layer     │
│   Nominatim / H3 Res 7   │   │  GDACS • USGS • FIRMS    │   │  1. Sanitized Narrator   │
│   District Boundaries    │   │  ACLED • Crime • Weather │   │  2. Deterministic Number │
└─────────────┬────────────┘   │  GDELT • Bhuvan Atlas    │   │     & Evidence Auditor   │
              │                └────────────┬─────────────┘   │  3. Model Verifier       │
              │                             │                 │  4. Fallback Template    │
              └──────────────┬──────────────┘                 └─────────────┬────────────┘
                             ▼                                              │
              ┌─────────────────────────────┐                               │
              │  Deterministic Fusion Engine│                               │
              │  • Per-Signal Normalization │                               │
              │  • Spatial/Temporal Decay   │                               │
              │  • Noisy-OR Aggregation     │                               │
              │  • Missing Data Exclusion   │                               │
              └──────────────┬──────────────┘                               │
                             │                                              │
                             ▼                                              │
              ┌─────────────────────────────┐                               │
              │   Accommodations Module     │                               │
              │  • Overpass Provider        │                               │
              │  • Local Per-Hotel Scoring  │                               │
              │  • Emergency Help Proximity │                               │
              │  • Transparent α-Ranking    │                               │
              └──────────────┬──────────────┘                               │
                             │                                              │
                             └──────────────────────┬───────────────────────┘
                                                    ▼
                                    ┌──────────────────────────────┐
                                    │ Unified JSON + GeoJSON Output│
                                    └──────────────────────────────┘
```

---

## Mathematical Fusion Methodology

All fusion parameters are defined in `config/fusion_config.yaml` and version-tagged.

### 1. Per-Signal Normalization ($\sigma_i \in [0, 1]$)
- **Landslide Susceptibility**: Model probability used directly: $\sigma = \text{prob} \in [0, 1]$.
- **Flood / Cyclone (GDACS)**: Ordinal anchors: Green = $0.20$, Orange = $0.55$, Red = $0.90$.
- **Earthquake (USGS)**: Sigmoid centered at magnitude $M_0 = 5.0$ with steepness $k = 1.2$:
  $$\sigma = \frac{1}{1 + e^{-k(M - M_0)}}$$
- **Fire (NASA FIRMS)**: Source confidence field normalized: $\sigma = \frac{\text{confidence}}{100}$.
- **Conflict (ACLED)**:
  $$\sigma = (1 - e^{-\lambda \cdot \text{fatalities}}) \times \text{multiplier}[\text{event\_type}]$$
  where $\lambda = 0.25$ and multipliers follow $\text{protest } (0.35) < \text{riot } (0.65) < \text{armed clash } (1.00)$.
- **Crime (data.gov.in / NCRB)**: District percentile rank across all national districts for the recorded year: $\sigma = \text{percentile} \in [0, 1]$.
- **Weather (Open-Meteo / IMD)**: Threshold ramp based on 24-hour rainfall and peak wind speed against configured extreme triggers.
- **Local News (GDELT DOC 2.0)**:
  $$\sigma = \min\left(1.0, \, c_{\text{conf}} \cdot \text{tone\_severity} \cdot \text{recency\_decay} \cdot \frac{\ln(1 + \text{count})}{\ln(1 + \text{norm})}\right)$$

### 2. Effective Weight ($w_i$)
$$w_i = \text{base\_weight}(\text{hazard}) \times c_i \times d(\text{tier}) \times g_{\text{hazard}}(\text{age}) \times K_{\text{hazard}}(\text{distance})$$
- $c_i$: Source / classifier confidence factor.
- $d(\text{tier})$: Resolution tier multiplier: Point = $1.0$, Polygon = $0.85$, District = $0.60$.
- $g_{\text{hazard}}(\text{age})$: Temporal half-life decay: $g = 2^{-\text{age} / t_{\text{half}}}$. Static layers do not decay ($g = 1.0$).
- $K_{\text{hazard}}(\text{distance})$: Gaussian spatial kernel:
  $$K(d) = \exp\left(-\frac{d^2}{2s^2}\right)$$
  For district-tier signals, $K = 1.0$ inside the district and $0.0$ outside.
- Every term $w_i \cdot \sigma_i$ is clamped to $[0, 1]$.

### 3. Noisy-OR Aggregation
Risk is aggregated independently across static and dynamic layers:
$$S_{\text{static}} = 1 - \prod_{i \in \text{static}} (1 - w_i \sigma_i)$$
$$S_{\text{dynamic}} = 1 - \prod_{i \in \text{dynamic}} (1 - w_i \sigma_i)$$
$$S_{\text{total}} = 1 - (1 - S_{\text{static}})(1 - S_{\text{dynamic}})$$
$$\text{safety\_score} = \text{round}(100 \times (1 - S_{\text{total}})) \in [0, 100]$$

### 4. Explainability & Contributions
$$\text{contribution}_i = \frac{w_i \sigma_i}{\sum_j w_j \sigma_j}$$
If no active hazards exist ($\sum = 0$), returns an empty contribution list and flags `no_active_hazards: true` without division errors.

### 5. Transparent Hotel Ranking
$$\text{rank\_score} = \alpha \cdot \text{safety\_norm} + (1 - \alpha) \cdot \text{quality\_norm}$$
- $\alpha \in [0, 1]$ (default $0.7$, adjustable via slider).
- $\text{quality\_norm}$ normalizes only present attributes (stars, guest rating weighted by review count, price tier).
- Missing attributes **never penalize** rank: properties without quality data are scored purely on safety with `limited_info: true`.
- Tie-breaks use distance to query point.
- **Same Area Warning**: If score spread between best and worst hotel is below $\epsilon = 2.5$, the system flags `same_area_warning: true` notifying the user that accommodations share uniform area exposure.

---

## Component Implementation Status

| Component | Status | Implementation Details |
| :--- | :---: | :--- |
| **Deterministic Fusion Engine** | **REAL** | Full Noisy-OR aggregation, Gaussian spatial kernels, exponential temporal decay, and explainability breakdown. |
| **OSM Overpass Hotel Provider** | **REAL** | Free Overpass API integration querying hotels, hostels, guest houses, and computing emergency hospital/police/fire distances. |
| **Google Places Provider** | **STUB** | Stubbed with `TODO(operator)` behind `HotelProvider` interface. |
| **Foursquare Provider** | **STUB** | Stubbed with `TODO(operator)` behind `HotelProvider` interface. |
| **Amadeus Hospitality Provider** | **STUB** | Stubbed with `TODO(operator)` behind `HotelProvider` interface. |
| **Nominatim Geocoding** | **REAL** | Pluggable geocoder with 1 req/sec rate limiting, in-memory cache, and `countrycodes=in`. |
| **Photon / Mapbox Geocoding** | **BEST-EFFORT** | Implemented as configurable providers falling back to Nominatim when keys are absent. |
| **GDACS / USGS / FIRMS Alerts** | **REAL** | Unified async connector for real-time flood, earthquake, and active fire anomalies. |
| **ACLED Conflict Connector** | **REAL** | Ingests political violence and protest records; enforces licensing redistribution boundaries. |
| **NCRB Crime Statistics** | **REAL** | data.gov.in district IPC crime percentile baseline ingestion. |
| **Open-Meteo & IMD Weather** | **REAL** | 24h precipitation, wind thresholds, atmospheric risk, and IMD warning alerts. |
| **GDELT News Client** | **REAL** | DOC 2.0 API ingestion with NER correction and keyword classification. |
| **ISRO Bhuvan Client** | **BEST-EFFORT** | WMS/WFS raster downloader; subject to ISRO portal uptime and IP access controls. |
| **OpenRouter Narrator & Verifier** | **REAL** | Two-model architecture (Narrator + Verifier) with deterministic number checking, budget limits, and fallback template. |
| **Curated Safety Advice** | **BEST-EFFORT** | Attached deterministically from `config/advice_catalog.yaml`. Currently marked as **PLACEHOLDER** awaiting operator review. |
| **Next.js Web Frontend** | **REAL** | Responsive App Router, MapLibre GL map, TanStack Query, progressive rendering, WCAG AA contrast. |

---

## Assumptions

1. **Geographic Coverage**: India territory is bounded by EPSG:4326 envelope $[68.0, 6.0, 97.5, 37.5]$. Coordinates outside this bounding box are rejected as out-of-coverage.
2. **Overpass Public Endpoint**: Public Overpass instances (`overpass-api.de`) are rate-limited and intended for development/demonstration. High-volume production deployments should point `OVERPASS_URL` to a self-hosted instance.
3. **OSM Accommodation Completeness**: OpenStreetMap accommodation tags often lack guest review ratings or price tiers. Missing quality attributes are treated as absent, not zero quality.
4. **Licensing Redistribution Restrictions**: Under ACLED academic terms, `REDISTRIBUTION_ALLOWED=false` causes the API to suppress raw lat/lon coordinates and detailed notes in public GeoJSON, emitting only aggregated H3 cell and derived metrics.
5. **Ordinal Hazard Anchor Calibration**: GDACS alerts are mapped to ordinal anchors (Green 0.2, Orange 0.55, Red 0.9). These parameters are expert-assigned priors marked in `fusion_config.yaml` to be calibrated against empirical damage data.

---

## Manual Operator Review Checklist

Before promoting to live public production, the operator must complete these manual tasks:

- [ ] **Review `config/advice_catalog.yaml`**: Validate all official emergency helpline numbers (e.g., NDMA 1078, Unified 112) and state-specific disaster authority links.
- [ ] **Calibrate Fusion Weights**: Calibrate the expert-assigned prior weights in `config/fusion_config.yaml` using historical incident datasets.
- [ ] **Provision Live Connector Credentials**:
  - OpenRouter API Key (`OPENROUTER_API_KEY`)
  - ACLED credentials (`ACLED_EMAIL`, `ACLED_PASSWORD`)
  - NASA FIRMS Map Key (`FIRMS_MAP_KEY`)
  - data.gov.in API Key (`DATAGOV_API_KEY`)
  - ISRO Bhuvan portal credentials (`BHUVAN_USERNAME`, `BHUVAN_PASSWORD`)
- [ ] **Select Production OpenRouter Models**: Choose your preferred narrator (`OPENROUTER_MODEL_NARRATOR`) and verifier (`OPENROUTER_MODEL_VERIFIER`) model IDs.
- [ ] **Select Production Map Tile Provider**: Replace the demo MapLibre tile style URL (`MAP_STYLE_URL`) with an API key from MapTiler, Stadia Maps, or a self-hosted vector tile server.
- [ ] **Commercial Hotel Provider**: If desired, implement the Google Places or Amadeus hotel provider stubs in `backend/hotels/provider.py`.

---

## Live Data Mode & Operating Pipeline

The system is configured by default for **Live Data Operation (`DEMO_MODE=false`)**:

1. **Live Multi-Hazard Connectors**:
   - **USGS**: Real-time M2.5+ earthquake alerts across India envelope.
   - **Open-Meteo**: Live 24h precipitation, wind speeds, atmospheric pressure, and 3-day weather forecasts.
   - **GDACS**: Global multi-hazard alerts (cyclones, floods, earthquakes).
   - **ISRO Bhuvan / NRSC**: Geospatial indexing across 6,670+ national/state thematic layers and private landing zone geo-hazard feeds (`data/landing/private/bhuvan/`).
   - **OpenStreetMap Overpass & Nominatim**: Real-time accommodation discovery (hotels, resorts, guest houses, hostels) with multi-mirror failover and live calculation of proximity to hospitals, police stations, and fire services.
   - **GDELT DOC 2.0**: Live local news ingestion, sentiment scoring, and recency decay.

2. **Resilience & Missing-Data Safety**:
   - If a third-party upstream source experiences temporary network downtime or rate limiting, it is never silently assumed safe ($\sigma \neq 0$). The source is logged and reported under `coverage[source] = "source_failed"` with mathematical Noisy-OR normalization.

---

## Quickstart: Running with Live Data

### 1. Run with Docker Compose
```bash
docker compose up --build
```
- **Web Frontend**: http://localhost:3000
- **FastAPI Documentation**: http://localhost:8000/docs
- **Health Endpoint**: http://localhost:8000/v1/health

### 2. Run Locally (Development Mode)

#### Backend:
```bash
cd backend
source ../india-travel-safety/.venv/bin/activate
# Start FastAPI server in live mode
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## Running Test Suites

Run the unified test runner to execute both backend and frontend suites:
```bash
./run_tests.sh
```

Or run individual suites:

### Backend Tests (Pytest)
```bash
PYTHONPATH=backend ./india-travel-safety/.venv/bin/pytest backend/tests/ -v
```
Expected output: **26 passed** (0 failures).

### Frontend Component Tests (Vitest)
```bash
npm --prefix frontend run test
```
Expected output: **9 passed** (0 failures).

### End-to-End Smoke Test (Playwright)
```bash
npm --prefix frontend run test:e2e
```

---

## Environment Variables Reference

See `.env.example` for all configurable keys.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DEMO_MODE` | `false` | When false, queries live external feeds; when true, serves fixtures. |
| `OPENROUTER_API_KEY` | `""` | Server-side OpenRouter bearer key. Never sent to frontend. |
| `OPENROUTER_MODEL_NARRATOR` | `anthropic/claude-3.5-sonnet` | Model ID for narrative generation. |
| `OPENROUTER_MODEL_VERIFIER` | `openai/gpt-4o-mini` | Model ID for independent fact verification. |
| `OPENROUTER_FALLBACK_MODELS` | `["google/gemini-2.0-flash-001", ...]` | Ordered fallback chain on 429/5xx. |
| `LLM_DAILY_BUDGET_USD` | `10.0` | Maximum daily spend cap on OpenRouter. |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Overpass API mirror endpoint. |
| `NOMINATIM_USER_AGENT` | `IndiaTravelSafety/2.0 (...)` | Required identifying User-Agent for Nominatim OSM policy. |
| `ALLOWED_ORIGINS` | `["*"]` | CORS origin allowlist. |
| `REDISTRIBUTION_ALLOWED` | `true` | Licensing toggle for raw record redistribution. |
