import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.config import settings
from qagent.decision.base import Decider
from qagent.decision.claude import ClaudeDecider
from qagent.decision.jev import JevDecider
from qagent.decision.stub import StubDecider
from qagent.decision.claude import BedrockClient
from qagent.decision.ledger import LedgerClient, TapedJudge
from qagent.decision.tape import ReplayDecider
from qagent.domain.models import App, AppFile, Decision, FlowRun, ModelCall, Playbook, PlaybookVersion, Run, Step
from qagent.checks.edge_cases import expand_flows, spec_items
from qagent.checks.ux_judged import Judge
from qagent.domain.runspec import RunSpec
from qagent.domain.schemas import CreateRunRequest, RunMode
from qagent.engine.graph import EngineRunner
from qagent.engine.tracing import logger
from qagent.storage.checkpoint import open_checkpointer
from qagent.storage.db import async_session_factory
from qagent.storage.persistence_sink import PersistenceSink
from qagent.storage.upload_queue import upload_queue


class RunStartError(Exception):
    """Raised when a run cannot be started; `status` is the HTTP status to report."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def default_decider(mode: RunMode) -> Decider:
    if mode == RunMode.STUB:
        return StubDecider()
    if mode == RunMode.HYBRID:
        return JevDecider()
    if not settings.bedrock_api_key:
        raise RunStartError("baseline mode needs BEDROCK_API_KEY", 400)
    return ClaudeDecider()


def default_escalator(mode: RunMode) -> Optional[Decider]:
    """Hybrid runs escalate medium-confidence Jev decisions to Claude when Bedrock is configured."""
    return ClaudeDecider() if mode == RunMode.HYBRID and settings.bedrock_api_key else None


def default_judge(mode: RunMode) -> Optional[Judge]:
    """Stub runs are offline (no judge). Hybrid uses Jev with Claude escalation; baseline uses Claude only."""
    if mode == RunMode.STUB:
        return None
    return Judge.from_settings(use_jev=mode == RunMode.HYBRID, use_claude=True)


@dataclass
class ActiveRun:
    runner: EngineRunner
    sink: PersistenceSink
    task: asyncio.Task


class RunManager:
    """Creates runs, executes them in the background, and exposes their live event streams."""

    def __init__(
        self,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        decider_factory: Callable[[RunMode], Decider] = default_decider,
        escalator_factory: Callable[[RunMode], Optional[Decider]] = default_escalator,
        judge_factory: Callable[[RunMode], Optional[Judge]] = default_judge,
        report_hook: Optional[Callable[..., Any]] = None,
        uploader=upload_queue,
        use_checkpointer: bool = False,
    ):
        self.session_factory = session_factory or async_session_factory
        self.decider_factory = decider_factory
        self.escalator_factory = escalator_factory
        self.judge_factory = judge_factory
        self.report_hook = report_hook
        self.uploader = uploader
        self.active: Dict[str, ActiveRun] = {}
        self.use_checkpointer = use_checkpointer
        self._checkpointer = None
        self._checkpoint_conn = None

    async def _resolve_version(self, session: AsyncSession, app: App, req: CreateRunRequest) -> PlaybookVersion:
        version_id = req.playbook_version_id
        if not version_id:
            stmt = select(Playbook).where(Playbook.app_id == app.id)
            if req.playbook_id:
                stmt = stmt.where(Playbook.id == req.playbook_id)
            playbooks = (await session.execute(stmt)).scalars().all()
            playbook = next((p for p in playbooks if p.current_version_id), None)
            if playbook is None:
                raise RunStartError("app has no playbook to run", 400)
            version_id = playbook.current_version_id
        version = await session.get(PlaybookVersion, version_id)
        if version is None:
            raise RunStartError(f"playbook version {version_id} not found", 404)
        return version

    async def _load_tape(self, session: AsyncSession, run_id: str) -> Dict[str, Dict[str, Any]]:
        """Rebuilds a decision tape (input hash -> recorded response) from a finished run's rows."""
        flow_ids = (await session.execute(select(FlowRun.id).where(FlowRun.run_id == run_id))).scalars().all()
        steps = {st.id: st for st in (await session.execute(select(Step).where(Step.flow_run_id.in_(flow_ids))))
                 .scalars().all()} if flow_ids else {}
        rows = (await session.execute(select(Decision).where(Decision.step_id.in_(list(steps))))).scalars().all() \
            if steps else []
        # An escalated step has two rows with one hash; the last one is what the run acted on.
        return {d.input_hash: {"response": d.response, "step_seq": steps[d.step_id].seq, "intent": d.question}
                for d in rows if d.input_hash and d.response}

    async def _load_plan_tape(self, session: AsyncSession, run_id: str) -> Dict[str, Dict[str, Any]]:
        rows = (await session.execute(select(ModelCall).where(
            ModelCall.run_id == run_id, ModelCall.purpose == "planner"))).scalars().all()
        return {c.input_hash: c.response for c in rows if c.input_hash and c.response and not c.replayed}

    async def _load_judge_tape(self, session: AsyncSession, run_id: str) -> Dict[str, Dict[str, Any]]:
        """Recorded judge verdicts of a finished run (input hash -> verdict)."""
        rows = (await session.execute(select(ModelCall).where(
            ModelCall.run_id == run_id, ModelCall.purpose == "judge"))).scalars().all()
        return {c.input_hash: c.response for c in rows if c.input_hash and c.response and not c.replayed}

    async def replay_run(self, source_run_id: str, overrides: Optional[Dict[str, Any]] = None) -> Run:
        """
        Re-runs a past run's playbook version in a fresh browser, answering every model call from
        the source run's tape. `overrides` may set gate_auto_min, gate_escalate_min, step_budget,
        time_budget_s, and `live_fallback` (true: steps missing from the tape go to the live decider).
        """
        overrides = overrides or {}
        async with self.session_factory() as session:
            source = await session.get(Run, source_run_id)
            if source is None:
                raise RunStartError(f"run {source_run_id} not found", 404)
            if source.status in ("pending", "running"):
                raise RunStartError("source run is still running", 409)
            tape = await self._load_tape(session, source_run_id)
            judge_tape = await self._load_judge_tape(session, source_run_id)
            plan_tape = await self._load_plan_tape(session, source_run_id)
        if not tape:
            raise RunStartError("source run has no recorded decisions to replay", 409)

        mode = RunMode(source.mode)
        fallback = self.decider_factory(mode) if overrides.get("live_fallback") else None
        fallback_judge = self.judge_factory(mode) if overrides.get("live_fallback") else None
        req = CreateRunRequest(
            app_id=source.app_id, playbook_version_id=source.playbook_version_id, mode=mode,
            trigger="replay", step_budget=overrides.get("step_budget"), time_budget_s=overrides.get("time_budget_s"),
            plan=bool(plan_tape),
        )
        return await self.start_run(
            req, decider=ReplayDecider(tape, fallback=fallback), replay_of=source_run_id, overrides=overrides,
            judge=TapedJudge(fallback_judge, tape=judge_tape) if (judge_tape or fallback_judge) else None,
            plan_tape=plan_tape,
        )

    async def start_run(self, req: CreateRunRequest, decider: Optional[Decider] = None,
                        replay_of: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None,
                        judge: Optional[Judge] = None, plan_tape: Optional[Dict[str, Dict[str, Any]]] = None) -> Run:
        decider = decider or self.decider_factory(req.mode)
        overrides = overrides or {}

        async with self.session_factory() as session:
            app = await session.get(App, req.app_id)
            if app is None:
                app = (await session.execute(select(App).where(App.slug == req.app_id))).scalar_one_or_none()
            if app is None:
                raise RunStartError(f"app {req.app_id} not found", 404)
            version = await self._resolve_version(session, app, req)

            parsed = version.parsed
            flows = expand_flows(parsed, req.flow_keys, req.include_edge_cases)
            if not flows:
                raise RunStartError("playbook has no matching flows", 400)

            test_files = {f.name: {"key": f.object_key, "content_type": f.content_type} for f in (
                await session.execute(select(AppFile).where(AppFile.app_id == app.id))).scalars().all()}
            run_id = str(uuid.uuid4())
            app_overrides = app.gate_overrides or {}
            spec = RunSpec(
                run_id=run_id,
                app_id=app.id,
                base_url=app.base_url,
                allowed_hosts=app.allowed_hosts or settings.allowed_hosts_list,
                mode=req.mode,
                flows=flows,
                step_budget=req.step_budget or settings.flow_step_budget,
                time_budget_s=req.time_budget_s or settings.flow_time_budget_s,
                gate_auto_min=overrides.get("gate_auto_min", app_overrides.get("auto_min", settings.gate_auto_min)),
                gate_escalate_min=overrides.get(
                    "gate_escalate_min", app_overrides.get("escalate_min", settings.gate_escalate_min)),
                trigger=req.trigger,
                replay_of_run_id=replay_of,
                plan=req.plan,
                files=test_files,
                reset_path=app.reset_path,
                redact_keys=app.redact_keys or [],
                inject_traceparent=settings.qagent_inject_traceparent,
                **spec_items(parsed),
            )
            run = Run(
                id=run_id,
                app_id=app.id,
                playbook_version_id=version.id,
                mode=req.mode.value,
                trigger=req.trigger,
                replay_of_run_id=replay_of,
                status="pending",
            )
            session.add(run)
            await session.commit()

        self.uploader.start()
        if self.use_checkpointer and self._checkpointer is None:
            # One saver for the process: Postgres `langgraph` schema via the direct URL when configured.
            self._checkpointer, self._checkpoint_conn = await open_checkpointer()
        sink = PersistenceSink(run_id, session_factory=self.session_factory)
        runner = EngineRunner(spec, decider, sink, uploader=self.uploader,
                              escalator=None if replay_of else self.escalator_factory(req.mode),
                              checkpointer=self._checkpointer,
                              judge=judge if replay_of else self.judge_factory(req.mode),
                              planner=self._planner_for(req, replay_of, plan_tape))
        task = asyncio.create_task(self._execute(run_id, runner, sink))
        self.active[run_id] = ActiveRun(runner, sink, task)
        return run

    def _planner_for(self, req: CreateRunRequest, replay_of: Optional[str], tape: Optional[Dict[str, Any]]):
        """Claude (live) for a run that asked for planning; the source run's recorded plans for a repeat."""
        if not req.plan or req.mode == RunMode.STUB:
            return None
        if replay_of:
            return LedgerClient(BedrockClient(), self._noop_record, tape or {}) if tape else None
        return BedrockClient() if settings.bedrock_api_key else None

    @staticmethod
    async def _noop_record(call: Dict[str, Any]) -> None:  # the engine rebinds this to its own recorder
        return None

    async def _execute(self, run_id: str, runner: EngineRunner, sink: PersistenceSink) -> None:
        try:
            await runner.run()
            if self.report_hook:
                await self.report_hook(self.session_factory, sink, runner.spec, self.uploader)
        except Exception as exc:
            logger.error("run.failed", run_id=run_id, error=type(exc).__name__)
        finally:
            await sink.flush()
            self.active.pop(run_id, None)

    async def stop(self, run_id: str) -> bool:
        """Requests a stop. Returns False if the run is not running in this process."""
        active = self.active.get(run_id)
        if active is None:
            return False
        active.runner.stop()
        return True

    def attach(self, run_id: str):
        """(queue, history snapshot) for a run that is live in this process, else None."""
        active = self.active.get(run_id)
        return active.sink.attach() if active else None

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        active = self.active.get(run_id)
        if active:
            active.sink.unsubscribe(queue)

    async def shutdown(self) -> None:
        for active in list(self.active.values()):
            active.runner.stop()
        if self.active:
            await asyncio.gather(*(a.task for a in self.active.values()), return_exceptions=True)
        if self._checkpoint_conn is not None:
            await self._checkpoint_conn.close()


_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        from qagent.reports.pipeline import run_report_pipeline
        _manager = RunManager(use_checkpointer=True, report_hook=run_report_pipeline)
    return _manager


async def recover_orphaned_runs(session_factory: Callable[[], AsyncSession]) -> int:
    """
    Runs live in this process. After a restart, any run still marked pending/running can never finish, so close
    it: mark it as an error, fail its open journeys, and append a final `error` event so viewers stop waiting.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func
    from qagent.domain.models import EventRecord

    async with session_factory() as session:
        orphans = (await session.execute(select(Run).where(Run.status.in_(["pending", "running"])))).scalars().all()
        for run in orphans:
            run.status, run.finished_at = "error", datetime.now(timezone.utc)
            for flow in (await session.execute(select(FlowRun).where(FlowRun.run_id == run.id))).scalars():
                if flow.status in ("pending", "running"):
                    flow.status, flow.failure_reason = "failed", flow.failure_reason or "Server restarted during this run"
            last = (await session.execute(select(func.max(EventRecord.seq)).where(EventRecord.run_id == run.id))).scalar() or 0
            session.add(EventRecord(run_id=run.id, seq=last + 1, type="error",
                                    payload={"message": "The server restarted while this run was in progress."}))
        await session.commit()
        return len(orphans)
