import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CrimeStatisticsVisualizer from "../CrimeStatisticsVisualizer";
import { SearchReport } from "@/types";

describe("CrimeStatisticsVisualizer component", () => {
  const mockReport: SearchReport = {
    report_id: "rep-crime-test",
    demo: false,
    config_version: "v1.0",
    timestamp: "2026-10-17T12:00:00Z",
    location: {
      display_name: "Sindh, Pakistan",
      lat: 25.8943,
      lon: 68.5247,
      radius_km: 10.0,
      bbox: [68.0, 25.0, 69.0, 26.0],
    },
    area_score: {
      safety_score: 52,
      band: { min: 40, max: 60, label: "Moderate Caution", code: "MOD", description: "Caution" },
      confidence: "high",
      S_static: 30,
      S_dynamic: 22,
      S_total: 52,
      no_active_hazards: false,
    },
    contributions: [],
    coverage: { crime: "contributing" },
    sources: { crime: { status: "active", last_fetched: "2026-10-17T12:00:00Z" } },
    geojson: { type: "FeatureCollection", features: [] },
    hotels_ranked: [],
    same_area_warning: false,
    disclaimer: "Test disclaimer",
    crime_statistics: {
      source_agency: "UNODC South Asia Crime Telemetry & Sindh Police Records",
      district_or_region: "Sindh",
      country: "Pakistan",
      timeframe: "2021 – 2026",
      headline: "5-Year Longitudinal Crime & Public Safety Audit for Sindh",
      overall_safety_index: 54,
      safety_band: "Moderate Caution",
      violent_crime_risk: "Moderate",
      tourist_night_safety: "Moderate",
      women_safety_index: 58,
      five_year_trend_pct: -9.4,
      trend_direction: "declining",
      yearly_series: [
        { year: "2021", total_cognizable_crimes: 44160, violent_crimes: 6912, property_thefts: 19968, cyber_fraud: 4416, crime_rate_per_100k: 258.2, safety_clearance_rate: 72.4 },
        { year: "2022", total_cognizable_crimes: 41472, violent_crimes: 6528, property_thefts: 19200, cyber_fraud: 4976, crime_rate_per_100k: 242.5, safety_clearance_rate: 75.1 },
        { year: "2023", total_cognizable_crimes: 39168, violent_crimes: 6144, property_thefts: 18816, cyber_fraud: 5483, crime_rate_per_100k: 229.0, safety_clearance_rate: 78.6 },
        { year: "2024", total_cognizable_crimes: 36480, violent_crimes: 5760, property_thefts: 18048, cyber_fraud: 5836, crime_rate_per_100k: 213.3, safety_clearance_rate: 82.0 },
        { year: "2025", total_cognizable_crimes: 34560, violent_crimes: 5376, property_thefts: 17664, cyber_fraud: 6220, crime_rate_per_100k: 202.0, safety_clearance_rate: 85.3 },
        { year: "2026", total_cognizable_crimes: 33024, violent_crimes: 5376, property_thefts: 17280, cyber_fraud: 6274, crime_rate_per_100k: 193.1, safety_clearance_rate: 87.8 },
      ],
      categories: [
        { category: "Violent Crimes (Assault, Grievous Hurt, Armed Robbery)", count: 6144, rate_per_100k: 35.9, share_pct: 16.0, trend: "declining", severity: "moderate" },
        { category: "Property Crimes (Burglary, Vehicle Theft, Pickpocketing)", count: 18816, rate_per_100k: 110.0, share_pct: 49.0, trend: "declining", severity: "low" },
        { category: "Cyber & Financial Frauds (Phishing, Online Scams)", count: 7296, rate_per_100k: 42.6, share_pct: 19.0, trend: "increasing", severity: "moderate" },
        { category: "Women Safety & Public Harassment Incidents", count: 3072, rate_per_100k: 17.9, share_pct: 8.0, trend: "declining", severity: "low" },
        { category: "Public Order & Commercial Infractions", count: 3072, rate_per_100k: 17.9, share_pct: 8.0, trend: "stable", severity: "low" },
      ],
      legal_framework: "Pakistan Penal Code (PPC) & Provincial Police Telemetry",
      data_provenance: "Official Police & UNODC Public Telemetry Registry (Normalized per 100,000 population)",
    },
  };

  it("renders 5-year crime statistics visualizer header and badges", () => {
    render(<CrimeStatisticsVisualizer report={mockReport} />);

    expect(screen.getByText(/5-Year Crime Statistics & Public Safety Audit/i)).toBeInTheDocument();
    expect(screen.getByText("2021 – 2026")).toBeInTheDocument();
    expect(screen.getByText("54")).toBeInTheDocument(); // Overall safety score
    expect(screen.getByText("Moderate Caution")).toBeInTheDocument();
    expect(screen.getByText("-9.4%")).toBeInTheDocument(); // 5-year crime delta
  });

  it("renders metric switcher buttons and changes active metric", () => {
    render(<CrimeStatisticsVisualizer report={mockReport} />);

    const violentBtn = screen.getByRole("button", { name: /violent crime/i });
    expect(violentBtn).toBeInTheDocument();
    fireEvent.click(violentBtn);

    expect(screen.getByText(/Violent & Street Crimes/i)).toBeInTheDocument();

    const clearanceBtn = screen.getByRole("button", { name: /clearance %/i });
    fireEvent.click(clearanceBtn);
    expect(screen.getByText(/Investigation Clearance Rate/i)).toBeInTheDocument();
  });

  it("renders crime categories breakdown and legal provenance", () => {
    render(<CrimeStatisticsVisualizer report={mockReport} />);

    expect(screen.getByText(/Offense Classification & Incidence Distribution/i)).toBeInTheDocument();
    expect(screen.getByText(/Violent Crimes \(Assault, Grievous Hurt, Armed Robbery\)/i)).toBeInTheDocument();
    expect(screen.getByText(/UNODC South Asia Crime Telemetry & Sindh Police Records/i)).toBeInTheDocument();
  });

  it("handles missing crime_statistics gracefully using location fallback", () => {
    const reportWithoutCrime: SearchReport = {
      ...mockReport,
      crime_statistics: undefined,
    };
    render(<CrimeStatisticsVisualizer report={reportWithoutCrime} />);

    expect(screen.getByText(/5-Year Crime Statistics & Public Safety Audit/i)).toBeInTheDocument();
    expect(screen.getByText("2021 – 2026")).toBeInTheDocument();
  });

  it("switches to Live Real-Time Crime Feed tab and displays incident dispatches", () => {
    const reportWithRealtime: SearchReport = {
      ...mockReport,
      crime_statistics: {
        ...mockReport.crime_statistics!,
        realtime_incidents: [
          {
            title: "Sindh Police deployment intensified across highway checkpoints",
            url: "https://www.sindhpolice.gov.pk/test",
            source: "Sindh Police Central Dispatch",
            published_at: "1h ago",
            category: "Police Enforcement & Arrests",
            severity: "low",
            snippet: "Patrol teams deployed to monitor tourist transit hubs.",
            location: "Sindh",
          },
        ],
      },
    };

    render(<CrimeStatisticsVisualizer report={reportWithRealtime} />);

    // Click Live Crime Feed tab
    const liveFeedTab = screen.getByRole("button", { name: /live crime feed/i });
    expect(liveFeedTab).toBeInTheDocument();
    fireEvent.click(liveFeedTab);

    expect(screen.getByText(/Live Crime & Police Dispatch Telemetry/i)).toBeInTheDocument();
    expect(screen.getByText(/Sindh Police deployment intensified across highway checkpoints/i)).toBeInTheDocument();
    expect(screen.getByText(/Sindh Police Central Dispatch/i)).toBeInTheDocument();
    expect(screen.getByText(/Police Enforcement & Arrests/i)).toBeInTheDocument();
  });

  it("displays verified honest zero-crime clear status when realtime_incidents is empty without serving fake data", () => {
    const reportEmptyRealtime: SearchReport = {
      ...mockReport,
      crime_statistics: {
        ...mockReport.crime_statistics!,
        realtime_incidents: [],
      },
    };

    render(<CrimeStatisticsVisualizer report={reportEmptyRealtime} />);

    const liveFeedTab = screen.getByRole("button", { name: /live crime feed/i });
    fireEvent.click(liveFeedTab);

    expect(screen.getByText(/No Active Crime Alerts or Severe Incidents Reported/i)).toBeInTheDocument();
    expect(screen.getByText(/Surveillance Active • Zero Critical Warnings/i)).toBeInTheDocument();
  });
});
