import { useState } from "react";
import { SearchBar } from "./components/SearchBar";
import { EntityReport } from "./components/EntityReport";
import { ChatPanel } from "./components/ChatPanel";
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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Cusco</h1>
          <p className="text-gray-500 mt-1">
            Entity intelligence for Portuguese companies
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        <SearchBar
          onSearchNif={handleSearchNif}
          onSearchName={handleSearchName}
          nameResults={nameResults}
          loading={loading}
          nameLoading={nameLoading}
        />

        {error && (
          <div className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {report && (
          <>
            <EntityReport report={report} />
            {!loading && (
              <ChatPanel
                key={report.nif + report.queried_at}
                report={report}
              />
            )}
          </>
        )}

        {!report && !loading && !error && nameResults.length === 0 && (
          <div className="text-center text-gray-400 mt-16">
            <p className="text-lg">Search by NIF or company name</p>
            <p className="text-sm mt-2">
              Aggregates data from CITIUS, Portal das Finanças, IMPIC, GLEIF,
              and more
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
