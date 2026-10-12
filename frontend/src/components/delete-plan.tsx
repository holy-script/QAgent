"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ConfirmDelete } from "@/components/confirm-delete";
import { Button } from "@/components/ui";
import { Checkbox } from "@/components/ui/checkbox";
import { api } from "@/lib/api/client";
import { useRuns } from "@/lib/api/hooks";
import type { Playbook } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** Deletes a test plan. Past runs stay (so history and "Repeat exactly" keep working) unless the user also ticks them. */
export function DeletePlan({ slug, plan, icon, onDeleted, className }: { slug: string; plan: Playbook; icon?: boolean; onDeleted?: () => void; className?: string }) {
  const qc = useQueryClient();
  const { data: runs } = useRuns(slug);
  const [open, setOpen] = useState(false);
  const [withRuns, setWithRuns] = useState(false);
  const versions = new Set(plan.versions.map((v) => v.id));
  const mine = (runs ?? []).filter((r) => versions.has(r.playbook_version_id));
  const del = useMutation({
    mutationFn: () => api.deletePlaybook(slug, plan.id, withRuns),
    onSuccess: (r) => {
      setOpen(false);
      for (const k of ["playbooks", "runs", "dashboard", "issues"]) qc.invalidateQueries({ queryKey: [k] });
      toast.success(r.runs_deleted ? `Test plan and ${r.runs_deleted} runs deleted` : "Test plan deleted");
      onDeleted?.();
    },
  });
  return (
    <>
      {icon ? (
        <button onClick={() => setOpen(true)} aria-label={`Delete test plan ${plan.name}`} title="Delete this test plan" className={cn("rounded-md p-1.5 text-muted-foreground hover:bg-bad-soft hover:text-bad", className)}><Trash2 className="size-4" /></button>
      ) : (
        <Button variant="danger" onClick={() => setOpen(true)} className={className}><Trash2 className="size-4" />Delete test plan</Button>
      )}
      <ConfirmDelete open={open} onOpenChange={(o) => { setOpen(o); if (!o) setWithRuns(false); }} title={`Delete “${plan.name}”?`} actionLabel="Delete test plan"
        pending={del.isPending} error={del.error?.message} onConfirm={() => del.mutate()}>
        <p>The test plan and all of its versions are removed. You cannot run it again.</p>
        {mine.length > 0 ? (
          <>
            <p className="text-muted-foreground">It has {mine.length} past {mine.length === 1 ? "run" : "runs"}. By default they stay in your history (shown as “Deleted test plan”), together with their bugs and reports.</p>
            <label className="mt-2 flex items-start gap-2 text-sm"><Checkbox checked={withRuns} onCheckedChange={(v) => setWithRuns(v === true)} className="mt-0.5" />
              <span>Also delete its {mine.length} {mine.length === 1 ? "run" : "runs"}, with screenshots, proof and reports</span></label>
          </>
        ) : <p className="text-muted-foreground">It has no runs.</p>}
      </ConfirmDelete>
    </>
  );
}
