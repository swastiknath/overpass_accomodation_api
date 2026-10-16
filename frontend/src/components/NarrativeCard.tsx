"use client";

import React from "react";
import { Sparkles, CheckCircle2, AlertTriangle, AlertCircle, Loader2, BookmarkCheck } from "lucide-react";
import { ExplanationResponse } from "@/types";

interface NarrativeCardProps {
  explanation?: ExplanationResponse | null;
  isLoading: boolean;
  error?: string | null;
}

export default function NarrativeCard({ explanation, isLoading, error }: NarrativeCardProps) {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "verified":
        return {
          label: "Verified Grounded",
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          icon: CheckCircle2,
          desc: "Audit check passed: all cited numbers and drivers match deterministic inputs.",
        };
      case "fallback_template":
        return {
          label: "Fallback Template",
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          icon: AlertTriangle,
          desc: "LLM output did not pass strict grounding verification; serving verified deterministic template.",
        };
      case "unavailable":
      default:
        return {
          label: "LLM Offline / Capped",
          badge: "bg-slate-700/50 text-slate-300 border-slate-600",
          icon: AlertCircle,
          desc: "OpenRouter layer offline or budget capped; serving deterministic template.",
        };
    }
  };

  return (
    <div
      aria-label="AI Generated Narrative"
      className="bg-gradient-to-br from-indigo-950/40 via-slate-900/90 to-slate-900 rounded-2xl p-5 border border-indigo-500/30 shadow-xl space-y-4"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              AI Situational Summary
              <span className="text-[10px] text-slate-400 font-normal">
                (AI-generated summary of the data shown here)
              </span>
            </h3>
          </div>
        </div>

        {/* Verification Status Badge */}
        {explanation && (
          <div className="flex items-center gap-1.5">
            {(() => {
              const statusInfo = getStatusBadge(explanation.narrative_status);
              const StatusIcon = statusInfo.icon;
              return (
                <span
                  id="narrative-verification-badge"
                  title={statusInfo.desc}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${statusInfo.badge}`}
                >
                  <StatusIcon className="h-3.5 w-3.5" />
                  {statusInfo.label}
                </span>
              );
            })()}
          </div>
        )}
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-3 py-4 animate-pulse">
          <div className="h-4 bg-slate-800 rounded w-3/4" />
          <div className="h-3 bg-slate-800/60 rounded w-full" />
          <div className="h-3 bg-slate-800/60 rounded w-5/6" />
          <div className="flex items-center gap-2 text-xs text-indigo-400 font-medium pt-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Verifying claims against deterministic data...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div className="bg-rose-950/40 p-3 rounded-xl border border-rose-800/50 text-xs text-rose-300">
          Could not retrieve narrative explanation: {error}
        </div>
      )}

      {/* Narrative Body */}
      {!isLoading && explanation && (
        <div className="space-y-4 text-xs sm:text-sm text-slate-300 leading-relaxed">
          <div>
            <h4 className="text-sm font-semibold text-white mb-1.5">
              {explanation.narrative.headline}
            </h4>
            <p className="text-slate-300 leading-normal">
              {explanation.narrative.summary}
            </p>
          </div>

          {/* Key Drivers */}
          {explanation.narrative.key_drivers?.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                Grounded Key Drivers:
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {explanation.narrative.key_drivers.map((kd, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-slate-850/80 border border-slate-800 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-white">{kd.factor}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/50">
                        {kd.evidence_ref}
                      </span>
                    </div>
                    <p className="text-slate-400 leading-tight">{kd.plain_language}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Hotel comparison */}
          {explanation.narrative.hotel_comparison && (
            <div className="bg-slate-850/60 p-3 rounded-xl border border-slate-800/80 text-xs">
              <span className="font-semibold text-slate-200 block mb-1">
                Accommodation Risk Context:
              </span>
              <p className="text-slate-400 leading-normal">
                {explanation.narrative.hotel_comparison}
              </p>
            </div>
          )}

          {/* Caveats */}
          {explanation.narrative.caveats?.length > 0 && (
            <div className="text-[11px] text-slate-400 pt-1 space-y-1">
              <span className="font-semibold text-slate-400 block uppercase tracking-wider">
                Audited Caveats & Limitations:
              </span>
              <ul className="list-disc pl-4 space-y-0.5">
                {explanation.narrative.caveats.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
