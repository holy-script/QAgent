"use client";
// Speech to text with the browser's built-in recogniser (Chrome, Edge and Safari; Firefox has none). The audio is handled
// by the browser vendor's service, not by QAgent. Spoken "new line" and "new paragraph" become line breaks.
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Recognition = any;
const ctor = (): (new () => Recognition) | null =>
  typeof window === "undefined" ? null : ((window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition ?? null);

export const LANGUAGES: { code: string; label: string }[] = [
  { code: "en-US", label: "English (US)" }, { code: "en-GB", label: "English (UK)" }, { code: "en-IN", label: "English (India)" },
  { code: "hi-IN", label: "Hindi" }, { code: "es-ES", label: "Spanish" }, { code: "fr-FR", label: "French" }, { code: "de-DE", label: "German" },
  { code: "pt-BR", label: "Portuguese (Brazil)" }, { code: "it-IT", label: "Italian" }, { code: "ja-JP", label: "Japanese" },
];
const LANG_KEY = "qagent_dictation_lang";
export const savedLanguage = (): string => { try { return localStorage.getItem(LANG_KEY) ?? (navigator.language || "en-US"); } catch { return "en-US"; } };
export const saveLanguage = (code: string) => { try { localStorage.setItem(LANG_KEY, code); } catch { /* private mode */ } };

/** Turns spoken commands into text: "new line", "new paragraph". Everything else is left as heard. */
export function applyVoiceCommands(text: string): string {
  return text.replace(/\s*\bnew paragraph\b[.,]?\s*/gi, "\n\n").replace(/\s*\bnew line\b[.,]?\s*/gi, "\n");
}

/** Joins a dictated chunk onto existing text with sensible spacing (and a capital after a full stop). */
export function appendDictation(existing: string, chunk: string): string {
  const add = applyVoiceCommands(chunk.trim());
  if (!add) return existing;
  if (!existing) return add;
  if (/\s$/.test(existing) || add.startsWith("\n")) return existing + add;
  return existing + " " + add;
}

export const dictationSupported = () => ctor() !== null;
/** Hydration-safe: false while the server HTML is adopted, then the real answer for this browser. */
export const useDictationSupported = () => useSyncExternalStore(() => () => {}, dictationSupported, () => false);

const MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access is blocked. Allow it in the address bar, then try again.",
  "service-not-allowed": "Microphone access is blocked. Allow it in the address bar, then try again.",
  "audio-capture": "No microphone was found.",
  network: "Speech recognition needs an internet connection.",
  "language-not-supported": "That language is not supported by your browser.",
};

/** Start/stop dictation. `onText` gets each finished phrase; `interim` is the phrase still being heard. */
export function useDictation(onText: (chunk: string) => void, lang: string) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const want = useRef(false);
  const cb = useRef(onText);
  useEffect(() => { cb.current = onText; }, [onText]);

  const stop = useCallback(() => { want.current = false; rec.current?.stop(); setListening(false); setInterim(""); }, []);

  const start = useCallback(() => {
    const C = ctor();
    if (!C) { setError("Your browser cannot dictate. Use Chrome, Edge or Safari."); return; }
    setError(null);
    const r: Recognition = new C();
    r.lang = lang; r.continuous = true; r.interimResults = true;
    r.onresult = (e: any) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) cb.current(res[0].transcript); else live += res[0].transcript;
      }
      setInterim(live);
    };
    r.onerror = (e: any) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      setError(MESSAGES[e.error] ?? `Dictation stopped (${e.error}).`);
      want.current = false; setListening(false);
    };
    // Browsers end the session after a pause; keep going until the user presses stop.
    r.onend = () => { if (want.current) { try { r.start(); } catch { setListening(false); } } else setListening(false); setInterim(""); };
    rec.current = r; want.current = true;
    try { r.start(); setListening(true); } catch { setError("Could not start the microphone."); want.current = false; }
  }, [lang]);

  useEffect(() => () => { want.current = false; rec.current?.abort?.(); }, []);
  const supported = useDictationSupported();
  return { listening, interim, error, start, stop, supported };
}
