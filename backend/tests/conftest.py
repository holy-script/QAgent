import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import uvicorn
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from qagent.storage.objects import object_store
from qagent.storage.upload_queue import UploadQueue

SHOP_DIR = Path(__file__).parents[2] / "demo-shop"
PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "checkout.md"


from qagent.checks.ux_judged import Verdict


class FakeJudge:
    """Judges by page text: statements about errors are true only if the page shows no 'Address saved'."""

    async def ask(self, question, page_text, screenshots=None, hints=None, examples=None):
        ok = "Address saved" not in page_text if "error" in question.lower() else True
        return Verdict(ok, 0.95 if ok else 0.05, "jev", 0.9, "fake")


class RecordingUploadQueue(UploadQueue):
    """The real upload queue (local object store, in-memory DB) that also records what was enqueued."""

    def __init__(self):
        super().__init__()
        self.items = []

    async def enqueue(self, **kwargs):
        self.items.append(kwargs)
        await super().enqueue(**kwargs)

    def keys(self, kind=None):
        return [i["key"] for i in self.items if kind is None or i["kind"] == kind]


@pytest.fixture(scope="session")
def shop_url():
    """Runs the real demo shop on a free local port for browser tests."""
    spec = importlib.util.spec_from_file_location("demo_shop_live", SHOP_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_shop_live"] = module
    spec.loader.exec_module(module)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(module.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def shop(shop_url):
    """Resets the shop and returns a helper for toggling bugs."""
    httpx.post(f"{shop_url}/__reset")

    def set_bugs(**flags):
        httpx.post(f"{shop_url}/__bugs", json={k.lstrip("bug"): v for k, v in flags.items()})

    set_bugs(bug1=True, bug2=True, bug3=True, bug4=True, bug5=True)
    return shop_url, set_bugs


@pytest_asyncio.fixture
async def mem_sessions(tmp_path):
    """
    Per-test SQLite file. Transactions start with BEGIN IMMEDIATE so concurrent sessions (the sink, the upload
    worker, API handlers) queue on the write lock instead of failing on read-to-write upgrades.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db", connect_args={"timeout": 30})

    @event.listens_for(engine.sync_engine, "connect")
    def _no_implicit_begin(dbapi_connection, _):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def uploader(mem_sessions, monkeypatch, tmp_path):
    monkeypatch.setattr(object_store, "client", None)  # never touch real object storage in tests
    monkeypatch.setattr(object_store, "local_dir", tmp_path)
    monkeypatch.setattr("qagent.storage.upload_queue.async_session_factory", mem_sessions)
    queue = RecordingUploadQueue()
    queue.start()
    yield queue
    await queue.stop()


@pytest.fixture(autouse=True)
def signed_in(request):
    """API tests run as a signed-in user. Tests marked `real_auth` exercise the actual login instead."""
    from qagent.api import auth
    from qagent.api.main import app as api_app
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    api_app.dependency_overrides[auth.require_user] = lambda: "test@example.com"
    yield
    api_app.dependency_overrides.pop(auth.require_user, None)
