"use client";

import React, { useState } from "react";
import {
  Cloud,
  CloudRain,
  Sun,
  CloudSun,
  Wind,
  Droplets,
  Gauge,
  Thermometer,
  ShieldAlert,
  Sparkles,
  Calendar,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import { WeatherAndAirQuality, WeatherDayForecast } from "@/types";

interface WeatherAirQualityPanelProps {
  weatherData?: WeatherAndAirQuality;
  locationName: string;
}

export default function WeatherAirQualityPanel({
  weatherData,
  locationName,
}: WeatherAirQualityPanelProps) {
  const [forecastView, setForecastView] = useState<"15day" | "7day">("15day");

  if (!weatherData || !weatherData.current_conditions) {
    return null;
  }

  const { current_conditions, air_quality, forecast_15day } = weatherData;

  const getWeatherIcon = (code?: number | null) => {
    if (code === undefined || code === null) return Cloud;
    if (code === 0) return Sun;
    if ([1, 2, 3].includes(code)) return CloudSun;
    if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return CloudRain;
    return Cloud;
  };

  const getWeatherDescription = (code?: number | null) => {
    if (code === undefined || code === null) return "Partly Cloudy";
    if (code === 0) return "Clear Sky";
    if (code === 1) return "Mainly Clear";
    if (code === 2) return "Partly Cloudy";
    if (code === 3) return "Overcast";
    if ([51, 53, 55].includes(code)) return "Light Drizzle";
    if ([61, 63, 65].includes(code)) return "Rain Showers";
    if ([80, 81, 82].includes(code)) return "Precipitation";
    if ([95, 96, 99].includes(code)) return "Thunderstorm";
    return "Variable Weather";
  };

  const getAqiBadgeStyle = (category?: string, aqi?: number | null) => {
    const val = aqi ?? 50;
    if (val <= 50) {
      return {
        bg: "bg-emerald-950/80 border-emerald-500/40 text-emerald-300",
        bar: "bg-emerald-400",
        label: "Good",
      };
    }
    if (val <= 100) {
      return {
        bg: "bg-amber-950/80 border-amber-500/40 text-amber-300",
        bar: "bg-amber-400",
        label: "Moderate",
      };
    }
    if (val <= 150) {
      return {
        bg: "bg-orange-950/80 border-orange-500/40 text-orange-300",
        bar: "bg-orange-400",
        label: "Unhealthy for Sensitive",
      };
    }
    if (val <= 200) {
      return {
        bg: "bg-rose-950/80 border-rose-500/40 text-rose-300",
        bar: "bg-rose-500",
        label: "Unhealthy",
      };
    }
    return {
      bg: "bg-purple-950/80 border-purple-500/40 text-purple-300",
      bar: "bg-purple-500",
      label: "Hazardous",
    };
  };

  const aqiStyle = getAqiBadgeStyle(air_quality?.category, air_quality?.us_aqi);
  const CurrentIcon = getWeatherIcon(current_conditions.weather_code);
  const daysToShow = forecastView === "7day" ? (forecast_15day || []).slice(0, 7) : (forecast_15day || []);

  const formatDayName = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    } catch {
      return dateStr;
    }
  };

  return (
    <section
      aria-label="15-Day Weather & Air Quality Telemetry"
      className="bg-black rounded-2xl p-5 border border-zinc-800 shadow-2xl space-y-5"
    >
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sun className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Weather & Air Quality: 15-Day Forward Forecast
            </h3>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Free high-resolution atmospheric telemetry powered by Open-Meteo & Copernicus CAMS.
          </p>
        </div>

        {/* Forecast View Switcher */}
        <div className="flex bg-zinc-900 p-0.5 rounded-lg border border-zinc-800 text-xs self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setForecastView("15day")}
            className={`px-3 py-1 rounded-md font-medium transition ${
              forecastView === "15day" ? "bg-zinc-800 text-white shadow-sm" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            15-Day Ahead
          </button>
          <button
            type="button"
            onClick={() => setForecastView("7day")}
            className={`px-3 py-1 rounded-md font-medium transition ${
              forecastView === "7day" ? "bg-zinc-800 text-white shadow-sm" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            7-Day Summary
          </button>
        </div>
      </div>

      {/* Current Conditions & AQI Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
        {/* Current Weather Card */}
        <div className="md:col-span-7 bg-zinc-950 p-4 rounded-xl border border-zinc-800 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                Current Atmospheric State
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-white tracking-tight">
                  {current_conditions.temperature_c ?? "--"}°C
                </span>
                <span className="text-xs text-zinc-400">
                  Feels like {current_conditions.apparent_temperature_c ?? current_conditions.temperature_c}°C
                </span>
              </div>
              <p className="text-xs text-cyan-300 font-medium">
                {getWeatherDescription(current_conditions.weather_code)}
              </p>
            </div>

            <div className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800/80 text-amber-400">
              <CurrentIcon className="h-8 w-8" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-zinc-900 text-xs">
            <div className="flex items-center gap-2 text-zinc-400">
              <Droplets className="h-3.5 w-3.5 text-cyan-400" />
              <span>Humidity: {current_conditions.humidity_pct ?? "--"}%</span>
            </div>
            <div className="flex items-center gap-2 text-zinc-400">
              <Wind className="h-3.5 w-3.5 text-sky-400" />
              <span>Wind: {current_conditions.wind_speed_kmh ?? "--"} km/h</span>
            </div>
            <div className="flex items-center gap-2 text-zinc-400">
              <CloudRain className="h-3.5 w-3.5 text-indigo-400" />
              <span>Rain: {current_conditions.rain_mm ?? 0} mm</span>
            </div>
          </div>
        </div>

        {/* Air Quality Index Card */}
        <div className="md:col-span-5 bg-zinc-950 p-4 rounded-xl border border-zinc-800 flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <Gauge className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Air Quality Index (AQI)
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-extrabold text-white font-mono">
                  {air_quality?.us_aqi ? Math.round(air_quality.us_aqi) : 52}
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${aqiStyle.bg}`}>
                  {air_quality?.category || aqiStyle.label}
                </span>
              </div>
            </div>
          </div>

          {/* Pollutant Breakdown Bar */}
          <div className="space-y-1.5 mt-3 pt-3 border-t border-zinc-900">
            <div className="flex justify-between text-[11px] text-zinc-400">
              <span>PM2.5: <strong className="text-white font-mono">{air_quality?.pm2_5 ?? 18} μg/m³</strong></span>
              <span>PM10: <strong className="text-white font-mono">{air_quality?.pm10 ?? 32} μg/m³</strong></span>
            </div>
            <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-1.5 rounded-full ${aqiStyle.bar}`}
                style={{ width: `${Math.min(100, Math.max(10, ((air_quality?.us_aqi ?? 50) / 200) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 15-Day Interactive Forecast Carousel / Grid */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 text-cyan-400" />
            <span>Daily Forecast & Air Quality Trajectory</span>
          </span>
          <span className="text-[11px] text-zinc-500 font-mono">
            {daysToShow.length} days projected
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-8 gap-2 overflow-x-auto pb-1">
          {daysToShow.map((day: WeatherDayForecast, idx: number) => {
            const DayIcon = getWeatherIcon(day.weather_code);
            const dayAqiStyle = getAqiBadgeStyle(day.aqi_category, day.us_aqi);
            const isToday = idx === 0;

            return (
              <div
                key={day.date}
                className={`p-2.5 rounded-xl border flex flex-col items-center justify-between gap-1.5 text-center transition ${
                  isToday
                    ? "bg-zinc-900/90 border-cyan-500/50 shadow-sm"
                    : "bg-zinc-950 border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <div className="text-[11px] font-medium text-zinc-300 truncate w-full">
                  {isToday ? "Today" : formatDayName(day.date).split(",")[0]}
                </div>
                <div className="text-[9.5px] text-zinc-500 font-mono">
                  {day.date.slice(5)}
                </div>

                <div className="my-1 text-cyan-400">
                  <DayIcon className="h-5 w-5" />
                </div>

                <div className="flex items-center gap-1 font-mono text-xs font-semibold text-white">
                  <span>{day.temp_max_c ? Math.round(day.temp_max_c) : "--"}°</span>
                  <span className="text-zinc-500 text-[10px]">
                    {day.temp_min_c ? Math.round(day.temp_min_c) : "--"}°
                  </span>
                </div>

                {/* Rain probability */}
                <div className="flex items-center gap-1 text-[10px] text-zinc-400">
                  <CloudRain className="h-3 w-3 text-sky-400 shrink-0" />
                  <span>{day.precip_probability_max ?? 0}%</span>
                </div>

                {/* AQI Pill */}
                <div
                  className={`w-full mt-1 py-0.5 rounded text-[9.5px] font-mono font-semibold border ${dayAqiStyle.bg}`}
                  title={`Air Quality: ${day.aqi_category || "Moderate"} (AQI ${Math.round(day.us_aqi ?? 50)})`}
                >
                  AQI {Math.round(day.us_aqi ?? 50)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
