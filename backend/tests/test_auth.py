import time

import pytest
from httpx import ASGITransport, AsyncClient

from qagent.api import auth
from qagent.api.main import app
from qagent.config import settings

pytestmark = pytest.mark.real_auth


@pytest.fixture
async def client():
    auth._failures.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def login(client, email=None, password=None):
    return await client.post("/auth/login", json={"email": email or settings.auth_email, "password": password or settings.auth_password})


def test_team_credentials_are_the_agreed_ones():
    assert settings.auth_email == "admin@chryselys.com" and settings.auth_password == "Admin@QAgent!2026"


@pytest.mark.asyncio
async def test_protected_routes_need_a_session_but_health_does_not(client):
    assert (await client.get("/apps")).status_code == 401
    assert (await client.get("/runs/x/events")).status_code == 401
    assert (await client.get("/api/artifacts/x/url")).status_code == 401
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_login_sets_an_http_only_cookie_that_unlocks_the_api(client):
    r = await login(client, "  ADMIN@chryselys.com ")  # email is case- and whitespace-insensitive
    assert r.status_code == 200 and r.json() == {"email": settings.auth_email}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and auth.COOKIE in cookie
    assert (await client.get("/auth/me")).json()["email"] == settings.auth_email
    assert (await client.get("/runs")).status_code != 401


@pytest.mark.asyncio
async def test_wrong_credentials_are_rejected_without_hinting_which_part(client):
    for e, p in ((settings.auth_email, "nope"), ("someone@else.com", settings.auth_password)):
        r = await login(client, e, p)
        assert r.status_code == 401 and r.json()["detail"] == "Email or password is not correct"
    assert "set-cookie" not in r.headers


@pytest.mark.asyncio
async def test_logout_clears_the_session(client):
    await login(client)
    assert (await client.post("/auth/logout")).status_code == 204
    client.cookies.clear()
    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_too_many_failures_are_throttled(client):
    for _ in range(auth.MAX_FAILURES):
        assert (await login(client, password="bad")).status_code == 401
    assert (await login(client)).status_code == 429  # even the right password waits out the window


def test_tokens_expire_and_cannot_be_tampered_with():
    good = auth.make_token("a@b.c")
    assert auth.read_token(good) == "a@b.c"
    assert auth.read_token(auth.make_token("a@b.c", ttl_s=-1)) is None
    body, sig = good.rsplit(".", 1)
    assert auth.read_token(f"{body}.{'0' * len(sig)}") is None
    assert auth.read_token(auth.make_token("x@y.z").split(".")[0] + "." + sig) is None
    assert auth.read_token("garbage") is None and auth.read_token(None) is None


@pytest.mark.asyncio
async def test_bearer_header_works_for_scripts(client):
    token = auth.make_token(settings.auth_email)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cors_allows_only_the_frontend_origin_with_credentials(client):
    ok = await client.options("/apps", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000" and ok.headers["access-control-allow-credentials"] == "true"
    bad = await client.options("/apps", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
