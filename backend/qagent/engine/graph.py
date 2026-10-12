import asyncio
import json
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin, urlparse

import httpx
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from qagent.browser.executor import BrowserExecutor
from qagent.browser.extractor import EXTRACTOR_JS
from qagent.browser.network_recorder import NetworkRecorder
from qagent.browser.redact import redact_body
from qagent.browser.sandbox import BrowserSandbox
from qagent.browser.selecting import choose_option, parse_utility, run_utility
from qagent.browser.wait_frames import WaitFramesWatcher, page_signature, wait_dom_stable
from qagent.checks import a11y, expectations, formulas as formula_checks, timing, ux_rules
from qagent.checks.base import CheckOutcome
from qagent.checks.resolver import BindingResolver
from qagent.checks.ux_judged import Judge
from qagent.config import settings
from qagent.browser import uploads
from qagent.decision.base import Decider
from qagent.decision.ledger import LedgerClient, TapedJudge, current_flow_run
from qagent.decision.director import next_step as direct_next_step
from qagent.decision.planner import plan_flow, step_hints
from qagent.decision.fewshot import example_ids, select_examples
from qagent.decision.tape import hash_request
from qagent.domain.events import QAgentEventType
from qagent.domain.runspec import FlowSpec, RunSpec
from qagent.domain.schemas import CandidateAction, ConfidenceTier, DecisionRequest, DecisionResult
from qagent.engine.callbacks import SpanCallbackHandler
from qagent.engine.gating import evaluate_gate
from qagent.engine.secrets import SecretMasker
from qagent.engine.state import FlowState
from qagent.engine.tracing import Span, logger
from qagent.reports.findings import final_severity, fingerprint
from qagent.storage.objects import object_store
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue

_NAV = re.compile(r"^\s*(?:open|go to|navigate to|visit)\s+(\S+)\s*$", re.IGNORECASE)
_QUOTED = re.compile(r"""["']([^"']+)["']""")
_COUNT = re.compile(r"\b(\d{1,2})\b")
_TIMING_KEYS = ("observe_ms", "extract_ms", "decide_ms", "gate_ms", "act_ms", "settle_ms", "verify_ms")
NODES_PER_STEP = 8
RISK_BLOCK_ABOVE = 0.7
EMPTY_VALUE = "<empty>"


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


# What the page shows right now that explains a failure: is a sign-in form on screen, and are there error messages?
PAGE_STATE_JS = """() => {
  const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const alerts = [...document.querySelectorAll('[role=alert], [aria-live=assertive], [class*=error], [class*=alert], [class*=invalid], [class*=toast], [class*=notification]')]
    .filter(vis).map((e) => (e.innerText || '').trim()).filter((t) => t && t.length < 240);
  return { password: [...document.querySelectorAll('input[type=password]')].some(vis), alerts: [...new Set(alerts)].slice(0, 3) };
}"""
_LOGIN = re.compile(r"\b(log ?in|sign ?in|sign-in|authenticate)\b", re.IGNORECASE)
_SUBMITTING = re.compile(r"^\s*(click|press|tap|submit|select|choose|hit)\b", re.IGNORECASE)

_PLACEHOLDER = re.compile(r"^\s*<[^>]*>\s*$")          # "<fill in>": the author has not given a value yet
_SECRET_REF = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")  # {{password}}: a saved sign-in detail


class MissingValue(LookupError):
    """A field needs a value that nobody has supplied yet."""


def _expand(value: str, secrets: Dict[str, str]) -> str:
    def sub(m: "re.Match[str]") -> str:
        name = next((k for k in secrets if k.lower() == m.group(1).lower()), None)
        if name is None:
            raise MissingValue(f"'{m.group(1)}' is not saved under Settings > Sign-in details")
        return secrets[name]
    return _SECRET_REF.sub(sub, value)


def resolve_fill_value(intent: str, candidate: CandidateAction, test_data: Dict[str, Any],
                       secrets: Optional[Dict[str, str]] = None) -> str:
    """
    What to type into a field: a quoted value in the step, else the journey's test data matched by field name (its values
    may say {{password}} to use a saved sign-in detail), else a saved sign-in detail matched by name. A password field uses
    the saved "password" even when the step only says "Enter the password". Values are never invented.
    """
    secrets = secrets or {}
    quoted = _QUOTED.search(intent)
    if quoted:
        return _expand(quoted.group(1), secrets)
    words = f"{intent} {candidate.label}".lower()
    for key, value in test_data.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(key.lower())}(?![a-z0-9])", words) or key.lower() in f"{words} {candidate.selector}".lower():
            text = "" if str(value) == EMPTY_VALUE else str(value)
            if _PLACEHOLDER.match(text):
                if any(re.search(rf"(?<![a-z0-9]){re.escape(n.lower())}(?![a-z0-9])", words) for n in secrets):
                    break                                   # a saved detail of that name fills it instead
                raise MissingValue(f"the test data value for '{key}' is still {text.strip()}: fill it in, or save it under Settings > Sign-in details")
            return _expand(text, secrets)
    if candidate.input_type == "password":
        for name, value in secrets.items():
            if name.lower() == "password":
                return value
    for name, value in secrets.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])", words):
            return value
    return candidate.value or "test"


@dataclass
class StepInfo:
    step_id: str = ""
    wait_keys: List[str] = field(default_factory=list)
    call_ids: List[str] = field(default_factory=list)
    console_errors: int = 0
    bbox: Optional[Dict[str, float]] = None
    url_before: str = ""
    had_password: bool = False       # a sign-in form was on the page before this step


@dataclass
class FlowContext:
    flow: FlowSpec
    flow_run_id: str
    trace_id: str
    findings: List[Any] = field(default_factory=list)
    failure_reason: Optional[str] = None
    steps_run: int = 0
    log_cursor: int = 0
    steps: Dict[int, StepInfo] = field(default_factory=dict)
    plan_hints: Dict[int, str] = field(default_factory=dict)
    downloads: List[str] = field(default_factory=list)   # files the page started downloading, with the step they followed
    snapshots: List[Dict[str, Any]] = field(default_factory=list)   # page text after each step that changed it
    done: List[str] = field(default_factory=list)   # the steps already done, for the final live checks
    blocked_seen: int = 0              # how many blocked requests were already reported
    last_note: str = ""                # what the page showed after the previous step, for clearer failure messages   # step number -> the planner's note
    settles: List[Dict[str, Any]] = field(default_factory=list)
    before_bytes: Optional[bytes] = None


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
        "input_hash": input_hash, "few_shot_ids": d.few_shot_ids, "outcome": d.outcome,
        "risky": d.risky, "prev_step_ok": d.prev_step_ok,
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

    `verify` runs the per-step checks (network, timing); `finish` runs the flow's playbook checks
    (formulas, UX rules, expectations). Every check writes a check result; every failed check becomes
    a finding with requirement keys, a fingerprint and evidence links.

    The engine only emits events to the sink and hands files to the upload queue; it never touches the
    database or object storage. Decisions go through LangChain runnables so callbacks trace every model call.
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
        judge: Optional[Judge] = None,
        planner: Optional[Any] = None,
        director: Optional[Any] = None,
    ):
        self.spec = run_spec
        self.decider = decider
        self.sink = sink
        self.uploader = uploader
        self.headless = headless
        self.escalator = escalator
        # Judge verdicts go on the tape and into the run's cost; a replay passes in a TapedJudge that serves them back.
        self.judge = (judge if isinstance(judge, TapedJudge) else TapedJudge(judge)) if judge is not None else None
        if self.judge:
            self.judge.bind(self._record_model_call)
        # A BedrockClient (live) or a LedgerClient (replay): planner calls go on the tape and into the cost.
        self.planner = None
        if planner is not None and run_spec.plan:
            self.planner = planner if isinstance(planner, LedgerClient) else LedgerClient(planner, self._record_model_call)
            self.planner.record = self._record_model_call
        # Goal-driven journeys: Claude chooses each next step from the live page (and it goes on the tape like any model call).
        self.director = None
        if director is not None:
            self.director = director if isinstance(director, LedgerClient) else LedgerClient(director, self._record_model_call)
            self.director.record = self._record_model_call
        # Saved sign-in details are masked everywhere they could be recorded (events, files, trace) and never sent to an AI.
        self.masker = SecretMasker(run_spec.secrets)
        if self.masker:
            sink.masker = self.masker
        self.shared_state: Optional[Dict[str, Any]] = None   # the signed-in session of a `role: setup` journey
        self.setup_failure: Optional[str] = None
        self.checkpointer = checkpointer or InMemorySaver()
        self.findings_count = 0
        self.total_steps = 0
        self.decision_stats = {"jev": 0, "claude": 0, "other": 0, "latency_ms": 0.0, "cost_usd": 0.0, "count": 0,
                               "escalations": 0,
                               "judge_calls": 0, "judge_cost_usd": 0.0}
        self.model_versions: Dict[str, str] = {}
        self.browser_version: Optional[str] = None
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

    async def _record_model_call(self, call: Dict[str, Any]) -> None:
        """Puts a judge verdict on the tape (a `model.call` event) and adds what it cost to the run."""
        if call.get("purpose") == "judge":
            self.decision_stats["judge_calls"] += 1
            self.decision_stats["judge_cost_usd"] += call.get("cost_usd", 0.0)
        elif call.get("purpose") == "director":
            self.decision_stats["director_calls"] = self.decision_stats.get("director_calls", 0) + 1
            self.decision_stats["director_cost_usd"] = self.decision_stats.get("director_cost_usd", 0.0) + call.get("cost_usd", 0.0)
        elif call.get("purpose") == "planner":
            self.decision_stats["planner_cost_usd"] = self.decision_stats.get("planner_cost_usd", 0.0) + call.get("cost_usd", 0.0)
        self.decision_stats["cost_usd"] += call.get("cost_usd", 0.0)
        await self.sink.emit(QAgentEventType.MODEL_CALL, call)

    # ---- run -------------------------------------------------------------------------

    async def _reset_target(self) -> None:
        """Resets the target app once before the run (shared state such as counters must start clean)."""
        if not self.spec.reset_path:
            return
        url = urljoin(self.spec.base_url, self.spec.reset_path)
        if (urlparse(url).hostname or "") not in self.spec.allowed_hosts:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url)
        except Exception as exc:
            logger.warning("engine.reset_failed", error=type(exc).__name__)

    async def _reset_for_flow(self, page) -> None:
        """Clears this flow's own server-side state (its cart, counters) through its own browser session,
        so parallel flows never reset each other and every flow starts from the same point."""
        if not (self.spec.reset_path and settings.deterministic_browser):
            return
        url = urljoin(self.spec.base_url, self.spec.reset_path)
        if (urlparse(url).hostname or "") not in self.spec.allowed_hosts:
            return
        try:
            await page.request.post(url, params={"scope": "session"}, timeout=5000)
        except Exception as exc:
            logger.warning("engine.flow_reset_failed", error=type(exc).__name__)

    async def _target_environment(self) -> Dict[str, Any]:
        env: Dict[str, Any] = {"base_url": self.spec.base_url, "playbook_hash": self.spec.playbook_hash}
        if self.spec.reset_path:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    r = await client.get(urljoin(self.spec.base_url, "/__bugs"))
                    if r.status_code == 200:
                        env["bug_flags"] = r.json().get("bugs")
            except Exception:
                pass
        return env

    async def run(self) -> Dict[str, Any]:
        logger.info("engine.run.started", run_id=self.spec.run_id, mode=self.spec.mode.value)
        started = time.perf_counter()
        await self._reset_target()
        environment = await self._target_environment()
        await self.sink.emit(QAgentEventType.RUN_STARTED, {
            "run_id": self.spec.run_id,
            "app_id": self.spec.app_id,
            "target_url": self.spec.base_url,
            "mode": self.spec.mode.value,
            "flow_count": len(self.spec.flows),
            "environment": environment,
        })

        sem = asyncio.Semaphore(max(1, settings.flow_max_parallel))

        async def guarded(flow: FlowSpec) -> str:
            async with sem:
                return await self._run_flow(flow)

        try:
            # A sign-in journey (`role: setup`) goes first and alone; every other journey then starts already signed in.
            setup = [f for f in self.spec.flows if f.role == "setup"]
            others = [f for f in self.spec.flows if f.role != "setup"]
            statuses: Dict[str, str] = {}
            for f in setup:
                statuses[f.key] = await self._run_flow(f)
            if others and (setup or settings.session_mode):
                # They share one signed-in session (and so one server-side cart, settings...): one at a time keeps them apart.
                # An existing browser profile is one session too, so journeys run one at a time there.
                for f in others:
                    statuses[f.key] = await self._run_flow(f)
            elif others:
                done = await asyncio.gather(*(guarded(f) for f in others))
                statuses.update({f.key: s for f, s in zip(others, done)})
            flow_statuses = [statuses[f.key] for f in self.spec.flows]
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
            "judge_calls": stats["judge_calls"],
            "judge_cost_usd": stats["judge_cost_usd"],
            "planner_cost_usd": stats.get("planner_cost_usd", 0.0),
            "director_calls": stats.get("director_calls", 0),
            "director_cost_usd": stats.get("director_cost_usd", 0.0),
            "avg_decision_latency_ms": stats["latency_ms"] / stats["count"] if stats["count"] else 0.0,
            "findings_count": self.findings_count,
            "status": status,
        }
        environment.update({"browser": self.browser_version, "models": self.model_versions})
        await self.sink.emit(QAgentEventType.RUN_FINISHED, {
            "run_id": self.spec.run_id,
            "outcome": "COMPLETED",
            "status": status,
            "total_steps": self.total_steps,
            "total_cost_usd": stats["cost_usd"],
            "duration_s": duration_s,
            "findings_count": self.findings_count,
            "escalations": stats["escalations"],
            "totals": totals,
            "environment": environment,
        })
        await self.sink.flush()  # rows are durable when run() returns
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
                      kind: str, step_seq: Optional[int] = None) -> str:
        key = self._key(ctx.flow.key, suffix)
        if self.masker and (content_type.startswith("text/") or "json" in content_type):
            data = self.masker.data(data)

        async def announce(artifact) -> None:
            await self.sink.emit(QAgentEventType.ARTIFACT_UPLOADED, {
                "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": step_seq,
                "artifact_id": artifact.id, "kind": kind, "object_key": key,
            })

        await self.uploader.enqueue(
            key=key,
            data=data,
            content_type=content_type,
            run_id=self.spec.run_id,
            flow_run_id=ctx.flow_run_id,
            step_seq=step_seq,
            kind=kind,
            on_done=announce,
        )
        return key

    async def _log(self, ctx: FlowContext, step_seq: Optional[int], level: str, source: str,
                   message: str, **data: Any) -> None:
        await self.sink.emit(QAgentEventType.LOG_EMITTED, {
            "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": step_seq,
            "level": level, "source": source, "message": message, "data": data,
        })

    def _count_decision(self, decision: DecisionResult, escalated: bool = False) -> None:
        s = self.decision_stats
        s["count"] += 1
        s["latency_ms"] += decision.latency_ms
        s["cost_usd"] += decision.cost_usd
        s["escalations"] += int(escalated)
        s["jev" if decision.decider == "jev" else "claude" if decision.decider == "claude" else "other"] += 1
        if decision.model_version:
            self.model_versions[decision.decider] = decision.model_version

    async def _upload_flow_artifacts(self, ctx: FlowContext, sandbox: BrowserSandbox, art_dir: Path) -> None:
        for name, content_type, kind in (
            ("trace.zip", "application/zip", "trace"),
            ("har.json", "application/json", "har"),
        ):
            path = art_dir / name
            if path.exists():
                if self.masker:
                    (self.masker.scrub_zip if name.endswith(".zip") else self.masker.scrub_file)(path)
                await self._upload(ctx, name, path.read_bytes(), content_type, kind)
        if sandbox.console_logs:
            lines = "\n".join(json.dumps(entry, default=str) for entry in sandbox.console_logs)
            await self._upload(ctx, "console.jsonl", lines.encode(), "application/x-ndjson", "console")

    def _hints_for(self, flow: FlowSpec) -> List[str]:
        return [g["note"] for g in self.spec.gotchas
                if g.get("note") and g.get("applies_to", flow.base_key) in ("", flow.base_key)]

    # ---- checks -> check results -> findings ------------------------------------------

    def _evidence_links(self, ctx: FlowContext, seq: int, outcome: CheckOutcome) -> List[Dict[str, str]]:
        info = ctx.steps.get(seq, StepInfo())
        links: List[Dict[str, str]] = [
            {"kind": "screenshot_before", "ref_id": self._key(ctx.flow.key, f"steps/{seq}/before.jpg"), "note": ""},
            {"kind": "screenshot_after", "ref_id": self._key(ctx.flow.key, f"steps/{seq}/after.jpg"), "note": ""},
            {"kind": "dom", "ref_id": self._key(ctx.flow.key, f"steps/{seq}/dom.html"), "note": ""},
            {"kind": "trace", "ref_id": self._key(ctx.flow.key, "trace.zip"), "note": "Playwright trace"},
            {"kind": "span", "ref_id": ctx.trace_id, "note": f"spans of step {seq}"},
        ]
        links += [{"kind": "wait_frame", "ref_id": k, "note": ""} for k in info.wait_keys]
        call_ids = list(info.call_ids)
        for src in outcome.inputs.values():
            if isinstance(src, dict) and src.get("call_id") and src["call_id"] not in call_ids:
                call_ids.append(src["call_id"])
        if outcome.evidence.get("call_id"):
            call_ids.insert(0, outcome.evidence["call_id"])
        links += [{"kind": "network_call", "ref_id": c, "note": ""} for c in dict.fromkeys(call_ids)]
        if info.console_errors:
            links.append({"kind": "console", "ref_id": self._key(ctx.flow.key, "console.jsonl"),
                          "note": f"{info.console_errors} console errors in this step"})
        for n in range(1, seq + 1):
            sid = ctx.steps.get(n, StepInfo()).step_id
            if sid:
                links.append({"kind": "decision", "ref_id": sid, "note": f"step {n}"})
        return links

    async def _emit_check(self, ctx: FlowContext, seq: int, outcome: CheckOutcome, only_failures: bool = False) -> None:
        if outcome.passed and only_failures:
            return
        check_id = str(uuid.uuid4())
        await self.sink.emit(QAgentEventType.CHECK_RESULT, {
            "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": seq, "check_id": check_id,
            "check_key": outcome.key, "kind": outcome.kind, "pass": outcome.passed, "expected": outcome.expected,
            "actual": outcome.actual, "inputs": outcome.inputs, "judged_by": outcome.judged_by,
            "confidence": outcome.confidence,
        })
        if outcome.passed:
            return

        reqs = outcome.requirement_keys
        priorities = [self.spec.requirements[r].get("priority", "") for r in reqs if r in self.spec.requirements]
        severity = final_severity(outcome.severity, priorities, outcome.judged_by != "code")
        finding_kind = outcome.finding_kind or outcome.kind
        finding = {
            "id": f"find-{uuid.uuid4().hex[:12]}", "flow_run_id": ctx.flow_run_id, "run_id": self.spec.run_id,
            "step_seq": seq, "severity": severity, "kind": finding_kind, "title": outcome.title,
            "expected": outcome.expected, "actual": outcome.actual, "evidence": outcome.evidence,
            "check_key": outcome.key, "check_result_id": check_id, "requirement_keys": reqs,
            "fingerprint": fingerprint(outcome.key, ctx.flow.key, finding_kind, outcome.locus),
            "judged_by": outcome.judged_by, "flow_key": ctx.flow.key,
            "evidence_links": self._evidence_links(ctx, seq, outcome),
        }
        ctx.findings.append(finding)
        self.findings_count += 1
        await self.sink.emit(QAgentEventType.FINDING_DISCOVERED, finding)

    async def _record_api_call(self, ctx: FlowContext, seq: int, call: Dict[str, Any]) -> str:
        """A call QAgent itself made while verifying (e.g. an API binding); stored so evidence can cite it."""
        call_id = str(uuid.uuid4())
        for suffix, body in (("request.json", call.get("req_body")), ("response.json", call.get("resp_body"))):
            body = redact_body(body, self.spec.redact_keys)
            if body:
                await self._upload(ctx, f"network/{call_id}/{suffix}", body, "application/json", "body", seq)
        await self.sink.emit(QAgentEventType.NETWORK_CALL, {
            "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": seq, "call_id": call_id,
            "method": call["method"], "url": call["url"], "status": call["status"],
            "duration_ms": call["duration_ms"], "is_api": call["is_api"], "background": call.get("background", False),
            "req_size": call.get("req_size", 0), "resp_size": call.get("resp_size", 0),
        })
        ctx.steps.setdefault(seq, StepInfo()).call_ids.append(call_id)
        return call_id

    # ---- flow ------------------------------------------------------------------------

    async def _run_flow(self, flow: FlowSpec) -> str:
        ctx = FlowContext(flow, str(uuid.uuid4()), uuid.uuid4().hex)
        current_flow_run.set(ctx.flow_run_id)
        flow_span = Span(f"flow:{flow.key}", "flow", ctx.trace_id, flow_key=flow.key)
        started = time.perf_counter()
        base = {"flow_key": flow.key, "flow_run_id": ctx.flow_run_id, "variant_of": flow.variant_of}

        await self.sink.emit(QAgentEventType.FLOW_STARTED, {
            **base, "severity": flow.severity, "total_steps": len(flow.steps),
        })

        if self.setup_failure and flow.role != "setup":
            reason = f"not run: the sign-in journey failed first ({self.setup_failure})"
            await self.sink.emit(QAgentEventType.FLOW_FINISHED, {**base, "status": "failed", "step_count": 0, "duration_ms": 0.0,
                                                                 "findings_count": 0, "failure_reason": reason})
            return "failed"

        art_dir = Path(tempfile.mkdtemp(prefix="qagent-"))
        sandbox = BrowserSandbox(
            headless=self.headless, allowed_hosts=self.spec.allowed_hosts, artifact_dir=art_dir
        )
        try:
            handler = SpanCallbackHandler(self.sink, ctx.trace_id, flow_span, flow.key)
            if self.spec.inject_traceparent:
                sandbox.traceparent_provider = lambda: f"00-{ctx.trace_id}-{handler.current_span_id}-01"
            page = await sandbox.start(storage_state=None if flow.role == "setup" else self.shared_state)
            self.browser_version = self.browser_version or sandbox.browser_version
            recorder = NetworkRecorder(page, ctx.flow_run_id, sandbox=sandbox)
            page.on("download", lambda d: ctx.downloads.append(f"{d.suggested_filename} (after step {ctx.steps_run})"))
            await self._reset_for_flow(page)
            await page.goto(self.spec.base_url, timeout=10000)
            recorder.drain()  # landing traffic is not part of any step

            rt = FlowRuntime(ctx, sandbox, page, recorder, started)
            config: RunnableConfig = {
                "configurable": {"thread_id": ctx.flow_run_id, "rt": rt},
                "callbacks": [handler],
                "recursion_limit": max(25, (max(len(flow.steps), self._step_limit(flow)) + 1) * NODES_PER_STEP + 10),
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
            if flow.role == "setup" and not ctx.failure_reason:
                self.shared_state = await sandbox.export_state()
            await sandbox.stop()
            await self._upload_flow_artifacts(ctx, sandbox, art_dir)
        if flow.role == "setup" and ctx.failure_reason:
            self.setup_failure = f"'{flow.key}': {ctx.failure_reason}"[:240]

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
        if s.get("step_status") in ("failed", "blocked") or s.get("step_done"):
            return "settle"
        if s["tier"] != ConfidenceTier.AUTO.value and self.escalator and not s.get("escalated"):
            return "escalate"
        return "act"

    # -- nodes: each returns a partial state update --

    async def _plan(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Validates the flow. With planning on, Claude also writes a note per step (the steps are never rewritten)."""
        rt = _rt(config)
        flow = rt.ctx.flow
        if not flow.steps and not flow.goal:
            rt.ctx.failure_reason = "flow has no steps"
            return {"done": True, "failure_reason": rt.ctx.failure_reason}
        if flow.goal and self.director is None:
            rt.ctx.failure_reason = "this journey is described by a goal, so it needs AI to choose the steps: run it in Smart or Thorough mode"
            return {"done": True, "failure_reason": rt.ctx.failure_reason}
        if self.planner and not flow.goal:
            try:
                examples = select_examples(self.spec.reasoning_examples, "plan", f"{flow.key} {' '.join(flow.steps)}")
                plan = await plan_flow(self.planner, flow.key, flow.steps, self.spec.base_url, flow.test_data, examples)
                rt.ctx.plan_hints = step_hints(plan, len(flow.steps))
                await self._log(rt.ctx, None, "info", "planner",
                                f"plan: {plan.get('summary', '')} ({len(rt.ctx.plan_hints)} step notes)")
            except Exception as exc:  # planning only helps; the journey runs as written without it
                await self._log(rt.ctx, None, "warning", "planner", f"planning skipped ({type(exc).__name__})")
        return {}

    def _step_limit(self, flow: FlowSpec) -> int:
        return max(self.spec.step_budget, settings.goal_step_budget) if flow.goal else self.spec.step_budget

    def _time_limit(self, flow: FlowSpec) -> int:
        return max(self.spec.time_budget_s, settings.goal_time_budget_s) if flow.goal else self.spec.time_budget_s

    async def _direct(self, rt: FlowRuntime, state: FlowState, idx: int) -> Dict[str, str]:
        """Asks the director for the next step of a goal journey, from what the page shows right now."""
        flow, page = rt.ctx.flow, rt.page
        err = ""
        for attempt in range(3):   # a page that is navigating or re-rendering can fail a read: look again before giving up
            try:
                await wait_dom_stable(page)
                raw = await page.evaluate(EXTRACTOR_JS)
                candidates = [CandidateAction.model_validate(c) for c in raw[:60]]
                text = (await page.evaluate("document.body ? document.body.innerText : ''"))[:6000]
                title = await page.title()
                try:
                    aria = (await page.locator("body").aria_snapshot(timeout=3000))[:2500]
                except Exception:
                    aria = ""
                err = ""
                break
            except Exception as exc:
                err = f"{type(exc).__name__}: {str(exc).splitlines()[0][:140] if str(exc) else 'no details'}"
                await self._log(rt.ctx, idx, "warning", "director", f"could not read the page ({err}); attempt {attempt + 1} of 3")
                await asyncio.sleep(1.5)
        if err:
            return {"status": "blocked", "intent": "", "why": f"could not read the page ({err})"}
        examples = select_examples(self.spec.reasoning_examples, "plan", f"{flow.key} {flow.goal}")
        fields = {**flow.test_data, **{name: "" for name in self.spec.secrets}}   # names only: the AI never sees a value
        return await direct_next_step(self.director, flow.goal or "", flow.expect, flow.steps, fields,
                                      state.get("history", []), page.url, title, text, candidates, examples, aria)

    async def _begin_step(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        flow, ctx = rt.ctx.flow, rt.ctx
        idx = state["idx"] + 1
        if not flow.goal and idx > len(flow.steps):
            return {"done": True}
        if self.cancel_requested:
            ctx.failure_reason = "stopped by user"
        elif idx > self._step_limit(flow):
            ctx.failure_reason = f"step budget ({self._step_limit(flow)}) exhausted" + (" before the goal was reached" if flow.goal else "")
        elif time.perf_counter() - rt.started > self._time_limit(flow):
            ctx.failure_reason = f"time budget ({self._time_limit(flow)}s) exhausted"
        if ctx.failure_reason:
            return {"done": True, "failure_reason": ctx.failure_reason}

        if flow.goal:
            try:
                nxt = await self._direct(rt, state, idx)
            except Exception as exc:
                ctx.failure_reason = f"could not decide the next step ({type(exc).__name__}: {str(exc).splitlines()[0][:120]})"
                return {"done": True, "failure_reason": ctx.failure_reason}
            hist = list(state.get("history", []))
            for attempt in range(settings.goal_block_retries + 1):
                await self._log(ctx, idx, "info", "director", f"{nxt['status']}: {nxt['intent'] or '-'} ({nxt['why']})")
                if nxt["status"] == "done":
                    return {"done": True}
                recent = [h.get("intent") for h in hist[-2:]]
                looping = nxt["status"] == "continue" and len(recent) == 2 and recent[0] == recent[1] == nxt["intent"]
                if nxt["status"] == "continue" and not looping:
                    break
                problem = (f"going in circles: '{nxt['intent']}' was chosen three times in a row" if looping
                           else f"blocked before the goal was reached: {nxt['why']}")
                if attempt >= settings.goal_block_retries:
                    ctx.failure_reason = problem
                    return {"done": True, "failure_reason": ctx.failure_reason}
                # Not accepted yet: the tester must try something it has not tried before giving up.
                await self._log(ctx, idx, "info", "director", f"not giving up yet ({problem}); asking for a different approach")
                hist = hist + [{"intent": nxt["intent"] or "(gave up)", "action": "", "status": "rejected",
                                "error": f"{'you were looping' if looping else 'you said blocked: ' + nxt['why']}; "
                                         "try an approach not tried yet: another element, open a menu or tab, close what is in the way, scroll"}]
                nxt = await self._direct(rt, {**state, "history": hist}, idx)
            intent = nxt["intent"]
        else:
            intent = flow.steps[idx - 1]
        ctx.steps_run = idx
        self.total_steps += 1
        step_id = str(uuid.uuid4())
        ctx.steps[idx] = StepInfo(step_id=step_id)
        rt.recorder.mark_step_start()
        return {
            "idx": idx, "step_id": step_id, "intent": intent, "nav_target": parse_navigation(intent) or parse_utility(intent),
            "candidates": [], "decision": None, "chosen_id": None, "label": "", "tier": ConfidenceTier.AUTO.value,
            "escalated": False, "acted": False, "settled": True, "step_status": "passed", "step_done": False,
            "target_bbox": None, "timings": {k: 0.0 for k in _TIMING_KEYS}, "steps_run": idx,
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

        # What the AI is shown must be one moment of the page: wait for it to stop changing, read the elements, take the
        # screenshot straight after, and read again if the page moved in between (so boxes always match the picture).
        t = time.perf_counter()
        candidates: List[CandidateAction] = []
        ctx.before_bytes = None
        for attempt in range(3):
            await wait_dom_stable(page)
            before_sig = await page_signature(page)
            if not state.get("nav_target"):
                try:
                    raw = await page.evaluate(EXTRACTOR_JS)
                except Exception:
                    raw = []   # the page navigated while being read: look again
                    before_sig = ""
                candidates = [CandidateAction.model_validate(c) for c in raw[:60]]
            try:
                ctx.before_bytes = await page.screenshot(type="jpeg", quality=70)
            except Exception as exc:
                ctx.before_bytes = None
                await self._log(ctx, seq, "warning", "engine", f"before screenshot failed: {exc}")
            if before_sig and before_sig == await page_signature(page):
                break
        if ctx.before_bytes:
            await self._upload(ctx, f"steps/{seq}/before.jpg", ctx.before_bytes, "image/jpeg", "screenshot_before", seq)
        timings["observe_ms"] = (time.perf_counter() - t) * 1000.0
        timings["extract_ms"] = 0.0
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        info = ctx.steps[seq]
        info.url_before = page.url
        try:
            info.had_password = bool((await page.evaluate(PAGE_STATE_JS))["password"])
        except Exception:
            info.had_password = False

        shot_url = f"/api/artifacts/{self.spec.run_id}/flows/{quote(ctx.flow.key, safe='')}/steps/{seq}/screenshot.jpg"
        await self.sink.emit(QAgentEventType.STEP_OBSERVED, {
            **self._base(state), "intent": state["intent"], "url": page.url, "page_title": title,
            "candidates_count": len(candidates), "screenshot_url": shot_url,
            "before_artifact_key": self._key(ctx.flow.key, f"steps/{seq}/before.jpg"),
        })
        if candidates:
            await self._upload(ctx, f"steps/{seq}/candidates.json",
                               json.dumps([c.model_dump(mode="json") for c in candidates]).encode(),
                               "application/json", "candidates", seq)
        return {"url": page.url, "title": title, "timings": timings,
                "candidates": [c.model_dump(mode="json") for c in candidates]}

    def _request(self, state: FlowState, candidates: List[CandidateAction], scope: Optional[str] = None,
                 flow: Optional[FlowSpec] = None, note: Optional[str] = None) -> DecisionRequest:
        examples: List[Dict[str, Any]] = []
        flow_note = note
        if scope and flow:
            examples = select_examples(self.spec.reasoning_examples, scope, f"{flow.key} {state['intent']}")
        return DecisionRequest(
            step_seq=state["idx"], intent=state["intent"], url=state["url"], candidates=candidates,
            page_summary=state["title"], history=state["history"][-3:],
            hints=(self._hints_for(flow) + ([flow_note] if flow_note else [])) if flow else [], examples=examples,
        )

    async def _decide(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        candidates = [CandidateAction.model_validate(c) for c in state["candidates"]]
        timings = dict(state["timings"])
        if not candidates:
            note = f" ({rt.ctx.last_note})" if rt.ctx.last_note else ""
            return self._fail(rt, f"step {state['idx']}: no interactive elements on {state['url']}{note}")

        req = self._request(state, candidates, flow=rt.ctx.flow, note=rt.ctx.plan_hints.get(state["idx"]))
        input_hash = hash_request(req)
        t = time.perf_counter()
        decision: DecisionResult = await self._decide_chain.ainvoke(req, config)
        timings["decide_ms"] = (time.perf_counter() - t) * 1000.0

        chosen = next((c for c in candidates if c.id == decision.selected_action_id), None)
        label = chosen.label if chosen else {"done": "(step already satisfied)", "stuck": "(stuck)"}.get(
            decision.outcome, "")
        self._count_decision(decision)
        await self.sink.emit(QAgentEventType.DECISION_MADE, {
            **self._base(state), **_decision_payload(decision, req, state["intent"], label, input_hash),
        })
        divergence = getattr(self.decider, "take_divergence", lambda _h: None)(input_hash)
        if divergence:
            await self.sink.emit(QAgentEventType.DIVERGENCE, {**self._base(state), **divergence})
        if decision.prev_step_ok is not None and decision.prev_step_ok < 0.3:
            await self._log(rt.ctx, state["idx"], "warning", "decide",
                            f"previous step may not have achieved its goal (p={decision.prev_step_ok:.2f})")
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
        update: Dict[str, Any] = {"tier": tier.value, "timings": timings}
        can_escalate = bool(self.escalator) and not state.get("escalated")
        seq = state["idx"]

        if decision.risky is not None and decision.risky > RISK_BLOCK_ABOVE:
            reason = f"Blocked: risk {decision.risky:.2f} > {RISK_BLOCK_ABOVE}"
            update.update(self._fail(rt, f"step {seq}: action judged risky (p={decision.risky:.2f})", "blocked"))
        elif decision.outcome == "stuck":
            note = f" ({rt.ctx.last_note})" if rt.ctx.last_note else ""
            update.update(self._fail(rt, f"step {seq}: model reports no element performs this step{note}"))
        elif decision.outcome == "done":
            update["step_done"] = True
        elif state.get("chosen_id") is None:
            update.update(self._fail(rt, f"step {seq}: decider chose unknown candidate "
                                         f"{decision.selected_action_id}"))
        elif tier == ConfidenceTier.STOP and not can_escalate:
            update.update(self._fail(rt, f"step {seq}: confidence {decision.confidence:.2f} "
                                         f"below stop threshold", "blocked"))
        elif tier == ConfidenceTier.ESCALATE and not can_escalate:
            await self._log(rt.ctx, seq, "warning", "gate", "still at escalation tier after review; proceeding")

        await self.sink.emit(QAgentEventType.GATE_TRIGGERED, {**self._base(state), "tier": tier.value,
                                                              "reason": reason})
        return update

    async def _escalate(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Medium or low confidence: a stronger model re-decides this step and its answer replaces Jev's."""
        rt = _rt(config)
        candidates = [CandidateAction.model_validate(c) for c in state["candidates"]]
        req = self._request(state, candidates, scope="escalation", flow=rt.ctx.flow,
                            note=rt.ctx.plan_hints.get(state["idx"]))
        try:
            escalated: DecisionResult = await self._escalate_chain.ainvoke(req, config)
        except Exception as exc:
            await self._log(rt.ctx, state["idx"], "warning", "gate",
                            f"escalation failed ({type(exc).__name__}); keeping original decision")
            return {"escalated": True}

        self._count_decision(escalated, escalated=True)
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
            if target.startswith("@"):   # scroll, wait, go back, press a key: done by the engine, no element to choose
                started = time.perf_counter()
                update = {"acted": True, "label": target[1:].replace(":", " ")}
                try:
                    update["label"] = await run_utility(page, target)
                except Exception as exc:
                    update.update(self._fail(rt, f"step {state['idx']}: {target[1:]} failed: {str(exc).splitlines()[0][:120]}"))
                timings["act_ms"] = (time.perf_counter() - started) * 1000.0
                await self.sink.emit(QAgentEventType.ACTION_EXECUTED, {
                    **base, "action_id": 0, "action_label": update["label"],
                    "status": "failed" if update.get("step_status") == "failed" else "success",
                    "duration_ms": timings["act_ms"], "target_bbox": None,
                })
                return {**update, "timings": timings}
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
                "duration_ms": timings["act_ms"], "target_bbox": None,
            })
            return {**update, "timings": timings}

        chosen = next(c for c in (CandidateAction.model_validate(x) for x in state["candidates"])
                      if c.id == state["chosen_id"])
        bbox = chosen.bounding_box.model_dump() if chosen.bounding_box else None
        ctx.steps[state["idx"]].bbox = bbox
        try:
            value = resolve_fill_value(state["intent"], chosen, ctx.flow.test_data, self.spec.secrets) if chosen.action_type == "fill" else None
            if chosen.action_type == "select":
                value = choose_option(state["intent"], chosen.label, chosen.options, ctx.flow.test_data)
                if value is None:
                    raise MissingValue(f"no option of '{chosen.label}' matches '{state['intent']}' (options: {', '.join(chosen.options[:12])})")
        except MissingValue as exc:
            update = {"acted": True, **self._fail(rt, f"step {state['idx']}: {exc}")}
            await self.sink.emit(QAgentEventType.ACTION_EXECUTED, {**base, "action_id": chosen.id, "action_label": chosen.label,
                                 "status": "failed", "duration_ms": 0.0, "error": str(exc), "target_bbox": bbox})
            return update
        executor = BrowserExecutor(page)
        started = time.perf_counter()
        outcome: Dict[str, Any] = {"status": "success", "error": None}
        upload_files: List[Dict[str, Any]] = []
        uploaded: List[Dict[str, Any]] = []
        if chosen.action_type == "upload":
            try:
                upload_files = await self._files_for(state["intent"], chosen, ctx.flow.test_data)
                uploaded = [{"name": f["name"], "size": len(f["buffer"]), "content_type": f["mimeType"]} for f in upload_files]
                await self._log(ctx, state["idx"], "info", "act",
                                "uploading " + ", ".join(f"{u['name']} ({u['size']} bytes)" for u in uploaded))
            except LookupError as exc:
                outcome = {"status": "failed", "error": str(exc)}
        for _ in range(repeat_count(state["intent"]) if outcome["status"] == "success" else 0):
            outcome = await executor.execute(chosen, value, upload_files)
            if outcome["status"] != "success":
                break
        timings["act_ms"] = (time.perf_counter() - started) * 1000.0
        await self.sink.emit(QAgentEventType.ACTION_EXECUTED, {
            **base, "action_id": chosen.id, "action_label": chosen.label, "status": outcome["status"],
            "duration_ms": timings["act_ms"], "error": outcome["error"], "target_bbox": bbox, "uploaded": uploaded,
        })
        update = {"acted": True, "timings": timings, "target_bbox": bbox}
        if outcome["status"] != "success":
            update.update(self._fail(rt, f"step {state['idx']}: action failed: {outcome['error']}"))
        return update

    async def _files_for(self, intent: str, chosen: CandidateAction, test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """The files this step uploads, read from the app's test files or the built-in samples."""
        available = list(dict.fromkeys([*self.spec.files, *uploads.BUILTIN]))
        names = uploads.choose_files(intent, chosen.label, test_data, available)
        if not names:
            raise LookupError("this step uploads a file, but the app has no test files")
        out: List[Dict[str, Any]] = []
        for name in names:
            stored = next((v for k, v in self.spec.files.items() if k.lower() == name.lower()), None)
            if stored is not None:
                data = await asyncio.to_thread(object_store.get_bytes, stored["key"])
                if data is None:
                    raise LookupError(f"test file '{name}' could not be read from storage")
                out.append(uploads.payload(name, data, stored.get("content_type")))
                continue
            builtin = next((v for k, v in uploads.BUILTIN.items() if k.lower() == name.lower()), None)
            if builtin is None:
                raise LookupError(f"test file '{name}' does not exist; add it under Settings > Test files")
            out.append(uploads.payload(name, builtin[0], builtin[1]))
        return out

    async def _settle(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Waits for the page to settle; wait frames are captured only while it is still busy."""
        rt = _rt(config)
        if not state.get("acted"):
            return {"settled": True}
        seq = state["idx"]
        timings = dict(state["timings"])

        # Gotcha hint `wait_for: api:<path>`: if the step triggered that request, wait for its response first.
        started = time.perf_counter()
        for g in self.spec.gotchas:
            spec = g.get("wait_for", "")
            if spec.startswith("api:") and g.get("applies_to", rt.ctx.flow.base_key) in ("", rt.ctx.flow.base_key):
                await rt.recorder.wait_for_response(spec[4:], timeout_ms=3000)

        result = await WaitFramesWatcher(rt.page, rt.recorder).wait_until_settled(
            timeout_ms=settings.settle_timeout_ms)
        timings["settle_ms"] = result.waited_ms + (time.perf_counter() - started) * 1000.0 - result.waited_ms
        for n, frame in enumerate(result.frames, start=1):
            key = await self._upload(rt.ctx, f"steps/{seq}/wait/{n}.jpg", frame, "image/jpeg", "wait_frame", seq)
            rt.ctx.steps[seq].wait_keys.append(key)
        rt.ctx.settles.append({"step_seq": seq, "settle_ms": timings["settle_ms"], "settled": result.settled})
        return {"settled": result.settled, "timings": timings}

    async def _verify(self, state: FlowState, config: RunnableConfig) -> FlowState:
        rt = _rt(config)
        page, ctx = rt.page, rt.ctx
        seq = state["idx"]
        timings = dict(state["timings"])
        info = ctx.steps[seq]

        try:
            await self._upload(ctx, f"steps/{seq}/after.jpg", await page.screenshot(type="jpeg", quality=70),
                               "image/jpeg", "screenshot_after", seq)
            await self._upload(ctx, f"steps/{seq}/dom.html", (await page.content()).encode(),
                               "text/html", "dom", seq)
        except Exception as exc:
            await self._log(ctx, seq, "warning", "engine", f"artifact capture failed: {exc}")

        t = time.perf_counter()
        await self._network_checks(ctx, rt.recorder, seq)

        ignore = [g["ignore_console"] for g in self.spec.gotchas if g.get("ignore_console")]
        for entry in list(rt.sandbox.console_logs)[ctx.log_cursor:]:
            is_error = entry["type"] in ("error", "pageerror") and not any(re.search(p, entry["text"]) for p in ignore)
            info.console_errors += int(is_error)
            await self._log(ctx, seq, "error" if is_error else "info", "browser", entry["text"], type=entry["type"])
        ctx.log_cursor = len(rt.sandbox.console_logs)

        if state.get("acted"):
            has_max_wait = any(self.spec.ux_rules.get(k, {}).get("check") == "max_wait" for k in ctx.flow.checks)
            if not has_max_wait:  # a playbook max_wait rule replaces the generic settle check
                await self._emit_check(ctx, seq, timing.settle_check(
                    state.get("settled", True), timings["settle_ms"], seq, ctx.flow.key), only_failures=True)
            if state.get("settled", True):
                await self._emit_check(ctx, seq, timing.step_timing_check(
                    timings["act_ms"] + timings["settle_ms"], settings.step_sla_ms, seq, ctx.flow.key),
                    only_failures=True)
        timings["verify_ms"] = (time.perf_counter() - t) * 1000.0

        observed = await self._observe_result(rt, state, info)
        # The allow-list keeps the tester on the app, but an app often talks to its own API on another host. Say so, once per host.
        hosts = {urlparse(u).hostname or u for u in rt.sandbox.blocked_requests[ctx.blocked_seen:]}
        ctx.blocked_seen = len(rt.sandbox.blocked_requests)
        for host in sorted(hosts):
            await self._log(ctx, seq, "warning", "network", f"requests to '{host}' were blocked because it is not in this app's allowed hosts; "
                                                         f"if the app needs it, add it in the app's settings (a '*.' prefix allows a whole domain)")
        try:
            await wait_dom_stable(page, quiet_ms=500, max_ms=2000)   # a screen that is still revealing its result is not what the step produced
            text = (await page.evaluate("document.body ? document.body.innerText : ''"))[:6000]
            if text and (not ctx.snapshots or ctx.snapshots[-1]["text"] != text):
                ctx.snapshots.append({"seq": seq, "intent": state["intent"], "url": page.url, "text": text})
                del ctx.snapshots[:-14]
        except Exception:
            pass
        failed_now = state["step_status"] in ("failed", "blocked")
        ctx.done.append(f"{state['intent']} [{'carried out' if state['step_status'] == 'passed' else state['step_status']}]" + (f" -> {state.get('label')}" if state.get("label") else ""))
        history = state["history"] + [{"seq": seq, "intent": state["intent"], "action": state.get("label", ""),
                                       "status": state["step_status"],
                                       **({"error": (ctx.failure_reason or "")[:160]} if failed_now else {})}]
        await self.sink.emit(QAgentEventType.VERIFICATION_STEP, {
            **self._base(state), "status": state["step_status"], "url": page.url,
            "settled": state.get("settled", True), "timings": timings, "observed": observed,
        })
        update: Dict[str, Any] = {"history": history, "timings": timings}
        if observed.get("signin_failed"):
            update.update(self._fail(rt, observed["signin_failed"]))
        elif failed_now and ctx.flow.goal:
            streak = 0
            for h in reversed(history):
                if h.get("status") not in ("failed", "blocked"):
                    break
                streak += 1
            if streak <= settings.goal_max_recoveries:
                # A goal journey does not end on one failed step: the director sees what failed and tries another way.
                await self._log(ctx, seq, "info", "engine", f"step failed ({ctx.failure_reason}); trying another way "
                                                           f"({streak}/{settings.goal_max_recoveries})")
                ctx.failure_reason = None
                update["step_status"] = "passed"   # routes on to the next decision; the step itself stays recorded as failed
                update["failure_reason"] = None
        return update

    async def _observe_result(self, rt: FlowRuntime, state: FlowState, info: StepInfo) -> Dict[str, Any]:
        """What the page shows after a step, so failures name their real cause (and a failed sign-in stops the journey)."""
        ctx, seq = rt.ctx, state["idx"]
        out: Dict[str, Any] = {}
        try:
            now = await rt.page.evaluate(PAGE_STATE_JS)
        except Exception:
            return out
        url_changed = rt.page.url != info.url_before
        out.update(url_changed=url_changed, signin_form_visible=bool(now["password"]), alerts=now["alerts"])
        label = state.get("label", "") or ""
        submit_like = bool(_LOGIN.search(label)) or bool(_LOGIN.search(state["intent"]) and _SUBMITTING.match(state["intent"]))
        ctx.last_note = ""
        if state.get("acted") and _SUBMITTING.match(state["intent"]) and not url_changed:
            says = f"; it shows: {' | '.join(now['alerts'])}" if now["alerts"] else ""
            ctx.last_note = f"after '{state['intent']}' the page did not change{says}"
        if state.get("acted") and state["step_status"] == "passed" and info.had_password and now["password"] and submit_like:
            says = f" and says: {' | '.join(now['alerts'])}" if now["alerts"] else ""
            reason = f"sign-in failed: after '{state['intent']}' the page still shows the sign-in form{says}"
            out["signin_failed"] = reason
            await self._log(ctx, seq, "error", "signin", reason)
            await self._emit_check(ctx, seq, CheckOutcome(
                key=f"signin:{ctx.flow.base_key}", kind="signin", passed=False, severity="high", finding_kind="dom",
                title="Sign-in did not succeed", expected="Signing in leads past the sign-in form",
                actual=reason, locus="sign-in form", requirement_keys=list(ctx.flow.covers)))
        elif now["alerts"] and state.get("acted") and _SUBMITTING.match(state["intent"]):
            await self._log(ctx, seq, "warning", "page", f"the page shows a message after this step: {' | '.join(now['alerts'])}")
        return out

    async def _network_checks(self, ctx: FlowContext, recorder: NetworkRecorder, seq: int) -> None:
        info = ctx.steps[seq]
        for call in recorder.drain():
            call_id = str(uuid.uuid4())
            for suffix, body in (("request.json", call["req_body"]), ("response.json", call["resp_body"])):
                body = redact_body(body, self.spec.redact_keys)
                if body:
                    await self._upload(ctx, f"network/{call_id}/{suffix}", body, "application/json", "body", seq)
            await self.sink.emit(QAgentEventType.NETWORK_CALL, {
                "flow_key": ctx.flow.key, "flow_run_id": ctx.flow_run_id, "step_seq": seq, "call_id": call_id,
                "method": call["method"], "url": call["url"], "status": call["status"],
                "duration_ms": call["duration_ms"], "is_api": call["is_api"],
                "req_size": call["req_size"], "resp_size": call["resp_size"],
                "traceparent": call.get("traceparent"),
            })
            info.call_ids.append(call_id)
            if call["is_api"] or call["status"] >= 500:
                outcome = timing.network_check(call, flow_expects_error=bool(ctx.flow.edge_case))
                outcome.evidence["call_id"] = call_id
                await self._emit_check(ctx, seq, outcome, only_failures=not call["is_api"])
            slow = timing.slow_call_check(call, settings.step_sla_ms) if call["is_api"] else None
            if slow:
                slow.evidence["call_id"] = call_id
                await self._emit_check(ctx, seq, slow)

    async def _finish(self, state: FlowState, config: RunnableConfig) -> FlowState:
        """Runs the flow's playbook checks against its final state (only if the flow ran clean)."""
        rt = _rt(config)
        ctx = rt.ctx
        if not ctx.failure_reason:
            await self._run_flow_checks(rt)
        return {"done": True, "failure_reason": ctx.failure_reason}

    async def _run_flow_checks(self, rt: FlowRuntime) -> None:
        ctx, flow, page = rt.ctx, rt.ctx.flow, rt.page
        seq = max(ctx.steps_run, 1)
        ctx.steps.setdefault(seq, StepInfo())

        async def on_api_call(call: Dict[str, Any]) -> str:
            return await self._record_api_call(ctx, seq, call)

        resolver = BindingResolver(page, self.spec.base_url, on_api_call)
        hints = self._hints_for(flow)
        ignore = [g["ignore_console"] for g in self.spec.gotchas if g.get("ignore_console")]
        page_text, shots = "", []

        async def judge_inputs() -> None:
            nonlocal page_text, shots
            if page_text:
                return
            try:
                page_text = await page.inner_text("body")
                shots = [b for b in (ctx.before_bytes, await page.screenshot(type="jpeg", quality=70)) if b]
            except Exception:
                page_text = ""

        severity = flow.severity
        for key in flow.checks:
            if key in self.spec.formulas:
                outcome = await formula_checks.run_formula(self.spec.formulas[key], resolver, severity, seq)
            elif key in self.spec.ux_rules:
                rule = self.spec.ux_rules[key]
                check = rule.get("check")
                if check == "consistent_value":
                    outcome = await ux_rules.consistent_value(rule, resolver)
                elif check == "format":
                    outcome = await ux_rules.format_rule(rule, resolver)
                elif check == "max_wait":
                    outcome = ux_rules.max_wait(rule, ctx.settles)
                    seq_for = outcome.evidence.get("step_seq", seq)
                    await self._emit_check(ctx, seq_for, outcome)
                    continue
                elif check == "no_console_errors":
                    outcome = ux_rules.no_console_errors(rule, rt.sandbox.console_logs, ignore)
                elif check == "a11y":
                    outcome = await a11y.a11y_rule(rule, page)
                elif check == "judged":
                    if not self.judge:
                        await self._log(ctx, seq, "info", "checks", f"{key} not evaluated: no judge configured")
                        continue
                    await judge_inputs()
                    examples = select_examples(self.spec.reasoning_examples, "judge", f"{flow.key} {rule['question']}")
                    try:
                        outcome = await expectations.run_judged_rule(self.judge, rule, page_text, shots, hints, examples)
                    except Exception as exc:
                        await self._log(ctx, seq, "warning", "checks", f"{key} could not be judged: {type(exc).__name__}")
                        continue
                else:
                    await self._log(ctx, seq, "warning", "checks", f"{key}: check type '{check}' is not supported")
                    continue
            else:
                await self._log(ctx, seq, "warning", "checks", f"{key}: referenced check not found in playbook")
                continue
            await self._emit_check(ctx, seq, outcome)

        if flow.expect:
            if not self.judge:
                await self._log(ctx, seq, "info", "checks", "expectations not evaluated: no judge configured")
            else:
                await judge_inputs()
                for n, text in enumerate(flow.expect, start=1):
                    examples = select_examples(self.spec.reasoning_examples, "judge", f"{flow.key} {text}")
                    try:
                        outcome = await expectations.run_expectation_live(
                            self.judge, flow.key, n, text, severity, flow.covers, page_text, shots, hints, examples, page,
                            journey=(flow.goal or "; ".join(flow.steps)) + ("\nSteps already done: " + " | ".join(ctx.done[-25:]) if ctx.done else "")
                            + ("\nFiles the browser downloaded during this journey (a download can start several seconds after the click that caused it, so it may be listed after a later step; a file named like a deck or report belongs to the Generate or Export click before it): " + ", ".join(ctx.downloads) if ctx.downloads else "\nNo file was downloaded during this journey."), console_logs=rt.sandbox.console_logs,
                            state_js=PAGE_STATE_JS, network_calls=rt.recorder.calls, snapshots=ctx.snapshots)
                    except Exception as exc:
                        await self._log(ctx, seq, "warning", "checks",
                                        f"expectation {n} could not be judged: {type(exc).__name__}")
                        continue
                    if outcome is None:
                        await self._log(ctx, seq, "info", "checks", f"expectation {n} stayed inconclusive after trying it on the live page: {text}")
                        continue
                    await self._emit_check(ctx, seq, outcome)
