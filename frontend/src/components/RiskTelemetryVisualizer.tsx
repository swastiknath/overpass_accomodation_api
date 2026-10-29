"use client";

import React, { useState } from "react";
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
  Wind,
  Compass,
  Calendar,
  Clock,
  CloudRain,
  AlertOctagon,
  Info,
} from "lucide-react";
import { SearchReport, RiverFloodTelemetry, CycloneTelemetry } from "@/types";
import CombinedTelemetryLinePlot from "./CombinedTelemetryLinePlot";

interface RiskTelemetryVisualizerProps {
  report: SearchReport;
}

export default function RiskTelemetryVisualizer({ report }: RiskTelemetryVisualizerProps) {
  const [activeView, setActiveView] = useState<"lines" | "river" | "cyclone" | "spectrum">("lines");

  const contributions = report.contributions || [];
  const sStatic = report.area_score?.S_static ?? 0.35;
  const sDynamic = report.area_score?.S_dynamic ?? 0.15;
  const scoreBand = report.area_score?.band?.label || "Moderate Caution";

  // Pure real telemetry from backend (strictly zero mock or synthetic fallback)
  const riverTelemetry: RiverFloodTelemetry | null = report.river_flood_telemetry || null;
  const cycloneTelemetry: CycloneTelemetry | null = report.cyclone_telemetry || null;

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
      case "cyclone":
        return "#e11d48"; // dark rose
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

  const hasCycloneThreat =
    cycloneTelemetry?.imminent_outlook?.has_imminent_cyclone_threat ||
    cycloneTelemetry?.active_alert_status === "ACTIVE CYCLONE WARNING" ||
    cycloneTelemetry?.active_alert_status === "IMMINENT CYCLONE / DEPRESSION WATCH";

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
              {hasCycloneThreat && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-rose-950 text-rose-300 border border-rose-700 animate-pulse">
                  <Wind className="h-2.5 w-2.5" />
                  Cyclone Watch Active
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Continuous multi-stream trajectory across rivers, cyclones, seismology & civic resilience
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

          {cycloneTelemetry && (
            <button
              type="button"
              onClick={() => setActiveView("cyclone")}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold tracking-tight transition-all flex items-center gap-1.5 ${
                activeView === "cyclone"
                  ? "bg-rose-500/25 text-rose-200 shadow-sm border border-rose-500/50"
                  : hasCycloneThreat
                  ? "text-rose-400 hover:text-rose-200"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Wind className="h-3.5 w-3.5 text-rose-400" />
              <span>Cyclone Watch</span>
              {hasCycloneThreat && (
                <span className="h-1.5 w-1.5 rounded-full bg-rose-400 animate-ping" />
              )}
            </button>
          )}

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
              <span>
                {riverTelemetry.has_river_in_city ? "City Rivers & Floods" : "City River Status"}
              </span>
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

      {/* Cyclone Warning Banner (if active/imminent threat) */}
      {hasCycloneThreat && activeView !== "cyclone" && cycloneTelemetry && (
        <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start sm:items-center gap-2.5 min-w-0">
            <div className="p-2 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/40 shrink-0">
              <Wind className="h-4 w-4 animate-pulse" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-rose-200 uppercase tracking-wide">
                  {cycloneTelemetry.active_alert_status}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-700">
                  Peak Gusts: {cycloneTelemetry.imminent_outlook.peak_forecast_wind_gust_kmh} km/h (
                  {cycloneTelemetry.imminent_outlook.peak_forecast_date})
                </span>
                <span className="text-[10px] font-mono text-zinc-300">
                  SLP: {cycloneTelemetry.realtime_conditions.sea_level_pressure_hpa} hPa (Drop:{" "}
                  {cycloneTelemetry.realtime_conditions.pressure_drop_hpa} hPa)
                </span>
              </div>
              <p className="text-[11px] text-zinc-300 truncate mt-0.5">
                {cycloneTelemetry.imminent_outlook.headline}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setActiveView("cyclone")}
            className="px-3 py-1.5 rounded-lg bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 border border-rose-500/50 text-[11px] font-semibold shrink-0 transition"
          >
            View Cyclone Intelligence & Track
          </button>
        </div>
      )}

      {/* Quick River Telemetry Strip (when river is within city and view !== river) */}
      {riverTelemetry && riverTelemetry.has_river_in_city && activeView !== "river" && (
        <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start sm:items-center gap-2.5 min-w-0">
            <div className="p-1.5 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shrink-0">
              <Waves className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-white">{riverTelemetry.river_name}</span>
                {riverTelemetry.current_water_level_m !== null && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/90 text-cyan-300 border border-cyan-800/60">
                    CWC Level: {riverTelemetry.current_water_level_m} m
                    {riverTelemetry.danger_level_m ? ` / DL ${riverTelemetry.danger_level_m} m` : ""}
                  </span>
                )}
                {riverTelemetry.current_discharge_m3s !== null && (
                  <span className="text-[10px] font-mono text-emerald-300">
                    GloFAS Discharge: {riverTelemetry.current_discharge_m3s} m³/s (
                    {riverTelemetry.current_discharge_cusecs?.toLocaleString()} cusecs)
                  </span>
                )}
                {riverTelemetry.historical_flow_stats?.flow_anomaly_pct !== null &&
                  riverTelemetry.historical_flow_stats?.flow_anomaly_pct !== undefined && (
                    <span
                      className={`text-[10px] font-mono ${
                        riverTelemetry.historical_flow_stats.flow_anomaly_pct > 20
                          ? "text-amber-300"
                          : "text-zinc-400"
                      }`}
                    >
                      Anomaly: {riverTelemetry.historical_flow_stats.flow_anomaly_pct > 0 ? "+" : ""}
                      {riverTelemetry.historical_flow_stats.flow_anomaly_pct}%
                    </span>
                  )}
              </div>
              <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                Situated within {riverTelemetry.city} limits • Upstream:{" "}
                {riverTelemetry.upstream_control || "Basin Runoff"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setActiveView("river")}
            className="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-[11px] font-semibold shrink-0 transition"
          >
            View Live Flow & Historical Trends
          </button>
        </div>
      )}

      {/* View 1: Combined Multi-Hazard Line Plot */}
      {activeView === "lines" && <CombinedTelemetryLinePlot report={report} />}

      {/* View 2: Cyclone Watch (Live, Imminent & Historical ERA5 Archive) */}
      {activeView === "cyclone" && cycloneTelemetry && (
        <div className="space-y-4">
          {/* Cyclone Alert Header */}
          <div className="p-4 rounded-xl bg-zinc-950/90 border border-white/[0.08] space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-rose-400">
                    {cycloneTelemetry.monitoring_authority}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-700">
                    Observed: {cycloneTelemetry.realtime_conditions.observation_time}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white mt-1 flex items-center gap-2">
                  <Wind className="h-4 w-4 text-rose-400" />
                  <span>Atmospheric Cyclonic Telemetry & Tracking — {cycloneTelemetry.location_name}</span>
                </h4>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-mono font-bold self-start sm:self-center border ${
                  cycloneTelemetry.active_alert_status === "ACTIVE CYCLONE WARNING"
                    ? "bg-rose-950 text-rose-300 border-rose-700 animate-pulse"
                    : cycloneTelemetry.active_alert_status === "IMMINENT CYCLONE / DEPRESSION WATCH"
                    ? "bg-amber-950 text-amber-300 border-amber-700"
                    : cycloneTelemetry.active_alert_status === "SQUALLY WIND / SYNOPTIC WATCH"
                    ? "bg-sky-950 text-sky-300 border-sky-700"
                    : "bg-emerald-950 text-emerald-300 border-emerald-700"
                }`}
              >
                {cycloneTelemetry.active_alert_status}
              </span>
            </div>

            {/* Headline Synopsis */}
            <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-xs text-rose-100 flex items-start gap-2">
              <AlertOctagon className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{cycloneTelemetry.imminent_outlook.headline}</span>
            </div>

            {/* Real-Time Atmospheric Cyclonic KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">Current Wind Gusts</span>
                <span className="text-lg font-black font-mono text-rose-300">
                  {cycloneTelemetry.realtime_conditions.wind_gust_kmh} km/h
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Sustained: {cycloneTelemetry.realtime_conditions.sustained_wind_kmh} km/h
                </span>
              </div>

              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">Sea-Level Pressure</span>
                <span className="text-lg font-black font-mono text-cyan-300">
                  {cycloneTelemetry.realtime_conditions.sea_level_pressure_hpa} hPa
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Deficit: {cycloneTelemetry.realtime_conditions.pressure_drop_hpa} hPa from normal
                </span>
              </div>

              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">IMD / WMO Classification</span>
                <span className="text-sm font-bold font-mono text-amber-300 block mt-0.5">
                  {cycloneTelemetry.realtime_conditions.imd_category}
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Wind Direction: {cycloneTelemetry.realtime_conditions.wind_direction_deg}°
                </span>
              </div>

              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <span className="text-[10px] text-zinc-400 uppercase block">15-Day Peak Forecast</span>
                <span className="text-lg font-black font-mono text-white">
                  {cycloneTelemetry.imminent_outlook.peak_forecast_wind_gust_kmh} km/h
                </span>
                <span className="text-[10px] text-zinc-400 block mt-0.5">
                  Expected on {cycloneTelemetry.imminent_outlook.peak_forecast_date}
                </span>
              </div>
            </div>

            {/* Active Global / Basin Tropical Cyclones (GDACS) */}
            {cycloneTelemetry.active_global_and_basin_cyclones &&
              cycloneTelemetry.active_global_and_basin_cyclones.length > 0 && (
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between text-xs text-zinc-400">
                    <span className="font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                      <Radio className="h-3.5 w-3.5 text-rose-400 animate-pulse" />
                      Active GDACS Tropical Cyclones in Basin & Impact Proximity
                    </span>
                    <span className="font-mono text-[10px]">
                      Source: Global Disaster Alert and Coordination System (gdacs.org)
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {cycloneTelemetry.active_global_and_basin_cyclones.map((tc, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-xl border text-xs flex flex-col justify-between gap-2 ${
                          tc.in_impact_zone
                            ? "bg-rose-950/30 border-rose-700/60"
                            : "bg-white/[0.02] border-white/[0.06]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-white text-sm">{tc.name}</span>
                              <span
                                className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                                  tc.alert_level === "Red"
                                    ? "bg-rose-950 text-rose-300 border border-rose-700"
                                    : tc.alert_level === "Orange"
                                    ? "bg-amber-950 text-amber-300 border border-amber-700"
                                    : "bg-emerald-950 text-emerald-300 border border-emerald-700"
                                }`}
                              >
                                {tc.alert_level} Alert
                              </span>
                              {tc.in_impact_zone && (
                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-200 border border-rose-600/60 font-semibold">
                                  In Threat Zone
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-zinc-400 block mt-0.5">
                              {tc.imd_category} • Max Winds: {tc.max_wind_kmh} km/h
                            </span>
                            {tc.affected_countries && (
                              <span className="text-[10px] text-zinc-500 block truncate">
                                Region: {tc.affected_countries}
                              </span>
                            )}
                          </div>
                          {tc.report_url && (
                            <a
                              href={tc.report_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[11px] font-mono text-cyan-400 hover:underline flex items-center gap-1 shrink-0"
                            >
                              <span>GDACS</span>
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-[11px] font-mono pt-1 border-t border-white/[0.05] text-zinc-400">
                          <span>Eye Distance: <strong className="text-white">{tc.distance_km} km</strong></span>
                          <span>Position: {tc.lat.toFixed(1)}°N, {tc.lon.toFixed(1)}°E</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* Imminent 15-Day Cyclonic Forecast Outlook Bar Chart */}
            {cycloneTelemetry.imminent_outlook.forecast_15day &&
              cycloneTelemetry.imminent_outlook.forecast_15day.length > 0 && (
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between text-[11px] text-zinc-400">
                    <span className="font-semibold text-white uppercase tracking-wider">
                      Imminent 15-Day Peak Wind Gust & Sea-Level Pressure Outlook
                    </span>
                    <span className="font-mono text-[10px]">
                      Open-Meteo Synoptic Forecast • Updated Real-Time
                    </span>
                  </div>

                  <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5 pt-1">
                    {cycloneTelemetry.imminent_outlook.forecast_15day.slice(0, 10).map((day, idx) => {
                      const gustPct = Math.min(100, Math.max(12, Math.round((day.max_wind_gust_kmh / 120) * 100)));
                      const isHighRisk = day.max_wind_gust_kmh >= 62 || day.cyclone_risk_pct >= 45;
                      const isModRisk = day.max_wind_gust_kmh >= 45 || day.cyclone_risk_pct >= 25;

                      return (
                        <div
                          key={idx}
                          className={`p-2 rounded-lg border text-center flex flex-col justify-between ${
                            isHighRisk
                              ? "bg-rose-950/30 border-rose-700/60"
                              : isModRisk
                              ? "bg-amber-950/20 border-amber-700/40"
                              : "bg-white/[0.02] border-white/[0.05]"
                          }`}
                          title={`${day.date}: Gust ${day.max_wind_gust_kmh} km/h (Sustained ${day.max_wind_speed_kmh} km/h) • Min SLP: ${day.min_pressure_hpa} hPa • Rain: ${day.precipitation_mm} mm • ${day.imd_category}`}
                        >
                          <span className="text-[9.5px] font-mono text-zinc-400">
                            {day.date.length >= 10 ? day.date.slice(5) : day.date}
                          </span>
                          <div className="w-full h-14 bg-zinc-900 rounded overflow-hidden flex items-end my-1 border border-zinc-800 p-0.5">
                            <div
                              style={{ height: `${gustPct}%` }}
                              className={`w-full rounded-sm ${
                                isHighRisk
                                  ? "bg-rose-500"
                                  : isModRisk
                                  ? "bg-amber-400"
                                  : "bg-sky-500/80"
                              }`}
                            />
                          </div>
                          <span className="text-[10px] font-mono font-bold text-white">
                            {day.max_wind_gust_kmh}k
                          </span>
                          <span className="text-[9px] font-mono text-zinc-500">
                            {day.min_pressure_hpa}hPa
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            {/* Real Multi-Year Historical Cyclone Archive (2021–2026 ERA5) */}
            {cycloneTelemetry.historical_archive && (
              <div className="space-y-3 pt-3 border-t border-zinc-800/80">
                <div className="flex items-center justify-between text-xs text-zinc-400">
                  <span className="font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5 text-cyan-400" />
                    Historical Cyclone & Storm Archive (2021 – 2026 ERA5 Telemetry)
                  </span>
                  <span className="font-mono text-[10px]">
                    {cycloneTelemetry.historical_archive.total_archived_days} Recorded Days
                  </span>
                </div>

                {/* Summary Metric Counters */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <span className="text-[10px] text-zinc-400 uppercase block">Total Cyclonic Storm Days</span>
                    <span className="text-base font-bold font-mono text-rose-300">
                      {cycloneTelemetry.historical_archive.total_cyclonic_storm_days}
                    </span>
                    <span className="text-[9.5px] text-zinc-500 block">Winds ≥ 62 km/h</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <span className="text-[10px] text-zinc-400 uppercase block">Depression / Gale Days</span>
                    <span className="text-base font-bold font-mono text-amber-300">
                      {cycloneTelemetry.historical_archive.total_depression_gale_days}
                    </span>
                    <span className="text-[9.5px] text-zinc-500 block">Winds ≥ 50 km/h</span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <span className="text-[10px] text-zinc-400 uppercase block">Max Gust Recorded</span>
                    <span className="text-base font-bold font-mono text-white">
                      {cycloneTelemetry.historical_archive.max_historical_wind_gust_kmh} km/h
                    </span>
                    <span className="text-[9.5px] text-zinc-500 block">
                      {cycloneTelemetry.historical_archive.max_historical_wind_date}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <span className="text-[10px] text-zinc-400 uppercase block">Lowest Pressure</span>
                    <span className="text-base font-bold font-mono text-cyan-300">
                      {cycloneTelemetry.historical_archive.min_historical_pressure_hpa} hPa
                    </span>
                    <span className="text-[9.5px] text-zinc-500 block">ERA5 Reanalysis</span>
                  </div>
                </div>

                {/* Yearly Cyclone Trends Table (2021–2026) */}
                {cycloneTelemetry.historical_archive.yearly_trends &&
                  cycloneTelemetry.historical_archive.yearly_trends.length > 0 && (
                    <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-white/[0.04] text-[10px] uppercase text-zinc-400 border-b border-white/[0.06]">
                          <tr>
                            <th className="py-2 px-3">Year</th>
                            <th className="py-2 px-3">Storm Days (≥62k)</th>
                            <th className="py-2 px-3">Gale Days (≥50k)</th>
                            <th className="py-2 px-3">Peak Gust</th>
                            <th className="py-2 px-3">Lowest SLP</th>
                            <th className="py-2 px-3">Peak Date</th>
                            <th className="py-2 px-3">Intensity</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {cycloneTelemetry.historical_archive.yearly_trends.map((yr, idx) => (
                            <tr key={idx} className="hover:bg-white/[0.02]">
                              <td className="py-2 px-3 font-bold text-white">{yr.year}</td>
                              <td className="py-2 px-3 text-rose-300">{yr.cyclonic_storm_days}</td>
                              <td className="py-2 px-3 text-amber-300">{yr.depression_gale_days}</td>
                              <td className="py-2 px-3 text-white font-bold">{yr.max_wind_gust_kmh} km/h</td>
                              <td className="py-2 px-3 text-cyan-300">{yr.min_pressure_hpa} hPa</td>
                              <td className="py-2 px-3 text-zinc-400">{yr.peak_date}</td>
                              <td className="py-2 px-3 text-zinc-300">{yr.peak_category}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                {/* Top Notable Multi-Day Cyclonic Episodes */}
                {cycloneTelemetry.historical_archive.notable_events &&
                  cycloneTelemetry.historical_archive.notable_events.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <span className="text-[10px] font-mono uppercase text-zinc-400 block font-semibold">
                        Notable Historical Cyclonic Episodes Recorded at this Location (2021–2026 Archive)
                      </span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {cycloneTelemetry.historical_archive.notable_events.slice(0, 4).map((ev, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05] text-xs flex items-center justify-between"
                          >
                            <div>
                              <div className="flex items-center gap-1.5 font-mono">
                                <span className="font-bold text-white">{ev.date}</span>
                                <span className="text-[10px] text-amber-300">({ev.imd_category})</span>
                              </div>
                              <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                                Rain: {ev.rainfall_mm} mm • Min Pressure: {ev.min_pressure_hpa} hPa
                              </span>
                            </div>
                            <div className="text-right font-mono">
                              <span className="text-sm font-black text-rose-300 block">
                                {ev.peak_wind_gust_kmh} km/h
                              </span>
                              <span className="text-[9px] text-zinc-500">Peak Gust</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* View 3: River Flow & Floods (Strictly City-Bounded & Live Telemetry) */}
      {activeView === "river" && riverTelemetry && (
        <div className="space-y-4">
          {/* Check if city has a river situated within municipal limits */}
          {!riverTelemetry.has_river_in_city ? (
            <div className="p-5 rounded-xl bg-zinc-950/90 border border-white/[0.08] text-center space-y-3">
              <div className="h-10 w-10 mx-auto rounded-full bg-cyan-950/60 border border-cyan-800/60 flex items-center justify-center text-cyan-400">
                <Info className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white">
                  No Major Perennial River Situated Within {riverTelemetry.city} Municipal Limits
                </h4>
                <p className="text-xs text-zinc-400 mt-1 max-w-lg mx-auto">
                  Strict municipal boundary filtering active: No perennial river intersects the immediate city perimeter.
                  Distant basin waterways and outside gauge stations are excluded to guarantee zero geographic distortion.
                </p>
              </div>
              <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.05] text-xs text-zinc-300 max-w-md mx-auto text-left">
                <span className="text-[10px] font-mono uppercase text-cyan-400 font-bold block">
                  Regional Drainage & Runoff Authority
                </span>
                <span className="font-semibold block mt-0.5">{riverTelemetry.authorities?.flood}</span>
                <span className="text-[11px] text-zinc-400 block mt-0.5">
                  Helpline: {riverTelemetry.authorities?.helpline || "112 / 1077"}
                </span>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-zinc-950/90 border border-white/[0.08] space-y-3">
              {/* Station Header & Stage Badge */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-800/80 pb-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">
                      Rivers Strictly Situated Within {riverTelemetry.city} Municipal Limits
                    </span>
                    {riverTelemetry.cwc_station_code && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/60">
                        CWC Station: {riverTelemetry.cwc_station_code}
                      </span>
                    )}
                    {riverTelemetry.floodwatch_india?.live_cwc_telemetry && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/60">
                        Live FloodWatch India Telemetry
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-bold text-white mt-0.5">
                    {riverTelemetry.river_name}
                    {riverTelemetry.cwc_station ? ` — ${riverTelemetry.cwc_station}` : ""}
                  </h4>
                  {riverTelemetry.rivers_in_city && riverTelemetry.rivers_in_city.length > 0 && (
                    <p className="text-[11px] text-zinc-400">
                      City Rivers: <strong className="text-zinc-200">{riverTelemetry.rivers_in_city.join(", ")}</strong>
                      {riverTelemetry.upstream_control && ` • Upstream: ${riverTelemetry.upstream_control}`}
                    </p>
                  )}
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

              {/* 4 Real Hydrological KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-zinc-400 uppercase block">Live River Discharge</span>
                  <span className="text-base font-black font-mono text-white">
                    {riverTelemetry.current_discharge_m3s !== null ? `${riverTelemetry.current_discharge_m3s} m³/s` : "N/A"}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400 block mt-0.5">
                    {riverTelemetry.current_discharge_cusecs !== null
                      ? `${riverTelemetry.current_discharge_cusecs.toLocaleString()} cusecs`
                      : "Unmodified GloFAS"}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-zinc-400 uppercase block">Water Level (CWC Gauge)</span>
                  <span className="text-base font-black font-mono text-cyan-300">
                    {riverTelemetry.current_water_level_m !== null ? `${riverTelemetry.current_water_level_m} m` : "Streamflow Only"}
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    {riverTelemetry.danger_level_m ? `Danger: ${riverTelemetry.danger_level_m} m` : "Normal Channel Flow"}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-zinc-400 uppercase block">Flow Anomaly vs Mean</span>
                  <span
                    className={`text-base font-black font-mono ${
                      (riverTelemetry.historical_flow_stats?.flow_anomaly_pct || 0) > 25
                        ? "text-amber-300"
                        : "text-emerald-300"
                    }`}
                  >
                    {riverTelemetry.historical_flow_stats?.flow_anomaly_pct !== null &&
                    riverTelemetry.historical_flow_stats?.flow_anomaly_pct !== undefined
                      ? `${riverTelemetry.historical_flow_stats.flow_anomaly_pct > 0 ? "+" : ""}${riverTelemetry.historical_flow_stats.flow_anomaly_pct}%`
                      : "Baseline"}
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                    2021–2026 Mean: {riverTelemetry.historical_flow_stats?.mean_discharge_m3s || "—"} m³/s
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] text-zinc-400 uppercase block">7-Day Peak Outlook</span>
                  <span className="text-base font-black font-mono text-white">
                    {riverTelemetry.peak_7d_discharge_m3s !== null ? `${riverTelemetry.peak_7d_discharge_m3s} m³/s` : "—"}
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    {riverTelemetry.peak_7d_date} • {riverTelemetry.inflow_trend} Inflow
                  </span>
                </div>
              </div>

              {/* River Prediction Narrative */}
              <div className="p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-800/40 text-xs text-cyan-100 flex items-start gap-2">
                <Droplets className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                <span>{riverTelemetry.prediction_summary}</span>
              </div>

              {/* 15-Day Forward River Flow Forecast */}
              {riverTelemetry.forecast_15day && riverTelemetry.forecast_15day.length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="flex items-center justify-between text-[11px] text-zinc-400">
                    <span className="font-semibold text-white uppercase tracking-wider">
                      15-Day Forward River Discharge Trajectory (m³/s)
                    </span>
                    <span className="font-mono text-[10px] text-zinc-400">
                      Copernicus GloFAS • Updated Daily
                    </span>
                  </div>
                  <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5 pt-1">
                    {riverTelemetry.forecast_15day.slice(0, 10).map((pt, idx) => {
                      const maxObs = Math.max(
                        ...riverTelemetry.forecast_15day.slice(0, 10).map((p) => p.discharge_m3s || 1),
                        10
                      );
                      const pct = Math.min(100, Math.max(15, Math.round(((pt.discharge_m3s || 0) / maxObs) * 100)));
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
                          title={`${pt.date}: ${pt.discharge_m3s} m³/s (${pt.discharge_cusecs} cusecs)`}
                        >
                          <span className="text-[9.5px] font-mono text-zinc-400">
                            {pt.date.length >= 10 ? pt.date.slice(5) : pt.date}
                          </span>
                          <div className="w-full h-14 bg-zinc-900 rounded overflow-hidden flex items-end my-1 border border-zinc-800 p-0.5">
                            <div style={{ height: `${pct}%` }} className={`w-full rounded-sm ${barColor}`} />
                          </div>
                          <span className="text-[10px] font-mono font-bold text-white">{pt.discharge_m3s}</span>
                          <span className="text-[9px] font-mono text-zinc-500">{pt.stage}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Multi-Year Real Historical River Flow Trends (2021–2026 Archive) */}
              {riverTelemetry.historical_flow_stats?.yearly_flow_trends &&
                riverTelemetry.historical_flow_stats.yearly_flow_trends.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-zinc-800/80">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="font-semibold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-cyan-400" />
                        Multi-Year Historical River Flow Archive (2021 – 2026 GloFAS)
                      </span>
                      <span className="font-mono text-[10px]">
                        {riverTelemetry.historical_flow_stats.total_observed_days} Daily Records
                      </span>
                    </div>

                    <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-white/[0.04] text-[10px] uppercase text-zinc-400 border-b border-white/[0.06]">
                          <tr>
                            <th className="py-2 px-3">Year</th>
                            <th className="py-2 px-3">Mean Discharge</th>
                            <th className="py-2 px-3">Peak Discharge</th>
                            <th className="py-2 px-3">Peak Cusecs</th>
                            <th className="py-2 px-3">Peak Date</th>
                            <th className="py-2 px-3">High Flow Days</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {riverTelemetry.historical_flow_stats.yearly_flow_trends.map((yr, idx) => (
                            <tr key={idx} className="hover:bg-white/[0.02]">
                              <td className="py-2 px-3 font-bold text-white">{yr.year}</td>
                              <td className="py-2 px-3 text-cyan-300">{yr.mean_discharge_m3s} m³/s</td>
                              <td className="py-2 px-3 text-white font-bold">{yr.peak_discharge_m3s} m³/s</td>
                              <td className="py-2 px-3 text-zinc-400">{yr.peak_discharge_cusecs?.toLocaleString()}</td>
                              <td className="py-2 px-3 text-zinc-400">{yr.peak_date}</td>
                              <td className="py-2 px-3 text-amber-300 font-bold">{yr.high_flow_days}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
            </div>
          )}

          {/* Local Disaster Authorities Card */}
          {riverTelemetry.authorities && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Building2 className="h-3.5 w-3.5 text-cyan-400" />
                <span>Local Disaster Authorities ({riverTelemetry.city})</span>
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-[10px] font-mono uppercase text-cyan-400 font-bold block">
                    River Flood Authority
                  </span>
                  <span className="font-semibold text-white block mt-0.5">{riverTelemetry.authorities.flood}</span>
                </div>
                {riverTelemetry.authorities.earthquake && (
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <span className="text-[10px] font-mono uppercase text-purple-400 font-bold block">
                      Earthquake & Seismology
                    </span>
                    <span className="font-semibold text-white block mt-0.5">
                      {riverTelemetry.authorities.earthquake}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* View 4: Proportional Threat Share Spectrum */}
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
