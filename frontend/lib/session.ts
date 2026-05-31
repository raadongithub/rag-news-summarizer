const SESSION_KEY = "news_summarizer_session_id";
const ACCESS_TOKEN_KEY = "news_summarizer_access_token";
const USER_KEY = "news_summarizer_user";
const ONBOARDING_KEY = "news_summarizer_onboarding_done";

export interface StoredUser {
  id: string;
  email: string;
  created_at: string;
  updated_at: string;
}

function canUseStorage(): boolean {
  return typeof window !== "undefined";
}

export function getStoredSessionId(): string | null {
  if (!canUseStorage()) return null;
  return localStorage.getItem(SESSION_KEY);
}

export function storeSessionId(sessionId: string): void {
  if (!canUseStorage()) return;
  localStorage.setItem(SESSION_KEY, sessionId);
}

export function clearStoredSessionId(): void {
  if (!canUseStorage()) return;
  localStorage.removeItem(SESSION_KEY);
}

export function getStoredAccessToken(): string | null {
  if (!canUseStorage()) return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function storeAccessToken(token: string): void {
  if (!canUseStorage()) return;
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearStoredAccessToken(): void {
  if (!canUseStorage()) return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function getStoredUser(): StoredUser | null {
  if (!canUseStorage()) return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

export function storeUser(user: StoredUser): void {
  if (!canUseStorage()) return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredUser(): void {
  if (!canUseStorage()) return;
  localStorage.removeItem(USER_KEY);
}

export function clearStoredAuth(): void {
  clearStoredAccessToken();
  clearStoredUser();
  clearStoredSessionId();
}

/**
 * Check whether the user has already completed the onboarding tour.
 *
 * Returns
 * -------
 * boolean
 *     True when the completion flag is present in localStorage,
 *     false when it is absent or when localStorage is unavailable
 *     (e.g. during server-side rendering).
 */
export function hasCompletedOnboarding(): boolean {
  if (!canUseStorage()) return false;
  return localStorage.getItem(ONBOARDING_KEY) === "1";
}

/**
 * Persist the onboarding completion flag so the tour is never shown again.
 *
 * Returns
 * -------
 * void
 */
export function markOnboardingComplete(): void {
  if (!canUseStorage()) return;
  localStorage.setItem(ONBOARDING_KEY, "1");
}
