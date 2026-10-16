"use client";

import React from "react";
import {
  PhoneCall,
  ExternalLink,
  ShieldCheck,
  Building2,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { CuratedAdviceItem } from "@/types";

interface CuratedAdvicePanelProps {
  adviceItems: CuratedAdviceItem[];
  locationName?: string;
}

export default function CuratedAdvicePanel({ adviceItems, locationName }: CuratedAdvicePanelProps) {
  if (!adviceItems || adviceItems.length === 0) return null;

  return (
    <section
      aria-label="Official Safety Guidance & Authorities"
      className="bg-black rounded-2xl p-5 sm:p-6 border border-zinc-800 shadow-2xl space-y-5"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-inner">
            <Building2 className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Official Safety Guidance & District Administration
            </h3>
            <p className="text-xs text-zinc-400">
              {locationName
                ? `Local emergency dispatch & civil administration for ${locationName.split(",")[0]}`
                : "Curated civic safety notices and verified emergency dispatch lines"}
            </p>
          </div>
        </div>
        <span className="text-[10px] text-cyan-400 font-semibold px-3 py-1 rounded-full bg-cyan-950/70 border border-cyan-800/80 self-start sm:self-center shadow-sm">
          Verified Local Authorities
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {adviceItems.map((item, idx) => {
          const isDistrictAdmin = item.hazard_type === "district_admin";
          const isConflict = item.hazard_type === "conflict";
          const isCrime = item.hazard_type === "crime";

          const accentLine = isDistrictAdmin
            ? "border-t-cyan-400"
            : isConflict
            ? "border-t-rose-500"
            : isCrime
            ? "border-t-amber-500"
            : "border-t-emerald-500";

          return (
            <div
              key={idx}
              className={`p-5 rounded-2xl transition-all duration-300 flex flex-col justify-between space-y-4 border-t-2 ${accentLine} ${
                isDistrictAdmin
                  ? "bg-gradient-to-b from-cyan-950/20 via-zinc-950 to-zinc-950 border-x border-b border-cyan-500/30 shadow-[0_0_25px_rgba(6,182,212,0.1)] ring-1 ring-cyan-500/15 col-span-full"
                  : "bg-gradient-to-b from-zinc-900/40 via-zinc-950 to-zinc-950 border-x border-b border-zinc-800/90 hover:border-zinc-700 shadow-xl"
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2 border-b border-zinc-800/70 pb-2.5">
                  <span className="text-xs font-bold text-white flex items-center gap-2">
                    {isDistrictAdmin ? (
                      <div className="p-1 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                        <Building2 className="h-4 w-4" />
                      </div>
                    ) : (
                      <div className="p-1 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        <ShieldCheck className="h-3.5 w-3.5" />
                      </div>
                    )}
                    <span className="text-sm font-bold tracking-tight">{item.hazard_name}</span>
                  </span>
                  <span
                    className={`text-[10px] uppercase font-mono px-2.5 py-0.5 rounded-full ${
                      isDistrictAdmin
                        ? "bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold"
                        : "bg-zinc-800 text-zinc-300 border border-zinc-700"
                    }`}
                  >
                    {isDistrictAdmin ? "Local Governance" : item.hazard_type}
                  </span>
                </div>

                {/* Actionable Tips */}
                {isDistrictAdmin ? (
                  <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {item.tips.map((tip, tIdx) => (
                      <li
                        key={tIdx}
                        className="flex items-start gap-2.5 p-3 rounded-xl bg-black/60 border border-zinc-800/80 text-xs text-zinc-300 leading-relaxed shadow-sm"
                      >
                        <CheckCircle2 className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <ul className="text-xs text-zinc-300 space-y-2 list-none">
                    {item.tips.map((tip, tIdx) => (
                      <li key={tIdx} className="flex items-start gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 shrink-0 mt-1.5" />
                        <span className="leading-relaxed">{tip}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Official Authorities & Helplines */}
              {item.authorities?.length > 0 && (
                <div className="pt-3 border-t border-zinc-800/80 space-y-2">
                  <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block">
                    {isDistrictAdmin
                      ? "District Administrative & Emergency Hotlines:"
                      : "Official Response Authorities:"}
                  </span>
                  <div className="flex flex-wrap gap-2.5">
                    {item.authorities.map((auth, aIdx) => (
                      <div
                        key={aIdx}
                        className={`flex items-center gap-2.5 px-3.5 py-2 rounded-xl border text-xs shadow-md transition-all duration-200 ${
                          isDistrictAdmin
                            ? "bg-zinc-900/90 border-zinc-700 text-zinc-100 hover:border-cyan-500/60 hover:bg-cyan-950/30"
                            : "bg-zinc-900/70 border-zinc-800 text-zinc-200 hover:border-zinc-700"
                        }`}
                      >
                        <span className="font-semibold">{auth.name}</span>
                        {auth.helpline && (
                          <a
                            href={`tel:${auth.helpline.replace(/[^0-9+]/g, "")}`}
                            className="inline-flex items-center gap-1.5 text-[11px] font-bold text-cyan-400 hover:text-cyan-300 ml-1 font-mono bg-cyan-950/70 px-2 py-0.5 rounded border border-cyan-800/60"
                          >
                            <PhoneCall className="h-3 w-3" />
                            {auth.helpline}
                          </a>
                        )}
                        {auth.url && (
                          <a
                            href={auth.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-zinc-400 hover:text-white p-0.5 rounded"
                            title="Visit official portal"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
