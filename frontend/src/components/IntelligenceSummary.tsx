import type { EntityReport } from "../types";
import { formatEUR } from "../format";

interface Props {
  report: EntityReport;
  loading: boolean;
}

interface Finding {
  text: string;
  severity: "risk" | "clear" | "info";
}

function buildFindings(report: EntityReport): Finding[] {
  const findings: Finding[] = [];
  const pending = report.source_statuses.filter((s) => s.status === "pending");
  const isComplete = pending.length === 0;

  // Insolvency
  if (report.has_insolvency) {
    const count = report.insolvency_proceedings.length;
    findings.push({
      text: `${count} insolvency proceeding${count !== 1 ? "s" : ""} found in CITIUS`,
      severity: "risk",
    });
  } else if (isSourceDone(report, "citius")) {
    findings.push({
      text: "No insolvency proceedings",
      severity: "clear",
    });
  }

  // Tax debtor
  if (report.is_tax_debtor && report.debtor?.found) {
    const bracket = report.debtor.debt_bracket_label;
    findings.push({
      text: `Listed as tax debtor${bracket ? ` (${bracket} EUR)` : ""}`,
      severity: "risk",
    });
  } else if (isSourceDone(report, "devedores")) {
    findings.push({
      text: "Not on the tax debtor list",
      severity: "clear",
    });
  }

  // AdC sanctions
  if (report.has_competition_issues) {
    const sanctions = (report.adc_processes ?? []).filter(
      (p) => p.final_decision === "Condenatória"
    ).length;
    findings.push({
      text: `${sanctions} competition authority sanction${sanctions !== 1 ? "s" : ""} (AdC)`,
      severity: "risk",
    });
  } else if (isComplete && (report.adc_processes ?? []).length === 0) {
    findings.push({
      text: "No competition authority issues",
      severity: "clear",
    });
  }

  // Contracts
  if (isSourceDone(report, "contracts") && report.contracts.length > 0) {
    findings.push({
      text: `${report.contracts.length} public contract${report.contracts.length !== 1 ? "s" : ""} worth ${formatEUR(report.contracts_total_value)} total`,
      severity: "info",
    });
  } else if (isSourceDone(report, "contracts")) {
    findings.push({
      text: "No public contracts found",
      severity: "info",
    });
  }

  // LEI status
  if (report.lei_record) {
    if (report.lei_record.entity_status === "ACTIVE") {
      findings.push({
        text: `Active LEI (${report.lei_record.lei.slice(0, 8)}...)`,
        severity: "clear",
      });
    } else if (report.lei_record.entity_status) {
      findings.push({
        text: `LEI status: ${report.lei_record.entity_status}`,
        severity: "risk",
      });
    }
  }

  return findings;
}

function isSourceDone(report: EntityReport, source: string): boolean {
  return report.source_statuses.some(
    (s) => s.source === source && s.status !== "pending"
  );
}

const SEVERITY_STYLES = {
  risk: "text-red-700 bg-red-50 border-red-200",
  clear: "text-green-700 bg-green-50 border-green-200",
  info: "text-stone-600 bg-stone-50 border-stone-200",
};

const SEVERITY_DOTS = {
  risk: "bg-red-500",
  clear: "bg-green-500",
  info: "bg-stone-400",
};

export function IntelligenceSummary({ report, loading }: Props) {
  const findings = buildFindings(report);
  const pending = report.source_statuses.filter((s) => s.status === "pending");
  const risks = findings.filter((f) => f.severity === "risk");

  if (findings.length === 0 && !loading) return null;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-5 animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-stone-700 uppercase tracking-wide">
          Quick Assessment
        </h3>
        {loading && pending.length > 0 && (
          <span className="text-xs text-stone-400 animate-pulse">
            {pending.length} source{pending.length !== 1 ? "s" : ""} loading...
          </span>
        )}
        {!loading && risks.length === 0 && findings.length > 0 && (
          <span className="px-2 py-0.5 text-[10px] font-bold bg-green-100 text-green-700 rounded-full">
            NO RISKS DETECTED
          </span>
        )}
        {risks.length > 0 && (
          <span className="px-2 py-0.5 text-[10px] font-bold bg-red-100 text-red-700 rounded-full">
            {risks.length} RISK{risks.length !== 1 ? "S" : ""} FOUND
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        {findings.map((f, i) => (
          <li
            key={i}
            className={`flex items-center gap-2 text-sm px-3 py-1.5 rounded border ${SEVERITY_STYLES[f.severity]} animate-fade-in`}
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOTS[f.severity]}`}
            />
            {f.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
