from typing import Any, Dict, List, Optional, TypedDict


class FlowState(TypedDict, total=False):
    """
    LangGraph state for one flow. Everything here is JSON-serializable so it can be
    checkpointed; live objects (page, sandbox, recorder) live in FlowRuntime, which is
    passed through `config["configurable"]["rt"]` and is never checkpointed.
    """

    flow_key: str
    flow_run_id: str
    idx: int                       # 1-based number of the step being executed (0 before the first)
    step_id: str
    intent: str
    nav_target: Optional[str]      # set when the step is deterministic navigation (no model call)
    url: str
    title: str
    candidates: List[Dict[str, Any]]
    decision: Optional[Dict[str, Any]]
    input_hash: str
    chosen_id: Optional[int]
    label: str
    tier: str                      # AUTO | ESCALATE | STOP
    escalated: bool
    acted: bool
    settled: bool
    step_status: str               # passed | failed | blocked
    timings: Dict[str, float]
    history: List[Dict[str, Any]]
    failure_reason: Optional[str]
    steps_run: int
    done: bool
