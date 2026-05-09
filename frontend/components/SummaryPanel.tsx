"use client";

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
      <div className="card p-4 space-y-2 shrink-0">
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

      {/* Article Summary — fixed height, scrollable */}
      <div className="card p-4 flex flex-col" style={{ height: "22vh" }}>
        <div className="flex items-center justify-between shrink-0 mb-3">
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

        <div className="flex-1 overflow-y-auto">
          {summary ? (
            <p className="text-sm text-gray-700 leading-relaxed">{summary}</p>
          ) : (
            <p className="text-sm text-gray-400 italic">
              Click &ldquo;Generate&rdquo; to create a full article summary.
            </p>
          )}
        </div>
      </div>

      {/* Full Article Text — fixed height, scrollable */}
      <div className="card p-4 flex flex-col" style={{ height: "32vh" }}>
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide shrink-0 mb-3">
          Full Article Text
        </h3>
        <div className="flex-1 overflow-y-auto">
          <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
            {article.content}
          </p>
        </div>
      </div>
    </div>
  );
}
