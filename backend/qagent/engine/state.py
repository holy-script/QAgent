from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from qagent.domain.schemas import CandidateAction, DecisionResult, Finding
from qagent.domain.runspec import RunSpec


class QAgentState(BaseModel):
    run_spec: RunSpec
    flow_key: str = ""
    step_seq: int = 0
    url: str = ""
    page_title: str = ""
    intent: str = ""
    candidates: List[CandidateAction] = Field(default_factory=list)
    decision: Optional[DecisionResult] = None
    step_status: str = "pending"
    flow_status: str = "pending"
    findings: List[Finding] = Field(default_factory=list)
    cancel_requested: bool = False
    step_budget_remaining: int = 25
    time_budget_remaining_s: int = 90
