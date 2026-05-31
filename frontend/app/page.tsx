"use client";

import { useEffect, useState } from "react";

import ArticleLoader from "@/components/ArticleLoader";
import AuthPanel from "@/components/AuthPanel";
import ChatPanel from "@/components/ChatPanel";
import ExpandedCanvas from "@/components/ExpandedCanvas";
import SessionDropdown from "@/components/SessionDropdown";
import SummaryPanel from "@/components/SummaryPanel";
import { api, ApiError, type ChatMessage, type Passage, type ScrapedArticle, type Session } from "@/lib/api";
import {
  clearStoredAuth,
  clearStoredSessionId,
  getStoredAccessToken,
  getStoredSessionId,
  getStoredUser,
  storeAccessToken,
  storeSessionId,
  storeUser,
  type StoredUser,
} from "@/lib/session";

interface ExpandedState {
  article: ScrapedArticle;
  summary: string | null;
  contextTitle?: string;
  contextBody?: string;
  contextLabel?: string;
  passages?: Passage[];
}

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [loadingArticle, setLoadingArticle] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [expandedState, setExpandedState] = useState<ExpandedState | null>(null);

  useEffect(() => {
    async function initializeApp() {
      const token = getStoredAccessToken();
      const storedUser = getStoredUser();

      if (!token || !storedUser) {
        setInitializing(false);
        return;
      }

      setUser(storedUser);

      try {
        const confirmedUser = await api.me();
        storeUser(confirmedUser);
        setUser(confirmedUser);
        await restoreOrCreateSession();
      } catch (error) {
        handleUnauthorized(error, "Your session expired. Please sign in again.");
      } finally {
        setInitializing(false);
      }
    }

    initializeApp();
  }, []);

  async function restoreOrCreateSession(): Promise<void> {
    const storedSessionId = getStoredSessionId();
    if (storedSessionId) {
      try {
        const existingSession = await api.getSession(storedSessionId);
        setSession(existingSession);
        return;
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 404)) {
          throw error;
        }
        clearStoredSessionId();
      }
    }

    const newSession = await api.createSession();
    storeSessionId(newSession.id);
    setSession(newSession);
  }

  function resetWorkspace(message?: string) {
    clearStoredAuth();
    setUser(null);
    setSession(null);
    setExpandedState(null);
    setErrorMessage(message || null);
  }

  function handleUnauthorized(error: unknown, fallbackMessage: string): boolean {
    if (error instanceof ApiError && error.status === 401) {
      resetWorkspace(fallbackMessage);
      return true;
    }
    return false;
  }

  async function handleAuthSubmit(
    mode: "login" | "register",
    email: string,
    password: string
  ): Promise<void> {
    setAuthLoading(true);
    setErrorMessage(null);

    try {
      const response =
        mode === "login" ? await api.login(email, password) : await api.register(email, password);
      storeAccessToken(response.access_token);
      storeUser(response.user);
      setUser(response.user);
      await restoreOrCreateSession();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authentication failed";
      setErrorMessage(message);
    } finally {
      setAuthLoading(false);
      setInitializing(false);
    }
  }

  async function handleLoadArticle(url: string) {
    if (!session) return;
    setErrorMessage(null);
    setLoadingArticle(true);

    try {
      const updatedSession = await api.loadArticle(session.id, url);
      setSession(updatedSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Failed to load article: ${message}`);
      try {
        const refreshedSession = await api.getSession(session.id);
        setSession(refreshedSession);
      } catch {
        // Preserve existing UI state when refresh fails.
      }
    } finally {
      setLoadingArticle(false);
    }
  }

  async function handleSummarize() {
    if (!session) return;
    setErrorMessage(null);
    setSummarizing(true);

    try {
      const updatedSession = await api.summarize(session.id);
      setSession(updatedSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Summarization failed: ${message}`);
      try {
        const refreshedSession = await api.getSession(session.id);
        setSession(refreshedSession);
      } catch {
        // Preserve existing UI state when refresh fails.
      }
    } finally {
      setSummarizing(false);
    }
  }

  async function handleSendQuestion(question: string) {
    if (!session) return;
    setErrorMessage(null);

    setSession((previous) =>
      previous
        ? {
            ...previous,
            chat_history: [
              ...previous.chat_history,
              { role: "user", content: question, critique: null, passages: [] },
            ],
          }
        : previous
    );
    setThinking(true);

    try {
      await api.chat(session.id, question);
      const refreshedSession = await api.getSession(session.id);
      setSession(refreshedSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Chat error: ${message}`);
      try {
        const refreshedSession = await api.getSession(session.id);
        setSession(refreshedSession);
      } catch {
        // Preserve existing UI state when refresh fails.
      }
    } finally {
      setThinking(false);
    }
  }

  async function handleNewSession() {
    setErrorMessage(null);
    setSession(null);
    setExpandedState(null);

    try {
      const newSession = await api.createSession();
      storeSessionId(newSession.id);
      setSession(newSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Could not create session: ${message}`);
    }
  }

  async function handleSwitchSession(sessionId: string) {
    setErrorMessage(null);
    setExpandedState(null);

    try {
      const targetSession = await api.getSession(sessionId);
      storeSessionId(targetSession.id);
      setSession(targetSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Could not switch session: ${message}`);
    }
  }

  function handleLogout() {
    resetWorkspace();
    setInitializing(false);
  }

  function openArticleCanvas(article: ScrapedArticle, summary: string | null) {
    setExpandedState({
      article,
      summary,
    });
  }

  function openMessageCanvas(message: ChatMessage, index: number) {
    if (!session?.article) return;

    const contextTitle =
      message.role === "user" ? `Prompt ${index + 1}` : `Answer ${index + 1}`;
    const contextBody =
      message.role === "assistant" && message.critique
        ? `${message.content}\n\nRelevance: ${message.critique.relevance_explanation}\n\nFaithfulness: ${message.critique.faithfulness_explanation}`
        : message.content;

    setExpandedState({
      article: session.article,
      summary: session.summary,
      contextTitle,
      contextBody,
      contextLabel: message.role === "user" ? "Question context" : "Answer context",
      passages: message.passages,
    });
  }

  const [leftPanelOpen, setLeftPanelOpen] = useState(true);
  const isProcessing = loadingArticle || summarizing || thinking;

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(125,211,252,0.2),_transparent_35%),linear-gradient(180deg,_#f8fafc_0%,_#e2e8f0_100%)]">
        <div className="text-sm text-slate-500">Connecting...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.16),_transparent_26%),radial-gradient(circle_at_bottom_right,_rgba(15,23,42,0.14),_transparent_24%),linear-gradient(180deg,_#f8fafc_0%,_#dbeafe_100%)] px-4 py-10">
        <AuthPanel onSubmit={handleAuthSubmit} isSubmitting={authLoading} errorMessage={errorMessage} />
      </main>
    );
  }

  return (
    <>
      <div className="flex h-screen flex-col overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(125,211,252,0.16),_transparent_18%),linear-gradient(180deg,_#f8fafc_0%,_#eef2ff_100%)]">

        {/* ── Header ─────────────────────────────────────────────── */}
        <header className="shrink-0 border-b border-white/70 bg-white/75 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4">

            {/* Left: panel toggle + brand */}
            <div className="flex shrink-0 items-center gap-2.5">
              <button
                type="button"
                onClick={() => setLeftPanelOpen((v) => !v)}
                title={leftPanelOpen ? "Hide article panel" : "Show article panel"}
                className="btn-ghost rounded-lg p-1.5"
                aria-label={leftPanelOpen ? "Hide article panel" : "Show article panel"}
              >
                <PanelToggleIcon open={leftPanelOpen} />
              </button>
              <div className="hidden sm:block leading-tight">
                <h1 className="text-base font-semibold text-slate-950 leading-tight">News Summarizer</h1>
                <p className="text-[11px] text-slate-500 leading-tight">Private RAG-powered article workspace</p>
              </div>
            </div>

            {/* Center: article metadata (flexible spacer) */}
            <div className="flex min-w-0 flex-1 items-center justify-center px-4">
              {session?.article && (
                <div className="hidden max-w-lg items-center gap-2 lg:flex">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true">
                    <path fillRule="evenodd" d="M4 4a2 2 0 0 1 2-2h4.586A2 2 0 0 1 12 2.586L15.414 6A2 2 0 0 1 16 7.414V16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Zm2 6a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 6 10Zm0 2.5a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
                  </svg>
                  <span className="truncate text-sm font-medium text-slate-600">
                    {session.article.title || session.url}
                  </span>
                </div>
              )}
            </div>

            {/* Right: session controls + divider + user controls */}
            <div className="flex shrink-0 items-center gap-2">
              {/* Session group */}
              {session && (
                <div className="flex items-center gap-1.5">
                  <SessionDropdown
                    activeSessionId={session.id}
                    onSelectSession={handleSwitchSession}
                    disabled={isProcessing}
                  />
                  <button
                    className="btn-secondary py-1.5 px-3 text-xs"
                    onClick={handleNewSession}
                    disabled={isProcessing}
                    type="button"
                  >
                    New session
                  </button>
                </div>
              )}

              {/* Divider */}
              <div className="mx-1 h-5 w-px bg-slate-200" aria-hidden="true" />

              {/* User group */}
              <div className="flex items-center gap-1.5">
                <span className="hidden max-w-[180px] truncate rounded-full bg-slate-100/80 px-2.5 py-1 text-xs text-slate-500 md:block">
                  {user.email}
                </span>
                <button className="btn-ghost" onClick={handleLogout} type="button">
                  Logout
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* ── Banners ─────────────────────────────────────────────── */}
        {errorMessage && (
          <div className="shrink-0 border-b border-rose-200 bg-rose-50/95 px-4 py-3">
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm text-rose-700">{errorMessage}</p>
              <button
                className="shrink-0 text-rose-400 transition hover:text-rose-600"
                onClick={() => setErrorMessage(null)}
                aria-label="Dismiss error"
                type="button"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {session?.status === "processing" && !isProcessing && (
          <div className="shrink-0 border-b border-sky-200 bg-sky-50/95 px-4 py-2 text-sm text-sky-700">
            Processing…
          </div>
        )}

        {/* ── Main three-section layout ───────────────────────────── */}
        <main className="flex flex-1 overflow-hidden">

          {/* Left panel – collapsible article workspace */}
          <div
            className={`shrink-0 overflow-hidden border-r border-slate-200/70 transition-[width] duration-300 ease-in-out ${
              leftPanelOpen ? "w-80" : "w-0"
            }`}
          >
            <div className="flex h-full w-80 flex-col gap-4 overflow-y-auto p-4">
              <div className="card shrink-0 p-5">
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-700">
                  Load Article
                </h2>
                <ArticleLoader
                  onLoad={handleLoadArticle}
                  isLoading={loadingArticle}
                  currentUrl={session?.url ?? null}
                />
              </div>

              {session?.article && (
                <SummaryPanel
                  article={session.article}
                  summary={session.summary}
                  onGenerateSummary={handleSummarize}
                  onExpand={() => openArticleCanvas(session.article!, session.summary)}
                  isSummarizing={summarizing}
                />
              )}

              {!session?.article && !loadingArticle && (
                <p className="px-2 text-center text-sm text-slate-400">
                  Paste an article URL above to load content into this session.
                </p>
              )}
            </div>
          </div>

          {/* Center – chat interface (primary workspace) */}
          <section className="flex flex-1 flex-col overflow-hidden p-4">
            <div className="card flex min-h-0 flex-1 flex-col overflow-hidden p-5">
              <h2 className="mb-4 shrink-0 text-sm font-semibold uppercase tracking-wide text-slate-700">
                Chat with the Article
              </h2>
              <ChatPanel
                messages={session?.chat_history ?? []}
                onSend={handleSendQuestion}
                onExpandMessage={openMessageCanvas}
                isThinking={thinking}
                disabled={!session?.article || loadingArticle}
                articleLoaded={!!session?.article}
              />
            </div>
          </section>
        </main>
      </div>

      {expandedState && (
        <ExpandedCanvas
          article={expandedState.article}
          summary={expandedState.summary}
          contextTitle={expandedState.contextTitle}
          contextBody={expandedState.contextBody}
          contextLabel={expandedState.contextLabel}
          passages={expandedState.passages}
          onClose={() => setExpandedState(null)}
        />
      )}
    </>
  );
}

function PanelToggleIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-4 w-4"
      aria-hidden="true"
    >
      {open ? (
        /* panel-left-close: two columns, left filled */
        <path
          fillRule="evenodd"
          d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
          clipRule="evenodd"
        />
      ) : (
        /* panel-left-open */
        <path
          fillRule="evenodd"
          d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
          clipRule="evenodd"
        />
      )}
    </svg>
  );
}
