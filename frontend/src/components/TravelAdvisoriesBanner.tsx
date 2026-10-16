"use client";

import React, { useState } from "react";
import {
  AlertOctagon,
  ShieldAlert,
  AlertTriangle,
  ExternalLink,
  PhoneCall,
  Building2,
  FileText,
  ChevronRight,
  Shield,
} from "lucide-react";
import { TravelAdvisoryInfo, GovTravelAdvisoryItem } from "@/types";

interface TravelAdvisoriesBannerProps {
  advisory?: TravelAdvisoryInfo | null;
  locationName: string;
}

export default function TravelAdvisoriesBanner({
  advisory,
  locationName,
}: TravelAdvisoriesBannerProps) {
  if (!advisory || !advisory.active_warning) {
    return null;
  }

  const [activeTab, setActiveTab] = useState<"all" | "india_mea" | "us_state_dept" | "uk_fcdo">("all");

  const level = advisory.level || 1;
  const isLevel4 = level >= 4;
  const isLevel3 = level === 3;

  const containerStyles = isLevel4
    ? "border-rose-600/80 bg-rose-950/40 text-rose-100 shadow-[0_0_35px_rgba(225,29,72,0.25)]"
    : isLevel3
    ? "border-amber-600/80 bg-amber-950/40 text-amber-100 shadow-[0_0_30px_rgba(217,119,6,0.20)]"
    : "border-yellow-600/50 bg-yellow-950/30 text-yellow-100";

  const topBadgeStyles = isLevel4
    ? "bg-rose-600 text-white border-rose-400 font-extrabold"
    : isLevel3
    ? "bg-amber-600 text-white border-amber-400 font-bold"
    : "bg-yellow-600 text-black border-yellow-400 font-semibold";

  const advisoriesList: GovTravelAdvisoryItem[] =
    advisory.advisories_list ||
    (advisory.sources
      ? [advisory.sources.india_mea, advisory.sources.us_state_dept, advisory.sources.uk_fcdo].filter(
          Boolean
        ) as GovTravelAdvisoryItem[]
      : []);

  const getStatusBadge = (lvl: number, label: string) => {
    if (lvl >= 4) {
      return "bg-rose-500/20 text-rose-300 border-rose-500/60";
    }
    if (lvl === 3) {
      return "bg-amber-500/20 text-amber-300 border-amber-500/60";
    }
    if (lvl === 2) {
      return "bg-yellow-500/20 text-yellow-300 border-yellow-500/50";
    }
    return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
  };

  return (
    <aside
      aria-label="Official Diplomatic Travel Advisories"
      className={`rounded-2xl p-5 border transition-all ${containerStyles} relative overflow-hidden space-y-4`}
    >
      {/* Background ambient gradient glow */}
      <div
        className={`absolute -right-24 -top-24 w-72 h-72 rounded-full blur-3xl opacity-25 pointer-events-none ${
          isLevel4 ? "bg-rose-600" : isLevel3 ? "bg-amber-600" : "bg-yellow-600"
        }`}
      />

      {/* Main Header */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/10 pb-3.5">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-black/60 border border-white/10 shrink-0 mt-0.5">
            {isLevel4 ? (
              <AlertOctagon className="h-6 w-6 text-rose-400 animate-pulse" />
            ) : isLevel3 ? (
              <ShieldAlert className="h-6 w-6 text-amber-400" />
            ) : (
              <AlertTriangle className="h-6 w-6 text-yellow-400" />
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs uppercase tracking-wider border shadow-sm ${topBadgeStyles}`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                {advisory.level_label || `Level ${level} Travel Warning`}
              </span>
              <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                Official Multi-Government Travel Bulletins &bull; {advisory.country}
              </span>
            </div>
            <h3 className="text-base sm:text-lg font-bold text-white tracking-tight mt-1">
              Active Diplomatic Advisories: {advisory.country}
            </h3>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-black/60 p-1 rounded-xl border border-white/10 text-xs self-start md:self-center">
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              activeTab === "all" ? "bg-white/20 text-white font-bold" : "text-zinc-400 hover:text-white"
            }`}
          >
            All Authorities (3)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("india_mea")}
            className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
              activeTab === "india_mea" ? "bg-amber-600/40 text-white font-bold border border-amber-500/40" : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>🇮🇳</span>
            <span>MEA India</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("us_state_dept")}
            className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
              activeTab === "us_state_dept" ? "bg-cyan-600/40 text-white font-bold border border-cyan-500/40" : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>🇺🇸</span>
            <span>US State</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("uk_fcdo")}
            className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
              activeTab === "uk_fcdo" ? "bg-indigo-600/40 text-white font-bold border border-indigo-500/40" : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>🇬🇧</span>
            <span>UK FCDO</span>
          </button>
        </div>
      </div>

      {/* Advisory Cards Grid */}
      <div className="relative z-10 grid grid-cols-1 md:grid-cols-3 gap-4">
        {advisoriesList
          .filter((item) => {
            if (activeTab === "all") return true;
            if (activeTab === "india_mea") return item.country_code === "IN";
            if (activeTab === "us_state_dept") return item.country_code === "US";
            if (activeTab === "uk_fcdo") return item.country_code === "GB";
            return true;
          })
          .map((item, idx) => {
            const badgeClass = getStatusBadge(item.level, item.level_label);
            const isMEA = item.country_code === "IN";

            return (
              <div
                key={item.authority || idx}
                className={`rounded-xl p-4 bg-black/75 border transition flex flex-col justify-between space-y-3 ${
                  isMEA
                    ? "border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.12)] ring-1 ring-amber-500/30"
                    : "border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <div className="space-y-2.5">
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-2 border-b border-white/5 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl shrink-0">{item.flag}</span>
                      <div>
                        <span className="text-[10px] uppercase font-bold tracking-widest text-zinc-400 block">
                          {isMEA ? "Primary National Authority" : "Diplomatic Partner"}
                        </span>
                        <h4 className="text-xs font-bold text-white line-clamp-1">
                          {item.authority}
                        </h4>
                      </div>
                    </div>
                  </div>

                  {/* Stance Badge */}
                  <div>
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${badgeClass}`}
                    >
                      <Shield className="h-3 w-3" />
                      {item.level_label}
                    </span>
                  </div>

                  {/* Summary Text */}
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {item.summary}
                  </p>

                  {/* Consular Helpline & Embassy Contact */}
                  {(item.helpline || item.embassy_contact) && (
                    <div className="p-2.5 rounded-lg bg-zinc-950/80 border border-zinc-900 text-[11px] space-y-1 text-zinc-300">
                      {item.embassy_contact && (
                        <div className="flex items-center gap-1.5 text-zinc-400">
                          <Building2 className="h-3 w-3 text-cyan-400 shrink-0" />
                          <span className="line-clamp-1">{item.embassy_contact}</span>
                        </div>
                      )}
                      {item.helpline && (
                        <div className="flex items-center gap-1.5 font-mono text-amber-300 font-semibold">
                          <PhoneCall className="h-3 w-3 text-amber-400 shrink-0" />
                          <span>{item.helpline}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Card Action Links */}
                <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
                  {item.registration_url && (
                    <a
                      href={item.registration_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 transition"
                    >
                      <span>{isMEA ? "Register on MEA Portal" : "Embassy Registry"}</span>
                      <ChevronRight className="h-3 w-3" />
                    </a>
                  )}

                  {item.official_link && (
                    <a
                      href={item.official_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-zinc-400 hover:text-white flex items-center gap-1 transition"
                      title="View Official Government Advisory Page"
                    >
                      <FileText className="h-3 w-3" />
                      <span>Official Bulletin</span>
                      <ExternalLink className="h-3 w-3 text-zinc-400" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
      </div>
    </aside>
  );
}
