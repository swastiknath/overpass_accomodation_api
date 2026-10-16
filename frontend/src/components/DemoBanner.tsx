"use client";

import React from "react";
import { AlertTriangle, Activity } from "lucide-react";

export default function DemoBanner({ show }: { show: boolean }) {
  if (show) {
    return (
      <div
        role="alert"
        className="bg-amber-950/25 backdrop-blur-xl text-amber-200/90 px-4 py-1.5 flex items-center justify-between text-xs font-normal border-b border-amber-500/20 shadow-sm"
      >
        <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-300 animate-pulse" />
          <span className="text-[11px] sm:text-xs text-amber-200/90">
            <strong className="font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-300 px-2 py-0.5 rounded-full mr-1.5 border border-amber-500/25 text-[10px]">
              DEMO MODE ACTIVE
            </strong>
            Serving verified recorded fixtures for all connectors and deterministic LLM narrative.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="bg-emerald-950/20 backdrop-blur-xl text-emerald-200/90 px-4 py-1.5 flex items-center justify-between text-xs font-normal border-b border-emerald-500/15 shadow-sm"
    >
      <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
        </span>
        <span className="text-[11px] sm:text-xs text-emerald-200/80">
          <strong className="font-semibold uppercase tracking-wider bg-emerald-500/15 text-emerald-300 px-2 py-0.5 rounded-full mr-2 border border-emerald-500/25 text-[10px]">
            LIVE DATA ACTIVE
          </strong>
          Aggregating real-time feeds: GDACS, USGS, Open-Meteo, Bhuvan/ISRO, GDELT & OSM Overpass.
        </span>
      </div>
    </div>
  );
}
