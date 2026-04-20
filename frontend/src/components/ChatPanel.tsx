import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../api/client";
import type { ChatMessage, EntityReport } from "../types";

interface Props {
  report: EntityReport;
  /**
   * When true, the report is still streaming — render the chat shell
   * but keep the input disabled and show a spinner. Mounting the panel
   * from the first partial report (instead of after loading finishes)
   * makes it clear to the user that chat will be ready shortly,
   * instead of the panel silently appearing later.
   */
  loading?: boolean;
}

export function ChatPanel({ report, loading = false }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Chat is disabled while the report is still loading (we don't have a
  // full snapshot to send as context yet) or while a previous message
  // is already streaming. `disabledReason` surfaces why, for the input
  // placeholder and the `title` tooltip on the Send button.
  const disabled = loading || isStreaming;
  const disabledReason = loading
    ? "Chat is available once the report finishes loading"
    : isStreaming
      ? "Waiting for the current answer to finish"
      : "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || disabled) return;

    setError(null);
    setInput("");

    const userMsg: ChatMessage = { role: "user", content: text };
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    // History to send: all complete messages (exclude the new placeholder)
    const history = [...messages, userMsg].filter((m) => m.content.length > 0);

    try {
      await sendChatMessage(text, history, report, (chunk) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = {
            ...last,
            content: last.content + chunk,
          };
          return updated;
        });
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="bg-white rounded-lg border border-stone-200">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-expanded={isExpanded}
          aria-controls="chat-panel-content"
          className="w-full flex items-center justify-between p-4 text-left hover:bg-stone-50 transition-colors"
        >
          <span className="font-semibold text-stone-700 flex items-center gap-2">
            Ask about this company
            {loading && (
              // Inline spinner next to the header so the reason for the
              // disabled input is visible even when the panel is collapsed.
              <span
                className="inline-flex items-center gap-1 text-xs font-normal text-stone-400"
                role="status"
                aria-live="polite"
              >
                <span className="inline-block w-3 h-3 border-2 border-stone-300 border-t-brand-500 rounded-full animate-spin" />
                <span>preparing…</span>
              </span>
            )}
          </span>
          <svg
            className={`w-5 h-5 text-stone-400 transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>

        <div
          id="chat-panel-content"
          className="grid-expand"
          aria-hidden={!isExpanded}
        >
          <div className="border-t">
            <div className="h-64 sm:h-80 overflow-y-auto p-3 sm:p-4 space-y-3">
              {messages.length === 0 && (
                <div className="text-center mt-8">
                  {loading ? (
                    // Mounted-but-not-ready state: the user sees the chat
                    // shell as soon as any partial report is on screen,
                    // with clear feedback that it will become interactive
                    // once the report finishes streaming.
                    <div
                      className="flex flex-col items-center gap-3"
                      role="status"
                      aria-live="polite"
                    >
                      <span className="inline-block w-6 h-6 border-2 border-stone-200 border-t-brand-500 rounded-full animate-spin" />
                      <p className="text-sm text-stone-400">
                        Chat will be available once the report finishes loading.
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm text-stone-400">
                      Ask a question about{" "}
                      {report.company?.name || `NIF ${report.nif}`}
                    </p>
                  )}
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-brand-600 text-white"
                        : "bg-stone-100 text-stone-800"
                    }`}
                  >
                    {msg.content}
                    {msg.role === "assistant" &&
                      msg.content === "" &&
                      isStreaming && (
                        <span className="inline-block w-2 h-4 bg-stone-400 animate-pulse" />
                      )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="mx-4 mb-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                {error}
              </div>
            )}

            <form
              onSubmit={handleSubmit}
              className="border-t p-3 flex gap-2"
              aria-busy={loading}
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  loading
                    ? "Waiting for report to finish loading…"
                    : "Ask a question..."
                }
                aria-label="Ask a question about this company"
                title={disabledReason || undefined}
                disabled={disabled}
                className="flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:bg-stone-100 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={disabled || !input.trim()}
                title={disabledReason || undefined}
                className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 active:scale-[0.97] disabled:bg-stone-300 disabled:cursor-not-allowed transition-all duration-150"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-1">
                    <span className="inline-block w-3 h-3 border-2 border-white/60 border-t-white rounded-full animate-spin" />
                  </span>
                ) : isStreaming ? (
                  "..."
                ) : (
                  "Send"
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
