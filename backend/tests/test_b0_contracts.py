import pytest
from httpx import AsyncClient, ASGITransport
from qagent.api.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "active_model" in data


@pytest.mark.asyncio
async def test_dev_events():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/dev/events")
        assert response.status_code == 200
        events = response.json()
        assert len(events) >= 10
        assert events[0]["type"] == "RUN_STARTED"


@pytest.mark.asyncio
async def test_list_apps():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/apps")
        assert response.status_code == 200
        apps = response.json()
        assert len(apps) >= 1
        assert apps[0]["slug"] == "demo-shop"


@pytest.mark.asyncio
async def test_list_runs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/runs")
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) >= 1
        assert runs[0]["id"] == "run-demo-001"
