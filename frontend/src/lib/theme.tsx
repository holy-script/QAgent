"use client";
// Light / dark / system theme without a library: next-themes renders an inline <script> inside a client
// component, which React 19 warns about. The no-flash script lives in the server layout instead (THEME_SCRIPT).
import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

export type Theme = "light" | "dark" | "system";
const KEY = "theme";

/** Runs before first paint (rendered from the server layout) so the page never flashes the wrong theme. Light is the default. */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${KEY}")||"light";var d=t==="dark"||(t==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;

interface Ctx { theme: Theme; resolvedTheme: "light" | "dark"; setTheme: (t: Theme) => void }
const ThemeContext = createContext<Ctx>({ theme: "light", resolvedTheme: "light", setTheme: () => {} });
export const useTheme = () => useContext(ThemeContext);

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  window.addEventListener("storage", cb);
  mq.addEventListener("change", cb);
  return () => { listeners.delete(cb); window.removeEventListener("storage", cb); mq.removeEventListener("change", cb); };
};
const readTheme = (): Theme => { try { return (localStorage.getItem(KEY) as Theme) || "light"; } catch { return "light"; } };
const readSystemDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

export function ThemeProvider({ children }: { children: ReactNode }) {
  // External stores keep React in sync with localStorage and the OS setting; no state is set inside effects.
  const theme = useSyncExternalStore(subscribe, readTheme, () => "light" as Theme);
  const systemDark = useSyncExternalStore(subscribe, readSystemDark, () => false);
  const dark = theme === "dark" || (theme === "system" && systemDark);

  useEffect(() => { document.documentElement.classList.toggle("dark", dark); }, [dark]);

  const setTheme = useCallback((t: Theme) => { try { localStorage.setItem(KEY, t); } catch { /* private mode */ } emit(); }, []);
  const value = useMemo<Ctx>(() => ({ theme, resolvedTheme: dark ? "dark" : "light", setTheme }), [theme, dark, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
