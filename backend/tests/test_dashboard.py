from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from qagent.api.seed import DEMO_APP_ID
from qagent.domain import models as m
from test_lifecycle import api  # noqa: F401  (fixture)

NOW = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_dashboard_aggregates_runs_bugs_and_cost(api: AsyncClient):  # noqa: F811
    async with api.sessions() as s:
        app = await s.get(m.App, DEMO_APP_ID)
        other = m.App(slug="other", name="Other", base_url="http://x")
        s.add(other)
        await s.flush()
        for app_id, status, age, cost, findings in [
            (app.id, "passed", 1, 0.02, 0), (app.id, "failed", 1, 0.04, 3), (app.id, "failed", 3, 0.03, 2),
            (other.id, "passed", 2, 0.01, 0), (other.id, "passed", 90, 9.0, 0),  # outside the 30 days
            (other.id, "running", 0, 0, 0)]:
            s.add(m.Run(app_id=app_id, status=status, started_at=NOW - timedelta(days=age, hours=1),
                        totals={"total_cost_usd": cost, "findings_count": findings, "duration_ms": 4000}))
        s.add(m.Issue(app_id=app.id, fingerprint="a", title="Server error", severity="critical", status="open", occurrences=3))
        s.add(m.Issue(app_id=app.id, fingerprint="b", title="Old", severity="low", status="resolved"))
        s.add(m.Issue(app_id=other.id, fingerprint="c", title="Cart badge", severity="medium", status="regressed"))
        await s.commit()

    d = (await api.get("/dashboard?days=30")).json()
    assert d["days"] == 30 and d["apps"] >= 2
    assert (d["runs"], d["passed"], d["failed"], d["running"]) == (5, 2, 2, 1)
    assert d["pass_rate"] == pytest.approx(0.5) and d["cost_usd"] == pytest.approx(0.10)
    assert d["avg_duration_ms"] == 4000 and d["open_bugs"] == 2
    assert d["bugs_by_severity"] == {"critical": 1, "medium": 1} and d["bugs_by_status"]["resolved"] == 1
    assert len(d["series"]) == 30 and sum(x["passed"] + x["failed"] for x in d["series"]) == 4
    assert sum(x["findings"] for x in d["series"]) == 5
    assert [b["severity"] for b in d["top_bugs"]] == ["critical", "medium"]            # worst first
    assert d["recent_runs"][0]["app_slug"] in ("other", "demo-shop") and len(d["recent_runs"]) <= 8
    mine = next(a for a in d["per_app"] if a["slug"] == app.slug)
    assert mine["runs"] == 3 and mine["open_bugs"] == 1 and mine["pass_rate"] == pytest.approx(1 / 3)
    assert (await api.get("/dashboard?days=0")).status_code == 422
