import type { EntityReport } from "../types";

const BASE = "/api";

export async function searchByNif(nif: string): Promise<EntityReport> {
  const res = await fetch(`${BASE}/search?nif=${encodeURIComponent(nif)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
