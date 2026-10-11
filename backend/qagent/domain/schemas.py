from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RunMode(str, Enum):
    HYBRID = "hybrid"      # Jev auto-pilot with Claude escalation
    BASELINE = "baseline"  # Full Claude Sonnet 4.6 reasoning
    STUB = "stub"          # Deterministic fast replay / stub fixtures


class ConfidenceTier(str, Enum):
    AUTO = "AUTO"          # Confidence >= GATE_AUTO_MIN (e.g. 0.75) -> Autonomous execution
    ESCALATE = "ESCALATE"  # GATE_ESCALATE_MIN <= Confidence < GATE_AUTO_MIN -> Escalates to Claude
    STOP = "STOP"          # Confidence < GATE_ESCALATE_MIN -> Safety pause


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingKind(str, Enum):
    FORMULA = "formula"
    DOM = "dom"
    NETWORK = "network"
    TIMING = "timing"


# --- Action & Browser DTOs ---

class BoundingRect(BaseModel):
    x: float
    y: float
    width: float
    height: float


class CandidateAction(BaseModel):
    id: int = Field(description="Compact 1-based index (1-40)")
    tag: str = Field(description="HTML tag, e.g. button, input, a")
    selector: str = Field(description="CSS or text selector to resolve locator")
    label: str = Field(description="Visible text or accessible label")
    action_type: str = Field(default="click", description="click, fill, select, navigate")
    value: Optional[str] = Field(default=None, description="Input value if fill action")
    bounding_box: Optional[BoundingRect] = Field(default=None)


class BrowserObservation(BaseModel):
    step_seq: int
    url: str
    page_title: str
    candidates: List[CandidateAction] = Field(default_factory=list)
    screenshot_url: Optional[str] = None
    dom_snapshot_url: Optional[str] = None
    network_summary: Dict[str, Any] = Field(default_factory=dict)


# --- Decision DTOs ---

class DecisionRequest(BaseModel):
    step_seq: int
    intent: str
    url: str
    candidates: List[CandidateAction]
    page_summary: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)


class DecisionResult(BaseModel):
    decider: str = Field(description="jev, claude, stub, or replay")
    model_version: str
    selected_action_id: int
    confidence: float
    tier: ConfidenceTier
    reasoning: Optional[str] = None
    probabilities: Dict[int, float] = Field(default_factory=dict)
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# --- Step Timing DTO ---

class StepTimings(BaseModel):
    observe_ms: float = 0.0
    extract_ms: float = 0.0
    decide_ms: float = 0.0
    gate_ms: float = 0.0
    act_ms: float = 0.0
    settle_ms: float = 0.0
    verify_ms: float = 0.0
    total_ms: float = 0.0


# --- Finding DTO ---

class Finding(BaseModel):
    id: str
    flow_run_id: str
    step_seq: int
    severity: FindingSeverity
    kind: FindingKind
    title: str
    expected: str
    actual: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


# --- Step DTO ---

class StepSummary(BaseModel):
    id: str
    flow_run_id: str
    seq: int
    intent: str
    action_id: int
    action_label: str
    page_tag: str
    url: str
    status: str
    timings: StepTimings
    screenshot_url: Optional[str] = None
    dom_url: Optional[str] = None
    decision: Optional[DecisionResult] = None
    findings: List[Finding] = Field(default_factory=list)


# --- Network Call DTO ---

class NetworkCall(BaseModel):
    id: str
    flow_run_id: str
    step_seq: int
    method: str
    url: str
    status: int
    duration_ms: float
    req_size: int = 0
    resp_size: int = 0
    is_api: bool = False
    req_body_url: Optional[str] = None
    resp_body_url: Optional[str] = None


# --- Run Totals & Metrics ---

class RunTotals(BaseModel):
    total_steps: int = 0
    duration_ms: float = 0.0
    jev_decisions: int = 0
    claude_decisions: int = 0
    total_cost_usd: float = 0.0
    avg_decision_latency_ms: float = 0.0
    findings_count: int = 0
    status: str = "pending"


# --- Request/Response API Schemas ---

class CreateAppRequest(BaseModel):
    slug: str
    name: str
    base_url: str
    allowed_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    description: Optional[str] = None
    prd_markdown: Optional[str] = None
    default_mode: RunMode = RunMode.HYBRID


class AppResponse(BaseModel):
    id: str
    slug: str
    name: str
    base_url: str
    allowed_hosts: List[str]
    description: Optional[str] = None
    prd_markdown: Optional[str] = None
    default_mode: RunMode
    created_at: str


class CreateRunRequest(BaseModel):
    app_id: str
    playbook_id: Optional[str] = None
    playbook_version_id: Optional[str] = None
    mode: RunMode = RunMode.HYBRID
    trigger: str = "manual"
    step_budget: Optional[int] = None
    time_budget_s: Optional[int] = None


class RunResponse(BaseModel):
    id: str
    app_id: str
    playbook_version_id: Optional[str] = None
    mode: RunMode
    status: str
    trigger: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    totals: RunTotals = Field(default_factory=RunTotals)


class FlowRunResponse(BaseModel):
    id: str
    run_id: str
    flow_key: str
    status: str
    step_count: int = 0
    duration_ms: float = 0.0
    failure_reason: Optional[str] = None
    steps: List[StepSummary] = Field(default_factory=list)


class PlaybookResponse(BaseModel):
    id: str
    app_id: str
    name: str
    current_version_id: Optional[str] = None
    status: str
    flows: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    jev_reachable: bool
    bedrock_reachable: bool
    postgres_reachable: bool
    storage_reachable: bool
    active_model: str


# --- Playbook upload, observability DTOs (added in B7; additive to the frozen B0 contract) ---

class CreatePlaybookRequest(BaseModel):
    app_id: str
    name: Optional[str] = None
    raw_markdown: str


class PlaybookVersionResponse(BaseModel):
    id: str
    playbook_id: str
    version_no: int
    content_hash: str
    warnings: List[str] = Field(default_factory=list)
    created_at: str


class SpanResponse(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    run_id: str
    name: str
    kind: str
    start_ns: int
    end_ns: int
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"


class LogEntryResponse(BaseModel):
    id: str
    run_id: str
    flow_run_id: Optional[str] = None
    step_seq: Optional[int] = None
    level: str
    source: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    ts: str


class NormalizeRequest(BaseModel):
    raw_text: str


class NormalizeResponse(BaseModel):
    markdown: str
    flows: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ReplayRequest(BaseModel):
    overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="gate_auto_min, gate_escalate_min, step_budget, time_budget_s, live_fallback",
    )
