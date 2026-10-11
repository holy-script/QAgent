from fastapi import APIRouter

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.get("/{run_id}/steps/{step_seq}/screenshot.jpg")
async def get_mock_screenshot(run_id: str, step_seq: int):
    # For fixture routes, returns a 1x1 placeholder SVG/JPEG or mock metadata
    return {"run_id": run_id, "step_seq": step_seq, "kind": "screenshot"}
