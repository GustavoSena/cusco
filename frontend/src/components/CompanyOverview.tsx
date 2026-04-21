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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Wait for main report to finish streaming before generating overview
    if (loading) return;

    // Reset state for a new NIF/report
    setNarrative("");
    setErrorMessage(null);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    streamOverview(
      report,
      {
        onChunk: (chunk) => {
          setNarrative((prev) => prev + chunk);
        },
        onError: (message) => {
          setErrorMessage(message);
        },
      },
      controller.signal,
    )
      .then(() => setStreaming(false))
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.warn("Overview stream failed", err);
        setErrorMessage(
          err instanceof Error ? err.message : "Overview unavailable",
        );
        setStreaming(false);
      });

    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.nif, loading]);

  // While a new report is loading, hide unconditionally. Previously this
  // leaked the previous company's narrative/error into the new search while
  // the main report was still streaming — stale intelligence.
  if (loading) return null;

  // Error state — show a subtle "unavailable" notice (user deserves to know why the card is empty)
  if (errorMessage && !narrative) {
    return (
      <section
        aria-labelledby="overview-heading"
        className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6 animate-fade-in"
      >
        <h3
          id="overview-heading"
          className="text-lg font-semibold tracking-tight mb-2"
        >
          Overview
        </h3>
        <p className="text-sm text-stone-500">
          AI summary unavailable — {errorMessage.toLowerCase()}.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="overview-heading"
      className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6 animate-fade-in-up"
    >
      <div className="flex items-center justify-between mb-3">
        <h3
          id="overview-heading"
          className="text-lg font-semibold tracking-tight"
        >
          Overview
        </h3>
        {streaming && (
          <span
            className="text-xs text-stone-500 flex items-center gap-1.5"
            aria-live="polite"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            Generating...
          </span>
        )}
      </div>

      {narrative ? (
        <div
          className="text-stone-700 whitespace-pre-wrap leading-relaxed text-sm sm:text-base"
          aria-live="polite"
          aria-busy={streaming}
        >
          {narrative}
        </div>
      ) : streaming ? (
        // `role="status"` makes the loading state perceivable to assistive
        // tech (announced politely). `aria-hidden="true"` on the SAME
        // element previously nullified that, so screen-reader users saw
        // nothing between the heading and the arriving text. The decorative
        // skeleton bars below opt out of the tree individually instead.
        <div
          className="space-y-2"
          role="status"
          aria-label="Generating company overview"
        >
          <div
            className="h-3 bg-stone-100 rounded animate-pulse w-full"
            aria-hidden="true"
          />
          <div
            className="h-3 bg-stone-100 rounded animate-pulse w-11/12"
            aria-hidden="true"
          />
          <div
            className="h-3 bg-stone-100 rounded animate-pulse w-10/12"
            aria-hidden="true"
          />
          <div
            className="h-3 bg-stone-100 rounded animate-pulse w-9/12"
            aria-hidden="true"
          />
          <div
            className="h-3 bg-stone-100 rounded animate-pulse w-8/12"
            aria-hidden="true"
          />
        </div>
      ) : (
        // Stream completed without any chunks (no error emitted) — rare,
        // but don't leave the skeleton spinning forever.
        <p className="text-sm text-stone-500">
          No summary was generated for this company.
        </p>
      )}

      {/* If the stream failed after some chunks arrived, surface the partial
          state so users know the narrative is incomplete. */}
      {errorMessage && narrative && (
        <p
          role="status"
          className="mt-3 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-2.5 py-1.5"
        >
          Generation interrupted — showing partial summary.
        </p>
      )}

      {narrative && !streaming && (
        <p className="mt-4 text-xs text-stone-500 border-t border-stone-100 pt-3">
          AI-generated summary from aggregated public data. May contain
          inaccuracies.
        </p>
      )}
    </section>
  );
}
