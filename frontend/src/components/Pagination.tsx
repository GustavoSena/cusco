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
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalPages <= 1) return null;

  const start = page * pageSize + 1;
  const end = Math.min(totalItems, (page + 1) * pageSize);

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
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
          className="px-2 py-1 rounded border border-stone-200 text-stone-600 hover:bg-stone-50 hover:border-stone-300 disabled:opacity-40 disabled:hover:bg-white disabled:hover:border-stone-200 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          ←
        </button>
        <span className="tabular-nums px-2" aria-live="polite">
          {page + 1} / {totalPages}
        </span>
        <button
          type="button"
          aria-label="Next page"
          onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
          disabled={page >= totalPages - 1}
          className="px-2 py-1 rounded border border-stone-200 text-stone-600 hover:bg-stone-50 hover:border-stone-300 disabled:opacity-40 disabled:hover:bg-white disabled:hover:border-stone-200 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1"
        >
          →
        </button>
      </div>
    </nav>
  );
}
