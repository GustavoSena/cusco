import { useState } from "react";
import { SearchBar } from "./components/SearchBar";
import { EntityReport } from "./components/EntityReport";
import { ChatPanel } from "./components/ChatPanel";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { searchByNifStream, searchByName } from "./api/client";
import type {
  EntityReport as EntityReportType,
  NameSearchMatch,
} from "./types";

export default function App() {
  const [report, setReport] = useState<EntityReportType | null>(null);
  const [loading, setLoading] = useState(false);
  const [nameLoading, setNameLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nameResults, setNameResults] = useState<NameSearchMatch[]>([]);

  const handleSearchNif = async (nif: string) => {
    setLoading(true);
    setError(null);
    setReport(null);
    setNameResults([]);
    try {
      await searchByNifStream(nif, (partial) => {
        setReport(partial);
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchName = async (name: string) => {
    setNameLoading(true);
    setError(null);
    setNameResults([]);
    try {
      const result = await searchByName(name);
      if (result.results.length === 0) {
        setError(`No entities found matching "${name}"`);
      } else {
        setNameResults(result.results);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Name search failed");
    } finally {
      setNameLoading(false);
    }
  };

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200">
        <div className="max-w-5xl mx-auto px-4 py-4 sm:py-5 flex items-baseline gap-3 sm:gap-4">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-900">Cusco</h1>
          <p className="text-xs sm:text-sm text-stone-400 hidden sm:block">
            Entity intelligence for Portuguese companies
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-4 py-4 sm:py-8 space-y-6 sm:space-y-8">
        <SearchBar
          onSearchNif={handleSearchNif}
          onSearchName={handleSearchName}
          nameResults={nameResults}
          loading={loading}
          nameLoading={nameLoading}
        />

        {error && (
          <div
            role="alert"
            className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start justify-between gap-3 animate-fade-in"
          >
            <p>{error}</p>
            <button
              onClick={() => setError(null)}
              aria-label="Dismiss error"
              className="shrink-0 text-red-400 hover:text-red-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {report && (
          <>
            <EntityReport report={report} loading={loading} />
            {!loading && (
              <ChatPanel
                key={report.nif + report.queried_at}
                report={report}
              />
            )}
          </>
        )}

        {!report && !loading && !error && nameResults.length === 0 && (
          <div className="text-center mt-24 animate-fade-in-up">
            <p className="text-lg text-stone-500">
              Search by NIF or company name
            </p>
            <p className="text-sm text-stone-400 mt-3">
              Aggregates data from CITIUS, Portal das Finanças, IMPIC, GLEIF, Seg. Social, and AdC
            </p>
            <p className="text-xs text-stone-300 mt-8">
              e.g. 500697256 (EDP) or 507280832 (Galp)
            </p>
          </div>
        )}
      </main>
      </div>
    </ErrorBoundary>
  );
}
