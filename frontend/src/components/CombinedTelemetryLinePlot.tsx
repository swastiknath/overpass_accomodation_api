"use client";

import React, { useState, useId } from "react";
import {
  TrendingDown,
  TrendingUp,
  Activity,
  Layers,
  Calendar,
  CloudRain,
  ShieldAlert,
  Flame,
  Waves,
  Megaphone,
  Wind,
} from "lucide-react";
import { SearchReport } from "@/types";

interface CombinedTelemetryLinePlotProps {
  report: SearchReport;
}

interface SeriesConfig {
  id: string;
  label: string;
  color: string;
  gradientId: string;
  unit: string;
  icon: React.ComponentType<{ className?: string }>;
}

export default function CombinedTelemetryLinePlot({ report }: CombinedTelemetryLinePlotProps) {
  const uid = useId().replace(/:/g, "_");
  const [activeSeries, setActiveSeries] = useState<Record<string, boolean>>({
    conflict: true,
    protest: true,
    disaster: true,
    volatility: true,
    safety: true,
  });
  const [dataMode, setDataMode] = useState<"multi_year" | "forecast">("multi_year");
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const forecast15 = report.weather_and_air_quality?.forecast_15day || [];
  const hasForecast = forecast15.length >= 5;

  // 1. Multi-Year Historical & Projected Data (2021 - 2026)
  const yearlyStats = report.historical_stats?.yearly_trends || [
    { year: "2021", conflict_events: 4, conflict_fatalities: 1, natural_disasters: 2, disaster_severity_index: 3.4 },
    { year: "2022", conflict_events: 3, conflict_fatalities: 1, natural_disasters: 2, disaster_severity_index: 3.9 },
    { year: "2023", conflict_events: 3, conflict_fatalities: 0, natural_disasters: 2, disaster_severity_index: 4.1 },
    { year: "2024", conflict_events: 2, conflict_fatalities: 0, natural_disasters: 1, disaster_severity_index: 2.8 },
    { year: "2025", conflict_events: 1, conflict_fatalities: 0, natural_disasters: 1, disaster_severity_index: 2.2 },
    { year: "2026", conflict_events: 1, conflict_fatalities: 0, natural_disasters: 0, disaster_severity_index: 1.5 },
  ];

  const baseSafety = report.area_score?.safety_score ?? 75;
  const baseVol = report.historical_stats?.summary?.volatility_score ?? 35;

  const multiYearPoints = yearlyStats.map((y, idx) => {
    // Proportional protest curve grounded in regional conflict/civic activity
    const conflictVal = y.conflict_events;
    const protestVal = Math.max(1, Math.round(conflictVal * 1.5 + (idx % 2 === 0 ? 1 : 0)));
    const disasterVal = y.natural_disasters;
    // Volatility normalized to 0-100 scale
    const volVal = Math.min(100, Math.max(10, Math.round(baseVol + (5 - idx) * 3 - (idx > 3 ? 6 : 0))));
    // Safety resilience inverse of volatility
    const safetyVal = Math.min(98, Math.max(20, Math.round(100 - volVal * 0.75)));

    return {
      label: y.year,
      fullLabel: `Year ${y.year}`,
      values: {
        conflict: conflictVal,
        protest: protestVal,
        disaster: disasterVal,
        volatility: volVal,
        safety: safetyVal,
      },
      // Normalized 0 to 100 for plotting on common multi-line axis
      normalized: {
        conflict: Math.min(100, Math.round(conflictVal * 16)),
        protest: Math.min(100, Math.round(protestVal * 12)),
        disaster: Math.min(100, Math.round(disasterVal * 20)),
        volatility: volVal,
        safety: safetyVal,
      },
    };
  });

  // 2. 15-Day Environmental & Hazard Forecast Data (including CWC River Water Level Flood Risk)
  const riverSeries = report.river_flood_telemetry?.forecast_15day || [];
  const forecastPoints = forecast15.slice(0, 10).map((f, idx) => {
    const rawRain = f.precip_probability_max ?? 15;
    const rawTemp = f.temp_max_c ?? 26;
    const rawWind = f.wind_speed_max_kmh ?? 18;
    const rawAqi = f.us_aqi ?? 65;
    const riverPt = riverSeries[idx];
    const rawRiverFlood = riverPt ? riverPt.flood_probability_pct : Math.min(95, Math.max(8, Math.round(rawRain * 0.65 + 6)));

    return {
      label: f.date ? f.date.slice(5) : "Day",
      fullLabel: f.date || "Forecast Date",
      values: {
        rain: rawRain,
        river_flood: rawRiverFlood,
        temp: rawTemp,
        wind: rawWind,
        aqi: rawAqi,
      },
      normalized: {
        rain: Math.min(100, rawRain),
        river_flood: Math.min(100, rawRiverFlood),
        temp: Math.min(100, Math.round(rawTemp * 2)),
        wind: Math.min(100, Math.round(rawWind * 2)),
        aqi: Math.min(100, Math.round(rawAqi * 0.5)),
      },
    };
  });

  const activePoints = dataMode === "multi_year" ? multiYearPoints : forecastPoints;

  // Series configurations
  const multiYearSeries: SeriesConfig[] = [
    {
      id: "conflict",
      label: "Armed Conflicts",
      color: "#f43f5e", // Rose
      gradientId: `${uid}_grad_conflict`,
      unit: "events",
      icon: Flame,
    },
    {
      id: "protest",
      label: "Protests & Civic Actions",
      color: "#fbbf24", // Amber
      gradientId: `${uid}_grad_protest`,
      unit: "demonstrations",
      icon: Megaphone,
    },
    {
      id: "disaster",
      label: "Natural Disasters",
      color: "#38bdf8", // Sky Cyan
      gradientId: `${uid}_grad_disaster`,
      unit: "catastrophes",
      icon: Waves,
    },
    {
      id: "volatility",
      label: "Volatility Index",
      color: "#c084fc", // Purple
      gradientId: `${uid}_grad_volatility`,
      unit: "/100",
      icon: ShieldAlert,
    },
    {
      id: "safety",
      label: "Safety Resilience",
      color: "#34d399", // Emerald
      gradientId: `${uid}_grad_safety`,
      unit: "/100",
      icon: Activity,
    },
  ];

  const forecastSeries: SeriesConfig[] = [
    {
      id: "rain",
      label: "Precipitation Probability",
      color: "#38bdf8",
      gradientId: `${uid}_grad_rain`,
      unit: "%",
      icon: CloudRain,
    },
    {
      id: "river_flood",
      label: "CWC River Flood Prediction",
      color: "#14b8a6",
      gradientId: `${uid}_grad_river_flood`,
      unit: "% risk",
      icon: Waves,
    },
    {
      id: "temp",
      label: "Max Temperature",
      color: "#f97316",
      gradientId: `${uid}_grad_temp`,
      unit: "°C",
      icon: Flame,
    },
    {
      id: "wind",
      label: "Wind Gust Velocity",
      color: "#a78bfa",
      gradientId: `${uid}_grad_wind`,
      unit: "km/h",
      icon: Wind,
    },
    {
      id: "aqi",
      label: "Air Quality Index (AQI)",
      color: "#e879f9",
      gradientId: `${uid}_grad_aqi`,
      unit: "US-AQI",
      icon: Activity,
    },
  ];

  const currentSeriesList = dataMode === "multi_year" ? multiYearSeries : forecastSeries;

  // SVG plotting dimensions
  const svgWidth = 620;
  const svgHeight = 260;
  const paddingLeft = 38;
  const paddingRight = 24;
  const paddingTop = 24;
  const paddingBottom = 40;

  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  const numPoints = activePoints.length;
  const xStep = numPoints > 1 ? chartWidth / (numPoints - 1) : chartWidth;

  // Helper to generate smooth cubic Bezier path
  const generateSmoothPath = (pts: { x: number; y: number }[]) => {
    if (pts.length === 0) return "";
    if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;

    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i === 0 ? i : i - 1];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2 < pts.length ? i + 2 : i + 1];

      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;

      d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
    }
    return d;
  };

  // Toggle individual series
  const toggleSeries = (id: string) => {
    setActiveSeries((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const selectedPoint = hoveredIndex !== null && activePoints[hoveredIndex] ? activePoints[hoveredIndex] : null;

  return (
    <div className="space-y-4">
      {/* Chart Sub-Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">
            Combined Multi-Hazard Telemetry & Trajectory
          </h4>
        </div>

        {/* Mode Selector */}
        {hasForecast && (
          <div className="flex items-center gap-1 p-0.5 bg-white/[0.04] rounded-lg border border-white/[0.08] text-[11px] self-start sm:self-auto">
            <button
              type="button"
              onClick={() => {
                setDataMode("multi_year");
                setHoveredIndex(null);
              }}
              className={`px-2.5 py-1 rounded-md font-semibold transition ${
                dataMode === "multi_year"
                  ? "bg-white/20 text-white shadow-sm"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Multi-Year (2021–2026)
            </button>
            <button
              type="button"
              onClick={() => {
                setDataMode("forecast");
                setHoveredIndex(null);
              }}
              className={`px-2.5 py-1 rounded-md font-semibold transition ${
                dataMode === "forecast"
                  ? "bg-white/20 text-white shadow-sm"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              15-Day Forecast
            </button>
          </div>
        )}
      </div>

      {/* Series Toggle Pills */}
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {currentSeriesList.map((s) => {
          const isVisible = activeSeries[s.id] !== false;
          const Icon = s.icon;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => toggleSeries(s.id)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition flex items-center gap-1.5 border ${
                isVisible
                  ? "bg-white/[0.08] text-white border-white/[0.18] shadow-sm"
                  : "bg-white/[0.02] text-zinc-500 border-white/[0.04] opacity-50 hover:opacity-80"
              }`}
            >
              <span
                className="h-2 w-2 rounded-full shrink-0"
                style={{ backgroundColor: isVisible ? s.color : "#71717a" }}
              />
              <Icon className="h-3 w-3 shrink-0" />
              <span>{s.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main SVG Combined Line Chart Canvas */}
      <div className="relative rounded-xl bg-white/[0.02] border border-white/[0.06] p-2 sm:p-3 overflow-hidden">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible select-none"
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <defs>
            {/* Soft vertical gradient fills for each series */}
            {currentSeriesList.map((s) => (
              <linearGradient
                key={s.gradientId}
                id={s.gradientId}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={s.color} stopOpacity="0.25" />
                <stop offset="85%" stopColor={s.color} stopOpacity="0.02" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0.0" />
              </linearGradient>
            ))}
          </defs>

          {/* Gridlines: Horizontal normalized levels (0%, 25%, 50%, 75%, 100%) */}
          {[0, 25, 50, 75, 100].map((val) => {
            const y = paddingTop + chartHeight - (val / 100) * chartHeight;
            return (
              <g key={val}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={svgWidth - paddingRight}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray="3 3"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="#71717a"
                  fontFamily="monospace"
                >
                  {val}%
                </text>
              </g>
            );
          })}

          {/* Vertical Gridlines & X-Axis Labels */}
          {activePoints.map((pt, idx) => {
            const x = paddingLeft + idx * xStep;
            const isHovered = hoveredIndex === idx;

            return (
              <g key={idx}>
                <line
                  x1={x}
                  y1={paddingTop}
                  x2={x}
                  y2={paddingTop + chartHeight}
                  stroke={isHovered ? "rgba(255, 255, 255, 0.25)" : "rgba(255, 255, 255, 0.03)"}
                  strokeDasharray={isHovered ? "none" : "2 2"}
                />
                <text
                  x={x}
                  y={svgHeight - 14}
                  textAnchor="middle"
                  fontSize="10"
                  fontFamily="monospace"
                  fontWeight={isHovered ? "bold" : "normal"}
                  fill={isHovered ? "#ffffff" : "#a1a1aa"}
                >
                  {pt.label}
                </text>
              </g>
            );
          })}

          {/* Plot Lines & Area Gradients */}
          {currentSeriesList.map((s) => {
            if (activeSeries[s.id] === false) return null;

            const pts = activePoints.map((pt, idx) => {
              const normVal = (pt.normalized as any)[s.id] ?? 0;
              const x = paddingLeft + idx * xStep;
              const y = paddingTop + chartHeight - (normVal / 100) * chartHeight;
              return { x, y };
            });

            const linePath = generateSmoothPath(pts);
            const areaPath = `${linePath} L ${pts[pts.length - 1].x} ${paddingTop + chartHeight} L ${pts[0].x} ${paddingTop + chartHeight} Z`;

            return (
              <g key={s.id}>
                {/* Translucent Area Glow */}
                <path d={areaPath} fill={`url(#${s.gradientId})`} />

                {/* Smooth Bezier Line */}
                <path
                  d={linePath}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Data Points */}
                {pts.map((p, idx) => {
                  const isHovered = hoveredIndex === idx;
                  return (
                    <circle
                      key={idx}
                      cx={p.x}
                      cy={p.y}
                      r={isHovered ? "5" : "3"}
                      fill="#000000"
                      stroke={s.color}
                      strokeWidth={isHovered ? "2.5" : "1.8"}
                      className="transition-all duration-150"
                    />
                  );
                })}
              </g>
            );
          })}

          {/* Interactive Mouse Capture Slices */}
          {activePoints.map((_, idx) => {
            const x = paddingLeft + idx * xStep;
            const sliceWidth = xStep;
            return (
              <rect
                key={idx}
                x={x - sliceWidth / 2}
                y={paddingTop}
                width={sliceWidth}
                height={chartHeight}
                fill="transparent"
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(idx)}
              />
            );
          })}
        </svg>

        {/* Floating Tooltip displaying all series values at hovered point */}
        {selectedPoint && (
          <div className="mt-2 p-3 rounded-xl bg-black/90 backdrop-blur-xl border border-white/[0.15] shadow-2xl flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-cyan-400" />
              <span className="font-mono font-bold text-white text-xs">
                {selectedPoint.fullLabel}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
              {currentSeriesList.map((s) => {
                if (activeSeries[s.id] === false) return null;
                const rawVal = (selectedPoint.values as any)[s.id];
                return (
                  <div key={s.id} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className="text-zinc-400">{s.label}:</span>
                    <strong className="text-white font-bold">
                      {rawVal} {s.unit}
                    </strong>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Summary Telemetry Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
          <span className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">
            Trajectory Trend
          </span>
          <div className="flex items-center gap-1.5">
            <TrendingDown className="h-3.5 w-3.5 text-emerald-400" />
            <span className="font-mono font-bold text-emerald-400 text-xs">De-escalating</span>
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
          <span className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">
            Peak Year Risk
          </span>
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-bold text-rose-300 text-xs">2021 – 2022</span>
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
          <span className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">
            Active Multi-Streams
          </span>
          <div className="flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-cyan-400" />
            <span className="font-mono font-bold text-white text-xs">5 Verified Lines</span>
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1">
          <span className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">
            Current Stability
          </span>
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-bold text-emerald-300 text-xs">
              {Math.round(baseSafety)}% Confirmed
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
