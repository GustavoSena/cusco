import type { EntityReport } from "../types";
import { formatEUR } from "../format";

interface Props {
  report: EntityReport;
  loading: boolean;
}

type FindingType = "risk" | "clear" | "info";

interface Finding {
  type: FindingType;
  label: string;
}

function isSourceDone(report: EntityReport, sourceName: string): boolean {
  const source = report.source_statuses.find((s) => s.source === sourceName);
  return source != null && source.status !== "pending";
}

function buildFindings(report: EntityReport): Finding[] {
  const findings: Finding[] = [];

  // Risk findings
  if (report.has_insolvency) {
    const count = report.insolvency_proceedings.length;
    findings.push({
      type: "risk",
      label: `Insolvency: ${count} proceeding${count !== 1 ? "s" : ""} found`,
    });
  }

  if (report.is_tax_debtor) {
    const bracket = report.debtor?.debt_bracket_label;
    findings.push({
      type: "risk",
      label: bracket ? `Tax debtor (${bracket})` : "Tax debtor",
    });
  }

  const sanctions = (report.adc_processes ?? []).filter(
    (p) => p.final_decision === "Condenatória"
  ).length;
  if (sanctions > 0) {
    findings.push({
      type: "risk",
      label: `Competition Authority: ${sanctions} sanction${sanctions !== 1 ? "s" : ""}`,
    });
  }

  // Clear findings
  if (!report.has_insolvency && isSourceDone(report, "citius")) {
    findings.push({ type: "clear", label: "No insolvency proceedings" });
  }

  if (!report.is_tax_debtor && isSourceDone(report, "devedores")) {
    findings.push({ type: "clear", label: "Not a tax debtor" });
  }

  const allDone = report.source_statuses.every((s) => s.status !== "pending");
  if (!report.has_competition_issues && allDone) {
    findings.push({ type: "clear", label: "No competition issues" });
  }

  if (report.lei_record?.entity_status === "ACTIVE") {
    findings.push({ type: "clear", label: "Active LEI" });
  }

  // Info findings
  if (isSourceDone(report, "contracts") && report.contracts.length > 0) {
    findings.push({
      type: "info",
      label: `${report.contracts.length} contract${report.contracts.length !== 1 ? "s" : ""} (${formatEUR(report.contracts_total_value)})`,
    });
  }

  if (isSourceDone(report, "prr") && report.has_prr_funding) {
    findings.push({
      type: "info",
      label: `PRR funding: ${formatEUR(report.prr_total_paid)} paid of ${formatEUR(report.prr_total_contracted)} contracted`,
    });
  }

  if (isSourceDone(report, "pt2030") && report.has_pt2030_funding) {
    findings.push({
      type: "info",
      label: `PT2030 funding: ${formatEUR(report.pt2030_total_fund_paid)} paid of ${formatEUR(report.pt2030_total_fund_approved)} approved`,
    });
  }

  if (report.corporate_group) {
    const cg = report.corporate_group;
    const childCount = cg.children?.length ?? 0;
    if (childCount > 0) {
      const count = cg.total_children || childCount;
      findings.push({
        type: "info",
        label: `Corporate group: ${count} subsidiar${count !== 1 ? "ies" : "y"}`,
      });
    } else if (cg.parent) {
      findings.push({
        type: "info",
        label: `Subsidiary of ${cg.parent.name || "a parent company"}`,
      });
    }
  }

  // Municipality contracts — only count as a finding if the company has
  // non-trivial exposure (contracts with multiple municipalities).
  const muniCount = report.municipality_contracts?.length ?? 0;
  if (muniCount >= 3 && isSourceDone(report, "contracts")) {
    findings.push({
      type: "info",
      label: `Contracts with ${muniCount} municipalit${muniCount !== 1 ? "ies" : "y"}`,
    });
  }

  return findings;
}

const DOT_COLORS: Record<FindingType, string> = {
  risk: "bg-red-500",
  clear: "bg-green-500",
  info: "bg-stone-400",
};

const TEXT_COLORS: Record<FindingType, string> = {
  risk: "text-red-700",
  clear: "text-green-700",
  info: "text-stone-600",
};

export function IntelligenceSummary({ report, loading }: Props) {
  const findings = buildFindings(report);
  const pendingCount = report.source_statuses.filter(
    (s) => s.status === "pending"
  ).length;
  const allDone = pendingCount === 0;
  const risks = findings.filter((f) => f.type === "risk");

  if (findings.length === 0 && !loading) return null;

  return (
    <section aria-label="Quick assessment" className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-wide">
          Quick Assessment
        </h3>
        {loading && pendingCount > 0 && (
          <span className="text-xs text-stone-400">
            {pendingCount} source{pendingCount !== 1 ? "s" : ""} loading...
          </span>
        )}
        {allDone && risks.length === 0 && (
          <span className="px-2.5 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded-full">
            NO RISKS DETECTED
          </span>
        )}
        {allDone && risks.length > 0 && (
          <span className="px-2.5 py-0.5 text-xs font-bold bg-red-100 text-red-700 rounded-full">
            {risks.length} RISK{risks.length !== 1 ? "S" : ""} FOUND
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {findings.map((f, i) => (
          <div
            key={f.label}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-stone-50 border border-stone-100 text-sm animate-fade-in"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT_COLORS[f.type]}`}
            />
            <span className={TEXT_COLORS[f.type]}>{f.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
