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
        <header className="shrink-0 border-b border-white/70 bg-white/75 px-6 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold text-slate-950">News Summarizer</h1>
              <p className="mt-0.5 text-xs text-slate-500">
                Private RAG-powered article workspace
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-xs text-slate-500 sm:block">
                {user.email}
              </div>
              {session && (
                <SessionDropdown
                  activeSessionId={session.id}
                  onSelectSession={handleSwitchSession}
                  disabled={isProcessing}
                />
              )}
              <button className="btn-secondary text-xs py-2 px-3" onClick={handleNewSession} disabled={isProcessing} type="button">
                New session
              </button>
              <button className="btn-ghost" onClick={handleLogout} type="button">
                Logout
              </button>
            </div>
          </div>
        </header>

        {errorMessage && (
          <div className="shrink-0 border-b border-rose-200 bg-rose-50/95 px-6 py-3">
            <div className="mx-auto flex max-w-7xl items-start justify-between gap-4">
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
          <div className="shrink-0 border-b border-sky-200 bg-sky-50/95 px-6 py-2">
            <div className="mx-auto max-w-7xl text-sm text-sky-700">Processing...</div>
          </div>
        )}

        <main className="mx-auto flex w-full max-w-7xl flex-1 overflow-hidden px-4 py-6 sm:px-6">
          <div className="grid h-full w-full grid-cols-1 gap-6 lg:grid-cols-[390px_1fr]">
            <aside className="flex h-full flex-col gap-5 overflow-y-auto pr-1">
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
            </aside>

            <section className="card flex min-h-0 flex-col overflow-hidden p-5">
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
            </section>
          </div>
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
