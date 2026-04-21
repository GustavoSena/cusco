import { useState } from "react";
import type { MunicipalityContract } from "../types";
import { formatEUR } from "../format";

interface Props {
  municipalities: MunicipalityContract[];
}

const INITIAL_LIMIT = 10;

export function MunicipalitiesCard({ municipalities }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!municipalities || municipalities.length === 0) return null;

  const visible = expanded ? municipalities : municipalities.slice(0, INITIAL_LIMIT);
  const hasMore = municipalities.length > INITIAL_LIMIT;
  const totalValue = municipalities.reduce((sum, m) => sum + m.total_value, 0);
  const totalContracts = municipalities.reduce(
    (sum, m) => sum + m.contract_count,
    0,
  );

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 gap-2">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          Sales to Municipalities
          <span className="px-2 py-0.5 text-xs font-medium bg-brand-100 text-brand-700 rounded-full">
            {municipalities.length}{" "}
            {municipalities.length === 1 ? "municipality" : "municipalities"}
          </span>
        </h3>
        <div className="text-right shrink-0">
          <p className="text-xs text-stone-500">Total value</p>
          <p className="text-base sm:text-lg font-bold text-brand-700">
            {formatEUR(totalValue)}
          </p>
        </div>
      </div>

      <p className="text-xs text-stone-500 mb-3">
        Public contracts where this company supplied a Portuguese municipality
        ({totalContracts.toLocaleString("pt-PT")} contract
        {totalContracts !== 1 ? "s" : ""}, ranked by value).
      </p>

      <ol className="space-y-1.5">
        {visible.map((m, i) => (
          <li
            key={m.nif}
            className="flex items-center justify-between gap-3 p-2 rounded border border-stone-100 bg-stone-50/60"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs font-mono text-stone-400 w-6 shrink-0 text-right">
                {i + 1}
              </span>
              <div className="min-w-0">
                <p className="text-sm text-stone-800 truncate" title={m.name}>
                  {m.name}
                </p>
                <p className="text-xs text-stone-500">
                  NIF {m.nif} · {m.contract_count} contract
                  {m.contract_count !== 1 ? "s" : ""}
                </p>
              </div>
            </div>
            <span className="font-medium text-sm text-stone-700 whitespace-nowrap shrink-0">
              {formatEUR(m.total_value)}
            </span>
          </li>
        ))}
      </ol>

      {hasMore && !expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-3 w-full py-1.5 text-xs text-brand-600 hover:text-brand-800 hover:bg-brand-50 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          Show {municipalities.length - INITIAL_LIMIT} more
        </button>
      )}
      {expanded && hasMore && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="mt-3 w-full py-1.5 text-xs text-stone-500 hover:text-stone-700 hover:bg-stone-50 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          Show less
        </button>
      )}
    </div>
  );
}
