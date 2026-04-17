import type { ReactNode } from "react";
import type { EntityReport, SourceResult } from "../types";

/** Pulsing placeholder bar */
export function SkeletonBar({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-stone-200 ${className}`}
      aria-hidden="true"
    />
  );
}

/** Card-shaped skeleton matching the real section heights */
export function SkeletonCard({
  lines = 3,
  className = "",
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div
      className={`bg-white rounded-lg border border-stone-200 p-4 sm:p-6 ${className}`}
      aria-hidden="true"
    >
      <SkeletonBar className="h-5 w-1/3 mb-4" />
      <div className="space-y-2.5">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonBar
            key={i}
            className={`h-3.5 ${i === lines - 1 ? "w-2/3" : "w-full"}`}
          />
        ))}
      </div>
    </div>
  );
}

/** Half-width skeleton for the 2-column risk grid */
export function SkeletonHalfCard() {
  return (
    <div
      className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6"
      aria-hidden="true"
    >
      <div className="flex items-center gap-2 mb-3">
        <SkeletonBar className="h-5 w-1/2" />
        <SkeletonBar className="h-5 w-16 rounded-full" />
      </div>
      <SkeletonBar className="h-3.5 w-full" />
    </div>
  );
}

/**
 * Wraps a section: shows skeleton while the source is pending,
 * fades in real content once loaded.
 */
export function StreamSection({
  source,
  report,
  skeleton,
  children,
}: {
  source: string | string[];
  report: EntityReport;
  skeleton: ReactNode;
  children: ReactNode;
}) {
  const sources = Array.isArray(source) ? source : [source];
  const isPending = sources.every((s) =>
    report.source_statuses.some(
      (st: SourceResult) => st.source === s && st.status === "pending"
    )
  );

  if (isPending) return <>{skeleton}</>;

  return <div className="animate-fade-in">{children}</div>;
}
