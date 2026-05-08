const SESSION_KEY = "news_summarizer_session_id";

export function getStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_KEY);
}

export function storeSessionId(sessionId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(SESSION_KEY, sessionId);
}

export function clearStoredSessionId(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_KEY);
}
