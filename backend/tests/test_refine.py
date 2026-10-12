import pytest
from httpx import AsyncClient

from qagent.api.routes import text as text_route
from qagent.playbooks import refine
from test_lifecycle import api  # noqa: F401  (fixture)


class FakeClaude:
    model_id = "fake"
    seen = None

    async def converse_tool(self, system, user, tool, max_tokens=512, images=None, timeout=60.0):
        FakeClaude.seen = (system, user)
        return {"input": {"text": "Cleaned: " + user.strip(), "notes": "check the tax rate"}, "usage": {"inputTokens": 10, "outputTokens": 5}}


@pytest.mark.asyncio
async def test_each_kind_has_its_own_instructions_and_never_invents():
    for kind in ("tidy", "description", "prd", "notes"):
        out = await refine.refine_text("um so the cart should like show the total", kind, FakeClaude())
        assert out["text"].startswith("Cleaned: ") and out["notes"] == "check the tax rate"
        assert "never invent" in FakeClaude.seen[0] and FakeClaude.seen[1].startswith("um so the cart")
    assert "## Acceptance criteria" in refine.KINDS["prd"]
    with pytest.raises(ValueError):
        await refine.refine_text("x", "poem", FakeClaude())


@pytest.mark.asyncio
async def test_endpoint_validates_and_reports_missing_key(api: AsyncClient, monkeypatch):  # noqa: F811
    monkeypatch.setattr(text_route.settings, "bedrock_api_key", "")
    assert (await api.post("/text/refine", json={"text": "hello", "kind": "tidy"})).status_code == 503
    assert (await api.post("/text/refine", json={"text": "hello", "kind": "poem"})).status_code == 422
    assert (await api.post("/text/refine", json={"text": "   ", "kind": "tidy"})).status_code == 422
    assert (await api.post("/text/refine", json={"text": "", "kind": "tidy"})).status_code == 422

    monkeypatch.setattr(text_route.settings, "bedrock_api_key", "k")

    async def fake(text, kind, client=None):
        return {"text": f"[{kind}] {text}", "notes": None, "usage": {}}
    monkeypatch.setattr(text_route, "refine_text", fake)
    r = await api.post("/text/refine", json={"text": "the cart total", "kind": "prd"})
    assert r.status_code == 200 and r.json() == {"text": "[prd] the cart total", "notes": None}
    assert (await api.post("/api/text/refine", json={"text": "x", "kind": "tidy"})).status_code == 200  # also under /api

    async def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(text_route, "refine_text", boom)
    assert (await api.post("/text/refine", json={"text": "x", "kind": "tidy"})).status_code == 502


@pytest.mark.asyncio
async def test_long_documents_are_accepted_and_the_answer_gets_room(api: AsyncClient, monkeypatch):  # noqa: F811
    monkeypatch.setattr(text_route.settings, "bedrock_api_key", "k")
    seen = {}

    class Big:
        model_id = "fake"

        async def converse_tool(self, system, user, tool, max_tokens=512, images=None, timeout=60.0):
            seen.update(len=len(user), max_tokens=max_tokens, timeout=timeout)
            return {"input": {"text": "ok"}, "usage": {}}

    monkeypatch.setattr(refine, "BedrockClient", lambda: Big())
    long_prd = "word " * 30_000                      # 150,000 characters: far over the old 20,000 limit
    r = await api.post("/text/refine", json={"text": long_prd, "kind": "prd"})
    assert r.status_code == 200 and seen["len"] == 150_000
    assert seen["max_tokens"] == 32_000 and seen["timeout"] >= 300   # capped at the model's room, long timeout
    await api.post("/text/refine", json={"text": "short", "kind": "tidy"})
    assert seen["max_tokens"] == 3_000
    assert (await api.post("/text/refine", json={"text": "x" * 200_001, "kind": "tidy"})).status_code == 422
