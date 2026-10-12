"use client";
// Hooks for the features that only exist on the real backend (issues, reports, traceability, evidence, playbook
// validation, PRD extraction, normalize, replay). Types come from the generated schema (npm run gen:api).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_ORIGIN, USE_MOCK, api, http } from "./client";
import { mockLive } from "./mock-live";
import type { components } from "./schema";

type S = components["schemas"];
export type Issue = S["IssueResponse"];
export type IssueDetail = S["IssueDetailResponse"];
export type Report = S["ReportResponse"];
export type Traceability = S["TraceabilityResponse"];
export type Validation = S["PlaybookValidationResponse"];
export type Proposal = S["RequirementProposal"];
export type FlowSummary = S["FlowSummaryResponse"];
export type TapeEntry = S["TapeEntry"];
// The API always sends every field; the generated type marks defaulted ones optional, so tighten it here.
export type Dashboard = Omit<Required<S["DashboardResponse"]>, "series" | "per_app" | "recent_runs" | "top_bugs"> & {
  series: Required<S["DashboardDay"]>[]; per_app: Required<S["DashboardApp"]>[]; recent_runs: Required<S["DashboardRun"]>[]; top_bugs: Required<S["DashboardBug"]>[];
};

export interface StepArtifact { id: string; kind: string; flow_key: string | null; step_seq: number | null; url: string; content_type: string }
export interface EvidenceItem { id: string; kind: string; ref_id: string; note: string; artifact_id?: string | null; available?: boolean; url?: string | null; call?: { id: string; method: string; url: string; status: number; duration_ms: number; traceparent?: string | null } }
export interface Evidence {
  finding: { id: string; run_id: string; flow_run_id: string; step_seq: number; severity: string; kind: string; title: string; expected: string; actual: string; check_key: string; requirement_keys: string[]; fingerprint: string; issue_id: string | null; judged_by: string };
  check_result: { check_key: string; passed: boolean; expected: string; actual: string; inputs: Record<string, Record<string, unknown>>; judged_by: string; confidence: number | null } | null;
  evidence: EvidenceItem[];
  decisions: { step_id: string; decider: string; choice: number; confidence: number; branch: string; few_shot_ids: string[] }[];
  spans: { span_id: string; name: string; kind: string; start_ns: number; end_ns: number }[];
  integrity: { run_id: string | null; playbook_version_id: string | null };
}

/** Absolute URL for a backend-relative path such as /api/artifacts/... */
export const assetUrl = (path?: string | null) => (path ? (path.startsWith("http") ? path : API_ORIGIN + path) : "");
const pick = <T,>(mock: () => Promise<T>, real: () => Promise<T>) => (USE_MOCK ? mock() : real());

export const useIssues = (slug: string, status?: string) =>
  useQuery({ queryKey: ["issues", slug, status], queryFn: () => pick(() => mockLive.issues(status), () => http<Issue[]>(`/apps/${slug}/issues${status ? `?status=${status}` : ""}`)) });
export const useIssue = (id: string) => useQuery({ queryKey: ["issue", id], queryFn: () => pick(() => mockLive.issue(id), () => http<IssueDetail>(`/issues/${id}`)) });
export const useIssueReport = (id: string) => useQuery({ queryKey: ["issue-report", id], queryFn: () => pick(() => mockLive.issueReport(id), () => http<Report>(`/issues/${id}/report`)), retry: false });
export const useRunReport = (runId: string) =>
  useQuery({ queryKey: ["run-report", runId], queryFn: () => pick(() => mockLive.runReport(runId), () => http<Report>(`/runs/${runId}/report`)), retry: false, refetchInterval: (q) => (q.state.status === "error" ? 3000 : false) });
export const useTraceability = (slug: string) => useQuery({ queryKey: ["trace", slug], queryFn: () => pick(() => mockLive.traceability(), () => http<Traceability>(`/apps/${slug}/traceability`)), retry: false });
export const useEvidence = (findingId: string | null) =>
  useQuery({ queryKey: ["evidence", findingId], enabled: !!findingId, queryFn: () => pick(() => mockLive.evidence(findingId!), () => http<Evidence>(`/findings/${findingId}/evidence`)) });
export const useStepArtifacts = (runId: string, flow: string, seq: number, enabled: boolean) =>
  useQuery({ queryKey: ["step-artifacts", runId, flow, seq], enabled: !USE_MOCK && enabled,
    queryFn: () => http<StepArtifact[]>(`/runs/${runId}/artifacts?flow_key=${encodeURIComponent(flow)}&step_seq=${seq}`) });
export const useAppFlows = (slug: string) => useQuery({ queryKey: ["app-flows", slug], enabled: !USE_MOCK, queryFn: () => http<FlowSummary[]>(`/apps/${slug}/flows`) });

/** Live validation of playbook Markdown (errors, warnings, coverage, parsed items). Debounce in the caller. */
export const useValidate = (markdown: string) =>
  useQuery({ queryKey: ["validate", markdown], enabled: markdown.trim().length > 0, placeholderData: (prev) => prev,
    queryFn: () => pick(async () => mockLive.validate(markdown), () => http<Validation>("/playbooks/validate", { method: "POST", body: JSON.stringify({ raw_text: markdown }) })) });

export const useExtractPrd = (slug: string) =>
  useMutation({ mutationFn: () => pick(() => mockLive.extractPrd(slug), () => http<{ proposals: Proposal[]; markdown: string }>(`/apps/${slug}/prd/extract`, { method: "POST" })) });
export const useNormalize = () =>
  useMutation({ mutationFn: (raw: string) => pick(() => mockLive.normalize(raw), () => http<{ markdown: string; warnings: string[]; notes: string | null }>("/playbooks/normalize", { method: "POST", body: JSON.stringify({ raw_text: raw }) })) });
export function useReplay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { runId: string; overrides: Record<string, unknown> }) => USE_MOCK ? api.mockReplay(v.runId) : http<{ id: string; app_id: string }>(`/runs/${v.runId}/replay`, { method: "POST", body: JSON.stringify({ overrides: v.overrides }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}
export function useRegenerateReport(runId: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => USE_MOCK ? mockLive.runReport(runId) : http<Report>(`/runs/${runId}/report`, { method: "POST" }), onSuccess: (r) => qc.setQueryData(["run-report", runId], r) });
}

/** Every model call of a run in order: plans, step decisions, judgements, report calls. */
export const useTape = (runId: string) =>
  useQuery({ queryKey: ["tape", runId], queryFn: () => pick(() => mockLive.tape(runId), () => http<TapeEntry[]>(`/runs/${runId}/tape`)) });

/** Home dashboard: totals, trends, bugs and app health across every app. */
export const useDashboard = (days: number) =>
  useQuery({ queryKey: ["dashboard", days], queryFn: () => pick(() => mockLive.dashboard(days), () => http<Dashboard>(`/dashboard?days=${days}`)), refetchInterval: 15_000 });
