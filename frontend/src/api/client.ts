import type { ChatMessage, EntityReport, NameSearchResult } from "../types";

const BASE = "/api";

export async function searchByNif(nif: string): Promise<EntityReport> {
  const res = await fetch(`${BASE}/search?nif=${encodeURIComponent(nif)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function searchByNifStream(
  nif: string,
  onUpdate: (report: EntityReport) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/search/stream?nif=${encodeURIComponent(nif)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      try {
        onUpdate(JSON.parse(data));
      } catch {
        // Skip malformed SSE events
      }
    }
  }
}

export async function searchByName(name: string): Promise<NameSearchResult> {
  const res = await fetch(`${BASE}/search?name=${encodeURIComponent(name)}`);
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

export async function fetchConfig(): Promise<{
  ai_overview_available: boolean;
  chat_available: boolean;
}> {
  const res = await fetch(`${BASE}/config`);
  if (!res.ok) return { ai_overview_available: false, chat_available: false };
  return res.json();
}

export interface OverviewHandlers {
  onChunk: (text: string) => void;
  onError?: (message: string) => void;
}

export async function streamOverview(
  report: EntityReport,
  handlers: OverviewHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/overview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    // SSE events are separated by double newlines; split on that boundary
    // so that data: payloads containing single newlines stay intact.
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      if (!event.startsWith("data: ")) continue;
      const data = event.slice(6);
      try {
        const parsed = JSON.parse(data) as
          | { type: "chunk"; text: string }
          | { type: "error"; message: string }
          | { type: "done" };
        if (parsed.type === "chunk") {
          handlers.onChunk(parsed.text);
        } else if (parsed.type === "error") {
          handlers.onError?.(parsed.message);
        } else if (parsed.type === "done") {
          return;
        }
      } catch {
        // Skip malformed event
      }
    }
  }
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  report: EntityReport,
  onChunk: (text: string) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, report }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Error ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      try {
        onChunk(data);
      } catch {
        // Skip malformed SSE events
      }
    }
  }
}
