"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Layers, CheckCircle2, XCircle, AlertCircle, Clock, Compass } from "lucide-react";
import { SearchReport, SignalContribution } from "@/types";

interface ExplanationPanelProps {
  report: SearchReport;
}

export default function ExplanationPanel({ report }: ExplanationPanelProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const { contributions, coverage, sources } = report;

  const toggleExpand = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  const getCoverageBadge = (status: string) => {
    switch (status) {
      case "contributing":
        return {
          label: "Active Signal",
          color: "bg-emerald-900/60 text-emerald-300 border-emerald-700/60",
          icon: CheckCircle2,
        };
      case "no_signal_found":
        return {
          label: "No Hazard Detected",
          color: "bg-slate-800 text-slate-300 border-slate-700",
          icon: CheckCircle2,
        };
      case "source_failed":
        return {
          label: "Source Failed",
          color: "bg-rose-900/60 text-rose-300 border-rose-700/60",
          icon: XCircle,
        };
      case "not_available_for_region":
      default:
        return {
          label: "Not Available for Region",
          color: "bg-amber-900/60 text-amber-300 border-amber-700/60",
          icon: AlertCircle,
        };
    }
  };

  return (
    <section
      aria-label="Hazard Explanation & Data Coverage"
      className="bg-slate-900/90 rounded-2xl p-5 border border-slate-800 shadow-xl space-y-6"
    >
      {/* 1. Top Risk Drivers (Contribution Breakdown) */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Primary Hazard Drivers & Contributions
            </h3>
          </div>
          <span className="text-xs text-slate-400">Sum of contributions = 100%</span>
        </div>

        {contributions.length === 0 ? (
          <div className="bg-slate-800/40 rounded-xl p-4 text-center text-xs text-slate-400 border border-slate-800">
            No active hazards or elevated risk signals detected in this search area.
          </div>
        ) : (
          <div className="space-y-2.5">
            {contributions.map((c: SignalContribution, idx: number) => {
              const isExpanded = expandedIndex === idx;
              const contribPct = Math.round(c.contribution * 100);

              return (
                <div
                  key={c.evidence_ref || idx}
                  className="bg-slate-800/70 rounded-xl border border-slate-700/60 overflow-hidden transition"
                >
                  {/* Summary Bar */}
                  <button
                    type="button"
                    onClick={() => toggleExpand(idx)}
                    aria-expanded={isExpanded}
                    className="w-full text-left p-3.5 flex items-center justify-between gap-3 hover:bg-slate-800 transition"
                  >
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white flex items-center gap-2">
                          {c.human_label}
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-slate-700 text-slate-300">
                            {c.source}
                          </span>
                        </span>
                        <span className="text-xs font-bold text-indigo-400 font-mono">
                          {contribPct}%
                        </span>
                      </div>

                      {/* Visual Contribution Bar */}
                      <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-indigo-500 to-rose-500 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(4, contribPct)}%` }}
                        />
                      </div>
                    </div>

                    <div className="text-slate-400 pl-2">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </div>
                  </button>

                  {/* Expandable Parameter Breakdown */}
                  {isExpanded && (
                    <div className="px-3.5 pb-3.5 pt-1 border-t border-slate-700/50 bg-slate-850 text-xs text-slate-300 space-y-2.5">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                        <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
                          <span className="text-[10px] text-slate-400 block">Distance to Query</span>
                          <span className="font-semibold text-white">{c.distance_km} km</span>
                        </div>
                        <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
                          <span className="text-[10px] text-slate-400 block">Resolution Tier</span>
                          <span className="font-semibold text-white capitalize">{c.resolution_tier}</span>
                        </div>
                        <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
                          <span className="text-[10px] text-slate-400 block">Normalized Hazard (σ)</span>
                          <span className="font-semibold text-white font-mono">{c.sigma}</span>
                        </div>
                        <div className="bg-slate-900/80 p-2 rounded-lg border border-slate-800">
                          <span className="text-[10px] text-slate-400 block">Effective Weight (w)</span>
                          <span className="font-semibold text-white font-mono">{c.weight}</span>
                        </div>
                      </div>

                      {/* Weight Breakdown */}
                      <div className="bg-slate-900/90 p-3 rounded-lg border border-slate-800 space-y-1">
                        <span className="text-[11px] font-semibold text-slate-200 block">
                          Weight Parameters Breakdown [w = base_weight × confidence × resolution × decay × spatial_kernel]:
                        </span>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400 font-mono">
                          <span>Base: {c.config_parameters.base_weight}</span>
                          <span>Confidence: {c.config_parameters.confidence}</span>
                          <span>Resolution: {c.config_parameters.resolution_factor}</span>
                          <span>Decay: {c.config_parameters.temporal_decay}</span>
                          <span>Spatial K: {c.config_parameters.spatial_kernel}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. Coverage Report & Data Freshness */}
      <div className="pt-2 border-t border-slate-800 space-y-3">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider">
          Data Source Coverage & Freshness Audit
        </h3>
        <p className="text-xs text-slate-400 leading-normal">
          Missing data is never treated as zero risk. Every configured hazard layer is accounted for explicitly.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {Object.entries(coverage).map(([hazard, status]) => {
            const badge = getCoverageBadge(status);
            const BadgeIcon = badge.icon;

            return (
              <div
                key={hazard}
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs"
              >
                <span className="font-medium text-slate-200 capitalize">
                  {hazard.replace("_", " ")}
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold border ${badge.color}`}
                >
                  <BadgeIcon className="h-3 w-3" />
                  {badge.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
