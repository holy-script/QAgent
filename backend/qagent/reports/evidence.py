from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain import models as m
from qagent.storage.objects import object_store

ARTIFACT_KINDS = {"screenshot_before", "screenshot_after", "annotated", "wait_frame", "dom", "trace", "console"}


def excerpt(key: str, limit: int = 600) -> Optional[str]:
    """First `limit` characters of a stored JSON/text object, for embedding in reports."""
    try:
        data = object_store.get_bytes(key)
    except Exception:
        return None
    return data[:limit].decode("utf-8", "replace") if data else None


async def evidence_graph(session: AsyncSession, finding_id: str) -> Optional[Dict[str, Any]]:
    """Everything that proves one finding, resolved from evidence links to concrete rows."""
    finding = await session.get(m.FindingRecord, finding_id)
    if finding is None:
        return None
    links = (await session.execute(
        select(m.EvidenceLink).where(m.EvidenceLink.finding_id == finding_id))).scalars().all()
    check = await session.get(m.CheckResult, finding.check_result_id) if finding.check_result_id else None
    run = await session.get(m.Run, finding.run_id) if finding.run_id else None

    keys = [l.ref_id for l in links if l.kind in ARTIFACT_KINDS]
    artifacts = {a.object_key: a for a in (await session.execute(
        select(m.Artifact).where(m.Artifact.object_key.in_(keys)))).scalars().all()} if keys else {}
    call_ids = [l.ref_id for l in links if l.kind == "network_call"]
    calls = {c.id: c for c in (await session.execute(
        select(m.NetworkCallRecord).where(m.NetworkCallRecord.id.in_(call_ids)))).scalars().all()} if call_ids else {}
    step_ids = [l.ref_id for l in links if l.kind == "decision"]
    decisions = (await session.execute(
        select(m.Decision).where(m.Decision.step_id.in_(step_ids)))).scalars().all() if step_ids else []
    trace_ids = [l.ref_id for l in links if l.kind == "span"]
    spans = []
    if trace_ids:
        for sp in (await session.execute(select(m.SpanRecord).where(m.SpanRecord.trace_id.in_(trace_ids)))).scalars():
            if (sp.attributes or {}).get("step_seq") in (finding.step_seq, None):
                spans.append(sp)

    items: List[Dict[str, Any]] = []
    for l in links:
        entry: Dict[str, Any] = {"id": l.id, "kind": l.kind, "ref_id": l.ref_id, "note": l.note}
        if l.kind in ARTIFACT_KINDS:
            art = artifacts.get(l.ref_id)
            entry["artifact_id"] = art.id if art else None
            entry["available"] = art is not None
            entry["url"] = f"/api/artifacts/{art.id}/url" if art else None
        elif l.kind == "network_call" and l.ref_id in calls:
            c = calls[l.ref_id]
            entry["call"] = {"id": c.id, "method": c.method, "url": c.url, "status": c.status,
                             "duration_ms": c.duration_ms, "is_api": c.is_api, "traceparent": c.traceparent}
        items.append(entry)

    return {
        "finding": {
            "id": finding.id, "run_id": finding.run_id, "flow_run_id": finding.flow_run_id,
            "step_seq": finding.step_seq, "severity": finding.severity, "kind": finding.kind,
            "title": finding.title, "expected": finding.expected, "actual": finding.actual,
            "check_key": finding.check_key, "requirement_keys": finding.requirement_keys or [],
            "fingerprint": finding.fingerprint, "issue_id": finding.issue_id, "judged_by": finding.judged_by,
        },
        "check_result": ({"id": check.id, "check_key": check.check_key, "kind": check.kind, "passed": check.passed,
                          "expected": check.expected, "actual": check.actual, "inputs": check.inputs,
                          "judged_by": check.judged_by, "confidence": check.confidence} if check else None),
        "evidence": items,
        "decisions": [{"step_id": d.step_id, "decider": d.decider, "choice": d.choice, "confidence": d.confidence,
                       "branch": d.branch, "few_shot_ids": d.few_shot_ids or []} for d in decisions],
        "spans": [{"span_id": s.span_id, "name": s.name, "kind": s.kind, "parent_span_id": s.parent_span_id,
                   "start_ns": s.start_ns, "end_ns": s.end_ns} for s in spans],
        "integrity": {"run_id": run.id if run else None,
                      "playbook_version_id": run.playbook_version_id if run else None},
    }
