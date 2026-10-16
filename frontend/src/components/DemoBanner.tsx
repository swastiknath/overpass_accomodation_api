"use client";

import React from "react";
import { AlertTriangle, Activity } from "lucide-react";

export default function DemoBanner({ show }: { show: boolean }) {
  if (show) {
    return (
      <div
        role="alert"
        className="bg-gradient-to-r from-amber-600/90 via-orange-600/90 to-amber-700/90 text-white px-4 py-2.5 shadow-md flex items-center justify-between text-xs sm:text-sm font-medium border-b border-amber-400/30"
      >
        <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-200 animate-pulse" />
          <span>
            <strong className="font-semibold uppercase tracking-wider bg-amber-900/60 px-1.5 py-0.5 rounded mr-1">
              DEMO MODE ACTIVE
            </strong>
            Serving verified recorded fixtures for all connectors and deterministic LLM narrative.
            No live API keys or external charges required.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="bg-gradient-to-r from-emerald-950 via-slate-900 to-emerald-950 text-emerald-200 px-4 py-2 shadow-sm flex items-center justify-between text-xs font-medium border-b border-emerald-800/40"
    >
      <div className="flex items-center gap-2 max-w-7xl mx-auto w-full">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
        <span>
          <strong className="font-semibold uppercase tracking-wider bg-emerald-900/80 text-emerald-300 px-1.5 py-0.5 rounded mr-1.5 border border-emerald-700/60">
            LIVE DATA ACTIVE
          </strong>
          Aggregating real-time feeds: GDACS, USGS, Open-Meteo, Bhuvan/ISRO, GDELT & OSM Overpass.
        </span>
      </div>
    </div>
  );
}
