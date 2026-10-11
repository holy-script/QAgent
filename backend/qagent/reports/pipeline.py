import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from qagent.config import settings
from qagent.decision.claude import BedrockClient
from qagent.decision.ledger import LedgerClient
from qagent.domain import models as m
from qagent.domain.events import QAgentEventType
from qagent.domain.schemas import RunMode
from qagent.engine.tracing import logger
from qagent.reports.annotate import annotate_screenshot, find_bbox
from qagent.reports.bug_report import build_bug_report
from qagent.reports.issues import sync_issues
from qagent.reports.render import render
from qagent.reports.run_report import build_run_report
from qagent.storage.objects import object_store


def _default_claude(mode: str) -> Optional[BedrockClient]:
    return BedrockClient() if settings.bedrock_api_key and mode != RunMode.STUB.value else None


def _add_artifact(session: AsyncSession, run: m.Run, key: str, data: bytes, content_type: str, kind: str,
                  flow_run_id: Optional[str] = None, step_seq: Optional[int] = None) -> m.Artifact:
    object_store.put_object(key, data, content_type)
    art = m.Artifact(run_id=run.id, flow_run_id=flow_run_id, step_seq=step_seq, kind=kind, object_key=key,
                     content_type=content_type, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    session.add(art)
    return art


async def annotate_findings(session: AsyncSession, run: m.Run) -> int:
    """Writes annotated.jpg for every step with a finding and links it as evidence."""
    findings = (await session.execute(select(m.FindingRecord).where(m.FindingRecord.run_id == run.id))).scalars().all()
    made: Dict[str, bool] = {}
    count = 0
    for f in findings:
        links = (await session.execute(select(m.EvidenceLink).where(m.EvidenceLink.finding_id == f.id))).scalars().all()
        after = next((l for l in links if l.kind == "screenshot_after"), None)
        if after is None:
            continue
        key = after.ref_id.replace("/after.jpg", "/annotated.jpg")
        if key not in made:
            jpeg = object_store.get_bytes(after.ref_id)
            if not jpeg:
                continue
            check = await session.get(m.CheckResult, f.check_result_id) if f.check_result_id else None
            step = (await session.execute(select(m.Step).where(
                m.Step.flow_run_id == f.flow_run_id, m.Step.seq == f.step_seq))).scalars().first()
            bbox = find_bbox((check.inputs if check else {}) or {}, step.target_bbox if step else None)
            _add_artifact(session, run, key, annotate_screenshot(jpeg, f.step_seq, bbox), "image/jpeg",
                          "annotated", f.flow_run_id, f.step_seq)
            made[key] = True
            count += 1
        if key in made:
            session.add(m.EvidenceLink(finding_id=f.id, kind="annotated", ref_id=key, note="target boxed"))
    await session.flush()
    return count


async def write_manifest(session: AsyncSession, run: m.Run) -> str:
    """manifest.json lists every artifact of the run with its sha256; its own hash goes into the reports."""
    arts = (await session.execute(select(m.Artifact).where(m.Artifact.run_id == run.id))).scalars().all()
    entries = sorted(({"key": a.object_key, "kind": a.kind, "size_bytes": a.size_bytes, "sha256": a.sha256}
                      for a in arts if a.kind != "manifest"), key=lambda e: e["key"])
    body = json.dumps({"run_id": run.id, "artifacts": entries}, indent=2, sort_keys=True).encode()
    key = f"apps/{run.app_id}/runs/{run.id}/manifest.json"
    old = (await session.execute(select(m.Artifact).where(m.Artifact.object_key == key))).scalars().all()
    for o in old:
        await session.delete(o)
    _add_artifact(session, run, key, body, "application/json", "manifest")
    await session.flush()
    return hashlib.sha256(body).hexdigest()


def _store_report(session: AsyncSession, run: m.Run, report: m.Report, content: Dict[str, Any], stem: str) -> None:
    base = f"apps/{run.app_id}/runs/{run.id}/reports/{stem}"
    md = render(content["kind"], content, "md").encode()
    html = render(content["kind"], content, "html").encode()
    report.markdown_artifact_id = _add_artifact(session, run, f"{base}.md", md, "text/markdown", "report_md").id
    report.html_artifact_id = _add_artifact(session, run, f"{base}.html", html, "text/html", "report_html").id


REPORT_PURPOSES = ("report", "bug_narrative")


async def _with_ledger(session: AsyncSession, session_factory, run: m.Run,
                       claude: Optional[BedrockClient]) -> Optional[LedgerClient]:
    """Wraps Claude so every report call is recorded (and costed). A replayed run serves the source run's answers."""
    if claude is None:
        return None
    # Regenerating replaces the earlier report calls of this run.
    await session.execute(delete(m.ModelCall).where(m.ModelCall.run_id == run.id, m.ModelCall.purpose.in_(REPORT_PURPOSES)))
    await session.commit()
    tape = None
    if run.replay_of_run_id:
        rows = (await session.execute(select(m.ModelCall).where(
            m.ModelCall.run_id == run.replay_of_run_id, m.ModelCall.purpose.in_(REPORT_PURPOSES)))).scalars().all()
        tape = {c.input_hash: c.response for c in rows if c.input_hash and c.response and not c.replayed}

    async def record(call: Dict[str, Any]) -> None:
        async with session_factory() as s:
            s.add(m.ModelCall(run_id=run.id, **call))
            await s.commit()

    return LedgerClient(claude, record, tape)


async def _roll_up_report_cost(session_factory, run_id: str) -> None:
    """Adds what the report calls cost to the run's total (kept separate so regenerating never double counts)."""
    async with session_factory() as session:
        run = await session.get(m.Run, run_id)
        calls = (await session.execute(select(m.ModelCall).where(
            m.ModelCall.run_id == run_id, m.ModelCall.purpose.in_(REPORT_PURPOSES)))).scalars().all()
        if run is None:
            return
        totals = dict(run.totals or {})
        base = totals.get("agent_cost_usd", totals.get("total_cost_usd", 0.0))
        cost = sum(c.cost_usd for c in calls)
        totals.update(agent_cost_usd=base, report_calls=len(calls), report_cost_usd=cost, total_cost_usd=base + cost)
        run.totals = totals
        await session.commit()


async def generate_reports(session_factory: Callable[[], AsyncSession], run_id: str,
                           claude: Optional[BedrockClient] = None,
                           on_report: Optional[Callable[[Dict[str, str]], Any]] = None) -> Dict[str, Any]:
    """
    Issues -> annotated screenshots -> manifest -> bug reports -> run report. Reads only stored facts;
    Claude (if given) adds narrative and recommendations on top. Safe to call again: earlier reports
    for the run are replaced.
    """
    async with session_factory() as session:
        run = await session.get(m.Run, run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        claude = await _with_ledger(session, session_factory, run, claude)
        summary = await sync_issues(session, run)
        await session.commit()
        annotated = await annotate_findings(session, run)
        manifest_hash = await write_manifest(session, run)

        old = (await session.execute(select(m.Report).where(m.Report.run_id == run_id))).scalars().all()
        for r in old:
            await session.execute(delete(m.Recommendation).where(m.Recommendation.report_id == r.id))
            await session.delete(r)
        await session.flush()

        issue_ids = {f.issue_id for f in (await session.execute(
            select(m.FindingRecord).where(m.FindingRecord.run_id == run_id))).scalars() if f.issue_id}
        bug_refs: List[Dict[str, str]] = []
        for issue_id in sorted(issue_ids):
            issue = await session.get(m.Issue, issue_id)
            content = await build_bug_report(session, issue, claude)
            report = m.Report(app_id=run.app_id, run_id=run_id, kind="bug", issue_id=issue_id, status="ready",
                              content=content, generated_at=datetime.now(timezone.utc),
                              model_version=claude.model_id if claude else None)
            session.add(report)
            await session.flush()
            _store_report(session, run, report, content, f"issues/{issue_id}")
            bug_refs.append({"issue_id": issue_id, "report_id": report.id})

        content = await build_run_report(session, run, summary, manifest_hash, bug_refs, claude)
        run_report = m.Report(app_id=run.app_id, run_id=run_id, kind="run", status="ready", content=content,
                              generated_at=datetime.now(timezone.utc),
                              model_version=claude.model_id if claude else None)
        session.add(run_report)
        await session.flush()
        for rec in content["recommendations"]:
            session.add(m.Recommendation(
                report_id=run_report.id, category=rec["category"], text=rec["text"], rationale=rec.get("rationale", ""),
                evidence_finding_ids=rec.get("evidence_finding_ids", []), requirement_keys=rec.get("requirement_keys", []),
                confidence=rec.get("confidence", "medium"), effort=rec.get("effort", "m")))
        _store_report(session, run, run_report, content, "run")
        await session.commit()
        await _roll_up_report_cost(session_factory, run_id)
        run_report_id = run_report.id
    if on_report:  # events are emitted after the transaction closes, never while it holds locks
        for ref in bug_refs:
            await on_report(ref)
    return {"run_report_id": run_report_id, "bug_reports": bug_refs, "issues": summary,
            "annotated": annotated, "manifest_hash": manifest_hash}


async def run_report_pipeline(session_factory, sink, spec, uploader) -> None:
    """Runs after a run finishes: waits for uploads, generates reports, emits report.* events."""
    await sink.emit(QAgentEventType.REPORT_GENERATING, {"kind": "run", "run_id": spec.run_id})
    try:
        await sink.flush()  # findings, checks and evidence links are read back from the database
        if hasattr(uploader, "drain"):
            await uploader.drain()

        async def on_report(ref: Dict[str, str]) -> None:
            await sink.emit(QAgentEventType.REPORT_READY, {"kind": "bug", "report_id": ref["report_id"],
                                                           "issue_id": ref["issue_id"]})

        result = await generate_reports(session_factory, spec.run_id, _default_claude(spec.mode.value), on_report)
        await sink.emit(QAgentEventType.REPORT_READY, {"kind": "run", "report_id": result["run_report_id"],
                                                       "issues": {k: len(v) for k, v in result["issues"].items()}})
    except Exception as exc:
        logger.error("report.failed", run_id=spec.run_id, error=type(exc).__name__, detail=str(exc)[:200])
        await sink.emit(QAgentEventType.REPORT_FAILED, {"kind": "run", "run_id": spec.run_id,
                                                        "message": f"{type(exc).__name__}: {str(exc)[:200]}"})
