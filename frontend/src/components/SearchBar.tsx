import { useState, useRef, useEffect } from "react";
import type { NameSearchMatch } from "../types";

interface Props {
  onSearchNif: (nif: string) => void;
  onSearchName: (name: string) => void;
  nameResults: NameSearchMatch[];
  loading: boolean;
  nameLoading: boolean;
}

export function SearchBar({
  onSearchNif,
  onSearchName,
  nameResults,
  loading,
  nameLoading,
}: Props) {
  const [input, setInput] = useState("");
  const [showResults, setShowResults] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const cleaned = input.replace(/\s/g, "");
  const isNif = /^\d{1,9}$/.test(cleaned);
  const isValidNif = /^\d{9}$/.test(cleaned);
  const isNameQuery = input.trim().length >= 2 && !isNif;

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Show results dropdown when we have name results
  useEffect(() => {
    if (nameResults.length > 0) setShowResults(true);
  }, [nameResults]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isValidNif) {
      setShowResults(false);
      onSearchNif(cleaned);
    } else if (isNameQuery) {
      onSearchName(input.trim());
    }
  };

  const handleSelectResult = (nif: string) => {
    setInput(nif);
    setShowResults(false);
    onSearchNif(nif);
  };

  return (
    <div ref={wrapperRef} className="w-full max-w-2xl mx-auto relative">
      <form onSubmit={handleSubmit}>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter a NIF (e.g. 500697256) or company name"
              aria-label="Search by NIF or company name"
              className="w-full px-3 sm:px-4 py-3 bg-white border border-stone-300 rounded-lg text-base sm:text-lg
                         focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                         placeholder:text-stone-400"
            />
            {input && !isValidNif && isNif && (
              <p className="absolute -bottom-6 left-1 text-sm text-stone-400">
                NIF must be exactly 9 digits
              </p>
            )}
            {isNameQuery && !nameLoading && (
              <p className="absolute -bottom-6 left-1 text-sm text-brand-500">
                Press Enter to search by name
              </p>
            )}
          </div>
          <button
            type="submit"
            disabled={(!isValidNif && !isNameQuery) || loading || nameLoading}
            className="px-4 sm:px-6 py-3 bg-brand-600 text-white font-medium rounded-lg
                       hover:bg-brand-700 active:scale-[0.97] disabled:bg-stone-300 disabled:cursor-not-allowed
                       transition-all duration-150 whitespace-nowrap"
          >
            {loading || nameLoading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Searching...
              </span>
            ) : (
              "Search"
            )}
          </button>
        </div>
      </form>

      {/* Name search results dropdown */}
      {showResults && nameResults.length > 0 && (
        <div className="absolute z-10 mt-2 w-full bg-white border border-stone-200 rounded-lg shadow-lg max-h-[60vh] sm:max-h-80 overflow-y-auto animate-slide-down">
          <div className="px-4 py-2 bg-stone-50 border-b text-xs text-stone-500 font-medium">
            {nameResults.length} matching entities — click to view report
          </div>
          {nameResults.map((r, i) => (
            <button
              key={`${r.nif}-${i}`}
              onClick={() => handleSelectResult(r.nif)}
              className="w-full text-left px-4 py-3 hover:bg-brand-50 border-b last:border-0 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-stone-900">{r.name}</span>
                  <span className="ml-2 text-sm text-stone-500">
                    NIF {r.nif}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {r.lei && (
                    <span className="px-1.5 py-0.5 text-[10px] bg-purple-100 text-purple-700 rounded font-medium">
                      LEI
                    </span>
                  )}
                  <span className="px-1.5 py-0.5 text-[10px] bg-stone-100 text-stone-600 rounded">
                    {r.source === "impic_entities" ? "IMPIC" : r.source.toUpperCase()}
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
