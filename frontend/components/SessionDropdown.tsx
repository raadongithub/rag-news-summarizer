"use client";

import { useEffect, useRef, useState } from "react";

import { api, type SessionListItem } from "@/lib/api";

interface SessionDropdownProps {
  /** The ID of the session currently open in the workspace. */
  activeSessionId: string | null;
  /** Called when the user selects a previous session to switch to. */
  onSelectSession: (sessionId: string) => void;
  /** When true, the switch action is disabled (e.g., a request is in flight). */
  disabled?: boolean;
}

/**
 * Derive a human-readable label for a session list item.
 *
 * The priority order is: article title, first user message,
 * then a locale-formatted creation timestamp as a last resort.
 *
 * Parameters
 * ----------
 * session : SessionListItem
 *     Compact session summary returned by the API.
 *
 * Returns
 * -------
 * string
 *     Human-readable label suitable for display in the dropdown.
 */
function getSessionLabel(session: SessionListItem): string {
  if (session.article_title) return session.article_title;
  if (session.first_message) return session.first_message;
  return new Date(session.created_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Truncate a string to at most maxLength characters, appending an ellipsis
 * when the string exceeds that length.
 *
 * Parameters
 * ----------
 * text : string
 *     Input text to truncate.
 * maxLength : number
 *     Maximum character length before truncation.
 *
 * Returns
 * -------
 * string
 *     Possibly-truncated string.
 */
function truncate(text: string, maxLength: number): string {
  return text.length > maxLength ? `${text.slice(0, maxLength)}\u2026` : text;
}

/**
 * A dropdown button that lists the user's recent sessions and allows
 * switching between them.
 *
 * The session list is fetched lazily the first time the dropdown opens.
 * The list is re-fetched whenever the active session changes so the label
 * for the current entry stays up to date.
 *
 * Parameters
 * ----------
 * activeSessionId : string | null
 *     ID of the session currently open in the workspace.
 * onSelectSession : function
 *     Callback invoked with the chosen session ID when the user makes a
 *     selection.
 * disabled : boolean, optional
 *     When true the trigger button and all session items are non-interactive.
 */
export default function SessionDropdown({
  activeSessionId,
  onSelectSession,
  disabled = false,
}: SessionDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  /**
   * Fetch the session list from the API and update local state.
   *
   * Sets the loading flag while the request is in flight and records any
   * error message when the request fails.
   *
   * Returns
   * -------
   * void
   */
  async function fetchSessions(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listSessions();
      setSessions(data);
    } catch {
      setError("Could not load sessions.");
    } finally {
      setLoading(false);
    }
  }

  // Fetch whenever the dropdown opens.
  useEffect(() => {
    if (isOpen) {
      fetchSessions();
    }
  }, [isOpen]);

  // Close when the user clicks outside the dropdown container.
  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handlePointerDown);
    }
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [isOpen]);

  // Close on Escape key.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false);
    }

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  function toggleOpen() {
    setIsOpen((previous) => !previous);
  }

  function handleSelect(sessionId: string) {
    if (sessionId === activeSessionId) {
      setIsOpen(false);
      return;
    }
    onSelectSession(sessionId);
    setIsOpen(false);
  }

  return (
    <div ref={containerRef} className="relative z-40">
      <button
        type="button"
        className="btn-secondary flex items-center gap-1.5 text-xs py-2 px-3"
        onClick={toggleOpen}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label="Previous sessions"
        title="Previous sessions"
      >
        <HistoryIcon />
        <span className="hidden sm:inline">Sessions</span>
        <ChevronIcon open={isOpen} />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label="Previous sessions"
          className="absolute right-0 z-[90] mt-2 w-72 rounded-2xl border border-white/70 bg-white/95 shadow-[0_16px_50px_-20px_rgba(15,23,42,0.35)] backdrop-blur ring-1 ring-slate-100 focus:outline-none"
        >
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Previous Sessions
            </p>
          </div>

          <div
            className="max-h-72 overflow-y-auto py-1"
            style={{ overscrollBehavior: "contain" }}
          >
            {loading && (
              <div className="flex items-center justify-center gap-2 px-4 py-6 text-sm text-slate-400">
                <SpinnerIcon />
                Loading sessions&hellip;
              </div>
            )}

            {!loading && error && (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-rose-600">{error}</p>
                <button
                  type="button"
                  className="mt-2 text-xs text-sky-700 hover:text-sky-900 underline underline-offset-2"
                  onClick={fetchSessions}
                >
                  Retry
                </button>
              </div>
            )}

            {!loading && !error && sessions.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-slate-400">
                No previous sessions found.
              </div>
            )}

            {!loading &&
              !error &&
              sessions.map((session) => {
                const isActive = session.id === activeSessionId;
                const label = truncate(getSessionLabel(session), 55);
                const subtitle = session.article_title
                  ? null
                  : session.url
                  ? truncate(session.url, 40)
                  : new Date(session.created_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    });

                return (
                  <button
                    key={session.id}
                    role="option"
                    aria-selected={isActive}
                    type="button"
                    disabled={disabled}
                    onClick={() => handleSelect(session.id)}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition ${
                      isActive
                        ? "bg-sky-50 text-sky-900"
                        : "text-slate-700 hover:bg-slate-50"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                    title={getSessionLabel(session)}
                  >
                    <span
                      className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                        isActive ? "bg-sky-500" : "bg-slate-300"
                      }`}
                      aria-hidden="true"
                    />
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-medium leading-snug">
                        {label}
                      </span>
                      {subtitle && (
                        <span className="mt-0.5 truncate text-xs text-slate-400">
                          {subtitle}
                        </span>
                      )}
                    </span>
                    {isActive && (
                      <span className="ml-auto shrink-0 text-xs font-medium text-sky-600">
                        Active
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-13a.75.75 0 0 0-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 0 0 0-1.5h-3.25V5Z"
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
      className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
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

function SpinnerIcon() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-slate-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
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
