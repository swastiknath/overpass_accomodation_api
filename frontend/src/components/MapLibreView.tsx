"use client";

import React, { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { Layers, Eye, EyeOff, MapPin } from "lucide-react";
import { SearchReport, HotelScored } from "@/types";

interface MapLibreViewProps {
  report: SearchReport;
  selectedHotelId: string | null;
  onSelectHotel: (hotelId: string) => void;
}

export default function MapLibreView({
  report,
  selectedHotelId,
  onSelectHotel,
}: MapLibreViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<{ [key: string]: maplibregl.Marker }>({});

  const [visibleLayers, setVisibleLayers] = useState({
    hazards: true,
    hotels: true,
  });

  const { location, geojson, hotels_ranked } = report;
  const styleUrl =
    process.env.NEXT_PUBLIC_MAP_STYLE_URL ||
    "https://demotiles.maplibre.org/style.json";

  useEffect(() => {
    if (!mapContainerRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: styleUrl,
      center: [location.lon, location.lat],
      zoom: 12,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      // 1. Add Query Anchor Marker
      const anchorEl = document.createElement("div");
      anchorEl.className =
        "w-6 h-6 rounded-full bg-indigo-600 border-2 border-white shadow-lg flex items-center justify-center text-white";
      anchorEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>`;
      new maplibregl.Marker({ element: anchorEl })
        .setLngLat([location.lon, location.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="color:#0f172a; font-size:12px; font-weight:600;">Search Location: ${location.display_name.split(",")[0]}</div>`
          )
        )
        .addTo(map);

      // 2. Add GeoJSON Hazard Layer
      if (geojson) {
        map.addSource("hazard-features", {
          type: "geojson",
          data: geojson,
        });

        // Circle layer for point hazards
        map.addLayer({
          id: "hazard-points",
          type: "circle",
          source: "hazard-features",
          filter: ["==", "feature_type", "hazard"],
          paint: {
            "circle-radius": 10,
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
            "circle-opacity": 0.75,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });

        // Tooltip popup on hover
        const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
        map.on("mouseenter", "hazard-points", (e) => {
          map.getCanvas().style.cursor = "pointer";
          const feat = e.features?.[0];
          if (!feat) return;
          const coords = (feat.geometry as any).coordinates.slice();
          const props = feat.properties;
          popup
            .setLngLat(coords)
            .setHTML(
              `<div style="color:#0f172a; font-size:11px; padding:2px;">
                <strong>${props.hazard_type?.toUpperCase()}</strong>: ${props.title || props.event_id}<br/>
                <span style="color:#64748b;">Source: ${props.source}</span>
              </div>`
            )
            .addTo(map);
        });

        map.on("mouseleave", "hazard-points", () => {
          map.getCanvas().style.cursor = "";
          popup.remove();
        });
      }

      // 3. Render Hotel Markers with Score & Band Label
      renderHotelMarkers(map, hotels_ranked, selectedHotelId);
    });

    mapRef.current = map;

    return () => {
      map.remove();
    };
  }, [location.lat, location.lon]);

  // Re-render markers if hotels or selection changes
  useEffect(() => {
    if (mapRef.current && mapRef.current.isStyleLoaded()) {
      renderHotelMarkers(mapRef.current, hotels_ranked, selectedHotelId);
    }
  }, [hotels_ranked, selectedHotelId]);

  // Handle layer visibility toggles
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    if (map.getLayer("hazard-points")) {
      map.setLayoutProperty(
        "hazard-points",
        "visibility",
        visibleLayers.hazards ? "visible" : "none"
      );
    }

    Object.values(markersRef.current).forEach((marker) => {
      marker.getElement().style.display = visibleLayers.hotels ? "flex" : "none";
    });
  }, [visibleLayers]);

  // Sync selected hotel flying
  useEffect(() => {
    if (!mapRef.current || !selectedHotelId) return;
    const selected = hotels_ranked.find((h) => h.hotel.id === selectedHotelId);
    if (selected) {
      mapRef.current.flyTo({
        center: [selected.hotel.lon, selected.hotel.lat],
        zoom: 14,
        essential: true,
      });
    }
  }, [selectedHotelId]);

  const renderHotelMarkers = (
    map: maplibregl.Map,
    hotels: HotelScored[],
    activeId: string | null
  ) => {
    // Clear existing
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    hotels.forEach((h) => {
      const isSelected = h.hotel.id === activeId;
      const score = h.safety_score;
      const bandCode = h.score_band.code.toLowerCase();

      let badgeBg = "#10b981"; // Low / green
      if (bandCode === "moderate") badgeBg = "#06b6d4"; // Cyan
      else if (bandCode === "elevated") badgeBg = "#f59e0b"; // Amber
      else if (bandCode === "high") badgeBg = "#f97316"; // Orange
      else if (bandCode === "severe") badgeBg = "#f43f5e"; // Rose

      const el = document.createElement("div");
      el.id = `map-marker-${h.hotel.id}`;
      el.className = `cursor-pointer transition-transform transform ${
        isSelected ? "scale-125 z-30" : "hover:scale-110 z-10"
      } flex items-center gap-1 px-1.5 py-0.5 rounded-full shadow-lg border text-[10px] font-bold text-white`;
      el.style.backgroundColor = badgeBg;
      el.style.borderColor = isSelected ? "#ffffff" : "rgba(255,255,255,0.4)";
      el.innerHTML = `<span>★ ${h.hotel.stars || ""}</span> <span>${score}</span>`;

      el.addEventListener("click", () => {
        onSelectHotel(h.hotel.id);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([h.hotel.lon, h.hotel.lat])
        .setPopup(
          new maplibregl.Popup({ offset: 10 }).setHTML(
            `<div style="color:#0f172a; font-size:12px; font-weight:bold;">${h.hotel.name}</div>
             <div style="color:#475569; font-size:11px;">Safety: ${score}/100 (${h.score_band.label})</div>
             <div style="color:#475569; font-size:11px;">Rank Score: ${h.rank_score}</div>`
          )
        )
        .addTo(map);

      markersRef.current[h.hotel.id] = marker;
    });
  };

  return (
    <div className="relative w-full h-[450px] lg:h-[520px] rounded-2xl overflow-hidden border border-slate-800 shadow-2xl bg-slate-900">
      {/* Map Container */}
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Map Overlay Controls / Layer Toggles */}
      <div className="absolute top-3 left-3 z-10 bg-slate-900/90 backdrop-blur-md p-2 rounded-xl border border-slate-700/80 shadow-lg text-xs space-y-2">
        <div className="flex items-center gap-1.5 text-slate-300 font-semibold border-b border-slate-800 pb-1">
          <Layers className="h-3.5 w-3.5 text-indigo-400" />
          <span>Map Layers</span>
        </div>
        <div className="space-y-1">
          <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={visibleLayers.hazards}
              onChange={(e) =>
                setVisibleLayers({ ...visibleLayers, hazards: e.target.checked })
              }
              className="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0"
            />
            <span>Geo-Hazards (Flood/Quake/Fire)</span>
          </label>
          <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={visibleLayers.hotels}
              onChange={(e) =>
                setVisibleLayers({ ...visibleLayers, hotels: e.target.checked })
              }
              className="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0"
            />
            <span>Hotel Markers with Scores</span>
          </label>
        </div>
      </div>

      {/* Tile Notice */}
      <div className="absolute bottom-1 right-2 z-10 text-[9px] text-slate-400 bg-slate-950/80 px-2 py-0.5 rounded backdrop-blur-sm">
        Public MapLibre demo tiles for light dev use
      </div>
    </div>
  );
}
