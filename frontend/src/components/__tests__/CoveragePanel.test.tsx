import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ExplanationPanel from "../ExplanationPanel";
import { SearchReport } from "@/types";

const mockReport: SearchReport = {
  report_id: "rep_test2",
  demo: false,
  config_version: "2026.1",
  timestamp: "2026-10-16T10:00:00Z",
  location: {
    display_name: "Test Location",
    lat: 28.6139,
    lon: 77.2090,
    radius_km: 5.0,
    bbox: [77.0, 28.5, 77.3, 28.7],
  },
  area_score: {
    safety_score: 80,
    band: { min: 80, max: 100, label: "Low Risk", code: "low", description: "Stable" },
    confidence: "medium",
    S_static: 0.1,
    S_dynamic: 0.1,
    S_total: 0.2,
    no_active_hazards: false,
  },
  contributions: [
    {
      evidence_ref: "fl_1",
      hazard_type: "flood",
      source: "gdacs",
      human_label: "Flood Alert",
      sigma: 0.5,
      weight: 0.8,
      contribution: 1.0,
      resolution_tier: "point",
      distance_km: 2.5,
      config_parameters: {
        base_weight: 0.85,
        confidence: 0.9,
        resolution_factor: 1.0,
        temporal_decay: 0.95,
        spatial_kernel: 0.8,
        effective_weight: 0.58,
      },
    },
  ],
  coverage: {
    flood: "contributing",
    cyclone: "no_signal_found",
    earthquake: "source_failed",
    landslide: "not_available_for_region",
  },
  sources: {},
  geojson: { type: "FeatureCollection", features: [] },
  hotels_ranked: [],
  same_area_warning: false,
  disclaimer: "Disclaimer",
};

describe("Coverage & Explanation Panel Component", () => {
  it("renders top driver with contribution percentage and human label", () => {
    render(<ExplanationPanel report={mockReport} />);
    expect(screen.getByText("Flood Alert")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders each coverage status explicitly so gaps are visible", () => {
    render(<ExplanationPanel report={mockReport} />);
    expect(screen.getByText("Active Signal")).toBeInTheDocument();
    expect(screen.getByText("No Hazard Detected")).toBeInTheDocument();
    expect(screen.getByText("Source Failed")).toBeInTheDocument();
    expect(screen.getByText("Not Available for Region")).toBeInTheDocument();
  });
});
