import { getStoredAccessToken, type StoredUser } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  metadata?: Record<string, unknown>;
  base_similarity_score?: number | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  critique: Critique | null;
  passages: Passage[];
}

export interface Session {
  id: string;
  user_id: string;
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

export interface SessionListItem {
  id: string;
  url: string | null;
  article_title: string | null;
  first_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  answer: string;
  critique: Critique | null;
  passages: Passage[];
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: StoredUser;
}

export class ApiError extends Error {
  status: number;
  errorCode: string | null;

  constructor(message: string, status: number, errorCode: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getStoredAccessToken();
  const headers = new Headers(options?.headers);

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    let errorCode: string | null = null;
    try {
      const body = await response.json();
      // Prefer the top-level detail string when it's human-readable
      if (typeof body.detail === "string" && body.detail !== "Request validation failed") {
        detail = body.detail;
      } else if (Array.isArray(body.errors) && body.errors.length > 0) {
        // Pydantic v2 validation errors — extract the first meaningful message
        const msgs = body.errors
          .map((entry: { msg?: string; ctx?: { error?: string } }) =>
            entry.ctx?.error ?? entry.msg ?? ""
          )
          .filter(Boolean);
        detail = msgs.length > 0 ? msgs.join("; ") : (body.detail ?? detail);
      } else if (typeof body.detail === "string") {
        detail = body.detail;
      }
      errorCode = typeof body.error_code === "string" ? body.error_code : null;
    } catch {
      // Ignore response parsing errors and fall back to HTTP status text.
    }
    throw new ApiError(detail, response.status, errorCode);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  register: (email: string, password: string) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<StoredUser>("/auth/me"),

  createSession: () => request<Session>("/sessions", { method: "POST" }),

  listSessions: () => request<SessionListItem[]>("/sessions"),

  getSession: (sessionId: string) => request<Session>(`/sessions/${sessionId}`),

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
