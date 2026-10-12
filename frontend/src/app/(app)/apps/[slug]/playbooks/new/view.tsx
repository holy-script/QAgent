"use client";
import { Sparkles, Upload } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Dictate } from "@/components/dictation";
import { Button, Card } from "@/components/ui";
import { appendDictation } from "@/lib/dictation";
import { useSavePlaybook } from "@/lib/api/hooks";
import { SAMPLE_PLAYBOOK } from "@/lib/api/fixtures";
import { USE_MOCK, api } from "@/lib/api/client";
import { useMutation } from "@tanstack/react-query";
import { MarkdownEditor } from "@/components/live/markdown-editor";
import { PlaybookEditor } from "@/components/live/playbook-editor";
import type { Validation } from "@/lib/api/live";

export default function UploadPlaybook() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const save = useSavePlaybook(slug);
  const [md, setMd] = useState("");
  const [validation, setValidation] = useState<Validation>();
  const file = useRef<HTMLInputElement>(null);
  const [notes, setNotes] = useState<{ notes: string | null; warnings: string[] } | null>(null);
  const fromPrd = useMutation({
    mutationFn: () => api.planFromPrd(slug),
    onSuccess: (r) => {
      const before = md;
      setMd(r.markdown);
      setNotes({ notes: r.notes, warnings: r.warnings });
      toast.success("Test plan written from your product document", { description: "Review it, fill in any test data, then save.", duration: 9000, action: before.trim() ? { label: "Undo", onClick: () => setMd(before) } : undefined });
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div><h2 className="text-lg font-medium">Add a test plan</h2><p className="text-sm text-muted-foreground">Describe what to test. Start from the sample, upload a file, or paste your own notes and use “Rewrite my notes” to turn them into a test plan.</p></div>
      <Card className="space-y-4 p-5" data-tour="new-plan">
        <div className="flex flex-wrap items-center gap-2">
          <input ref={file} type="file" accept=".md,text/markdown,text/plain" hidden
            onChange={async (e) => { const f = e.target.files?.[0]; if (f) setMd(await f.text()); e.target.value = ""; }} />
          <Button onClick={() => file.current?.click()}><Upload className="size-4" />Upload a file</Button>
          <Button onClick={() => fromPrd.mutate()} disabled={fromPrd.isPending} data-tour="plan-from-prd"
            title="AI reads your product document (Settings) and writes high-level journeys: a goal and what should be true, not click-by-click steps.">
            <Sparkles className="size-4" />{fromPrd.isPending ? "Writing the plan…" : "Create from product document"}
          </Button>
          <Button onClick={() => setMd(SAMPLE_PLAYBOOK)}>Start from a sample</Button>
          {USE_MOCK && <Dictate onText={(chunk) => setMd((m) => appendDictation(m, chunk))} />}
          <span className="text-xs text-muted-foreground">or paste text below. You can review everything before it is saved.</span>
        </div>
        {USE_MOCK ? (
          <MarkdownEditor value={md} onChange={setMd} label="Test plan text" />
        ) : <PlaybookEditor value={md} onChange={setMd} slug={slug} onValidation={setValidation} />}
        {fromPrd.error && <p role="alert" className="text-sm text-bad">{fromPrd.error.message}</p>}
        {notes && (notes.notes || notes.warnings.length > 0) && (
          <div className="space-y-1 rounded-lg border border-warn/30 bg-warn-soft px-4 py-3 text-sm" role="status">
            <div className="font-medium text-warn">Check before saving</div>
            {notes.notes && <p>{notes.notes}</p>}
            {notes.warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        )}
        {save.error && <p role="alert" className="whitespace-pre-line text-sm text-bad">{save.error.message}</p>}
        <div className="flex justify-end gap-2">
          <Button onClick={() => router.back()}>Cancel</Button>
          <Button variant="primary" disabled={!md.trim() || save.isPending || (validation?.errors?.length ?? 0) > 0}
            onClick={() => save.mutate({ markdown: md }, { onSuccess: (pb) => router.push(`/apps/${slug}/playbooks/${pb.id}`) })}>
            {save.isPending ? "Checking…" : "Save and review"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
