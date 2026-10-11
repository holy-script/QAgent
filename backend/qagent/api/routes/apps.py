from typing import List, Optional
from fastapi import APIRouter, HTTPException
from qagent.domain.schemas import CreateAppRequest, AppResponse, RunMode

router = APIRouter(prefix="/apps", tags=["Apps"])

# In-memory fixture registry for B0 contract freezing
_MOCK_APPS = [
    {
        "id": "app-demo-shop-001",
        "slug": "demo-shop",
        "name": "Demo E-Commerce Shop",
        "base_url": "http://localhost:8001",
        "allowed_hosts": ["localhost", "127.0.0.1"],
        "description": "Target test application with 5 simulated e-commerce defects",
        "prd_markdown": "# Demo Shop PRD\nCheckout flow testing requirements.",
        "default_mode": RunMode.HYBRID,
        "created_at": "2026-10-11T12:00:00Z",
    }
]


@router.get("", response_model=List[AppResponse])
async def list_apps():
    return _MOCK_APPS


@router.post("", response_model=AppResponse)
async def create_app(payload: CreateAppRequest):
    new_app = {
        "id": f"app-{payload.slug}",
        "slug": payload.slug,
        "name": payload.name,
        "base_url": payload.base_url,
        "allowed_hosts": payload.allowed_hosts,
        "description": payload.description,
        "prd_markdown": payload.prd_markdown,
        "default_mode": payload.default_mode,
        "created_at": "2026-10-11T12:00:00Z",
    }
    _MOCK_APPS.append(new_app)
    return new_app


@router.get("/{slug}", response_model=AppResponse)
async def get_app(slug: str):
    for a in _MOCK_APPS:
        if a["slug"] == slug or a["id"] == slug:
            return a
    raise HTTPException(status_code=404, detail="App not found")
