import { useState } from "react";
import type { PRRFunding, PRRContract, PT2030Funding } from "../types";
import { formatEUR } from "../format";

interface Props {
  prrFundings: PRRFunding[];
  prrContracts: PRRContract[];
  prrTotalContracted: number;
  prrTotalPaid: number;
  pt2030Fundings: PT2030Funding[];
  pt2030TotalFundApproved: number;
  pt2030TotalFundPaid: number;
}

const INITIAL_ROWS = 5;

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs text-stone-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-lg font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function Section({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (count === 0) return null;
  return (
    <div className="border border-stone-200 rounded">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-stone-50"
      >
        <span className="text-sm font-medium text-stone-700">
          {title} ({count})
        </span>
        <svg
          className={`w-4 h-4 text-stone-400 transition-transform ${open ? "rotate-180" : ""}`}
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
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

function truncate(value: string, max = 60): string {
  if (!value) return "-";
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

export function EUFundingCard({
  prrFundings,
  prrContracts,
  prrTotalContracted,
  prrTotalPaid,
  pt2030Fundings,
  pt2030TotalFundApproved,
  pt2030TotalFundPaid,
}: Props) {
  const prrF = prrFundings ?? [];
  const prrC = prrContracts ?? [];
  const pt2030F = pt2030Fundings ?? [];

  const [prrProjectsCount, setPrrProjectsCount] = useState(INITIAL_ROWS);
  const [prrContractsCount, setPrrContractsCount] = useState(INITIAL_ROWS);
  const [pt2030Count, setPt2030Count] = useState(INITIAL_ROWS);

  const totalProjects = prrF.length + prrC.length + pt2030F.length;

  if (totalProjects === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 gap-2">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          EU Funding
          <span className="px-2 py-0.5 text-xs font-medium bg-brand-100 text-brand-700 rounded-full">
            {totalProjects}{" "}
            {totalProjects === 1 ? "project" : "projects"}
          </span>
        </h3>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <Stat label="PRR Contracted" value={formatEUR(prrTotalContracted)} />
        <Stat label="PRR Paid" value={formatEUR(prrTotalPaid)} />
        <Stat
          label="PT2030 Approved"
          value={formatEUR(pt2030TotalFundApproved)}
        />
        <Stat label="PT2030 Paid" value={formatEUR(pt2030TotalFundPaid)} />
      </div>

      <div className="space-y-2">
        <Section title="PRR Projects" count={prrF.length}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-stone-500 text-xs">
                  <th className="py-2 pr-3">Project</th>
                  <th className="py-2 pr-3">Role</th>
                  <th className="py-2 pr-3 whitespace-nowrap">Contracted</th>
                  <th className="py-2 pr-3 whitespace-nowrap">Paid</th>
                  <th className="py-2">Municipality</th>
                </tr>
              </thead>
              <tbody>
                {prrF.slice(0, prrProjectsCount).map((p, i) => (
                  <tr
                    key={`${p.project_code}-${i}`}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-3 font-mono text-xs">
                      {p.project_code || "-"}
                    </td>
                    <td className="py-2 pr-3 text-stone-600">
                      {p.role || "-"}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {formatEUR(p.value_contracted)}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {formatEUR(p.value_paid)}
                    </td>
                    <td className="py-2 text-stone-600">
                      {p.municipality || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {prrProjectsCount < prrF.length && (
              <button
                onClick={() =>
                  setPrrProjectsCount((c) => c + INITIAL_ROWS * 2)
                }
                className="mt-2 w-full py-1.5 text-xs text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors"
              >
                Show more ({prrProjectsCount} of {prrF.length})
              </button>
            )}
          </div>
        </Section>

        <Section title="PRR Public Contracts" count={prrC.length}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-stone-500 text-xs">
                  <th className="py-2 pr-3">Code</th>
                  <th className="py-2 pr-3">Description</th>
                  <th className="py-2 pr-3">Role</th>
                  <th className="py-2 whitespace-nowrap">Value</th>
                </tr>
              </thead>
              <tbody>
                {prrC.slice(0, prrContractsCount).map((c, i) => (
                  <tr
                    key={`${c.contract_code}-${i}`}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-3 font-mono text-xs">
                      {c.contract_code || "-"}
                    </td>
                    <td
                      className="py-2 pr-3 text-stone-700 max-w-xs"
                      title={c.description || undefined}
                    >
                      {truncate(c.description)}
                    </td>
                    <td className="py-2 pr-3 text-stone-600">
                      {c.role || "-"}
                    </td>
                    <td className="py-2 whitespace-nowrap">
                      {formatEUR(c.value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {prrContractsCount < prrC.length && (
              <button
                onClick={() =>
                  setPrrContractsCount((c) => c + INITIAL_ROWS * 2)
                }
                className="mt-2 w-full py-1.5 text-xs text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors"
              >
                Show more ({prrContractsCount} of {prrC.length})
              </button>
            )}
          </div>
        </Section>

        <Section title="PT2030 Operations" count={pt2030F.length}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-stone-500 text-xs">
                  <th className="py-2 pr-3">Operation</th>
                  <th className="py-2 pr-3">Role</th>
                  <th className="py-2 pr-3 whitespace-nowrap">Approved</th>
                  <th className="py-2 pr-3 whitespace-nowrap">Executed</th>
                  <th className="py-2 whitespace-nowrap">Paid</th>
                </tr>
              </thead>
              <tbody>
                {pt2030F.slice(0, pt2030Count).map((p, i) => (
                  <tr
                    key={`${p.operation_code}-${i}`}
                    className="border-b last:border-0"
                  >
                    <td className="py-2 pr-3 font-mono text-xs">
                      {p.operation_code || "-"}
                    </td>
                    <td className="py-2 pr-3 text-stone-600">
                      {p.role || "-"}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {formatEUR(p.fund_approved)}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {formatEUR(p.fund_executed)}
                    </td>
                    <td className="py-2 whitespace-nowrap">
                      {formatEUR(p.fund_paid)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {pt2030Count < pt2030F.length && (
              <button
                onClick={() => setPt2030Count((c) => c + INITIAL_ROWS * 2)}
                className="mt-2 w-full py-1.5 text-xs text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors"
              >
                Show more ({pt2030Count} of {pt2030F.length})
              </button>
            )}
          </div>
        </Section>
      </div>
    </div>
  );
}
