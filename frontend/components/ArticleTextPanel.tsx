"use client";

import { useState } from "react";

interface ArticleTextPanelProps {
  content: string;
  /** Initial open state. Defaults to false so the panel starts collapsed. */
  defaultOpen?: boolean;
}

/**
 * Collapsible panel that shows the raw article text.
 *
 * The header bar is always visible so the panel stays discoverable. Clicking
 * the header (or the chevron) toggles the content area open/closed with a
 * smooth CSS grid-row animation.
 */
export default function ArticleTextPanel({
  content,
  defaultOpen = false,
}: ArticleTextPanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="card overflow-hidden">
      {/* Always-visible header / toggle ──────────────────── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left transition hover:bg-slate-50/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
      >
        <div className="flex items-center gap-2">
          <ArticleIcon />
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">
            Full Article Text
          </span>
        </div>
        <ChevronIcon open={open} />
      </button>

      {/* Collapsible content — grid-rows trick for smooth animation ─ */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          {/* Inner wrapper gives the scrollable reading area a fixed height */}
          <div className="border-t border-slate-100 px-5 py-4">
            <div className="max-h-[55vh] overflow-y-auto pr-1">
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">
                {content}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ArticleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5 shrink-0 text-slate-400"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M4 4a2 2 0 0 1 2-2h4.586A2 2 0 0 1 12 2.586L15.414 6A2 2 0 0 1 16 7.414V16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Zm2 6a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 6 10Zm0 2.5a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5a.75.75 0 0 1-.75-.75Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-300 ${
        open ? "rotate-180" : ""
      }`}
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
        clipRule="evenodd"
      />
    </svg>
  );
}
