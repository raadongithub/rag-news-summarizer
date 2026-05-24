"use client";

import { useEffect } from "react";

import type { Passage, ScrapedArticle } from "@/lib/api";

interface ExpandedCanvasProps {
  article: ScrapedArticle;
  summary: string | null;
  contextTitle?: string;
  contextBody?: string;
  contextLabel?: string;
  passages?: Passage[];
  onClose: () => void;
}

export default function ExpandedCanvas({
  article,
  summary,
  contextTitle,
  contextBody,
  contextLabel,
  passages = [],
  onClose,
}: ExpandedCanvasProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  const showContext = Boolean(contextTitle && contextBody && contextLabel);

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/55 p-3 backdrop-blur-sm sm:p-6">
      <div className="relative flex h-full flex-col overflow-hidden rounded-[2rem] border border-slate-200/70 bg-[radial-gradient(circle_at_top_left,_rgba(125,211,252,0.18),_transparent_28%),linear-gradient(180deg,_#ffffff_0%,_#f8fafc_100%)] shadow-[0_40px_120px_-40px_rgba(15,23,42,0.6)]">
        <button
          className="absolute right-4 top-4 z-10 inline-flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white/90 text-slate-700 shadow-sm transition hover:bg-white hover:text-slate-950"
          onClick={onClose}
          aria-label="Close expanded canvas"
          type="button"
        >
          <CloseIcon />
        </button>

        <div className="grid h-full grid-cols-1 gap-0 xl:grid-cols-[0.95fr_1.05fr]">
          <section className="border-b border-slate-200/80 px-6 pb-6 pt-20 xl:border-b-0 xl:border-r">
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-700">
                Focus view
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                {article.title}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {article.source_domain}
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-1">
              <div className="rounded-[1.5rem] border border-slate-200 bg-white/80 p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  Generated summary
                </p>
                <p className="mt-3 text-sm leading-7 text-slate-700">
                  {summary || "Generate a summary to see it here."}
                </p>
              </div>

              {showContext && (
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-950 p-5 text-slate-50 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-200">
                    {contextLabel}
                  </p>
                  <h3 className="mt-3 text-lg font-semibold">{contextTitle}</h3>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200/90">
                    {contextBody}
                  </p>
                </div>
              )}

              {passages.length > 0 && (
                <div className="rounded-[1.5rem] border border-emerald-200 bg-emerald-50/70 p-5 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                    Supporting passages
                  </p>
                  <div className="mt-4 space-y-3">
                    {passages.map((passage, index) => (
                      <div
                        key={`${passage.rank}-${index}`}
                        className="rounded-2xl border border-emerald-100 bg-white/85 p-4"
                      >
                        <div className="mb-2 flex items-center justify-between gap-3 text-xs text-emerald-800">
                          <span>Passage {index + 1}</span>
                          <span>{(passage.similarity_score * 100).toFixed(0)}% match</span>
                        </div>
                        <p className="text-sm leading-6 text-slate-700">{passage.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="min-h-0 px-6 pb-6 pt-8 xl:pt-20">
            <div className="flex h-full flex-col rounded-[1.75rem] border border-slate-200 bg-white/75 shadow-inner">
              <div className="border-b border-slate-200 px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  Full article text
                </p>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                  {article.content}
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M6 6l12 12M18 6L6 18"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}
