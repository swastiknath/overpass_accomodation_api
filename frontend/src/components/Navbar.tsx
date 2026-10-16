"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, MapPin, Loader2, Globe, X } from "lucide-react";
import { fetchGeocode } from "@/lib/api";
import { GeocodeCandidate } from "@/types";

interface NavbarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  currentQuery: string;
}

export default function Navbar({ onSearch, isLoading, currentQuery }: NavbarProps) {
  const [inputValue, setInputValue] = useState(currentQuery);
  const [suggestions, setSuggestions] = useState<GeocodeCandidate[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync state when currentQuery changes externally
  useEffect(() => {
    setInputValue(currentQuery);
  }, [currentQuery]);

  // Debounced autocomplete fetch on input change
  useEffect(() => {
    const trimmed = inputValue.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsFetching(true);
        const results = await fetchGeocode(trimmed);
        setSuggestions(results || []);
        setIsOpen(true);
        setSelectedIndex(-1);
      } catch (err) {
        console.warn("Autocomplete fetch failed:", err);
      } finally {
        setIsFetching(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [inputValue]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelectCandidate = (candidate: GeocodeCandidate) => {
    const parts = candidate.display_name.split(",");
    const primaryName = parts[0].trim();
    setInputValue(primaryName);
    setIsOpen(false);
    setSuggestions([]);
    onSearch(candidate.display_name);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedIndex >= 0 && suggestions[selectedIndex]) {
      handleSelectCandidate(suggestions[selectedIndex]);
      return;
    }
    if (inputValue.trim()) {
      setIsOpen(false);
      onSearch(inputValue.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const handleClear = () => {
    setInputValue("");
    setSuggestions([]);
    setIsOpen(false);
    inputRef.current?.focus();
  };

  const handleChipClick = (q: string) => {
    setInputValue(q);
    setIsOpen(false);
    onSearch(q);
  };

  return (
    <header className="sticky top-0 z-40 bg-black/50 backdrop-blur-2xl backdrop-saturate-150 border-b border-white/[0.08] shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset,0_8px_32px_0_rgba(0,0,0,0.37)] transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-start">
          <div className="flex flex-col">
            <div className="flex items-center gap-2.5">
              <h1 className="text-base sm:text-[17px] font-semibold tracking-tight text-white/95">
                India Travel Safety
              </h1>
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium tracking-wider uppercase bg-white/[0.06] text-zinc-300 border border-white/[0.10] backdrop-blur-md">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
                Fusion Intelligence
              </span>
            </div>
            <p className="text-[11px] text-zinc-400/90 font-normal tracking-normal hidden sm:block mt-0.5">
              Deterministic Multi-Hazard Scoring & Hotel Ranking
            </p>
          </div>
        </div>

        {/* Search Bar with Autocomplete Dropdown */}
        <div ref={containerRef} className="relative w-full md:max-w-md">
          <form
            onSubmit={handleSubmit}
            role="search"
            className="flex items-center gap-2 w-full bg-white/[0.06] hover:bg-white/[0.08] focus-within:bg-black/75 backdrop-blur-xl rounded-full px-3 py-1.5 border border-white/[0.10] focus-within:border-white/25 focus-within:ring-2 focus-within:ring-white/10 transition-all duration-200 shadow-[inset_0_1px_1px_rgba(255,255,255,0.05)]"
          >
            <div className="pl-1 text-zinc-400 shrink-0">
              <MapPin className="h-3.5 w-3.5" />
            </div>
            <input
              ref={inputRef}
              type="text"
              id="place-search-input"
              role="combobox"
              aria-expanded={isOpen}
              aria-autocomplete="list"
              aria-controls="location-autocomplete-list"
              aria-label="Search destination worldwide"
              value={inputValue}
              onFocus={() => {
                if (suggestions.length > 0) setIsOpen(true);
              }}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search any destination (e.g. Manali, Paris, Tokyo, Kathmandu)..."
              className="w-full bg-transparent px-1.5 py-0.5 text-xs sm:text-sm text-white placeholder-zinc-400/70 focus:outline-none font-normal"
            />
            {inputValue && (
              <button
                type="button"
                onClick={handleClear}
                aria-label="Clear search input"
                className="p-1 text-zinc-400 hover:text-white rounded-full hover:bg-white/10 transition"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-3.5 py-1 bg-white/[0.12] hover:bg-white/[0.20] active:scale-[0.98] border border-white/[0.15] disabled:opacity-40 text-white rounded-full text-xs font-medium tracking-tight transition-all duration-150 flex items-center gap-1.5 shrink-0 shadow-sm backdrop-blur-md"
            >
              {isLoading || isFetching ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Search className="h-3 w-3" />
              )}
              <span>Search</span>
            </button>
          </form>

          {/* Autocomplete Suggestions Menu (Apple Spotlight style) */}
          {isOpen && (suggestions.length > 0 || isFetching) && (
            <div
              id="location-autocomplete-list"
              role="listbox"
              aria-label="Location suggestions"
              className="absolute left-0 right-0 top-full mt-2 bg-zinc-950/85 backdrop-blur-3xl border border-white/[0.12] rounded-2xl shadow-[0_24px_48px_-12px_rgba(0,0,0,0.8),0_0_0_1px_rgba(255,255,255,0.06)] overflow-hidden z-50 divide-y divide-white/[0.06]"
            >
              {isFetching && suggestions.length === 0 ? (
                <div className="flex items-center gap-2.5 px-4 py-3 text-xs text-zinc-400">
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                  <span>Searching global locations...</span>
                </div>
              ) : (
                suggestions.map((c, idx) => {
                  const parts = c.display_name.split(",");
                  const primary = parts[0].trim();
                  const secondary = parts.slice(1, 4).join(",").trim();
                  const isSelected = idx === selectedIndex;

                  return (
                    <div
                      key={`${c.lat}-${c.lon}-${idx}`}
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => handleSelectCandidate(c)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`flex items-center justify-between gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-white/[0.10] border-l-2 border-l-emerald-400 pl-3.5"
                          : "hover:bg-white/[0.06] pl-4 text-zinc-200"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`p-1.5 rounded-lg shrink-0 ${
                            c.is_in_india
                              ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                              : "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                          }`}
                        >
                          {c.is_in_india ? <MapPin className="h-3.5 w-3.5" /> : <Globe className="h-3.5 w-3.5" />}
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-white truncate">{primary}</p>
                          {secondary && <p className="text-[11px] text-zinc-400 truncate">{secondary}</p>}
                        </div>
                      </div>
                      <div className="shrink-0 flex items-center gap-1.5">
                        <span
                          className={`text-[10px] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider ${
                            c.is_in_india
                              ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                              : "bg-white/[0.06] text-zinc-300 border border-white/[0.10]"
                          }`}
                        >
                          {c.country || (c.is_in_india ? "India" : "Global")}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Quick Location Chips */}
        <div className="flex items-center gap-1.5 text-xs text-zinc-400 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider mr-0.5">Popular:</span>
          {["Manali", "Rishikesh", "Kathmandu", "Paris"].map((loc) => (
            <button
              key={loc}
              type="button"
              onClick={() => handleChipClick(loc)}
              className="px-3 py-1 rounded-full bg-white/[0.05] hover:bg-white/[0.12] text-zinc-300 hover:text-white border border-white/[0.08] hover:border-white/[0.18] text-xs font-normal transition-all duration-150 backdrop-blur-sm whitespace-nowrap active:scale-95"
            >
              {loc}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
