from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from qagent.domain.models import App, Playbook, PlaybookVersion
from qagent.playbooks.parser import parse_playbook_markdown

PLAYBOOK_PATH = Path(__file__).parents[3] / "playbooks" / "checkout-flow.md"

# Ids match the B0 fixtures so the frontend's mock data stays valid after switching to the real API.
DEMO_APP_ID = "app-demo-shop-001"
DEMO_PLAYBOOK_ID = "pb-checkout-001"
DEMO_VERSION_ID = "pb-ver-001"


async def seed_demo(session: AsyncSession) -> None:
    """Registers the demo shop and its checkout playbook if they are not there yet."""
    if await session.get(App, DEMO_APP_ID) is None:
        session.add(App(
            id=DEMO_APP_ID, slug="demo-shop", name="Demo E-Commerce Shop", base_url="http://localhost:8001",
            allowed_hosts=["localhost", "127.0.0.1"],
            description="Target test application with 5 simulated e-commerce defects",
            prd_markdown="# Demo Shop PRD\nCheckout flow testing requirements.",
        ))
    if await session.get(Playbook, DEMO_PLAYBOOK_ID) is None and PLAYBOOK_PATH.exists():
        raw = PLAYBOOK_PATH.read_text(encoding="utf-8")
        parsed = parse_playbook_markdown(raw)
        session.add(Playbook(
            id=DEMO_PLAYBOOK_ID, app_id=DEMO_APP_ID, name="Checkout Flow Playbook",
            current_version_id=DEMO_VERSION_ID,
        ))
        session.add(PlaybookVersion(
            id=DEMO_VERSION_ID, playbook_id=DEMO_PLAYBOOK_ID, version_no=1, raw_markdown=raw, parsed=parsed,
            warnings=parsed["warnings"], content_hash=parsed["content_hash"],
        ))
    await session.commit()
