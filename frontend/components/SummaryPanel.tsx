"use client";

import type { ScrapedArticle } from "@/lib/api";

interface SummaryPanelProps {
  article: ScrapedArticle;
  summary: string | null;
  onGenerateSummary: () => void;
  onExpand: () => void;
  isSummarizing: boolean;
}

export default function SummaryPanel({
  article,
  summary,
  onGenerateSummary,
  onExpand,
  isSummarizing,
}: SummaryPanelProps) {
  const publishDate = article.publish_date
    ? new Date(article.publish_date).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <div className="space-y-4">
      <div className="card flex flex-col p-5" style={{ height: "28vh" }}>
        <div className="mb-4 flex items-start justify-between gap-4 shrink-0">
          <div>
            <h2 className="text-base font-semibold leading-snug text-slate-950">{article.title}</h2>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
              <span>{article.source_domain}</span>
              {article.authors.length > 0 && <span>{article.authors.join(", ")}</span>}
              {publishDate && <span>{publishDate}</span>}
              <span>{article.word_count.toLocaleString()} words</span>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {!summary && (
              <button
                className="btn-secondary text-xs py-1 px-3"
                onClick={onGenerateSummary}
                disabled={isSummarizing}
                type="button"
              >
                {isSummarizing ? "Generating..." : "Generate"}
              </button>
            )}
            <button className="btn-ghost" onClick={onExpand} type="button">
              Open canvas
            </button>
          </div>
        </div>

        <div className="mb-3 shrink-0">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
            Article Summary
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto">
          {summary ? (
            <p className="text-sm leading-7 text-slate-700">{summary}</p>
          ) : (
            <p className="text-sm italic text-slate-400">
              Click "Generate" to create a full article summary.
            </p>
          )}
        </div>
      </div>

      <div className="card flex flex-col p-5" style={{ height: "28vh" }}>
        <div className="mb-3 flex items-center justify-between gap-3 shrink-0">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
            Full Article Text
          </h3>
          <button className="btn-ghost" onClick={onExpand} type="button">
            Expand
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{article.content}</p>
        </div>
      </div>
    </div>
  );
}
