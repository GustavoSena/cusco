import { useState } from "react";
import type { AdCProcess } from "../types";

interface Props {
  processes: AdCProcess[];
  hasCompetitionIssues: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  praticas_anticoncorrenciais: "Anti-competitive Practices",
  concentracoes: "Merger Control",
  contencioso: "Judicial Decisions",
  estudos_pareceres: "Studies & Opinions",
};

const DECISION_COLORS: Record<string, string> = {
  "Condenatória": "bg-red-100 text-red-700",
  "Arquivamento": "bg-stone-100 text-stone-600",
  "Arquivamento com compromissos": "bg-yellow-100 text-yellow-700",
  "Não oposição": "bg-green-100 text-green-700",
  "Não oposição com compromissos": "bg-sky-100 text-sky-700",
};

const INITIAL_LIMIT = 5;
const LOAD_MORE_STEP = 10;

export function AdCCard({ processes, hasCompetitionIssues }: Props) {
  const [expanded, setExpanded] = useState(hasCompetitionIssues);
  const [visibleCount, setVisibleCount] = useState(INITIAL_LIMIT);

  // Group by type
  const byType: Record<string, AdCProcess[]> = {};
  for (const p of processes) {
    const key = p.process_type || "other";
    if (!byType[key]) byType[key] = [];
    byType[key].push(p);
  }

  // Count sanctions
  const sanctions = processes.filter(
    (p) => p.final_decision === "Condenatória"
  ).length;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          Competition Authority (AdC)
          {hasCompetitionIssues ? (
            <span className="px-2 py-0.5 text-xs font-bold bg-red-100 text-red-700 rounded-full">
              {sanctions} SANCTION{sanctions !== 1 ? "S" : ""}
            </span>
          ) : processes.length > 0 ? (
            <span className="px-2 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded-full">
              NO SANCTIONS
            </span>
          ) : (
            <span className="px-2 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded-full">
              CLEAR
            </span>
          )}
        </h3>
        {processes.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="text-xs text-brand-600 hover:text-brand-800"
          >
            {expanded ? "Hide" : `Show ${processes.length} processes`}
          </button>
        )}
      </div>

      {processes.length === 0 && (
        <p className="text-stone-500 text-sm mt-2">
          No competition authority processes found.
        </p>
      )}

      {processes.length > 0 && (
        <div
          className="grid-expand"
          aria-hidden={!expanded}
        >
        <div className="mt-4 space-y-4">
          {Object.entries(byType).map(([type, procs]) => {
            const visible = procs.slice(0, visibleCount);
            const hasMore = visibleCount < procs.length;
            return (
            <div key={type}>
              <h4 className="text-sm font-medium text-stone-500 mb-2">
                {TYPE_LABELS[type] || type} ({procs.length})
              </h4>
              <div className="space-y-2">
                {visible.map((p, i) => (
                  <div
                    key={`${p.process_number}-${i}`}
                    className={`p-3 rounded border ${
                      p.final_decision === "Condenatória"
                        ? "bg-red-50 border-red-200"
                        : "bg-stone-50 border-stone-200"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-sm font-medium">
                            {p.process_number}
                          </span>
                          {p.final_decision && (
                            <span
                              className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                                DECISION_COLORS[p.final_decision] ||
                                "bg-stone-100 text-stone-600"
                              }`}
                            >
                              {p.final_decision}
                            </span>
                          )}
                          {p.status && p.status !== "Fechado" && (
                            <span className="px-1.5 py-0.5 text-[10px] bg-brand-100 text-brand-700 rounded">
                              {p.status}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 text-sm text-stone-700">
                          {p.entities.slice(0, 3).join(", ")}
                          {p.entities.length > 3 && (
                            <span className="text-stone-400">
                              {" "}+{p.entities.length - 3} more
                            </span>
                          )}
                        </div>
                        {p.practice_type && (
                          <p className="text-xs text-stone-500 mt-0.5">
                            {p.practice_type}
                          </p>
                        )}
                        {p.court && (
                          <p className="text-xs text-stone-500 mt-0.5">
                            {p.court}
                            {p.court_process_number &&
                              ` — ${p.court_process_number}`}
                          </p>
                        )}
                        <div className="flex gap-3 mt-1 text-xs text-stone-400">
                          {p.sector && p.sector !== "*" && (
                            <span>{p.sector}</span>
                          )}
                          {p.year_opened && p.year_opened !== "*" && (
                            <span>Opened: {p.year_opened}</span>
                          )}
                          {p.year_decided && p.year_decided !== "*" && (
                            <span>Decided: {p.year_decided}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-1 shrink-0">
                        {p.detail_url && (
                          <a
                            href={p.detail_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2 py-1 text-[10px] bg-brand-50 text-brand-600 rounded hover:bg-brand-100"
                          >
                            Details
                          </a>
                        )}
                        {p.pdf_url && (
                          <a
                            href={p.pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-2 py-1 text-[10px] bg-stone-100 text-stone-600 rounded hover:bg-stone-200"
                          >
                            PDF
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {hasMore && (
                <button
                  onClick={() => setVisibleCount((prev) => prev + LOAD_MORE_STEP)}
                  className="mt-2 w-full py-1.5 text-xs text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors"
                >
                  Show more ({visible.length} of {procs.length})
                </button>
              )}
              {!hasMore && procs.length > INITIAL_LIMIT && (
                <button
                  onClick={() => setVisibleCount(INITIAL_LIMIT)}
                  className="mt-2 w-full py-1.5 text-xs text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded transition-colors"
                >
                  Show less
                </button>
              )}
            </div>
          );
          })}
        </div>
        </div>
      )}
    </div>
  );
}
