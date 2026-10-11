import json
from typing import Any, Iterable, Optional

MASK = "[redacted]"


def _mask(value: Any, keys: set) -> Any:
    if isinstance(value, dict):
        return {k: (MASK if k.lower() in keys else _mask(v, keys)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask(v, keys) for v in value]
    return value


def redact_body(body: Optional[bytes], keys: Iterable[str]) -> Optional[bytes]:
    """Masks the app's `redact_keys` (case-insensitive) in a JSON body. Non-JSON bodies are left untouched."""
    wanted = {k.lower() for k in keys}
    if not body or not wanted:
        return body
    try:
        data = json.loads(body)
    except ValueError:
        return body
    return json.dumps(_mask(data, wanted)).encode()
