"use client";
import { useEffect, useRef, useState } from "react";
import { API_URL, USE_MOCK, api } from "./api/client";
import type { Run, RunEvent } from "./api/types";
import { emptyView, reduce, type RunView } from "./run-state";
import { EVENT_TYPES, EventTranslator } from "./api/adapter";

export const SPEEDS = [1, 2, 4, 10] as const;

/**
 * Feeds a RunView from the event log. Mock mode replays the scripted log on a timer (pausable, variable speed);
 * real mode subscribes to /runs/{id}/events via EventSource (the browser resends Last-Event-ID on reconnect).
 * Mount it with `key={run.id + replay}`: a new key is a fresh stream, so no reset logic is needed here.
 * `animate` forces the timed path for runs that already finished (the Replay button).
 */
export function useRunStream(run: Run, animate: boolean) {
  const instant = USE_MOCK && !animate && run.status !== "running" && run.status !== "queued";
  const [view, setView] = useState<RunView>(() => (instant ? api.mockEvents(run).reduce((v, e) => reduce(v, e.event), emptyView) : emptyView));
  const total = USE_MOCK ? api.mockEvents(run).length : 0;
  const [done, setDone] = useState(instant ? total : 0);
  const [speed, setSpeedState] = useState<number>(4);
  const [paused, setPaused] = useState(false);
  const speedRef = useRef(4), pausedRef = useRef(false);
  const kick = useRef<() => void>(() => {});

  useEffect(() => {
    if (instant) return;
    if (!USE_MOCK) {
      // The backend sends named SSE events, so each type needs its own listener (onmessage never fires).
      // The browser resends Last-Event-ID on reconnect; we close for good once the run's report is ready.
      const es = new EventSource(`${API_URL}/runs/${run.id}/events`, { withCredentials: true });
      const tr = new EventTranslator(run, API_URL);
      for (const type of EVENT_TYPES) {
        es.addEventListener(type, (m) => {
          const env = JSON.parse((m as MessageEvent).data);
          const out = tr.translate(type, env);
          if (out.length) setView((v) => out.reduce((acc, ev) => reduce(acc, ev as RunEvent), v));
          if (type === "error" || type === "report.failed" || (type === "report.ready" && env.payload?.kind === "run")) es.close();
        });
      }
      es.onerror = () => es.readyState === EventSource.CLOSED && es.close();
      return () => es.close();
    }
    const events = api.mockEvents(run);
    let i = 0, timer: ReturnType<typeof setTimeout> | undefined, dead = false;
    const step = () => {
      if (dead || pausedRef.current || i >= events.length) return;
      const batch = [events[i++]];
      while (i < events.length && events[i].ts === batch[0].ts) batch.push(events[i++]);
      setView((v) => batch.reduce((acc, e) => reduce(acc, e.event), v));
      setDone(i);
      const last = batch[batch.length - 1].event;
      if (last.type === "run.finished") api.mockFinish(run.id, { status: last.payload.status, totals: last.payload.totals, finished_at: last.payload.finished_at });
      if (i < events.length) timer = setTimeout(step, Math.max(16, (events[i].ts - batch[0].ts) / speedRef.current));
    };
    kick.current = () => { clearTimeout(timer); step(); };
    timer = setTimeout(step, 0);
    return () => { dead = true; clearTimeout(timer); };
    // run.id, not run: a refetched Run object must not restart the stream.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.id, instant]);

  return {
    view, speed, paused, progress: { i: done, n: total },
    setSpeed: (s: number) => { speedRef.current = s; setSpeedState(s); },
    togglePause: () => {
      pausedRef.current = !pausedRef.current;
      setPaused(pausedRef.current);
      if (!pausedRef.current) kick.current();
    },
  };
}
