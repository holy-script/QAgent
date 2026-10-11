import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain.events import EventEnvelope, QAgentEventType
from qagent.domain.models import (
    CheckResult,
    Decision,
    EvidenceLink,
    EventRecord,
    FindingRecord,
    FlowRun,
    LogEntryRecord,
    ModelCall,
    NetworkCallRecord,
    Run,
    SpanRecord,
    Step,
    StepTiming,
)
from qagent.storage.db import async_session_factory
from qagent.engine.tracing import logger


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class PersistenceSink:
    """
    Subscribes to engine events: appends each one to the `events` log, projects it
    into the relational tables, and fans it out to in-process listeners (SSE).
    """

    def __init__(
        self,
        run_id: str,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        start_seq: int = 0,
        batch_size: int = 50,
    ):
        self.run_id = run_id
        self._seq = start_seq
        self._session_factory = session_factory or async_session_factory
        self.listeners: List[asyncio.Queue] = []
        # Every event of the run, in order. Live consumers (SSE) read from here, so they never wait on the
        # database and a late joiner still gets the full history while the run is active.
        self.buffer: List[EventEnvelope] = []
        self._pending: asyncio.Queue = asyncio.Queue()
        self._writer: Optional[asyncio.Task] = None
        self._batch_size = batch_size

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.listeners.append(q)
        return q

    def attach(self) -> Tuple[asyncio.Queue, List[EventEnvelope]]:
        """Atomically (no await in between) snapshot the history and subscribe to what follows."""
        return self.subscribe(), list(self.buffer)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.listeners:
            self.listeners.remove(q)

    async def emit(self, event_type: QAgentEventType, payload: Dict[str, Any]) -> EventEnvelope:
        """Assigns the next seq, broadcasts immediately, and queues the event for batched persistence."""
        self._seq += 1
        now = datetime.now(timezone.utc)
        envelope = EventEnvelope(
            run_id=self.run_id, seq=self._seq, type=event_type, payload=payload, ts=now.isoformat()
        )
        self.buffer.append(envelope)
        for listener in list(self.listeners):
            listener.put_nowait(envelope)
        if self._writer is None or self._writer.done():
            self._writer = asyncio.create_task(self._write_loop())
        self._pending.put_nowait((envelope, now))
        return envelope

    async def flush(self) -> None:
        """Waits until every emitted event has been written to the database."""
        await self._pending.join()

    async def _write_loop(self) -> None:
        while True:
            batch = [await self._pending.get()]
            while len(batch) < self._batch_size and not self._pending.empty():
                batch.append(self._pending.get_nowait())
            try:
                await self._write(batch)
            except Exception as exc:  # persistence must never kill a run: fall back to one event per transaction
                logger.error("sink.batch_failed", run_id=self.run_id, error=type(exc).__name__, size=len(batch))
                for item in batch:
                    try:
                        await self._write([item])
                    except Exception as inner:
                        logger.error("sink.persist_failed", run_id=self.run_id, type=item[0].type.value,
                                     error=type(inner).__name__)
            finally:
                for _ in batch:
                    self._pending.task_done()

    async def _write(self, batch: List[Tuple[EventEnvelope, datetime]]) -> None:
        async with self._session_factory() as session:
            for env, now in batch:
                session.add(EventRecord(run_id=self.run_id, seq=env.seq, type=env.type.value,
                                        payload=env.payload, ts=now))
                await self._project(session, env.type, env.payload, now)
            await session.commit()

    async def _project(self, session: AsyncSession, t: QAgentEventType, p: Dict[str, Any], now: datetime) -> None:
        if t == QAgentEventType.RUN_STARTED:
            run = await session.get(Run, self.run_id)
            if run is None:
                run = Run(id=self.run_id, app_id=p.get("app_id", ""), mode=p.get("mode", "hybrid"))
                session.add(run)
            run.status = "running"
            run.started_at = run.started_at or now
            run.environment = p.get("environment", {})

        elif t == QAgentEventType.RUN_FINISHED:
            run = await session.get(Run, self.run_id)
            if run:
                run.status = p.get("status", "passed")
                run.finished_at = now
                run.totals = p.get("totals", {})
                run.environment = {**(run.environment or {}), **p.get("environment", {})}

        elif t == QAgentEventType.MODEL_CALL:
            session.add(ModelCall(run_id=self.run_id, created_at=now, **{k: p[k] for k in (
                "flow_run_id", "purpose", "decider", "model_version", "label", "input_hash", "response", "latency_ms",
                "input_tokens", "output_tokens", "cost_usd", "replayed") if k in p}))

        elif t == QAgentEventType.RUN_ERROR:
            run = await session.get(Run, self.run_id)
            if run:
                run.status = "error"
                run.finished_at = now

        elif t == QAgentEventType.FLOW_STARTED:
            session.add(FlowRun(
                id=p["flow_run_id"], run_id=self.run_id, flow_key=p["flow_key"],
                variant_of=p.get("variant_of"), status="running"
            ))

        elif t == QAgentEventType.FLOW_FINISHED:
            flow = await session.get(FlowRun, p["flow_run_id"])
            if flow:
                flow.status = p.get("status", "passed")
                flow.step_count = p.get("step_count", 0)
                flow.duration_ms = p.get("duration_ms", 0.0)
                flow.failure_reason = p.get("failure_reason")

        elif t == QAgentEventType.STEP_OBSERVED:
            session.add(Step(
                id=p["step_id"], flow_run_id=p["flow_run_id"], seq=p["step_seq"], intent=p.get("intent", ""),
                action_id=0, action_label="", page_tag=p.get("page_title", ""), url=p.get("url", ""),
                status="running",
            ))

        elif t == QAgentEventType.DECISION_MADE:
            session.add(Decision(
                step_id=p["step_id"], decider=p["decider"], model_version=p.get("model_version", ""),
                question=p.get("question", ""), choice=p["selected_action_id"],
                probabilities={str(k): v for k, v in p.get("probabilities", {}).items()},
                confidence=p["confidence"], branch=p.get("branch") or p.get("tier", "AUTO"), latency_ms=p.get("latency_ms", 0.0),
                input_tokens=p.get("input_tokens", 0), output_tokens=p.get("output_tokens", 0),
                input_hash=p.get("input_hash", ""), few_shot_ids=p.get("few_shot_ids", []),
                request=p.get("request", {}), response=p.get("response", {}),
            ))

        elif t == QAgentEventType.ACTION_EXECUTED:
            step = await session.get(Step, p["step_id"])
            if step:
                step.action_id = p.get("action_id") or 0
                step.action_label = p.get("action_label", "")
                step.target_bbox = p.get("target_bbox")
                step.status = "running" if p.get("status") == "success" else "failed"

        elif t == QAgentEventType.VERIFICATION_STEP:
            step = await session.get(Step, p["step_id"])
            if step:
                step.status = p.get("status", step.status)
                step.url = p.get("url", step.url)
            timings = p.get("timings") or {}
            session.add(StepTiming(
                step_id=p["step_id"],
                **{k: timings.get(k, 0.0) for k in (
                    "observe_ms", "extract_ms", "decide_ms", "gate_ms", "act_ms", "settle_ms", "verify_ms"
                )},
            ))

        elif t == QAgentEventType.ARTIFACT_UPLOADED:
            # A step's evidence is complete once its "after" screenshot is stored.
            if p.get("kind") == "screenshot_after" and p.get("step_seq") is not None:
                step = (await session.execute(select(Step).where(
                    Step.flow_run_id == p["flow_run_id"], Step.seq == p["step_seq"]))).scalars().first()
                if step:
                    step.artifacts_complete = True

        elif t == QAgentEventType.NETWORK_CALL:
            session.add(NetworkCallRecord(
                id=p["call_id"], flow_run_id=p["flow_run_id"], step_seq=p["step_seq"], method=p["method"],
                url=p["url"], status=p["status"], duration_ms=p["duration_ms"], req_size=p.get("req_size", 0),
                resp_size=p.get("resp_size", 0), is_api=p.get("is_api", False),
                traceparent=p.get("traceparent"),
            ))

        elif t == QAgentEventType.CHECK_RESULT:
            session.add(CheckResult(
                id=p["check_id"], run_id=self.run_id, flow_run_id=p["flow_run_id"], step_seq=p["step_seq"],
                check_key=p["check_key"], kind=p["kind"], passed=bool(p["pass"]), expected=p.get("expected", ""),
                actual=p.get("actual", ""), inputs=p.get("inputs", {}), judged_by=p.get("judged_by", "code"),
                confidence=p.get("confidence"), created_at=now,
            ))

        elif t == QAgentEventType.FINDING_DISCOVERED:
            session.add(FindingRecord(
                id=p["id"], flow_run_id=p["flow_run_id"], run_id=p.get("run_id", self.run_id),
                step_seq=p["step_seq"], check_result_id=p.get("check_result_id"), check_key=p.get("check_key", ""),
                severity=p["severity"], kind=p["kind"], title=p["title"], expected=p["expected"], actual=p["actual"],
                requirement_keys=p.get("requirement_keys", []), fingerprint=p.get("fingerprint", ""),
                judged_by=p.get("judged_by", "code"), evidence=p.get("evidence", {}),
            ))
            for link in p.get("evidence_links", []):
                session.add(EvidenceLink(finding_id=p["id"], kind=link["kind"], ref_id=link["ref_id"],
                                         note=link.get("note", "")))

        elif t == QAgentEventType.LOG_EMITTED:
            session.add(LogEntryRecord(
                run_id=self.run_id, flow_run_id=p.get("flow_run_id"), step_seq=p.get("step_seq"),
                level=p.get("level", "info"), source=p.get("source", "engine"), message=p.get("message", ""),
                data=p.get("data", {}), ts=now,
            ))

        elif t == QAgentEventType.SPAN_ENDED:
            session.add(SpanRecord(run_id=self.run_id, **p))
