from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.api.deps import get_session
from qagent.domain import models as m
from qagent.domain.schemas import TraceabilityResponse

router = APIRouter(tags=["Traceability"])


@router.get("/apps/{app_id}/traceability", response_model=TraceabilityResponse)
async def traceability(app_id: str, version_id: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    """
    Requirements -> the flows, formulas, UX rules and edge cases that cover them -> their latest check results
    -> findings -> issues. Built from the stored item links and the most recent run of the version.
    """
    app = (await session.execute(select(m.App).where((m.App.id == app_id) | (m.App.slug == app_id)))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    if version_id is None:
        pb = (await session.execute(
            select(m.Playbook).where(m.Playbook.app_id == app.id, m.Playbook.current_version_id.is_not(None))
        )).scalars().first()
        if pb is None:
            raise HTTPException(status_code=404, detail="App has no playbook")
        version_id = pb.current_version_id
    version = await session.get(m.PlaybookVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Playbook version not found")

    items = {i.item_key: i for i in (await session.execute(
        select(m.PlaybookItem).where(m.PlaybookItem.version_id == version_id))).scalars().all()}
    links = (await session.execute(select(m.ItemLink).where(m.ItemLink.version_id == version_id))).scalars().all()

    run = (await session.execute(
        select(m.Run).where(m.Run.app_id == app.id, m.Run.playbook_version_id == version_id,
                            m.Run.status.in_(["passed", "failed"])).order_by(m.Run.started_at.desc().nullslast())
    )).scalars().first()
    flow_runs = (await session.execute(select(m.FlowRun).where(m.FlowRun.run_id == run.id))).scalars().all() if run else []
    checks = (await session.execute(select(m.CheckResult).where(m.CheckResult.run_id == run.id))).scalars().all() if run else []
    findings = (await session.execute(select(m.FindingRecord).where(m.FindingRecord.run_id == run.id))).scalars().all() if run else []

    def result_for(key: str) -> Optional[Dict[str, Any]]:
        rows = [c for c in checks if c.check_key == key]
        if rows:
            return {"passed": all(c.passed for c in rows), "check_result_ids": [c.id for c in rows]}
        flows = [f for f in flow_runs if f.flow_key.split("#")[0] == key or f.flow_key == key]
        if flows:
            return {"passed": all(f.status != "failed" for f in flows), "flow_run_ids": [f.id for f in flows]}
        return None

    def linked_to(req: str) -> Dict[str, str]:
        """item key -> relation, including the checks of flows/edge cases that cover the requirement."""
        out = {l.from_key: l.relation for l in links if l.to_key == req and l.relation in ("covers", "verifies")}
        for key in list(out):
            for l in links:
                if l.from_key == key and l.relation == "checks":
                    out.setdefault(l.to_key, "checks")
        return out

    rows: List[Dict[str, Any]] = []
    for key, item in sorted(items.items()):
        if item.category != "requirement":
            continue
        linked = linked_to(key)
        direct = {k: r for k, r in linked.items() if r in ("covers", "verifies")}
        req_findings = [f for f in findings if key in (f.requirement_keys or [])]
        item_rows = []
        for k, rel in linked.items():
            it = items.get(k)
            item_rows.append({"key": k, "category": it.category if it else "flow", "title": it.title if it else k,
                              "relation": rel, "latest_result": result_for(k)})
        if not direct:
            status = "uncovered"
        elif req_findings:
            status = "covered_failing"
        elif any(r["latest_result"] for r in item_rows):
            status = "covered_passing"
        else:
            status = "not_run"
        rows.append({"key": key, "title": item.title, "priority": item.body.get("priority"),
                     "prd_ref": item.body.get("prd_ref"), "acceptance": item.body.get("acceptance"),
                     "status": status, "items": item_rows, "finding_ids": [f.id for f in req_findings],
                     "issue_ids": sorted({f.issue_id for f in req_findings if f.issue_id})})
    return TraceabilityResponse(
        version_id=version_id, playbook_id=version.playbook_id, latest_run_id=run.id if run else None,
        requirements=rows, uncovered=[r["key"] for r in rows if r["status"] == "uncovered"])
