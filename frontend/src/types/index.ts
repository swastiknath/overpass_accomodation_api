export interface ScoreBand {
  min: number;
  max: number;
  label: string;
  code: string;
  description: string;
}

export interface WeightBreakdown {
  base_weight: number;
  confidence: number;
  resolution_factor: number;
  temporal_decay: number;
  spatial_kernel: number;
  effective_weight: number;
}

export interface SignalContribution {
  evidence_ref: string;
  hazard_type: string;
  source: string;
  human_label: string;
  sigma: number;
  weight: number;
  contribution: number;
  event_time?: string;
  age_hours?: number;
  resolution_tier: string;
  distance_km: number;
  config_parameters: WeightBreakdown;
}

export interface AccessToHelp {
  hospital_distance_km?: number | null;
  police_distance_km?: number | null;
  fire_station_distance_km?: number | null;
  hospital_name?: string | null;
  police_name?: string | null;
  fire_station_name?: string | null;
}

export interface RankBreakdown {
  rank_score: number;
  safety_norm: number;
  quality_norm?: number | null;
  alpha: number;
  quality_weight: number;
  attributes_used: string[];
  limited_info: boolean;
  explanation: string;
}

export interface ProximityPoint {
  name: string;
  distance_km: number;
  type: string;
  walk_min?: number;
}

export interface CrawledReview {
  source: string;
  snippet: string;
  sentiment: string;
  date?: string;
  reviewer_type?: string;
  reviewer_name?: string;
  rating?: number;
  badge?: string;
}

export interface Hotel {
  id: string;
  name: string;
  lat: number;
  lon: number;
  source: string;
  source_id: string;
  category: string;
  stars?: number | null;
  rating?: number | null;
  review_count?: number | null;
  price_band?: string | null;
  amenities: string[];
  address?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  reception_hours?: string | null;
  distance_to_query_km: number;
  review_snippet?: string | null;
  women_safety_score?: number | null;
  women_safety_features?: string[];
  fire_safety_score?: number | null;
  fire_safety_features?: string[];
  proximity_points?: ProximityPoint[];
  crawled_reviews?: CrawledReview[];
  booking_url?: string | null;
  brand?: string | null;
  brand_tier?: string | null;
  brand_amenities?: string[];
  is_hostel_or_solo?: boolean;
  nearest_hub?: string | null;
  is_nearest_location?: boolean;
}

export interface WeatherDayForecast {
  date: string;
  temp_max_c?: number | null;
  temp_min_c?: number | null;
  precipitation_sum_mm?: number | null;
  rain_sum_mm?: number | null;
  precip_probability_max?: number | null;
  wind_speed_max_kmh?: number | null;
  uv_index_max?: number | null;
  weather_code?: number | null;
  us_aqi?: number | null;
  aqi_category?: string;
}

export interface AirQualityInfo {
  us_aqi?: number | null;
  pm2_5?: number | null;
  pm10?: number | null;
  category?: string;
  source?: string;
}

export interface WeatherCurrentConditions {
  temperature_c?: number | null;
  apparent_temperature_c?: number | null;
  humidity_pct?: number | null;
  precipitation_mm?: number | null;
  rain_mm?: number | null;
  weather_code?: number | null;
  wind_speed_kmh?: number | null;
  wind_direction_deg?: number | null;
  pressure_hpa?: number | null;
  observation_time?: string;
}

export interface WeatherAndAirQuality {
  source?: string;
  current_conditions?: WeatherCurrentConditions;
  air_quality?: AirQualityInfo;
  forecast_3day?: WeatherDayForecast[];
  forecast_15day?: WeatherDayForecast[];
  warnings?: any[];
  rainfall_mm_24h?: number;
}

export interface HotelScored {
  hotel: Hotel;
  safety_score: number;
  score_band: ScoreBand;
  S_static: number;
  S_dynamic: number;
  top_contributions: SignalContribution[];
  differentiating_factors: SignalContribution[];
  access_to_help: AccessToHelp;
  rank_score: number;
  rank_breakdown: RankBreakdown;
  limited_info: boolean;
}

export interface NewsArticle {
  title: string;
  url: string;
  source: string;
  seendate?: string;
  category?: string;
  snippet?: string;
}

export interface SearchReport {
  report_id: string;
  demo: boolean;
  config_version: string;
  timestamp: string;
  location: {
    display_name: string;
    lat: number;
    lon: number;
    radius_km: number;
    district?: string | null;
    state?: string | null;
    country?: string | null;
    is_in_india?: boolean;
    bbox: [number, number, number, number];
  };
  is_in_india?: boolean;
  area_score: {
    safety_score: number;
    band: ScoreBand;
    confidence: "high" | "medium" | "low";
    S_static: number;
    S_dynamic: number;
    S_total: number;
    no_active_hazards: boolean;
    safety_decision?: DecisionOutput;
  };
  safety_decision?: DecisionOutput;
  contributions: SignalContribution[];
  coverage: Record<string, string>;
  sources: Record<string, { status: string; last_fetched?: string; data_effective_date?: string; error?: string }>;
  geojson: any;
  news_articles?: NewsArticle[];
  hotels_ranked: HotelScored[];
  same_area_warning: boolean;
  weather_and_air_quality?: WeatherAndAirQuality;
  travel_advisories?: TravelAdvisoryInfo | null;
  river_flood_telemetry?: RiverFloodTelemetry | null;
  cyclone_telemetry?: CycloneTelemetry | null;
  historical_stats?: HistoricalStats;
  crime_statistics?: CrimeStatistics;
  disclaimer: string;
  disambiguation_candidates?: GeocodeCandidate[];
  radius_expanded?: boolean;
  original_radius_km?: number;
  effective_radius_km?: number;
  radius_expansion_message?: string | null;
}

export interface RiverForecastPoint {
  date: string;
  is_past?: boolean;
  water_level_m: number | null;
  normal_level_m?: number | null;
  warning_level_m?: number | null;
  danger_level_m?: number | null;
  hfl_m?: number | null;
  discharge_m3s: number;
  discharge_max_m3s?: number;
  discharge_min_m3s?: number;
  discharge_cusecs: number;
  rainfall_mm?: number;
  flood_probability_pct?: number;
  stage: "normal" | "watch" | "warning" | "danger" | string;
  stage_label: string;
}

export interface RiverYearlyFlowTrend {
  year: string;
  mean_discharge_m3s: number;
  mean_discharge_cusecs: number;
  peak_discharge_m3s: number;
  peak_discharge_cusecs: number;
  min_discharge_m3s: number;
  peak_date: string;
  high_flow_days: number;
}

export interface RiverHistoricalFlowStats {
  timeframe: string;
  total_observed_days: number;
  mean_discharge_m3s: number;
  mean_discharge_cusecs: number;
  median_discharge_m3s: number;
  p90_watch_discharge_m3s: number;
  p98_danger_discharge_m3s: number;
  peak_discharge_m3s: number | null;
  peak_discharge_cusecs: number | null;
  peak_date: string | null;
  flow_anomaly_pct: number | null;
  yearly_flow_trends: RiverYearlyFlowTrend[];
  recent_observed_30d: RiverForecastPoint[];
}

export interface CycloneForecastDay {
  date: string;
  max_wind_speed_kmh: number;
  max_wind_gust_kmh: number;
  min_pressure_hpa: number;
  precipitation_mm: number;
  precip_probability_pct?: number;
  imd_category: string;
  cyclone_risk_pct: number;
}

export interface ActiveTropicalCyclone {
  event_id: string;
  name: string;
  title?: string;
  summary?: string;
  alert_level: string;
  is_current?: boolean;
  from_date?: string;
  to_date?: string;
  lat: number;
  lon: number;
  max_wind_kmh: number;
  imd_category: string;
  affected_countries?: string;
  affected_population?: number | string | null;
  report_url?: string;
  cap_url?: string;
  distance_km: number;
  in_impact_zone: boolean;
  country_match?: boolean;
}

export interface CycloneBulletin {
  id?: string;
  title: string;
  authority?: string;
  publisher?: string;
  date?: string;
  severity?: string;
  url?: string;
  is_local?: boolean;
  area?: string;
}

export interface CycloneYearlyTrend {
  year: string;
  cyclonic_storm_days: number;
  depression_gale_days: number;
  max_wind_gust_kmh: number;
  max_sustained_wind_kmh: number;
  min_pressure_hpa: number;
  max_daily_rain_mm: number;
  peak_date: string;
  peak_category: string;
}

export interface CycloneNotableEvent {
  date: string;
  peak_wind_gust_kmh: number;
  max_sustained_wind_kmh: number;
  min_pressure_hpa: number;
  rainfall_mm: number;
  imd_category: string;
}

export interface CycloneTelemetry {
  location_name: string;
  is_in_india: boolean;
  monitoring_authority: string;
  active_alert_status: string;
  realtime_conditions: {
    observation_time: string;
    sustained_wind_kmh: number;
    wind_gust_kmh: number;
    wind_direction_deg: number;
    surface_pressure_hpa: number;
    sea_level_pressure_hpa: number;
    pressure_drop_hpa: number;
    precipitation_mm: number;
    imd_category: string;
  };
  imminent_outlook: {
    has_imminent_cyclone_threat: boolean;
    threat_level: "Low" | "Watch" | "Elevated" | "Severe" | string;
    headline: string;
    peak_forecast_date: string;
    peak_forecast_wind_gust_kmh: number;
    peak_forecast_sustained_wind_kmh: number;
    min_forecast_pressure_hpa: number;
    max_daily_rainfall_mm: number;
    peak_imd_category: string;
    nearest_active_cyclone: ActiveTropicalCyclone | null;
    forecast_15day: CycloneForecastDay[];
  };
  active_global_and_basin_cyclones: ActiveTropicalCyclone[];
  live_bulletins: CycloneBulletin[];
  historical_archive: {
    timeframe: string;
    total_archived_days: number;
    total_cyclonic_storm_days: number;
    total_depression_gale_days: number;
    max_historical_wind_gust_kmh: number;
    max_historical_wind_date: string;
    min_historical_pressure_hpa: number;
    yearly_trends: CycloneYearlyTrend[];
    notable_events: CycloneNotableEvent[];
  };
  data_sources?: string[];
}

export interface IndiaAuthorityBulletin {
  id: string;
  hazard_type: "flood" | "earthquake" | "fire" | string;
  title: string;
  authority: string;
  publisher?: string;
  date: string;
  severity: string;
  url?: string;
}

export interface FloodWatchIndiaLiveInfo {
  live_cwc_telemetry?: boolean;
  station_code?: string;
  station_name?: string;
  observed_water_level_m?: number | null;
  last_observed_at?: string | null;
  hourly_readings?: Array<{
    timestamp: string;
    water_level_m: number;
  }>;
  hourly_trend?: string;
  forecasted_water_level_m?: number | null;
  forecasted_at?: string | null;
  station_alert_status?: string;
  active_national_warnings_count?: number;
  active_national_warnings?: Array<{
    station_code: string;
    status: string;
    trend: string;
    water_level_m: number;
  }>;
  sachet_cap_alerts_count?: number;
  source_portal?: string;
  sachet_cap_feed?: string;
}

export interface RiverFloodTelemetry {
  is_in_india: boolean;
  has_river_in_city?: boolean;
  rivers_in_city?: string[];
  flow_data_available?: boolean;
  city: string;
  state?: string | null;
  country?: string | null;
  river_name: string;
  basin?: string | null;
  cwc_station?: string | null;
  cwc_station_code?: string | null;
  upstream_control?: string | null;
  current_water_level_m: number | null;
  normal_level_m: number | null;
  warning_level_m: number | null;
  danger_level_m: number | null;
  hfl_m: number | null;
  hfl_year?: number | null;
  margin_to_warning_m: number | null;
  margin_to_danger_m: number | null;
  current_discharge_m3s: number | null;
  current_discharge_cusecs: number | null;
  current_stage: "normal" | "watch" | "warning" | "danger" | string;
  current_stage_label: string;
  inflow_trend: "Rising" | "Receding" | "Steady" | string;
  peak_7d_water_level_m: number | null;
  peak_7d_date: string;
  peak_7d_discharge_m3s: number | null;
  peak_7d_stage_label: string;
  flood_probability_7d_pct: number | null;
  prediction_summary: string;
  seismic_zone?: string | null;
  historical_flow_stats?: RiverHistoricalFlowStats | null;
  floodwatch_india?: FloodWatchIndiaLiveInfo | null;
  authorities: {
    flood: string;
    earthquake?: string;
    wildfire?: string;
    sdma?: string;
    helpline?: string;
  };
  forecast_15day: RiverForecastPoint[];
  ncs_recent_earthquakes?: Array<{
    id: string;
    magnitude: number;
    depth_km: number;
    place: string;
    distance_km: number;
    event_time: string;
    authority: string;
    url?: string;
  }>;
  indian_authority_bulletins?: IndiaAuthorityBulletin[];
  data_sources?: string[];
}

export interface CrimeYearData {
  year: string;
  total_cognizable_crimes: number;
  violent_crimes: number;
  property_thefts: number;
  cyber_fraud: number;
  crime_rate_per_100k: number;
  safety_clearance_rate: number;
}

export interface CrimeCategoryDetail {
  category: string;
  count: number;
  rate_per_100k: number;
  share_pct: number;
  trend: "declining" | "stable" | "increasing";
  severity: "low" | "moderate" | "high";
}

export interface RealtimeCrimeIncident {
  title: string;
  url: string;
  source: string;
  published_at?: string;
  category?: string;
  severity?: "low" | "moderate" | "high";
  snippet?: string;
  location?: string;
}

export interface CrimeStatistics {
  source_agency: string;
  district_or_region: string;
  country: string;
  timeframe: string;
  headline: string;
  overall_safety_index: number;
  safety_band: "High Safety" | "Moderate Caution" | "Heightened Vigilance" | "Elevated Risk";
  violent_crime_risk: "Low" | "Moderate" | "Elevated";
  tourist_night_safety: "High" | "Moderate" | "Caution Advised";
  women_safety_index: number;
  five_year_trend_pct: number;
  trend_direction: "declining" | "stable" | "increasing";
  yearly_series: CrimeYearData[];
  categories: CrimeCategoryDetail[];
  legal_framework: string;
  data_provenance: string;
  realtime_incidents?: RealtimeCrimeIncident[];
}

export interface HistoricalYearData {
  year: string;
  conflict_events: number;
  conflict_fatalities: number;
  natural_disasters: number;
  disaster_severity_index: number;
  felt_earthquakes?: number;
  max_earthquake_magnitude?: number | null;
  river_high_flow_days?: number | null;
  river_peak_discharge_m3s?: number | null;
  cyclonic_storm_days?: number;
  max_wind_gust_kmh?: number | null;
}

export interface HazardCategoryBreakdown {
  category: string;
  count: number;
  percentage: number;
  metric_label: string;
  metric_value: string | number;
  severity: "low" | "moderate" | "high" | "severe";
}

export interface HistoricalIncidentItem {
  id: string;
  date: string;
  category: "conflict" | "disaster" | "civil" | "weather" | "protest";
  title: string;
  source: string;
  location: string;
  distance_km?: number;
  fatalities?: number;
  severity?: string;
  description: string;
  url?: string;
}

export interface HistoricalStats {
  location_name: string;
  timeframe: string;
  summary: {
    total_conflicts: number;
    total_fatalities: number;
    total_disasters: number;
    volatility_index: "Low" | "Moderate" | "Elevated" | "High";
    volatility_score: number;
    trend_direction: "declining" | "stable" | "elevated";
    trend_pct: number;
    primary_threat: string;
    disaster_threat: string;
  };
  yearly_trends: HistoricalYearData[];
  conflict_breakdown: HazardCategoryBreakdown[];
  disaster_breakdown: HazardCategoryBreakdown[];
  incident_log: HistoricalIncidentItem[];
  data_availability?: Record<string, string>;
}

export interface GovTravelAdvisoryItem {
  authority: string;
  country: string;
  country_code: string;
  flag: string;
  level: number;
  level_label: string;
  status_color: string;
  summary: string;
  helpline?: string | null;
  embassy_contact?: string | null;
  registration_url?: string | null;
  official_link?: string | null;
  issued_date?: string | null;
}

export interface TravelAdvisoryInfo {
  country: string;
  level: number;
  level_label: string;
  summary: string;
  link?: string;
  pub_date?: string;
  active_warning?: boolean;
  status_color?: string;
  is_domestic_safe?: boolean;
  matched_term?: string;
  sources?: {
    india_mea?: GovTravelAdvisoryItem;
    us_state_dept?: GovTravelAdvisoryItem;
    uk_fcdo?: GovTravelAdvisoryItem;
  };
  advisories_list?: GovTravelAdvisoryItem[];
}

export interface GeocodeCandidate {
  display_name: string;
  lat: number;
  lon: number;
  bbox: [number, number, number, number];
  type: string;
  state?: string | null;
  district?: string | null;
  country: string;
  is_in_india: boolean;
  h3_cell?: string | null;
}

export interface NarratorKeyDriver {
  factor: string;
  plain_language: string;
  evidence_ref: string;
}

export interface NarratorOutput {
  headline: string;
  summary: string;
  key_drivers: NarratorKeyDriver[];
  caveats: string[];
  hotel_comparison: string;
}

export interface OfficialAuthority {
  name: string;
  url?: string | null;
  helpline?: string | null;
}

export interface CuratedAdviceItem {
  hazard_type: string;
  hazard_name: string;
  tips: string[];
  authorities: OfficialAuthority[];
}

export interface DecisionOutput {
  choice: "safe" | "caution" | "unsafe" | string;
  confidence: number;
  probabilities: Record<string, number>;
  model: string;
}

export interface ExplanationResponse {
  narrative_status: "verified" | "unverified" | "fallback_template" | "unavailable";
  narrative: NarratorOutput;
  curated_advice: CuratedAdviceItem[];
  decision?: DecisionOutput;
  verification_details: Record<string, any>;
  model_used?: string | null;
  cached: boolean;
  config_version: string;
}
