import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import HistoricalDataViewer from "../HistoricalDataViewer";
import { SearchReport } from "@/types";

describe("HistoricalDataViewer component", () => {
  const mockReport: SearchReport = {
    report_id: "rep-123",
    demo: true,
    config_version: "v1.0",
    timestamp: "2026-10-16T12:00:00Z",
    location: {
      display_name: "Karachi Division, Sindh, Pakistan",
      lat: 24.8607,
      lon: 67.0011,
      radius_km: 5.0,
      bbox: [66.9, 24.7, 67.1, 24.9],
    },
    area_score: {
      safety_score: 55,
      band: { min: 40, max: 60, label: "Moderate Risk", code: "MOD", description: "Caution" },
      confidence: "high",
      S_static: 30,
      S_dynamic: 25,
      S_total: 55,
      no_active_hazards: false,
    },
    contributions: [],
    coverage: {},
    sources: {},
    geojson: { type: "FeatureCollection", features: [] },
    hotels_ranked: [],
    same_area_warning: false,
    disclaimer: "Test disclaimer",
    historical_stats: {
      location_name: "Karachi Division, Sindh, Pakistan",
      timeframe: "2021 – 2026",
      summary: {
        total_conflicts: 38,
        total_fatalities: 12,
        total_disasters: 9,
        volatility_index: "Elevated",
        volatility_score: 64,
        trend_direction: "stable",
        trend_pct: -6.5,
        primary_threat: "Armed Clashes & Civil Unrest",
        disaster_threat: "Monsoon Floods & Overflow",
      },
      yearly_trends: [
        { year: "2021", conflict_events: 8, conflict_fatalities: 3, natural_disasters: 2, disaster_severity_index: 3.5 },
        { year: "2022", conflict_events: 10, conflict_fatalities: 4, natural_disasters: 3, disaster_severity_index: 4.8 },
        { year: "2023", conflict_events: 8, conflict_fatalities: 2, natural_disasters: 2, disaster_severity_index: 3.9 },
        { year: "2024", conflict_events: 6, conflict_fatalities: 2, natural_disasters: 1, disaster_severity_index: 2.8 },
        { year: "2025", conflict_events: 4, conflict_fatalities: 1, natural_disasters: 1, disaster_severity_index: 2.2 },
        { year: "2026", conflict_events: 2, conflict_fatalities: 0, natural_disasters: 0, disaster_severity_index: 1.2 },
      ],
      conflict_breakdown: [
        { category: "Armed Clashes & Battles", count: 16, percentage: 42, metric_label: "Fatalities", metric_value: 8, severity: "severe" },
        { category: "Protests & Civic Demonstrations", count: 12, percentage: 32, metric_label: "Crowd Actions", metric_value: 12, severity: "moderate" },
      ],
      disaster_breakdown: [
        { category: "Monsoon Floods & Overflow", count: 5, percentage: 55, metric_label: "Alerts", metric_value: "Orange", severity: "high" },
        { category: "Severe Coastal Storms", count: 4, percentage: 45, metric_label: "Max Gusts", metric_value: "80 km/h", severity: "moderate" },
      ],
      incident_log: [
        {
          id: "log-1",
          date: "2026-09-14",
          category: "conflict",
          title: "Transit Checkpoint Security Alert in Karachi",
          source: "ACLED",
          location: "Karachi Central Corridor",
          distance_km: 3.5,
          fatalities: 0,
          severity: "Moderate",
          description: "Targeted verification operations conducted safely.",
        },
        {
          id: "log-2",
          date: "2026-08-20",
          category: "protest",
          title: "Civic Demonstration on Commercial Avenue",
          source: "News Wire",
          location: "Karachi Central Boulevard",
          distance_km: 2.1,
          fatalities: 0,
          severity: "Low",
          description: "Peaceful rally regarding municipal utility tariffs.",
        },
        {
          id: "log-3",
          date: "2026-07-15",
          category: "protest",
          title: "Student Climate Assembly and Rally",
          source: "Verified News Feed",
          location: "Karachi Civic Square",
          distance_km: 1.8,
          fatalities: 0,
          severity: "Low",
          description: "Civic environmental youth gathering.",
        },
        {
          id: "log-4",
          date: "2026-06-10",
          category: "disaster",
          title: "Monsoon Inundation Warning near Drainage Basin",
          source: "GDACS",
          location: "Southern Lowland Reach",
          distance_km: 4.2,
          fatalities: 0,
          severity: "Moderate",
          description: "Torrential runoff caused temporary roadway waterlogging.",
        },
        {
          id: "log-5",
          date: "2026-05-02",
          category: "protest",
          title: "Transport Workers Union March",
          source: "Local News",
          location: "Karachi Port Axis",
          distance_km: 3.0,
          fatalities: 0,
          severity: "Low",
          description: "Orderly labor procession safely concluded.",
        },
      ],
    },
  };

  it("renders header and summary metrics correctly", () => {
    render(<HistoricalDataViewer report={mockReport} />);
    expect(screen.getByText(/HISTORICAL INTELLIGENCE & MULTI-HAZARD TRENDS/i)).toBeDefined();
    expect(screen.getByText("38")).toBeDefined(); // Total conflicts
    expect(screen.getByText("9")).toBeDefined(); // Total disasters
    expect(screen.getByText("Elevated")).toBeDefined(); // Volatility index
  });

  it("switches to armed conflicts tab on click", () => {
    render(<HistoricalDataViewer report={mockReport} />);
    const conflictTabBtn = screen.getByRole("button", { name: /Armed Conflicts/i });
    fireEvent.click(conflictTabBtn);

    expect(screen.getByText(/Armed Conflict Categories & Civilian Exposure/i)).toBeDefined();
    expect(screen.getByText(/Armed Clashes & Battles/i)).toBeDefined();
  });

  it("switches to natural disasters tab on click", () => {
    render(<HistoricalDataViewer report={mockReport} />);
    const disasterTabBtn = screen.getByRole("button", { name: /Natural Disasters/i });
    fireEvent.click(disasterTabBtn);

    expect(screen.getByText(/Natural Disaster Classifications & Severity/i)).toBeDefined();
    expect(screen.getByText(/Monsoon Floods & Overflow/i)).toBeDefined();
  });

  it("switches to incident log tab and filters items", () => {
    render(<HistoricalDataViewer report={mockReport} />);
    const logTabBtn = screen.getByRole("button", { name: /Incident Log/i });
    fireEvent.click(logTabBtn);

    expect(screen.getByText(/Documented Regional Incident Log/i)).toBeDefined();
    expect(screen.getByText(/Transit Checkpoint Security Alert in Karachi/i)).toBeDefined();

    // Verify Protests filter button exists and filters protest records
    const protestFilterBtn = screen.getByRole("button", { name: /Protests \(News\)/i });
    expect(protestFilterBtn).toBeDefined();
    fireEvent.click(protestFilterBtn);

    // Verify protest records are displayed
    const protestBadges = screen.getAllByText(/Protest • News/i);
    expect(protestBadges.length).toBeGreaterThan(0);
  });

  it("handles pagination in incident log", () => {
    render(<HistoricalDataViewer report={mockReport} />);
    const logTabBtn = screen.getByRole("button", { name: /Incident Log/i });
    fireEvent.click(logTabBtn);

    // Should render pagination controls
    expect(screen.getByText(/Showing/i)).toBeDefined();
    const nextBtn = screen.getByLabelText(/Next page/i);
    expect(nextBtn).toBeDefined();
    fireEvent.click(nextBtn);

    // Safe page advanced
    expect(screen.getByLabelText(/Previous page/i)).toBeDefined();
  });
});
