"use client";

import React, { useState, useEffect } from "react";
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
  Quote,
  ChevronLeft,
  ChevronRight,
  Sparkles,
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
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 6;

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

  // Reset to page 1 on filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [categoryFilter, starsFilter, maxDistanceKm, hotels.length]);

  const totalPages = Math.max(1, Math.ceil(filteredHotels.length / pageSize));
  const paginatedHotels = filteredHotels.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const toggleExpand = (id: string) => {
    setExpandedHotelId(expandedHotelId === id ? null : id);
  };

  const getBandBadge = (code: string) => {
    switch (code.toLowerCase()) {
      case "low":
        return "bg-emerald-950/80 text-emerald-300 border-emerald-500/40";
      case "moderate":
        return "bg-cyan-950/80 text-cyan-300 border-cyan-500/40";
      case "elevated":
        return "bg-amber-950/80 text-amber-300 border-amber-500/40";
      case "high":
        return "bg-orange-950/80 text-orange-300 border-orange-500/40";
      case "severe":
      default:
        return "bg-rose-950/80 text-rose-300 border-rose-500/40";
    }
  };

  return (
    <div
      aria-label="Accommodation Rankings"
      className="bg-black rounded-2xl p-5 border border-zinc-800 shadow-2xl space-y-5"
    >
      {/* Header & Alpha Slider */}
      <div className="space-y-3 border-b border-zinc-800/80 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Building className="h-5 w-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white tracking-tight">
              Accommodation Rankings
            </h3>
            <span className="text-xs text-zinc-400 font-mono">
              ({filteredHotels.length} properties found)
            </span>
          </div>

          {/* Alpha Slider */}
          <div className="flex items-center gap-3 bg-zinc-950 px-3.5 py-2 rounded-xl border border-zinc-800">
            <Sliders className="h-3.5 w-3.5 text-cyan-400" />
            <label htmlFor="alpha-slider" className="text-xs text-zinc-300 whitespace-nowrap font-medium">
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
              aria-label="Alpha: Trade-off between safety and quality"
              className="w-24 sm:w-28 accent-cyan-400 cursor-pointer"
            />
          </div>
        </div>

        {/* Same-Area Warning Notice */}
        {sameAreaWarning && (
          <div
            role="status"
            className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-950/40 border border-amber-800/60 text-xs text-amber-200"
          >
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold block text-amber-300">
                Uniform District Exposure: Micro-Differentiated Accommodation Zone
              </strong>
              Accommodations in this immediate vicinity share uniform regional disaster baseline risks. Ranking differences reflect emergency facility proximity, verified credentials, and user preferences.
            </div>
          </div>
        )}

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5 pt-1 text-xs">
          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-zinc-950 text-zinc-300 border border-zinc-800 rounded-lg px-2.5 py-1 focus:outline-none focus:border-zinc-700"
          >
            <option value="all">All Categories</option>
            <option value="hotel">Hotels</option>
            <option value="guest_house">Guest Houses</option>
            <option value="hostel">Hostels</option>
            <option value="resort">Resorts</option>
          </select>

          {/* Stars Filter */}
          <select
            value={starsFilter}
            onChange={(e) => setStarsFilter(parseInt(e.target.value))}
            className="bg-zinc-950 text-zinc-300 border border-zinc-800 rounded-lg px-2.5 py-1 focus:outline-none focus:border-zinc-700"
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
            className="bg-zinc-950 text-zinc-300 border border-zinc-800 rounded-lg px-2.5 py-1 focus:outline-none focus:border-zinc-700"
          >
            <option value="50">Any Distance</option>
            <option value="2">Within 2 km</option>
            <option value="5">Within 5 km</option>
            <option value="10">Within 10 km</option>
          </select>
        </div>
      </div>

      {/* Hotels List Cards */}
      <div className="space-y-3">
        {filteredHotels.length === 0 ? (
          <div className="text-center py-8 text-xs text-zinc-400 bg-zinc-950 rounded-xl border border-zinc-800">
            No accommodations match the active category and distance filters.
          </div>
        ) : (
          paginatedHotels.map((item: HotelScored, pIdx: number) => {
            const actualIndex = (currentPage - 1) * pageSize + pIdx;
            const isSelected = item.hotel.id === selectedHotelId;
            const isExpanded = item.hotel.id === expandedHotelId;
            const bandBadge = getBandBadge(item.score_band.code);

            return (
              <div
                key={item.hotel.id}
                id={`hotel-card-${item.hotel.id}`}
                className={`rounded-xl border transition-all ${
                  isSelected
                    ? "bg-zinc-900 border-cyan-500 ring-1 ring-cyan-500/50 shadow-xl shadow-cyan-950/40"
                    : "bg-zinc-950 hover:bg-zinc-900/60 border-zinc-800"
                }`}
              >
                {/* Main Card Header */}
                <div
                  className="p-4 cursor-pointer"
                  onClick={() => onSelectHotel(item.hotel.id)}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    {/* Hotel Info */}
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-cyan-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-700">
                          #{actualIndex + 1}
                        </span>
                        <h4 className="text-sm font-bold text-white hover:text-cyan-300 transition">
                          {item.hotel.name}
                        </h4>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                        <span className="capitalize">{item.hotel.category.replace("_", " ")}</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 text-zinc-400" />
                          {item.hotel.distance_to_query_km} km away
                        </span>

                        {/* Stars & Rating */}
                        {item.hotel.stars && (
                          <span className="flex items-center gap-1 text-amber-300 font-bold text-xs bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/50">
                            <Star className="h-3 w-3 fill-amber-400" />
                            {item.hotel.stars}★
                          </span>
                        )}
                        {item.hotel.rating && (
                          <span className="text-zinc-200 font-semibold text-xs bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                            Rating: {item.hotel.rating} / 5.0 ({item.hotel.review_count || 50} Google reviews)
                          </span>
                        )}
                        {item.hotel.price_band && (
                          <span className="capitalize text-zinc-300 text-xs bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                            {item.hotel.price_band.replace("_", " ")}
                          </span>
                        )}
                        {item.limited_info && (
                          <span className="text-zinc-500 text-xs bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                            Limited Quality Info in OSM
                          </span>
                        )}
                      </div>

                      {/* Review Snippet */}
                      {item.hotel.review_snippet && (
                        <div className="flex items-start gap-1.5 text-xs text-zinc-300 italic pt-0.5">
                          <Quote className="h-3.5 w-3.5 text-cyan-400 shrink-0 mt-0.5" />
                          <span>&ldquo;{item.hotel.review_snippet.replace(/^["“”']+|["“”']+$/g, "")}&rdquo;</span>
                        </div>
                      )}
                    </div>

                    {/* Independent Safety Score & Rank Score */}
                    <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 shrink-0">
                      <div className="text-right">
                        <span className="text-xs text-zinc-400 block sm:inline mr-1">Rank Score:</span>
                        <span className="text-sm font-bold text-white font-mono">{item.rank_score}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-zinc-400">Safety:</span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold border font-mono ${bandBadge}`}
                        >
                          {item.safety_score}/100 ({item.score_band.label})
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Emergency Proximity Context */}
                  <div className="mt-3 pt-2.5 border-t border-zinc-900 flex flex-wrap items-center gap-4 text-xs text-zinc-400">
                    <span className="font-semibold text-zinc-300 uppercase tracking-wider text-[10px]">
                      Emergency Proximity:
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Hospital className="h-3.5 w-3.5 text-rose-400" />
                      Hospital:{" "}
                      <strong className="text-white font-mono">
                        {item.access_to_help.hospital_distance_km !== null
                          ? `${item.access_to_help.hospital_distance_km} km`
                          : "Not nearby"}
                      </strong>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Shield className="h-3.5 w-3.5 text-cyan-400" />
                      Police:{" "}
                      <strong className="text-white font-mono">
                        {item.access_to_help.police_distance_km !== null
                          ? `${item.access_to_help.police_distance_km} km`
                          : "Not nearby"}
                      </strong>
                    </span>
                    {item.access_to_help.fire_station_distance_km !== null && (
                      <span className="flex items-center gap-1.5">
                        <Flame className="h-3.5 w-3.5 text-amber-400" />
                        Fire:{" "}
                        <strong className="text-white font-mono">
                          {item.access_to_help.fire_station_distance_km} km
                        </strong>
                      </span>
                    )}
                  </div>
                </div>

                {/* Ranking Breakdown Trigger */}
                <div className="bg-zinc-950 px-4 py-2 border-t border-zinc-900 flex items-center justify-between text-xs">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(item.hotel.id);
                    }}
                    className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition"
                  >
                    <span>Why is this property ranked #{actualIndex + 1}?</span>
                    {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>

                  {item.hotel.website && (
                    <a
                      href={item.hotel.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-400 hover:text-white flex items-center gap-1 transition"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>Website</span>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>

                {/* Expandable Breakdown Drawer */}
                {isExpanded && (
                  <div className="p-4 bg-zinc-950 border-t border-zinc-900 text-xs text-zinc-300 space-y-3 animate-fadeIn">
                    <p className="text-zinc-400">{item.rank_breakdown.explanation}</p>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-[10px] text-zinc-500 block">Safety Score Component</span>
                        <span className="font-semibold text-white text-xs font-mono">
                          {item.safety_score}/100 (weight {Math.round(alpha * 100)}%)
                        </span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-[10px] text-zinc-500 block">Quality Score Component</span>
                        <span className="font-semibold text-white text-xs font-mono">
                          {item.rank_breakdown?.quality_norm != null
                            ? `${Math.round(item.rank_breakdown.quality_norm * 100)}/100`
                            : "N/A"}
                        </span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-[10px] text-zinc-500 block">Police Distance</span>
                        <span className="font-semibold text-white text-xs">
                          {item.access_to_help.police_distance_km ? `${item.access_to_help.police_distance_km} km` : "N/A"}
                        </span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-[10px] text-zinc-500 block">Hospital Distance</span>
                        <span className="font-semibold text-white text-xs">
                          {item.access_to_help.hospital_distance_km ? `${item.access_to_help.hospital_distance_km} km` : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Controls */}
      {filteredHotels.length > pageSize && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-zinc-800/80 text-xs text-zinc-400">
          <div>
            Showing{" "}
            <strong className="text-white font-mono">
              {(currentPage - 1) * pageSize + 1}
            </strong>{" "}
            to{" "}
            <strong className="text-white font-mono">
              {Math.min(currentPage * pageSize, filteredHotels.length)}
            </strong>{" "}
            of <strong className="text-white font-mono">{filteredHotels.length}</strong> accommodations
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className={`p-1.5 px-3 rounded-lg border flex items-center gap-1 font-medium transition ${
                currentPage === 1
                  ? "bg-zinc-950 border-zinc-800 text-zinc-600 cursor-not-allowed"
                  : "bg-zinc-900 border-zinc-800 text-zinc-200 hover:bg-zinc-800"
              }`}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Prev</span>
            </button>

            {/* Page number indicators */}
            {Array.from({ length: totalPages }).map((_, i) => {
              const p = i + 1;
              if (totalPages > 6 && Math.abs(p - currentPage) > 2 && p !== 1 && p !== totalPages) {
                if (Math.abs(p - currentPage) === 3) {
                  return (
                    <span key={`dots-${p}`} className="px-1 text-zinc-600">
                      ...
                    </span>
                  );
                }
                return null;
              }

              return (
                <button
                  key={`page-${p}`}
                  type="button"
                  onClick={() => setCurrentPage(p)}
                  className={`w-7 h-7 rounded-lg font-mono text-xs font-semibold transition ${
                    currentPage === p
                      ? "bg-cyan-500 text-black shadow-md shadow-cyan-950"
                      : "bg-zinc-950 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-900"
                  }`}
                >
                  {p}
                </button>
              );
            })}

            <button
              type="button"
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className={`p-1.5 px-3 rounded-lg border flex items-center gap-1 font-medium transition ${
                currentPage === totalPages
                  ? "bg-zinc-950 border-zinc-800 text-zinc-600 cursor-not-allowed"
                  : "bg-zinc-900 border-zinc-800 text-zinc-200 hover:bg-zinc-800"
              }`}
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
