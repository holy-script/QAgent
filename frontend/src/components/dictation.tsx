"use client";
import { FileUp, Mic, Sparkles, Square } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore, type ComponentProps } from "react";
import { toast } from "sonner";
import { Button, cn, inputCls } from "@/components/ui";
import { api } from "@/lib/api/client";
import { LANGUAGES, appendDictation, saveLanguage, savedLanguage, useDictation } from "@/lib/dictation";
import type { RefineKind } from "@/lib/refine-mock";

// The chosen dictation language is remembered; a tiny store keeps every mic button in step with it.
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
const useLanguage = () => useSyncExternalStore(subscribe, savedLanguage, () => "en-US");
const setLanguage = (code: string) => { saveLanguage(code); listeners.forEach((l) => l()); };

/** Mic button with a language picker. Each finished phrase goes to `onText`; the phrase being heard shows beside it. */
export function Dictate({ onText, label = "Dictate", className, compact }: { onText: (chunk: string) => void; label?: string; className?: string; compact?: boolean }) {
  const lang = useLanguage();
  const d = useDictation(onText, lang);
  return (
    <span className={cn("inline-flex min-w-0 flex-wrap items-center gap-2", className)}>
      <Button type="button" onClick={d.listening ? d.stop : d.start} disabled={!d.supported} aria-pressed={d.listening}
        aria-label={d.listening ? `Stop ${label.toLowerCase()}` : label}
        title={d.supported ? "Speak instead of typing. Say “new line” or “new paragraph” for line breaks." : "Your browser cannot dictate. Use Chrome, Edge or Safari."}
        className={cn(compact && "h-8 px-2.5", d.listening && "border-bad/50 bg-bad-soft text-bad")}>
        {d.listening ? <><span className="size-2 rounded-full bg-bad pulse-ring" /><Square className="size-3.5" />Stop</> : <><Mic className="size-4" />{!compact && label}</>}
      </Button>
      {d.supported && !compact && (
        <select aria-label="Dictation language" value={lang} onChange={(e) => setLanguage(e.target.value)} disabled={d.listening}
          className="h-8 rounded-lg border border-input bg-card px-2 text-xs text-muted-foreground">
          {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          {!LANGUAGES.some((l) => l.code === lang) && <option value={lang}>{lang}</option>}
        </select>
      )}
      <span className="min-w-0 truncate text-xs text-muted-foreground" aria-live="polite">
        {d.listening ? (d.interim ? <i>{d.interim}</i> : "Listening…") : !d.supported && !compact ? "Dictation needs Chrome, Edge or Safari." : ""}
      </span>
      {d.error && <span role="alert" className="text-xs text-bad">{d.error}</span>}
    </span>
  );
}

/** A textarea with dictation, optional AI tidy-up (with undo) and optional import from a .md/.txt file. */
export function DictatableTextarea({ value, onChange, refine, importFile, tidyLabel = "Tidy up with AI", className, ...rest }: {
  value: string; onChange: (v: string) => void; refine?: RefineKind; importFile?: boolean; tidyLabel?: string;
} & Omit<ComponentProps<"textarea">, "value" | "onChange">) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const latest = useRef(value);
  useEffect(() => { latest.current = value; }, [value]);

  const tidy = async () => {
    const before = value;
    setBusy(true); setErr(null);
    try {
      const r = await api.refineText(before, refine!);
      onChange(r.text);
      toast.success("Tidied up", { description: r.notes ?? undefined, duration: 9000, action: { label: "Undo", onClick: () => onChange(before) } });
    } catch (e) { setErr(e instanceof Error ? e.message : "Could not tidy this up"); } finally { setBusy(false); }
  };
  const load = async (f: File) => {
    if (f.size > 200_000) { setErr("That file is too large (200 KB maximum)."); return; }
    setErr(null);
    const text = await f.text();
    onChange(value.trim() ? value.replace(/\s+$/, "") + "\n\n" + text : text);
    toast.success(`Imported ${f.name}`);
  };
  return (
    <div className="space-y-2">
      <textarea {...rest} className={cn(inputCls, className)} value={value} onChange={(e) => onChange(e.target.value)} />
      <div className="flex flex-wrap items-center gap-2">
        <Dictate onText={(chunk) => onChange(appendDictation(latest.current, chunk))} />
        {refine && <Button type="button" onClick={tidy} disabled={busy || !value.trim()} title="AI fixes punctuation and wording, and organises it. You can undo."><Sparkles className="size-4" />{busy ? "Working…" : tidyLabel}</Button>}
        {importFile && (
          <>
            <input ref={file} type="file" hidden accept=".md,.markdown,.txt,text/plain,text/markdown" aria-label="Choose a text file to import" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void load(f); }} />
            <Button type="button" onClick={() => file.current?.click()}><FileUp className="size-4" />Import a file</Button>
          </>
        )}
      </div>
      {err && <p role="alert" className="text-xs text-bad">{err}</p>}
    </div>
  );
}

/** A one-line input with a small mic inside it. */
export function DictatableInput({ value, onChange, className, ...rest }: { value: string; onChange: (v: string) => void } & Omit<ComponentProps<"input">, "value" | "onChange">) {
  const latest = useRef(value);
  useEffect(() => { latest.current = value; }, [value]);
  const lang = useLanguage();
  const d = useDictation((chunk) => onChange(appendDictation(latest.current, chunk).replace(/\n+/g, " ")), lang);
  return (
    <div className="relative">
      <input {...rest} className={cn(inputCls, "pr-10", className)} value={value} onChange={(e) => onChange(e.target.value)} />
      {d.supported && (
        <button type="button" onClick={d.listening ? d.stop : d.start} aria-pressed={d.listening} aria-label={d.listening ? "Stop dictation" : "Dictate into this field"}
          className={cn("absolute right-1.5 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground", d.listening && "bg-bad-soft text-bad")}>
          {d.listening ? <Square className="size-3.5" /> : <Mic className="size-4" />}
        </button>
      )}
    </div>
  );
}
