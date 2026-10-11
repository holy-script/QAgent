"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { AppInput, Mode } from "./types";

export const useApps = () => useQuery({ queryKey: ["apps"], queryFn: api.listApps });
export const useApp = (slug: string) => useQuery({ queryKey: ["app", slug], queryFn: () => api.getApp(slug) });
export const usePlaybooks = (slug: string) => useQuery({ queryKey: ["playbooks", slug], queryFn: () => api.listPlaybooks(slug) });
export const usePlaybook = (id: string) => useQuery({ queryKey: ["playbook", id], queryFn: () => api.getPlaybook(id) });
export const useRuns = (slug: string) => useQuery({ queryKey: ["runs", slug], queryFn: () => api.listRuns(slug) });
export const useFlowHistory = (slug: string) => useQuery({ queryKey: ["flows", slug], queryFn: () => api.flowHistory(slug) });
export const useRun = (id: string) => useQuery({ queryKey: ["run", id], queryFn: () => api.getRun(id) });

export function useCreateApp() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (i: AppInput) => api.createApp(i), onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }) });
}
export function useSavePlaybook(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { markdown: string; playbookId?: string }) => api.savePlaybook(slug, v.markdown, v.playbookId),
    onSuccess: (pb) => { qc.invalidateQueries({ queryKey: ["playbooks", slug] }); qc.setQueryData(["playbook", pb.id], pb); },
  });
}
export function useConfirmPlaybook(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.confirmPlaybook,
    onSuccess: (pb) => { qc.invalidateQueries({ queryKey: ["playbooks", slug] }); qc.setQueryData(["playbook", pb.id], pb); },
  });
}
export function useStartRun(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { versionId: string; mode: Mode }) => api.startRun(slug, v.versionId, v.mode),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs", slug] }),
  });
}
