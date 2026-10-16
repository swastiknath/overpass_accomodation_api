"use client";

import React from "react";
import { SignalContribution } from "@/types";

interface HazardRadarChartProps {
  contributions: SignalContribution[];
  coverage: Record<string, string>;
  safetyScore?: number;
}

interface RadarAxis {
  key: string;
  label: string;
  hazardType: string;
  value: number; // 0 to 100
  status: string;
  color: string;
}

export default function HazardRadarChart({
  contributions,
  coverage,
  safetyScore = 80,
}: HazardRadarChartProps) {
  // Map contributions & coverage into normalized radar axes (0 - 100 risk scale)
  const axesDef: { key: string; label: string; hazardType: string; color: string }[] = [
    { key: "crime", label: "Crime & Law", hazardType: "crime", color: "#f43f5e" },
    { key: "weather", label: "Severe Weather", hazardType: "weather", color: "#38bdf8" },
    { key: "fire", label: "Fire & Thermal", hazardType: "fire", color: "#fb923c" },
    { key: "earthquake", label: "Seismic Activity", hazardType: "earthquake", color: "#a855f7" },
    { key: "conflict", label: "Conflict & Protests", hazardType: "conflict", color: "#ef4444" },
    { key: "news", label: "News & Alerts", hazardType: "news", color: "#818cf8" },
    { key: "flood", label: "Flood Inundation", hazardType: "flood", color: "#06b6d4" },
    { key: "landslide", label: "Landslide Risk", hazardType: "landslide", color: "#eab308" },
  ];

  const axes: RadarAxis[] = axesDef.map((def) => {
    // Find active contribution for this hazard
    const c = contributions.find((item) => item.hazard_type === def.hazardType);
    let val = 12; // baseline minimal noise level
    if (c) {
      val = Math.min(100, Math.max(15, Math.round(c.contribution * 100 * 1.5 + c.sigma * 40)));
    } else {
      const covStatus = coverage[def.hazardType];
      if (covStatus === "source_failed") val = 25;
      else if (covStatus === "not_available_for_region") val = 18;
    }
    return {
      key: def.key,
      label: def.label,
      hazardType: def.hazardType,
      value: val,
      status: coverage[def.hazardType] || "no_signal_found",
      color: def.color,
    };
  });

  const size = 320;
  const center = size / 2;
  const radius = center - 52;
  const numAxes = axes.length;
  const angleStep = (2 * Math.PI) / numAxes;

  // Concentric levels (25%, 50%, 75%, 100%)
  const levels = [0.25, 0.5, 0.75, 1.0];

  // Helper to compute (x, y) coordinates
  const getCoordinates = (index: number, factor: number) => {
    const angle = index * angleStep - Math.PI / 2;
    return {
      x: center + radius * factor * Math.cos(angle),
      y: center + radius * factor * Math.sin(angle),
    };
  };

  // Generate radar polygon points
  const polygonPoints = axes
    .map((axis, i) => {
      const { x, y } = getCoordinates(i, axis.value / 100);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="flex flex-col items-center justify-center p-3 bg-zinc-950/80 rounded-xl border border-zinc-800">
      <div className="w-full flex items-center justify-between mb-2 px-2">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Multi-Hazard Radar Telemetry
          </span>
        </div>
        <span className="text-[11px] text-zinc-500 font-mono">
          Composite Sensitivity: {100 - safetyScore}%
        </span>
      </div>

      <div className="relative w-full max-w-[340px] aspect-square flex items-center justify-center">
        <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full overflow-visible">
          <defs>
            <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.35" />
              <stop offset="70%" stopColor="#4f46e5" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#000000" stopOpacity="0.0" />
            </radialGradient>
            <linearGradient id="polyStroke" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="50%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#ec4899" />
            </linearGradient>
          </defs>

          {/* Concentric Web Polygons */}
          {levels.map((lvl, lvlIdx) => {
            const levelPoints = axes
              .map((_, i) => {
                const { x, y } = getCoordinates(i, lvl);
                return `${x},${y}`;
              })
              .join(" ");
            return (
              <polygon
                key={`lvl-${lvlIdx}`}
                points={levelPoints}
                fill="none"
                stroke="#27272a"
                strokeWidth={lvl === 1.0 ? "1.5" : "1"}
                strokeDasharray={lvl === 1.0 ? "none" : "3,3"}
              />
            );
          })}

          {/* Axis Spokes */}
          {axes.map((_, i) => {
            const { x, y } = getCoordinates(i, 1.0);
            return (
              <line
                key={`spoke-${i}`}
                x1={center}
                y1={center}
                x2={x}
                y2={y}
                stroke="#27272a"
                strokeWidth="1"
              />
            );
          })}

          {/* Filled Risk Polygon with Glow */}
          <polygon
            points={polygonPoints}
            fill="url(#radarGlow)"
            stroke="url(#polyStroke)"
            strokeWidth="2.5"
            className="transition-all duration-700 ease-out"
          />

          {/* Vertex Points & Labels */}
          {axes.map((axis, i) => {
            const { x, y } = getCoordinates(i, axis.value / 100);
            const labelPos = getCoordinates(i, 1.18);
            const isLeft = labelPos.x < center - 10;
            const isRight = labelPos.x > center + 10;
            const anchor = isLeft ? "end" : isRight ? "start" : "middle";

            return (
              <g key={`vertex-${axis.key}`} className="group cursor-pointer">
                {/* Vertex circle */}
                <circle
                  cx={x}
                  cy={y}
                  r="4"
                  fill="#09090b"
                  stroke={axis.color}
                  strokeWidth="2"
                  className="transition-transform group-hover:scale-150"
                />

                {/* Axis Label */}
                <text
                  x={labelPos.x}
                  y={labelPos.y}
                  textAnchor={anchor}
                  dominantBaseline="central"
                  fontSize="9.5"
                  fontWeight="600"
                  fill={axis.value > 25 ? "#f4f4f5" : "#a1a1aa"}
                  className="select-none tracking-tight transition-colors group-hover:fill-cyan-400"
                >
                  {axis.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="w-full grid grid-cols-2 sm:grid-cols-4 gap-1.5 mt-3 pt-2 border-t border-zinc-900 text-[10px]">
        {axes.map((ax) => (
          <div
            key={`badge-${ax.key}`}
            className="flex items-center justify-between p-1 px-2 rounded bg-zinc-900/60 border border-zinc-800/80"
          >
            <span className="text-zinc-400 truncate max-w-[85px]">{ax.label}</span>
            <span
              className="font-mono font-bold"
              style={{ color: ax.value > 30 ? ax.color : "#71717a" }}
            >
              {ax.value}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
