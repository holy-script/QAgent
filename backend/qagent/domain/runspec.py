from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from qagent.domain.schemas import RunMode


class FlowSpec(BaseModel):
    key: str                                  # "add-to-cart" or a variant such as "add-to-cart#EC-2"
    severity: str = "high"
    steps: List[str] = Field(default_factory=list)
    expect: List[str] = Field(default_factory=list)
    test_data: Dict[str, Any] = Field(default_factory=dict)
    covers: List[str] = Field(default_factory=list)   # REQ- keys
    checks: List[str] = Field(default_factory=list)   # F- / UX- keys evaluated at the end of the flow
    variant_of: Optional[str] = None                  # base flow key for edge-case variants
    edge_case: Optional[str] = None                   # EC- key that produced this variant

    @property
    def base_key(self) -> str:
        return self.variant_of or self.key


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

    # Playbook items referenced by flows (keyed by ID), copied from the pinned playbook version.
    requirements: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    formulas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    ux_rules: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    gotchas: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_examples: List[Dict[str, Any]] = Field(default_factory=list)
    playbook_hash: str = ""
    plan: bool = False                        # Claude writes per-step notes before each journey
    reset_path: Optional[str] = None          # POST once before the run to reset the target app
    inject_traceparent: bool = False
    redact_keys: List[str] = Field(default_factory=list)   # JSON keys masked in stored network bodies
