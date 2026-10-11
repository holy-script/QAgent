from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.checks.base import SEVERITY_ORDER, max_severity
from qagent.domain.models import FindingRecord, FlowRun, Issue, Run


async def sync_issues(session: AsyncSession, run: Run) -> Dict[str, List[str]]:
    """
    Attaches this run's findings to issues (by fingerprint) and updates issue state:
      new fingerprint            -> new open issue
      known fingerprint          -> occurrence recorded; a resolved issue becomes regressed
      open issue, flow ran clean -> resolved (its flow ran in this run without reproducing it)
    """
    now = datetime.now(timezone.utc)
    flow_runs = (await session.execute(select(FlowRun).where(FlowRun.run_id == run.id))).scalars().all()
    findings = (await session.execute(
        select(FindingRecord).where(FindingRecord.run_id == run.id).order_by(FindingRecord.step_seq)
    )).scalars().all()
    flow_key_by_run = {f.id: f.flow_key for f in flow_runs}

    summary: Dict[str, List[str]] = {"new": [], "recurring": [], "regressed": [], "resolved": []}
    seen: set = set()
    by_fp: Dict[str, List[FindingRecord]] = {}
    for f in findings:
        if f.fingerprint:
            by_fp.setdefault(f.fingerprint, []).append(f)

    for fp, group in by_fp.items():
        first = group[0]
        severity = max_severity(*[g.severity for g in group])
        flow_key = flow_key_by_run.get(first.flow_run_id, "").split("#", 1)[0]
        issue = (await session.execute(
            select(Issue).where(Issue.app_id == run.app_id, Issue.fingerprint == fp))).scalar_one_or_none()
        if issue is None:
            issue = Issue(
                app_id=run.app_id, fingerprint=fp, title=first.title, severity=severity, kind=first.kind,
                check_key=first.check_key, flow_key=flow_key, requirement_keys=first.requirement_keys or [],
                first_seen_run_id=run.id, last_seen_run_id=run.id,
            )
            session.add(issue)
            await session.flush()
            summary["new"].append(issue.id)
        else:
            if issue.last_seen_run_id != run.id:
                issue.occurrences += 1
            if issue.status == "resolved":
                issue.status = "regressed"
                summary["regressed"].append(issue.id)
            else:
                summary["recurring"].append(issue.id)
            issue.last_seen_run_id = run.id
            if SEVERITY_ORDER.index(severity) > SEVERITY_ORDER.index(issue.severity):
                issue.severity = severity
            issue.updated_at = now
        seen.add(fp)
        for g in group:
            g.issue_id = issue.id

    clean_flows = {f.flow_key.split("#", 1)[0] for f in flow_runs if f.status != "failed"}
    open_issues = (await session.execute(
        select(Issue).where(Issue.app_id == run.app_id, Issue.status.in_(["open", "regressed"])))).scalars().all()
    for issue in open_issues:
        if issue.fingerprint not in seen and issue.flow_key in clean_flows:
            issue.status = "resolved"
            issue.last_pass_run_id = run.id
            issue.updated_at = now
            summary["resolved"].append(issue.id)
    await session.flush()
    return summary
