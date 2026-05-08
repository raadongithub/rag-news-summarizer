"use client";

import { useState } from "react";
import type { ScrapedArticle } from "@/lib/api";

interface Props {
  article: ScrapedArticle;
  summary: string | null;
  onGenerateSummary: () => void;
  isSummarizing: boolean;
}

export default function SummaryPanel({
  article,
  summary,
  onGenerateSummary,
  isSummarizing,
}: Props) {
  const [contentExpanded, setContentExpanded] = useState(false);

  const publishDate = article.publish_date
    ? new Date(article.publish_date).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <div className="space-y-4">
      {/* Article metadata */}
      <div className="card p-4 space-y-2">
        <h2 className="font-semibold text-gray-900 text-base leading-snug">
          {article.title}
        </h2>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
          <span>{article.source_domain}</span>
          {article.authors.length > 0 && (
            <span>{article.authors.join(", ")}</span>
          )}
          {publishDate && <span>{publishDate}</span>}
          <span>{article.word_count.toLocaleString()} words</span>
        </div>
      </div>

      {/* Full article summary */}
      <div className="card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Article Summary
          </h3>
          {!summary && (
            <button
              className="btn-secondary text-xs py-1 px-3"
              onClick={onGenerateSummary}
              disabled={isSummarizing}
            >
              {isSummarizing ? "Generating…" : "Generate"}
            </button>
          )}
        </div>

        {summary ? (
          <p className="text-sm text-gray-700 leading-relaxed">{summary}</p>
        ) : (
          <p className="text-sm text-gray-400 italic">
            Click &ldquo;Generate&rdquo; to create a full article summary.
          </p>
        )}
      </div>

      {/* Raw article content (collapsible) */}
      <div className="card overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          onClick={() => setContentExpanded((v) => !v)}
        >
          <span>Full Article Text</span>
          <ChevronIcon expanded={contentExpanded} />
        </button>
        {contentExpanded && (
          <div className="px-4 pb-4 border-t border-gray-100">
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap mt-3">
              {article.content}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`h-4 w-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}
