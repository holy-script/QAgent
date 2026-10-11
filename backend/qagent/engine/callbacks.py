from typing import Any, Dict, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler

from qagent.domain.events import QAgentEventType
from qagent.engine.tracing import Span
from qagent.storage.persistence_sink import PersistenceSink

# LangGraph node names that get a span. Model calls are spans too (runs named "model:<decider>").
TRACED_NODES = {"observe", "decide", "gate", "escalate", "act", "settle", "verify"}


class SpanCallbackHandler(AsyncCallbackHandler):
    """
    Turns LangChain/LangGraph run callbacks into persisted spans:
    flow -> {observe, decide -> model:<decider>, gate, escalate, act, settle, verify}.
    """

    def __init__(self, sink: PersistenceSink, trace_id: str, flow_span: Span, flow_key: str):
        self.sink = sink
        self.trace_id = trace_id
        self.flow_span = flow_span
        self.flow_key = flow_key
        self._open: Dict[UUID, Span] = {}

    def _kind(self, name: Optional[str]) -> Optional[str]:
        if name in TRACED_NODES:
            return "node"
        if name and name.startswith("model:"):
            return "model"
        return None

    async def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None,
                             metadata=None, name=None, **kwargs: Any) -> None:
        kind = self._kind(name)
        if kind is None:
            return
        parent = self._open.get(parent_run_id) if parent_run_id else None
        step_seq = inputs.get("idx") if isinstance(inputs, dict) else None
        span = Span(name, kind, self.trace_id, parent=parent or self.flow_span,
                    flow_key=self.flow_key, step_seq=step_seq)
        self._open[run_id] = span

    async def _end(self, run_id: UUID, status: str) -> None:
        span = self._open.pop(run_id, None)
        if span is not None:
            await self.sink.emit(QAgentEventType.SPAN_ENDED, span.end(status))

    async def on_chain_end(self, outputs, *, run_id, **kwargs: Any) -> None:
        await self._end(run_id, "ok")

    async def on_chain_error(self, error, *, run_id, **kwargs: Any) -> None:
        await self._end(run_id, "error")
