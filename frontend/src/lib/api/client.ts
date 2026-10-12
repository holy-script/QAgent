import type { App, AppInput, FlowHistory, Mode, Playbook, PlaybookVersion, RetentionStatus, Run, TestFile, SseEnvelope } from "./types";
import { buildRunEvents, makeRun, seedApps, seedPlaybooks, seedRuns, versionFrom } from "./fixtures";
import { validateMarkdown } from "../playbook-validate";
import { mockRefine, type RefineKind } from "../refine-mock";
import { toApp, toFlowHistory, toPlaybook, toRun } from "./adapter";

/** Unset → in-browser mock backed by fixtures (F0–F5). Set → real API (F6). */
export const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
export const USE_MOCK = !API_URL;
/** Where `/api/...` paths from the backend (screenshot URLs) are served. API_URL may already end in /api (same-origin deploy: NEXT_PUBLIC_API_URL=/api). */
export const API_ORIGIN = API_URL.replace(/\/api$/, "");

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...init?.headers } });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/") && !window.location.pathname.startsWith("/login")) {
    // The session ended (or never started): go to the sign-in page and come back afterwards.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- a full reload clears cached data after sign-out
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
  }
  if (!res.ok) throw new ApiError(res.status, detailOf(await res.text().catch(() => "")) || res.statusText);
  return res.json();
}
export const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MOCK_BUILTIN: TestFile[] = [["sample.png", "image/png", 74], ["sample.pdf", "application/pdf", 214], ["sample.txt", "text/plain", 25], ["sample.csv", "text/csv", 24], ["sample.json", "application/json", 17]]
  .map(([name, content_type, size_bytes]) => ({ id: `builtin:${name}`, name: name as string, content_type: content_type as string, size_bytes: size_bytes as number, created_at: "", builtin: true }));
const mockFileStore = new Map<string, TestFile[]>();
const mockFiles = (slug: string): TestFile[] => { if (!mockFileStore.has(slug)) mockFileStore.set(slug, []); return mockFileStore.get(slug)!; };

/** Same rule as the backend: finished runs older than the policy, except the newest `keep_last`. */
export function expiredMock(a: App, runs: Run[]): Run[] {
  if (!a.retention_days) return [];
  const cutoff = Date.now() - a.retention_days * 86_400_000;
  const protectedIds = new Set([...runs].sort((x, y) => +new Date(y.started_at) - +new Date(x.started_at)).slice(0, a.retention_keep_last).map((r) => r.id));
  return runs.filter((r) => !protectedIds.has(r.id) && !["running", "queued"].includes(r.status) && +new Date(r.started_at) < cutoff);
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** FastAPI validation errors arrive as {detail: {errors: [...]}} or {detail: "..."}; show them as readable text. */
function detailOf(text: string): string {
  try {
    const d = JSON.parse(text).detail;
    if (d?.errors) return d.errors.join("\n");
    if (Array.isArray(d)) return d.map((e: { msg?: string; type?: string }) => (e.type === "string_too_long" ? "That text is too long for this tool (200,000 characters at most)." : e.msg ?? "Invalid input")).join("\n"); // never echo the input back
    return typeof d === "string" ? d : text;
  } catch { return text; }
}

// ---------- real API helpers ----------
/* eslint-disable @typescript-eslint/no-explicit-any */
async function realPlaybook(id: string): Promise<Playbook> {
  const [pb, versions] = await Promise.all([http<any>(`/playbooks/${id}`), http<any[]>(`/playbooks/${id}/versions`)]);
  const full = await Promise.all(versions.map(async (v) => ({ ...v, ...(await http<any>(`/playbook-versions/${v.id}/markdown`)) })));
  return toPlaybook(pb, full);
}
async function versionNames(appId: string): Promise<Map<string, string>> {
  const names = new Map<string, string>();
  for (const pb of await http<any[]>(`/apps/${encodeURIComponent(appId)}/playbooks`))
    for (const v of await http<any[]>(`/playbooks/${pb.id}/versions`)) names.set(v.id, pb.name);
  return names;
}
async function realRuns(path: string): Promise<Run[]> {
  const runs = await http<any[]>(path);
  const names = runs.length ? await versionNames(runs[0].app_id) : new Map<string, string>();
  return runs.map((r) => toRun(r, names.get(r.playbook_version_id)));
}

// ---------- mock store (module-level so it survives client navigations) ----------
const db = { apps: seedApps(), playbooks: seedPlaybooks(), runs: seedRuns(), live: new Map<string, SseEnvelope[]>() };
const delay = <T,>(v: T, ms = 150) => new Promise<T>((r) => setTimeout(() => r(v), ms));
const uid = () => Math.random().toString(36).slice(2, 10);
const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "app";

export const api = {
  listApps: async (): Promise<App[]> => USE_MOCK ? delay([...db.apps]) : (await http<any[]>("/apps")).map(toApp),

  async getApp(slug: string): Promise<App> {
    if (!USE_MOCK) return toApp(await http(`/apps/${slug}`));
    const a = db.apps.find((x) => x.slug === slug);
    if (!a) throw new ApiError(404, `App '${slug}' not found`);
    return delay(a);
  },

  async createApp(input: AppInput): Promise<App> {
    if (!USE_MOCK) return toApp(await http("/apps", { method: "POST", body: JSON.stringify(input) }));
    let slug = slugify(input.name);
    while (db.apps.some((a) => a.slug === slug)) slug += "-" + uid().slice(0, 2);
    const app: App = {
      id: "app-" + uid(), slug, allowed_hosts: [new URL(input.base_url).hostname], prd_markdown: "", default_mode: "hybrid",
      gate_overrides: {}, redact_keys: ["authorization", "cookie"], retention_days: null, retention_keep_last: 10, created_at: new Date().toISOString(), ...input,
    };
    db.apps.push(app);
    return delay(app);
  },

  async updateApp(slug: string, patch: Partial<App>): Promise<App> {
    if (!USE_MOCK) return toApp(await http(`/apps/${slug}`, { method: "PATCH", body: JSON.stringify(patch) }));
    const a = db.apps.find((x) => x.slug === slug);
    if (!a) throw new ApiError(404, "not found");
    return delay(Object.assign(a, patch));
  },

  async listPlaybooks(slug: string): Promise<Playbook[]> {
    if (!USE_MOCK) return Promise.all((await http<any[]>(`/apps/${slug}/playbooks`)).map((p) => realPlaybook(p.id)));
    const app = await api.getApp(slug);
    return delay(db.playbooks.filter((p) => p.app_id === app.id));
  },

  async getPlaybook(id: string): Promise<Playbook> {
    if (!USE_MOCK) return realPlaybook(id);
    const p = db.playbooks.find((x) => x.id === id);
    if (!p) throw new ApiError(404, "Playbook not found");
    return delay(p);
  },

  /** Upload a new playbook, or a new version when `playbookId` is given. Parse errors come back as warnings, not exceptions. */
  async savePlaybook(slug: string, markdown: string, playbookId?: string): Promise<Playbook> {
    if (!USE_MOCK) {
      // Errors (HTTP 422) block the upload; the thrown message lists them for the editor to show.
      const saved = await http<any>(playbookId ? `/playbooks/${playbookId}/versions` : `/apps/${slug}/playbooks`, { method: "POST", body: JSON.stringify({ raw_markdown: markdown }) });
      return realPlaybook(saved.playbook.id);
    }
    const app = await api.getApp(slug);
    const val = validateMarkdown(markdown);
    if (val.errors.length) throw new ApiError(422, val.errors.join("\n")); // errors block saving, like the real API
    let pb = playbookId ? db.playbooks.find((p) => p.id === playbookId) : undefined;
    if (!pb) {
      pb = { id: "pb-" + uid(), app_id: app.id, name: val.title || "Untitled test plan", current_version_id: "", status: "confirmed", versions: [] };
      db.playbooks.push(pb);
    }
    const v: PlaybookVersion = versionFrom("pbv-" + uid(), pb.id, pb.versions.length + 1, markdown, new Date().toISOString());
    if (pb.versions[0]?.content_hash === v.content_hash) return delay(pb, 200); // unchanged: no new version
    pb.versions.unshift(v);
    pb.current_version_id = v.id;
    pb.status = "confirmed";
    return delay(pb, 300);
  },

  async confirmPlaybook(id: string): Promise<Playbook> {
    if (!USE_MOCK) return realPlaybook(id); // the backend confirms on save: no draft state
    const p = await api.getPlaybook(id);
    p.status = "confirmed";
    return p;
  },

  async listRuns(slug: string): Promise<Run[]> {
    if (!USE_MOCK) return realRuns(`/apps/${slug}/runs`);
    const app = await api.getApp(slug);
    return delay(db.runs.filter((r) => r.app_id === app.id).sort((a, b) => b.started_at.localeCompare(a.started_at)));
  },

  async getRun(id: string): Promise<Run> {
    if (!USE_MOCK) { const r = await http<any>(`/runs/${id}`); return toRun(r, (await versionNames(r.app_id)).get(r.playbook_version_id)); }
    const r = db.runs.find((x) => x.id === id);
    if (!r) throw new ApiError(404, "Run not found");
    return delay(r);
  },

  async startRun(slug: string, playbookVersionId: string, mode: Mode, plan = false): Promise<Run> {
    if (!USE_MOCK) {
      const r = await http<any>(`/apps/${slug}/runs`, { method: "POST", body: JSON.stringify({ playbook_version_id: playbookVersionId, mode, plan }) });
      return toRun(r, (await versionNames(r.app_id)).get(r.playbook_version_id));
    }
    const run = makeRun("run-" + uid(), mode, 0, playbookVersionId);
    const pb = db.playbooks.find((p) => p.versions.some((v) => v.id === playbookVersionId));
    run.playbook_name = pb?.name ?? run.playbook_name;
    db.runs.unshift(run);
    db.live.set(run.id, buildRunEvents(run));
    return delay(run);
  },

  /** Per-flow results across runs. Mock derives them from the scripted event logs. */
  async flowHistory(slug: string): Promise<FlowHistory[]> {
    if (!USE_MOCK) {
      const [flows, runs] = await Promise.all([http<any[]>(`/apps/${slug}/flows`), realRuns(`/apps/${slug}/runs`)]);
      return toFlowHistory(flows, new Map(runs.map((r) => [r.id, r.mode])));
    }
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

  /** Mock only: a "repeat exactly" run that starts from a finished run. */
  async mockReplay(sourceId: string): Promise<Run> {
    const src = db.runs.find((r) => r.id === sourceId);
    if (!src) throw new ApiError(404, "Run not found");
    const run = { ...makeRun("run-" + uid(), src.mode, 0, src.playbook_version_id), trigger: "replay" as const, replay_of_run_id: src.id, playbook_name: src.playbook_name };
    db.runs.unshift(run);
    db.live.set(run.id, buildRunEvents(run));
    return run;
  },

  /** Deletes the app with its test plans, runs, bugs, reports and stored files. */
  async deleteApp(slug: string): Promise<void> {
    if (!USE_MOCK) { await http(`/apps/${slug}`, { method: "DELETE" }); return; }
    const app = await api.getApp(slug);
    db.apps = db.apps.filter((a) => a.id !== app.id);
    db.playbooks = db.playbooks.filter((p) => p.app_id !== app.id);
    db.runs = db.runs.filter((r) => r.app_id !== app.id);
  },

  async deleteRun(id: string): Promise<void> {
    if (!USE_MOCK) { await http(`/runs/${id}`, { method: "DELETE" }); return; }
    db.runs = db.runs.filter((r) => r.id !== id);
    db.live.delete(id);
  },

  /** AI tidy-up of dictated or rough text (nothing is saved). */
  async refineText(text: string, kind: RefineKind): Promise<{ text: string; notes: string | null }> {
    if (!USE_MOCK) return http(`/text/refine`, { method: "POST", body: JSON.stringify({ text, kind }) });
    return delay(mockRefine(text, kind));
  },
  async listFiles(slug: string): Promise<TestFile[]> {
    if (!USE_MOCK) return http<TestFile[]>(`/apps/${slug}/files`);
    return delay([...mockFiles(slug), ...MOCK_BUILTIN]);
  },
  async uploadFile(slug: string, file: File): Promise<TestFile> {
    if (file.size > MAX_FILE_BYTES) throw new ApiError(413, `Files can be at most ${MAX_FILE_BYTES / (1024 * 1024)} MB`);
    if (!USE_MOCK) {
      const res = await fetch(`${API_URL}/apps/${slug}/files?name=${encodeURIComponent(file.name)}`, { method: "POST", body: file, credentials: "include", headers: { "Content-Type": file.type || "application/octet-stream", "X-File-Type": file.type || "" } });
      if (!res.ok) throw new ApiError(res.status, detailOf(await res.text().catch(() => "")) || res.statusText);
      return res.json();
    }
    const list = mockFiles(slug);
    const rec: TestFile = { id: "f-" + uid(), name: file.name, content_type: file.type || "application/octet-stream", size_bytes: file.size, created_at: new Date().toISOString(), builtin: false };
    const i = list.findIndex((f) => f.name.toLowerCase() === rec.name.toLowerCase());
    if (i >= 0) list[i] = { ...rec, id: list[i].id }; else list.push(rec);
    return delay(i >= 0 ? list[i] : rec);
  },
  async deleteFile(slug: string, id: string): Promise<void> {
    if (!USE_MOCK) { await http(`/apps/${slug}/files/${id}`, { method: "DELETE" }); return; }
    const list = mockFiles(slug);
    list.splice(0, list.length, ...list.filter((f) => f.id !== id));
  },

  /** How many runs the app's clean-up policy would remove right now. */
  async retention(slug: string): Promise<RetentionStatus> {
    if (!USE_MOCK) return http<RetentionStatus>(`/apps/${slug}/retention`);
    const a = db.apps.find((x) => x.slug === slug)!;
    const runs = db.runs.filter((r) => r.app_id === a.id);
    return delay({ retention_days: a.retention_days, retention_keep_last: a.retention_keep_last, total_runs: runs.length, would_delete: expiredMock(a, runs).length, oldest_started_at: runs.map((r) => r.started_at).sort()[0] ?? null });
  },
  async cleanRetention(slug: string): Promise<{ runs_deleted: number; files_removed: number }> {
    if (!USE_MOCK) return http(`/apps/${slug}/retention/clean`, { method: "POST" });
    const a = db.apps.find((x) => x.slug === slug)!;
    const gone = new Set(expiredMock(a, db.runs.filter((r) => r.app_id === a.id)).map((r) => r.id));
    db.runs = db.runs.filter((r) => !gone.has(r.id));
    gone.forEach((id) => db.live.delete(id));
    return delay({ runs_deleted: gone.size, files_removed: gone.size * 12 });
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
