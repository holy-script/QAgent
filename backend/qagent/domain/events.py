from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QAgentEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    FLOW_STARTED = "FLOW_STARTED"
    STEP_OBSERVED = "STEP_OBSERVED"
    DECISION_MADE = "DECISION_MADE"
    GATE_TRIGGERED = "GATE_TRIGGERED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    NETWORK_CALL = "NETWORK_CALL"
    VERIFICATION_STEP = "VERIFICATION_STEP"
    FINDING_DISCOVERED = "FINDING_DISCOVERED"
    FLOW_FINISHED = "FLOW_FINISHED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    LOG_EMITTED = "LOG_EMITTED"
    SPAN_ENDED = "SPAN_ENDED"


class EventEnvelope(BaseModel):
    run_id: str
    seq: int
    type: QAgentEventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: str
