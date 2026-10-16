import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ScorePanel from "../ScorePanel";
import { SearchReport } from "@/types";

const mockReport: SearchReport = {
  report_id: "rep_test1",
  demo: true,
  config_version: "2026.1",
  timestamp: "2026-10-16T10:00:00Z",
  location: {
    display_name: "Manali, Himachal Pradesh, India",
    lat: 32.2396,
    lon: 77.1887,
    radius_km: 5.0,
    district: "Kullu",
    state: "Himachal Pradesh",
    bbox: [77.15, 32.21, 77.22, 32.27],
  },
  area_score: {
    safety_score: 76,
    band: {
      min: 65,
      max: 79,
      label: "Moderate Risk",
      code: "moderate",
      description: "Localized weather/civil alerts present. Exercise standard precautions.",
    },
    confidence: "high",
    S_static: 0.15,
    S_dynamic: 0.10,
    S_total: 0.24,
    no_active_hazards: false,
  },
  contributions: [],
  coverage: { flood: "contributing", weather: "contributing" },
  sources: {},
  geojson: { type: "FeatureCollection", features: [] },
  hotels_ranked: [],
  same_area_warning: false,
  disclaimer: "Research tool disclaimer.",
};

describe("ScorePanel Component", () => {
  it("renders large 0-100 safety score", () => {
    render(<ScorePanel report={mockReport} />);
    const scoreEl = screen.getByText("76");
    expect(scoreEl).toBeInTheDocument();
  });

  it("renders explicit band label text (not color alone)", () => {
    render(<ScorePanel report={mockReport} />);
    const bandLabel = screen.getByText("Moderate Risk");
    expect(bandLabel).toBeInTheDocument();
  });

  it("renders confidence label badge", () => {
    render(<ScorePanel report={mockReport} />);
    const confBadge = screen.getByText("High Confidence");
    expect(confBadge).toBeInTheDocument();
  });

  it("displays static and dynamic sub-scores with explanations", () => {
    render(<ScorePanel report={mockReport} />);
    expect(screen.getByText("Static Terrain & Baseline")).toBeInTheDocument();
    expect(screen.getByText("Live & Dynamic Hazards")).toBeInTheDocument();
    expect(screen.getByText("Risk: 15%")).toBeInTheDocument();
    expect(screen.getByText("Risk: 10%")).toBeInTheDocument();
  });
});
