from typing import Any, Dict, List, Optional

from qagent.domain import models as m
from qagent.domain import schemas as s


def iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


def app_out(a: m.App) -> s.AppResponse:
    return s.AppResponse(
        id=a.id, slug=a.slug, name=a.name, base_url=a.base_url, allowed_hosts=a.allowed_hosts or [],
        description=a.description, prd_markdown=a.prd_markdown, default_mode=s.RunMode(a.default_mode),
        created_at=iso(a.created_at) or "", reset_path=a.reset_path,
        gate_overrides=a.gate_overrides or {}, redact_keys=a.redact_keys or [],
    )


def run_out(r: m.Run) -> s.RunResponse:
    return s.RunResponse(
        id=r.id, app_id=r.app_id, playbook_version_id=r.playbook_version_id, mode=s.RunMode(r.mode),
        status=r.status, trigger=r.trigger, started_at=iso(r.started_at), finished_at=iso(r.finished_at),
        totals=s.RunTotals.model_validate(r.totals or {}),
    )


def screenshot_url(run_id: str, flow_key: str, seq: int) -> str:
    return f"/api/artifacts/{run_id}/flows/{flow_key}/steps/{seq}/screenshot.jpg"


def finding_out(f: m.FindingRecord) -> s.Finding:
    return s.Finding(
        id=f.id, flow_run_id=f.flow_run_id, step_seq=f.step_seq, severity=f.severity, kind=f.kind,
        title=f.title, expected=f.expected, actual=f.actual, evidence=f.evidence or {},
        check_key=f.check_key, check_result_id=f.check_result_id, requirement_keys=f.requirement_keys or [],
        fingerprint=f.fingerprint, judged_by=f.judged_by, issue_id=f.issue_id,
    )


def decision_out(d: m.Decision) -> s.DecisionResult:
    resp: Dict[str, Any] = d.response or {}
    return s.DecisionResult(
        decider=d.decider, model_version=d.model_version, selected_action_id=d.choice, confidence=d.confidence,
        tier=s.ConfidenceTier(d.branch), reasoning=resp.get("reasoning"),
        probabilities={int(k): v for k, v in (d.probabilities or {}).items()},
        latency_ms=d.latency_ms, input_tokens=d.input_tokens, output_tokens=d.output_tokens,
        cost_usd=resp.get("cost_usd", 0.0),
    )


def step_out(
    step: m.Step, run_id: str, flow_key: str, timing: Optional[m.StepTiming],
    decision: Optional[m.Decision], findings: List[m.FindingRecord],
) -> s.StepSummary:
    t = s.StepTimings()
    if timing:
        t = s.StepTimings(
            observe_ms=timing.observe_ms, extract_ms=timing.extract_ms, decide_ms=timing.decide_ms,
            gate_ms=timing.gate_ms, act_ms=timing.act_ms, settle_ms=timing.settle_ms, verify_ms=timing.verify_ms,
            total_ms=timing.observe_ms + timing.extract_ms + timing.decide_ms + timing.gate_ms
            + timing.act_ms + timing.settle_ms + timing.verify_ms,
        )
    base = f"/api/artifacts/{run_id}/flows/{flow_key}/steps/{step.seq}"
    return s.StepSummary(
        id=step.id, flow_run_id=step.flow_run_id, seq=step.seq, intent=step.intent, action_id=step.action_id,
        action_label=step.action_label, page_tag=step.page_tag, url=step.url, status=step.status, timings=t,
        screenshot_url=f"{base}/screenshot.jpg" if step.artifacts_complete else None,
        dom_url=f"{base}/dom.html" if step.artifacts_complete else None,
        decision=decision_out(decision) if decision else None,
        findings=[finding_out(f) for f in findings if f.step_seq == step.seq],
    )


def network_out(c: m.NetworkCallRecord, run_id: str, flow_key: str) -> s.NetworkCall:
    base = f"/api/artifacts/{run_id}/flows/{flow_key}/network/{c.id}"
    return s.NetworkCall(
        id=c.id, flow_run_id=c.flow_run_id, step_seq=c.step_seq, method=c.method, url=c.url, status=c.status,
        duration_ms=c.duration_ms, req_size=c.req_size, resp_size=c.resp_size, is_api=c.is_api,
        req_body_url=f"{base}/request.json" if c.req_size else None,
        resp_body_url=f"{base}/response.json" if c.resp_size else None,
    )
