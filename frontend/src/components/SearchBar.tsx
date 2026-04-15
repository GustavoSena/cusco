import { useState } from "react";

interface Props {
  onSearch: (nif: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = input.replace(/\s/g, "");
    if (cleaned.length === 9 && /^\d+$/.test(cleaned)) {
      onSearch(cleaned);
    }
  };

  const isValidNif = /^\d{9}$/.test(input.replace(/\s/g, ""));

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter a 9-digit NIF (e.g. 500697256)"
            className="w-full px-4 py-3 bg-white border border-gray-300 rounded-lg text-lg
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       placeholder:text-gray-400"
            maxLength={9}
          />
          {input && !isValidNif && (
            <p className="absolute -bottom-6 left-1 text-sm text-red-500">
              NIF must be exactly 9 digits
            </p>
          )}
        </div>
        <button
          type="submit"
          disabled={!isValidNif || loading}
          className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg
                     hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                     transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Searching...
            </span>
          ) : (
            "Search"
          )}
        </button>
      </div>
    </form>
  );
}
