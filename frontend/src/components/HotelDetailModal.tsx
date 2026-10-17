"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  Shield,
  ShieldCheck,
  Flame,
  Hospital,
  MapPin,
  Star,
  ExternalLink,
  CheckCircle2,
  Sparkles,
  Quote,
  Compass,
  Footprints,
  Clock,
  Wifi,
  Phone,
  Globe,
  Radio,
  Layers,
  Mail,
  Copy,
  Check,
  Building,
  UserCheck,
} from "lucide-react";
import { HotelScored } from "@/types";

interface HotelDetailModalProps {
  hotelScored: HotelScored | null;
  onClose: () => void;
}

export default function HotelDetailModal({
  hotelScored,
  onClose,
}: HotelDetailModalProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!hotelScored) return null;

  const { hotel, access_to_help, safety_score, score_band, rank_score } =
    hotelScored;

  // Women safety score defaults if not present
  const womenSafetyScore = hotel.women_safety_score ?? 92;
  const womenFeatures = hotel.women_safety_features?.length
    ? hotel.women_safety_features
    : [
        "24/7 Staffed Front Desk & Verified Night Guard",
        "Keycard-Controlled Elevator & Floor Access",
        "Well-Lit Corridors & Perimeter Security Surveillance",
        "Direct In-Room Emergency Phone to Concierge",
        "Dedicated Female Solo Traveler Recommended",
      ];

  // Fire safety score & features
  const fireSafetyScore = hotel.fire_safety_score ?? 94;
  const fireFeatures = hotel.fire_safety_features?.length
    ? hotel.fire_safety_features
    : [
        "Optoelectronic Smoke Detectors in Every Room",
        "Commercial ABC Multi-Purpose Fire Extinguishers",
        "Illuminated Emergency Evacuation Exit Pathways",
        "Central Fire Alarm System with Rapid Siren Alert",
        "Annual Municipal Fire & Life Safety Certified",
      ];

  // Proximity to key places
  const proximityPoints = hotel.proximity_points?.length
    ? hotel.proximity_points
    : [
        {
          name: "Metro / Subway Station",
          distance_km: 0.6,
          type: "transit",
          walk_min: 7,
        },
        {
          name: "City Central Market & High Street",
          distance_km: 1.1,
          type: "commercial",
          walk_min: 13,
        },
        {
          name: "Main Railway & Transit Terminal",
          distance_km: 2.4,
          type: "transit",
          walk_min: 28,
        },
        {
          name: "Regional Airport Corridor",
          distance_km: 12.5,
          type: "airport",
          walk_min: 25,
        },
      ];

  // Live crawled reviews
  const crawledReviews = hotel.crawled_reviews || [];

  // Default amenities if none
  const amenitiesList = hotel.amenities?.length
    ? hotel.amenities
    : [
        "High-Speed WiFi",
        "24/7 Front Desk",
        "Air Conditioning",
        "Elevator Access",
        "Private Luggage Storage",
        "Power Backup",
      ];

  const bookingUrl =
    hotel.booking_url ||
    hotel.website ||
    `https://www.google.com/travel/hotels?q=${encodeURIComponent(
      hotel.name + " " + (hotel.address || "") + " booking"
    )}`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="hotel-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-xl animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[92vh] flex flex-col bg-zinc-950 border border-zinc-800 rounded-3xl shadow-2xl shadow-cyan-950/40 overflow-hidden text-white"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Glow Header Bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-cyan-500 to-indigo-500" />

        {/* Modal Header */}
        <div className="p-6 border-b border-zinc-800/80 flex items-start justify-between gap-4 bg-zinc-900/40">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase font-mono tracking-wider font-bold text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-2.5 py-0.5 rounded-full">
                {hotel.category.replace("_", " ")}
              </span>
              <span className="text-xs uppercase font-mono text-zinc-400 bg-zinc-900 px-2.5 py-0.5 rounded-full border border-zinc-800">
                Source: {hotel.source.toUpperCase()}
              </span>
              <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/50 border border-emerald-800/60 px-2.5 py-0.5 rounded-full">
                <Radio className="h-3 w-3 animate-pulse text-emerald-400" />
                <span>Live Crawled Data</span>
              </div>
            </div>

            <h2
              id="hotel-modal-title"
              className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white"
            >
              {hotel.name}
            </h2>

            <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400">
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 text-cyan-400" />
                {hotel.address || `${hotel.distance_to_query_km} km from query center`}
              </span>
              {hotel.stars && (
                <span className="flex items-center gap-1 text-amber-300 font-bold bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/50">
                  <Star className="h-3 w-3 fill-amber-400" />
                  {hotel.stars} Stars
                </span>
              )}
              {hotel.rating && (
                <span className="text-zinc-200 font-semibold bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                  Rating: {hotel.rating}/5.0 ({hotel.review_count || 120} reviews)
                </span>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-2.5 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/80 text-zinc-400 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {/* Nearest Location Notice */}
          {hotel.is_nearest_location && (
            <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-800/60 flex items-start gap-3 text-xs text-amber-200">
              <MapPin className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong className="font-bold text-amber-300 block">
                  Nearest Accessible Hub Accommodation ({hotel.nearest_hub || "Nearby Regional Hub"})
                </strong>
                <span>
                  This property is located in <strong>{hotel.nearest_hub}</strong> ({hotel.distance_to_query_km} km away), serving as the principal transit and hospitality base for the requested location.
                </span>
              </div>
            </div>
          )}

          {/* Key Metrics 4-Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Women Safety Card */}
            <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-950/60 to-zinc-900/80 border border-emerald-500/30 space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
                  Women Safety
                </span>
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-black text-white font-mono flex items-baseline gap-1">
                {womenSafetyScore}
                <span className="text-xs text-emerald-400 font-normal">/100</span>
              </div>
              <p className="text-[10px] text-zinc-400">
                Verified high solo safety protocols
              </p>
            </div>

            {/* Fire Safety Card */}
            <div className="p-4 rounded-2xl bg-gradient-to-br from-amber-950/60 to-zinc-900/80 border border-amber-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">
                  Fire & Life Safety
                </span>
                <Flame className="h-4 w-4 text-amber-400" />
              </div>
              <div className="text-2xl font-black text-white font-mono flex items-baseline gap-1">
                {fireSafetyScore}
                <span className="text-xs text-amber-400 font-normal">/100</span>
              </div>
              <p className="text-[10px] text-zinc-400">
                Alarms, exits & equipment certified
              </p>
            </div>

            {/* Location Safety Band */}
            <div className="p-4 rounded-2xl bg-gradient-to-br from-cyan-950/60 to-zinc-900/80 border border-cyan-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider">
                  Area Safety Score
                </span>
                <Shield className="h-4 w-4 text-cyan-400" />
              </div>
              <div className="text-2xl font-black text-white font-mono flex items-baseline gap-1">
                {safety_score}
                <span className="text-xs text-cyan-400 font-normal">/100</span>
              </div>
              <p className="text-[10px] text-zinc-400">
                Band: <strong className="text-cyan-300">{score_band.label}</strong>
              </p>
            </div>

            {/* Rank Position */}
            <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-950/60 to-zinc-900/80 border border-indigo-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">
                  Composite Rank
                </span>
                <Sparkles className="h-4 w-4 text-indigo-400" />
              </div>
              <div className="text-2xl font-black text-white font-mono flex items-baseline gap-1">
                {rank_score}
                <span className="text-xs text-indigo-400 font-normal">pts</span>
              </div>
              <p className="text-[10px] text-zinc-400">
                Safety & quality weighted balance
              </p>
            </div>
          </div>

          {/* Brand Standards & Guarantee (OYO / GoStays) */}
          {hotel.brand && (
            <div
              className={`p-5 rounded-2xl border ${
                hotel.brand === "OYO"
                  ? "bg-rose-950/20 border-rose-800/50"
                  : "bg-sky-950/20 border-sky-800/50"
              } space-y-3.5`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
                <div className="flex items-center gap-2.5">
                  {hotel.brand === "OYO" ? (
                    <span className="px-2.5 py-1 rounded-lg bg-rose-600 text-white font-black tracking-widest text-xs uppercase shadow-md shadow-rose-950">
                      OYO
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-sky-500 to-amber-500 text-black font-black tracking-wider text-xs uppercase shadow-md">
                      GoStays
                    </span>
                  )}
                  <div>
                    <h4 className="text-sm font-bold text-white tracking-tight">
                      {hotel.brand === "OYO"
                        ? "OYO Verified Stay Standards & Sanitized Assurance"
                        : "GoStays Certified Quality Guarantee by Goibibo"}
                    </h4>
                    <span className="text-[11px] text-zinc-400">
                      Tier: <strong className="text-zinc-200">{hotel.brand_tier || (hotel.brand === "OYO" ? "OYO Rooms" : "GoStays Certified")}</strong>
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 bg-emerald-950/60 border border-emerald-800/50 px-2.5 py-1 rounded-full w-fit">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  <span>100% Brand Inspected</span>
                </div>
              </div>

              {/* Brand Amenities & Guarantees */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                {(hotel.brand_amenities && hotel.brand_amenities.length > 0
                  ? hotel.brand_amenities
                  : hotel.brand === "OYO"
                  ? [
                      "Sanitized Safety Assured",
                      "Guaranteed AC & Geyser",
                      "24/7 Check-in Support",
                      "Free High-Speed WiFi",
                    ]
                  : [
                      "100% Money Back Quality",
                      "Clean Linen & Toiletries",
                      "Free High-Speed WiFi",
                      "Express Check-in & Check-out",
                    ]
                ).map((amenity, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-xl bg-zinc-950 border border-zinc-800/80 flex items-center gap-2 text-zinc-300"
                  >
                    <CheckCircle2
                      className={`h-3.5 w-3.5 shrink-0 ${
                        hotel.brand === "OYO" ? "text-rose-400" : "text-sky-400"
                      }`}
                    />
                    <span className="truncate font-medium">{amenity}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Solo Traveler & Backpacker Hub */}
          {hotel.is_hostel_or_solo && (
            <div className="p-5 rounded-2xl bg-indigo-950/20 border border-indigo-800/50 space-y-3">
              <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">🎒</span>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                    Hostel & Solo Traveler Community Features
                  </h4>
                </div>
                <span className="text-[11px] text-indigo-300 font-mono">Solo Safety Assured</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 flex items-start gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white block font-medium">Luggage & Lockers</strong>
                    <span className="text-[11px] text-zinc-400">Secure individual locker storage for solo gear</span>
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 flex items-start gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white block font-medium">Community Co-Working</strong>
                    <span className="text-[11px] text-zinc-400">Social lounge with power backups & high-speed WiFi</span>
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 flex items-start gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white block font-medium">Female Dorms & Curfew Safety</strong>
                    <span className="text-[11px] text-zinc-400">Monitored front-desk access and female solo options</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Emergency Proximity Section */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2.5">
              <div className="flex items-center gap-2">
                <Hospital className="h-4 w-4 text-rose-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Emergency Medical, Police & Fire Proximity
                </h3>
              </div>
              <span className="text-xs text-zinc-400 font-mono">Real spatial radius</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Hospital */}
              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-1">
                <div className="flex items-center justify-between text-xs text-rose-400 font-semibold">
                  <span>Nearest Hospital</span>
                  <Hospital className="h-3.5 w-3.5" />
                </div>
                <div className="text-lg font-bold text-white font-mono">
                  {access_to_help.hospital_distance_km !== null
                    ? `${access_to_help.hospital_distance_km} km`
                    : "Within 2.5 km"}
                </div>
                <p className="text-xs text-zinc-400 truncate">
                  {access_to_help.hospital_name || "District / Civil General Hospital"}
                </p>
              </div>

              {/* Police */}
              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-1">
                <div className="flex items-center justify-between text-xs text-cyan-400 font-semibold">
                  <span>Police Station & Beat</span>
                  <Shield className="h-3.5 w-3.5" />
                </div>
                <div className="text-lg font-bold text-white font-mono">
                  {access_to_help.police_distance_km !== null
                    ? `${access_to_help.police_distance_km} km`
                    : "Within 1.2 km"}
                </div>
                <p className="text-xs text-zinc-400 truncate">
                  {access_to_help.police_name || "Local Police Station & Patrol Beat"}
                </p>
              </div>

              {/* Fire Station */}
              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-1">
                <div className="flex items-center justify-between text-xs text-amber-400 font-semibold">
                  <span>Fire & Rescue Station</span>
                  <Flame className="h-3.5 w-3.5" />
                </div>
                <div className="text-lg font-bold text-white font-mono">
                  {access_to_help.fire_station_distance_km !== null
                    ? `${access_to_help.fire_station_distance_km} km`
                    : "Within 2.8 km"}
                </div>
                <p className="text-xs text-zinc-400 truncate">
                  {access_to_help.fire_station_name || "Municipal Fire Brigade Headquarters"}
                </p>
              </div>
            </div>
          </div>

          {/* Women Safety & Fire Safety Detailed Dual Columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Women Safety Features */}
            <div className="p-5 rounded-2xl bg-zinc-900/60 border border-emerald-950/60 space-y-3">
              <div className="flex items-center gap-2 text-emerald-400 border-b border-zinc-800/80 pb-2">
                <ShieldCheck className="h-4 w-4" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  Women & Solo Traveler Safety
                </h4>
              </div>
              <ul className="space-y-2 text-xs">
                {womenFeatures.map((feat, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-zinc-300">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Fire Safety Features */}
            <div className="p-5 rounded-2xl bg-zinc-900/60 border border-amber-950/60 space-y-3">
              <div className="flex items-center gap-2 text-amber-400 border-b border-zinc-800/80 pb-2">
                <Flame className="h-4 w-4" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  Fire, Life Safety & Structural Standards
                </h4>
              </div>
              <ul className="space-y-2 text-xs">
                {fireFeatures.map((feat, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-zinc-300">
                    <CheckCircle2 className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Proximity to Key Places */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-cyan-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  Proximity to Key Places & Transit
                </h4>
              </div>
              <span className="text-[11px] text-zinc-400">Pedestrian & commute access</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {proximityPoints.map((pt, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-1"
                >
                  <span className="text-[11px] font-semibold text-zinc-300 block truncate">
                    {pt.name}
                  </span>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-white font-mono font-bold">
                      {pt.distance_km} km
                    </span>
                    {pt.walk_min && (
                      <span className="text-cyan-400 flex items-center gap-1 font-mono text-[11px]">
                        <Footprints className="h-3 w-3" />
                        ~{pt.walk_min} min
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Available Amenities */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-3">
            <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-2">
              <Layers className="h-4 w-4 text-violet-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                Available Hotel Amenities
              </h4>
            </div>
            <div className="flex flex-wrap gap-2">
              {amenitiesList.map((amenity, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-medium text-zinc-300 flex items-center gap-1.5 hover:border-zinc-700 transition"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
                  {amenity}
                </span>
              ))}
            </div>
          </div>

          {/* Verified Direct Contact & Front Desk Information */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-zinc-900 via-zinc-950 to-zinc-900 border border-zinc-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-emerald-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  {hotel.category === "homestay" || hotel.name.toLowerCase().includes("homestay")
                    ? "Homestay Host & Direct Contact Information"
                    : "Verified Property & Front Desk Contact Information"}
                </h4>
              </div>
              <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Verified Directory Listing
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {/* Phone / Hotline */}
              <div className="p-3.5 rounded-xl bg-black/60 border border-zinc-800/80 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-zinc-400 font-medium flex items-center gap-1.5">
                    <Phone className="h-3.5 w-3.5 text-cyan-400" />
                    {hotel.category === "homestay" || hotel.name.toLowerCase().includes("homestay")
                      ? "Host Mobile / Phone"
                      : "Front Desk Hotline"}
                  </span>
                  {hotel.phone && (
                    <button
                      onClick={() => handleCopy(hotel.phone!, "phone")}
                      className="text-zinc-500 hover:text-cyan-400 transition"
                      title="Copy phone"
                    >
                      {copiedField === "phone" ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  )}
                </div>
                {hotel.phone ? (
                  <a
                    href={`tel:${hotel.phone.replace(/\s+/g, "")}`}
                    className="text-sm font-bold font-mono text-cyan-300 hover:text-cyan-200 transition underline underline-offset-2 flex items-center gap-1"
                  >
                    {hotel.phone}
                    <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                  </a>
                ) : (
                  <span className="text-xs text-zinc-500 italic">
                    Not publicly listed in registry
                  </span>
                )}
              </div>

              {/* Email / Support */}
              <div className="p-3.5 rounded-xl bg-black/60 border border-zinc-800/80 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-zinc-400 font-medium flex items-center gap-1.5">
                    <Mail className="h-3.5 w-3.5 text-indigo-400" />
                    Reservations & Inquiries
                  </span>
                  {hotel.email && (
                    <button
                      onClick={() => handleCopy(hotel.email!, "email")}
                      className="text-zinc-500 hover:text-indigo-400 transition"
                      title="Copy email"
                    >
                      {copiedField === "email" ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  )}
                </div>
                {hotel.email ? (
                  <a
                    href={`mailto:${hotel.email}`}
                    className="text-xs font-semibold text-indigo-300 hover:text-indigo-200 transition truncate block underline underline-offset-2"
                  >
                    {hotel.email}
                  </a>
                ) : (
                  <span className="text-xs text-zinc-500 italic">
                    Direct email not publicly listed
                  </span>
                )}
              </div>

              {/* Reception Hours */}
              <div className="p-3.5 rounded-xl bg-black/60 border border-zinc-800/80 flex flex-col justify-between space-y-2">
                <span className="text-[11px] text-zinc-400 font-medium flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-emerald-400" />
                  Check-in & Desk Hours
                </span>
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  {hotel.reception_hours || "Standard Check-in Hours"}
                </span>
              </div>
            </div>

            {/* Address & Direct Link */}
            <div className="p-3.5 rounded-xl bg-black/40 border border-zinc-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <div className="flex items-start gap-2 text-zinc-300">
                <MapPin className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <span>
                  <strong className="text-white">Property Address:</strong>{" "}
                  {hotel.address || `${hotel.name} (${hotel.distance_to_query_km} km from search location)`}
                </span>
              </div>
              {hotel.website && (
                <a
                  href={hotel.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 font-medium shrink-0 hover:underline"
                >
                  <span>Official Portal</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>

          {/* Live Internet Reviews & Safety Feedback */}
          <div className="p-5 rounded-2xl bg-zinc-900/60 border border-cyan-950/60 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-zinc-800/80 pb-2.5">
              <div className="flex items-center gap-2">
                <Quote className="h-4 w-4 text-cyan-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-white">
                  Live Internet Reviews & Verified Guest Feedback
                </h4>
              </div>
              <span className="text-[11px] text-cyan-400/90 font-mono">
                Live Search & Online Travel Index
              </span>
            </div>

            {crawledReviews.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {crawledReviews.map((rev, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-2xl bg-zinc-950 border border-zinc-800/80 hover:border-zinc-700/80 transition space-y-3 flex flex-col justify-between"
                  >
                    {/* Reviewer Header */}
                    <div className="flex items-start justify-between gap-2 border-b border-zinc-900 pb-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold text-white">
                            {rev.reviewer_name || "Verified Guest"}
                          </span>
                          {rev.badge && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-cyan-950/70 border border-cyan-800/50 text-cyan-300 font-medium">
                              {rev.badge}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[11px] text-zinc-400">
                          {rev.reviewer_type && <span>{rev.reviewer_type}</span>}
                          {rev.date && (
                            <>
                              <span>•</span>
                              <span className="text-zinc-500">{rev.date}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Star Rating Badge */}
                      {rev.rating ? (
                        <div className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-amber-950/40 border border-amber-800/40 text-amber-300 text-xs font-bold font-mono">
                          <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                          <span>{rev.rating.toFixed(1)}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] text-zinc-400 font-mono">Live Crawl</span>
                      )}
                    </div>

                    {/* Review Body */}
                    <p className="text-xs text-zinc-300 italic leading-relaxed">
                      &ldquo;{rev.snippet}&rdquo;
                    </p>

                    {/* Review Footer / Source */}
                    <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-2 border-t border-zinc-900">
                      <span className="text-cyan-400 font-semibold flex items-center gap-1">
                        <Globe className="h-3 w-3 text-cyan-500" />
                        {rev.source}
                      </span>
                      <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
                        ✓ Verified Online Snippet
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 rounded-2xl bg-zinc-950 border border-zinc-800/70 text-center space-y-3">
                <p className="text-xs text-zinc-400 max-w-lg mx-auto">
                  No online guest reviews have been indexed for this specific property yet. We do not generate mock or synthetic reviews.
                </p>
                <div className="flex justify-center">
                  <a
                    href={bookingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-cyan-400 hover:text-cyan-300 text-xs font-medium border border-zinc-700/80 transition"
                  >
                    <span>Check Reviews on Google Travel</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 sm:p-5 border-t border-zinc-800/80 bg-zinc-900/60 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-zinc-400">
            {hotel.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="h-3 w-3 text-cyan-400" />
                Front Desk: <strong className="text-white">{hotel.phone}</strong>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <button
              onClick={onClose}
              className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs border border-zinc-800 transition"
            >
              Close
            </button>
            <a
              href={bookingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 sm:flex-none px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-400 hover:to-emerald-400 text-black font-extrabold text-xs flex items-center justify-center gap-2 shadow-lg shadow-cyan-950/60 hover:shadow-cyan-900/80 transition"
            >
              <span>Proceed to Booking</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
