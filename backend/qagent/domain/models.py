from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import BigInteger, Column, JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class App(SQLModel, table=True):
    __tablename__ = "apps"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    base_url: str
    allowed_hosts: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    description: Optional[str] = None
    prd_markdown: Optional[str] = None
    default_mode: str = "hybrid"
    reset_path: Optional[str] = None  # POST here before each flow to reset the target app's state
    gate_overrides: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    redact_keys: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    retention_days: Optional[int] = None  # finished runs older than this are cleaned up; None keeps them for ever
    retention_keep_last: int = 10         # ...but the newest N runs are always kept
    created_at: datetime = Field(default_factory=utc_now)


class AppFile(SQLModel, table=True):
    """A file an app's tests can upload through a page's file field (Settings > Test files)."""
    __tablename__ = "app_files"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    app_id: str = Field(index=True)
    name: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    object_key: str
    sha256: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Playbook(SQLModel, table=True):
    __tablename__ = "playbooks"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    app_id: str = Field(index=True)
    name: str
    current_version_id: Optional[str] = None
    status: str = "confirmed"  # draft, confirmed
    created_at: datetime = Field(default_factory=utc_now)


class PlaybookVersion(SQLModel, table=True):
    __tablename__ = "playbook_versions"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    playbook_id: str = Field(index=True)
    version_no: int = 1
    raw_markdown: str
    parsed: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    warnings: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    content_hash: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    app_id: str = Field(index=True)
    playbook_version_id: Optional[str] = Field(default=None, index=True)
    mode: str = "hybrid"  # hybrid, baseline, stub
    trigger: str = "manual"  # manual, replay
    replay_of_run_id: Optional[str] = None
    status: str = "pending"  # pending, running, passed, failed, stopped, error
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    totals: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    environment: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class FlowRun(SQLModel, table=True):
    __tablename__ = "flow_runs"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_key: str = Field(index=True)
    variant_of: Optional[str] = None
    status: str = "pending"
    step_count: int = 0
    duration_ms: float = 0.0
    failure_reason: Optional[str] = None


class Step(SQLModel, table=True):
    __tablename__ = "steps"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    flow_run_id: str = Field(index=True)
    seq: int = Field(index=True)
    intent: str
    action_id: int
    action_label: str
    target_bbox: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    page_tag: str
    url: str
    status: str = "pending"
    artifacts_complete: bool = False


class StepTiming(SQLModel, table=True):
    __tablename__ = "step_timings"

    step_id: str = Field(primary_key=True)
    observe_ms: float = 0.0
    extract_ms: float = 0.0
    decide_ms: float = 0.0
    gate_ms: float = 0.0
    act_ms: float = 0.0
    settle_ms: float = 0.0
    verify_ms: float = 0.0


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    step_id: str = Field(index=True)
    decider: str
    model_version: str
    question: str
    choice: int
    probabilities: Dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float
    branch: str
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    input_hash: str = ""
    few_shot_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    request: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    response: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ModelCall(SQLModel, table=True):
    """Every judge and report call a run makes (the step decisions live in `decisions`). Together they are the
    run's tape: replay serves these back by `input_hash`, and `cost_usd` rolls up into the run's cost."""
    __tablename__ = "model_calls"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_run_id: Optional[str] = Field(default=None, index=True)
    purpose: str = Field(index=True)  # judge | report | bug_narrative | planner
    decider: str = ""                 # jev | claude
    model_version: str = ""
    label: str = ""                   # the question or task, for humans
    input_hash: str = Field(default="", index=True)
    response: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    replayed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class FindingRecord(SQLModel, table=True):
    __tablename__ = "findings"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    flow_run_id: str = Field(index=True)
    run_id: Optional[str] = Field(default=None, index=True)
    step_seq: int
    check_result_id: Optional[str] = None
    check_key: str = ""
    severity: str
    kind: str
    title: str
    expected: str
    actual: str
    requirement_keys: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    fingerprint: str = Field(default="", index=True)
    issue_id: Optional[str] = Field(default=None, index=True)
    judged_by: str = "code"
    evidence: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class NetworkCallRecord(SQLModel, table=True):
    __tablename__ = "network_calls"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    flow_run_id: str = Field(index=True)
    step_seq: int
    method: str
    url: str
    status: int
    duration_ms: float
    req_size: int = 0
    resp_size: int = 0
    is_api: bool = False
    traceparent: Optional[str] = None
    req_artifact_id: Optional[str] = None
    resp_artifact_id: Optional[str] = None


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_run_id: Optional[str] = Field(default=None, index=True)
    step_seq: Optional[int] = None
    kind: str  # screenshot, dom, har, trace, console, body
    object_key: str
    content_type: str
    size_bytes: int = 0
    sha256: str = ""
    uploaded_at: datetime = Field(default_factory=utc_now)


class SpanRecord(SQLModel, table=True):
    __tablename__ = "spans"

    trace_id: str
    span_id: str = Field(primary_key=True)
    parent_span_id: Optional[str] = None
    run_id: str = Field(index=True)
    name: str
    kind: str
    start_ns: int = Field(sa_column=Column(BigInteger, nullable=False))  # epoch ns overflows int4
    end_ns: int = Field(sa_column=Column(BigInteger, nullable=False))
    attributes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "ok"


class LogEntryRecord(SQLModel, table=True):
    __tablename__ = "log_entries"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_run_id: Optional[str] = Field(default=None, index=True)
    step_seq: Optional[int] = None
    level: str
    source: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ts: datetime = Field(default_factory=utc_now)


class EventRecord(SQLModel, table=True):
    __tablename__ = "events"

    run_id: str = Field(primary_key=True)
    seq: int = Field(primary_key=True)
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ts: datetime = Field(default_factory=utc_now)


class PlaybookItem(SQLModel, table=True):
    __tablename__ = "playbook_items"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    version_id: str = Field(index=True)
    item_key: str = Field(index=True)  # REQ-1, F-1, UX-2, G-1, EC-1, RX-1, or a flow key
    category: str
    title: str = ""
    body: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    content_hash: str = ""


class ItemLink(SQLModel, table=True):
    __tablename__ = "item_links"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    version_id: str = Field(index=True)
    from_key: str
    to_key: str = Field(index=True)
    relation: str  # covers, verifies, checks, applies_to


class CheckResult(SQLModel, table=True):
    __tablename__ = "check_results"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_run_id: str = Field(index=True)
    step_seq: int
    check_key: str = Field(index=True)  # F-1, UX-2, expect:add-to-cart:1, EC-3, network:POST /api/pay
    kind: str  # formula, ux_rule, ux_judged, expectation, network, timing
    passed: bool
    expected: str = ""
    actual: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    judged_by: str = "code"  # code, jev, claude
    confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceLink(SQLModel, table=True):
    __tablename__ = "evidence_links"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    finding_id: str = Field(index=True)
    kind: str  # screenshot_before, screenshot_after, annotated, wait_frame, dom, network_call, console, span, decision, trace
    ref_id: str  # object key, call id, step id or span id depending on kind
    note: str = ""


class Issue(SQLModel, table=True):
    __tablename__ = "issues"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    app_id: str = Field(index=True)
    fingerprint: str = Field(index=True)
    title: str
    severity: str
    status: str = "open"  # open, resolved, regressed
    kind: str = ""
    check_key: str = ""
    flow_key: str = ""
    requirement_keys: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    first_seen_run_id: Optional[str] = None
    last_seen_run_id: Optional[str] = None
    last_pass_run_id: Optional[str] = None
    occurrences: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    app_id: str = Field(index=True)
    run_id: Optional[str] = Field(default=None, index=True)
    kind: str  # run, bug
    issue_id: Optional[str] = Field(default=None, index=True)
    status: str = "generating"  # generating, ready, failed
    content: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    markdown_artifact_id: Optional[str] = None
    html_artifact_id: Optional[str] = None
    pdf_artifact_id: Optional[str] = None
    model_version: Optional[str] = None
    generated_at: Optional[datetime] = None


class Recommendation(SQLModel, table=True):
    __tablename__ = "recommendations"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    report_id: str = Field(index=True)
    category: str  # functional, ux, performance, accessibility, test_coverage
    text: str
    rationale: str = ""
    evidence_finding_ids: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    requirement_keys: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: str = "medium"  # high, medium, low
    effort: str = "m"  # s, m, l
