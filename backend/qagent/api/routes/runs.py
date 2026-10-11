from typing import List, Optional
from fastapi import APIRouter, HTTPException
from qagent.domain.schemas import CreateRunRequest, RunResponse, FlowRunResponse, RunTotals, RunMode

router = APIRouter(prefix="/runs", tags=["Runs"])

_MOCK_RUNS = [
    {
        "id": "run-demo-001",
        "app_id": "app-demo-shop-001",
        "playbook_version_id": "pb-ver-001",
        "mode": RunMode.HYBRID,
        "status": "completed",
        "trigger": "manual",
        "started_at": "2026-10-11T12:00:00Z",
        "finished_at": "2026-10-11T12:00:05Z",
        "totals": RunTotals(
            total_steps=3,
            duration_ms=4500.0,
            jev_decisions=2,
            claude_decisions=0,
            total_cost_usd=0.0008,
            avg_decision_latency_ms=325.35,
            findings_count=1,
            status="completed",
        )
    }
]


@router.get("", response_model=List[RunResponse])
async def list_runs(app_id: Optional[str] = None):
    if app_id:
        return [r for r in _MOCK_RUNS if r["app_id"] == app_id]
    return _MOCK_RUNS


@router.post("", response_model=RunResponse)
async def create_run(payload: CreateRunRequest):
    new_run = {
        "id": f"run-{len(_MOCK_RUNS) + 1:03d}",
        "app_id": payload.app_id,
        "playbook_version_id": payload.playbook_version_id,
        "mode": payload.mode,
        "status": "pending",
        "trigger": payload.trigger,
        "started_at": "2026-10-11T12:05:00Z",
        "finished_at": None,
        "totals": RunTotals(),
    }
    _MOCK_RUNS.append(new_run)
    return new_run


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    for r in _MOCK_RUNS:
        if r["id"] == run_id:
            return r
    raise HTTPException(status_code=404, detail="Run not found")


@router.post("/{run_id}/stop", response_model=RunResponse)
async def stop_run(run_id: str):
    for r in _MOCK_RUNS:
        if r["id"] == run_id:
            r["status"] = "stopped"
            return r
    raise HTTPException(status_code=404, detail="Run not found")
