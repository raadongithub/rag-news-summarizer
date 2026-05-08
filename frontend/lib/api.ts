const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScrapedArticle {
  url: string;
  title: string;
  content: string;
  authors: string[];
  publish_date: string | null;
  summary: string;
  source_domain: string;
  word_count: number;
  extraction_method: string;
}

export interface Critique {
  is_faithful: boolean;
  faithfulness_explanation: string;
  is_relevant: boolean;
  relevance_explanation: string;
  confidence_score: number;
}

export interface Passage {
  text: string;
  similarity_score: number;
  rank: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  critique: Critique | null;
  passages: Passage[];
}

export interface Session {
  id: string;
  url: string | null;
  article: ScrapedArticle | null;
  summary: string | null;
  chat_history: ChatMessage[];
  retrieved_passages: Passage[] | null;
  status: "idle" | "processing" | "error";
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  answer: string;
  critique: Critique | null;
  passages: Passage[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const api = {
  health: () => request<{ status: string }>("/health"),

  createSession: () =>
    request<Session>("/sessions", { method: "POST" }),

  getSession: (sessionId: string) =>
    request<Session>(`/sessions/${sessionId}`),

  loadArticle: (sessionId: string, url: string) =>
    request<Session>(`/sessions/${sessionId}/article`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  summarize: (sessionId: string) =>
    request<Session>(`/sessions/${sessionId}/summarize`, { method: "POST" }),

  chat: (sessionId: string, question: string) =>
    request<ChatResponse>(`/sessions/${sessionId}/chat`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};
