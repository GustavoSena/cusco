import type { EntityReport as EntityReportType } from "../types";
import { InsolvencyBadge } from "./InsolvencyBadge";
import { DebtorStatus } from "./DebtorStatus";
import { ContractsList } from "./ContractsList";
import { CompanyProfile } from "./CompanyProfile";
import { AdCCard } from "./AdCCard";

interface Props {
  report: EntityReportType;
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

// SegSocialSection — hidden until connected to entity-level intelligence

export function EntityReport({ report }: Props) {
  const hasWarnings =
    report.has_insolvency || report.is_tax_debtor || report.has_competition_issues;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
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

        {/* Source statuses */}
        <div className="mt-4 flex gap-1.5 flex-wrap" role="status" aria-label="Data source statuses">
          {report.source_statuses.map((s) => (
            <span
              key={s.source}
              className={`px-2 py-0.5 text-xs rounded inline-flex items-center gap-1 ${
                s.status === "ok"
                  ? "bg-green-100 text-green-700"
                  : s.status === "pending"
                    ? "bg-stone-100 text-stone-500"
                    : s.status === "timeout"
                      ? "bg-yellow-100 text-yellow-700"
                      : "bg-red-100 text-red-700"
              }`}
            >
              {s.status === "pending" && (
                <span className="inline-block w-2 h-2 rounded-full bg-stone-400 animate-pulse" />
              )}
              {s.source}: {s.status}
              {s.error && s.status !== "ok" ? ` (${s.error})` : ""}
            </span>
          ))}
        </div>
      </div>

      {/* Risk indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <InsolvencyBadge
          proceedings={report.insolvency_proceedings}
          hasInsolvency={report.has_insolvency}
        />
        <DebtorStatus
          debtor={report.debtor}
          isTaxDebtor={report.is_tax_debtor}
        />
      </div>

      {/* Company Profile — unified identity + stats from LEI, IMPIC, ptdata */}
      <CompanyProfile report={report} />

      {/* Competition Authority (AdC) */}
      <AdCCard
        processes={report.adc_processes ?? []}
        hasCompetitionIssues={report.has_competition_issues ?? false}
      />

      {/* Contracts */}
      <ContractsList
        contracts={report.contracts}
        totalValue={report.contracts_total_value}
      />

      {/* Seg Social — hidden until connected to entity-level intelligence */}
    </div>
  );
}
