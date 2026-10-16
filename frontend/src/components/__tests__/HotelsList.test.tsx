import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import HotelsList from "../HotelsList";
import { HotelScored } from "@/types";

const mockHotels: HotelScored[] = [
  {
    hotel: {
      id: "h1",
      name: "Luxury Alpine Resort",
      lat: 32.24,
      lon: 77.19,
      source: "osm",
      source_id: "1",
      category: "hotel",
      stars: 5,
      rating: 4.8,
      review_count: 150,
      price_band: "luxury",
      amenities: ["WiFi", "Pool"],
      distance_to_query_km: 1.0,
    },
    safety_score: 85,
    score_band: { min: 80, max: 100, label: "Low Risk", code: "low", description: "Safe" },
    S_static: 0.1,
    S_dynamic: 0.05,
    top_contributions: [],
    differentiating_factors: [],
    access_to_help: { hospital_distance_km: 1.2, police_distance_km: 0.8 },
    rank_score: 0.88,
    rank_breakdown: {
      rank_score: 0.88,
      safety_norm: 0.85,
      quality_norm: 0.95,
      alpha: 0.7,
      quality_weight: 0.3,
      attributes_used: ["stars", "rating"],
      limited_info: false,
      explanation: "Balanced score",
    },
    limited_info: false,
  },
  {
    hotel: {
      id: "h2",
      name: "Backpacker Lodge",
      lat: 32.25,
      lon: 77.18,
      source: "osm",
      source_id: "2",
      category: "hostel",
      stars: null,
      rating: null,
      review_count: null,
      price_band: null,
      amenities: ["WiFi"],
      distance_to_query_km: 2.5,
    },
    safety_score: 80,
    score_band: { min: 80, max: 100, label: "Low Risk", code: "low", description: "Safe" },
    S_static: 0.1,
    S_dynamic: 0.1,
    top_contributions: [],
    differentiating_factors: [],
    access_to_help: { hospital_distance_km: 2.0, police_distance_km: 1.5 },
    rank_score: 0.80,
    rank_breakdown: {
      rank_score: 0.80,
      safety_norm: 0.80,
      quality_norm: null,
      alpha: 0.7,
      quality_weight: 0.0,
      attributes_used: [],
      limited_info: true,
      explanation: "Safety only",
    },
    limited_info: true,
  },
];

describe("HotelsList Component", () => {
  it("renders hotels and their respective scores", () => {
    render(
      <HotelsList
        hotels={mockHotels}
        sameAreaWarning={false}
        alpha={0.7}
        onAlphaChange={vi.fn()}
        selectedHotelId={null}
        onSelectHotel={vi.fn()}
      />
    );
    expect(screen.getByText("Luxury Alpine Resort")).toBeInTheDocument();
    expect(screen.getByText("Backpacker Lodge")).toBeInTheDocument();
    expect(screen.getByText("Limited Quality Info in OSM")).toBeInTheDocument();
  });

  it("triggers onAlphaChange when alpha slider changes", () => {
    const handleAlpha = vi.fn();
    render(
      <HotelsList
        hotels={mockHotels}
        sameAreaWarning={false}
        alpha={0.7}
        onAlphaChange={handleAlpha}
        selectedHotelId={null}
        onSelectHotel={vi.fn()}
      />
    );

    const slider = screen.getByLabelText(/Safety Weight/i);
    fireEvent.change(slider, { target: { value: "0.9" } });
    expect(handleAlpha).toHaveBeenCalledWith(0.9);
  });

  it("displays same area warning banner when sameAreaWarning is true", () => {
    render(
      <HotelsList
        hotels={mockHotels}
        sameAreaWarning={true}
        alpha={0.7}
        onAlphaChange={vi.fn()}
        selectedHotelId={null}
        onSelectHotel={vi.fn()}
      />
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText(/Uniform District Exposure/i)).toBeInTheDocument();
  });
});
