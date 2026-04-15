import { useState } from "react";
import type { Contract } from "../types";

interface Props {
  contracts: Contract[];
  totalValue: number;
}

type SortField = "contract_price" | "signing_date" | "year";

const INITIAL_LIMIT = 10;
const LOAD_MORE_STEP = 20;

function formatEUR(value: number | null): string {
  if (value == null) return "-";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function ContractsList({ contracts, totalValue }: Props) {
  const [sortBy, setSortBy] = useState<SortField>("signing_date");
  const [sortDesc, setSortDesc] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(INITIAL_LIMIT);

  const sorted = [...contracts].sort((a, b) => {
    const dir = sortDesc ? -1 : 1;
    if (sortBy === "contract_price") {
      return dir * ((a.contract_price ?? 0) - (b.contract_price ?? 0));
    }
    if (sortBy === "year") {
      return dir * ((a.year ?? 0) - (b.year ?? 0));
    }
    return dir * (a.signing_date || "").localeCompare(b.signing_date || "");
  });

  const handleSort = (field: SortField) => {
    if (sortBy === field) setSortDesc(!sortDesc);
    else {
      setSortBy(field);
      setSortDesc(true);
    }
  };

  const visible = sorted.slice(0, visibleCount);
  const hasMore = visibleCount < contracts.length;

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex justify-between items-center mb-4 gap-2">
        <h3 className="text-base sm:text-lg font-semibold">
          Public Contracts
          <span className="ml-1.5 sm:ml-2 text-xs sm:text-sm font-normal text-stone-500">
            ({contracts.length})
          </span>
        </h3>
        <div className="text-right shrink-0">
          <p className="text-xs sm:text-sm text-stone-500">Total value</p>
          <p className="text-lg sm:text-xl font-bold text-brand-700">{formatEUR(totalValue)}</p>
        </div>
      </div>

      {contracts.length === 0 ? (
        <p className="text-stone-500 text-sm">No public contracts found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-stone-500 text-xs sm:text-sm">
                <th className="pb-2 pr-3 sm:pr-4">Description</th>
                <th className="pb-2 pr-3 sm:pr-4 hidden md:table-cell">Entity</th>
                <th
                  className="pb-2 pr-3 sm:pr-4 cursor-pointer hover:text-stone-900 select-none"
                  onClick={() => handleSort("contract_price")}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleSort("contract_price"); } }}
                  tabIndex={0}
                  role="columnheader"
                  aria-sort={sortBy === "contract_price" ? (sortDesc ? "descending" : "ascending") : "none"}
                >
                  Price {sortBy === "contract_price" && (sortDesc ? "\u2193" : "\u2191")}
                </th>
                <th className="pb-2 pr-3 sm:pr-4 hidden lg:table-cell">Procedure</th>
                <th
                  className="pb-2 cursor-pointer hover:text-stone-900 select-none"
                  onClick={() => handleSort("signing_date")}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleSort("signing_date"); } }}
                  tabIndex={0}
                  role="columnheader"
                  aria-sort={sortBy === "signing_date" ? (sortDesc ? "descending" : "ascending") : "none"}
                >
                  Date {sortBy === "signing_date" && (sortDesc ? "\u2193" : "\u2191")}
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c, i) => (
                <tr
                  key={c.id || `contract-${i}`}
                  className="border-b last:border-0 hover:bg-stone-50 cursor-pointer"
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                >
                  <td className="py-2.5 pr-3 sm:pr-4 max-w-[140px] sm:max-w-xs truncate text-xs sm:text-sm" title={c.object_description || undefined}>
                    {c.object_description || "-"}
                  </td>
                  <td className="py-2.5 pr-3 sm:pr-4 text-stone-600 hidden md:table-cell">
                    {c.contracting_entity || "-"}
                  </td>
                  <td className="py-2.5 pr-3 sm:pr-4 font-medium text-xs sm:text-sm whitespace-nowrap">
                    {formatEUR(c.contract_price)}
                  </td>
                  <td className="py-2.5 pr-3 sm:pr-4 text-stone-600 hidden lg:table-cell">{c.procedure_type || "-"}</td>
                  <td className="py-2.5 text-stone-600 text-xs sm:text-sm whitespace-nowrap">{c.signing_date || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {hasMore && (
            <button
              onClick={() => setVisibleCount((prev) => prev + LOAD_MORE_STEP)}
              className="mt-3 w-full py-2 text-sm text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors"
            >
              Show more ({visibleCount} of {contracts.length})
            </button>
          )}
          {!hasMore && contracts.length > INITIAL_LIMIT && (
            <button
              onClick={() => setVisibleCount(INITIAL_LIMIT)}
              className="mt-3 w-full py-2 text-sm text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded transition-colors"
            >
              Show less
            </button>
          )}
        </div>
      )}
    </div>
  );
}
