"use client";

import React from "react";
import { LifeBuoy, PhoneCall, ExternalLink, ShieldCheck } from "lucide-react";
import { CuratedAdviceItem } from "@/types";

interface CuratedAdvicePanelProps {
  adviceItems: CuratedAdviceItem[];
}

export default function CuratedAdvicePanel({ adviceItems }: CuratedAdvicePanelProps) {
  if (!adviceItems || adviceItems.length === 0) return null;

  return (
    <section
      aria-label="Official Safety Guidance & Authorities"
      className="bg-slate-900/90 rounded-2xl p-5 border border-slate-800 shadow-xl space-y-4"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30">
            <LifeBuoy className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Official Safety Guidance & Emergency Contacts
            </h3>
            <p className="text-xs text-slate-400">
              Curated tips from NDMA, IMD, and state disaster authorities
            </p>
          </div>
        </div>
        <span className="text-[10px] text-teal-400 font-semibold px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800">
          Curated Catalog
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {adviceItems.map((item, idx) => (
          <div
            key={idx}
            className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
                {item.hazard_name}
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                {item.hazard_type}
              </span>
            </div>

            {/* Actionable Tips */}
            <ul className="text-xs text-slate-300 space-y-1.5 list-disc pl-4 leading-normal">
              {item.tips.map((tip, tIdx) => (
                <li key={tIdx}>{tip}</li>
              ))}
            </ul>

            {/* Official Authorities & Helplines */}
            {item.authorities?.length > 0 && (
              <div className="pt-2 border-t border-slate-700/60 space-y-1.5">
                <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider block">
                  Official Authorities:
                </span>
                <div className="flex flex-wrap gap-2">
                  {item.authorities.map((auth, aIdx) => (
                    <div
                      key={aIdx}
                      className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-slate-900 border border-slate-700/80 text-xs text-slate-200"
                    >
                      <span>{auth.name}</span>
                      {auth.helpline && (
                        <a
                          href={`tel:${auth.helpline.replace(/[^0-9]/g, "")}`}
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-teal-400 hover:text-teal-300 ml-1"
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
                          className="text-slate-400 hover:text-white"
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
        ))}
      </div>
    </section>
  );
}
