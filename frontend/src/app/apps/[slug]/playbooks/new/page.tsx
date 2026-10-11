"use client";
import { Upload } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button, Card, inputCls } from "@/components/ui";
import { useSavePlaybook } from "@/lib/api/hooks";
import { SAMPLE_PLAYBOOK, SAMPLE_PLAYBOOK_V2 } from "@/lib/api/fixtures";
import { USE_MOCK } from "@/lib/api/client";
import { PlaybookEditor } from "@/components/live/playbook-editor";
import type { Validation } from "@/lib/api/live";

export default function UploadPlaybook() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const save = useSavePlaybook(slug);
  const [md, setMd] = useState("");
  const [validation, setValidation] = useState<Validation>();
  const file = useRef<HTMLInputElement>(null);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h2 className="text-lg font-medium">Upload playbook</h2>
      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <input ref={file} type="file" accept=".md,text/markdown,text/plain" hidden
            onChange={async (e) => { const f = e.target.files?.[0]; if (f) setMd(await f.text()); e.target.value = ""; }} />
          <Button onClick={() => file.current?.click()}><Upload className="size-4" />Choose .md file</Button>
          <Button onClick={() => setMd(USE_MOCK ? SAMPLE_PLAYBOOK : SAMPLE_PLAYBOOK_V2)}>Use sample</Button>
          <span className="text-xs text-muted">or paste Markdown below. You&apos;ll review the parsed flows before confirming.</span>
        </div>
        {USE_MOCK ? (
          <textarea aria-label="Playbook Markdown" className={`${inputCls} h-80 font-mono text-xs`} value={md} onChange={(e) => setMd(e.target.value)} placeholder={"# Playbook: My flow\n\n## Flow: login\n…"} spellCheck={false} />
        ) : <PlaybookEditor value={md} onChange={setMd} slug={slug} onValidation={setValidation} />}
        {save.error && <p role="alert" className="whitespace-pre-line text-sm text-bad">{save.error.message}</p>}
        <div className="flex justify-end gap-2">
          <Button onClick={() => router.back()}>Cancel</Button>
          <Button variant="primary" disabled={!md.trim() || save.isPending || (validation?.errors?.length ?? 0) > 0}
            onClick={() => save.mutate({ markdown: md }, { onSuccess: (pb) => router.push(`/apps/${slug}/playbooks/${pb.id}`) })}>
            {save.isPending ? "Parsing…" : "Upload & review"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
