import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from qagent.domain.events import EventEnvelope, QAgentEventType
from qagent.domain.models import (
    CheckResult,
    Decision,
    EvidenceLink,
    EventRecord,
    FindingRecord,
    FlowRun,
    LogEntryRecord,
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
    ):
        self.run_id = run_id
        self._seq = start_seq
        self._session_factory = session_factory or async_session_factory
        self.listeners: List[asyncio.Queue] = []
        # Parallel flows emit concurrently; seq assignment, persistence and fan-out must happen
        # in one order, or SSE consumers and resume cursors would see gaps.
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.listeners:
            self.listeners.remove(q)

    async def emit(self, event_type: QAgentEventType, payload: Dict[str, Any]) -> EventEnvelope:
        async with self._lock:
            self._seq += 1
            now = datetime.now(timezone.utc)
            envelope = EventEnvelope(
                run_id=self.run_id, seq=self._seq, type=event_type, payload=payload, ts=now.isoformat()
            )

            try:
                async with self._session_factory() as session:
                    session.add(EventRecord(
                        run_id=self.run_id, seq=self._seq, type=event_type.value, payload=payload, ts=now
                    ))
                    await self._project(session, event_type, payload, now)
                    await session.commit()
            except Exception as exc:  # persistence must never kill a run
                logger.error("sink.persist_failed", run_id=self.run_id, type=event_type.value,
                             error=type(exc).__name__)

            # Notify listeners after the row is durable so SSE resume never skips an event.
            for listener in list(self.listeners):
                await listener.put(envelope)
            return envelope

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
                step.artifacts_complete = True
            timings = p.get("timings") or {}
            session.add(StepTiming(
                step_id=p["step_id"],
                **{k: timings.get(k, 0.0) for k in (
                    "observe_ms", "extract_ms", "decide_ms", "gate_ms", "act_ms", "settle_ms", "verify_ms"
                )},
            ))

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
