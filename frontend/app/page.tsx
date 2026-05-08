"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Session } from "@/lib/api";
import { getStoredSessionId, storeSessionId, clearStoredSessionId } from "@/lib/session";
import ArticleLoader from "@/components/ArticleLoader";
import SummaryPanel from "@/components/SummaryPanel";
import ChatPanel from "@/components/ChatPanel";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [loadingArticle, setLoadingArticle] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  // Restore or create session on mount
  useEffect(() => {
    async function init() {
      const stored = getStoredSessionId();
      if (stored) {
        try {
          const s = await api.getSession(stored);
          setSession(s);
          setInitializing(false);
          return;
        } catch {
          // Session gone – create fresh one
          clearStoredSessionId();
        }
      }
      try {
        const s = await api.createSession();
        storeSessionId(s.id);
        setSession(s);
      } catch (e) {
        setErrorMsg("Could not connect to the backend. Is it running?");
      }
      setInitializing(false);
    }
    init();
  }, []);

  const clearError = useCallback(() => setErrorMsg(null), []);

  // Load article
  async function handleLoadArticle(url: string) {
    if (!session) return;
    clearError();
    setLoadingArticle(true);
    try {
      const updated = await api.loadArticle(session.id, url);
      setSession(updated);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(`Failed to load article: ${msg}`);
      // Re-fetch session to preserve any prior state
      try {
        const refreshed = await api.getSession(session.id);
        setSession(refreshed);
      } catch {
        // ignore
      }
    } finally {
      setLoadingArticle(false);
    }
  }

  // Generate full summary
  async function handleSummarize() {
    if (!session) return;
    clearError();
    setSummarizing(true);
    try {
      const updated = await api.summarize(session.id);
      setSession(updated);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(`Summarization failed: ${msg}`);
      try {
        const refreshed = await api.getSession(session.id);
        setSession(refreshed);
      } catch {
        // ignore
      }
    } finally {
      setSummarizing(false);
    }
  }

  // Chat
  async function handleSendQuestion(question: string) {
    if (!session) return;
    clearError();

    // Optimistically add user message to UI
    setSession((prev) =>
      prev
        ? {
            ...prev,
            chat_history: [
              ...prev.chat_history,
              { role: "user", content: question, critique: null, passages: [] },
            ],
          }
        : prev
    );
    setThinking(true);

    try {
      const result = await api.chat(session.id, question);
      // Re-fetch full session to sync persisted state
      const refreshed = await api.getSession(session.id);
      setSession(refreshed);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(`Chat error: ${msg}`);
      // Re-fetch to get the error assistant message that backend saved
      try {
        const refreshed = await api.getSession(session.id);
        setSession(refreshed);
      } catch {
        // ignore
      }
    } finally {
      setThinking(false);
    }
  }

  // New session
  async function handleNewSession() {
    clearStoredSessionId();
    clearError();
    setSession(null);
    setInitializing(true);
    try {
      const s = await api.createSession();
      storeSessionId(s.id);
      setSession(s);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(`Could not create session: ${msg}`);
    } finally {
      setInitializing(false);
    }
  }

  const isProcessing = loadingArticle || summarizing || thinking;

  if (initializing) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400 text-sm">Connecting…</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">News Summarizer</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              RAG-powered article Q&amp;A
            </p>
          </div>

          <div className="flex items-center gap-3">
            {session && (
              <span className="hidden sm:inline text-xs text-gray-400 font-mono">
                Session: {session.id.slice(0, 8)}…
              </span>
            )}
            <button
              className="btn-secondary text-xs py-1.5 px-3"
              onClick={handleNewSession}
              disabled={isProcessing}
            >
              New Session
            </button>
          </div>
        </div>
      </header>

      {/* Error banner */}
      {errorMsg && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-start justify-between gap-4">
            <p className="text-sm text-red-700">{errorMsg}</p>
            <button
              className="text-red-400 hover:text-red-600 shrink-0"
              onClick={clearError}
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Status banner when processing */}
      {session?.status === "processing" && !isProcessing && (
        <div className="bg-blue-50 border-b border-blue-200 px-6 py-2">
          <div className="max-w-7xl mx-auto text-sm text-blue-700">
            Processing…
          </div>
        </div>
      )}

      {/* Main layout */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 h-full">
          {/* Left panel */}
          <aside className="space-y-5">
            {/* Article loader */}
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
                Load Article
              </h2>
              <ArticleLoader
                onLoad={handleLoadArticle}
                isLoading={loadingArticle}
                currentUrl={session?.url ?? null}
              />
            </div>

            {/* Article info + summary */}
            {session?.article && (
              <SummaryPanel
                article={session.article}
                summary={session.summary}
                onGenerateSummary={handleSummarize}
                isSummarizing={summarizing}
              />
            )}

            {!session?.article && !loadingArticle && (
              <p className="text-sm text-gray-400 text-center">
                Enter a URL above to load an article.
              </p>
            )}
          </aside>

          {/* Right panel — chat */}
          <div className="card p-5 flex flex-col" style={{ minHeight: "60vh" }}>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
              Chat with the Article
            </h2>
            <ChatPanel
              messages={session?.chat_history ?? []}
              onSend={handleSendQuestion}
              isThinking={thinking}
              disabled={!session?.article || loadingArticle}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
