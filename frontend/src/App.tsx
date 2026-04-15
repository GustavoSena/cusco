import { useState } from "react";
import { SearchBar } from "./components/SearchBar";
import { EntityReport } from "./components/EntityReport";
import { searchByNif } from "./api/client";
import type { EntityReport as EntityReportType } from "./types";

export default function App() {
  const [report, setReport] = useState<EntityReportType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (nif: string) => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const result = await searchByNif(nif);
      setReport(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
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
        <SearchBar onSearch={handleSearch} loading={loading} />

        {error && (
          <div className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {report && <EntityReport report={report} />}

        {!report && !loading && !error && (
          <div className="text-center text-gray-400 mt-16">
            <p className="text-lg">Search a NIF to get started</p>
            <p className="text-sm mt-2">
              Aggregates data from CITIUS, Portal das Financas, and IMPIC public
              contracts
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
