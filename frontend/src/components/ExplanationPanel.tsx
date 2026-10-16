"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Layers,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Compass,
  Radar,
  HelpCircle,
  ShieldCheck,
  Scale,
} from "lucide-react";
import { SearchReport, SignalContribution } from "@/types";
import HazardRadarChart from "@/components/HazardRadarChart";

interface ExplanationPanelProps {
  report: SearchReport;
}

export default function ExplanationPanel({ report }: ExplanationPanelProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [activeView, setActiveView] = useState<"radar" | "list">("radar");
  const [showFormulaExplainer, setShowFormulaExplainer] = useState(false);
  const { contributions, coverage, sources, area_score } = report;

  const toggleExpand = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  const getCoverageBadge = (status: string) => {
    switch (status) {
      case "contributing":
        return {
          label: "Active Signal",
          color: "bg-emerald-950/80 text-emerald-300 border-emerald-700/60",
          icon: CheckCircle2,
        };
      case "no_signal_found":
        return {
          label: "No Hazard Detected",
          color: "bg-zinc-900 text-zinc-300 border-zinc-800",
          icon: CheckCircle2,
        };
      case "source_failed":
        return {
          label: "Source Failed",
          color: "bg-rose-950/80 text-rose-300 border-rose-800/60",
          icon: XCircle,
        };
      case "not_available_for_region":
      default:
        return {
          label: "Not Available for Region",
          color: "bg-amber-950/80 text-amber-300 border-amber-800/60",
          icon: AlertCircle,
        };
    }
  };

  return (
    <section
      aria-label="Hazard Explanation & Data Coverage"
      className="bg-black rounded-2xl p-5 border border-zinc-800 shadow-2xl space-y-6"
    >
      {/* Header with Title and Mode Toggles */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Primary Hazard Drivers & Contributions
            </h3>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Deterministic multi-source safety decomposition. Sum of contributions = 100%.
          </p>
        </div>

        {/* View toggles & Help trigger */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowFormulaExplainer(!showFormulaExplainer)}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg bg-zinc-900 text-zinc-300 hover:text-white border border-zinc-800 transition"
            title="Explain mathematical model parameters"
          >
            <HelpCircle className="h-3.5 w-3.5 text-cyan-400" />
            <span>How it Works</span>
          </button>

          <div className="flex bg-zinc-900 p-0.5 rounded-lg border border-zinc-800 text-xs">
            <button
              type="button"
              onClick={() => setActiveView("radar")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition font-medium ${
                activeView === "radar"
                  ? "bg-zinc-800 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Radar className="h-3.5 w-3.5 text-cyan-400" />
              <span>Radar View</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveView("list")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition font-medium ${
                activeView === "list"
                  ? "bg-zinc-800 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Layers className="h-3.5 w-3.5 text-indigo-400" />
              <span>Drivers List</span>
            </button>
          </div>
        </div>
      </div>

      {/* Explanatory Educational Callout */}
      {showFormulaExplainer && (
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/90 text-xs text-zinc-300 space-y-3 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-300 font-semibold">
              <Scale className="h-4 w-4" />
              <span>Deterministic Fusion Formula Explained</span>
            </div>
            <button
              type="button"
              onClick={() => setShowFormulaExplainer(false)}
              className="text-zinc-500 hover:text-white text-sm"
            >
              &times;
            </button>
          </div>
          <p className="text-zinc-400 leading-relaxed">
            Safety scores are computed using pure mathematical aggregation, never guessed or altered by AI.
            Each observed incident receives an <span className="text-white font-medium">Effective Weight (w)</span> based on:
          </p>
          <div className="p-2.5 rounded-lg bg-zinc-900/80 border border-zinc-800 font-mono text-[11px] text-cyan-300 text-center">
            w = base_weight &times; confidence &times; resolution_tier &times; temporal_decay &times; spatial_kernel
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1 text-zinc-400">
            <div className="bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-800/70">
              <span className="text-zinc-200 font-semibold block mb-0.5">Normalized Hazard (&sigma;)</span>
              Normalized intensity scaled from 0.0 (baseline calm) to 1.0 (severe hazard/emergency).
            </div>
            <div className="bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-800/70">
              <span className="text-zinc-200 font-semibold block mb-0.5">Spatial & Temporal Kernels</span>
              Risk decays smoothly with distance (Gaussian kernel) and age (half-life decay).
            </div>
            <div className="bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-800/70">
              <span className="text-zinc-200 font-semibold block mb-0.5">Resolution Tier</span>
              Differentiates pin-point satellite coordinates (1.0), neighborhood grids (0.8), and district averages (0.6).
            </div>
            <div className="bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-800/70">
              <span className="text-zinc-200 font-semibold block mb-0.5">Coverage Freshness Audit</span>
              Missing data is never treated as zero risk. Every configured feed is monitored explicitly.
            </div>
          </div>
        </div>
      )}

      {/* Primary Hazard Drivers Content: Radar or List */}
      {activeView === "radar" ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">
          <div className="lg:col-span-6">
            <HazardRadarChart
              contributions={contributions}
              coverage={coverage}
              safetyScore={area_score?.safety_score}
            />
          </div>

          <div className="lg:col-span-6 space-y-3">
            <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
              <Compass className="h-3.5 w-3.5 text-cyan-400" />
              <span>Observed Hazard Weights & Contributions</span>
            </h4>

            {contributions.length === 0 ? (
              <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-400 text-center">
                No active elevated hazard signals detected in this search area.
              </div>
            ) : (
              <div className="space-y-2">
                {contributions.slice(0, 4).map((c: SignalContribution, idx: number) => {
                  const contribPct = Math.round(c.contribution * 100);
                  return (
                    <div
                      key={c.evidence_ref || idx}
                      className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/90 text-xs text-zinc-300 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white flex items-center gap-2">
                          {c.human_label}
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 uppercase">
                            {c.source}
                          </span>
                        </span>
                        <span className="font-bold text-cyan-400 font-mono text-sm">{contribPct}%</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-cyan-500 via-indigo-500 to-rose-500 h-1.5 rounded-full"
                          style={{ width: `${Math.max(4, contribPct)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-0.5">
                        <span>Distance: {c.distance_km} km ({c.resolution_tier})</span>
                        <span>Normalized Hazard (&sigma;): {c.sigma}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Full Itemized Drivers List with Accordion */
        <div className="space-y-2.5">
          {contributions.length === 0 ? (
            <div className="bg-zinc-950 rounded-xl p-4 text-center text-xs text-zinc-400 border border-zinc-800">
              No active hazards or elevated risk signals detected in this search area.
            </div>
          ) : (
            contributions.map((c: SignalContribution, idx: number) => {
              const isExpanded = expandedIndex === idx;
              const contribPct = Math.round(c.contribution * 100);

              return (
                <div
                  key={c.evidence_ref || idx}
                  className="bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden transition"
                >
                  {/* Summary Bar */}
                  <button
                    type="button"
                    onClick={() => toggleExpand(idx)}
                    aria-expanded={isExpanded}
                    className="w-full text-left p-3.5 flex items-center justify-between gap-3 hover:bg-zinc-900/60 transition"
                  >
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white flex items-center gap-2">
                          {c.human_label}
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                            {c.source}
                          </span>
                        </span>
                        <span className="text-xs font-bold text-cyan-400 font-mono">
                          {contribPct}%
                        </span>
                      </div>

                      {/* Visual Contribution Bar */}
                      <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-cyan-500 via-indigo-500 to-rose-500 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(4, contribPct)}%` }}
                        />
                      </div>
                    </div>

                    <div className="text-zinc-400 pl-2">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </div>
                  </button>

                  {/* Expandable Parameter Breakdown */}
                  {isExpanded && (
                    <div className="px-3.5 pb-3.5 pt-2 border-t border-zinc-800/80 bg-zinc-950 text-xs text-zinc-300 space-y-3">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                        <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                          <span className="text-[10px] text-zinc-400 block">Distance to Query</span>
                          <span className="font-semibold text-white text-xs">{c.distance_km} km</span>
                        </div>
                        <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                          <span className="text-[10px] text-zinc-400 block">Resolution Tier</span>
                          <span className="font-semibold text-white text-xs capitalize">{c.resolution_tier}</span>
                        </div>
                        <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                          <span className="text-[10px] text-zinc-400 block">Normalized Hazard (&sigma;)</span>
                          <span className="font-semibold text-white text-xs font-mono">{c.sigma}</span>
                        </div>
                        <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                          <span className="text-[10px] text-zinc-400 block">Effective Weight (w)</span>
                          <span className="font-semibold text-white text-xs font-mono">{c.weight}</span>
                        </div>
                      </div>

                      {/* Weight Breakdown Formula */}
                      {c.config_parameters && (
                        <div className="bg-zinc-900/60 p-2.5 rounded-lg border border-zinc-800/80 text-[11px] text-zinc-400 space-y-1">
                          <span className="font-semibold text-zinc-300 block">
                            Weight Parameters Breakdown [w = base_weight &times; confidence &times; resolution &times; decay &times; spatial_kernel]:
                          </span>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-zinc-400">
                            <span>Base: {c.config_parameters.base_weight}</span>
                            <span>Confidence: {c.config_parameters.confidence}</span>
                            <span>Resolution: {c.config_parameters.resolution_factor}</span>
                            <span>Decay: {c.config_parameters.temporal_decay}</span>
                            <span>Spatial K: {c.config_parameters.spatial_kernel}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* 2. Coverage Audit & Freshness Grid */}
      <div className="pt-4 border-t border-zinc-800/80">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Data Source Coverage & Freshness Audit
            </h3>
          </div>
          <span className="text-[11px] text-zinc-500 font-mono">Live Audited</span>
        </div>

        <p className="text-xs text-zinc-400 mb-4 leading-relaxed">
          Missing data is <span className="text-white font-medium">never treated as zero risk</span>. Every configured hazard layer is explicitly audited for telemetry freshness and regional availability.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
          {Object.entries(coverage).map(([layer, status]) => {
            const badge = getCoverageBadge(status);
            const BadgeIcon = badge.icon;
            const srcMeta = sources[layer] || sources[`${layer}_client`] || sources[`${layer}_feed`];

            return (
              <div
                key={layer}
                className="bg-zinc-950 p-3 rounded-xl border border-zinc-800 flex items-center justify-between gap-2 transition hover:border-zinc-700"
              >
                <div>
                  <span className="text-xs font-semibold text-white capitalize block">
                    {layer.replace("_", " ")}
                  </span>
                  {srcMeta?.last_fetched && (
                    <span className="text-[10px] text-zinc-500 block truncate max-w-[130px]">
                      {new Date(srcMeta.last_fetched).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                </div>

                <div
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${badge.color}`}
                >
                  <BadgeIcon className="h-3 w-3 shrink-0" />
                  <span>{badge.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
