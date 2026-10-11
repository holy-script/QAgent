"use client";
import { useParams } from "next/navigation";
import { RunsTable } from "@/components/runs-table";
import { ErrorState, Loading } from "@/components/ui";
import { useRuns } from "@/lib/api/hooks";

export default function Runs() {
  const { slug } = useParams<{ slug: string }>();
  const { data, error, isPending, refetch } = useRuns(slug);
  if (isPending) return <Loading />;
  if (error) return <ErrorState error={error} retry={refetch} />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Every time you run a test plan it is recorded here. Open a run to watch it, see screenshots and read the proof.</p>
      <RunsTable slug={slug} runs={data} />
    </div>
  );
}
