"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertOctagon, Loader2 } from "lucide-react";

import Navbar from "@/components/Navbar";
import DemoBanner from "@/components/DemoBanner";
import ScorePanel from "@/components/ScorePanel";
import ExplanationPanel from "@/components/ExplanationPanel";
import NarrativeCard from "@/components/NarrativeCard";
import CuratedAdvicePanel from "@/components/CuratedAdvicePanel";
import HotelsList from "@/components/HotelsList";
import NewsSection from "@/components/NewsSection";
import DisambiguationModal from "@/components/DisambiguationModal";
import ExportButtons from "@/components/ExportButtons";
import WeatherAirQualityPanel from "@/components/WeatherAirQualityPanel";
import TravelAdvisoriesBanner from "@/components/TravelAdvisoriesBanner";
import HistoricalDataViewer from "@/components/HistoricalDataViewer";
import CrimeStatisticsVisualizer from "@/components/CrimeStatisticsVisualizer";
import RiskTelemetryVisualizer from "@/components/RiskTelemetryVisualizer";
import SearchLoadingAnimation from "@/components/SearchLoadingAnimation";
import Footer from "@/components/Footer";
import dynamic from "next/dynamic";

const MapLibreView = dynamic(() => import("@/components/MapLibreView"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[450px] lg:h-[520px] rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-xs text-slate-400">
      Loading Interactive Hazard & Hotel Map...
    </div>
  ),
});

import { fetchSearchReport, fetchExplanation } from "@/lib/api";
import { GeocodeCandidate, SearchReport, ExplanationResponse } from "@/types";

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlQuery = searchParams.get("q") || "Manali";
  const urlAlpha = parseFloat(searchParams.get("alpha") || "0.7");

  const [currentQuery, setCurrentQuery] = useState(urlQuery);
  const [alpha, setAlpha] = useState(urlAlpha);
  const [selectedHotelId, setSelectedHotelId] = useState<string | null>(null);

  useEffect(() => {
    if (urlQuery && urlQuery !== currentQuery) {
      setCurrentQuery(urlQuery);
    }
  }, [urlQuery]);

  useEffect(() => {
    if (!isNaN(urlAlpha) && urlAlpha !== alpha) {
      setAlpha(urlAlpha);
    }
  }, [urlAlpha]);

  // Sync state to URL without full page reload
  const updateUrlState = (newQuery: string, newAlpha: number) => {
    const params = new URLSearchParams();
    params.set("q", newQuery);
    params.set("alpha", newAlpha.toString());
    router.push(`/?${params.toString()}`);
  };

  const handleSearch = (newQuery: string) => {
    setCurrentQuery(newQuery);
    setSelectedHotelId(null);
    updateUrlState(newQuery, alpha);
  };

  const handleAlphaChange = (newAlpha: number) => {
    setAlpha(newAlpha);
    updateUrlState(currentQuery, newAlpha);
  };

  // 1. Fetch Deterministic Report immediately
  const {
    data: report,
    isLoading: reportLoading,
    error: reportError,
    refetch: refetchReport,
  } = useQuery<SearchReport, Error>({
    queryKey: ["search-report", currentQuery, alpha],
    queryFn: () =>
      fetchSearchReport({
        q: currentQuery,
        alpha: alpha,
        radius_km: 5.0,
        max_hotels: 30,
      }),
  });

  // 2. Fetch AI Explanation progressively once deterministic report_id is available
  const reportId = report?.report_id;
  const {
    data: explanation,
    isLoading: explanationLoading,
    error: explanationError,
  } = useQuery<ExplanationResponse, Error>({
    queryKey: ["explanation", reportId],
    queryFn: () => fetchExplanation(reportId!),
    enabled: !!reportId,
  });

  const handleSelectDisambiguation = (candidate: GeocodeCandidate) => {
    handleSearch(candidate.display_name.split(",")[0]);
  };

  const isDemo = report ? Boolean(report.demo) : false;

  return (
    <div className="flex flex-col min-h-screen bg-black text-zinc-100 font-sans">
      <DemoBanner show={isDemo} />
      <Navbar
        onSearch={handleSearch}
        isLoading={reportLoading}
        currentQuery={currentQuery}
      />

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full space-y-6">
        {/* Disambiguation if multiple candidates were found */}
        {report?.disambiguation_candidates && (
          <DisambiguationModal
            candidates={report.disambiguation_candidates}
            onSelectCandidate={handleSelectDisambiguation}
          />
        )}

        {/* Global Error Banner */}
        {reportError && (
          <div
            role="alert"
            className="p-4 rounded-2xl bg-rose-950/70 border border-rose-500/40 text-rose-200 flex items-start gap-3 shadow-lg"
          >
            <AlertOctagon className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white">Coverage or Query Error</h3>
              <p className="text-xs leading-normal">{reportError.message}</p>
            </div>
          </div>
        )}

        {/* Report Loading State */}
        {reportLoading && (
          <div className="py-6">
            <SearchLoadingAnimation query={currentQuery} />
          </div>
        )}

        {/* Report Content - Progressive Render */}
        {report && (
          <div className="space-y-6">
            {/* Top Toolbar: Destination Title & Export Buttons */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-zinc-950 p-4 rounded-2xl border border-zinc-800 shadow-xl">
              <div>
                <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-widest block">
                  Ground Safety & Hotel Intelligence
                </span>
                <h2 className="text-xl font-extrabold text-white tracking-tight">
                  {report.location.display_name}
                </h2>
              </div>
              <ExportButtons report={report} />
            </div>

            {/* Official International Travel Advisory Alert Banner */}
            {report.travel_advisories && (
              <TravelAdvisoriesBanner
                advisory={report.travel_advisories}
                locationName={report.location.display_name}
              />
            )}

            {/* Score Panel */}
            <ScorePanel report={report} />

            {/* Row 1: Geospatial Intelligence & AI Executive Synthesis (Balanced Left & Right Columns) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div className="lg:col-span-7 space-y-6">
                <MapLibreView
                  report={report}
                  selectedHotelId={selectedHotelId}
                  onSelectHotel={setSelectedHotelId}
                />
                <ExplanationPanel report={report} />
              </div>
              <div className="lg:col-span-5 space-y-6">
                <NarrativeCard
                  explanation={explanation}
                  isLoading={explanationLoading}
                  error={explanationError?.message}
                />
              </div>
            </div>

            {/* Row 2: Multi-Hazard Live Telemetry & Historical Longitudinal Retrospectives */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div className="lg:col-span-6">
                <RiskTelemetryVisualizer report={report} />
              </div>
              <div className="lg:col-span-6">
                <HistoricalDataViewer report={report} />
              </div>
            </div>

            {/* Row 3: 5-Year Crime Statistics & Real-Time Crime Telemetry (Full Width Panoramic Audit) */}
            <CrimeStatisticsVisualizer report={report} />

            {/* Official Safety Guidance & Local District Administration (Shifted Down Full Width) */}
            <CuratedAdvicePanel
              adviceItems={explanation?.curated_advice || []}
              locationName={report.location.display_name}
            />

            {/* 15-Day Weather & Air Quality Forecaster */}
            {report.weather_and_air_quality && (
              <WeatherAirQualityPanel
                weatherData={report.weather_and_air_quality}
                locationName={report.location.display_name.split(",")[0]}
              />
            )}

            {/* Relevant News Section */}
            {report.news_articles && report.news_articles.length > 0 && (
              <NewsSection
                articles={report.news_articles}
                locationName={report.location.display_name.split(",")[0]}
              />
            )}

            {/* Hotels Ranking Section */}
            <HotelsList
              hotels={report.hotels_ranked}
              sameAreaWarning={report.same_area_warning}
              alpha={alpha}
              onAlphaChange={handleAlphaChange}
              selectedHotelId={selectedHotelId}
              onSelectHotel={setSelectedHotelId}
              radiusExpanded={report.radius_expanded}
              originalRadiusKm={report.original_radius_km}
              effectiveRadiusKm={report.effective_radius_km}
              radiusExpansionMessage={report.radius_expansion_message}
            />
          </div>
        )}
      </main>

      <Footer
        configVersion={report?.config_version}
        reportTimestamp={report?.timestamp}
        disclaimer={report?.disclaimer}
      />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400 text-xs">
          Loading India Travel Safety Intelligence...
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
