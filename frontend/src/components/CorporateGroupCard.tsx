import { useEffect, useState } from "react";
import type { CorporateGroup, GroupMember } from "../types";
import { Pagination } from "./Pagination";

interface Props {
  group: CorporateGroup;
  onSelectNif: (nif: string) => void;
}

const PAGE_SIZE = 5;

function StatusBadge({ status }: { status: string }) {
  if (!status) return null;
  const isActive = status === "ACTIVE";
  return (
    <span
      className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
        isActive
          ? "bg-green-100 text-green-700"
          : "bg-yellow-100 text-yellow-700"
      }`}
    >
      {status}
    </span>
  );
}

function CountryBadge({ country }: { country: string }) {
  if (!country) return null;
  return (
    <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-stone-100 text-stone-600">
      {country}
    </span>
  );
}

function MemberRow({
  member,
  onSelectNif,
}: {
  member: GroupMember;
  onSelectNif: (nif: string) => void;
}) {
  // Searchable = PT company that actually has a NIF we can query.
  // Two separate "not searchable" reasons: the entity is foreign (can't
  // look it up against PT-only datasets), OR it's PT but the upstream
  // source didn't include a NIF for it (nothing to query with). We
  // distinguish the two so the former isn't mislabelled as the latter
  // — a PT subsidiary with an empty NIF should not read as "non-PT".
  const isSearchablePT = member.country === "PT" && !!member.nif;
  const unavailableReason =
    member.country === "PT" ? "missing NIF" : "non-PT";
  const unavailableTitle =
    member.country === "PT"
      ? "PT entity — not searchable because no NIF is available for it"
      : "Foreign entity — not searchable in this tool";

  const content = (
    <div className="flex items-start justify-between gap-3 w-full">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-stone-900 truncate">
          {member.name || "Unknown"}
        </p>
        <div className="mt-1 flex items-center gap-2 flex-wrap">
          {member.nif && (
            <span className="font-mono text-xs text-stone-500">
              NIF {member.nif}
            </span>
          )}
          <CountryBadge country={member.country} />
          <StatusBadge status={member.entity_status} />
          {!isSearchablePT && (
            <span className="text-[10px] text-stone-400">
              {unavailableReason}
            </span>
          )}
        </div>
        {member.lei && (
          <p className="mt-1 font-mono text-[11px] text-stone-400 truncate">
            LEI: {member.lei}
          </p>
        )}
      </div>
    </div>
  );

  if (isSearchablePT) {
    return (
      <button
        type="button"
        onClick={() => onSelectNif(member.nif)}
        className="w-full text-left p-3 rounded border border-stone-200 bg-stone-50 hover:bg-brand-50 hover:border-brand-200 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1"
      >
        {content}
      </button>
    );
  }

  // Non-searchable member — display only. Visually dimmed + no hover
  // affordance so users understand it isn't interactive.
  return (
    <div
      className="w-full p-3 rounded border border-dashed border-stone-200 bg-stone-50/60 opacity-80"
      title={unavailableTitle}
    >
      {content}
    </div>
  );
}

export function CorporateGroupCard({ group, onSelectNif }: Props) {
  const children = group.children ?? [];
  const [page, setPage] = useState(0);

  // Reset pagination when the children array identity changes — a
  // different NIF with the same child count would otherwise leave
  // the user on a stale page index.
  useEffect(() => {
    setPage(0);
  }, [children]);

  if (!group.parent && children.length === 0) return null;

  // Clamp against the current length on render so an out-of-range
  // page (from an unrelated parent re-render) doesn't slice into nothing.
  const totalPages = Math.max(1, Math.ceil(children.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const visible = children.slice(
    currentPage * PAGE_SIZE,
    (currentPage + 1) * PAGE_SIZE,
  );

  return (
    <div className="bg-white rounded-lg border border-stone-200 p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 gap-2">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          Corporate Group
          {group.total_children > 0 && (
            <span className="px-2 py-0.5 text-xs font-medium bg-brand-100 text-brand-700 rounded-full">
              {group.total_children}{" "}
              {group.total_children === 1 ? "company" : "companies"}
            </span>
          )}
        </h3>
      </div>

      <div className="space-y-4">
        {group.parent && (
          <div>
            <p className="text-xs text-stone-500 uppercase tracking-wide mb-2">
              Parent company
            </p>
            <MemberRow member={group.parent} onSelectNif={onSelectNif} />
          </div>
        )}

        {children.length > 0 && (
          <div>
            <p className="text-xs text-stone-500 uppercase tracking-wide mb-2">
              Subsidiaries ({children.length})
            </p>
            <div className="space-y-2">
              {visible.map((child, i) => (
                <MemberRow
                  key={`${child.lei || child.nif || "m"}-${i}`}
                  member={child}
                  onSelectNif={onSelectNif}
                />
              ))}
            </div>
            <Pagination
              page={currentPage}
              pageSize={PAGE_SIZE}
              totalItems={children.length}
              onPageChange={setPage}
              label="Subsidiaries pagination"
            />
            {group.has_more_children && (
              <p className="mt-2 text-xs text-stone-400 text-center">
                +{group.total_children - children.length} more subsidiaries not
                shown (GLEIF pagination limit)
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
