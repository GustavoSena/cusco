import { useState } from "react";
import type { LEIRecord } from "../types";

interface Props {
  record: LEIRecord;
}

export function LEICard({ record }: Props) {
  const [expanded, setExpanded] = useState(false);

  const isActive = record.entity_status === "ACTIVE";

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-start justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          LEI Record
          <span
            className={`px-2 py-0.5 text-xs font-bold rounded-full ${
              isActive
                ? "bg-green-100 text-green-700"
                : "bg-yellow-100 text-yellow-700"
            }`}
          >
            {record.entity_status || "UNKNOWN"}
          </span>
        </h3>
        <span className="font-mono text-xs text-stone-400 bg-stone-50 px-2 py-1 rounded">
          {record.lei}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            Legal Name
          </p>
          <p className="text-sm font-medium text-stone-900 mt-1">
            {record.legal_name}
          </p>
          {record.other_names.length > 0 && (
            <p className="text-xs text-stone-500 mt-0.5">
              Also: {record.other_names.slice(0, 3).join(", ")}
            </p>
          )}
        </div>
        <div>
          <p className="text-xs text-stone-500 uppercase tracking-wide">
            Registered Address
          </p>
          <p className="text-sm text-stone-700 mt-1">
            {[record.legal_address, record.legal_city, record.legal_postal_code]
              .filter(Boolean)
              .join(", ")}
          </p>
        </div>
      </div>

      {/* Expandable details */}
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="mt-3 text-xs text-brand-600 hover:text-brand-800"
      >
        {expanded ? "Hide details" : "Show more details"}
      </button>

      <div className="grid-expand" aria-hidden={!expanded}>
        <div className="mt-3 pt-3 border-t grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          {record.headquarters_address && (
            <div>
              <p className="text-xs text-stone-500">Headquarters</p>
              <p className="text-stone-700">
                {[record.headquarters_address, record.headquarters_city]
                  .filter(Boolean)
                  .join(", ")}
              </p>
            </div>
          )}
          <div>
            <p className="text-xs text-stone-500">Jurisdiction</p>
            <p className="text-stone-700">{record.jurisdiction || "-"}</p>
          </div>
          <div>
            <p className="text-xs text-stone-500">Registration Status</p>
            <p className="text-stone-700">{record.registration_status || "-"}</p>
          </div>
          <div>
            <p className="text-xs text-stone-500">First Registered</p>
            <p className="text-stone-700">
              {record.initial_registration_date || "-"}
            </p>
          </div>
          <div>
            <p className="text-xs text-stone-500">Last Updated</p>
            <p className="text-stone-700">{record.last_update_date || "-"}</p>
          </div>
          <div>
            <p className="text-xs text-stone-500">Next Renewal</p>
            <p className="text-stone-700">{record.next_renewal_date || "-"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
