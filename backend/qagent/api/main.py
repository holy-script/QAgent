from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qagent.api import auth
from qagent.config import settings
from qagent.api.routes import apps, artifacts, dev, health, issues, observability, playbooks, reports, runs, traceability
from qagent.api.seed import seed_demo
from qagent.engine.tracing import logger
from qagent.runs.manager import get_run_manager, recover_orphaned_runs
from qagent.storage import db
from qagent.storage.upload_queue import upload_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    if db.db_url.startswith("sqlite"):
        await db.init_db()  # Postgres schemas come from Alembic; SQLite has no migrations
    try:
        async with db.async_session_factory() as session:
            await seed_demo(session)
    except Exception as exc:
        logger.error("startup.seed_failed", error=type(exc).__name__)
    try:
        closed = await recover_orphaned_runs(db.async_session_factory)
        if closed:
            logger.warning("startup.orphaned_runs_closed", count=closed)
    except Exception as exc:
        logger.error("startup.recovery_failed", error=type(exc).__name__)
    upload_queue.start()
    yield
    await get_run_manager().shutdown()
    await upload_queue.stop()


app = FastAPI(
    title="QAgent API",
    description="Backend API for QAgent autonomous web application QA platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Everything except login, logout and the health check needs a signed-in user.
_routers = [dev.router, apps.router, runs.router, runs.app_router, playbooks.router,
            observability.router, issues.router, reports.router, traceability.router, artifacts.router]
protected = [Depends(auth.require_user)]
app.include_router(auth.router)
app.include_router(health.router)
for router in _routers:
    app.include_router(router, dependencies=protected)

# Artifact and screenshot URLs in events and DTOs are `/api/...` paths; serve them too
# (hidden from the OpenAPI schema so the generated client has one copy of each operation).
api_alias = APIRouter(prefix="/api")
for router in _routers:
    api_alias.include_router(router, dependencies=protected)
app.include_router(api_alias, include_in_schema=False)


@app.get("/")
async def root():
    return {
        "service": "QAgent API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
