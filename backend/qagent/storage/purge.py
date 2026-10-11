"""Deleting runs and apps together with everything they own (rows and stored files)."""
from collections import Counter
from typing import Dict, List

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain import models as m


async def _ids(session: AsyncSession, stmt) -> List[str]:
    return list((await session.execute(stmt)).scalars().all())


async def purge_runs(session: AsyncSession, run_ids: List[str]) -> Dict[str, int]:
    """Deletes runs and every row hanging off them. Does not touch object storage or issues."""
    counts: Counter = Counter()
    if not run_ids:
        return dict(counts)
    flow_ids = await _ids(session, select(m.FlowRun.id).where(m.FlowRun.run_id.in_(run_ids)))
    step_ids = await _ids(session, select(m.Step.id).where(m.Step.flow_run_id.in_(flow_ids))) if flow_ids else []
    finding_ids = await _ids(session, select(m.FindingRecord.id).where(m.FindingRecord.run_id.in_(run_ids)))
    if flow_ids:
        finding_ids += await _ids(session, select(m.FindingRecord.id).where(m.FindingRecord.flow_run_id.in_(flow_ids)))
    report_ids = await _ids(session, select(m.Report.id).where(m.Report.run_id.in_(run_ids)))

    async def rm(model, label, cond) -> None:
        res = await session.execute(delete(model).where(cond))
        counts[label] += res.rowcount or 0

    if finding_ids:
        await rm(m.EvidenceLink, "evidence_links", m.EvidenceLink.finding_id.in_(set(finding_ids)))
    if report_ids:
        await rm(m.Recommendation, "recommendations", m.Recommendation.report_id.in_(report_ids))
    await rm(m.Report, "reports", m.Report.run_id.in_(run_ids))
    await rm(m.FindingRecord, "findings", m.FindingRecord.run_id.in_(run_ids))
    if flow_ids:
        await rm(m.FindingRecord, "findings", m.FindingRecord.flow_run_id.in_(flow_ids))
        await rm(m.NetworkCallRecord, "network_calls", m.NetworkCallRecord.flow_run_id.in_(flow_ids))
    if step_ids:
        await rm(m.StepTiming, "step_timings", m.StepTiming.step_id.in_(step_ids))
        await rm(m.Decision, "decisions", m.Decision.step_id.in_(step_ids))
        await rm(m.Step, "steps", m.Step.id.in_(step_ids))
    await rm(m.CheckResult, "check_results", m.CheckResult.run_id.in_(run_ids))
    await rm(m.Artifact, "artifacts", m.Artifact.run_id.in_(run_ids))
    await rm(m.SpanRecord, "spans", m.SpanRecord.run_id.in_(run_ids))
    await rm(m.LogEntryRecord, "log_entries", m.LogEntryRecord.run_id.in_(run_ids))
    await rm(m.EventRecord, "events", m.EventRecord.run_id.in_(run_ids))
    if flow_ids:
        await rm(m.FlowRun, "flow_runs", m.FlowRun.id.in_(flow_ids))
    await rm(m.Run, "runs", m.Run.id.in_(run_ids))
    return dict(counts)


async def refresh_issues(session: AsyncSession, app_id: str) -> int:
    """After runs are removed: recount each issue from the findings that remain; drop issues with none."""
    removed = 0
    for issue in (await session.execute(select(m.Issue).where(m.Issue.app_id == app_id))).scalars().all():
        runs = await _ids(session, select(m.FindingRecord.run_id).where(m.FindingRecord.issue_id == issue.id))
        distinct = sorted({r for r in runs if r})
        if not distinct:
            await session.delete(issue)
            removed += 1
            continue
        ordered = (await session.execute(
            select(m.Run).where(m.Run.id.in_(distinct)).order_by(m.Run.started_at))).scalars().all()
        issue.occurrences = len(distinct)
        issue.first_seen_run_id = ordered[0].id if ordered else distinct[0]
        issue.last_seen_run_id = ordered[-1].id if ordered else distinct[-1]
    return removed


async def purge_run(session: AsyncSession, run_id: str) -> Dict[str, int]:
    run = await session.get(m.Run, run_id)
    counts = await purge_runs(session, [run_id])
    if run is not None:
        counts["issues_removed"] = await refresh_issues(session, run.app_id)
    return counts


async def purge_app(session: AsyncSession, app_id: str) -> Dict[str, int]:
    """Deletes an app, its runs, playbooks (versions, items, links) and issues."""
    run_ids = await _ids(session, select(m.Run.id).where(m.Run.app_id == app_id))
    counts = Counter(await purge_runs(session, run_ids))
    pb_ids = await _ids(session, select(m.Playbook.id).where(m.Playbook.app_id == app_id))
    version_ids = await _ids(session, select(m.PlaybookVersion.id).where(m.PlaybookVersion.playbook_id.in_(pb_ids))) if pb_ids else []

    async def rm(model, label, cond) -> None:
        res = await session.execute(delete(model).where(cond))
        counts[label] += res.rowcount or 0

    if version_ids:
        await rm(m.ItemLink, "item_links", m.ItemLink.version_id.in_(version_ids))
        await rm(m.PlaybookItem, "playbook_items", m.PlaybookItem.version_id.in_(version_ids))
        await rm(m.PlaybookVersion, "playbook_versions", m.PlaybookVersion.id.in_(version_ids))
    if pb_ids:
        await rm(m.Playbook, "playbooks", m.Playbook.id.in_(pb_ids))
    await rm(m.Report, "reports", m.Report.app_id == app_id)
    await rm(m.Issue, "issues", m.Issue.app_id == app_id)
    await rm(m.App, "apps", m.App.id == app_id)
    return dict(counts)
