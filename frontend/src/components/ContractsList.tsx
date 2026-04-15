import { useState } from "react";
import type { Contract } from "../types";

interface Props {
  contracts: Contract[];
  totalValue: number;
}

type SortField = "contract_price" | "signing_date" | "year";

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

  return (
    <div className="bg-white rounded-lg border p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">
          Public Contracts
          <span className="ml-2 text-sm font-normal text-gray-500">
            ({contracts.length} contracts)
          </span>
        </h3>
        <div className="text-right">
          <p className="text-sm text-gray-500">Total value</p>
          <p className="text-xl font-bold text-blue-600">{formatEUR(totalValue)}</p>
        </div>
      </div>

      {contracts.length === 0 ? (
        <p className="text-gray-500 text-sm">No public contracts found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2 pr-4">Description</th>
                <th className="pb-2 pr-4">Entity</th>
                <th
                  className="pb-2 pr-4 cursor-pointer hover:text-gray-900"
                  onClick={() => handleSort("contract_price")}
                >
                  Price {sortBy === "contract_price" && (sortDesc ? "v" : "^")}
                </th>
                <th className="pb-2 pr-4">Procedure</th>
                <th
                  className="pb-2 cursor-pointer hover:text-gray-900"
                  onClick={() => handleSort("signing_date")}
                >
                  Date {sortBy === "signing_date" && (sortDesc ? "v" : "^")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.slice(0, 50).map((c) => (
                <tr
                  key={c.id || Math.random()}
                  className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                >
                  <td className="py-2 pr-4 max-w-xs truncate">
                    {c.object_description || "-"}
                  </td>
                  <td className="py-2 pr-4 text-gray-600">
                    {c.contracting_entity || "-"}
                  </td>
                  <td className="py-2 pr-4 font-medium">
                    {formatEUR(c.contract_price)}
                  </td>
                  <td className="py-2 pr-4 text-gray-600">{c.procedure_type || "-"}</td>
                  <td className="py-2 text-gray-600">{c.signing_date || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {contracts.length > 50 && (
            <p className="mt-2 text-sm text-gray-400">
              Showing 50 of {contracts.length} contracts
            </p>
          )}
        </div>
      )}
    </div>
  );
}
