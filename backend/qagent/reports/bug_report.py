from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.decision.claude import BedrockClient
from qagent.domain import models as m
from qagent.reports import narrative
from qagent.reports.evidence import evidence_graph, excerpt
from qagent.reports.repro import steps_to_reproduce

LAST_RUNS = 10


async def build_bug_report(session: AsyncSession, issue: m.Issue, claude: Optional[BedrockClient] = None) -> Dict[str, Any]:
    """
    Everything except the narrative is assembled by code from stored facts: the latest finding of the issue,
    its check result, evidence links, the recorded steps, and the pinned playbook version.
    """
    finding = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.issue_id == issue.id)
        .order_by(m.FindingRecord.run_id.desc()))).scalars().first()
    # the latest occurrence is the one in the issue's last_seen run
    occurrences = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.issue_id == issue.id))).scalars().all()
    finding = next((f for f in occurrences if f.run_id == issue.last_seen_run_id), finding)
    if finding is None:
        return {"kind": "bug", "issue_id": issue.id, "title": issue.title, "status": issue.status,
                "severity": issue.severity, "error": "no findings recorded for this issue"}

    run = await session.get(m.Run, finding.run_id)
    app = await session.get(m.App, issue.app_id)
    version = await session.get(m.PlaybookVersion, run.playbook_version_id) if run and run.playbook_version_id else None
    parsed = version.parsed if version else {}
    flow_run = await session.get(m.FlowRun, finding.flow_run_id)
    graph = await evidence_graph(session, finding.id) or {}
    check = graph.get("check_result") or {}

    reqs = {r["key"]: r for r in parsed.get("requirements", [])}
    violated = [{"key": k, **{f: reqs[k].get(f) for f in ("title", "prd_ref", "acceptance", "priority")}}
                for k in (finding.requirement_keys or []) if k in reqs]

    steps = (await session.execute(select(m.Step).where(m.Step.flow_run_id == finding.flow_run_id))).scalars().all()
    flow_spec = next((f for f in parsed.get("flows", []) if f["key"] == (flow_run.flow_key.split("#")[0] if flow_run else "")), {})
    test_data = dict(flow_spec.get("test_data", {}))
    if flow_run and flow_run.variant_of:
        ec = next((e for e in parsed.get("edge_cases", []) if e["key"] == flow_run.flow_key.split("#")[-1]), {})
        test_data.update(ec.get("test_data", {}))

    inputs = [{"name": name, **{k: v for k, v in src.items() if k != "bbox"}} if isinstance(src, dict)
              else {"name": name, "value": src} for name, src in (check.get("inputs") or {}).items()]

    ev_items = graph.get("evidence", [])
    network = []
    for e in ev_items:
        if e["kind"] == "network_call" and e.get("call"):
            body_key = None
            network.append({**e["call"], "evidence_id": e["id"], "response_excerpt": body_key})
    # response excerpts live under the flow's network/ prefix
    flow_key = flow_run.flow_key if flow_run else ""
    for c in network:
        c["response_excerpt"] = excerpt(
            f"apps/{issue.app_id}/runs/{finding.run_id}/flows/{flow_key}/network/{c['id']}/response.json")

    recent = (await session.execute(
        select(m.Run).where(m.Run.app_id == issue.app_id).order_by(m.Run.started_at.desc().nullslast())
        .limit(LAST_RUNS))).scalars().all()
    recent_ids = [r.id for r in recent]
    seen_runs = {f.run_id for f in occurrences if f.run_id in recent_ids}

    content: Dict[str, Any] = {
        "kind": "bug", "issue_id": issue.id, "finding_id": finding.id, "title": issue.title,
        "status": issue.status, "severity": issue.severity,
        "priority": max((v["priority"] for v in violated if v.get("priority")), default=issue.severity,
                        key=lambda p: ["info", "low", "medium", "high", "critical"].index(p)
                        if p in ["info", "low", "medium", "high", "critical"] else 0),
        "judged_by": finding.judged_by,
        "violated_requirements": violated,
        "environment": {
            "app_url": app.base_url if app else None, "run_id": run.id if run else None,
            "playbook_version_id": run.playbook_version_id if run else None,
            "playbook_hash": version.content_hash if version else None, **(run.environment if run else {}),
        },
        "steps_to_reproduce": steps_to_reproduce(steps, finding.step_seq, test_data),
        "expected_actual": {"check_key": finding.check_key, "expected": finding.expected, "actual": finding.actual,
                            "inputs": inputs},
        "evidence": {"items": ev_items, "network_calls": network, "step_seq": finding.step_seq,
                     "flow_key": flow_key, "run_link": f"/apps/{issue.app_id}/runs/{finding.run_id}"
                                                       f"?flow={flow_key}&step={finding.step_seq}"},
        "reproducibility": {"seen_in": len(seen_runs), "of_last": len(recent_ids),
                            "first_seen_run_id": issue.first_seen_run_id, "last_seen_run_id": issue.last_seen_run_id,
                            "occurrences": issue.occurrences},
        "integrity": graph.get("integrity", {}),
        "narrative": {"status": "not generated", "impact": None, "suspected_cause": None, "cited_evidence_ids": []},
    }

    if claude:
        valid_ids = {e["id"] for e in ev_items}
        try:
            facts = {"title": issue.title, "severity": issue.severity, "violated": violated,
                     "expected": finding.expected, "actual": finding.actual, "inputs": inputs,
                     "evidence": [{"id": e["id"], "kind": e["kind"], "note": e["note"]} for e in ev_items],
                     "network": [{k: c[k] for k in ("method", "url", "status")} for c in network]}
            got = await narrative.bug_narrative(claude, facts)
            cited = list(got.get("cited_evidence_ids", []))
            if cited and all(c in valid_ids for c in cited):  # drop narratives that cite evidence that isn't there
                content["narrative"] = {"status": "generated", "impact": got["impact"],
                                        "suspected_cause": got["suspected_cause"], "cited_evidence_ids": cited}
            else:
                content["narrative"]["status"] = "rejected: cited evidence ids do not exist"
        except Exception as exc:
            content["narrative"]["status"] = f"not generated ({type(exc).__name__})"
    return content
