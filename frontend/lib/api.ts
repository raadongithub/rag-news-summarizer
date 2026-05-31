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

export interface ChatStreamDoneEvent {
  answer: string;
  critique: Critique | null;
  passages: Passage[];
}

interface ChatStreamTokenEvent {
  type: "token";
  token: string;
}

interface ChatStreamDonePayload extends ChatStreamDoneEvent {
  type: "done";
}

interface ChatStreamErrorEvent {
  type: "error";
  message: string;
}

type ChatStreamEvent = ChatStreamTokenEvent | ChatStreamDonePayload | ChatStreamErrorEvent;

export interface ChatStreamHandlers {
  onToken?: (token: string) => void;
  onDone?: (event: ChatStreamDoneEvent) => void;
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

/**
 * Build API request headers with auth when available.
 *
 * Parameters
 * ----------
 * base : HeadersInit | undefined
 *     Optional headers to merge into the result.
 *
 * Returns
 * -------
 * Headers
 *     Headers object with content type and bearer token when present.
 */
function buildApiHeaders(base?: HeadersInit): Headers {
  const token = getStoredAccessToken();
  const headers = new Headers(base);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

/**
 * Read a non-empty NDJSON line as a chat stream event payload.
 *
 * Parameters
 * ----------
 * line : string
 *     Single NDJSON line from the stream.
 *
 * Returns
 * -------
 * ChatStreamEvent
 *     Parsed event payload.
 */
function parseStreamEvent(line: string): ChatStreamEvent {
  return JSON.parse(line) as ChatStreamEvent;
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

  /**
   * Stream a chat answer as incremental token events.
   *
   * Parameters
   * ----------
   * sessionId : string
   *     Active session identifier.
   * question : string
   *     User question for the article.
   * handlers : ChatStreamHandlers
   *     Token and completion callbacks for incremental rendering.
   *
   * Returns
   * -------
   * Promise<void>
   *     Resolves when the stream completes successfully.
   */
  async chatStream(
    sessionId: string,
    question: string,
    handlers: ChatStreamHandlers
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/chat/stream`, {
      method: "POST",
      headers: buildApiHeaders(),
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      let errorCode: string | null = null;
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : detail;
        errorCode = typeof body.error_code === "string" ? body.error_code : null;
      } catch {
        // Ignore parse errors and keep fallback details.
      }
      throw new ApiError(detail, response.status, errorCode);
    }

    if (!response.body) {
      throw new ApiError("Streaming response body was unavailable", 500);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;

        const event = parseStreamEvent(line);
        if (event.type === "token") {
          handlers.onToken?.(event.token);
          continue;
        }

        if (event.type === "done") {
          handlers.onDone?.({
            answer: event.answer,
            critique: event.critique,
            passages: event.passages,
          });
          continue;
        }

        throw new ApiError(event.message || "Chat stream failed", 500);
      }
    }
  },
};
