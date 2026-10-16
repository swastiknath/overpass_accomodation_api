"use client";

import React from "react";
import { Download, FileJson } from "lucide-react";
import { SearchReport } from "@/types";

interface ExportButtonsProps {
  report: SearchReport;
}

export default function ExportButtons({ report }: ExportButtonsProps) {
  const downloadJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `travel_safety_report_${report.report_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const downloadGeoJSON = () => {
    if (!report.geojson) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report.geojson, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `travel_safety_spatial_${report.report_id}.geojson`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={downloadJSON}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 hover:text-white transition shadow-sm"
        title="Download complete report payload as JSON"
      >
        <FileJson className="h-3.5 w-3.5 text-indigo-400" />
        <span>Report JSON</span>
      </button>

      <button
        type="button"
        onClick={downloadGeoJSON}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 hover:text-white transition shadow-sm"
        title="Download spatial hazards and accommodation markers as GeoJSON"
      >
        <Download className="h-3.5 w-3.5 text-indigo-400" />
        <span>Spatial GeoJSON</span>
      </button>
    </div>
  );
}
