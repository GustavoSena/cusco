import { useState } from "react";
import type { SegSocialOrganism, SegSocialProcedure } from "../types";

interface Props {
  procedures: SegSocialProcedure[];
  organisms: SegSocialOrganism[];
}

const DEFAULT_VISIBLE = 3;

/**
 * Segurança Social public-sector recruitment activity.
 *
 * The backend populates `seg_social_procedures` + `seg_social_organisms`
 * for every NIF search, but nothing was rendering them — so the feature
 * shipped invisible. This card surfaces the top procedures (most
 * recent first by publication date when available) with a "show more"
 * toggle since some public entities have dozens of open procedures.
 *
 * Treated as supplementary data: if there's nothing to show, the whole
 * card disappears (rather than rendering an empty "no data" state that
 * would clutter pages for private companies).
 */
export function SegSocialCard({ procedures, organisms }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!procedures.length && !organisms.length) return null;

  const visible = expanded ? procedures : procedures.slice(0, DEFAULT_VISIBLE);
  const hiddenCount = Math.max(0, procedures.length - DEFAULT_VISIBLE);

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h3 className="text-base sm:text-lg font-semibold">
          Segurança Social activity
          {procedures.length > 0 && (
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-stone-100 text-stone-600 rounded-full">
              {procedures.length}{" "}
              {procedures.length === 1 ? "procedure" : "procedures"}
            </span>
          )}
        </h3>
      </div>

      {procedures.length > 0 ? (
        <div className="space-y-2">
          {visible.map((p, i) => (
            <div
              key={`${p.code || "p"}-${i}`}
              className="p-3 rounded border border-stone-100 bg-stone-50"
            >
              <p className="text-sm font-medium text-stone-900">
                {p.title || "Untitled procedure"}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
                {p.code && (
                  <span className="font-mono">{p.code}</span>
                )}
                {p.procedure_type && <span>{p.procedure_type}</span>}
                {p.career && <span>· {p.career}</span>}
                {p.publication_date && (
                  <span className="text-stone-400">
                    Published {p.publication_date}
                  </span>
                )}
                {p.organism_acronym && (
                  <span className="px-1.5 py-0.5 bg-white border border-stone-200 rounded text-stone-600">
                    {p.organism_acronym}
                  </span>
                )}
              </div>
            </div>
          ))}

          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              className="w-full text-center text-xs text-brand-700 hover:text-brand-900 hover:bg-brand-50 py-2 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
            >
              {expanded ? "Show fewer" : `Show ${hiddenCount} more`}
            </button>
          )}
        </div>
      ) : (
        // Entity has organism links but no open procedures — show a
        // single muted line rather than the full empty card state.
        <p className="text-sm text-stone-500">
          No open recruitment procedures.
        </p>
      )}

      {organisms.length > 0 && (
        <div className="mt-4 pt-3 border-t border-stone-100">
          <p className="text-xs text-stone-500 uppercase tracking-wide mb-2">
            Linked organisms
          </p>
          <div className="flex flex-wrap gap-1.5">
            {organisms.map((o) => (
              <span
                key={o.id}
                title={o.name}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] bg-stone-100 text-stone-700 rounded"
              >
                <span className="font-medium">{o.acronym || o.name}</span>
                {o.procedure_count > 0 && (
                  <span className="text-stone-500">({o.procedure_count})</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
