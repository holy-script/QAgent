import base64
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from qagent.storage.objects import object_store

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True, lstrip_blocks=True,
)


def _data_uri(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    try:
        data = object_store.get_bytes(key)
    except Exception:
        return None
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode()}" if data else None


def render(kind: str, content: Dict[str, Any], fmt: str) -> str:
    """kind: run | bug ; fmt: md | html. HTML embeds screenshots as data URIs so the file is self-contained."""
    images: Dict[str, Optional[str]] = {}
    if fmt == "html" and kind == "bug":
        for item in content.get("evidence", {}).get("items", []):
            if item["kind"] in ("annotated", "screenshot_before", "screenshot_after"):
                images[item["kind"]] = _data_uri(item["ref_id"])
    return _env.get_template(f"{kind}.{fmt}.j2").render(c=content, images=images)
