"use client";
// Sign-in for the team account. Real mode talks to the API (HttpOnly cookie session). Mock mode can emulate the
// same flow so the screens and tests behave identically: set NEXT_PUBLIC_REQUIRE_LOGIN=true.
import { ApiError, USE_MOCK, http } from "./client";

export const REQUIRE_LOGIN = !USE_MOCK || process.env.NEXT_PUBLIC_REQUIRE_LOGIN === "true";
export const DEMO_ACCOUNT = { email: "admin@chryselys.com", password: "Admin@QAgent!2026" };
const KEY = "qagent_mock_session";

export interface Session { email: string }

export const auth = {
  async me(): Promise<Session | null> {
    if (!REQUIRE_LOGIN) return { email: "demo@local" };
    if (USE_MOCK) { const v = typeof window === "undefined" ? null : window.localStorage.getItem(KEY); return v ? { email: v } : null; }
    try { return await http<Session>("/auth/me"); } catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e; }
  },
  async login(email: string, password: string): Promise<Session> {
    if (USE_MOCK) {
      if (email.trim().toLowerCase() !== DEMO_ACCOUNT.email || password !== DEMO_ACCOUNT.password) throw new ApiError(401, "Email or password is not correct");
      window.localStorage.setItem(KEY, DEMO_ACCOUNT.email);
      return { email: DEMO_ACCOUNT.email };
    }
    return http<Session>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  },
  async logout(): Promise<void> {
    if (USE_MOCK) { window.localStorage.removeItem(KEY); return; }
    await http<void>("/auth/logout", { method: "POST" }).catch(() => undefined);
  },
};
