"use client";
import "@xyflow/react/dist/style.css";
import { Background, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";
import { Card, cn } from "@/components/ui";
import { activeStep, type RunView } from "@/lib/run-state";

type NodeData = { label: string; sub?: string; count: number; tone: "slate" | "accent" | "violet" | "warn" | "ok" | "bad"; active: boolean };
const RING: Record<NodeData["tone"], string> = {
  slate: "border-slate-500/50", accent: "border-accent/60", violet: "border-violet/60", warn: "border-warn/60", ok: "border-ok/60", bad: "border-bad/60",
};

function StageNode({ data }: NodeProps<Node<NodeData>>) {
  return (
    <div className={cn("w-36 rounded-xl border bg-surface-2 px-3 py-2.5 text-center transition", RING[data.tone], data.active && "pulse-ring scale-105 border-accent bg-accent/10")}>
      <Handle type="target" position={Position.Left} className="!size-1.5 !border-0 !bg-slate-500" />
      <div className="text-sm font-medium">{data.label}</div>
      {data.sub && <div className="text-[11px] text-muted">{data.sub}</div>}
      <div className="mt-1 text-lg font-semibold tabular-nums">{data.count}</div>
      <Handle type="source" position={Position.Right} className="!size-1.5 !border-0 !bg-slate-500" />
      <Handle id="b" type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-slate-500" />
      <Handle id="bt" type="target" position={Position.Bottom} className="!size-1.5 !border-0 !bg-slate-500" />
      <Handle id="t" type="source" position={Position.Top} className="!size-1.5 !border-0 !bg-slate-500" />
      <Handle id="tt" type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-slate-500" />
    </div>
  );
}
const nodeTypes = { stage: StageNode };

/** Which stage of the loop the agent is in right now, from the newest step's progress. */
function activeStage(v: RunView, running: boolean): string | null {
  if (!running) return null;
  const s = activeStep(v);
  if (!v.flows.length) return "plan";
  if (!s) return "observe";
  if (!s.decisions.length) return "decide";
  if (!s.timings) return s.decisions.length > 1 ? "escalate" : "gate";
  return s.status === "running" ? "verify" : "observe";
}

export function GraphTab({ view, running }: { view: RunView; running: boolean }) {
  const { nodes, edges } = useMemo(() => {
    const steps = view.flows.flatMap((f) => f.steps);
    const mode = view.run?.mode;
    const escalated = steps.filter((s) => s.decisions.length > 1).length;
    const acted = steps.filter((s) => s.timings).length;
    const verified = steps.filter((s) => s.status !== "running").length;
    const auto = steps.filter((s) => s.decisions.length && s.decisions[0].branch === "AUTO").length;
    const failed = steps.filter((s) => s.status === "failed").length;
    const act = activeStage(view, running);
    const n = (id: string, x: number, y: number, label: string, count: number, tone: NodeData["tone"], sub?: string): Node<NodeData> => ({
      id, type: "stage", position: { x, y }, data: { label, sub, count, tone, active: act === id }, draggable: false,
    });
    const nodes = [
      n("plan", 0, 60, "Plan", view.flows.length, "violet", "Claude"),
      n("observe", 200, 60, "Observe", steps.length, "slate", "extract ≤40"),
      n("decide", 400, 60, "Decide", steps.length, "accent", mode === "baseline" ? "Claude" : "Jev"),
      n("gate", 600, 60, "Gate", steps.length, "warn", `auto ≥ 0.75`),
      n("act", 800, 60, "Act", acted, "ok", "Playwright"),
      n("verify", 1000, 60, "Verify", verified, failed ? "bad" : "ok", `${failed} failed`),
      n("finish", 1200, 60, "Report", view.done ? 1 : 0, "violet", "Claude"),
      n("escalate", 600, 230, "Escalate", escalated, "violet", "Claude re-decide"),
    ];
    const e = (id: string, source: string, target: string, label?: string, extra: Partial<Edge> = {}): Edge => ({
      id, source, target, label, animated: act === source || act === target,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#64748b" }, style: { stroke: "#64748b", strokeWidth: 1.5 },
      labelStyle: { fill: "#8b95a9", fontSize: 11 }, labelBgStyle: { fill: "#090d16" }, ...extra,
    });
    const edges = [
      e("plan-observe", "plan", "observe"),
      e("observe-decide", "observe", "decide"),
      e("decide-gate", "decide", "gate"),
      e("gate-act", "gate", "act", `AUTO ${auto}`),
      e("gate-escalate", "gate", "escalate", `ESCALATE ${escalated}`, { sourceHandle: "b", targetHandle: "tt", style: { stroke: "#f59e0b", strokeWidth: 1.5 } }),
      e("escalate-act", "escalate", "act", undefined, { sourceHandle: "t", targetHandle: "bt" }),
      e("act-verify", "act", "verify"),
      e("verify-observe", "verify", "observe", "next step", { sourceHandle: "t", targetHandle: "tt", type: "smoothstep" }),
      e("verify-finish", "verify", "finish", "flow done"),
    ];
    return { nodes, edges };
  }, [view, running]);

  return (
    <div className="space-y-3">
      <Card className="h-[26rem] overflow-hidden">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.15 }}
          nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} zoomOnScroll={false} proOptions={{ hideAttribution: true }}>
          <Background gap={24} color="#1e293b" />
        </ReactFlow>
      </Card>
      <p className="text-xs text-muted">Counts are cumulative across the run. The pulsing stage is where the agent is right now; amber is the escalation path to Claude when Jev&apos;s confidence falls below the gate.</p>
    </div>
  );
}
