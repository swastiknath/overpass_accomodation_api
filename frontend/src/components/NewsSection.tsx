"use client";

import React, { useState } from "react";
import { Newspaper, ExternalLink, Globe, Calendar, Scale, ChevronLeft, ChevronRight, Megaphone } from "lucide-react";
import { NewsArticle } from "@/types";

interface NewsSectionProps {
  articles: NewsArticle[];
  locationName: string;
}

export default function NewsSection({ articles, locationName }: NewsSectionProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const pageSize = 6;

  if (!articles || articles.length === 0) {
    return null;
  }

  // Detect and include protest & civic actions in category list if present in articles
  const categories = Array.from(
    new Set(
      articles.map((a) => {
        const text = `${a.title} ${a.snippet || ""} ${a.category || ""}`.toLowerCase();
        if (/protest|rally|demonstrat|strike|march|unrest|blockade|sit-in|bandh/.test(text)) {
          return "protests & unrest";
        }
        return a.category ? a.category.replace("_", " ").toLowerCase() : "general";
      })
    )
  );

  const filteredArticles = articles.filter((a) => {
    if (selectedCategory === "all") return true;
    const text = `${a.title} ${a.snippet || ""} ${a.category || ""}`.toLowerCase();
    const isProtest = /protest|rally|demonstrat|strike|march|unrest|blockade|sit-in|bandh/.test(text);
    if (selectedCategory === "protests & unrest") return isProtest;
    const cat = (a.category || "general").replace("_", " ").toLowerCase();
    return cat === selectedCategory;
  });

  const totalPages = Math.max(1, Math.ceil(filteredArticles.length / pageSize));
  const safePage = Math.min(Math.max(1, currentPage), totalPages);
  const displayedArticles = filteredArticles.slice((safePage - 1) * pageSize, safePage * pageSize);

  const getCategoryBadgeClass = (category?: string) => {
    const cat = (category || "").toLowerCase();
    if (cat.includes("socio") || cat.includes("political") || cat.includes("govern")) {
      return "bg-amber-950/60 text-amber-300 border-amber-800/50";
    }
    if (cat.includes("security") || cat.includes("military") || cat.includes("conflict")) {
      return "bg-purple-950/60 text-purple-300 border-purple-800/50";
    }
    if (cat.includes("unrest") || cat.includes("protest") || cat.includes("crime") || cat.includes("riot")) {
      return "bg-rose-950/60 text-rose-300 border-rose-800/50";
    }
    if (cat.includes("weather") || cat.includes("flood") || cat.includes("disaster")) {
      return "bg-cyan-950/60 text-cyan-300 border-cyan-800/50";
    }
    return "bg-zinc-900 text-zinc-300 border-zinc-700/50";
  };

  return (
    <section
      aria-label="Relevant News and Situation Reports"
      className="bg-black rounded-2xl p-5 border border-zinc-800 shadow-2xl space-y-4"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-800/90 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Scale className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white tracking-tight">
                Socio-Political & Regional Safety News
              </h3>
              <span className="text-xs bg-zinc-900 text-zinc-300 font-mono px-2 py-0.5 rounded-full border border-zinc-800">
                {articles.length} verified
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Live sourced socio-political developments and situation awareness for{" "}
              <strong className="text-zinc-200">{locationName}</strong>
            </p>
          </div>
        </div>

        {/* Category Filter Pills */}
        {categories.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <button
              onClick={() => {
                setSelectedCategory("all");
                setCurrentPage(1);
              }}
              className={`px-2.5 py-1 rounded-lg font-medium transition ${
                selectedCategory === "all"
                  ? "bg-zinc-200 text-black font-bold shadow-sm"
                  : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
              }`}
            >
              All
            </button>
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => {
                  setSelectedCategory(c);
                  setCurrentPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg capitalize font-medium transition ${
                  selectedCategory === c
                    ? "bg-zinc-200 text-black font-bold shadow-sm"
                    : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Articles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {displayedArticles.map((article, idx) => {
          const categoryTag = article.category
            ? article.category.replace("_", " ")
            : "Socio-Political";

          return (
            <article
              key={`${article.url}-${idx}`}
              className="flex flex-col justify-between bg-zinc-950 hover:bg-zinc-900/90 rounded-xl p-4 border border-zinc-800/80 hover:border-zinc-700 transition duration-200 group shadow-lg"
            >
              <div className="space-y-2.5">
                {/* Meta Header: Source & Date */}
                <div className="flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-zinc-300">
                    <Globe className="h-3.5 w-3.5 text-cyan-400 shrink-0" />
                    <span className="truncate max-w-[140px] text-zinc-200">
                      {article.source || "News Wire"}
                    </span>
                  </div>

                  {article.seendate && (
                    <span className="text-[11px] text-zinc-400 flex items-center gap-1 shrink-0">
                      <Calendar className="h-3 w-3" />
                      {article.seendate.length > 16
                        ? article.seendate.slice(0, 16)
                        : article.seendate}
                    </span>
                  )}
                </div>

                {/* Title */}
                <h4 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition line-clamp-2 leading-snug">
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="focus:outline-none"
                  >
                    {article.title}
                  </a>
                </h4>

                {/* Snippet */}
                {article.snippet && (
                  <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                    {article.snippet}
                  </p>
                )}
              </div>

              {/* Bottom Footer: Category & Direct External Link */}
              <div className="mt-3 pt-3 border-t border-zinc-800/80 flex items-center justify-between gap-2">
                <span
                  className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded border ${getCategoryBadgeClass(
                    article.category
                  )}`}
                >
                  {categoryTag}
                </span>

                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300 group-hover:underline"
                >
                  <span>Read Report</span>
                  <ExternalLink className="h-3 w-3 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </a>
              </div>
            </article>
          );
        })}
      </div>

      {/* Numbered Pagination Controls */}
      {totalPages > 1 && (
        <div className="pt-3 border-t border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <span className="text-zinc-400 text-[11px]">
            Showing <strong className="text-white font-mono font-medium">{(safePage - 1) * pageSize + 1}</strong> to{" "}
            <strong className="text-white font-mono font-medium">{Math.min(safePage * pageSize, filteredArticles.length)}</strong> of{" "}
            <strong className="text-white font-mono font-medium">{filteredArticles.length}</strong> news reports
          </span>

          <div className="flex items-center gap-1.5 self-center sm:self-auto">
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
              className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-30 disabled:pointer-events-none transition"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((pg) => (
              <button
                key={pg}
                type="button"
                onClick={() => setCurrentPage(pg)}
                className={`min-w-[28px] h-7 px-2 rounded-lg text-[11px] font-mono font-semibold transition ${
                  safePage === pg
                    ? "bg-zinc-200 text-black font-bold shadow-sm"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800/60 border border-transparent"
                }`}
              >
                {pg}
              </button>
            ))}

            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
              className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-30 disabled:pointer-events-none transition"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
