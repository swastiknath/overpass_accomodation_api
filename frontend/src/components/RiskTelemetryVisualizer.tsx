"use client";

import React, { useState } from "react";
import {
  Compass,
  Activity,
  Layers,
  PieChart,
  ShieldAlert,
  ShieldCheck,
  Zap,
  Radio,
  Flame,
  Waves,
} from "lucide-react";
import { SearchReport, SignalContribution } from "@/types";
import CombinedTelemetryLinePlot from "./CombinedTelemetryLinePlot";

interface RiskTelemetryVisualizerProps {
  report: SearchReport;
}

export default function RiskTelemetryVisualizer({ report }: RiskTelemetryVisualizerProps) {
  const [activeView, setActiveView] = useState<"lines" | "spectrum">("lines");

  const contributions = report.contributions || [];
  const coverage = report.coverage || {};
  const safetyScore = report.area_score?.safety_score ?? 75;
  const sStatic = report.area_score?.S_static ?? 0.35;
  const sDynamic = report.area_score?.S_dynamic ?? 0.15;
  const scoreBand = report.area_score?.band?.label || "Moderate Caution";

  // Compute threat share percentages from active contributions
  const totalContribWeight = contributions.reduce((acc, c) => acc + (c.contribution || 0), 0) || 1.0;
  const sortedContribs = [...contributions].sort((a, b) => (b.contribution || 0) - (a.contribution || 0));

  const getHazardColor = (type: string) => {
    switch (type) {
      case "conflict":
        return "#f43f5e"; // rose
      case "crime":
        return "#fb923c"; // amber
      case "weather":
        return "#38bdf8"; // cyan
      case "earthquake":
        return "#a855f7"; // purple
      case "flood":
        return "#06b6d4"; // teal
      case "fire":
        return "#f97316"; // orange
      case "news":
        return "#818cf8"; // indigo
      default:
        return "#10b981"; // emerald
    }
  };

  return (
    <section
      aria-label="Multi-Hazard Spectrum and Exposure Line Plot"
      className="bg-black/50 backdrop-blur-2xl border border-white/[0.08] shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset,0_12px_36px_0_rgba(0,0,0,0.5)] rounded-2xl p-5 sm:p-6 space-y-5"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.08] pb-4">
        <div className="flex items-center gap-2.5">
          <Activity className="h-5 w-5 text-cyan-400 shrink-0" />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm sm:text-base font-bold tracking-tight text-white uppercase">
                Hazard Spectrum & Multi-Line Plot
              </h3>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-cyan-950/70 text-cyan-300 border border-cyan-800/60">
                <Radio className="h-2.5 w-2.5 animate-pulse text-cyan-400" />
                Live Telemetry
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Continuous multi-stream trajectory across hazards & resilience
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 p-1 bg-white/[0.04] rounded-xl border border-white/[0.08] self-start sm:self-center">
          <button
            type="button"
            onClick={() => setActiveView("lines")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
              activeView === "lines"
                ? "bg-white/[0.15] text-white shadow-sm border border-white/[0.20]"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
            <span>Combined Line Plot</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveView("spectrum")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
              activeView === "spectrum"
                ? "bg-white/[0.15] text-white shadow-sm border border-white/[0.20]"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <PieChart className="h-3.5 w-3.5" />
            <span>Threat Share</span>
          </button>
        </div>
      </div>

      {/* View 1: Combined Multi-Hazard Line Plot */}
      {activeView === "lines" && (
        <CombinedTelemetryLinePlot report={report} />
      )}

      {/* View 2: Proportional Threat Share Spectrum */}
      {activeView === "spectrum" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-white uppercase tracking-wider">
              Proportional Hazard Contribution
            </span>
            <span className="font-mono text-zinc-400">{sortedContribs.length} Active Feeds</span>
          </div>

          {/* Segmented Risk Composition Bar */}
          <div className="w-full h-3 bg-zinc-900 rounded-full overflow-hidden flex border border-zinc-800 shadow-inner">
            {sortedContribs.length === 0 ? (
              <div className="w-full h-full bg-emerald-500/80 rounded-full" />
            ) : (
              sortedContribs.map((c, idx) => {
                const pct = Math.max(8, Math.round(((c.contribution || 0) / totalContribWeight) * 100));
                const color = getHazardColor(c.hazard_type);
                return (
                  <div
                    key={idx}
                    style={{ width: `${pct}%`, backgroundColor: color }}
                    className="h-full border-r border-black/40 transition-all duration-300"
                    title={`${c.human_label}: ${pct}%`}
                  />
                );
              })
            )}
          </div>

          {/* Detailed Contribution Breakdown Rows */}
          <div className="space-y-2 pt-1">
            {sortedContribs.length === 0 ? (
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04] text-center text-xs text-zinc-500">
                No active threats detected. Location operating under baseline safety parameters.
              </div>
            ) : (
              sortedContribs.map((c, idx) => {
                const pct = Math.round(((c.contribution || 0) / totalContribWeight) * 100);
                const color = getHazardColor(c.hazard_type);

                return (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.12] transition flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span
                        className="h-2.5 w-2.5 rounded-full shrink-0 shadow-sm"
                        style={{ backgroundColor: color }}
                      />
                      <div className="min-w-0">
                        <span className="font-semibold text-white truncate block">{c.human_label}</span>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {c.source.toUpperCase()} • σ: {c.sigma} • {c.distance_km} km
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs font-mono font-bold text-white">{pct}%</span>
                      <span className="text-[10px] text-zinc-500 font-mono">weight</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Safety Score Sensitivity Split */}
      <div className="p-3.5 sm:p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-amber-400 shrink-0" />
          <span>
            Static Baseline: <strong className="text-white font-mono">{Math.round(sStatic * 100)}%</strong> •
            Dynamic Inflow: <strong className="text-white font-mono">{Math.round(sDynamic * 100)}%</strong>
          </span>
        </div>
        <span className="text-[11px] font-semibold text-zinc-400 capitalize">
          {scoreBand}
        </span>
      </div>
    </section>
  );
}
