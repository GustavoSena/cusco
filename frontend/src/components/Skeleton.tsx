import type { ReactNode } from "react";
import type { EntityReport } from "../types";

interface SkeletonBarProps {
  className?: string;
}

export function SkeletonBar({ className = "" }: SkeletonBarProps) {
  return (
    <div
      className={`animate-pulse bg-stone-200 rounded ${className}`}
      aria-hidden="true"
    />
  );
}

interface SkeletonCardProps {
  lines?: number;
  className?: string;
}

export function SkeletonCard({ lines = 3, className = "" }: SkeletonCardProps) {
  return (
    <div
      className={`bg-white rounded-lg border border-stone-200 p-4 sm:p-6 ${className}`}
      aria-hidden="true"
    >
      <SkeletonBar className="h-5 w-40 mb-4" />
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonBar
          key={i}
          className={`h-3.5 mb-2.5 last:mb-0 ${i === lines - 1 ? "w-2/3" : "w-full"}`}
        />
      ))}
    </div>
  );
}

interface SkeletonHalfCardProps {
  className?: string;
}

export function SkeletonHalfCard({ className = "" }: SkeletonHalfCardProps) {
  return (
    <div
      className={`bg-white rounded-lg border border-stone-200 p-4 sm:p-6 ${className}`}
      aria-hidden="true"
    >
      <SkeletonBar className="h-5 w-32 mb-3" />
      <SkeletonBar className="h-3.5 w-full mb-2" />
      <SkeletonBar className="h-3.5 w-1/2" />
    </div>
  );
}

interface StreamSectionProps {
  source: string | string[];
  report: EntityReport;
  skeleton: ReactNode;
  children: ReactNode;
}

export function StreamSection({
  source,
  report,
  skeleton,
  children,
}: StreamSectionProps) {
  const sources = Array.isArray(source) ? source : [source];
  const allPending = sources.every((s) => {
    const found = report.source_statuses.find((r) => r.source === s);
    return !found || found.status === "pending";
  });

  if (allPending) {
    return <>{skeleton}</>;
  }

  return <div className="animate-fade-in">{children}</div>;
}
