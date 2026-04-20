interface Props {
  page: number; // 0-indexed
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  /**
   * Optional: label the controls for assistive tech (e.g. "Contracts pagination").
   * Falls back to a generic label if omitted.
   */
  label?: string;
}

/**
 * Compact prev/next pagination for in-card lists.
 * Shows "X-Y of Z" + buttons; collapses to nothing when there's only one page.
 */
export function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
  label = "Pagination",
}: Props) {
  if (totalItems <= 0) return null;
  // Defensive: clamp pageSize and page against stale/invalid inputs so the
  // rendered labels never lie. The click handlers already clamp when
  // firing, but a parent passing page=99 after shrinking the dataset
  // would otherwise render "496–8 of 8" until the next render cycle.
  const safePageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(totalItems / safePageSize));
  if (totalPages <= 1) return null;

  const currentPage = Math.min(Math.max(0, page), totalPages - 1);
  const start = currentPage * safePageSize + 1;
  const end = Math.min(totalItems, (currentPage + 1) * safePageSize);

  return (
    <nav
      aria-label={label}
      className="mt-3 flex items-center justify-between gap-2 text-xs text-stone-500"
    >
      <span>
        {start.toLocaleString("pt-PT")}–{end.toLocaleString("pt-PT")} of{" "}
        {totalItems.toLocaleString("pt-PT")}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Previous page"
          onClick={() => onPageChange(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0}
          className="px-2 py-1 rounded border border-stone-200 text-stone-600 hover:bg-stone-50 hover:border-stone-300 disabled:opacity-40 disabled:hover:bg-white disabled:hover:border-stone-200 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          ←
        </button>
        <span className="tabular-nums px-2" aria-live="polite">
          {currentPage + 1} / {totalPages}
        </span>
        <button
          type="button"
          aria-label="Next page"
          onClick={() => onPageChange(Math.min(totalPages - 1, currentPage + 1))}
          disabled={currentPage >= totalPages - 1}
          className="px-2 py-1 rounded border border-stone-200 text-stone-600 hover:bg-stone-50 hover:border-stone-300 disabled:opacity-40 disabled:hover:bg-white disabled:hover:border-stone-200 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          →
        </button>
      </div>
    </nav>
  );
}
