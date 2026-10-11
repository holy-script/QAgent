from typing import List, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from qagent.domain.models import App, Playbook, PlaybookVersion, Run, FlowRun, Step, Decision, FindingRecord, NetworkCallRecord, EventRecord


class StorageRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_app_by_slug(self, slug: str) -> Optional[App]:
        stmt = select(App).where(App.slug == slug)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_app(self, app: App) -> App:
        self.session.add(app)
        await self.session.commit()
        await self.session.refresh(app)
        return app

    async def list_apps(self) -> List[App]:
        stmt = select(App)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def save_run(self, run: Run) -> Run:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, run_id: str) -> Optional[Run]:
        stmt = select(Run).where(Run.id == run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def save_event(self, event: EventRecord) -> EventRecord:
        self.session.add(event)
        await self.session.commit()
        return event

    async def get_events(self, run_id: str, after_seq: int = 0) -> List[EventRecord]:
        stmt = select(EventRecord).where(
            EventRecord.run_id == run_id,
            EventRecord.seq > after_seq
        ).order_by(EventRecord.seq)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
