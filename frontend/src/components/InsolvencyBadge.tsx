import type { InsolvencyProceeding } from "../types";

interface Props {
  proceedings: InsolvencyProceeding[];
  hasInsolvency: boolean;
}

export function InsolvencyBadge({ proceedings, hasInsolvency }: Props) {
  return (
    <div className="bg-white rounded-lg border p-6">
      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
        Insolvency Status
        {hasInsolvency ? (
          <span className="px-2 py-0.5 text-xs font-bold bg-red-100 text-red-700 rounded-full">
            PROCEEDINGS FOUND
          </span>
        ) : (
          <span className="px-2 py-0.5 text-xs font-bold bg-green-100 text-green-700 rounded-full">
            CLEAR
          </span>
        )}
      </h3>

      {proceedings.length > 0 ? (
        <div className="space-y-3">
          {proceedings.map((p, i) => (
            <div key={i} className="p-3 bg-red-50 border border-red-200 rounded">
              <div className="flex justify-between text-sm">
                <span className="font-medium">{p.process_number}</span>
                <span className="text-gray-500">{p.date}</span>
              </div>
              {p.court && <p className="text-sm text-gray-600 mt-1">{p.court}</p>}
              {p.description && <p className="text-sm mt-1">{p.description}</p>}
              {p.action_type && (
                <span className="inline-block mt-1 px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded">
                  {p.action_type}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-sm">
          No insolvency proceedings found in CITIUS.
        </p>
      )}
    </div>
  );
}
