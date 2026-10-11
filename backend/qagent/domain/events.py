from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QAgentEventType(str, Enum):
    RUN_STARTED = "run.started"
    FLOW_STARTED = "flow.started"
    STEP_OBSERVED = "step.observed"
    DECISION_MADE = "decision.made"
    MODEL_CALL = "model.call"
    GATE_TRIGGERED = "gate.triggered"
    ACTION_EXECUTED = "action.executed"
    NETWORK_CALL = "network.call"
    VERIFICATION_STEP = "step.verified"
    FINDING_DISCOVERED = "finding.created"
    FLOW_FINISHED = "flow.finished"
    RUN_FINISHED = "run.finished"
    RUN_ERROR = "error"
    LOG_EMITTED = "log"
    SPAN_ENDED = "span.ended"
    CHECK_RESULT = "check.result"
    REPORT_GENERATING = "report.generating"
    REPORT_READY = "report.ready"
    REPORT_FAILED = "report.failed"
    DIVERGENCE = "divergence"
    ARTIFACT_UPLOADED = "artifact.uploaded"


class EventEnvelope(BaseModel):
    run_id: str
    seq: int
    type: QAgentEventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: str
