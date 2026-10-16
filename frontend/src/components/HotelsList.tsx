"use client";

import React, { useState } from "react";
import {
  Sliders,
  AlertTriangle,
  Hospital,
  Shield,
  Flame,
  Star,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  MapPin,
  Building,
} from "lucide-react";
import { HotelScored } from "@/types";

interface HotelsListProps {
  hotels: HotelScored[];
  sameAreaWarning: boolean;
  alpha: number;
  onAlphaChange: (newAlpha: number) => void;
  selectedHotelId: string | null;
  onSelectHotel: (id: string) => void;
}

export default function HotelsList({
  hotels,
  sameAreaWarning,
  alpha,
  onAlphaChange,
  selectedHotelId,
  onSelectHotel,
}: HotelsListProps) {
  const [expandedHotelId, setExpandedHotelId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [starsFilter, setStarsFilter] = useState<number>(0);
  const [maxDistanceKm, setMaxDistanceKm] = useState<number>(50);

  // Filter hotels locally
  const filteredHotels = hotels.filter((h) => {
    if (categoryFilter !== "all" && h.hotel.category !== categoryFilter) {
      return false;
    }
    if (starsFilter > 0 && (!h.hotel.stars || h.hotel.stars < starsFilter)) {
      return false;
    }
    if (h.hotel.distance_to_query_km > maxDistanceKm) {
      return false;
    }
    return true;
  });

  const toggleExpand = (id: string) => {
    setExpandedHotelId(expandedHotelId === id ? null : id);
  };

  const getBandBadge = (code: string) => {
    switch (code.toLowerCase()) {
      case "low":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
      case "moderate":
        return "bg-cyan-500/20 text-cyan-300 border-cyan-500/40";
      case "elevated":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "high":
        return "bg-orange-500/20 text-orange-300 border-orange-500/40";
      case "severe":
      default:
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
    }
  };

  return (
    <div
      aria-label="Accommodation Rankings"
      className="bg-slate-900/90 rounded-2xl p-5 border border-slate-800 shadow-xl space-y-5"
    >
      {/* Header & Alpha Slider */}
      <div className="space-y-3 border-b border-slate-800 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Building className="h-5 w-5 text-indigo-400" />
            <h3 className="text-base font-bold text-white tracking-tight">
              Accommodation Rankings
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              ({filteredHotels.length} listings)
            </span>
          </div>

          {/* Alpha Slider */}
          <div className="flex items-center gap-3 bg-slate-800/80 px-3 py-2 rounded-xl border border-slate-700/60">
            <Sliders className="h-3.5 w-3.5 text-indigo-400" />
            <label htmlFor="alpha-slider" className="text-xs text-slate-300 whitespace-nowrap font-medium">
              Safety Weight (α): <strong className="text-white font-mono">{Math.round(alpha * 100)}%</strong>
            </label>
            <input
              id="alpha-slider"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={alpha}
              onChange={(e) => onAlphaChange(parseFloat(e.target.value))}
              className="w-24 sm:w-32 accent-indigo-500 cursor-pointer"
            />
            <span className="text-[10px] text-slate-400 font-mono">
              {Math.round((1 - alpha) * 100)}% Quality
            </span>
          </div>
        </div>

        {/* Same Area Warning Banner */}
        {sameAreaWarning && (
          <div
            id="same-area-warning-banner"
            role="status"
            className="flex items-center gap-2 p-3 rounded-xl bg-amber-950/60 border border-amber-500/40 text-amber-200 text-xs leading-normal"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>
              <strong>Uniform District Exposure:</strong> Hotels in this area share virtually identical localized
              safety metrics (spread &lt; threshold). Relative ranks are driven predominantly by guest ratings,
              verified stars, and proximity to your search point.
            </span>
          </div>
        )}

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          {/* Category */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-slate-800 text-slate-300 border border-slate-700 rounded-lg px-2.5 py-1 focus:outline-none"
          >
            <option value="all">All Categories</option>
            <option value="hotel">Hotels</option>
            <option value="hostel">Hostels</option>
            <option value="guest_house">Guest Houses</option>
            <option value="apartment">Apartments</option>
          </select>

          {/* Stars */}
          <select
            value={starsFilter}
            onChange={(e) => setStarsFilter(parseInt(e.target.value))}
            className="bg-slate-800 text-slate-300 border border-slate-700 rounded-lg px-2.5 py-1 focus:outline-none"
          >
            <option value="0">All Stars</option>
            <option value="3">3+ Stars</option>
            <option value="4">4+ Stars</option>
            <option value="5">5 Stars only</option>
          </select>

          {/* Max Distance */}
          <select
            value={maxDistanceKm}
            onChange={(e) => setMaxDistanceKm(parseFloat(e.target.value))}
            className="bg-slate-800 text-slate-300 border border-slate-700 rounded-lg px-2.5 py-1 focus:outline-none"
          >
            <option value="50">Any Distance</option>
            <option value="2">Within 2 km</option>
            <option value="5">Within 5 km</option>
            <option value="10">Within 10 km</option>
          </select>
        </div>
      </div>

      {/* Hotels List */}
      <div className="space-y-3">
        {filteredHotels.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-400 bg-slate-850/50 rounded-xl border border-slate-800">
            No accommodations match the active category and distance filters.
          </div>
        ) : (
          filteredHotels.map((item: HotelScored, index: number) => {
            const isSelected = item.hotel.id === selectedHotelId;
            const isExpanded = item.hotel.id === expandedHotelId;
            const bandBadge = getBandBadge(item.score_band.code);

            return (
              <div
                key={item.hotel.id}
                id={`hotel-card-${item.hotel.id}`}
                className={`rounded-xl border transition-all ${
                  isSelected
                    ? "bg-slate-850 border-indigo-500 ring-1 ring-indigo-500 shadow-lg shadow-indigo-950/40"
                    : "bg-slate-800/60 hover:bg-slate-800 border-slate-700/60"
                }`}
              >
                {/* Main Card Header */}
                <div
                  className="p-4 cursor-pointer"
                  onClick={() => onSelectHotel(item.hotel.id)}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    {/* Hotel Info */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-800/40">
                          #{index + 1}
                        </span>
                        <h4 className="text-sm font-bold text-white hover:text-indigo-300 transition">
                          {item.hotel.name}
                        </h4>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span className="capitalize">{item.hotel.category.replace("_", " ")}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 text-slate-400" />
                          {item.hotel.distance_to_query_km} km away
                        </span>

                        {/* Quality attributes or limited info */}
                        {item.limited_info ? (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                            Limited Quality Info in OSM
                          </span>
                        ) : (
                          <>
                            {item.hotel.stars && (
                              <span className="flex items-center gap-0.5 text-amber-300 font-semibold text-xs">
                                <Star className="h-3 w-3 fill-amber-400" />
                                {item.hotel.stars}★
                              </span>
                            )}
                            {item.hotel.rating && (
                              <span className="text-slate-300 font-medium">
                                Rating: {item.hotel.rating}/5 ({item.hotel.review_count || 1} reviews)
                              </span>
                            )}
                            {item.hotel.price_band && (
                              <span className="capitalize text-slate-300">
                                Tier: {item.hotel.price_band}
                              </span>
                            )}
                          </>
                        )}
                      </div>
                    </div>

                    {/* Scores */}
                    <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 shrink-0">
                      <div className="text-right">
                        <span className="text-xs text-slate-400 block sm:inline mr-1">Rank Score:</span>
                        <span className="text-sm font-extrabold text-white font-mono">
                          {item.rank_score}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-slate-400">Safety:</span>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-bold border ${bandBadge}`}
                        >
                          {item.safety_score}/100 ({item.score_band.label})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Access to Help Proximity */}
                  <div className="mt-3 pt-2.5 border-t border-slate-700/50 flex flex-wrap items-center gap-3 text-xs text-slate-300">
                    <span className="text-[10px] uppercase font-semibold text-slate-400">
                      Emergency Proximity:
                    </span>
                    {item.access_to_help.hospital_distance_km !== null ? (
                      <span className="flex items-center gap-1">
                        <Hospital className="h-3 w-3 text-rose-400" />
                        Hospital: {item.access_to_help.hospital_distance_km} km
                      </span>
                    ) : null}
                    {item.access_to_help.police_distance_km !== null ? (
                      <span className="flex items-center gap-1">
                        <Shield className="h-3 w-3 text-blue-400" />
                        Police: {item.access_to_help.police_distance_km} km
                      </span>
                    ) : null}
                    {item.access_to_help.fire_station_distance_km !== null ? (
                      <span className="flex items-center gap-1">
                        <Flame className="h-3 w-3 text-orange-400" />
                        Fire Station: {item.access_to_help.fire_station_distance_km} km
                      </span>
                    ) : null}
                  </div>
                </div>

                {/* Why This Rank Expander Button */}
                <div className="px-4 pb-2.5">
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.hotel.id)}
                    className="text-xs font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    <span>Why is this hotel ranked #{index + 1}?</span>
                    {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>

                  {/* Expanded Breakdown */}
                  {isExpanded && (
                    <div className="mt-2 p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300 space-y-2">
                      <p className="text-slate-300 leading-relaxed font-mono">
                        {item.rank_breakdown.explanation}
                      </p>

                      {/* Differentiating Factors */}
                      {item.differentiating_factors.length > 0 && (
                        <div className="pt-2 border-t border-slate-800 space-y-1">
                          <span className="font-semibold text-slate-200 block text-[11px] uppercase tracking-wider">
                            Localized Differentiating Factors (vs Median Hotel):
                          </span>
                          <ul className="list-disc pl-4 space-y-0.5 text-slate-400">
                            {item.differentiating_factors.map((df, dIdx) => (
                              <li key={dIdx}>
                                <strong>{df.human_label}</strong> at {df.distance_km} km — contributing{" "}
                                {Math.round(df.contribution * 100)}% of this property&apos;s observed risk.
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
