export function formatEUR(value: number | null | undefined): string {
  if (value == null) return "-";
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}
