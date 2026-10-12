"""make doctor: preflight checks for every external dependency. Never prints secrets."""
import asyncio
import json
import sys
import uuid
from typing import Awaitable, Callable, List, Tuple

import httpx
from sqlalchemy import text

from qagent.config import settings

Result = Tuple[str, bool, str]


async def check_postgres() -> Result:
    from qagent.storage import db
    try:
        async with db.async_session_factory() as s:
            version = (await s.execute(text("select version()"))).scalar()
        detail = f"pooled ok: {str(version)[:40]}"
        if db.direct_engine is not None:
            async with db.direct_engine.connect() as c:
                await c.execute(text("select 1"))
            detail += "; direct ok"
        else:
            detail += "; DATABASE_URL_DIRECT not set"
        return "postgres", True, detail
    except Exception as exc:
        return "postgres", False, f"{type(exc).__name__}"


async def check_storage() -> Result:
    from qagent.storage.objects import object_store as o
    if not o.is_configured():
        return "object storage", False, "NEON_S3_* not configured (using local disk fallback)"
    try:
        try:
            o.client.head_bucket(Bucket=o.bucket)
            created = ""
        except Exception:
            o.client.create_bucket(Bucket=o.bucket)
            created = " (bucket created)"
        key = f"doctor/{uuid.uuid4().hex}.txt"
        o.put_object(key, b"ok", "text/plain")
        assert o.get_bytes(key) == b"ok"
        url = o.get_presigned_url(key, 60)
        async with httpx.AsyncClient(timeout=10) as c:
            fetched = (await c.get(url)).content
        o.client.delete_object(Bucket=o.bucket, Key=key)
        return "object storage", fetched == b"ok", f"put/get/presign ok in '{o.bucket}'{created}"
    except Exception as exc:
        return "object storage", False, f"{type(exc).__name__}"


async def check_jev() -> Result:
    if not settings.active_jev_token:
        return "jev", False, "TYPESAFE_API_KEY not set"
    try:
        h = {"Authorization": f"Bearer {settings.active_jev_token}"}
        async with httpx.AsyncClient(timeout=15) as c:
            aliases = [m["name"] for m in (await c.get(f"{settings.typesafe_base_url}/v1/models", headers=h)).json()["models"]]
            r = await c.post(f"{settings.typesafe_base_url}/v1/systemone", headers=h, json={
                "model": settings.jev_model, "state": "ping",
                "questions": {"q": {"type": "choice", "instructions": "pick", "criteria": {"a": "first", "b": "second"}}}})
            r.raise_for_status()
            data = r.json()
        pinned = data["model"] == settings.jev_model
        return "jev", True, (f"JEV_MODEL={settings.jev_model} answered as {data['model']}"
                             f"{'' if pinned else ' (alias; pin a concrete version)'}; aliases: {aliases}")
    except Exception as exc:
        return "jev", False, f"{type(exc).__name__}"


async def check_bedrock() -> Result:
    if not settings.bedrock_api_key:
        return "bedrock", False, "BEDROCK_API_KEY not set"
    from qagent.decision.claude import BedrockClient
    tool = {"toolSpec": {"name": "ping", "description": "ping", "inputSchema": {"json": {
        "type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}}}}
    try:
        client = BedrockClient()
        out = await client.converse_tool("Call the tool.", "ping", tool, max_tokens=50)
        return "bedrock", "ok" in out["input"], f"{client.model_id} in {client.region}: forced tool use ok"
    except Exception as exc:
        return "bedrock", False, f"{type(exc).__name__}"


async def check_browser() -> Result:
    from qagent.browser.sandbox import BrowserSandbox
    sb = BrowserSandbox()
    try:
        page = await sb.start()
        await page.set_content("<h1>doctor</h1>")
        shot = await page.screenshot(type="jpeg")
        return "browser", len(shot) > 100, f"{sb.browser_version} via {sb.browser_source}, screenshot {len(shot)} bytes"
    except Exception as exc:
        return "browser", False, f"{type(exc).__name__}"
    finally:
        await sb.stop()


async def main() -> int:
    checks: List[Callable[[], Awaitable[Result]]] = [check_postgres, check_storage, check_jev, check_bedrock, check_browser]
    results = await asyncio.gather(*(c() for c in checks))
    for name, ok, detail in results:
        print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}")
    failed = [n for n, ok, _ in results if not ok]
    print(json.dumps({"models": {"jev": settings.jev_model, "bedrock": settings.bedrock_reasoning_model_id}}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
