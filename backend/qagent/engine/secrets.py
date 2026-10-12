"""
Saved sign-in details must never leak: not into screenshots' text, logs, events, saved server calls, the DOM snapshots, the
Playwright trace, or a prompt to an AI. `SecretMasker` replaces every occurrence of a secret value (plain, URL-encoded and
JSON-escaped) with `[hidden]`. Values shorter than 4 characters are not masked (they would damage ordinary text).
"""
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import quote, quote_plus

MIN_LEN = 4
MASK = "[hidden]"
_TEXT_SUFFIXES = (".trace", ".network", ".json", ".jsonl", ".html", ".txt", ".har", ".stacks", ".md", ".csv")


class SecretMasker:
    def __init__(self, secrets: Dict[str, str]):
        variants: List[str] = []
        for value in secrets.values():
            if not value or len(value) < MIN_LEN:
                continue
            for v in (value, quote(value, safe=""), quote_plus(value), json.dumps(value)[1:-1]):
                if v and v not in variants:
                    variants.append(v)
        self._variants = sorted(variants, key=len, reverse=True)   # longest first, so a value is never half-masked
        self._bytes = [v.encode() for v in self._variants]

    def __bool__(self) -> bool:
        return bool(self._variants)

    def text(self, s: str) -> str:
        for v in self._variants:
            if v in s:
                s = s.replace(v, MASK)
        return s

    def data(self, b: bytes) -> bytes:
        for v in self._bytes:
            if v in b:
                b = b.replace(v, MASK.encode())
        return b

    def obj(self, o: Any) -> Any:
        """Masks every string inside nested dicts and lists (event payloads)."""
        if isinstance(o, str):
            return self.text(o)
        if isinstance(o, dict):
            return {k: self.obj(v) for k, v in o.items()}
        if isinstance(o, list):
            return [self.obj(v) for v in o]
        if isinstance(o, tuple):
            return tuple(self.obj(v) for v in o)
        return o

    def scrub_zip(self, path: Path) -> int:
        """Rewrites text entries of a zip (the Playwright trace) with secrets masked; returns how many entries changed."""
        if not self or not path.exists():
            return 0
        src = io.BytesIO(path.read_bytes())
        out = io.BytesIO()
        changed = 0
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                body = zin.read(item.filename)
                if item.filename.lower().endswith(_TEXT_SUFFIXES):
                    masked = self.data(body)
                    changed += masked != body
                    body = masked
                zout.writestr(item, body)
        path.write_bytes(out.getvalue())
        return changed

    def scrub_file(self, path: Path) -> bool:
        if not self or not path.exists():
            return False
        body = path.read_bytes()
        masked = self.data(body)
        if masked != body:
            path.write_bytes(masked)
        return masked != body
