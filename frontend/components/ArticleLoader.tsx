"use client";

import { useEffect, useState } from "react";

interface ArticleLoaderProps {
  onLoad: (url: string) => void;
  isLoading: boolean;
  currentUrl: string | null;
}

export default function ArticleLoader({
  onLoad,
  isLoading,
  currentUrl,
}: ArticleLoaderProps) {
  const [urlInput, setUrlInput] = useState(currentUrl || "");

  useEffect(() => {
    setUrlInput(currentUrl || "");
  }, [currentUrl]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = urlInput.trim();
    if (trimmed) {
      onLoad(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label htmlFor="article-url" className="block text-sm font-medium text-slate-700">
        Article URL
      </label>
      <input
        id="article-url"
        type="url"
        value={urlInput}
        onChange={(event) => setUrlInput(event.target.value)}
        placeholder="https://example.com/news/article"
        className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400"
        disabled={isLoading}
      />
      <button type="submit" className="btn-primary w-full" disabled={isLoading || !urlInput.trim()}>
        {isLoading ? (
          <span className="flex items-center gap-2">
            <Spinner />
            Loading article...
          </span>
        ) : (
          "Load article"
        )}
      </button>
    </form>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-white"
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
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
