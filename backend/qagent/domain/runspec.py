from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from qagent.domain.schemas import RunMode


class FlowSpec(BaseModel):
    key: str
    severity: str = "high"
    steps: List[str] = Field(default_factory=list)
    expect: List[str] = Field(default_factory=list)
    test_data: Dict[str, Any] = Field(default_factory=dict)
    formulas: Dict[str, Any] = Field(default_factory=dict)
    edge_cases: List[str] = Field(default_factory=list)


class RunSpec(BaseModel):
    run_id: str
    app_id: str
    base_url: str
    allowed_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    mode: RunMode = RunMode.HYBRID
    flows: List[FlowSpec] = Field(default_factory=list)
    step_budget: int = 25
    time_budget_s: int = 90
    gate_auto_min: float = 0.75
    gate_escalate_min: float = 0.45
    trigger: str = "manual"
    replay_of_run_id: Optional[str] = None
