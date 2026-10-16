"use client";

import React from "react";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Loader2,
  BookmarkCheck,
  Activity,
  ShieldCheck,
  ShieldAlert,
  Shield,
  Building2,
  Newspaper,
  Compass,
} from "lucide-react";
import { ExplanationResponse } from "@/types";

interface NarrativeCardProps {
  explanation?: ExplanationResponse | null;
  isLoading: boolean;
  error?: string | null;
}

// Regex to capture key terms across agencies, telemetry metrics, scores, risk bands, and findings
const KEYWORD_PATTERN = new RegExp(
  "(" +
    [
      // Specific Agencies and Telemetry Feeds
      "NASA FIRMS VIIRS",
      "NASA FIRMS",
      "USGS",
      "Open-Meteo",
      "GDACS",
      "ACLED",
      "UNODC_CRIME",
      "UNODC",
      "MEA India Alert",
      "MEA India",
      "Home Front Command",
      "Inception Mercury Decide",
      "inception/mercury-decide-20260930",
      "inception/mercury-decide",
      "OpenRouter",
      "Bhuvan",

      // Specific Telemetry Findings
      "zero active fire hotspots",
      "zero earthquakes",
      "active precipitation",
      "stable regional river and flood basin levels",
      "stable regional river",
      "predictable civilian security",
      "regular commercial activity and public transit",

      // Risk Bands with quotes
      "'Elevated Risk'",
      "'Moderate Risk'",
      "'Low Risk'",
      "'High Risk'",
      "'Severe Risk'",

      // Risk Bands without quotes
      "Elevated Risk",
      "Moderate Risk",
      "Low Risk",
      "High Risk",
      "Severe Risk",

      // Decisions
      "\\bCAUTION\\b",
      "\\bSAFE\\b",
      "\\bUNSAFE\\b",

      // Metrics, Quantities, Distances & Scores
      "\\b\\d{1,3}/100\\b",
      "\\b\\d+(?:\\.\\d+)?%\\b",
      "\\b\\d+(?:\\.\\d+)?\\s*km\\b",
      "\\bM\\d+(?:\\.\\d+)?\\b",
    ].join("|") +
  ")",
  "gi"
);

function HighlightedText({ text }: { text: string }) {
  if (!text) return null;

  const parts = text.split(KEYWORD_PATTERN);

  return (
    <>
      {parts.map((part, idx) => {
        if (!part) return null;

        const lower = part.toLowerCase();

        // 1. Telemetry Agencies & System Feeds (Crisp cyan font highlight without bulky boxes)
        if (
          lower.includes("nasa") ||
          lower.includes("usgs") ||
          lower.includes("open-meteo") ||
          lower.includes("gdacs") ||
          lower.includes("acled") ||
          lower.includes("unodc") ||
          lower.includes("mea india") ||
          lower.includes("home front command") ||
          lower.includes("mercury-decide") ||
          lower.includes("openrouter") ||
          lower.includes("bhuvan")
        ) {
          return (
            <span key={idx} className="font-semibold text-cyan-300">
              {part}
            </span>
          );
        }

        // 2. Scores, Percentages, and Distances (Glowing amber mono highlight)
        if (
          /^\d{1,3}\/100$/.test(part) ||
          /^\d+(\.\d+)?%$/.test(part) ||
          /^\d+(\.\d+)?\s*km$/i.test(part) ||
          /^m\d+(\.\d+)?$/i.test(part)
        ) {
          return (
            <span key={idx} className="font-mono font-bold text-amber-300">
              {part}
            </span>
          );
        }

        // 3. Risk Bands & Decisions (Colored status highlights)
        if (
          lower.includes("caution") ||
          lower.includes("elevated") ||
          lower.includes("moderate") ||
          lower.includes("safe") ||
          lower.includes("high") ||
          lower.includes("severe") ||
          lower.includes("unsafe")
        ) {
          const isSafeOrLow = lower.includes("safe") || lower.includes("low");
          const isCautionOrElevated = lower.includes("caution") || lower.includes("elevated") || lower.includes("moderate");

          return (
            <span
              key={idx}
              className={`font-semibold ${
                isSafeOrLow
                  ? "text-emerald-400"
                  : isCautionOrElevated
                  ? "text-amber-400"
                  : "text-rose-400"
              }`}
            >
              {part}
            </span>
          );
        }

        // 4. Positive Telemetry Findings
        if (
          lower.includes("zero active fire") ||
          lower.includes("zero earthquake") ||
          lower.includes("stable regional river") ||
          lower.includes("predictable civilian security") ||
          lower.includes("regular commercial activity")
        ) {
          return (
            <span key={idx} className="font-medium text-emerald-300">
              {part}
            </span>
          );
        }

        // 5. Active Precipitation Finding
        if (lower.includes("active precipitation")) {
          return (
            <span key={idx} className="font-medium text-cyan-300">
              {part}
            </span>
          );
        }

        return <React.Fragment key={idx}>{part}</React.Fragment>;
      })}
    </>
  );
}

interface TelemetryCardInfo {
  title: string;
  category: "evaluation" | "geohazard" | "security" | "infrastructure" | "general";
  icon: React.ComponentType<{ className?: string }>;
  accentColor: string;
  badgeLabel: string;
  badgeColor: string;
  body: string;
}

function parseParagraphToCard(paragraph: string): TelemetryCardInfo {
  const p = paragraph.trim();

  if (p.startsWith("Geo-Hazard & Environmental Telemetry:") || p.includes("NASA FIRMS") || p.includes("USGS")) {
    const cleanBody = p.replace(/^Geo-Hazard & Environmental Telemetry:\s*/i, "");
    return {
      title: "Geo-Hazard & Satellite Telemetry",
      category: "geohazard",
      icon: Activity,
      accentColor: "border-l-2 border-l-cyan-400",
      badgeLabel: "Live Satellite Feeds",
      badgeColor: "text-cyan-400 bg-cyan-950/60 border-cyan-800/60",
      body: cleanBody,
    };
  }

  if (p.startsWith("Security, Civil Stability & Law Enforcement:") || p.includes("ACLED")) {
    const cleanBody = p.replace(/^Security, Civil Stability & Law Enforcement:\s*/i, "");
    return {
      title: "Security, Civil Stability & Law Enforcement",
      category: "security",
      icon: ShieldCheck,
      accentColor: "border-l-2 border-l-indigo-400",
      badgeLabel: "Civil Security",
      badgeColor: "text-indigo-400 bg-indigo-950/60 border-indigo-800/60",
      body: cleanBody,
    };
  }

  if (
    p.startsWith("Accommodation Risk & Emergency Infrastructure:") ||
    p.includes("emergency facilities") ||
    p.includes("healthcare centers")
  ) {
    const cleanBody = p.replace(/^Accommodation Risk & Emergency Infrastructure:\s*/i, "");
    return {
      title: "Accommodation Risk & Critical Infrastructure",
      category: "infrastructure",
      icon: Building2,
      accentColor: "border-l-2 border-l-teal-400",
      badgeLabel: "Civic Infrastructure",
      badgeColor: "text-teal-400 bg-teal-950/60 border-teal-800/60",
      body: cleanBody,
    };
  }

  let cleanBody = p;
  // Cleanly strip any prepended AI decision summaries or partial confidence artifacts
  cleanBody = cleanBody.replace(/^AI Travel Decision:\s*[A-Z_]+\s*\([^)]*\)\.?\s*/i, "");
  cleanBody = cleanBody.replace(/^AI Travel Decision:[^.]*?\.\s*/i, "");
  cleanBody = cleanBody.replace(/^.*?\b\d+(?:\.\d+)?%\s*confidence\s+via\s+[^)]+\)\.?\s*/i, "");
  cleanBody = cleanBody.replace(/^\s*\d+(?:\.\d+)?%\s*confidence\s+via\s+[^)]+\)\.?\s*/i, "");
  cleanBody = cleanBody.replace(/^\)\.?\s*/, "");

  return {
    title: "Composite Safety & Primary Risk Assessment",
    category: "evaluation",
    icon: Sparkles,
    accentColor: "border-l-2 border-l-amber-400",
    badgeLabel: "Deterministic Evaluation",
    badgeColor: "text-amber-400 bg-amber-950/60 border-amber-800/60",
    body: cleanBody,
  };
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

  // Headline extraction for bracketed confidence prefixes like [SAFE · 80.0% AI Confidence]
  const headlineMatch = explanation?.narrative.headline.match(/^\[(.*?)\]\s*(.*)$/);
  const headlineBadge = headlineMatch ? headlineMatch[1] : null;
  const cleanHeadline = headlineMatch ? headlineMatch[2] : explanation?.narrative.headline;

  // Split summary into structured paragraphs
  const summaryParagraphs = explanation?.narrative.summary
    ? explanation.narrative.summary.split(/\n\s*\n/).filter((p) => p.trim().length > 0)
    : [];

  return (
    <div
      aria-label="AI Generated Narrative"
      className="bg-black rounded-2xl p-5 sm:p-6 border border-zinc-800 shadow-2xl space-y-5"
    >
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-zinc-900 text-zinc-300 border border-zinc-700/60 shadow-inner">
            <Sparkles className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              AI Situational Summary
              <span className="text-[11px] text-zinc-400 font-normal">
                (AI-generated summary of the data shown here)
              </span>
            </h3>
          </div>
        </div>

        {/* Verification Status Badge */}
        {explanation && (
          <div className="flex items-center gap-1.5 self-start sm:self-center">
            {(() => {
              const statusInfo = getStatusBadge(explanation.narrative_status);
              const StatusIcon = statusInfo.icon;
              return (
                <span
                  id="narrative-verification-badge"
                  title={statusInfo.desc}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border shadow-sm ${statusInfo.badge}`}
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
        <div className="space-y-3.5 py-6 animate-pulse">
          <div className="h-4 bg-zinc-800 rounded w-3/4" />
          <div className="h-3 bg-zinc-850 rounded w-full" />
          <div className="h-3 bg-zinc-850 rounded w-5/6" />
          <div className="flex items-center gap-2 text-xs text-zinc-400 font-medium pt-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-400" />
            <span>Verifying claims against deterministic data...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div className="bg-rose-950/40 p-4 rounded-xl border border-rose-800/50 text-xs text-rose-300">
          Could not retrieve narrative explanation: {error}
        </div>
      )}

      {/* Narrative Body */}
      {!isLoading && explanation && (
        <div className="space-y-5">
          {/* Active AI Travel Decision Banner */}
          {explanation.decision && (
            <div
              id="ai-travel-decision-banner"
              className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg transition-all ${
                explanation.decision.choice === "safe"
                  ? "bg-gradient-to-r from-emerald-950/40 via-zinc-950 to-zinc-950 border-emerald-500/40 shadow-[0_0_20px_rgba(16,185,129,0.08)]"
                  : explanation.decision.choice === "caution"
                  ? "bg-gradient-to-r from-amber-950/40 via-zinc-950 to-zinc-950 border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.08)]"
                  : "bg-gradient-to-r from-rose-950/40 via-zinc-950 to-zinc-950 border-rose-500/40 shadow-[0_0_20px_rgba(244,63,94,0.08)]"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`p-2 rounded-xl border shrink-0 ${
                    explanation.decision.choice === "safe"
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      : explanation.decision.choice === "caution"
                      ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                      : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                  }`}
                >
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <div
                    className={`text-xs font-extrabold uppercase tracking-wider ${
                      explanation.decision.choice === "safe"
                        ? "text-emerald-300"
                        : explanation.decision.choice === "caution"
                        ? "text-amber-300"
                        : "text-rose-300"
                    }`}
                  >
                    AI Travel Decision: {explanation.decision.choice}
                  </div>
                  <div className="text-[11px] text-zinc-400">
                    Confidence:{" "}
                    <strong className="text-zinc-200">
                      {Math.round(explanation.decision.confidence * 100)}% certainty
                    </strong>{" "}
                    • Grounded via Inception Mercury Decide
                  </div>
                </div>
              </div>
              <span className="text-[10px] font-mono bg-black/80 px-2.5 py-1 rounded-md border border-zinc-700/80 text-zinc-300 shrink-0 self-start sm:self-center">
                {explanation.decision.model}
              </span>
            </div>
          )}

          {/* Headline with Status Badge */}
          <div className="space-y-1.5 pt-1">
            {headlineBadge && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  <Sparkles className="h-3 w-3 text-amber-400" />
                  {headlineBadge}
                </span>
              </div>
            )}
            <h4 className="text-base sm:text-lg font-bold text-white tracking-tight leading-snug">
              {cleanHeadline}
            </h4>
          </div>

          {/* Telemetry Sections (Clean vertical flow with ample width) */}
          <div className="space-y-3">
            {summaryParagraphs.map((paragraph, pIdx) => {
              const cardInfo = parseParagraphToCard(paragraph);
              const CardIcon = cardInfo.icon;

              return (
                <div
                  key={pIdx}
                  className={`p-4 rounded-xl bg-zinc-950/80 border border-zinc-800/80 ${cardInfo.accentColor} space-y-2 shadow-md hover:border-zinc-700/90 transition-all duration-200`}
                >
                  <div className="flex items-center justify-between gap-2 border-b border-zinc-900 pb-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300">
                        <CardIcon className="h-3.5 w-3.5" />
                      </div>
                      <span className="text-xs font-bold text-white tracking-tight">
                        {cardInfo.title}
                      </span>
                    </div>
                    <span
                      className={`text-[9px] uppercase font-mono font-semibold px-2 py-0.5 rounded border ${cardInfo.badgeColor}`}
                    >
                      {cardInfo.badgeLabel}
                    </span>
                  </div>

                  <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    <HighlightedText text={cardInfo.body} />
                  </p>
                </div>
              );
            })}
          </div>

          {/* Grounded Key Drivers (Single-column layout with full breathing room) */}
          {explanation.narrative.key_drivers?.length > 0 && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-2">
                  <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
                  Grounded Key Drivers
                </span>
                <span className="text-[10px] text-zinc-400 font-mono">
                  {explanation.narrative.key_drivers.length} Verified Evidence Signals
                </span>
              </div>

              <div className="space-y-2.5">
                {explanation.narrative.key_drivers.map((kd, idx) => {
                  const pctMatch = kd.plain_language.match(/(\d+(?:\.\d+)?%)/);
                  const riskWeight = pctMatch ? pctMatch[1] : null;

                  const isAdvisoryOrConflict =
                    kd.evidence_ref.includes("advisory") ||
                    kd.evidence_ref.includes("conflict") ||
                    kd.factor.toLowerCase().includes("alert");
                  const isCrime = kd.evidence_ref.includes("crime");
                  const isNews =
                    kd.evidence_ref.includes("news") || kd.factor.toLowerCase().includes("news");

                  const theme = isAdvisoryOrConflict
                    ? {
                        border: "border-l-rose-500 hover:border-rose-500/60",
                        badge: "bg-rose-950 text-rose-300 border-rose-800/80",
                        icon: ShieldAlert,
                        iconColor: "text-rose-400 bg-rose-500/10 border-rose-500/20",
                        tag: "Advisory / Conflict",
                      }
                    : isCrime
                    ? {
                        border: "border-l-amber-500 hover:border-amber-500/60",
                        badge: "bg-amber-950 text-amber-300 border-amber-800/80",
                        icon: Shield,
                        iconColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
                        tag: "District Baseline",
                      }
                    : isNews
                    ? {
                        border: "border-l-blue-500 hover:border-blue-500/60",
                        badge: "bg-blue-950 text-blue-300 border-blue-800/80",
                        icon: Newspaper,
                        iconColor: "text-blue-400 bg-blue-500/10 border-blue-500/20",
                        tag: "Live Reports",
                      }
                    : {
                        border: "border-l-cyan-500 hover:border-cyan-500/60",
                        badge: "bg-cyan-950 text-cyan-300 border-cyan-800/80",
                        icon: Activity,
                        iconColor: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
                        tag: "Telemetry Signal",
                      };

                  const DriverIcon = theme.icon;

                  return (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl bg-zinc-950/90 border border-zinc-800/90 ${theme.border} border-l-2 text-xs flex flex-col justify-between space-y-2.5 transition-all duration-200 shadow-md group`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <div className={`p-1 rounded-md border ${theme.iconColor}`}>
                              <DriverIcon className="h-3 w-3" />
                            </div>
                            <span className="text-[10px] uppercase font-mono font-semibold text-zinc-400">
                              {theme.tag}
                            </span>
                          </div>
                          {riskWeight && (
                            <span
                              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border shadow-sm ${theme.badge}`}
                            >
                              {riskWeight} Risk
                            </span>
                          )}
                        </div>

                        <h5 className="font-bold text-white text-xs leading-snug group-hover:text-zinc-100 transition-colors">
                          {kd.factor}
                        </h5>

                        <p className="text-zinc-300 text-xs leading-relaxed">
                          <HighlightedText text={kd.plain_language} />
                        </p>
                      </div>

                      <div className="pt-2 border-t border-zinc-900 flex items-center justify-between">
                        <span className="text-[10px] font-mono text-zinc-400 bg-zinc-900/90 px-2 py-0.5 rounded border border-zinc-800 flex items-center gap-1.5 truncate max-w-full">
                          <BookmarkCheck className="h-3 w-3 text-zinc-500 shrink-0" />
                          <span className="truncate">{kd.evidence_ref}</span>
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Accommodation Risk Context */}
          {explanation.narrative.hotel_comparison && (
            <div className="bg-gradient-to-r from-zinc-950 via-zinc-900/60 to-zinc-950 p-4 rounded-xl border border-zinc-800 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shrink-0 mt-0.5">
                  <Building2 className="h-4 w-4" />
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      Accommodation Risk & Ranking Context
                    </span>
                    <span className="text-[10px] font-semibold text-cyan-400 bg-cyan-950/70 border border-cyan-800/80 px-2 py-0.5 rounded-full">
                      Verified Policy
                    </span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    <HighlightedText text={explanation.narrative.hotel_comparison} />
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Caveats */}
          {explanation.narrative.caveats?.length > 0 && (
            <div className="text-[11px] text-zinc-400 pt-1 space-y-1 bg-zinc-950/60 p-3.5 rounded-xl border border-zinc-800/80">
              <span className="font-semibold text-zinc-300 block uppercase tracking-wider flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 text-amber-400" />
                Audited Caveats & Limitations
              </span>
              <ul className="list-disc pl-4 space-y-0.5 text-zinc-400">
                {explanation.narrative.caveats.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Model Citation Footer */}
          <div className="pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] text-zinc-400">
            <span>
              Engine:{" "}
              <strong className="text-zinc-300 font-mono">
                {explanation.decision?.model || explanation.model_used || "OpenRouter"}
              </strong>
            </span>
            {explanation.cached && (
              <span className="bg-zinc-900 px-2 py-0.5 rounded text-[9px] text-zinc-400 border border-zinc-800 font-mono">
                Cached Result
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
