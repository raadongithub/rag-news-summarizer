"use client";

import { useEffect, useRef, useState } from "react";

interface ArticleTextPanelProps {
  /** Raw article body text to display. */
  content: string;
  /**
   * When true, an onboarding callout is shown inside the panel and the
   * panel is forced open so the user sees the tip immediately.
   */
  showOnboardingTip?: boolean;
  /**
   * Called when the user dismisses the onboarding callout.
   * The parent is responsible for persisting the dismissal.
   */
  onDismissOnboarding?: () => void;
  /** Called when the user wants to open the full-screen expanded canvas. */
  onExpand?: () => void;
}

/**
 * Fixed overlay panel that slides in from the left edge of the screen to
 * display the raw article body text.
 *
 * A narrow tab button is always visible on the right edge of the panel so
 * the control remains discoverable even when the panel is fully collapsed
 * off-screen. Clicking the tab or clicking outside the panel toggles the
 * open/closed state.
 *
 * Parameters
 * ----------
 * content : string
 *     Raw article body text. Whitespace and newlines are preserved.
 * showOnboardingTip : bool, optional
 *     When true the panel is forced open and an onboarding callout is shown.
 * onDismissOnboarding : function, optional
 *     Callback invoked when the user closes the onboarding callout.
 * onExpand : function, optional
 *     Callback invoked when the user opens the expanded canvas view.
 */
export default function ArticleTextPanel({
  content,
  showOnboardingTip = false,
  onDismissOnboarding,
  onExpand,
}: ArticleTextPanelProps) {
  const [open, setOpen] = useState(showOnboardingTip);
  const panelRef = useRef<HTMLDivElement>(null);

  // Force open when the onboarding tip becomes active.
  useEffect(() => {
    if (showOnboardingTip) {
      setOpen(true);
    }
  }, [showOnboardingTip]);

  // Collapse when the user clicks outside the panel.
  useEffect(() => {
    function handlePointerDown(event: MouseEvent | TouchEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    if (open) {
      document.addEventListener("mousedown", handlePointerDown);
      document.addEventListener("touchstart", handlePointerDown);
    }
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [open]);

  return (
    <div
      ref={panelRef}
      className={`fixed left-0 top-1/2 z-20 flex -translate-y-1/2 items-stretch transition-transform duration-300 ease-out ${
        open ? "translate-x-0" : "-translate-x-80"
      }`}
    >
      {/* Panel body */}
      <div className="flex h-[70vh] w-80 flex-col overflow-hidden rounded-r-[1.75rem] border border-white/70 bg-white/95 shadow-[0_16px_50px_-20px_rgba(15,23,42,0.45)] backdrop-blur">
        {/* Header */}
        <div className="shrink-0 border-b border-slate-100 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ArticleIcon />
              <span className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                Full Article Text
              </span>
            </div>
            <button
              type="button"
              onClick={onExpand}
              className="btn-ghost px-2.5 py-1.5 text-xs"
              title="Open expanded canvas"
              aria-label="Open expanded canvas"
            >
              Expand
            </button>
          </div>
        </div>

        {/* Onboarding callout */}
        {showOnboardingTip && (
          <div className="shrink-0 border-b border-sky-100 bg-sky-50 px-5 py-4">
            <div className="flex items-start gap-3">
              <SparkleIcon />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-sky-800">Full article text is right here</p>
                <p className="mt-1 text-sm leading-5 text-sky-700">
                  This panel holds the complete article. Click the tab on the left edge any time to open or close it.
                </p>
              </div>
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={onDismissOnboarding}
                className="rounded-xl bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              >
                Got it
              </button>
            </div>
          </div>
        )}

        {/* Scrollable article content */}
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">{content}</p>
        </div>
      </div>

      {/* Tab toggle button — always visible on the right edge of the panel */}
      <button
        type="button"
        onClick={() => setOpen((previous) => !previous)}
        title={open ? "Hide article text" : "Show article text"}
        aria-label={open ? "Hide article text" : "Show article text"}
        className="flex h-20 w-9 shrink-0 items-center justify-center self-center rounded-r-xl bg-slate-200 shadow-md transition hover:brightness-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
      >
        <ChevronIcon open={open} />
      </button>
    </div>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      className={`h-5 w-5 text-slate-600 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

function ArticleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4 shrink-0 text-slate-400"
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

function SparkleIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="mt-0.5 h-4 w-4 shrink-0 text-sky-500"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.83-4.4Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

