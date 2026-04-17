import { useState } from "react";
import type { EntityReport as EntityReportType, SourceResult } from "../types";
import { InsolvencyBadge } from "./InsolvencyBadge";
import { DebtorStatus } from "./DebtorStatus";
import { ContractsList } from "./ContractsList";
import { CompanyProfile } from "./CompanyProfile";
import { AdCCard } from "./AdCCard";
import { IntelligenceSummary } from "./IntelligenceSummary";
import { CompanyOverview } from "./CompanyOverview";
import { StreamSection, SkeletonHalfCard, SkeletonCard } from "./Skeleton";

interface Props {
  report: EntityReportType;
  loading?: boolean;
  aiOverviewAvailable?: boolean;
}

function entityTypeLabel(type: string): string {
  switch (type) {
    case "company":
      return "Company (Pessoa Coletiva)";
    case "individual":
      return "Individual (Pessoa Singular)";
    default:
      return "Unknown";
  }
}

function SourceStatuses({ statuses }: { statuses: SourceResult[] }) {
  const ok = statuses.filter((s) => s.status === "ok");
  const pending = statuses.filter((s) => s.status === "pending");
  const issues = statuses.filter(
    (s) => s.status !== "ok" && s.status !== "pending"
  );

  return (
    <div className="mt-4 flex gap-1.5 flex-wrap items-center" role="status" aria-label="Data source statuses">
      {ok.length > 0 && (
        <span className="px-2 py-0.5 text-xs rounded bg-green-100 text-green-700">
          {ok.length}/{statuses.length} sources OK
        </span>
      )}
      {pending.map((s) => (
        <span
          key={s.source}
          className="px-2 py-0.5 text-xs rounded bg-stone-100 text-stone-500 inline-flex items-center gap-1"
        >
          <span className="inline-block w-2 h-2 rounded-full bg-stone-400 animate-pulse" />
          {s.source}
        </span>
      ))}
      {issues.map((s) => (
        <span
          key={s.source}
          className={`px-2 py-0.5 text-xs rounded ${
            s.status === "timeout"
              ? "bg-yellow-100 text-yellow-700"
              : "bg-red-100 text-red-700"
          }`}
        >
          {s.source}: {s.status}
          {s.error ? ` (${s.error})` : ""}
        </span>
      ))}
    </div>
  );
}

export function EntityReport({
  report,
  loading = false,
  aiOverviewAvailable = false,
}: Props) {
  const hasWarnings =
    report.has_insolvency || report.is_tax_debtor || report.has_competition_issues;

  // When the AI overview is available, collapse the detailed sections by default
  // so the overview is the focal point. When it isn't, fall back to the legacy
  // behaviour (details visible).
  const [detailsExpanded, setDetailsExpanded] = useState(!aiOverviewAvailable);

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6 animate-fade-in-up">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              NIF {report.nif}
              {report.company?.valid && (
                <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-brand-100 text-brand-700 rounded-full align-middle">
                  VALID
                </span>
              )}
            </h2>
            {report.company?.name && (
              <p className="text-lg text-stone-600 mt-1">
                {report.company.name}
              </p>
            )}
            {report.company && (
              <p className="text-sm text-stone-500 mt-1">
                {entityTypeLabel(report.company.entity_type)}
              </p>
            )}
            {/* LEI inline if available */}
            {report.lei_record && (
              <p className="text-xs text-stone-400 mt-1 font-mono">
                LEI: {report.lei_record.lei}
              </p>
            )}
          </div>
          {hasWarnings && (
            <div className="flex gap-2 flex-wrap">
              {report.has_insolvency && (
                <span className="px-3 py-1 text-sm font-bold bg-red-600 text-white rounded-full">
                  Insolvency
                </span>
              )}
              {report.is_tax_debtor && (
                <span className="px-3 py-1 text-sm font-bold bg-orange-600 text-white rounded-full">
                  Tax Debtor
                </span>
              )}
              {report.has_competition_issues && (
                <span className="px-3 py-1 text-sm font-bold bg-purple-600 text-white rounded-full">
                  AdC Sanctions
                </span>
              )}
            </div>
          )}
        </div>

        {/* Source statuses — compact: show summary + only non-ok details */}
        <SourceStatuses statuses={report.source_statuses} />
      </div>

      {/* AI-generated overview */}
      {aiOverviewAvailable && (
        <CompanyOverview report={report} loading={loading} />
      )}

      {/* Collapse toggle — only shown when the overview is available */}
      {aiOverviewAvailable && (
        <button
          onClick={() => setDetailsExpanded(!detailsExpanded)}
          className="w-full py-2.5 text-sm text-stone-600 hover:text-stone-900 hover:bg-stone-50 rounded-lg border border-stone-200 transition-colors flex items-center justify-center gap-2"
          aria-expanded={detailsExpanded}
        >
          <svg
            className={`w-4 h-4 transition-transform ${detailsExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
          {detailsExpanded ? "Hide detailed sections" : "Show detailed sections"}
        </button>
      )}

      {/* Detailed sections — collapsible when the AI overview is available */}
      <div className="grid-expand" aria-hidden={!detailsExpanded}>
        <div>
          <div className="space-y-6">
            {/* Intelligence Summary */}
            <IntelligenceSummary report={report} loading={loading} />

            {/* Risk indicators */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StreamSection
                source="citius"
                report={report}
                skeleton={<SkeletonHalfCard />}
              >
                <InsolvencyBadge
                  proceedings={report.insolvency_proceedings}
                  hasInsolvency={report.has_insolvency}
                />
              </StreamSection>
              <StreamSection
                source="devedores"
                report={report}
                skeleton={<SkeletonHalfCard />}
              >
                <DebtorStatus
                  debtor={report.debtor}
                  isTaxDebtor={report.is_tax_debtor}
                />
              </StreamSection>
            </div>

            {/* Company Profile — unified identity + stats from LEI, IMPIC, ptdata */}
            <StreamSection
              source={["entities", "gleif"]}
              report={report}
              skeleton={<SkeletonCard lines={5} />}
            >
              <CompanyProfile report={report} />
            </StreamSection>

            {/* Competition Authority (AdC) */}
            <AdCCard
              processes={report.adc_processes ?? []}
              hasCompetitionIssues={report.has_competition_issues ?? false}
            />

            {/* Contracts */}
            <StreamSection
              source="contracts"
              report={report}
              skeleton={<SkeletonCard lines={6} />}
            >
              <ContractsList
                contracts={report.contracts}
                totalValue={report.contracts_total_value}
              />
            </StreamSection>
          </div>
        </div>
      </div>
    </div>
  );
}
