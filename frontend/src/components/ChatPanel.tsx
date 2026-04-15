import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../api/client";
import type { ChatMessage, EntityReport } from "../types";

interface Props {
  report: EntityReport;
}

export function ChatPanel({ report }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;

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
          <span className="font-semibold text-stone-700">
            Ask about this company
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
                <p className="text-sm text-stone-400 text-center mt-8">
                  Ask a question about {report.company?.name || `NIF ${report.nif}`}
                </p>
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
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question..."
                aria-label="Ask a question about this company"
                disabled={isStreaming}
                className="flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:bg-stone-100"
              />
              <button
                type="submit"
                disabled={isStreaming || !input.trim()}
                className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 active:scale-[0.97] disabled:bg-stone-300 disabled:cursor-not-allowed transition-all duration-150"
              >
                {isStreaming ? "..." : "Send"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
