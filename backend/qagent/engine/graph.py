import asyncio
import json
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from qagent.browser.executor import BrowserExecutor
from qagent.browser.extractor import EXTRACTOR_JS
from qagent.browser.network_recorder import NetworkRecorder
from qagent.browser.sandbox import BrowserSandbox
from qagent.browser.wait_frames import WaitFramesWatcher
from qagent.config import settings
from qagent.decision.base import Decider
from qagent.decision.tape import hash_request
from qagent.domain.events import QAgentEventType
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import CandidateAction, ConfidenceTier, DecisionRequest, DecisionResult, Finding
from qagent.engine.callbacks import SpanCallbackHandler
from qagent.engine.findings import Verifier
from qagent.engine.gating import evaluate_gate
from qagent.engine.state import FlowState
from qagent.engine.tracing import Span, logger
from qagent.engine.verify import verify_flow_formulas
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue

_NAV = re.compile(r"^\s*(?:open|go to|navigate to|visit)\s+(\S+)\s*$", re.IGNORECASE)
_QUOTED = re.compile(r"""["']([^"']+)["']""")
_COUNT = re.compile(r"\b(\d{1,2})\b")
_TIMING_KEYS = ("observe_ms", "extract_ms", "decide_ms", "gate_ms", "act_ms", "settle_ms", "verify_ms")
NODES_PER_STEP = 8


def parse_navigation(intent: str) -> Optional[str]:
    """'Open /products' is deterministic navigation: no model call needed."""
    m = _NAV.match(intent)
    if m and (m.group(1).startswith("/") or m.group(1).startswith("http")):
        return m.group(1)
    return None


def repeat_count(intent: str) -> int:
    """'Add 2 items to cart' clicks the chosen control twice."""
    if intent.strip().lower().startswith("add"):
        m = _COUNT.search(intent)
        if m:
            return max(1, min(int(m.group(1)), 10))
    return 1


def resolve_fill_value(intent: str, candidate: CandidateAction, test_data: Dict[str, Any]) -> str:
    quoted = _QUOTED.search(intent)
    if quoted:
        return quoted.group(1)
    haystack = f"{intent} {candidate.label} {candidate.selector}".lower()
    for key, value in test_data.items():
        if key.lower() in haystack:
            return str(value)
    return candidate.value or "test"


@dataclass
class FlowContext:
    flow: FlowSpec
    flow_run_id: str
    trace_id: str
    findings: List[Finding] = field(default_factory=list)
    failure_reason: Optional[str] = None
    steps_run: int = 0
    log_cursor: int = 0


@dataclass
class FlowRuntime:
    """Live, non-serializable per-flow objects. Passed via config["configurable"]["rt"]."""
    ctx: FlowContext
    sandbox: BrowserSandbox
    page: Any
    recorder: NetworkRecorder
    started: float


def _rt(config: RunnableConfig) -> FlowRuntime:
    return config["configurable"]["rt"]


def _decision_payload(d: DecisionResult, req: DecisionRequest, question: str, label: str, input_hash: str,
                      **extra: Any) -> Dict[str, Any]:
    return {
        "decider": d.decider, "model_version": d.model_version, "question": question,
        "selected_action_id": d.selected_action_id, "action_label": label, "confidence": d.confidence,
        "tier": d.tier.value, "latency_ms": d.latency_ms, "cost_usd": d.cost_usd,
        "input_tokens": d.input_tokens, "output_tokens": d.output_tokens, "probabilities": d.probabilities,
        "input_hash": input_hash,
        "request": {"intent": req.intent, "url": req.url, "candidates_count": len(req.candidates)},
        "response": d.model_dump(mode="json"), **extra,
    }


class EngineRunner:
    """
    Runs a RunSpec. Each flow is one LangGraph execution (one isolated browser, one checkpoint
    thread):

        plan -> begin_step -> observe -> decide -> gate -> [escalate -> gate] -> act -> settle
                   ^                                                                  |
                   |                                                                verify
                   +---------------------------- loop ------------------------------+ -> finish

    The engine only emits events to the sink and hands files to the upload queue; it never
    touches the database or object storage. Decisions go through LangChain runnables so
    callbacks trace every model call.
    """

    def __init__(
        self,
        run_spec: RunSpec,
        decider: Decider,
        sink: PersistenceSink,
        uploader=upload_queue,
        headless: Optional[bool] = None,
        escalator: Optional[Decider] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        self.spec = run_spec
        self.decider = decider
        self.sink = sink
        self.uploader = uploader
        self.headless = headless
        self.escalator = escalator
        self.checkpointer = checkpointer or InMemorySaver()
        self.findings_count = 0
        self.total_steps = 0
        self.decision_stats = {"jev": 0, "claude": 0, "other": 0, "latency_ms": 0.0, "cost_usd": 0.0, "count": 0}
        self.cancel_requested = False

        self._decide_chain = RunnableLambda(self.decider.decide).with_config(
            run_name=f"model:{type(self.decider).__name__}")
        self._escalate_chain = (
            RunnableLambda(self.escalator.decide).with_config(run_name=f"model:{type(self.escalator).__name__}")
            if self.escalator else None
        )
        self.graph = self._build_graph()

    def stop(self) -> None:
        self.cancel_requested = True

    # ---- run -------------------------------------------------------------------------

    async def run(self) -> Dict[str, Any]:
        logger.info("engine.run.started", run_id=self.spec.run_id, mode=self.spec.mode.value)
        started = time.perf_counter()
        await self.sink.emit(QAgentEventType.RUN_STARTED, {
            "run_id": self.spec.run_id,
            "app_id": self.spec.app_id,
            "target_url": self.spec.base_url,
            "mode": self.spec.mode.value,
            "flow_count": len(self.spec.flows),
        })

        sem = asyncio.Semaphore(max(1, settings.flow_max_parallel))

        async def guarded(flow: FlowSpec) -> str:
            async with sem:
                return await self._run_flow(flow)

        try:
            flow_statuses = list(await asyncio.gather(*(guarded(f) for f in self.spec.flows)))
        except Exception as exc:
            logger.error("engine.run.error", run_id=self.spec.run_id, error=str(exc))
            await self.sink.emit(QAgentEventType.RUN_ERROR, {"run_id": self.spec.run_id, "message": str(exc)})
            raise

        duration_s = time.perf_counter() - started
        if self.cancel_requested:
            status = "stopped"
        elif "failed" in flow_statuses or self.findings_count:
            status = "failed"
        else:
            status = "passed"

        stats = self.decision_stats
        totals = {
            "total_steps": self.total_steps,
            "duration_ms": duration_s * 1000.0,
            "jev_decisions": stats["jev"],
            "claude_decisions": stats["claude"],
            "total_cost_usd": stats["cost_usd"],
            "avg_decision_latency_ms": stats["latency_ms"] / stats["count"] if stats["count"] else 0.0,
            "findings_count": self.findings_count,
            "status": status,
        }
        await self.sink.emit(QAgentEventType.RUN_FINISHED, {
            "run_id": self.spec.run_id,
            "outcome": "COMPLETED",
            "status": status,
            "total_steps": self.total_steps,
            "total_cost_usd": stats["cost_usd"],
            "duration_s": duration_s,
            "findings_count": self.findings_count,
            "totals": totals,
        })
        return {
            "run_id": self.spec.run_id,
            "status": status,
            "total_steps": self.total_steps,
            "duration_s": duration_s,
            "findings_count": self.findings_count,
            "flows": dict(zip([f.key for f in self.spec.flows], flow_statuses)),
        }

    # ---- helpers ---------------------------------------------------------------------

    def _key(self, flow_key: str, suffix: str) -> str:
        return f"apps/{self.spec.app_id}/runs/{self.spec.run_id}/flows/{flow_key}/{suffix}"

    async def _upload(self, ctx: FlowContext, suffix: str, data: bytes, content_type: str,
                      kind: str, step_seq: Optional[int] = None) -> None:
        await self.uploader.enqueue(
            key=self._key(ctx.flow.key, suffix),
            data=data,
            content_type=content_type,
            run_id=self.spec.run_id,
            flow_run_id=ctx.flow_run_id,
            step_seq=step_seq,
            kind=kind,
        )

    async def _record_finding(self, ctx: FlowContext, finding: Finding) -> None:
        ctx.findings.append(finding)
        self.findings_count += 1
        await self.sink.emit(
            QAgentEventType.FINDING_DISCOVERED,
            {**finding.model_dump(mode="json"), "flow_key": ctx.flow.key},
        )

    async def _log(self, ctx: FlowContext, step_seq: Optional[int], level: str, source: str,
                   message: str, **data: Any) -> None:
        await self.sink.emit(QAgentEventType.LOG_EMITTED, {
            "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": step_seq,
            "level": level, "source": source, "message": message, "data": data,
        })

    def _count_decision(self, decision: DecisionResult) -> None:
        s = self.decision_stats
        s["count"] += 1
        s["latency_ms"] += decision.latency_ms
        s["cost_usd"] += decision.cost_usd
        s["jev" if decision.decider == "jev" else "claude" if decision.decider == "claude" else "other"] += 1

    async def _upload_flow_artifacts(self, ctx: FlowContext, sandbox: BrowserSandbox, art_dir: Path) -> None:
        for name, content_type, kind in (
            ("trace.zip", "application/zip", "trace"),
            ("har.json", "application/json", "har"),
        ):
            path = art_dir / name
            if path.exists():
                await self._upload(ctx, name, path.read_bytes(), content_type, kind)
        if sandbox.console_logs:
            lines = "\n".join(json.dumps(entry, default=str) for entry in sandbox.console_logs)
            await self._upload(ctx, "console.jsonl", lines.encode(), "application/x-ndjson", "console")

    # ---- flow ------------------------------------------------------------------------

    async def _run_flow(self, flow: FlowSpec) -> str:
        ctx = FlowContext(flow, str(uuid.uuid4()), uuid.uuid4().hex)
        flow_span = Span(f"flow:{flow.key}", "flow", ctx.trace_id, flow_key=flow.key)
        started = time.perf_counter()
        base = {"flow_key": flow.key, "flow_run_id": ctx.flow_run_id}

        await self.sink.emit(QAgentEventType.FLOW_STARTED, {
            **base, "severity": flow.severity, "total_steps": len(flow.steps),
        })

        art_dir = Path(tempfile.mkdtemp(prefix="qagent-"))
        sandbox = BrowserSandbox(
            headless=self.headless, allowed_hosts=self.spec.allowed_hosts, artifact_dir=art_dir
        )
        try:
            page = await sandbox.start()
            recorder = NetworkRecorder(page, ctx.flow_run_id)
            await page.goto(self.spec.base_url, timeout=10000)
            recorder.drain()  # landing traffic is not part of any step

            rt = FlowRuntime(ctx, sandbox, page, recorder, started)
            config: RunnableConfig = {
                "configurable": {"thread_id": ctx.flow_run_id, "rt": rt},
                "callbacks": [SpanCallbackHandler(self.sink, ctx.trace_id, flow_span, flow.key)],
                "recursion_limit": max(25, (len(flow.steps) + 1) * NODES_PER_STEP + 10),
                "run_name": f"flow:{flow.key}",
            }
            await self.graph.ainvoke(
                {"flow_key": flow.key, "flow_run_id": ctx.flow_run_id, "idx": 0, "history": [],
                 "failure_reason": None, "done": False},
                config,
            )
        except Exception as exc:
            ctx.failure_reason = f"{type(exc).__name__}: {exc}".splitlines()[0]
            logger.error("engine.flow.error", flow=flow.key, error=ctx.failure_reason)
            await self._log(ctx, None, "error", "engine", f"flow aborted: {ctx.failure_reason}")
        finally:
            await sandbox.stop()
            await self._upload_flow_artifacts(ctx, sandbox, art_dir)

        if ctx.failure_reason:
            status = "failed"
        else:
            status = "passed_with_findings" if ctx.findings else "passed"

        await self.sink.emit(QAgentEventType.SPAN_ENDED, flow_span.end("error" if ctx.failure_reason else "ok"))
        await self.sink.emit(QAgentEventType.FLOW_FINISHED, {
            **base,
            "status": status,
            "step_count": ctx.steps_run,
            "duration_ms": (time.perf_counter() - started) * 1000.0,
            "findings_count": len(ctx.findings),
            "failure_reason": ctx.failure_reason,
        })
        return status

    # ---- the graph -------------------------------------------------------------------

    def _build_graph(self):
        g: StateGraph = StateGraph(FlowState)
        g.add_node("plan", self._plan)
        g.add_node("begin_step", self._begin_step)
        g.add_node("observe", self._observe)
        g.add_node("decide", self._decide)
        g.add_node("gate", self._gate)
        g.add_node("escalate", self._escalate)
        g.add_node("act", self._act)
        g.add_node("settle", self._settle)
        g.add_node("verify", self._verify)
        g.add_node("finish", self._finish)

        g.add_edge(START, "plan")
        g.add_conditional_edges("plan", lambda s: "finish" if s.get("done") else "begin_step",
                                {"begin_step": "begin_step", "finish": "finish"})
        g.add_conditional_edges("begin_step", lambda s: "finish" if s.get("done") else "observe",
                                {"observe": "observe", "finish": "finish"})
        g.add_conditional_edges("observe", lambda s: "act" if s.get("nav_target") else "decide",
                                {"act": "act", "decide": "decide"})
        g.add_conditional_edges("decide", lambda s: "settle" if s.get("step_status") == "failed" else "gate",
                                {"settle": "settle", "gate": "gate"})
        g.add_conditional_edges("gate", self._route_gate,
                                {"act": "act", "escalate": "escalate", "settle": "settle"})
        g.add_edge("escalate", "gate")
        g.add_edge("act", "settle")
        g.add_edge("settle", "verify")
        g.add_conditional_edges("verify", lambda s: "begin_step" if s.get("step_status") == "passed" else "finish",
                                {"begin_step": "begin_step", "finish": "finish"})
        g.add_edge("finish", END)
        return g.compile(checkpointer=self.checkpointer)

    def _route_gate(self, s: FlowState) -> str:
        if s.get("step_status") in ("failed", "blocked"):
            return "settle"
        if s["tier"] != ConfidenceTier.AUTO.value and self.escalator and not s.get("escalated"):
            return "escalate"
        return "act"

    # -- nodes: each returns a partial state update --

    async def _plan(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Validates the flow. (Claude-written step intents are a later increment.)"""
        rt = _rt(config)
        if not rt.ctx.flow.steps:
            rt.ctx.failure_reason = "flow has no steps"
            return {"done": True, "failure_reason": rt.ctx.failure_reason}
        return {}

    async def _begin_step(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        flow, ctx = rt.ctx.flow, rt.ctx
        idx = state["idx"] + 1
        if idx > len(flow.steps):
            return {"done": True}
        if self.cancel_requested:
            ctx.failure_reason = "stopped by user"
        elif idx > self.spec.step_budget:
            ctx.failure_reason = f"step budget ({self.spec.step_budget}) exhausted"
        elif time.perf_counter() - rt.started > self.spec.time_budget_s:
            ctx.failure_reason = f"time budget ({self.spec.time_budget_s}s) exhausted"
        if ctx.failure_reason:
            return {"done": True, "failure_reason": ctx.failure_reason}

        ctx.steps_run = idx
        self.total_steps += 1
        intent = flow.steps[idx - 1]
        return {
            "idx": idx, "step_id": str(uuid.uuid4()), "intent": intent, "nav_target": parse_navigation(intent),
            "candidates": [], "decision": None, "chosen_id": None, "label": "", "tier": ConfidenceTier.AUTO.value,
            "escalated": False, "acted": False, "settled": True, "step_status": "passed",
            "timings": {k: 0.0 for k in _TIMING_KEYS}, "steps_run": idx,
        }

    def _base(self, state: FlowState) -> Dict[str, Any]:
        return {"flow_key": state["flow_key"], "flow_run_id": state["flow_run_id"],
                "step_seq": state["idx"], "step_id": state["step_id"]}

    def _fail(self, rt: FlowRuntime, reason: str, status: str = "failed") -> Dict[str, Any]:
        rt.ctx.failure_reason = reason
        return {"step_status": status, "failure_reason": reason}

    async def _observe(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        page, ctx = rt.page, rt.ctx
        seq = state["idx"]
        timings = dict(state["timings"])

        candidates: List[CandidateAction] = []
        t = time.perf_counter()
        if not state.get("nav_target"):
            raw = await page.evaluate(EXTRACTOR_JS)
            candidates = [CandidateAction.model_validate(c) for c in raw[:40]]
        timings["extract_ms"] = (time.perf_counter() - t) * 1000.0
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass

        shot_url = f"/api/artifacts/{self.spec.run_id}/flows/{ctx.flow.key}/steps/{seq}/screenshot.jpg"
        await self.sink.emit(QAgentEventType.STEP_OBSERVED, {
            **self._base(state), "intent": state["intent"], "url": page.url, "page_title": title,
            "candidates_count": len(candidates), "screenshot_url": shot_url,
        })
        if candidates:
            await self._upload(ctx, f"steps/{seq}/candidates.json",
                               json.dumps([c.model_dump(mode="json") for c in candidates]).encode(),
                               "application/json", "candidates", seq)
        return {"url": page.url, "title": title, "timings": timings,
                "candidates": [c.model_dump(mode="json") for c in candidates]}

    def _request(self, state: FlowState, candidates: List[CandidateAction]) -> DecisionRequest:
        return DecisionRequest(
            step_seq=state["idx"], intent=state["intent"], url=state["url"], candidates=candidates,
            page_summary=state["title"], history=state["history"][-3:],
        )

    async def _decide(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        candidates = [CandidateAction.model_validate(c) for c in state["candidates"]]
        timings = dict(state["timings"])
        if not candidates:
            return self._fail(rt, f"step {state['idx']}: no interactive elements on {state['url']}")

        req = self._request(state, candidates)
        input_hash = hash_request(req)
        t = time.perf_counter()
        decision: DecisionResult = await self._decide_chain.ainvoke(req, config)
        timings["decide_ms"] = (time.perf_counter() - t) * 1000.0

        chosen = next((c for c in candidates if c.id == decision.selected_action_id), None)
        label = chosen.label if chosen else ""
        self._count_decision(decision)
        await self.sink.emit(QAgentEventType.DECISION_MADE, {
            **self._base(state), **_decision_payload(decision, req, state["intent"], label, input_hash),
        })
        return {"decision": decision.model_dump(mode="json"), "input_hash": input_hash, "timings": timings,
                "chosen_id": chosen.id if chosen else None, "label": label}

    async def _gate(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        decision = DecisionResult.model_validate(state["decision"])
        t = time.perf_counter()
        tier = evaluate_gate(decision.confidence, self.spec.gate_auto_min, self.spec.gate_escalate_min)
        timings = dict(state["timings"])
        timings["gate_ms"] += (time.perf_counter() - t) * 1000.0

        reason = (f"Confidence {decision.confidence:.2f} "
                  f"(auto >= {self.spec.gate_auto_min}, escalate >= {self.spec.gate_escalate_min})")
        if state.get("escalated"):
            reason = f"After escalation to {decision.decider}: confidence {decision.confidence:.2f}"
        await self.sink.emit(QAgentEventType.GATE_TRIGGERED, {**self._base(state), "tier": tier.value,
                                                              "reason": reason})
        update: Dict[str, Any] = {"tier": tier.value, "timings": timings}

        can_escalate = bool(self.escalator) and not state.get("escalated")
        if state.get("chosen_id") is None:
            update.update(self._fail(rt, f"step {state['idx']}: decider chose unknown candidate "
                                         f"{decision.selected_action_id}"))
        elif tier == ConfidenceTier.STOP and not can_escalate:
            update.update(self._fail(rt, f"step {state['idx']}: confidence {decision.confidence:.2f} "
                                         f"below stop threshold", "blocked"))
        elif tier == ConfidenceTier.ESCALATE and not can_escalate:
            await self._log(rt.ctx, state["idx"], "warning", "gate",
                            "still at escalation tier after review; proceeding")
        return update

    async def _escalate(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Medium or low confidence: a stronger model re-decides this step and its answer replaces Jev's."""
        rt = _rt(config)
        candidates = [CandidateAction.model_validate(c) for c in state["candidates"]]
        req = self._request(state, candidates)
        try:
            escalated: DecisionResult = await self._escalate_chain.ainvoke(req, config)
        except Exception as exc:
            await self._log(rt.ctx, state["idx"], "warning", "gate",
                            f"escalation failed ({type(exc).__name__}); keeping original decision")
            return {"escalated": True}

        self._count_decision(escalated)
        chosen = next((c for c in candidates if c.id == escalated.selected_action_id), None)
        label = chosen.label if chosen else ""
        await self.sink.emit(QAgentEventType.DECISION_MADE, {
            **self._base(state),
            **_decision_payload(escalated, req, state["intent"], label, state["input_hash"], branch="escalated"),
        })
        return {"escalated": True, "decision": escalated.model_dump(mode="json"),
                "chosen_id": chosen.id if chosen else None, "label": label}

    async def _act(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        page, ctx = rt.page, rt.ctx
        timings = dict(state["timings"])
        base = self._base(state)

        if state.get("nav_target"):
            target = state["nav_target"]
            url = urljoin(page.url if page.url.startswith("http") else self.spec.base_url, target)
            label = f"Navigate to {target}"
            host = urlparse(url).hostname or ""
            started = time.perf_counter()
            update: Dict[str, Any] = {"acted": True, "label": label}
            if self.spec.allowed_hosts and host not in self.spec.allowed_hosts:
                update.update(self._fail(rt, f"navigation to disallowed host '{host}'"))
            else:
                try:
                    await page.goto(url, timeout=8000)
                except Exception as exc:
                    update.update(self._fail(rt, f"navigation to {target} failed: {str(exc).splitlines()[0]}"))
            timings["act_ms"] = (time.perf_counter() - started) * 1000.0
            await self.sink.emit(QAgentEventType.ACTION_EXECUTED, {
                **base, "action_id": 0, "action_label": label,
                "status": "failed" if update.get("step_status") == "failed" else "success",
                "duration_ms": timings["act_ms"],
            })
            return {**update, "timings": timings}

        chosen = next(c for c in (CandidateAction.model_validate(x) for x in state["candidates"])
                      if c.id == state["chosen_id"])
        value = resolve_fill_value(state["intent"], chosen, ctx.flow.test_data) if chosen.action_type == "fill" else None
        executor = BrowserExecutor(page)
        started = time.perf_counter()
        outcome: Dict[str, Any] = {"status": "success", "error": None}
        for _ in range(repeat_count(state["intent"])):
            outcome = await executor.execute(chosen, value)
            if outcome["status"] != "success":
                break
        timings["act_ms"] = (time.perf_counter() - started) * 1000.0
        await self.sink.emit(QAgentEventType.ACTION_EXECUTED, {
            **base, "action_id": chosen.id, "action_label": chosen.label, "status": outcome["status"],
            "duration_ms": timings["act_ms"], "error": outcome["error"],
        })
        update = {"acted": True, "timings": timings}
        if outcome["status"] != "success":
            update.update(self._fail(rt, f"step {state['idx']}: action failed: {outcome['error']}"))
        return update

    async def _settle(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Waits for the page to settle; wait frames are captured only while it is still busy."""
        rt = _rt(config)
        if not state.get("acted"):
            return {"settled": True}
        timings = dict(state["timings"])
        result = await WaitFramesWatcher(rt.page, rt.recorder).wait_until_settled(
            timeout_ms=settings.settle_timeout_ms)
        timings["settle_ms"] = result.waited_ms
        for n, frame in enumerate(result.frames, start=1):
            await self._upload(rt.ctx, f"steps/{state['idx']}/wait/{n}.jpg", frame, "image/jpeg", "wait",
                               state["idx"])
        return {"settled": result.settled, "timings": timings}

    async def _verify(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        page, ctx = rt.page, rt.ctx
        seq = state["idx"]
        timings = dict(state["timings"])

        try:
            await self._upload(ctx, f"steps/{seq}/screenshot.jpg",
                               await page.screenshot(type="jpeg", quality=75), "image/jpeg", "screenshot", seq)
            await self._upload(ctx, f"steps/{seq}/dom.html", (await page.content()).encode(),
                               "text/html", "dom", seq)
        except Exception as exc:
            await self._log(ctx, seq, "warning", "engine", f"artifact capture failed: {exc}")

        t = time.perf_counter()
        await self._emit_network(ctx, rt.recorder, seq)
        for entry in list(rt.sandbox.console_logs)[ctx.log_cursor:]:
            await self._log(ctx, seq, "error" if entry["type"] in ("error", "pageerror") else "info",
                            "browser", entry["text"], type=entry["type"])
        ctx.log_cursor = len(rt.sandbox.console_logs)

        if not state.get("settled", True):
            await self._record_finding(ctx, Verifier.check_unsettled(timings["settle_ms"], seq, ctx.flow_run_id))
        else:
            timing = Verifier.check_timing(timings["act_ms"] + timings["settle_ms"], settings.step_sla_ms,
                                           seq, ctx.flow_run_id)
            if timing:
                await self._record_finding(ctx, timing)
        timings["verify_ms"] = (time.perf_counter() - t) * 1000.0

        history = state["history"] + [{"seq": seq, "intent": state["intent"], "action": state.get("label", ""),
                                       "status": state["step_status"]}]
        await self.sink.emit(QAgentEventType.VERIFICATION_STEP, {
            **self._base(state), "status": state["step_status"], "url": page.url,
            "settled": state.get("settled", True), "timings": timings,
        })
        return {"history": history, "timings": timings}

    async def _finish(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Evaluates playbook formulas against the flow's final state (only if the flow ran clean)."""
        rt = _rt(config)
        ctx = rt.ctx
        if not ctx.failure_reason and ctx.flow.formulas:
            for finding in await verify_flow_formulas(
                rt.page, self.spec.base_url, ctx.flow, max(ctx.steps_run, 1), ctx.flow_run_id
            ):
                await self._record_finding(ctx, finding)
        return {"done": True, "failure_reason": ctx.failure_reason}

    async def _emit_network(self, ctx: FlowContext, recorder: NetworkRecorder, seq: int) -> None:
        for call in recorder.drain():
            call_id = str(uuid.uuid4())
            for suffix, body in (("request.json", call["req_body"]), ("response.json", call["resp_body"])):
                if body:
                    await self._upload(ctx, f"network/{call_id}/{suffix}", body, "application/json", "body", seq)
            await self.sink.emit(QAgentEventType.NETWORK_CALL, {
                "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": seq, "call_id": call_id,
                "method": call["method"], "url": call["url"], "status": call["status"],
                "duration_ms": call["duration_ms"], "is_api": call["is_api"],
                "req_size": call["req_size"], "resp_size": call["resp_size"],
            })
            finding = Verifier.check_network_status(
                call["status"], call["url"], seq, ctx.flow_run_id, call["method"]
            )
            if finding:
                finding.evidence["call_id"] = call_id
                await self._record_finding(ctx, finding)
