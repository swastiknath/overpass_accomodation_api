"use client";

import React, { useState, useEffect } from "react";
import {
  Compass,
  Radio,
  Shield,
  Layers,
  Sparkles,
  Globe2,
  Hotel,
  Activity,
  Flame,
  AlertTriangle,
  Building,
} from "lucide-react";

interface SearchLoadingAnimationProps {
  query?: string;
}

const TELEMETRY_STAGES = [
  {
    phase: "Spatial Resolution",
    title: "Resolving High-Precision Geocoding & Geographic Perimeters",
    description:
      "Interrogating OpenStreetMap Nominatim and Photon spatial indexes to establish municipal polygons and anchor coordinates.",
    icon: Compass,
    badgeColor: "text-emerald-400 border-emerald-500/30 bg-emerald-950/40",
    node: "GEODATA",
  },
  {
    phase: "Remote Sensing",
    title: "Aggregating GDACS, USGS Seismic & NASA FIRMS Telemetry",
    description:
      "Scanning active satellite orbital passes for thermal anomaly signatures, wildfire clusters, and tectonic event focal points.",
    icon: Flame,
    badgeColor: "text-amber-400 border-amber-500/30 bg-amber-950/40",
    node: "SATELLITE",
  },
  {
    phase: "Conflict & Protests",
    title: "Auditing ACLED Civil Unrest, Protests & Public Demonstrations",
    description:
      "Ingesting live political violence records, localized civil demonstrations, and municipal security advisories across districts.",
    icon: Activity,
    badgeColor: "text-cyan-400 border-cyan-500/30 bg-cyan-950/40",
    node: "CIVIL HAZARDS",
  },
  {
    phase: "Diplomatic Bulletins",
    title: "Synthesizing Official MEA India & Diplomatic Travel Advisories",
    description:
      "Cross-referencing Ministry of External Affairs (India), U.S. State Department, and UK FCDO national travel advisories.",
    icon: Shield,
    badgeColor: "text-purple-400 border-purple-500/30 bg-purple-950/40",
    node: "CONSULAR",
  },
  {
    phase: "Accommodation Discovery",
    title: "Crawling Accommodations via Overpass, Foursquare & Live Indices",
    description:
      "Harvesting verified hotels, hostels, homestays, OYO, and GoStays properties with real-time proximity to emergency police and hospitals.",
    icon: Hotel,
    badgeColor: "text-teal-400 border-teal-500/30 bg-teal-950/40",
    node: "FOURSQUARE & OSM",
  },
  {
    phase: "Deterministic Fusion",
    title: "Computing Calibrated Multi-Hazard Fusion & Safety Matrix",
    description:
      "Calculating deterministic mathematical safety scoring, safety-quality weighted ranking, and grounded natural language insights.",
    icon: Sparkles,
    badgeColor: "text-emerald-400 border-emerald-500/30 bg-emerald-950/40",
    node: "FUSION ENGINE",
  },
];

export default function SearchLoadingAnimation({ query }: SearchLoadingAnimationProps) {
  const [currentStageIdx, setCurrentStageIdx] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [fadeAnim, setFadeAnim] = useState(true);

  // Cycling stages every 1.8s
  useEffect(() => {
    const stageInterval = setInterval(() => {
      setFadeAnim(false);
      setTimeout(() => {
        setCurrentStageIdx((prev) => (prev + 1) % TELEMETRY_STAGES.length);
        setFadeAnim(true);
      }, 200);
    }, 2200);

    return () => clearInterval(stageInterval);
  }, []);

  // Elapsed stopwatch
  useEffect(() => {
    const start = Date.now();
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - start) / 100) / 10);
    }, 100);
    return () => clearInterval(timer);
  }, []);

  const currentStage = TELEMETRY_STAGES[currentStageIdx];
  const IconComponent = currentStage.icon;

  return (
    <div
      role="status"
      aria-live="polite"
      className="relative w-full max-w-3xl mx-auto py-12 px-6 flex flex-col items-center justify-center text-center select-none overflow-hidden rounded-3xl border border-zinc-800/80 bg-zinc-950/80 backdrop-blur-2xl shadow-[0_0_60px_rgba(0,0,0,0.8)]"
    >
      {/* Background Animated Ambient Radiant Gradients */}
      <div className="absolute -top-32 -left-32 w-80 h-80 rounded-full bg-emerald-600/15 blur-[100px] pointer-events-none animate-pulse" />
      <div className="absolute -bottom-32 -right-32 w-80 h-80 rounded-full bg-cyan-600/15 blur-[100px] pointer-events-none animate-pulse" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-zinc-900/40 via-transparent to-transparent pointer-events-none" />

      {/* Orbiting Gyroscope Radar Scanning Animation */}
      <div className="relative mb-8 flex items-center justify-center">
        {/* Outer orbital dash ring */}
        <div className="w-36 h-36 rounded-full border border-dashed border-emerald-500/30 animate-[spin_16s_linear_infinite] flex items-center justify-center p-3">
          {/* Satellite tracking particle */}
          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-emerald-400 shadow-[0_0_12px_#34d399]" />
        </div>

        {/* Counter-rotating mid ring */}
        <div className="absolute w-28 h-28 rounded-full border border-cyan-500/35 border-t-transparent border-b-transparent animate-[spin_8s_linear_infinite_reverse] flex items-center justify-center" />

        {/* Glowing Radar Sweep Core */}
        <div className="absolute w-20 h-20 rounded-full bg-gradient-to-tr from-emerald-950/80 via-zinc-900 to-cyan-950/80 border border-emerald-500/40 shadow-[0_0_30px_rgba(16,185,129,0.35)] flex items-center justify-center overflow-hidden">
          {/* Sweeping radar cone beam */}
          <div className="absolute inset-0 origin-center bg-[conic-gradient(from_0deg,transparent_0_300deg,rgba(52,211,153,0.35)_360deg)] animate-[spin_2.5s_linear_infinite]" />

          {/* Central Beacon Icon with Micro Pulse */}
          <div className="relative z-10 p-2.5 rounded-full bg-black/60 border border-white/10 shadow-inner">
            <IconComponent className="h-6 w-6 text-emerald-300 animate-pulse transition-all duration-300" />
          </div>
        </div>

        {/* Outer subtle glow rings */}
        <div className="absolute w-44 h-44 rounded-full border border-emerald-500/10 animate-ping opacity-25 pointer-events-none" />
      </div>

      {/* Stage Badge & Live Telemetry Stream Indicator */}
      <div className="flex flex-wrap items-center justify-center gap-2.5 mb-3.5 z-10">
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase tracking-wider bg-black/70 border border-white/10 text-zinc-300 shadow-sm">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
          </span>
          Live Fusion Engine
        </span>

        <span
          className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-[11px] font-semibold border ${currentStage.badgeColor}`}
        >
          <Radio className="h-3 w-3 animate-pulse" />
          {currentStage.phase} &bull; Stage {currentStageIdx + 1} of {TELEMETRY_STAGES.length}
        </span>

        <span className="px-2.5 py-1 rounded-full text-[11px] font-mono text-zinc-400 bg-zinc-900/80 border border-zinc-800">
          {elapsedSeconds.toFixed(1)}s elapsed
        </span>
      </div>

      {/* Query Destination Target Header */}
      {query && (
        <div className="mb-2 z-10">
          <span className="text-xs uppercase tracking-widest text-zinc-400 font-medium">
            Analyzing Target Destination
          </span>
          <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight line-clamp-1 mt-0.5">
            &ldquo;{query}&rdquo;
          </h2>
        </div>
      )}

      {/* Animated Telemetry Stage Title & Detailed Narrative */}
      <div
        className={`max-w-xl mx-auto space-y-2 z-10 transition-all duration-300 transform ${
          fadeAnim ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
        }`}
      >
        <h3 className="text-base sm:text-lg font-semibold text-zinc-100 tracking-tight">
          {currentStage.title}
        </h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed font-normal">
          {currentStage.description}
        </p>
      </div>

      {/* Stepped Progress Bar with Gradient Flow */}
      <div className="w-full max-w-md mx-auto mt-6 space-y-1.5 z-10">
        <div className="h-1.5 w-full bg-zinc-900 rounded-full overflow-hidden border border-zinc-800 p-0.5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-teal-400 to-cyan-400 transition-all duration-500 ease-out shadow-[0_0_12px_rgba(52,211,153,0.5)]"
            style={{
              width: `${((currentStageIdx + 1) / TELEMETRY_STAGES.length) * 100}%`,
            }}
          />
        </div>
        <div className="flex justify-between items-center text-[10px] text-zinc-400 font-mono px-1">
          <span>Active Node: {currentStage.node}</span>
          <span>{Math.round(((currentStageIdx + 1) / TELEMETRY_STAGES.length) * 100)}% Synchronized</span>
        </div>
      </div>

      {/* Connected Real-time Data Connector Node Chips */}
      <div className="mt-8 pt-6 border-t border-zinc-800/80 w-full flex flex-wrap items-center justify-center gap-2 z-10">
        <span className="text-[10px] font-semibold tracking-wider uppercase text-zinc-400 mr-1">
          Connected Feeds:
        </span>
        {[
          { label: "OSM Geocoding", status: "Active" },
          { label: "GDACS & USGS", status: "24h Live" },
          { label: "NASA FIRMS", status: "Orbital" },
          { label: "ACLED Unrest", status: "Synced" },
          { label: "MEA Advisories", status: "Verified" },
          { label: "Foursquare Places", status: "Integrated" },
          { label: "Overpass Accommodations", status: "Ready" },
        ].map((node) => (
          <span
            key={node.label}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium bg-zinc-900/90 border border-zinc-800 text-zinc-300"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-zinc-200">{node.label}</span>
            <span className="text-zinc-400 font-mono text-[9px] uppercase">[{node.status}]</span>
          </span>
        ))}
      </div>
    </div>
  );
}
