import json
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin

from playwright.async_api import Page

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_API_SPEC = re.compile(r"^(/[^.]*)(?:\.(.+))?$")

ApiCallHook = Callable[[Dict[str, Any]], Awaitable[Optional[str]]]


class BindingError(Exception):
    pass


def parse_number(text: str) -> Any:
    """'$1,234.50' -> 1234.5; text without a number is returned stripped."""
    match = _NUMBER.search(text)
    if not match:
        return text.strip()
    num = match.group(0).replace(",", "")
    return float(num) if "." in num else int(num)


def _drill(data: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        else:
            raise BindingError(f"field '{dotted}' not found in API response")
    return data


class BindingResolver:
    """
    Resolves playbook bindings against the live app:
      api:/path.field  -> GET through the browser context (shared cookies); the call is reported to
                          `on_api_call` so it is stored as a network call evidence can cite
      ui:<selector>    -> text of the first match, numbers parsed;  ui_all() for every match
      const:<value>    -> literal
    Each resolution returns the value plus where it came from.
    """

    def __init__(self, page: Page, base_url: str, on_api_call: Optional[ApiCallHook] = None):
        self.page = page
        self.base_url = base_url
        self.on_api_call = on_api_call
        self._api_cache: Dict[str, Any] = {}

    async def _fetch(self, path: str) -> Dict[str, Any]:
        if path in self._api_cache:
            return self._api_cache[path]
        url = urljoin(self.base_url, path)
        started = time.perf_counter()
        try:
            resp = await self.page.context.request.get(url, timeout=5000)
            body = await resp.body()
            data = json.loads(body)
        except Exception as exc:
            raise BindingError(f"API {path} unreachable: {exc}") from exc
        call = {
            "method": "GET", "url": url, "status": resp.status, "duration_ms": (time.perf_counter() - started) * 1000,
            "is_api": True, "req_body": None, "resp_body": body[: 256 * 1024], "background": True,
            "req_size": 0, "resp_size": len(body),
        }
        call_id = await self.on_api_call(call) if self.on_api_call else None
        entry = {"data": data, "call_id": call_id, "url": url}
        self._api_cache[path] = entry
        return entry

    async def resolve(self, spec: str) -> Dict[str, Any]:
        kind, _, rest = spec.partition(":")
        if kind == "const":
            try:
                value = json.loads(rest)
            except ValueError:
                value = rest
            return {"value": value, "source": spec}
        if kind == "ui":
            try:
                loc = self.page.locator(rest).first
                text = await loc.inner_text(timeout=2000)
            except Exception as exc:
                raise BindingError(f"UI element {rest} not found on {self.page.url}") from exc
            try:
                bbox = await loc.bounding_box(timeout=1000)
            except Exception:
                bbox = None
            return {"value": parse_number(text), "source": spec, "raw": text.strip(), "page_url": self.page.url,
                    "bbox": bbox}
        if kind == "api":
            m = _API_SPEC.match(rest)
            if not m:
                raise BindingError(f"bad api binding '{spec}'")
            path, field = m.groups()
            entry = await self._fetch(path)
            value = _drill(entry["data"], field) if field else entry["data"]
            return {"value": value, "source": spec, "call_id": entry["call_id"], "url": entry["url"]}
        raise BindingError(f"unknown binding source '{kind}' in '{spec}'")

    async def ui_all(self, selector: str) -> List[str]:
        try:
            return [t.strip() for t in await self.page.locator(selector).all_inner_texts()]
        except Exception as exc:
            raise BindingError(f"UI selector {selector} failed: {exc}") from exc
