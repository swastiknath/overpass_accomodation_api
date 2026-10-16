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
  distance_to_query_km: number;
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
    bbox: [number, number, number, number];
  };
  area_score: {
    safety_score: number;
    band: ScoreBand;
    confidence: "high" | "medium" | "low";
    S_static: number;
    S_dynamic: number;
    S_total: number;
    no_active_hazards: boolean;
  };
  contributions: SignalContribution[];
  coverage: Record<string, string>;
  sources: Record<string, { status: string; last_fetched?: string; data_effective_date?: string; error?: string }>;
  geojson: any;
  hotels_ranked: HotelScored[];
  same_area_warning: boolean;
  disclaimer: string;
  disambiguation_candidates?: GeocodeCandidate[];
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

export interface ExplanationResponse {
  narrative_status: "verified" | "unverified" | "fallback_template" | "unavailable";
  narrative: NarratorOutput;
  curated_advice: CuratedAdviceItem[];
  verification_details: Record<string, any>;
  model_used?: string | null;
  cached: boolean;
  config_version: string;
}
