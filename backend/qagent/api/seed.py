from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from qagent.domain.models import App, Playbook, PlaybookVersion
from qagent.playbooks.parser import parse_playbook_markdown
from qagent.playbooks.versioning import store_version

PLAYBOOK_PATH = Path(__file__).parents[3] / "playbooks" / "checkout.md"

# Ids match the B0 fixtures so the frontend's mock data stays valid after switching to the real API.
DEMO_APP_ID = "app-demo-shop-001"
DEMO_PLAYBOOK_ID = "pb-checkout-001"
DEMO_VERSION_ID = "pb-ver-001"


async def seed_demo(session: AsyncSession) -> None:
    """Registers the demo shop and its checkout playbook; a changed playbook file becomes a new version."""
    app = await session.get(App, DEMO_APP_ID)
    if app is None:
        session.add(App(
            id=DEMO_APP_ID, slug="demo-shop", name="Demo E-Commerce Shop", base_url="http://localhost:8001",
            allowed_hosts=["localhost", "127.0.0.1"], reset_path="/__reset",
            description="Target test application with 5 simulated e-commerce defects",
            prd_markdown="# Demo Shop PRD\nCheckout flow testing requirements.",
        ))
    elif not app.reset_path:
        app.reset_path = "/__reset"

    if PLAYBOOK_PATH.exists():
        pb = await session.get(Playbook, DEMO_PLAYBOOK_ID)
        if pb is None:
            pb = Playbook(id=DEMO_PLAYBOOK_ID, app_id=DEMO_APP_ID, name="Checkout Flow Playbook")
            session.add(pb)
            await session.flush()
        raw = PLAYBOOK_PATH.read_text(encoding="utf-8")
        first = (await session.execute(
            select(PlaybookVersion).where(PlaybookVersion.playbook_id == pb.id))).first() is None
        current = await session.get(PlaybookVersion, pb.current_version_id) if pb.current_version_id else None
        parsed = parse_playbook_markdown(raw, current.parsed if current else None)
        await store_version(session, pb, raw, parsed, version_id=DEMO_VERSION_ID if first else None)
    await session.commit()
