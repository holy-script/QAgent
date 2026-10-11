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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

SHOP_DIR = Path(__file__).parents[2] / "demo-shop"
PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "checkout-flow.md"


class FakeUploader:
    """Collects enqueue() calls so engine tests need no object storage."""

    def __init__(self):
        self.items = []

    def start(self):
        pass

    async def enqueue(self, **kwargs):
        self.items.append(kwargs)

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
async def mem_sessions():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def uploader():
    return FakeUploader()
