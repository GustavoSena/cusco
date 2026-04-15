import { useState } from "react";
import type { EntityReport } from "../types";

interface Props {
  report: EntityReport;
}

function formatEUR(value: number | null | undefined): string {
  if (value == null) return "-";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function parseIberinformContent(content: string): {
  fields: { label: string; value: string }[];
  summary: string | null;
} {
  const lines = content.split("\n");
  const fields: { label: string; value: string }[] = [];
  let summary: string | null = null;
  let currentLabel: string | null = null;
  let inSummary = false;
  const summaryLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (/^#{1,3}\s+(Dados Gerais|Resumo)/i.test(line)) {
      if (/resumo/i.test(line)) {
        inSummary = true;
        continue;
      }
      continue;
    }

    if (inSummary) {
      if (/^#{1,3}\s+/.test(line)) break;
      if (line) summaryLines.push(line);
      continue;
    }

    if (/^#{2,4}\s+/.test(line)) {
      if (currentLabel && !fields.find((f) => f.label === currentLabel)) {
        fields.push({ label: currentLabel, value: "" });
      }
      currentLabel = line.replace(/^#{2,4}\s+/, "").trim();
      continue;
    }

    if (currentLabel && line) {
      const cleanValue = line.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").trim();
      if (cleanValue) {
        fields.push({ label: currentLabel, value: cleanValue });
        currentLabel = null;
      }
    }
  }

  if (summaryLines.length > 0) {
    summary = summaryLines.join(" ").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
    // Remove Iberinform promotional boilerplate (company name varies)
    summary = summary
      .replace(/Esta informação sobre .+? é apenas uma breve descrição .+$/i, "")
      .replace(/Pode utilizar a nossa solução .+$/i, "")
      .replace(/Este é um resumo sobre .+$/, "")
      .replace(/Recomendamo-lo a explorar .+$/, "")
      .replace(/Ver o relatório alargado .+$/, "")
      .replace(/Descubra tudo .+$/, "")
      .replace(/ACESSO GRATUITO/g, "")
      .replace(/Insight View/g, "")
      .trim();
    if (!summary) summary = null;
  }

  return { fields, summary };
}

export function CompanyProfile({ report }: Props) {
  const [showDetails, setShowDetails] = useState(true);

  const profile = report.entity_profile;
  const lei = report.lei_record;
  const company = report.company;
  const iberinform = report.iberinform_content
    ? parseIberinformContent(report.iberinform_content)
    : null;

  const hasIberinform =
    iberinform && (iberinform.fields.length > 0 || iberinform.summary);

  // Nothing to show if we have no identity data at all
  if (!profile && !lei && !company?.name && !hasIberinform) return null;

  const companyName =
    company?.name || profile?.name || lei?.legal_name || null;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <button
        type="button"
        onClick={() => setShowDetails(!showDetails)}
        aria-expanded={showDetails}
        aria-controls="company-profile-content"
        className="w-full flex items-center justify-between text-left"
      >
        <h3 className="text-lg font-semibold">Company Profile</h3>
        <svg
          className={`w-5 h-5 text-stone-400 transition-transform ${showDetails ? "rotate-180" : ""}`}
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
      </button>

      {showDetails && (
        <div id="company-profile-content" className="mt-4 space-y-4">
          {/* Iberinform fields — richest source, show first when available */}
          {hasIberinform && (
            <>
              {iberinform!.fields.length > 0 && (
                <table className="w-full text-sm">
                  <tbody>
                    {iberinform!.fields.map((f, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="px-2 sm:px-4 py-2 text-stone-500 font-medium sm:w-1/3 align-top sm:whitespace-nowrap">
                          {f.label}
                        </td>
                        <td className="px-2 sm:px-4 py-2 text-stone-800 break-words">{f.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {iberinform!.summary && (
                <div className="p-3 bg-stone-50 rounded">
                  <p className="text-xs text-stone-500 uppercase tracking-wide mb-1">
                    Summary
                  </p>
                  <p className="text-sm text-stone-600 leading-relaxed">
                    {iberinform!.summary}
                  </p>
                </div>
              )}
            </>
          )}

          {/* Identity info from LEI / IMPIC / ptdata (shown when no Iberinform, or as supplement) */}
          {!hasIberinform && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {companyName && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    Name
                  </p>
                  <p className="text-sm font-medium text-stone-900 mt-1">
                    {companyName}
                  </p>
                </div>
              )}
              {lei && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    LEI
                  </p>
                  <p className="text-sm font-mono text-stone-700 mt-1">
                    {lei.lei}
                  </p>
                  {lei.entity_status && (
                    <span
                      className={`inline-block mt-1 px-1.5 py-0.5 text-[10px] font-medium rounded ${
                        lei.entity_status === "ACTIVE"
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {lei.entity_status}
                    </span>
                  )}
                </div>
              )}
              {lei?.legal_address && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    Registered Address
                  </p>
                  <p className="text-sm text-stone-700 mt-1">
                    {[lei.legal_address, lei.legal_city, lei.legal_postal_code]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                </div>
              )}
              {lei?.headquarters_address &&
                lei.headquarters_address !== lei.legal_address && (
                  <div>
                    <p className="text-xs text-stone-500 uppercase tracking-wide">
                      Headquarters
                    </p>
                    <p className="text-sm text-stone-700 mt-1">
                      {[lei.headquarters_address, lei.headquarters_city]
                        .filter(Boolean)
                        .join(", ")}
                    </p>
                  </div>
                )}
              {(profile?.country || lei?.jurisdiction) && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    Jurisdiction
                  </p>
                  <p className="text-sm text-stone-700 mt-1">
                    {profile?.country || lei?.jurisdiction || "-"}
                    {profile?.country_code && (
                      <span className="ml-1 text-stone-400">
                        ({profile.country_code})
                      </span>
                    )}
                  </p>
                </div>
              )}
              {lei?.initial_registration_date && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    First Registered
                  </p>
                  <p className="text-sm text-stone-700 mt-1">
                    {lei.initial_registration_date}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* LEI supplement when Iberinform is present */}
          {hasIberinform && lei && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide">
                  LEI
                </p>
                <p className="text-sm font-mono text-stone-700 mt-1">
                  {lei.lei}
                  {lei.entity_status && (
                    <span
                      className={`ml-2 px-1.5 py-0.5 text-[10px] font-medium rounded ${
                        lei.entity_status === "ACTIVE"
                          ? "bg-green-100 text-green-700"
                          : "bg-yellow-100 text-yellow-700"
                      }`}
                    >
                      {lei.entity_status}
                    </span>
                  )}
                </p>
              </div>
              {lei.legal_address && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    Registered Address (GLEIF)
                  </p>
                  <p className="text-sm text-stone-700 mt-1">
                    {[lei.legal_address, lei.legal_city, lei.legal_postal_code]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* IMPIC contract stats */}
          {profile && profile.total_contracts != null && (
            <>
              <hr className="border-stone-100" />
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide mb-3">
                  Public Procurement Summary (IMPIC)
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xl font-bold text-stone-900">
                      {profile.total_contracts ?? "-"}
                    </p>
                    <p className="text-xs text-stone-500">Total Contracts</p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-stone-800">
                      {profile.times_as_supplier ?? "-"}
                    </p>
                    <p className="text-xs text-stone-500">As Supplier</p>
                    <p className="text-xs text-stone-400">
                      {formatEUR(profile.total_value_as_supplier)}
                    </p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-stone-800">
                      {profile.times_as_entity ?? "-"}
                    </p>
                    <p className="text-xs text-stone-500">As Entity</p>
                    <p className="text-xs text-stone-400">
                      {formatEUR(profile.total_value_as_entity)}
                    </p>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-stone-800">
                      {profile.country_code ?? "-"}
                    </p>
                    <p className="text-xs text-stone-500">Country</p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Other names from LEI */}
          {lei && lei.other_names.length > 0 && (
            <>
              <hr className="border-stone-100" />
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide mb-1">
                  Other Known Names
                </p>
                <p className="text-sm text-stone-600">
                  {lei.other_names.join(", ")}
                </p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
