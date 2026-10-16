"use client";

import React, { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  Layers,
  CloudRain,
  ShieldCheck,
  MapPin,
  Hospital,
  Shield,
  Compass,
  Thermometer,
  SunMedium,
} from "lucide-react";
import { SearchReport, HotelScored } from "@/types";

if (typeof window !== "undefined") {
  try {
    (maplibregl as any).setWorkerUrl(`${window.location.origin}/maplibre-gl-worker.mjs`);
  } catch (err) {
    console.warn("Could not set MapLibre workerUrl at module init:", err);
  }
}

function getWeatherDescription(code: number): string {
  if (code === 0) return "Clear Sky";
  if (code === 1) return "Mainly Clear";
  if (code === 2) return "Partly Cloudy";
  if (code === 3) return "Overcast";
  if ([45, 48].includes(code)) return "Fog / Mist";
  if ([51, 53, 55].includes(code)) return "Drizzle";
  if ([61, 63, 65].includes(code)) return "Rain";
  if ([71, 73, 75].includes(code)) return "Snowfall";
  if ([80, 81, 82].includes(code)) return "Rain Showers";
  if ([95, 96, 99].includes(code)) return "Thunderstorm";
  return "Clear";
}

interface MapLibreViewProps {
  report: SearchReport;
  selectedHotelId: string | null;
  onSelectHotel: (hotelId: string) => void;
}

const CARTO_KEY =
  process.env.NEXT_PUBLIC_CARTO_API_KEY || "cb1_4mnl_1_bec5e5affba90bd94917f6fa";

const CARTO_VECTOR_STYLE =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ||
  `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json?key=${CARTO_KEY}`;

// Crisp dark raster style with CARTO API Key to eliminate watermark
const CARTO_DARK_MATTER_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "carto-dark-raster": {
      type: "raster",
      tiles: [
        `https://a.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}@2x.png?key=${CARTO_KEY}`,
        `https://b.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}@2x.png?key=${CARTO_KEY}`,
        `https://c.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}@2x.png?key=${CARTO_KEY}`,
        `https://d.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}@2x.png?key=${CARTO_KEY}`,
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "carto-dark-layer",
      type: "raster",
      source: "carto-dark-raster",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

const OSM_FALLBACK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "osm-raster-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "osm-raster-layer",
      type: "raster",
      source: "osm-raster-tiles",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export default function MapLibreView({
  report,
  selectedHotelId,
  onSelectHotel,
}: MapLibreViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<{ [key: string]: maplibregl.Marker }>({});

  const [visibleLayers, setVisibleLayers] = useState({
    temperatureHeatmap: true,
    weatherStations: true,
    weatherRadar: true,
    searchRadius: true,
    hazards: true,
    emergency: true,
    hotels: true,
  });

  const [centerWeather, setCenterWeather] = useState<{
    temp: number;
    condition: string;
    precipitation: number;
    windSpeed: number;
  } | null>(null);

  const { location, geojson, hotels_ranked } = report;

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (typeof window !== "undefined") {
      try {
        (maplibregl as any).setWorkerUrl(`${window.location.origin}/maplibre-gl-worker.mjs`);
      } catch (err) {
        console.warn("Could not set MapLibre workerUrl in effect:", err);
      }
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: CARTO_VECTOR_STYLE,
      center: [location.lon, location.lat],
      zoom: 12,
    });

    map.on("error", (e) => {
      if (
        e.error &&
        (e.error.message?.includes("Failed to fetch") ||
          (e.error as any).status === 404 ||
          (e.error as any).status === 401)
      ) {
        console.warn("CARTO vector style issue; falling back to authenticated raster:", e.error);
        try {
          map.setStyle(CARTO_DARK_MATTER_STYLE);
        } catch (err) {
          try {
            map.setStyle(OSM_FALLBACK_STYLE);
          } catch (osmErr) {}
        }
      }
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const handleWindowResize = () => {
      try {
        map.resize();
      } catch (err) {}
    };
    window.addEventListener("resize", handleWindowResize);

    map.on("load", () => {
      map.resize();

      // 1. Add Query Anchor Marker synchronously
      const anchorEl = document.createElement("div");
      anchorEl.className =
        "w-6 h-6 rounded-full bg-cyan-400 border-2 border-white shadow-[0_0_15px_rgba(6,182,212,0.8)] flex items-center justify-center text-black font-bold animate-pulse";
      anchorEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/></svg>`;
      new maplibregl.Marker({ element: anchorEl })
        .setLngLat([location.lon, location.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="color:#09090b; font-size:12px; font-weight:700;">Query Center: ${location.display_name.split(",")[0]}</div>`
          )
        )
        .addTo(map);

      // 2. Add GeoJSON Feature Collection synchronously (Search radius, emergency services, hazards)
      if (geojson) {
        if (!map.getSource("spatial-features")) {
          map.addSource("spatial-features", {
            type: "geojson",
            data: geojson,
          });
        }

        // Layer: Search Radius Zone (Polygon Fill & Stroke)
        if (!map.getLayer("search-radius-fill")) {
          map.addLayer({
            id: "search-radius-fill",
            type: "fill",
            source: "spatial-features",
            filter: ["==", "feature_type", "search_radius"],
            paint: {
              "fill-color": "#06b6d4",
              "fill-opacity": 0.08,
            },
          });
        }

        if (!map.getLayer("search-radius-line")) {
          map.addLayer({
            id: "search-radius-line",
            type: "line",
            source: "spatial-features",
            filter: ["==", "feature_type", "search_radius"],
            paint: {
              "line-color": "#22d3ee",
              "line-width": 1.75,
              "line-dasharray": [3, 2],
            },
          });
        }

        // Layer: Emergency Facilities - Hospitals
        if (!map.getLayer("emergency-hospitals")) {
          map.addLayer({
            id: "emergency-hospitals",
            type: "circle",
            source: "spatial-features",
            filter: ["all", ["==", "feature_type", "emergency"], ["==", "amenity", "hospital"]],
            paint: {
              "circle-radius": 7,
              "circle-color": "#f43f5e",
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          });
        }

        // Layer: Emergency Facilities - Police
        if (!map.getLayer("emergency-police")) {
          map.addLayer({
            id: "emergency-police",
            type: "circle",
            source: "spatial-features",
            filter: ["all", ["==", "feature_type", "emergency"], ["==", "amenity", "police"]],
            paint: {
              "circle-radius": 7,
              "circle-color": "#38bdf8",
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          });
        }

        // Layer: Hazard Points
        if (!map.getLayer("hazard-points")) {
          map.addLayer({
            id: "hazard-points",
            type: "circle",
            source: "spatial-features",
            filter: ["==", "feature_type", "hazard"],
            paint: {
              "circle-radius": 9,
              "circle-color": [
                "match",
                ["get", "hazard_type"],
                "flood",
                "#06b6d4",
                "cyclone",
                "#3b82f6",
                "earthquake",
                "#eab308",
                "fire",
                "#f97316",
                "conflict",
                "#ef4444",
                "weather",
                "#8b5cf6",
                "#ec4899",
              ],
              "circle-opacity": 0.85,
              "circle-stroke-width": 2,
              "circle-stroke-color": "#ffffff",
            },
          });
        }

        // Popups for hazards & emergency facilities
        const hoverPopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });

        map.on("mouseenter", "hazard-points", (e) => {
          map.getCanvas().style.cursor = "pointer";
          const feat = e.features?.[0];
          if (!feat) return;
          const coords = (feat.geometry as any).coordinates.slice();
          const props = feat.properties;
          hoverPopup
            .setLngLat(coords)
            .setHTML(
              `<div style="color:#09090b; font-size:11px; padding:3px; max-width:220px;">
                <strong style="color:#ef4444;">HAZARD: ${props.hazard_type?.toUpperCase()}</strong><br/>
                ${props.title || props.event_id}<br/>
                <span style="color:#71717a; font-size:10px;">Source: ${props.source}</span>
              </div>`
            )
            .addTo(map);
        });

        map.on("mouseleave", "hazard-points", () => {
          map.getCanvas().style.cursor = "";
          hoverPopup.remove();
        });

        map.on("mouseenter", "emergency-hospitals", (e) => {
          map.getCanvas().style.cursor = "pointer";
          const feat = e.features?.[0];
          if (!feat) return;
          const coords = (feat.geometry as any).coordinates.slice();
          hoverPopup
            .setLngLat(coords)
            .setHTML(
              `<div style="color:#09090b; font-size:11px; padding:3px;">
                <strong style="color:#e11d48;">🏥 HOSPITAL</strong><br/>
                ${feat.properties?.name || "Medical Facility"}
              </div>`
            )
            .addTo(map);
        });

        map.on("mouseleave", "emergency-hospitals", () => {
          map.getCanvas().style.cursor = "";
          hoverPopup.remove();
        });

        map.on("mouseenter", "emergency-police", (e) => {
          map.getCanvas().style.cursor = "pointer";
          const feat = e.features?.[0];
          if (!feat) return;
          const coords = (feat.geometry as any).coordinates.slice();
          hoverPopup
            .setLngLat(coords)
            .setHTML(
              `<div style="color:#09090b; font-size:11px; padding:3px;">
                <strong style="color:#0284c7;">🛡️ POLICE STATION</strong><br/>
                ${feat.properties?.name || "Police Facility"}
              </div>`
            )
            .addTo(map);
        });

        map.on("mouseleave", "emergency-police", () => {
          map.getCanvas().style.cursor = "";
          hoverPopup.remove();
        });
      }

      // 3. Render Hotel Markers synchronously
      renderHotelMarkers(map, hotels_ranked, selectedHotelId);

      // 4. Open-Meteo High-Resolution Spatial Thermal Mesh (100% Free IMD/ECMWF coverage for India & Global)
      const offsets = [-0.35, 0, 0.35];
      const sampleLats: number[] = [];
      const sampleLons: number[] = [];
      for (const dy of offsets) {
        for (const dx of offsets) {
          sampleLats.push(Number((location.lat + dy).toFixed(4)));
          sampleLons.push(Number((location.lon + dx).toFixed(4)));
        }
      }

      const openMeteoUrl = `https://api.open-meteo.com/v1/forecast?latitude=${sampleLats.join(",")}&longitude=${sampleLons.join(",")}&current=temperature_2m,precipitation,weather_code,wind_speed_10m`;

      fetch(openMeteoUrl)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data || !mapRef.current) return;
          const items = Array.isArray(data) ? data : [data];
          if (items.length === 0) return;

          // Center item (index 4 in 3x3)
          const centerItem = items[Math.floor(items.length / 2)] || items[0];
          if (centerItem?.current) {
            setCenterWeather({
              temp: centerItem.current.temperature_2m,
              condition: getWeatherDescription(centerItem.current.weather_code),
              precipitation: centerItem.current.precipitation,
              windSpeed: centerItem.current.wind_speed_10m,
            });
          }

          const weatherGeoJson: any = {
            type: "FeatureCollection",
            features: items.map((pt, idx) => {
              const c = pt.current || {};
              const t = c.temperature_2m ?? 22;
              return {
                type: "Feature",
                geometry: {
                  type: "Point",
                  coordinates: [pt.longitude, pt.latitude],
                },
                properties: {
                  id: `station-${idx}`,
                  temp: t,
                  precipitation: c.precipitation ?? 0,
                  wind_speed: c.wind_speed_10m ?? 0,
                  weather_code: c.weather_code ?? 0,
                  weather_desc: getWeatherDescription(c.weather_code ?? 0),
                },
              };
            }),
          };

          if (!map.getSource("weather-thermal-source")) {
            map.addSource("weather-thermal-source", {
              type: "geojson",
              data: weatherGeoJson,
            });

            // WebGL Temperature Heatmap Layer
            map.addLayer(
              {
                id: "weather-temperature-heatmap",
                type: "heatmap",
                source: "weather-thermal-source",
                paint: {
                  "heatmap-weight": [
                    "interpolate",
                    ["linear"],
                    ["get", "temp"],
                    0, 0.2,
                    15, 0.5,
                    25, 0.8,
                    35, 1.1,
                    45, 1.4,
                  ],
                  "heatmap-intensity": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    0, 0.8,
                    7, 1.5,
                    12, 2.2,
                    15, 3.0,
                  ],
                  "heatmap-color": [
                    "interpolate",
                    ["linear"],
                    ["heatmap-density"],
                    0, "rgba(0, 0, 0, 0)",
                    0.15, "rgba(59, 130, 246, 0.45)",  // Cold / Blue
                    0.35, "rgba(6, 182, 212, 0.55)",   // Cool / Cyan
                    0.55, "rgba(16, 185, 129, 0.60)",  // Pleasant / Emerald
                    0.75, "rgba(245, 158, 11, 0.70)",  // Warm / Amber
                    1.0, "rgba(239, 68, 68, 0.85)",    // Hot / Crimson
                  ],
                  "heatmap-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    4, 45,
                    8, 80,
                    12, 125,
                    16, 180,
                  ],
                  "heatmap-opacity": 0.65,
                },
              },
              "search-radius-fill"
            );

            // Weather Station Circles Layer
            map.addLayer(
              {
                id: "weather-station-circles",
                type: "circle",
                source: "weather-thermal-source",
                paint: {
                  "circle-radius": 13,
                  "circle-color": [
                    "interpolate",
                    ["linear"],
                    ["get", "temp"],
                    5, "#3b82f6",
                    15, "#06b6d4",
                    25, "#10b981",
                    32, "#f59e0b",
                    40, "#ef4444",
                  ],
                  "circle-stroke-width": 2,
                  "circle-stroke-color": "#ffffff",
                  "circle-opacity": 0.9,
                },
              },
              "search-radius-fill"
            );

            // Weather Station Inner Dot
            map.addLayer(
              {
                id: "weather-station-inner",
                type: "circle",
                source: "weather-thermal-source",
                paint: {
                  "circle-radius": 4,
                  "circle-color": "#ffffff",
                  "circle-opacity": 0.9,
                },
              },
              "search-radius-fill"
            );

            const weatherPopup = new maplibregl.Popup({
              closeButton: false,
              closeOnClick: false,
              offset: 14,
            });

            map.on("mouseenter", "weather-station-circles", (e) => {
              map.getCanvas().style.cursor = "pointer";
              const feat = e.features?.[0];
              if (!feat) return;
              const coords = (feat.geometry as any).coordinates.slice();
              const p = feat.properties;
              weatherPopup
                .setLngLat(coords)
                .setHTML(
                  `<div style="color:#09090b; font-size:12px; font-weight:600; padding:4px 6px; min-width:145px;">
                    <div style="font-size:13px; font-weight:700; color:#0284c7; margin-bottom:2px;">
                      🌡️ ${p.temp}°C
                    </div>
                    <div style="color:#27272a; font-size:11px;">Condition: <strong>${p.weather_desc}</strong></div>
                    <div style="color:#52525b; font-size:11px;">Rain: <strong>${p.precipitation} mm/h</strong></div>
                    <div style="color:#52525b; font-size:11px;">Wind: <strong>${p.wind_speed} km/h</strong></div>
                    <div style="color:#71717a; font-size:9px; margin-top:3px; border-top:1px solid #e4e4e7; padding-top:2px;">
                      Open-Meteo Live India Station
                    </div>
                  </div>`
                )
                .addTo(map);
            });

            map.on("mouseleave", "weather-station-circles", () => {
              map.getCanvas().style.cursor = "";
              weatherPopup.remove();
            });

            // Synchronize initial layer toggles
            if (!visibleLayers.temperatureHeatmap && map.getLayer("weather-temperature-heatmap")) {
              map.setLayoutProperty("weather-temperature-heatmap", "visibility", "none");
            }
            if (!visibleLayers.weatherStations) {
              if (map.getLayer("weather-station-circles")) {
                map.setLayoutProperty("weather-station-circles", "visibility", "none");
              }
              if (map.getLayer("weather-station-inner")) {
                map.setLayoutProperty("weather-station-inner", "visibility", "none");
              }
            }
          }
        })
        .catch((wErr) => {
          console.warn("Open-Meteo spatial mesh fetch error:", wErr);
        });

      // 5. Background Non-Blocking Weather Radar Layer (RainViewer capped at maxzoom: 7)
      // Setting maxzoom: 7 prevents RainViewer API from serving "Zoom Level Not Supported" tiles
      fetch("https://api.rainviewer.com/public/weather-maps.json")
        .then((rvRes) => (rvRes.ok ? rvRes.json() : null))
        .then((rvData) => {
          if (!rvData || !mapRef.current) return;
          const radarPast = rvData?.radar?.past;
          const latestPath =
            radarPast && radarPast.length > 0 ? radarPast[radarPast.length - 1].path : null;

          if (latestPath && !map.getSource("live-radar-source")) {
            map.addSource("live-radar-source", {
              type: "raster",
              tiles: [`https://tilecache.rainviewer.com${latestPath}/256/{z}/{x}/{y}/2/1_1.png`],
              tileSize: 256,
              maxzoom: 7, // RainViewer public API cap: MapLibre smoothly upsamples for z >= 8
            });

            map.addLayer(
              {
                id: "live-weather-radar",
                type: "raster",
                source: "live-radar-source",
                paint: {
                  "raster-opacity": 0.6,
                },
              },
              "search-radius-fill" // Place underneath the vector radius fill
            );

            // Apply visibility setting if user toggled it off before load
            if (!visibleLayers.weatherRadar && map.getLayer("live-weather-radar")) {
              map.setLayoutProperty("live-weather-radar", "visibility", "none");
            }
          }
        })
        .catch((rvErr) => {
          console.warn("RainViewer live radar tile fetch non-blocking error:", rvErr);
        });
    });

    mapRef.current = map;

    return () => {
      window.removeEventListener("resize", handleWindowResize);
      map.remove();
    };
  }, [location.lat, location.lon]);

  // Update GeoJSON when changed
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource("spatial-features") as maplibregl.GeoJSONSource;
    if (source && geojson) {
      source.setData(geojson);
    }

    if (hotels_ranked) {
      renderHotelMarkers(mapRef.current, hotels_ranked, selectedHotelId);
    }
  }, [hotels_ranked, selectedHotelId, geojson]);

  // Handle layer visibility toggles
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const setLayerVis = (id: string, isVis: boolean) => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", isVis ? "visible" : "none");
      }
    };

    setLayerVis("weather-temperature-heatmap", visibleLayers.temperatureHeatmap);
    setLayerVis("weather-station-circles", visibleLayers.weatherStations);
    setLayerVis("weather-station-inner", visibleLayers.weatherStations);
    setLayerVis("live-weather-radar", visibleLayers.weatherRadar);
    setLayerVis("search-radius-fill", visibleLayers.searchRadius);
    setLayerVis("search-radius-line", visibleLayers.searchRadius);
    setLayerVis("hazard-points", visibleLayers.hazards);
    setLayerVis("emergency-hospitals", visibleLayers.emergency);
    setLayerVis("emergency-police", visibleLayers.emergency);

    Object.values(markersRef.current).forEach((marker) => {
      marker.getElement().style.display = visibleLayers.hotels ? "flex" : "none";
    });
  }, [visibleLayers]);

  // Hotel markers creation
  const renderHotelMarkers = (
    mapInstance: maplibregl.Map | null,
    hotels: HotelScored[],
    currentSelectedId: string | null
  ) => {
    if (!mapInstance) return;

    // Remove existing markers
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    hotels.forEach((h, index) => {
      const isSelected = h.hotel.id === currentSelectedId;
      const el = document.createElement("div");
      el.className = `cursor-pointer transition-all duration-200 transform hover:scale-110 flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-bold border shadow-xl ${
        isSelected
          ? "bg-cyan-500 text-black border-white scale-110 z-30 ring-2 ring-cyan-300 ring-offset-2 ring-offset-black"
          : "bg-emerald-500 text-black border-white/80 z-10 hover:z-20"
      }`;

      const starText = h.hotel.stars ? `${h.hotel.stars}★` : `${index + 1}`;
      el.innerHTML = `<span>${starText}</span><span class="bg-black/20 px-1 rounded text-[10px]">${h.safety_score}</span>`;

      el.addEventListener("click", () => {
        onSelectHotel(h.hotel.id);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([h.hotel.lon, h.hotel.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="color:#09090b; font-size:12px; font-weight:700;">${h.hotel.name}</div>
             <div style="color:#71717a; font-size:11px;">Safety Score: ${h.safety_score}/100 &bull; Rank Score: ${h.rank_score}</div>`
          )
        )
        .addTo(mapInstance);

      markersRef.current[h.hotel.id] = marker;
    });
  };

  return (
    <div className="relative w-full h-[460px] sm:h-[500px] rounded-2xl overflow-hidden border border-zinc-800 shadow-2xl bg-black">
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Live Map Layers Floating Control Panel */}
      <div className="absolute top-4 left-4 z-10 bg-black/85 backdrop-blur-md p-3.5 rounded-xl border border-zinc-800/90 text-xs text-white shadow-2xl space-y-2.5 max-w-[275px]">
        <div className="flex items-center gap-2 font-bold text-zinc-200 border-b border-zinc-800 pb-2 uppercase tracking-wider text-[11px]">
          <Layers className="h-4 w-4 text-cyan-400" />
          <span>Interactive Map Layers</span>
        </div>

        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer hover:text-amber-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.temperatureHeatmap}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, temperatureHeatmap: e.target.checked }))
              }
              className="accent-amber-400 rounded"
            />
            <Thermometer className="h-3.5 w-3.5 text-amber-400" />
            <span>Temperature Heatmap (Open-Meteo)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-cyan-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.weatherStations}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, weatherStations: e.target.checked }))
              }
              className="accent-cyan-400 rounded"
            />
            <SunMedium className="h-3.5 w-3.5 text-cyan-400" />
            <span>Weather Stations & Badges</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-sky-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.weatherRadar}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, weatherRadar: e.target.checked }))
              }
              className="accent-sky-400 rounded"
            />
            <CloudRain className="h-3.5 w-3.5 text-sky-400" />
            <span>Live RainViewer Radar</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-cyan-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.searchRadius}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, searchRadius: e.target.checked }))
              }
              className="accent-cyan-400 rounded"
            />
            <Compass className="h-3.5 w-3.5 text-cyan-400" />
            <span>Search Radius ({location.radius_km || 5} km)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-rose-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.hazards}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, hazards: e.target.checked }))
              }
              className="accent-rose-500 rounded"
            />
            <ShieldCheck className="h-3.5 w-3.5 text-rose-400" />
            <span>Geo-Hazards (Fire/Quake/Conflict)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-rose-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.emergency}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, emergency: e.target.checked }))
              }
              className="accent-rose-400 rounded"
            />
            <div className="flex items-center gap-1">
              <Hospital className="h-3.5 w-3.5 text-rose-400" />
              <Shield className="h-3 w-3 text-sky-400" />
            </div>
            <span>Emergency (Hospitals & Police)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer hover:text-emerald-300 transition text-[11px]">
            <input
              type="checkbox"
              checked={visibleLayers.hotels}
              onChange={(e) =>
                setVisibleLayers((prev) => ({ ...prev, hotels: e.target.checked }))
              }
              className="accent-emerald-400 rounded"
            />
            <MapPin className="h-3.5 w-3.5 text-emerald-400" />
            <span>Hotel Markers & Scores</span>
          </label>
        </div>
      </div>

      {/* Live Thermal Mesh Legend & Weather Pill */}
      <div className="absolute bottom-3 left-3 z-10 hidden sm:flex flex-col gap-1.5 p-2.5 rounded-xl bg-black/85 backdrop-blur-md border border-zinc-800/90 text-xs text-white shadow-2xl max-w-[310px]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-200">
            <Thermometer className="h-3.5 w-3.5 text-amber-400" />
            <span>Live Thermal Overlay</span>
          </div>
          {centerWeather && (
            <span className="text-[11px] font-bold text-amber-300 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/50">
              {centerWeather.temp}°C &bull; {centerWeather.condition}
            </span>
          )}
        </div>

        {/* Thermal Spectrum Bar */}
        <div className="space-y-1">
          <div className="h-2 w-full rounded-full bg-gradient-to-r from-blue-500 via-cyan-400 via-emerald-400 via-amber-400 to-rose-500 border border-white/20" />
          <div className="flex justify-between text-[9px] text-zinc-400 font-medium">
            <span>&lt;10°C Cool</span>
            <span>20°C Mild</span>
            <span>30°C Warm</span>
            <span>&gt;38°C Hot</span>
          </div>
        </div>

        <div className="text-[9px] text-zinc-500 border-t border-zinc-800/60 pt-1 flex items-center justify-between">
          <span>Free Open-Meteo High-Res Mesh</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
        </div>
      </div>

      {/* Radar telemetry status pill */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-2 px-3 py-1 rounded-full bg-black/80 backdrop-blur-md border border-zinc-800 text-[11px] text-zinc-300">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>Live Doppler Precipitation Stream</span>
      </div>
    </div>
  );
}
