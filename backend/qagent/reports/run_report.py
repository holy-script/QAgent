from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.config import settings
from qagent.decision.claude import BedrockClient
from qagent.decision.fewshot import select_examples
from qagent.domain import models as m
from qagent.playbooks.coverage import requirement_coverage
from qagent.reports import narrative
from qagent.reports.grounding import ground_recommendations


def category_of(f: m.FindingRecord) -> str:
    key = f.check_key or ""
    if key.startswith("expect:"):
        return "functional"
    if key.startswith("F-") or f.kind == "formula":
        return "formula"
    if key.startswith("UX-") or f.kind == "dom":
        return "ux"
    if f.kind == "network":
        return "network"
    if f.kind == "timing":
        return "performance"
    return "functional"


async def build_run_report(session: AsyncSession, run: m.Run, issue_summary: Dict[str, List[str]],
                           manifest_hash: Optional[str], bug_reports: List[Dict[str, str]],
                           claude: Optional[BedrockClient] = None) -> Dict[str, Any]:
    version = await session.get(m.PlaybookVersion, run.playbook_version_id) if run.playbook_version_id else None
    parsed = version.parsed if version else {}
    flows = (await session.execute(select(m.FlowRun).where(m.FlowRun.run_id == run.id))).scalars().all()
    findings = (await session.execute(
        select(m.FindingRecord).where(m.FindingRecord.run_id == run.id))).scalars().all()
    checks = (await session.execute(select(m.CheckResult).where(m.CheckResult.run_id == run.id))).scalars().all()
    flow_ids = [f.id for f in flows]
    calls = (await session.execute(
        select(m.NetworkCallRecord).where(m.NetworkCallRecord.flow_run_id.in_(flow_ids)))).scalars().all() if flow_ids else []
    steps = (await session.execute(select(m.Step).where(m.Step.flow_run_id.in_(flow_ids)))).scalars().all() if flow_ids else []
    timings = {t.step_id: t for t in (await session.execute(select(m.StepTiming))).scalars().all()
               if t.step_id in {s.id for s in steps}}
    decisions = (await session.execute(
        select(m.Decision).where(m.Decision.step_id.in_([s.id for s in steps])))).scalars().all() if steps else []
    flow_key_of = {f.id: f.flow_key for f in flows}

    # requirements coverage
    coverage = requirement_coverage(parsed) if parsed else {"covered_by": {}, "uncovered": []}
    ran = {f.flow_key.split("#")[0] for f in flows} | {c.check_key for c in checks}
    requirements = []
    for r in parsed.get("requirements", []):
        covered_by = coverage["covered_by"].get(r["key"], [])
        failing = [f.id for f in findings if r["key"] in (f.requirement_keys or [])]
        if not covered_by:
            status = "not_covered"
        elif failing:
            status = "covered_failing"
        elif any(k in ran for k in covered_by):
            status = "covered_passing"
        else:
            status = "not_run"
        requirements.append({"key": r["key"], "title": r["title"], "priority": r.get("priority"),
                             "status": status, "covered_by": covered_by, "finding_ids": failing})

    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        by_category.setdefault(category_of(f), []).append(
            {"id": f.id, "title": f.title, "severity": f.severity, "flow": flow_key_of.get(f.flow_run_id),
             "step_seq": f.step_seq, "issue_id": f.issue_id, "requirement_keys": f.requirement_keys or [],
             "judged_by": f.judged_by})

    api_calls = sorted((c for c in calls if c.is_api), key=lambda c: -c.duration_ms)[:5]
    waits = sorted(((t.settle_ms, s) for s in steps if (t := timings.get(s.id))), key=lambda p: -p[0])[:5]
    low_conf = [{"step_id": d.step_id, "decider": d.decider, "confidence": d.confidence, "branch": d.branch}
                for d in decisions if d.confidence < settings.gate_auto_min]

    content: Dict[str, Any] = {
        "kind": "run",
        "run": {"id": run.id, "app_id": run.app_id, "status": run.status, "mode": run.mode, "trigger": run.trigger,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "totals": run.totals or {}, "environment": run.environment or {}},
        "integrity": {"run_id": run.id, "playbook_version_id": run.playbook_version_id,
                      "playbook_hash": version.content_hash if version else None, "manifest_hash": manifest_hash},
        "summary": {
            "flows": [{"flow_key": f.flow_key, "status": f.status, "step_count": f.step_count,
                       "duration_ms": f.duration_ms, "failure_reason": f.failure_reason,
                       "findings": len([x for x in findings if x.flow_run_id == f.id])} for f in flows],
            "issues": {k: len(v) for k, v in issue_summary.items()},
            "total_findings": len(findings),
            "duration_ms": (run.totals or {}).get("duration_ms", 0), "cost_usd": (run.totals or {}).get("total_cost_usd", 0),
        },
        "requirements": requirements,
        "findings_by_category": by_category,
        "performance": {
            "slowest_api_calls": [{"id": c.id, "method": c.method, "url": c.url, "duration_ms": round(c.duration_ms),
                                   "status": c.status} for c in api_calls],
            "longest_waits": [{"step_id": s.id, "flow": flow_key_of.get(s.flow_run_id), "step_seq": s.seq,
                               "settle_ms": round(ms)} for ms, s in waits],
        },
        "test_quality": {
            "escalations": len([d for d in decisions if d.branch == "escalated"]),
            "low_confidence_decisions": low_conf, "divergences": 0,
            "judged_findings": len([f for f in findings if f.judged_by != "code"]),
            "checks_run": len(checks),
        },
        "appendix": {"bug_reports": bug_reports, "manifest_hash": manifest_hash},
        "recommendations": [], "recommendations_status": "not generated", "recommendations_dropped": [],
    }

    if claude and findings:
        fact_pack = {
            "findings": [{"id": f.id, "title": f.title, "severity": f.severity, "kind": f.kind,
                          "check_key": f.check_key, "expected": f.expected, "actual": f.actual,
                          "requirement_keys": f.requirement_keys or []} for f in findings],
            "requirements": requirements, "performance": content["performance"],
            "gotchas": [{"key": g["key"], "note": g.get("note")} for g in parsed.get("gotchas", [])],
        }
        examples = select_examples(parsed.get("reasoning_examples", []), "report",
                                   " ".join(f.title for f in findings))
        try:
            got = await narrative.recommend(claude, fact_pack, examples)
            kept, dropped = ground_recommendations(
                got["recommendations"], [f.id for f in findings], [r["key"] for r in requirements])
            content.update({"recommendations": kept, "recommendations_dropped": dropped,
                            "recommendations_status": "generated", "few_shot_ids": got["few_shot_ids"]})
        except Exception as exc:
            content["recommendations_status"] = f"not generated ({type(exc).__name__})"
    return content
