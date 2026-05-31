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

  const metaParts = [
    article.source_domain,
    article.authors.length > 0 ? article.authors.join(", ") : null,
    publishDate,
    `${article.word_count.toLocaleString()} words`,
  ].filter(Boolean) as string[];

  return (
    <div className="card flex flex-col overflow-hidden">
      {/* Article identity */}
      <div className="shrink-0 border-b border-slate-100 px-5 pt-5 pb-4">
        <h2 className="text-base font-semibold leading-snug text-slate-950">
          {article.title}
        </h2>

        {metaParts.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
            {metaParts.map((part, i) => (
              <span key={i} className="flex items-center gap-1.5 text-xs text-slate-500">
                {i > 0 && <span className="text-slate-300" aria-hidden="true">·</span>}
                {part}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Summary content */}
      <div className="flex min-h-0 flex-1 flex-col px-5 pt-4 pb-3">
        <p className="mb-3 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Summary
        </p>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {summary ? (
            <p className="text-sm leading-7 text-slate-700">{summary}</p>
          ) : isSummarizing ? (
            <p className="text-sm italic text-slate-400">Generating summary…</p>
          ) : null}
        </div>
      </div>

      {/* Action row */}
      <div className="shrink-0 border-t border-slate-100 px-5 py-3 flex items-center justify-end gap-2">
        {!summary && (
          <button
            className="btn-secondary py-1.5 px-3 text-xs"
            onClick={onGenerateSummary}
            disabled={isSummarizing}
            type="button"
          >
            {isSummarizing ? (
              <span className="flex items-center gap-1.5">
                <SpinnerIcon />
                Generating…
              </span>
            ) : (
              "Generate summary"
            )}
          </button>
        )}
        {summary && (
          <button className="btn-ghost" onClick={onExpand} type="button">
            Open canvas
          </button>
        )}
      </div>
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="h-3 w-3 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
