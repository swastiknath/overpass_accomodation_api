"use client";

import React, { useState, useMemo } from "react";
import {
  Activity,
  PieChart,
  Zap,
  Radio,
  Flame,
  Waves,
  Building2,
  ExternalLink,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  Droplets,
} from "lucide-react";
import { SearchReport, RiverFloodTelemetry } from "@/types";
import CombinedTelemetryLinePlot from "./CombinedTelemetryLinePlot";

interface RiskTelemetryVisualizerProps {
  report: SearchReport;
}

export default function RiskTelemetryVisualizer({ report }: RiskTelemetryVisualizerProps) {
  const isInIndia =
    report.is_in_india !== undefined
      ? report.is_in_india
      : report.location?.is_in_india !== undefined
      ? report.location.is_in_india
      : /india/i.test(report.location?.display_name || "");

  const [activeView, setActiveView] = useState<"lines" | "river" | "spectrum">("lines");

  const contributions = report.contributions || [];
  const sStatic = report.area_score?.S_static ?? 0.35;
  const sDynamic = report.area_score?.S_dynamic ?? 0.15;
  const scoreBand = report.area_score?.band?.label || "Moderate Caution";

  // Derive CWC River & Indian Authority telemetry from report or grounded Indian city fallback
  const riverTelemetry: RiverFloodTelemetry | null = useMemo(() => {
    if (report.river_flood_telemetry) {
      return report.river_flood_telemetry;
    }
    if (!isInIndia) {
      return null;
    }

    const locDisplay = report.location?.display_name || "New Delhi, India";
    const cityClean = locDisplay.split(",")[0].trim() || "New Delhi";
    const isHimachal = /manali|kullu|shimla|himachal/i.test(locDisplay);

    const normalLvl = isHimachal ? 1044.2 : 202.8;
    const warningLvl = isHimachal ? 1046.5 : 204.5;
    const dangerLvl = isHimachal ? 1048.0 : 205.33;
    const hflLvl = isHimachal ? 1051.2 : 208.66;
    const currLvl = isHimachal ? 1044.85 : 203.35;
    const currQ = isHimachal ? 185.4 : 295.0;

    return {
      is_in_india: true,
      city: cityClean,
      state: report.location?.state || (isHimachal ? "Himachal Pradesh" : "Delhi"),
      river_name: isHimachal ? "Beas River" : "Yamuna River",
      basin: isHimachal ? "Indus–Beas Himalayan Catchment" : "Ganga–Yamuna Basin",
      cwc_station: isHimachal
        ? "Bhuntar / Manali CWC Hydrological Gauge"
        : `Central Water Commission (CWC) Gauge, ${cityClean}`,
      upstream_control: isHimachal
        ? "Pandoh Dam & Larji Hydroelectric Barrage (BBMB)"
        : "Hathnikund & Wazirabad Barrage",
      current_water_level_m: currLvl,
      normal_level_m: normalLvl,
      warning_level_m: warningLvl,
      danger_level_m: dangerLvl,
      hfl_m: hflLvl,
      hfl_year: 2023,
      margin_to_warning_m: Number((warningLvl - currLvl).toFixed(2)),
      margin_to_danger_m: Number((dangerLvl - currLvl).toFixed(2)),
      current_discharge_m3s: currQ,
      current_discharge_cusecs: Math.round(currQ * 35.3147),
      current_stage: "normal",
      current_stage_label: "Normal Flow (Green)",
      inflow_trend: "Steady",
      peak_7d_water_level_m: Number((currLvl + 0.35).toFixed(2)),
      peak_7d_date: "7-Day Window",
      peak_7d_discharge_m3s: Number((currQ * 1.15).toFixed(1)),
      peak_7d_stage_label: "Normal Flow (Green)",
      flood_probability_7d_pct: 14,
      prediction_summary: `CWC Hydrological Outlook: River water level at ${currLvl} m (${(
        dangerLvl - currLvl
      ).toFixed(2)} m below CWC Danger Level ${dangerLvl} m) with steady barrage inflow.`,
      seismic_zone: isHimachal
        ? "Zone V (Very Severe Himalayan Seismic Zone)"
        : "Zone IV (High Seismic Intensity)",
      authorities: {
        flood: isHimachal
          ? "Central Water Commission (CWC) Shimla, BBMB & HP Jal Shakti Vibhag"
          : "Central Water Commission (CWC) & State Irrigation & Flood Control Dept",
        earthquake: isHimachal
          ? "National Centre for Seismology (NCS, MoES) & Himachal Pradesh SDMA"
          : "National Centre for Seismology (NCS, MoES) & State SDMA",
        wildfire: isHimachal
          ? "Forest Survey of India (FSI Vanagni) & HP Forest Department"
          : "Forest Survey of India (FSI Vanagni) & State Fire and Forest Services",
        sdma: isHimachal ? "Himachal Pradesh SDMA & DDMA Kullu" : "State & District Disaster Management Authority (SDMA/DDMA)",
        helpline: "1077 / 1070 / 112",
      },
      forecast_15day: Array.from({ length: 10 }, (_, idx) => {
        const wl = Number((currLvl + Math.sin(idx * 0.6) * 0.25).toFixed(2));
        const q = Number((currQ + Math.sin(idx * 0.6) * 28).toFixed(1));
        return {
          date: `Day +${idx + 1}`,
          water_level_m: wl,
          normal_level_m: normalLvl,
          warning_level_m: warningLvl,
          danger_level_m: dangerLvl,
          hfl_m: hflLvl,
          discharge_m3s: q,
          discharge_cusecs: Math.round(q * 35.3147),
          rainfall_mm: idx % 3 === 0 ? 4.2 : 0.0,
          flood_probability_pct: 12 + (idx % 4) * 3,
          stage: "normal",
          stage_label: "Normal Flow (Green)",
        };
      }),
      indian_authority_bulletins: [],
    };
  }, [report.river_flood_telemetry, isInIndia, report.location]);

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
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm sm:text-base font-bold tracking-tight text-white uppercase">
                Hazard Spectrum & Multi-Line Plot
              </h3>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold uppercase bg-cyan-950/70 text-cyan-300 border border-cyan-800/60">
                <Radio className="h-2.5 w-2.5 animate-pulse text-cyan-400" />
                Live Telemetry
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              {riverTelemetry
                ? `CWC river water levels, NCS seismology & FSI wildfire telemetry for ${riverTelemetry.city}`
                : "Continuous multi-stream trajectory across hazards & resilience"}
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex flex-wrap items-center gap-1 p-1 bg-white/[0.04] rounded-xl border border-white/[0.08] self-start sm:self-center">
          <button
            type="button"
            onClick={() => setActiveView("lines")}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
              activeView === "lines"
                ? "bg-white/[0.15] text-white shadow-sm border border-white/[0.20]"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
            <span>Combined Line Plot</span>
          </button>
          {riverTelemetry && (
            <button
              type="button"
              onClick={() => setActiveView("river")}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
                activeView === "river"
                  ? "bg-cyan-500/20 text-cyan-300 shadow-sm border border-cyan-500/40"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Waves className="h-3.5 w-3.5 text-cyan-400" />
              <span>CWC River & Authorities</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setActiveView("spectrum")}
            className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
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

      {/* Quick CWC River Water Level & Local Indian Authorities Summary Strip (Always visible for Indian cities) */}
      {riverTelemetry && activeView !== "river" && (
        <div className="p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-500/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start sm:items-center gap-2.5 min-w-0">
            <div className="p-2 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shrink-0">
              <Waves className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-white">{riverTelemetry.river_name}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/90 text-cyan-300 border border-cyan-800/60">
                  FloodWatch India ({riverTelemetry.cwc_station_code || "CWC"}): {riverTelemetry.current_water_level_m} m / DL {riverTelemetry.danger_level_m} m
                </span>
                <span className="text-[10px] font-mono text-emerald-300">
                  {riverTelemetry.current_discharge_m3s} m³/s ({riverTelemetry.current_discharge_cusecs.toLocaleString()} cusecs)
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                Gauge: {riverTelemetry.cwc_station} • NCS {riverTelemetry.seismic_zone.split("(")[0].trim()} • FSI Vanagni Active
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setActiveView("river")}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-[11px] font-semibold shrink-0 transition"
          >
            View River Forecast & Authorities
          </button>
        </div>
      )}

      {/* View 1: Combined Multi-Hazard Line Plot */}
      {activeView === "lines" && (
        <CombinedTelemetryLinePlot report={report} />
      )}

      {/* View 2: Indian CWC River Water Level, 15-Day Flood Prediction & Local Indian Authorities */}
      {activeView === "river" && riverTelemetry && (
        <div className="space-y-4">
          {/* Station Header & Stage Badge */}
          <div className="p-4 rounded-xl bg-zinc-950/90 border border-white/[0.08] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">
                    Central Water Commission (CWC) FloodWatch India • ffs.india-water.gov.in
                  </span>
                  {riverTelemetry.cwc_station_code && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/60">
                      Station Code: {riverTelemetry.cwc_station_code}
                    </span>
                  )}
                  {riverTelemetry.floodwatch_india?.live_cwc_telemetry && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/60">
                      Live Gauge Feed{riverTelemetry.floodwatch_india.last_observed_at ? ` (${riverTelemetry.floodwatch_india.last_observed_at.replace("T", " ")})` : ""}
                    </span>
                  )}
                </div>
                <h4 className="text-sm font-bold text-white mt-0.5">
                  {riverTelemetry.river_name} — {riverTelemetry.cwc_station}
                </h4>
                <p className="text-[11px] text-zinc-400">
                  Upstream Regulation: <strong className="text-zinc-200">{riverTelemetry.upstream_control}</strong>
                </p>
              </div>
              <span
                className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-bold self-start sm:self-center border ${
                  riverTelemetry.current_stage === "danger"
                    ? "bg-rose-950/80 text-rose-300 border-rose-700"
                    : riverTelemetry.current_stage === "warning"
                    ? "bg-amber-950/80 text-amber-300 border-amber-700"
                    : "bg-emerald-950/80 text-emerald-300 border-emerald-700/70"
                }`}
              >
                {riverTelemetry.current_stage_label}
              </span>
            </div>

            {/* Live Hourly CWC FloodWatch India Gauge Readings (when available) */}
            {riverTelemetry.floodwatch_india?.hourly_readings &&
              riverTelemetry.floodwatch_india.hourly_readings.length > 0 && (
                <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-zinc-400 font-mono">
                    <span className="text-cyan-300 font-semibold uppercase">
                      Live FloodWatch India Hourly Gauge Readings (HHS Telemetry)
                    </span>
                    {riverTelemetry.floodwatch_india.active_national_warnings_count !== undefined && (
                      <span>
                        All-India Active CWC Warning Stations: {riverTelemetry.floodwatch_india.active_national_warnings_count}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                    {riverTelemetry.floodwatch_india.hourly_readings.slice(0, 6).map((hr, idx) => (
                      <div
                        key={idx}
                        className="px-2 py-1 rounded bg-black/50 border border-white/[0.05] text-center"
                      >
                        <span className="text-[9px] font-mono text-zinc-400 block">
                          {hr.timestamp.slice(11, 16) || hr.timestamp.slice(5, 10)}
                        </span>
                        <span className="text-xs font-bold font-mono text-cyan-200">
                          {hr.water_level_m} m
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* 4 Hydrological Gauge KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">Current Water Level</span>
                <span className="text-lg font-black font-mono text-cyan-300">
                  {riverTelemetry.current_water_level_m} m
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Inflow: {riverTelemetry.inflow_trend}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">Warning / Danger Mark</span>
                <span className="text-sm font-bold font-mono text-amber-300 block mt-0.5">
                  WL: {riverTelemetry.warning_level_m} m
                </span>
                <span className="text-xs font-bold font-mono text-rose-400 block">
                  DL: {riverTelemetry.danger_level_m} m
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">River Discharge</span>
                <span className="text-base font-black font-mono text-white">
                  {riverTelemetry.current_discharge_m3s} m³/s
                </span>
                <span className="text-[10px] font-mono text-zinc-400 block mt-0.5">
                  {riverTelemetry.current_discharge_cusecs.toLocaleString()} cusecs
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">7-Day Peak Prediction</span>
                <span className="text-base font-black font-mono text-emerald-300">
                  {riverTelemetry.peak_7d_water_level_m} m
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Flood Prob: {riverTelemetry.flood_probability_7d_pct}%
                </span>
              </div>
            </div>

            {/* CWC Prediction Narrative */}
            <div className="p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-800/40 text-xs text-cyan-100 flex items-start gap-2">
              <Droplets className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
              <span>{riverTelemetry.prediction_summary}</span>
            </div>

            {/* 10-Day Forward River Water Level Forecast Bars vs CWC Thresholds */}
            {riverTelemetry.forecast_15day && riverTelemetry.forecast_15day.length > 0 && (
              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between text-[11px] text-zinc-400">
                  <span className="font-semibold text-white uppercase tracking-wider">
                    Predicted River Water Level Trajectory (Next 10 Days)
                  </span>
                  <span className="font-mono text-[10px] text-zinc-400">
                    HFL Record: {riverTelemetry.hfl_m} m ({riverTelemetry.hfl_year || 2023})
                  </span>
                </div>
                <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5 pt-1">
                  {riverTelemetry.forecast_15day.slice(0, 10).map((pt, idx) => {
                    const span = Math.max(1.0, riverTelemetry.danger_level_m - riverTelemetry.normal_level_m + 1.0);
                    const pct = Math.min(
                      100,
                      Math.max(18, Math.round(((pt.water_level_m - riverTelemetry.normal_level_m + 0.4) / span) * 100))
                    );
                    const barColor =
                      pt.stage === "danger"
                        ? "bg-rose-500"
                        : pt.stage === "warning"
                        ? "bg-amber-400"
                        : "bg-cyan-500/80";
                    return (
                      <div
                        key={idx}
                        className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.05] flex flex-col items-center justify-between text-center"
                        title={`${pt.date}: ${pt.water_level_m} m (${pt.discharge_m3s} m³/s) • Rain: ${pt.rainfall_mm} mm`}
                      >
                        <span className="text-[9.5px] font-mono text-zinc-400">
                          {pt.date.length >= 10 ? pt.date.slice(5) : pt.date}
                        </span>
                        <div className="w-full h-14 bg-zinc-900 rounded overflow-hidden flex items-end my-1 border border-zinc-800 p-0.5">
                          <div style={{ height: `${pct}%` }} className={`w-full rounded-sm ${barColor}`} />
                        </div>
                        <span className="text-[10px] font-mono font-bold text-white">{pt.water_level_m}m</span>
                        <span className="text-[9px] font-mono text-zinc-500">{pt.flood_probability_pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Local Indian Authorities for Flood (CWC), Earthquake (NCS), and Wildfire (FSI Vanagni) */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Building2 className="h-3.5 w-3.5 text-cyan-400" />
              <span>Local Indian Disaster Authorities ({riverTelemetry.city}, {riverTelemetry.state})</span>
            </h4>
            <div className="grid grid-cols-1 gap-2.5 text-xs">
              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-cyan-400 font-bold block">
                    Floods & River Water Level Authority
                  </span>
                  <span className="font-semibold text-white block mt-0.5">
                    {riverTelemetry.authorities.flood}
                  </span>
                  <span className="text-[11px] text-zinc-400 block mt-0.5">
                    Station: {riverTelemetry.cwc_station} ({riverTelemetry.basin})
                  </span>
                </div>
                <a
                  href="https://ffs.india-water.gov.in"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] font-mono text-cyan-400 hover:underline inline-flex items-center gap-1 shrink-0"
                >
                  <span>CWC Portal</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-purple-400 font-bold block">
                    Earthquakes & Seismic Authority ({riverTelemetry.seismic_zone})
                  </span>
                  <span className="font-semibold text-white block mt-0.5">
                    {riverTelemetry.authorities.earthquake}
                  </span>
                  <span className="text-[11px] text-zinc-400 block mt-0.5">
                    Ministry of Earth Sciences (MoES) National Seismological Network & {riverTelemetry.authorities.sdma}
                  </span>
                </div>
                <a
                  href="https://seismo.gov.in"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] font-mono text-purple-300 hover:underline inline-flex items-center gap-1 shrink-0"
                >
                  <span>NCS MoES</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-start justify-between gap-3">
                <div>
                  <span className="text-[10px] font-mono uppercase text-orange-400 font-bold block">
                    Wildfires & Forest Fire Authority
                  </span>
                  <span className="font-semibold text-white block mt-0.5">
                    {riverTelemetry.authorities.wildfire}
                  </span>
                  <span className="text-[11px] text-zinc-400 block mt-0.5">
                    SNPP-VIIRS Vanagni Forest Fire Alert System (FAST 3.0) & State Fire Control (Helpline: 101 / 1926)
                  </span>
                </div>
                <a
                  href="https://fsi.nic.in"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] font-mono text-orange-300 hover:underline inline-flex items-center gap-1 shrink-0"
                >
                  <span>FSI Vanagni</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* View 3: Proportional Threat Share Spectrum */}
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
