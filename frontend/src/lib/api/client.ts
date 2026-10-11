import type { App, AppInput, FlowHistory, Mode, Playbook, PlaybookVersion, Run, SseEnvelope } from "./types";
import { buildRunEvents, makeRun, seedApps, seedPlaybooks, seedRuns } from "./fixtures";
import { parsePlaybook } from "../playbook-parser";

/** Unset → in-browser mock backed by fixtures (F0–F5). Set → real API (F6). */
export const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
export const USE_MOCK = !API_URL;

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!res.ok) throw new ApiError(res.status, (await res.text().catch(() => "")) || res.statusText);
  return res.json();
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

// ---------- mock store (module-level so it survives client navigations) ----------
const db = { apps: seedApps(), playbooks: seedPlaybooks(), runs: seedRuns(), live: new Map<string, SseEnvelope[]>() };
const delay = <T,>(v: T, ms = 150) => new Promise<T>((r) => setTimeout(() => r(v), ms));
const uid = () => Math.random().toString(36).slice(2, 10);
const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "app";
const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7).toString(16).padStart(8, "0");

export const api = {
  listApps: (): Promise<App[]> => USE_MOCK ? delay([...db.apps]) : http("/apps"),

  async getApp(slug: string): Promise<App> {
    if (!USE_MOCK) return http(`/apps/${slug}`);
    const a = db.apps.find((x) => x.slug === slug);
    if (!a) throw new ApiError(404, `App '${slug}' not found`);
    return delay(a);
  },

  async createApp(input: AppInput): Promise<App> {
    if (!USE_MOCK) return http("/apps", { method: "POST", body: JSON.stringify(input) });
    let slug = slugify(input.name);
    while (db.apps.some((a) => a.slug === slug)) slug += "-" + uid().slice(0, 2);
    const app: App = {
      id: "app-" + uid(), slug, allowed_hosts: [new URL(input.base_url).hostname], prd_markdown: "", default_mode: "hybrid",
      gate_overrides: {}, redact_keys: ["authorization", "cookie"], created_at: new Date().toISOString(), ...input,
    };
    db.apps.push(app);
    return delay(app);
  },

  async updateApp(slug: string, patch: Partial<App>): Promise<App> {
    if (!USE_MOCK) return http(`/apps/${slug}`, { method: "PATCH", body: JSON.stringify(patch) });
    const a = db.apps.find((x) => x.slug === slug);
    if (!a) throw new ApiError(404, "not found");
    return delay(Object.assign(a, patch));
  },

  async listPlaybooks(slug: string): Promise<Playbook[]> {
    if (!USE_MOCK) return http(`/apps/${slug}/playbooks`);
    const app = await api.getApp(slug);
    return delay(db.playbooks.filter((p) => p.app_id === app.id));
  },

  async getPlaybook(id: string): Promise<Playbook> {
    if (!USE_MOCK) return http(`/playbooks/${id}`);
    const p = db.playbooks.find((x) => x.id === id);
    if (!p) throw new ApiError(404, "Playbook not found");
    return delay(p);
  },

  /** Upload a new playbook, or a new version when `playbookId` is given. Parse errors come back as warnings, not exceptions. */
  async savePlaybook(slug: string, markdown: string, playbookId?: string): Promise<Playbook> {
    if (!USE_MOCK) return http(playbookId ? `/playbooks/${playbookId}/versions` : `/apps/${slug}/playbooks`, { method: "POST", body: JSON.stringify({ raw_markdown: markdown }) });
    const app = await api.getApp(slug);
    const parsed = parsePlaybook(markdown);
    let pb = playbookId ? db.playbooks.find((p) => p.id === playbookId) : undefined;
    if (!pb) {
      pb = { id: "pb-" + uid(), app_id: app.id, name: parsed.parsed.title || "Untitled playbook", current_version_id: "", status: "draft", versions: [] };
      db.playbooks.push(pb);
    }
    const v: PlaybookVersion = {
      id: "pbv-" + uid(), playbook_id: pb.id, version_no: pb.versions.length + 1, raw_markdown: markdown,
      ...parsed, content_hash: hash(markdown), created_at: new Date().toISOString(),
    };
    pb.versions.unshift(v);
    pb.current_version_id = v.id;
    pb.status = "draft";
    return delay(pb, 300);
  },

  async confirmPlaybook(id: string): Promise<Playbook> {
    if (!USE_MOCK) return http(`/playbooks/${id}/confirm`, { method: "POST" });
    const p = await api.getPlaybook(id);
    p.status = "confirmed";
    return p;
  },

  async listRuns(slug: string): Promise<Run[]> {
    if (!USE_MOCK) return http(`/apps/${slug}/runs`);
    const app = await api.getApp(slug);
    return delay(db.runs.filter((r) => r.app_id === app.id).sort((a, b) => b.started_at.localeCompare(a.started_at)));
  },

  async getRun(id: string): Promise<Run> {
    if (!USE_MOCK) return http(`/runs/${id}`);
    const r = db.runs.find((x) => x.id === id);
    if (!r) throw new ApiError(404, "Run not found");
    return delay(r);
  },

  async startRun(slug: string, playbookVersionId: string, mode: Mode): Promise<Run> {
    if (!USE_MOCK) return http("/runs", { method: "POST", body: JSON.stringify({ app_slug: slug, playbook_version_id: playbookVersionId, mode }) });
    const run = makeRun("run-" + uid(), mode, 0, playbookVersionId);
    const pb = db.playbooks.find((p) => p.versions.some((v) => v.id === playbookVersionId));
    run.playbook_name = pb?.name ?? run.playbook_name;
    db.runs.unshift(run);
    db.live.set(run.id, buildRunEvents(run));
    return delay(run);
  },

  /** Per-flow results across runs. Mock derives them from the scripted event logs. */
  async flowHistory(slug: string): Promise<FlowHistory[]> {
    if (!USE_MOCK) return http(`/apps/${slug}/flows`);
    const runs = await api.listRuns(slug);
    const by = new Map<string, FlowHistory>();
    for (const r of [...runs].reverse()) {
      if (r.status === "running") continue;
      const ev = api.mockEvents(r).map((e) => e.event);
      for (const e of ev) {
        if (e.type === "run.started") e.payload.flows.forEach((f) => by.has(f.key) || by.set(f.key, { flow_key: f.key, severity: f.severity, runs: [] }));
        if (e.type === "flow.finished") by.get(e.payload.flow_key)?.runs.unshift({
          run_id: r.id, mode: r.mode, status: e.payload.status, duration_ms: e.payload.duration_ms, started_at: r.started_at,
          findings: ev.filter((x) => x.type === "finding" && x.payload.flow_key === e.payload.flow_key).length,
        });
      }
    }
    return delay([...by.values()]);
  },

  async stopRun(id: string): Promise<void> {
    if (!USE_MOCK) await http(`/runs/${id}/stop`, { method: "POST" });
  },

  /** Mock only: the scripted event log for a run. Real runs stream from /runs/{id}/events instead. */
  mockEvents(run: Run): SseEnvelope[] {
    let ev = db.live.get(run.id);
    if (!ev) { ev = buildRunEvents(run); db.live.set(run.id, ev); }
    return ev;
  },
  /** Mock only: persist the finished state so history shows real totals. */
  mockFinish(runId: string, patch: Partial<Run>) {
    const r = db.runs.find((x) => x.id === runId);
    if (r) Object.assign(r, patch);
  },
};
