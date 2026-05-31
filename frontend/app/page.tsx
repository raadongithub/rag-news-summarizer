"use client";

import { useEffect, useState } from "react";

import ArticleLoader from "@/components/ArticleLoader";
import ArticleTextPanel from "@/components/ArticleTextPanel";
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
  hasCompletedOnboarding,
  markOnboardingComplete,
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

/**
 * Render the authenticated article workspace and coordinate session actions.
 *
 * Returns
 * -------
 * JSX.Element
 *     Root workspace UI, including header, sidebar, chat surface, and
 *     optional expanded content overlays.
 */
export default function Home() {
  const MIN_LEFT_PANEL_WIDTH = 280;
  const MAX_LEFT_PANEL_WIDTH = 520;

  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<StoredUser | null>(null);
  const [loadingArticle, setLoadingArticle] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [expandedState, setExpandedState] = useState<ExpandedState | null>(null);
  // showOnboarding becomes true exactly once: when the user loads their first
  // article and has never completed the onboarding tour before.
  const [showOnboarding, setShowOnboarding] = useState(false);

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
      if (mode === "register" && !hasCompletedOnboarding()) {
        setShowOnboarding(true);
      }
      await restoreOrCreateSession();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authentication failed";
      setErrorMessage(message);
    } finally {
      setAuthLoading(false);
      setInitializing(false);
    }
  }

  /**
   * Load an article into the current session from a URL.
   *
   * This is a one-way operation per session: once an article is attached the
   * Load Article form is hidden and can only be reset by starting a new
   * session. After a successful load, the onboarding tip is triggered the
   * first time a user loads any article.
   *
   * Parameters
   * ----------
   * url : string
   *     The publicly accessible URL of the news article to fetch and index.
   *
   * Returns
   * -------
   * void
   */
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

  /**
   * Dismiss the onboarding callout and persist the completion flag.
   *
   * After this is called, hasCompletedOnboarding() returns true for all
   * future page loads on this device, ensuring the tour is shown only once.
   *
   * Returns
   * -------
   * void
   */
  function handleDismissOnboarding() {
    markOnboardingComplete();
    setShowOnboarding(false);
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

  /**
   * Send a chat question using the streaming chat pipeline.
   *
   * Chat responses are rendered incrementally from stream tokens.
   * Summary generation is intentionally handled by the separate batch
   * summarize flow and is not mixed into this handler.
   *
   * Parameters
   * ----------
   * question : string
   *     User question submitted from the chat input.
   *
   * Returns
   * -------
   * Promise<void>
   *     Resolves when token streaming and final synchronization complete.
   */
  async function handleSendQuestion(question: string) {
    if (!session) return;
    const activeSessionId = session.id;
    setErrorMessage(null);

    setSession((previous) =>
      previous
        ? {
            ...previous,
            chat_history: [
              ...previous.chat_history,
              { role: "user", content: question, critique: null, passages: [] },
              { role: "assistant", content: "", critique: null, passages: [] },
            ],
          }
        : previous
    );
    setThinking(true);

    try {
      await api.chatStream(activeSessionId, question, {
        onToken: (token) => {
          setSession((previous) => {
            if (!previous) return previous;
            const nextHistory = [...previous.chat_history];
            const lastIndex = nextHistory.length - 1;
            if (lastIndex < 0 || nextHistory[lastIndex].role !== "assistant") {
              return previous;
            }
            nextHistory[lastIndex] = {
              ...nextHistory[lastIndex],
              content: `${nextHistory[lastIndex].content}${token}`,
            };
            return { ...previous, chat_history: nextHistory };
          });
        },
        onDone: (event) => {
          setSession((previous) => {
            if (!previous) return previous;
            const nextHistory = [...previous.chat_history];
            const lastIndex = nextHistory.length - 1;
            if (lastIndex < 0 || nextHistory[lastIndex].role !== "assistant") {
              return previous;
            }
            nextHistory[lastIndex] = {
              ...nextHistory[lastIndex],
              content: event.answer,
              critique: event.critique,
              passages: event.passages,
            };
            return {
              ...previous,
              chat_history: nextHistory,
              retrieved_passages: event.passages,
            };
          });
        },
      });

      const refreshedSession = await api.getSession(activeSessionId);
      setSession(refreshedSession);
    } catch (error) {
      if (handleUnauthorized(error, "Please sign in again to continue.")) return;
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(`Chat error: ${message}`);
      try {
        const refreshedSession = await api.getSession(activeSessionId);
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
  const [leftPanelWidth, setLeftPanelWidth] = useState(320);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const isProcessing = loadingArticle || summarizing || thinking;

  const expandedArticle =
    expandedState &&
    session?.article &&
    expandedState.article.url === session.article.url
      ? session.article
      : expandedState?.article;
  const expandedSummary =
    expandedState &&
    session?.article &&
    expandedState.article.url === session.article.url
      ? session.summary
      : expandedState?.summary;

  /**
   * Start the drag-resize interaction for the left sidebar.
   *
   * Parameters
   * ----------
   * event : React.MouseEvent<HTMLDivElement>
   *     Mouse down event originating from the sidebar resize handle.
   *
   * Returns
   * -------
   * void
   */
  function handleSidebarResizeStart(event: React.MouseEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsResizingSidebar(true);
  }

  useEffect(() => {
    if (!isResizingSidebar) {
      return;
    }

    function handleMouseMove(event: MouseEvent) {
      const nextWidth = Math.min(
        MAX_LEFT_PANEL_WIDTH,
        Math.max(MIN_LEFT_PANEL_WIDTH, event.clientX)
      );
      setLeftPanelWidth(nextWidth);
    }

    function stopResizing() {
      setIsResizingSidebar(false);
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", stopResizing);

    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", stopResizing);
    };
  }, [MAX_LEFT_PANEL_WIDTH, MIN_LEFT_PANEL_WIDTH, isResizingSidebar]);

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

        {/* Header */}
        <header className="relative z-50 shrink-0 border-b border-white/70 bg-white/75 backdrop-blur">
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

            {/* Right: session controls */}
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
                    className="btn-secondary py-1.5 px-3 text-base font-semibold leading-none"
                    onClick={handleNewSession}
                    disabled={isProcessing}
                    type="button"
                    aria-label="New session"
                    title="New session"
                  >
                    +
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Banners */}
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

        {/* Main layout */}
        <main className="flex flex-1 overflow-hidden">

          {/* Left panel – collapsible article workspace */}
          <div
            className="relative shrink-0 overflow-hidden border-r border-slate-200/70 transition-[width] duration-300 ease-in-out"
            style={{ width: leftPanelOpen ? leftPanelWidth : 0 }}
          >
            <div className="flex h-full flex-col gap-4 p-4">
              {/*
               * Article URL loader — only shown before an article is attached.
               * Once a session has an article the form is intentionally hidden:
               * one session = one article. A new session is required to load a
               * different article.
               */}
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
                {!session?.article && (
                  <div className="card shrink-0 p-5">
                    <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-700">
                      Load Article
                    </h2>
                    <ArticleLoader
                      onLoad={handleLoadArticle}
                      isLoading={loadingArticle}
                      currentUrl={session?.url ?? null}
                    />
                    {!loadingArticle && (
                      <p className="mt-4 text-center text-xs text-slate-400">
                        Paste an article URL above to load content into this session.
                      </p>
                    )}
                  </div>
                )}

                {session?.article && (
                  <>
                    {/* Summary card */}
                    <div className="flex min-h-[240px] flex-col" style={{ flex: "0 0 auto" }}>
                      <SummaryPanel
                        article={session.article}
                        summary={session.summary}
                        onGenerateSummary={handleSummarize}
                        onExpand={() => openArticleCanvas(session.article!, session.summary)}
                        isSummarizing={summarizing}
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="mt-auto shrink-0 border-t border-slate-200/80 pt-3">
                <div className="rounded-2xl border border-white/70 bg-white/70 px-3.5 py-3 backdrop-blur">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Account
                  </p>
                  <p className="mt-1 truncate text-sm font-medium text-slate-700" title={user.email}>
                    {user.email}
                  </p>
                  <button
                    className="mt-2 w-full rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-100 hover:text-rose-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
                    onClick={handleLogout}
                    type="button"
                  >
                    Logout
                  </button>
                </div>
              </div>
            </div>

            {leftPanelOpen && (
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize sidebar"
                onMouseDown={handleSidebarResizeStart}
                className="absolute right-0 top-0 h-full w-2 cursor-col-resize bg-transparent transition hover:bg-sky-200/50"
              />
            )}
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

      {expandedState && expandedArticle && (
        <ExpandedCanvas
          article={expandedArticle}
          summary={expandedSummary ?? null}
          contextTitle={expandedState.contextTitle}
          contextBody={expandedState.contextBody}
          contextLabel={expandedState.contextLabel}
          passages={expandedState.passages}
          onGenerateSummary={handleSummarize}
          isSummarizing={summarizing}
          onClose={() => setExpandedState(null)}
        />
      )}

      {session?.article && (
        <ArticleTextPanel
          content={session.article.content}
          showOnboardingTip={showOnboarding}
          onDismissOnboarding={handleDismissOnboarding}
          onExpand={() => openArticleCanvas(session.article!, session.summary)}
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
