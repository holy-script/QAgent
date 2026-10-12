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
    hints: List[str] = Field(default_factory=list, description="Applicable gotcha notes (one line each)")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Reasoning examples for Claude only")


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
    few_shot_ids: List[str] = Field(default_factory=list)
    outcome: str = Field(default="act", description="act | done (step already satisfied) | stuck (no candidate fits)")
    risky: Optional[float] = Field(default=None, description="P(action is harmful beyond the test step)")
    prev_step_ok: Optional[float] = Field(default=None, description="P(previous step achieved its goal)")


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
    check_key: str = ""
    check_result_id: Optional[str] = None
    requirement_keys: List[str] = Field(default_factory=list)
    fingerprint: str = ""
    judged_by: str = "code"
    issue_id: Optional[str] = None


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
    # Where the cost went: step decisions + judge + planner make up the agent's cost; reports are added after.
    agent_cost_usd: float = 0.0
    judge_calls: int = 0
    judge_cost_usd: float = 0.0
    planner_cost_usd: float = 0.0
    report_calls: int = 0
    report_cost_usd: float = 0.0


# --- Request/Response API Schemas ---

class CreateAppRequest(BaseModel):
    slug: Optional[str] = Field(default=None, description="Derived from the URL's hostname when omitted")
    name: Optional[str] = Field(default=None, description="Derived from the URL's hostname when omitted")
    base_url: str
    reset_path: Optional[str] = Field(default=None, description="POST here before each run to reset the app")
    allowed_hosts: Optional[List[str]] = Field(default=None, description="Defaults to the base URL's hostname")
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
    reset_path: Optional[str] = None
    gate_overrides: Dict[str, Any] = Field(default_factory=dict)
    redact_keys: List[str] = Field(default_factory=list)
    retention_days: Optional[int] = None
    retention_keep_last: int = 10


class CreateRunRequest(BaseModel):
    app_id: str = Field(default="", description="Ignored on POST /apps/{app_id}/runs")
    playbook_id: Optional[str] = None
    playbook_version_id: Optional[str] = None
    mode: RunMode = RunMode.HYBRID
    trigger: str = "manual"
    step_budget: Optional[int] = None
    time_budget_s: Optional[int] = None
    flow_keys: Optional[List[str]] = Field(default=None, description="Run only these flows (default: all)")
    include_edge_cases: bool = Field(default=True, description="Also run edge-case variants of the selected flows")
    plan: bool = Field(default=False, description="Let Claude write a short note for each step before a journey runs")


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


class TapeEntry(BaseModel):
    """One model call on a run's tape: a step decision, a judgement, a plan, or a report call."""
    kind: str                       # decision | judge | planner | report | bug_narrative
    phase: int                      # 0 plan, 1 steps, 2 judgements, 3 reports (the order things happen in)
    flow_key: Optional[str] = None
    step_seq: Optional[int] = None
    decider: str = ""
    model_version: str = ""
    label: str = ""
    outcome: str = ""               # e.g. the chosen element, or "true"/"false", or "plan written"
    confidence: Optional[float] = None
    branch: Optional[str] = None    # AUTO | ESCALATE (decisions)
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    replayed: bool = False


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
    app_id: str = Field(default="", description="Ignored on app-scoped and version routes")
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


class PlaybookUploadResponse(BaseModel):
    playbook: PlaybookResponse
    version: PlaybookVersionResponse
    created: bool = Field(description="False when the content hash matched the latest version")
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    coverage: Dict[str, Any] = Field(default_factory=dict)


class PlaybookValidationResponse(BaseModel):
    title: str
    base_url: str
    counts: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    coverage: Dict[str, Any] = Field(default_factory=dict)
    flows: List[Dict[str, Any]] = Field(default_factory=list)
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Every parsed item: key, category, title, body")
    links: List[Dict[str, str]] = Field(default_factory=list)


class PlaybookItemResponse(BaseModel):
    id: str
    version_id: str
    item_key: str
    category: str
    title: str
    body: Dict[str, Any] = Field(default_factory=dict)


# --- Apps, flows, checks, issues, reports, traceability (B18) ---

class UpdateAppRequest(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    allowed_hosts: Optional[List[str]] = None
    description: Optional[str] = None
    prd_markdown: Optional[str] = None
    default_mode: Optional[RunMode] = None
    gate_overrides: Optional[Dict[str, Any]] = None
    redact_keys: Optional[List[str]] = None
    reset_path: Optional[str] = None
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650, description="null keeps runs for ever")
    retention_keep_last: Optional[int] = Field(default=None, ge=0, le=1000)


class AppFileResponse(BaseModel):
    id: str
    name: str
    content_type: str
    size_bytes: int
    created_at: str
    builtin: bool = False


class RetentionStatus(BaseModel):
    retention_days: Optional[int] = None
    retention_keep_last: int = 10
    total_runs: int = 0
    would_delete: int = 0
    oldest_started_at: Optional[str] = None


class RetentionResult(BaseModel):
    runs_deleted: int = 0
    files_removed: int = 0


class AppSummaryResponse(AppResponse):
    last_run: Optional[RunResponse] = None
    recent_statuses: List[str] = Field(default_factory=list, description="Newest first, up to 20")
    pass_rate: Optional[float] = None
    open_issues: int = 0


class CheckResultResponse(BaseModel):
    id: str
    run_id: str
    flow_run_id: str
    flow_key: Optional[str] = None
    step_seq: int
    check_key: str
    kind: str
    passed: bool
    expected: str = ""
    actual: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict)
    judged_by: str = "code"
    confidence: Optional[float] = None


class FlowResultDot(BaseModel):
    run_id: str
    flow_run_id: str
    status: str
    duration_ms: float
    started_at: Optional[str] = None


class FlowSummaryResponse(BaseModel):
    flow_key: str
    variant_of: Optional[str] = None
    severity: str = "high"
    covers: List[str] = Field(default_factory=list)
    checks: List[str] = Field(default_factory=list)
    last_results: List[FlowResultDot] = Field(default_factory=list)
    median_duration_ms: Optional[float] = None
    flakiness: float = Field(default=0.0, description="Share of consecutive runs whose status changed")


class IssueResponse(BaseModel):
    id: str
    app_id: str
    fingerprint: str
    title: str
    severity: str
    status: str
    kind: str = ""
    check_key: str = ""
    flow_key: str = ""
    requirement_keys: List[str] = Field(default_factory=list)
    first_seen_run_id: Optional[str] = None
    last_seen_run_id: Optional[str] = None
    last_pass_run_id: Optional[str] = None
    occurrences: int = 1
    updated_at: Optional[str] = None


class IssueOccurrence(BaseModel):
    run_id: str
    finding_id: str
    step_seq: int
    severity: str
    started_at: Optional[str] = None


class IssueDetailResponse(IssueResponse):
    occurrence_list: List[IssueOccurrence] = Field(default_factory=list)


class ReportResponse(BaseModel):
    id: str
    app_id: str
    run_id: Optional[str] = None
    kind: str
    issue_id: Optional[str] = None
    status: str
    content: Dict[str, Any] = Field(default_factory=dict)
    markdown_artifact_id: Optional[str] = None
    html_artifact_id: Optional[str] = None
    pdf_artifact_id: Optional[str] = None
    model_version: Optional[str] = None
    generated_at: Optional[str] = None


class TraceabilityResponse(BaseModel):
    version_id: str
    playbook_id: str
    latest_run_id: Optional[str] = None
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    uncovered: List[str] = Field(default_factory=list)


class NetworkCallDetail(NetworkCall):
    background: bool = False
    traceparent: Optional[str] = None
    flow_key: Optional[str] = None
    req_artifact_key: Optional[str] = None
    resp_artifact_key: Optional[str] = None


class RequirementProposal(BaseModel):
    key: str
    title: str
    prd_ref: str
    acceptance: str
    priority: str
    quote: str


class PrdExtractResponse(BaseModel):
    proposals: List[RequirementProposal] = Field(default_factory=list)
    markdown: str = Field(default="", description="The proposals as playbook Markdown, ready to paste under ## Requirements")
