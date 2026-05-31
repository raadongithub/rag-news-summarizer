"use client";

import type { ScrapedArticle } from "@/lib/api";

interface SummaryPanelProps {
  article: ScrapedArticle;
  summary: string | null;
  onGenerateSummary: () => void;
  onExpand: () => void;
  isSummarizing: boolean;
}

/**
 * Render article metadata, summary content, and summary actions.
 *
 * Parameters
 * ----------
 * article : ScrapedArticle
 *     Loaded article whose metadata is shown in the summary card.
 * summary : string | null
 *     Generated summary text. When null, summary content is hidden.
 * onGenerateSummary : () => void
 *     Callback used to start summary generation.
 * onExpand : () => void
 *     Callback used to open the expanded canvas view.
 * isSummarizing : boolean
 *     Indicates whether summary generation is currently in progress.
 *
 * Returns
 * -------
 * JSX.Element
 *     Summary panel card for the article workspace.
 */
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

  const metadata = [
    { label: "Source", value: article.source_domain || "Unknown" },
    {
      label: "Authors",
      value: article.authors.length > 0 ? article.authors.join(", ") : "Unknown",
    },
    { label: "Published", value: publishDate || "Unknown" },
    { label: "Length", value: `${article.word_count.toLocaleString()} words` },
  ];
  const hasSummaryContent = Boolean(summary || isSummarizing);

  return (
    <div className="card flex flex-col overflow-hidden">
      {/* Article metadata */}
      <div className="shrink-0 border-b border-slate-100 px-5 pt-5 pb-4">
        <div className="space-y-2">
          {metadata.map((item) => (
            <div key={item.label} className="grid grid-cols-[80px_1fr] items-start gap-2 text-xs">
              <span className="font-semibold uppercase tracking-wide text-slate-400">
                {item.label}
              </span>
              <span className="text-slate-600">{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {hasSummaryContent && (
        <div className="flex min-h-0 flex-1 flex-col px-5 pt-4 pb-3">
          {summary && (
            <p className="mb-3 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Summary
            </p>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {summary ? (
              <p className="text-sm leading-7 text-slate-700">{summary}</p>
            ) : isSummarizing ? (
              <p className="text-sm italic text-slate-400">Generating summary…</p>
            ) : null}
          </div>
        </div>
      )}

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
