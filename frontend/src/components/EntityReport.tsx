import { useState } from "react";
import type { EntityReport as EntityReportType } from "../types";
import { InsolvencyBadge } from "./InsolvencyBadge";
import { DebtorStatus } from "./DebtorStatus";
import { ContractsList } from "./ContractsList";
import { EntityProfileCard } from "./EntityProfileCard";
import { LEICard } from "./LEICard";
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

function IberinformSection({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-lg border">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="font-semibold text-gray-700">
          Iberinform — Company Profile
        </span>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      {expanded && (
        <div className="border-t p-4 prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
          {content}
        </div>
      )}
    </div>
  );
}

// SegSocialSection — hidden until connected to entity-level intelligence
// Kept as a comment for future use when Seg Social data is mapped to entities

export function EntityReport({ report }: Props) {
  const hasWarnings =
    report.has_insolvency || report.is_tax_debtor || report.has_competition_issues;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg border p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold">
              NIF {report.nif}
              {report.company?.valid && (
                <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-blue-100 text-blue-700 rounded-full align-middle">
                  VALID
                </span>
              )}
            </h2>
            {report.company?.name && (
              <p className="text-lg text-gray-600 mt-1">{report.company.name}</p>
            )}
            {report.company && (
              <p className="text-sm text-gray-500 mt-1">
                {entityTypeLabel(report.company.entity_type)}
              </p>
            )}
            {/* LEI inline if available */}
            {report.lei_record && (
              <p className="text-xs text-gray-400 mt-1 font-mono">
                LEI: {report.lei_record.lei}
              </p>
            )}
          </div>
          {hasWarnings && (
            <div className="flex gap-2">
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
        <div className="mt-4 flex gap-2 flex-wrap">
          {report.source_statuses.map((s) => (
            <span
              key={s.source}
              className={`px-2 py-0.5 text-xs rounded ${
                s.status === "ok"
                  ? "bg-green-100 text-green-700"
                  : s.status === "timeout"
                    ? "bg-yellow-100 text-yellow-700"
                    : "bg-red-100 text-red-700"
              }`}
            >
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

      {/* Competition Authority (AdC) */}
      <AdCCard
        processes={report.adc_processes ?? []}
        hasCompetitionIssues={report.has_competition_issues ?? false}
      />

      {/* LEI Record */}
      {report.lei_record && <LEICard record={report.lei_record} />}

      {/* Entity Profile (IMPIC stats) */}
      {report.entity_profile && (
        <EntityProfileCard profile={report.entity_profile} />
      )}

      {/* Iberinform */}
      {report.iberinform_content && (
        <IberinformSection content={report.iberinform_content} />
      )}

      {/* Contracts */}
      <ContractsList
        contracts={report.contracts}
        totalValue={report.contracts_total_value}
      />

      {/* Seg Social — hidden until connected to entity-level intelligence */}
    </div>
  );
}
