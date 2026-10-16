"use client";

import React from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Info, CheckCircle2, AlertOctagon, Sparkles } from "lucide-react";
import { SearchReport } from "@/types";

interface ScorePanelProps {
  report: SearchReport;
}

export default function ScorePanel({ report }: ScorePanelProps) {
  const { area_score, location } = report;
  const { safety_score, band, confidence, S_static, S_dynamic } = area_score;

  // Color-blind safe styling mapping
  const getBandStyle = (code: string) => {
    switch (code.toLowerCase()) {
      case "low":
        return {
          bg: "bg-emerald-950/70 border-emerald-500/40 text-emerald-300",
          ring: "stroke-emerald-400",
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          icon: ShieldCheck,
        };
      case "moderate":
        return {
          bg: "bg-cyan-950/70 border-cyan-500/40 text-cyan-300",
          ring: "stroke-cyan-400",
          badge: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
          icon: ShieldAlert,
        };
      case "elevated":
        return {
          bg: "bg-amber-950/70 border-amber-500/40 text-amber-300",
          ring: "stroke-amber-400",
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          icon: AlertTriangle,
        };
      case "high":
        return {
          bg: "bg-orange-950/70 border-orange-500/40 text-orange-300",
          ring: "stroke-orange-400",
          badge: "bg-orange-500/20 text-orange-300 border-orange-500/40",
          icon: AlertOctagon,
        };
      case "severe":
      default:
        return {
          bg: "bg-rose-950/70 border-rose-500/40 text-rose-300",
          ring: "stroke-rose-400",
          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
          icon: AlertOctagon,
        };
    }
  };

  const style = getBandStyle(band.code);
  const BandIcon = style.icon;

  const getConfidenceBadge = (conf: string) => {
    switch (conf) {
      case "high":
        return { label: "High Confidence", color: "bg-emerald-900/60 text-emerald-300 border-emerald-700/60" };
      case "medium":
        return { label: "Medium Confidence", color: "bg-amber-900/60 text-amber-300 border-amber-700/60" };
      case "low":
      default:
        return { label: "Low Confidence", color: "bg-rose-900/60 text-rose-300 border-rose-700/60" };
    }
  };

  const confBadge = getConfidenceBadge(confidence);

  return (
    <section
      aria-label="Safety Score Overview"
      className="bg-black rounded-2xl p-5 border border-zinc-800 shadow-2xl"
    >
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        {/* Main Score Section */}
        <div className="flex items-center gap-5 w-full lg:w-auto">
          {/* Circular Score Gauge */}
          <div className="relative w-28 h-28 flex items-center justify-center shrink-0">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="42"
                className="stroke-zinc-800"
                strokeWidth="9"
                fill="transparent"
              />
              <circle
                cx="50"
                cy="50"
                r="42"
                className={`${style.ring} transition-all duration-1000 ease-out`}
                strokeWidth="9"
                strokeDasharray="264"
                strokeDashoffset={264 - (264 * safety_score) / 100}
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-3xl font-extrabold text-white tracking-tighter" id="overall-safety-score">
                {safety_score}
              </span>
              <span className="text-[10px] text-zinc-400 font-medium uppercase tracking-wider">
                out of 100
              </span>
            </div>
          </div>

          {/* Band details */}
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span
                id="safety-band-label"
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${style.badge}`}
              >
                <BandIcon className="h-3.5 w-3.5" />
                {band.label}
              </span>
              <span
                id="confidence-label-badge"
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${confBadge.color}`}
              >
                {confBadge.label}
              </span>
              {report.safety_decision && (
                <span
                  id="ai-decision-badge"
                  title={`Assessed by ${report.safety_decision.model}`}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                    report.safety_decision.choice === "safe"
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50"
                      : report.safety_decision.choice === "caution"
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/50"
                      : "bg-rose-500/20 text-rose-300 border-rose-500/50"
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                  AI Decision: {report.safety_decision.choice.toUpperCase()} ({Math.round(report.safety_decision.confidence * 100)}%)
                </span>
              )}
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">
              {location.display_name.split(",")[0]}
            </h2>
            <p className="text-xs text-zinc-300 max-w-sm leading-relaxed">
              {band.description}
            </p>
          </div>
        </div>

        {/* Sub-Scores (Static vs Dynamic) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full lg:max-w-md">
          <div className="bg-gradient-to-b from-zinc-900/40 via-zinc-950 to-zinc-950 p-4 rounded-xl border border-zinc-800 border-t-2 border-t-cyan-500/80 shadow-lg hover:border-zinc-700 transition">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-200">Static Terrain & Baseline</span>
              <span className="text-xs font-bold text-white bg-zinc-900 border border-zinc-700/80 px-2 py-0.5 rounded font-mono">
                Risk: {Math.round(S_static * 100)}%
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Susceptibility models, slope geology, and multi-year regional crime baselines.
            </p>
          </div>

          <div className="bg-gradient-to-b from-zinc-900/40 via-zinc-950 to-zinc-950 p-4 rounded-xl border border-zinc-800 border-t-2 border-t-amber-500/80 shadow-lg hover:border-zinc-700 transition">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-200">Live & Dynamic Hazards</span>
              <span className="text-xs font-bold text-white bg-zinc-900 border border-zinc-700/80 px-2 py-0.5 rounded font-mono">
                Risk: {Math.round(S_dynamic * 100)}%
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Real-time flood/cyclone alerts (GDACS), seismic feeds (USGS), NASA FIRMS fires, and weather.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
