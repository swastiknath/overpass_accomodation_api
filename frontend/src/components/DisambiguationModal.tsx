"use client";

import React from "react";
import { MapPin, ArrowRight } from "lucide-react";
import { GeocodeCandidate } from "@/types";

interface DisambiguationProps {
  candidates?: GeocodeCandidate[];
  onSelectCandidate: (candidate: GeocodeCandidate) => void;
}

export default function DisambiguationModal({ candidates, onSelectCandidate }: DisambiguationProps) {
  if (!candidates || candidates.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="Location Disambiguation"
      className="p-3.5 bg-indigo-950/40 rounded-xl border border-indigo-500/40 shadow-lg text-xs space-y-2"
    >
      <div className="flex items-center gap-2 text-indigo-300 font-semibold">
        <MapPin className="h-4 w-4" />
        <span>Did you mean one of these specific places?</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {candidates.map((c, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => onSelectCandidate(c)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 hover:text-white transition"
          >
            <span>{c.display_name.split(",").slice(0, 3).join(",")}</span>
            <ArrowRight className="h-3 w-3 text-indigo-400" />
          </button>
        ))}
      </div>
    </div>
  );
}
