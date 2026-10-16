"use client";

import React, { useState } from "react";
import { Search, ShieldAlert, MapPin, Loader2 } from "lucide-react";

interface NavbarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  currentQuery: string;
}

export default function Navbar({ onSearch, isLoading, currentQuery }: NavbarProps) {
  const [inputValue, setInputValue] = useState(currentQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSearch(inputValue.trim());
    }
  };

  const handleChipClick = (q: string) => {
    setInputValue(q);
    onSearch(q);
  };

  return (
    <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-start">
          <div className="flex items-center gap-2.5">
            <div className="bg-indigo-600/30 p-2 rounded-xl border border-indigo-500/40 text-indigo-400">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                India Travel Safety
                <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60">
                  Fusion Intelligence
                </span>
              </h1>
              <p className="text-xs text-slate-400 hidden sm:block">
                Deterministic Multi-Hazard Scoring & Hotel Ranking
              </p>
            </div>
          </div>
        </div>

        {/* Search Bar */}
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 w-full md:max-w-md bg-slate-800/80 rounded-xl p-1 border border-slate-700/80 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 transition-all shadow-inner"
        >
          <div className="pl-3 text-slate-400">
            <MapPin className="h-4 w-4" />
          </div>
          <input
            type="text"
            id="place-search-input"
            aria-label="Search destination in India"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search destination in India (e.g. Manali, Delhi)..."
            className="w-full bg-transparent px-2 py-1.5 text-sm text-white placeholder-slate-400 focus:outline-none"
          />
          <button
            type="submit"
            disabled={isLoading || !inputValue.trim()}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold tracking-wide transition flex items-center gap-1.5 shrink-0"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            <span>Search</span>
          </button>
        </form>

        {/* Quick Location Chips */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mr-1">Popular:</span>
          {["Manali", "New Delhi", "Rishikesh"].map((loc) => (
            <button
              key={loc}
              type="button"
              onClick={() => handleChipClick(loc)}
              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 text-xs transition whitespace-nowrap"
            >
              {loc}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
