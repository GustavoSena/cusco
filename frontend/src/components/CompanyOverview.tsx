import { useEffect, useRef, useState } from "react";
import type { EntityReport } from "../types";
import { streamOverview } from "../api/client";

interface Props {
  report: EntityReport;
  loading: boolean;
}

export function CompanyOverview({ report, loading }: Props) {
  const [narrative, setNarrative] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [failed, setFailed] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Wait for main report to finish streaming before generating overview
    if (loading) return;

    // Reset state for a new NIF/report
    setNarrative("");
    setFailed(false);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    streamOverview(
      report,
      (chunk) => {
        setNarrative((prev) => prev + chunk);
      },
      controller.signal,
    )
      .then(() => {
        setStreaming(false);
      })
      .catch((err) => {
        // Ignore aborts triggered by unmount/NIF change
        if (controller.signal.aborted) return;
        console.warn("Overview stream failed", err);
        setFailed(true);
        setStreaming(false);
      });

    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.nif, loading]);

  // If it failed and there's nothing to show, hide the component entirely
  if (failed && !narrative) return null;

  // Don't render anything while waiting for the main report to stream
  if (loading && !narrative) return null;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6 animate-fade-in-up">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold tracking-tight">Overview</h3>
        {streaming && (
          <span className="text-xs text-stone-400 flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            Generating...
          </span>
        )}
      </div>

      {narrative ? (
        <div className="prose prose-sm max-w-none text-stone-700 whitespace-pre-wrap leading-relaxed">
          {narrative}
        </div>
      ) : (
        <div className="space-y-2" aria-hidden="true">
          <div className="h-3 bg-stone-100 rounded animate-pulse w-full" />
          <div className="h-3 bg-stone-100 rounded animate-pulse w-11/12" />
          <div className="h-3 bg-stone-100 rounded animate-pulse w-10/12" />
          <div className="h-3 bg-stone-100 rounded animate-pulse w-9/12" />
          <div className="h-3 bg-stone-100 rounded animate-pulse w-8/12" />
        </div>
      )}

      {narrative && !streaming && (
        <p className="mt-4 text-xs text-stone-400 border-t border-stone-100 pt-3">
          AI-generated summary from aggregated public data. May contain inaccuracies.
        </p>
      )}
    </div>
  );
}
