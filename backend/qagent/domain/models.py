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
    gate_overrides: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    redact_keys: List[str] = Field(default_factory=list, sa_column=Column(JSON))
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


class FlowRun(SQLModel, table=True):
    __tablename__ = "flow_runs"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    run_id: str = Field(index=True)
    flow_key: str = Field(index=True)
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
    request: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    response: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class FindingRecord(SQLModel, table=True):
    __tablename__ = "findings"

    id: str = Field(default_factory=gen_uuid, primary_key=True)
    flow_run_id: str = Field(index=True)
    step_seq: int
    severity: str
    kind: str
    title: str
    expected: str
    actual: str
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
