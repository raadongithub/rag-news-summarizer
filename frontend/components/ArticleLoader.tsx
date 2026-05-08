"use client";

import { useState } from "react";

interface Props {
  onLoad: (url: string) => void;
  isLoading: boolean;
  currentUrl: string | null;
}

export default function ArticleLoader({ onLoad, isLoading, currentUrl }: Props) {
  const [urlInput, setUrlInput] = useState(currentUrl || "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = urlInput.trim();
    if (trimmed) onLoad(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label
        htmlFor="article-url"
        className="block text-sm font-medium text-gray-700"
      >
        Article URL
      </label>
      <input
        id="article-url"
        type="url"
        value={urlInput}
        onChange={(e) => setUrlInput(e.target.value)}
        placeholder="https://example.com/news/article"
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
        disabled={isLoading}
      />
      <button type="submit" className="btn-primary w-full" disabled={isLoading || !urlInput.trim()}>
        {isLoading ? (
          <span className="flex items-center gap-2">
            <Spinner />
            Loading article…
          </span>
        ) : (
          "Load Article"
        )}
      </button>
    </form>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}
