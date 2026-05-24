"use client";

import { useState } from "react";

type AuthMode = "login" | "register";

interface AuthPanelProps {
  onSubmit: (mode: AuthMode, email: string, password: string) => Promise<void>;
  isSubmitting: boolean;
  errorMessage: string | null;
}

function EyeIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

export default function AuthPanel({
  onSubmit,
  isSubmitting,
  errorMessage,
}: AuthPanelProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Reset password visibility when switching modes
  function switchMode(next: AuthMode) {
    setMode(next);
    setShowPassword(false);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(mode, email.trim(), password);
  }

  return (
    <div className="w-full max-w-md rounded-[2rem] border border-slate-200/80 bg-white/90 p-8 shadow-[0_25px_80px_-30px_rgba(15,23,42,0.35)] backdrop-blur">
      <div className="mb-6 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-700">
          Secure workspace
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          News Summarizer
        </h1>
        <p className="text-sm leading-6 text-slate-600">
          Sign in to your article workspace or create an account to keep sessions private.
        </p>
      </div>

      <div className="mb-6 inline-flex rounded-full bg-slate-100 p-1">
        <button
          className={`rounded-full px-4 py-2 text-sm transition ${
            mode === "login"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-500 hover:text-slate-800"
          }`}
          onClick={() => switchMode("login")}
          type="button"
        >
          Login
        </button>
        <button
          className={`rounded-full px-4 py-2 text-sm transition ${
            mode === "register"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-500 hover:text-slate-800"
          }`}
          onClick={() => switchMode("register")}
          type="button"
        >
          Register
        </button>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="auth-email">
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={isSubmitting}
            placeholder="you@example.com"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="auth-password">
            Password
          </label>
          <div className="relative">
            <input
              id="auth-password"
              type={showPassword ? "text" : "password"}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 pr-11 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isSubmitting}
              placeholder={mode === "register" ? "Min 8 chars, letters and numbers" : "Your password"}
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-slate-600 focus:outline-none disabled:opacity-40"
              onClick={() => setShowPassword((v) => !v)}
              disabled={isSubmitting}
              tabIndex={-1}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
          {mode === "register" && (
            <p className="text-xs text-slate-400">
              At least 8 characters including a letter and a number.
            </p>
          )}
        </div>

        {errorMessage && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errorMessage}
          </div>
        )}

        <button
          className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={isSubmitting || !email.trim() || !password}
        >
          {isSubmitting
            ? mode === "login"
              ? "Signing in..."
              : "Creating account..."
            : mode === "login"
              ? "Sign in"
              : "Create account"}
        </button>
      </form>
    </div>
  );
}
