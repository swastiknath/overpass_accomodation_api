import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import HotelDetailModal from "../HotelDetailModal";
import { HotelScored } from "@/types";

const mockHotelScored: HotelScored = {
  hotel: {
    id: "h_test",
    name: "Grand Orchid Resort & Suites",
    lat: 28.6139,
    lon: 77.209,
    source: "osm",
    source_id: "999",
    category: "hotel",
    stars: 5,
    rating: 4.8,
    review_count: 320,
    price_band: "luxury",
    amenities: ["High-Speed WiFi", "24/7 Security", "Swimming Pool", "Private Parking"],
    address: "Connaught Place, New Delhi",
    website: "https://example.com/orchid",
    phone: "+91 11 2345 6789",
    distance_to_query_km: 0.8,
    review_snippet: "Pristine cleanliness and 24/7 guarded security.",
    women_safety_score: 96,
    women_safety_features: [
      "24/7 Staffed Front Desk & Verified Night Guard",
      "Keycard-Controlled Elevator & Floor Access",
      "Well-Lit Corridors & Perimeter Security Surveillance",
    ],
    fire_safety_score: 95,
    fire_safety_features: [
      "Optoelectronic Smoke Detectors in Every Room",
      "Commercial ABC Multi-Purpose Fire Extinguishers",
    ],
    proximity_points: [
      { name: "Metro / Subway Station", distance_km: 0.4, type: "transit", walk_min: 5 },
      { name: "Central Market", distance_km: 0.9, type: "commercial", walk_min: 11 },
    ],
    crawled_reviews: [
      {
        source: "Tripadvisor Verified",
        snippet: "Remarkably safe and dependable hotel for solo female business travelers.",
        sentiment: "positive",
        reviewer_type: "Solo Female Traveler",
      },
    ],
    booking_url: "https://www.google.com/travel/hotels?q=Grand+Orchid+booking",
  },
  safety_score: 89,
  score_band: { min: 80, max: 100, label: "Low Risk", code: "low", description: "Safe" },
  S_static: 0.1,
  S_dynamic: 0.05,
  top_contributions: [],
  differentiating_factors: [],
  access_to_help: {
    hospital_distance_km: 1.1,
    hospital_name: "City Central Multi-Specialty Hospital",
    police_distance_km: 0.6,
    police_name: "Connaught Beat Police Station",
    fire_station_distance_km: 1.8,
    fire_station_name: "Fire Headquarters",
  },
  rank_score: 0.92,
  rank_breakdown: {
    rank_score: 0.92,
    safety_norm: 0.89,
    quality_norm: 0.95,
    alpha: 0.7,
    quality_weight: 0.3,
    attributes_used: ["stars", "rating"],
    limited_info: false,
    explanation: "Top tier accommodation with high security.",
  },
  limited_info: false,
};

describe("HotelDetailModal", () => {
  it("renders hotel modal with women safety, fire safety, and emergency proximity", () => {
    const handleClose = vi.fn();
    render(<HotelDetailModal hotelScored={mockHotelScored} onClose={handleClose} />);

    // Name and header elements
    expect(screen.getByText("Grand Orchid Resort & Suites")).toBeInTheDocument();
    expect(screen.getByText("96")).toBeInTheDocument(); // Women safety score
    expect(screen.getByText("95")).toBeInTheDocument(); // Fire safety score

    // Features and emergency proximity
    expect(screen.getByText("24/7 Staffed Front Desk & Verified Night Guard")).toBeInTheDocument();
    expect(screen.getByText("Connaught Beat Police Station")).toBeInTheDocument();
    expect(screen.getByText("City Central Multi-Specialty Hospital")).toBeInTheDocument();

    // Key places
    expect(screen.getByText("Metro / Subway Station")).toBeInTheDocument();

    // Reviews and booking button
    expect(
      screen.getByText(/Remarkably safe and dependable hotel for solo female business travelers/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Proceed to Booking")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", () => {
    const handleClose = vi.fn();
    render(<HotelDetailModal hotelScored={mockHotelScored} onClose={handleClose} />);

    const closeButtons = screen.getAllByRole("button", { name: /close/i });
    fireEvent.click(closeButtons[0]);
    expect(handleClose).toHaveBeenCalled();
  });

  it("does not render fake contacts or fake reviews when properties lack listed details", () => {
    const unlistedHotel: HotelScored = {
      ...mockHotelScored,
      hotel: {
        ...mockHotelScored.hotel,
        phone: null,
        email: null,
        crawled_reviews: [],
      },
    };
    render(<HotelDetailModal hotelScored={unlistedHotel} onClose={vi.fn()} />);

    // Assert absence of fake fallbacks
    expect(screen.queryByText("+91 191 254 0000")).not.toBeInTheDocument();
    expect(screen.queryByText("reservations@propertyhotel.com")).not.toBeInTheDocument();
    expect(screen.queryByText("Priya Sharma")).not.toBeInTheDocument();
    expect(screen.queryByText("Marcus Vance")).not.toBeInTheDocument();

    // Assert authentic unlisted notices
    expect(screen.getByText("Not publicly listed in registry")).toBeInTheDocument();
    expect(screen.getByText("Direct email not publicly listed")).toBeInTheDocument();
    expect(
      screen.getByText(/No online guest reviews have been indexed for this specific property yet/i)
    ).toBeInTheDocument();
  });
});
