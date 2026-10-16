"use client";

import React from "react";
import { Info, ShieldAlert } from "lucide-react";

interface FooterProps {
  configVersion?: string;
  reportTimestamp?: string;
  disclaimer?: string;
}

export default function Footer({ configVersion, reportTimestamp, disclaimer }: FooterProps) {
  return (
    <footer className="mt-12 bg-slate-950 border-t border-slate-900 text-xs text-slate-400 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Research Disclaimer */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs leading-relaxed flex items-start gap-3">
          <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
          <p className="text-slate-300">
            {disclaimer || (
              "This platform is an automated research intelligence and situational awareness tool aggregating public and satellite data. It is NOT an official disaster alert or travel advisory and must not replace official guidance from NDMA, IMD, or local state authorities."
            )}
          </p>
        </div>

        {/* Data Attributions */}
        <div className="space-y-2">
          <span className="font-semibold text-slate-300 uppercase tracking-wider text-[11px] block">
            Data Source Attributions & Licensing:
          </span>
          <p className="text-[11px] text-slate-400 leading-normal">
            OpenStreetMap (ODbL) © OpenStreetMap contributors • GDACS (United Nations / European Commission) •
            USGS Earthquake Hazards Program • NASA FIRMS (MODIS/VIIRS) • Armed Conflict Location & Event Data (ACLED) •
            data.gov.in / National Crime Records Bureau (NCRB) • Open-Meteo & India Meteorological Department (IMD) •
            NRSC / ISRO Bhuvan Geological Atlas.
          </p>
        </div>

        {/* Build & Config Info */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-4 border-t border-slate-900 text-[11px] text-slate-400">
          <span>Copyright (C) 2026 Basabdutta Mondal & Swastik Nath. All rights reserved.</span>
          <div className="flex items-center gap-3">
            {configVersion && (
              <span>
                Config Version: <strong className="text-slate-300 font-mono">{configVersion}</strong>
              </span>
            )}
            {reportTimestamp && (
              <span>
                Report Generated: <strong className="text-slate-300 font-mono">{new Date(reportTimestamp).toLocaleTimeString()}</strong>
              </span>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
