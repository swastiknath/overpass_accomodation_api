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
  ShieldCheck,
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
  if (!advisory) {
    return null;
  }

  const [activeTab, setActiveTab] = useState<"all" | "india_mea" | "us_state_dept" | "uk_fcdo">("all");

  const level = advisory.level || 1;
  const summaryLower = ((advisory.summary || "") + " " + (advisory.level_label || "")).toLowerCase();
  const countryLower = (advisory.country || "").toLowerCase();
  const locLower = (locationName || "").toLowerCase();

  // Rule 1: For any Indian travelling to Pakistan, show the banner in red and mention that it's not going to be safe
  const isPakistan =
    countryLower.includes("pakistan") ||
    locLower.includes("pakistan") ||
    summaryLower.includes("pakistan");

  // Rule 2: High advisory (Level 3 or above, or "avoid non essential travel", or "do not travel", or Pakistan)
  const isAvoidNonEssential =
    summaryLower.includes("avoid non essential") ||
    summaryLower.includes("avoid non-essential") ||
    summaryLower.includes("avoid all travel") ||
    summaryLower.includes("do not travel") ||
    summaryLower.includes("strictly advised against") ||
    summaryLower.includes("not safe") ||
    summaryLower.includes("not going to be safe") ||
    summaryLower.includes("reconsider travel");

  const isHighThreat = isPakistan || level >= 3 || isAvoidNonEssential;

  // Rule 3: Within India, when MEA does not mention anything above domestic measures, show box in GREEN.
  // Except for the specific places mentioned in the MEA (e.g., J&K, Ladakh, Manipur, border areas).
  const isMEAExceptionPlace =
    summaryLower.includes("jammu") ||
    summaryLower.includes("kashmir") ||
    summaryLower.includes("ladakh") ||
    summaryLower.includes("manipur") ||
    summaryLower.includes("border region") ||
    locLower.includes("jammu") ||
    locLower.includes("kashmir") ||
    locLower.includes("srinagar") ||
    locLower.includes("ladakh") ||
    locLower.includes("leh") ||
    locLower.includes("kargil") ||
    locLower.includes("manipur") ||
    locLower.includes("imphal");

  const isDomesticIndia =
    countryLower.includes("india") ||
    advisory.matched_term === "india" ||
    advisory.is_domestic_safe === true;

  const isDomesticGreen =
    isDomesticIndia && !isHighThreat && !isMEAExceptionPlace;

  // If not domestic green, and not high threat, and active_warning is false, return null
  if (!isDomesticGreen && !isHighThreat && !advisory.active_warning && !isMEAExceptionPlace) {
    return null;
  }

  // Determine styling based on the user's exact requirements
  let containerStyles = "border-yellow-600/50 bg-yellow-950/30 text-yellow-100";
  let topBadgeStyles = "bg-yellow-600 text-black border-yellow-400 font-semibold";
  let glowColor = "bg-yellow-600";
  let badgeLabel = advisory.level_label || `Level ${level} Travel Advisory`;

  if (isHighThreat) {
    // Red banner for Level 3+, "avoid non-essential travels", or Pakistan
    containerStyles = "border-rose-600/80 bg-rose-950/45 text-rose-100 shadow-[0_0_35px_rgba(225,29,72,0.30)] ring-1 ring-rose-500/40";
    topBadgeStyles = "bg-rose-600 text-white border-rose-400 font-extrabold";
    glowColor = "bg-rose-600";
    if (isPakistan) {
      badgeLabel = "CRITICAL ADVISORY • NOT SAFE FOR INDIAN NATIONALS";
    } else if (level >= 4) {
      badgeLabel = advisory.level_label || "Level 4: Do Not Travel";
    } else {
      badgeLabel = advisory.level_label || "Level 3: Avoid All Non-Essential Travel";
    }
  } else if (isDomesticGreen) {
    // Green box for within India when MEA mentions standard domestic measures only
    containerStyles = "border-emerald-600/70 bg-emerald-950/35 text-emerald-100 shadow-[0_0_30px_rgba(16,185,129,0.20)] ring-1 ring-emerald-500/30";
    topBadgeStyles = "bg-emerald-600 text-white border-emerald-400 font-bold";
    glowColor = "bg-emerald-600";
    badgeLabel = "DOMESTIC TRAVEL ADVISORY • STANDARD MEASURES (SAFE)";
  } else if (level === 2 || isMEAExceptionPlace) {
    // Amber / Yellow for specific regional guidance in India (e.g. J&K, Manipur) or international Level 2
    containerStyles = "border-amber-600/80 bg-amber-950/40 text-amber-100 shadow-[0_0_30px_rgba(217,119,6,0.20)]";
    topBadgeStyles = "bg-amber-600 text-white border-amber-400 font-bold";
    glowColor = "bg-amber-600";
    badgeLabel = advisory.level_label || "Level 2: Exercise Increased Caution / Route Guidance";
  }

  const advisoriesList: GovTravelAdvisoryItem[] =
    advisory.advisories_list ||
    (advisory.sources
      ? [advisory.sources.india_mea, advisory.sources.us_state_dept, advisory.sources.uk_fcdo].filter(
          Boolean
        ) as GovTravelAdvisoryItem[]
      : []);

  const getStatusBadge = (lvl: number, label: string) => {
    const lbl = (label || "").toLowerCase();
    if (isPakistan || lvl >= 4 || lbl.includes("not safe") || lbl.includes("do not travel") || lbl.includes("against all travel")) {
      return "bg-rose-500/25 text-rose-200 border-rose-500/70 font-bold";
    }
    if (lvl >= 3 || lbl.includes("avoid non essential") || lbl.includes("avoid non-essential")) {
      return "bg-rose-500/20 text-rose-300 border-rose-500/60 font-semibold";
    }
    if (isDomesticGreen) {
      return "bg-emerald-500/20 text-emerald-300 border-emerald-500/50 font-semibold";
    }
    if (lvl === 2) {
      return "bg-amber-500/20 text-amber-300 border-amber-500/60";
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
        className={`absolute -right-24 -top-24 w-72 h-72 rounded-full blur-3xl opacity-25 pointer-events-none ${glowColor}`}
      />

      {/* Main Header */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/10 pb-3.5">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-black/60 border border-white/10 shrink-0 mt-0.5">
            {isHighThreat ? (
              <AlertOctagon className="h-6 w-6 text-rose-400 animate-pulse" />
            ) : isDomesticGreen ? (
              <ShieldCheck className="h-6 w-6 text-emerald-400" />
            ) : (
              <ShieldAlert className="h-6 w-6 text-amber-400" />
            )}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs uppercase tracking-wider border shadow-sm ${topBadgeStyles}`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                {badgeLabel}
              </span>
              <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                {isDomesticGreen
                  ? "National Domestic Safety Protocol • India"
                  : isPakistan
                  ? "High-Risk Diplomatic Security Alert • Pakistan"
                  : `Official Multi-Government Travel Bulletins • ${advisory.country}`}
              </span>
            </div>
            <h3 className="text-base sm:text-lg font-bold text-white tracking-tight mt-1">
              {isPakistan
                ? "Travel to Pakistan: Not Safe for Indian Nationals"
                : isDomesticGreen
                ? `Domestic Travel Status: ${locationName || advisory.country} (Safe / Normal Measures)`
                : `Active Diplomatic Advisories: ${advisory.country}`}
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
            All Authorities ({advisoriesList.length || 3})
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

      {/* Prominent Pakistan Security Warning Notice */}
      {isPakistan && (
        <div className="relative z-10 p-3.5 rounded-xl bg-rose-950/90 border border-rose-500/60 text-xs text-rose-100 flex items-start gap-2.5 shadow-md">
          <AlertOctagon className="h-5 w-5 text-rose-400 shrink-0 mt-0.5 animate-pulse" />
          <div className="space-y-1">
            <strong className="font-bold text-rose-200 block text-sm">
              Urgent Advisory: Travel to Pakistan is not going to be safe for Indian Nationals
            </strong>
            <p className="leading-relaxed text-rose-200/90">
              In view of severe bilateral tensions, active military border friction, high terrorism risks,
              heightened surveillance, and severely restricted consular assistance, Indian passport holders
              are strictly advised that traveling to Pakistan is not safe and strongly advised against.
            </p>
          </div>
        </div>
      )}

      {/* Domestic Green Notice */}
      {isDomesticGreen && (
        <div className="relative z-10 p-3.5 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-xs text-emerald-100 flex items-start gap-2.5 shadow-sm">
          <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <strong className="font-bold text-emerald-200 block text-xs">
              Domestic Travel Measures: Standard / Low Risk
            </strong>
            <p className="leading-relaxed text-emerald-200/90 text-[11px]">
              Destination is within India and the Ministry of External Affairs (MEA) and NDMA indicate standard
              domestic safety measures. No elevated travel advisories or regional security restrictions apply.
            </p>
          </div>
        </div>
      )}

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
                    ? isHighThreat
                      ? "border-rose-500/50 shadow-[0_0_20px_rgba(244,63,94,0.15)] ring-1 ring-rose-500/30"
                      : isDomesticGreen
                      ? "border-emerald-500/40 shadow-[0_0_20px_rgba(16,185,129,0.12)] ring-1 ring-emerald-500/30"
                      : "border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.12)] ring-1 ring-amber-500/30"
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
                      {isPakistan && isMEA
                        ? "Not Safe for Indian Nationals"
                        : item.level_label}
                    </span>
                  </div>

                  {/* Summary Text */}
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {isPakistan && isMEA
                      ? "Travel to Pakistan is not going to be safe for Indian nationals. Bilateral travel is subject to extreme security risks and high diplomatic warnings."
                      : item.summary}
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
