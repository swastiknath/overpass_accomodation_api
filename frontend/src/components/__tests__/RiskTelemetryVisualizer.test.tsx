import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RiskTelemetryVisualizer from "../RiskTelemetryVisualizer";
import { SearchReport } from "@/types";

describe("RiskTelemetryVisualizer component", () => {
  const mockReport: SearchReport = {
    report_id: "rep-radar-1",
    demo: true,
    config_version: "v1.0",
    timestamp: "2026-10-16T12:00:00Z",
    location: {
      display_name: "New Delhi, Delhi, India",
      lat: 28.6139,
      lon: 77.209,
      radius_km: 5.0,
      bbox: [77.1, 28.5, 77.3, 28.7],
    },
    area_score: {
      safety_score: 72,
      band: { min: 60, max: 80, label: "Exercise Increased Caution", code: "CAUTION", description: "Caution" },
      confidence: "high",
      S_static: 0.30,
      S_dynamic: 0.18,
      S_total: 0.48,
      no_active_hazards: false,
    },
    contributions: [
      {
        evidence_ref: "acled:1",
        hazard_type: "conflict",
        source: "acled",
        human_label: "Civil Protest Activity",
        sigma: 0.7,
        weight: 0.8,
        contribution: 0.55,
        resolution_tier: "point",
        distance_km: 2.1,
        config_parameters: {
          base_weight: 1.0,
          confidence: 0.9,
          resolution_factor: 1.0,
          temporal_decay: 0.9,
          spatial_kernel: 0.9,
          effective_weight: 0.8,
        },
      },
      {
        evidence_ref: "crime:1",
        hazard_type: "crime",
        source: "crime",
        human_label: "District Crime Baseline",
        sigma: 0.5,
        weight: 0.6,
        contribution: 0.45,
        resolution_tier: "district",
        distance_km: 0.0,
        config_parameters: {
          base_weight: 1.0,
          confidence: 0.8,
          resolution_factor: 0.8,
          temporal_decay: 1.0,
          spatial_kernel: 1.0,
          effective_weight: 0.6,
        },
      },
    ],
    coverage: {
      conflict: "contributing",
      crime: "contributing",
      weather: "no_signal_found",
    },
    sources: {},
    geojson: { type: "FeatureCollection", features: [] },
    hotels_ranked: [],
    same_area_warning: false,
    disclaimer: "Test disclaimer",
  };

  it("renders header and combined multi-line plot by default", () => {
    render(<RiskTelemetryVisualizer report={mockReport} />);
    expect(screen.getByText(/Hazard Spectrum & Multi-Line Plot/i)).toBeDefined();
    expect(screen.getByText(/Combined Multi-Hazard Telemetry & Trajectory/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /Combined Line Plot/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Armed Conflicts/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /Protests & Civic Actions/i })).toBeDefined();
    expect(screen.getByText(/Static Baseline:/i)).toBeDefined();
  });

  it("switches to Threat Share view on click", () => {
    render(<RiskTelemetryVisualizer report={mockReport} />);
    const threatShareBtn = screen.getByRole("button", { name: /Threat Share/i });
    fireEvent.click(threatShareBtn);

    expect(screen.getByText(/Proportional Hazard Contribution/i)).toBeDefined();
    expect(screen.getByText(/Civil Protest Activity/i)).toBeDefined();
    expect(screen.getByText(/District Crime Baseline/i)).toBeDefined();
  });
});
