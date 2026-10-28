import { GeocodeCandidate, SearchReport, ExplanationResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchGeocode(query: string): Promise<GeocodeCandidate[]> {
  const url = `${API_BASE_URL}/v1/geocode?q=${encodeURIComponent(query)}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Geocoding failed with status ${resp.status}`);
  }
  return resp.json();
}

export async function fetchSearchReport(params: {
  q?: string;
  lat?: number;
  lon?: number;
  radius_km?: number;
  alpha?: number;
  max_hotels?: number;
}): Promise<SearchReport> {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.lat !== undefined && params.lon !== undefined) {
    searchParams.set("lat", params.lat.toString());
    searchParams.set("lon", params.lon.toString());
  }
  if (params.radius_km !== undefined) searchParams.set("radius_km", params.radius_km.toString());
  if (params.alpha !== undefined) searchParams.set("alpha", params.alpha.toString());
  if (params.max_hotels !== undefined) searchParams.set("max_hotels", params.max_hotels.toString());

  const url = `${API_BASE_URL}/v1/search-report?${searchParams.toString()}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    const errorData = await resp.json().catch(() => null);
    if (resp.status === 400 && errorData?.error === "out_of_coverage") {
      throw new Error(errorData.message || "Location is outside India territory.");
    }
    throw new Error(errorData?.detail || `Search report failed with status ${resp.status}`);
  }
  return resp.json();
}

export async function fetchExplanation(reportId: string): Promise<ExplanationResponse> {
  const url = `${API_BASE_URL}/v1/explanation`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: jsonStringifySafe({ report_id: reportId }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => null);
    throw new Error(err?.detail || `Explanation request failed with status ${resp.status}`);
  }
  return resp.json();
}

function jsonStringifySafe(data: any): string {
  return JSON.stringify(data);
}
