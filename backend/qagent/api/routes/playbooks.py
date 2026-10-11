from typing import List, Optional
from fastapi import APIRouter, HTTPException
from qagent.domain.schemas import PlaybookResponse

router = APIRouter(prefix="/playbooks", tags=["Playbooks"])

_MOCK_PLAYBOOKS = [
    {
        "id": "pb-checkout-001",
        "app_id": "app-demo-shop-001",
        "name": "Checkout Flow Playbook",
        "current_version_id": "pb-ver-001",
        "status": "confirmed",
        "flows": [
            {
                "key": "add-to-cart",
                "severity": "high",
                "steps": [
                    "Open /products",
                    "Add 2 items to cart",
                    "Go to /cart"
                ],
                "expect": [
                    "Cart shows 2 items",
                    "Total is visible"
                ],
                "formulas": {
                    "cart_total": "total == round(sum(i.price * i.qty for i in items) * (1 + tax_rate), 2)"
                }
            }
        ]
    }
]


@router.get("", response_model=List[PlaybookResponse])
async def list_playbooks(app_id: Optional[str] = None):
    if app_id:
        return [p for p in _MOCK_PLAYBOOKS if p["app_id"] == app_id]
    return _MOCK_PLAYBOOKS


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(playbook_id: str):
    for p in _MOCK_PLAYBOOKS:
        if p["id"] == playbook_id:
            return p
    raise HTTPException(status_code=404, detail="Playbook not found")
