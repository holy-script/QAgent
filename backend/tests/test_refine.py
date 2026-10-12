import pytest
from httpx import AsyncClient

from qagent.api.routes import text as text_route
from qagent.playbooks import refine
from test_lifecycle import api  # noqa: F401  (fixture)


class FakeClaude:
    model_id = "fake"
    seen = None

    async def converse_tool(self, system, user, tool, max_tokens=512, images=None):
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
