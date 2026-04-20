import { useState } from "react";
import type { EntityReport } from "../types";
import { formatEUR } from "../format";

interface Props {
  report: EntityReport;
  /**
   * When true, the profile opens in a denser layout intended to sit
   * above the AI overview as the page focal point: CAE secondary codes
   * default-truncated, Iberinform summary omitted (the AI narrative
   * covers it), no hard borders that would fight the overview card.
   */
  compact?: boolean;
}

// Secondary CAE codes can get long (some companies list 30+). Show the
// first N by default and hide the rest behind a "show all" click so
// the profile doesn't dominate the viewport on code-heavy companies.
const SECONDARY_CAE_DEFAULT_VISIBLE = 3;

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

export function CompanyProfile({ report, compact = false }: Props) {
  const [showDetails, setShowDetails] = useState(true);
  const [showAllCaes, setShowAllCaes] = useState(false);

  const profile = report.entity_profile;
  const lei = report.lei_record;
  const company = report.company;
  const ptdata = report.ptdata_company;
  const iberinform = report.iberinform_content
    ? parseIberinformContent(report.iberinform_content)
    : null;

  const hasIberinform =
    iberinform && (iberinform.fields.length > 0 || iberinform.summary);

  // Nothing to show if we have no identity data at all
  if (!profile && !lei && !company?.name && !hasIberinform && !ptdata) return null;

  const companyName =
    company?.name || profile?.name || lei?.legal_name || ptdata?.name || null;

  const principalCae = ptdata?.cae_codes.find((c) => c.type === "principal");
  const secondaryCaes = ptdata?.cae_codes.filter((c) => c.type !== "principal") ?? [];
  const hasLeiAddress = !!lei?.legal_address;
  const showPtdataAddress = !!ptdata?.address && !hasLeiAddress && !hasIberinform;
  const sourceChecks = ptdata?.source_checks ?? [];

  const secondaryCaesHidden = Math.max(
    0,
    secondaryCaes.length - SECONDARY_CAE_DEFAULT_VISIBLE,
  );
  const visibleSecondaryCaes = showAllCaes
    ? secondaryCaes
    : secondaryCaes.slice(0, SECONDARY_CAE_DEFAULT_VISIBLE);

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
          className={`w-5 h-5 text-stone-400 transition-transform duration-300 ${showDetails ? "rotate-180" : ""}`}
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

      <div
        id="company-profile-content"
        className="grid-expand"
        aria-hidden={!showDetails}
      >
        <div className="mt-4 space-y-4">
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
              {/* In compact mode (profile is the lede, AI overview comes
                  below), the Iberinform "Summary" blurb is redundant
                  with the AI narrative — hide it to keep the card
                  tight. In full mode, show it as before. */}
              {iberinform!.summary && !compact && (
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
              {showPtdataAddress && (
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-wide">
                    Registered Address
                  </p>
                  <p
                    className="text-sm text-stone-700 mt-1"
                    style={{ whiteSpace: "pre-line" }}
                  >
                    {ptdata!.address}
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

          {/* CAE industry classification (ptdata / SICAE) */}
          {ptdata && (principalCae || secondaryCaes.length > 0) && (
            <>
              <hr className="border-stone-100" />
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide mb-2">
                  Industry (CAE)
                </p>
                {principalCae && (
                  <div className="text-sm text-stone-800">
                    <span className="font-mono text-stone-600">
                      {principalCae.code}
                    </span>
                    {principalCae.description && (
                      <span className="ml-2">— {principalCae.description}</span>
                    )}
                  </div>
                )}
                {secondaryCaes.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 items-center">
                    {visibleSecondaryCaes.map((c) => (
                      <span
                        key={c.code}
                        title={c.description}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] bg-stone-100 text-stone-700 rounded"
                      >
                        <span className="font-mono text-stone-500">{c.code}</span>
                        {c.description && (
                          <span className="truncate max-w-[220px]">
                            {c.description}
                          </span>
                        )}
                      </span>
                    ))}
                    {/* "show more" affordance when the list is truncated.
                        Keeps the default view compact on companies with
                        many secondary CAEs (common for holdings / retail). */}
                    {secondaryCaesHidden > 0 && (
                      <button
                        type="button"
                        onClick={() => setShowAllCaes(!showAllCaes)}
                        aria-expanded={showAllCaes}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] text-brand-700 hover:text-brand-900 hover:bg-brand-50 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
                      >
                        {showAllCaes
                          ? "Show fewer"
                          : `+${secondaryCaesHidden} more`}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          {/* ptdata address supplement when another source already provided one */}
          {ptdata?.address && !showPtdataAddress && !hasLeiAddress && hasIberinform && (
            <>
              <hr className="border-stone-100" />
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide mb-1">
                  Registered Address (SICAE)
                </p>
                <p
                  className="text-sm text-stone-700"
                  style={{ whiteSpace: "pre-line" }}
                >
                  {ptdata.address}
                </p>
              </div>
            </>
          )}

          {/* ptdata source checks — subtle diagnostic row */}
          {sourceChecks.length > 0 && (
            <div className="pt-1">
              <div className="flex flex-wrap gap-1">
                {sourceChecks.map((s) => {
                  const ok = s.status === "ok";
                  const label =
                    s.id === "checksum"
                      ? "NIF"
                      : s.id === "sicae"
                        ? "SICAE"
                        : s.id === "vies"
                          ? "VIES"
                          : s.id === "base"
                            ? "BASE"
                            : s.id.toUpperCase();
                  return (
                    <span
                      key={s.id}
                      title={s.name || s.id}
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded ${
                        ok
                          ? "bg-green-50 text-green-700"
                          : "bg-stone-100 text-stone-500"
                      }`}
                    >
                      {label}
                      <span aria-hidden="true">{ok ? "✓" : "·"}</span>
                    </span>
                  );
                })}
              </div>
            </div>
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
      </div>
    </div>
  );
}
