"""
Files a test can upload. An app can store its own test files (Settings > Test files); every run also has a few
built-in samples so an upload step works with no setup. Which file a step uses:
  1. the journey's test data (`file: report.pdf`, or several separated by commas),
  2. a file name mentioned in the step itself ("Upload report.pdf as the invoice"),
  3. otherwise the file whose type matches what the upload field accepts, else the first file.
"""
import re
import struct
import zlib
from typing import Any, Dict, List, Optional, Tuple

from qagent.domain.schemas import CandidateAction

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_APP = 50

_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
    "pdf": "application/pdf", "txt": "text/plain", "csv": "text/csv", "json": "application/json",
    "md": "text/markdown", "html": "text/html", "zip": "application/zip", "xml": "application/xml",
    "doc": "application/msword", "xls": "application/vnd.ms-excel", "mp4": "video/mp4",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def guess_type(name: str) -> str:
    return _TYPES.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream") if "." in name else "application/octet-stream"


def _png(size: int = 8) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + bytes([201, 146, 42]) * size for _ in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


_PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")

# name -> (bytes, content type). Small on purpose; they exist so "upload a file" works out of the box.
BUILTIN: Dict[str, Tuple[bytes, str]] = {
    "sample.png": (_png(), "image/png"),
    "sample.pdf": (_PDF, "application/pdf"),
    "sample.txt": (b"QAgent sample text file.\n", "text/plain"),
    "sample.csv": (b"id,name\n1,Alpha\n2,Beta\n", "text/csv"),
    "sample.json": (b'{"sample": true}\n', "application/json"),
}

_QUOTED = re.compile(r"""["'`]([^"'`]+\.[A-Za-z0-9]{1,5})["'`]""")
_ACCEPTS = re.compile(r"accepts? ([^)]*)\)", re.IGNORECASE)


def split_names(value: Any) -> List[str]:
    return [n.strip() for n in str(value).split(",") if n.strip()]


def _resolve(name: str, available: List[str], label: str) -> str:
    """One name from the journey's test data -> a file that exists. A real file name is kept as asked (so a missing one is
    reported by name). A description such as 'attached CSV file' or 'the dirty data file' is matched to the app's files by
    type words (csv, pdf...) and then by the words it shares with a file name, and failing that by what the field accepts."""
    lowered = {a.lower(): a for a in available}
    if name.lower() in lowered:
        return lowered[name.lower()]
    if re.search(r"\.[A-Za-z0-9]{1,5}$", name):
        return name
    words = re.findall(r"[a-z0-9]+", name.lower())
    ext_words = {w for w in words if w in _TYPES}
    pool = [a for a in available if not ext_words or a.rsplit(".", 1)[-1].lower() in ext_words] or available
    # the app's own files come first in `available`; among them prefer the one sharing the most words with the description
    best = max(pool, key=lambda a: (sum(w in re.findall(r"[a-z0-9]+", a.lower()) for w in words if w not in ext_words), -pool.index(a)))
    return best


def choose_files(intent: str, label: str, test_data: Dict[str, Any], available: List[str]) -> List[str]:
    """Names of the files to upload for this step, or [] when nothing is available. Unknown names are returned as
    asked, so the caller can report exactly which file is missing."""
    keys = [k for k in ("file", "files", "upload", "attachment") if k in test_data]
    keys += [k for k in test_data if k not in keys and re.search(r"file|upload|attach|csv|document", str(k), re.I)]
    for key in keys:
        if str(test_data[key]).strip():
            return [_resolve(n, available, label) for n in split_names(test_data[key])]
    lowered = {a.lower(): a for a in available}
    quoted = _QUOTED.findall(intent)
    if quoted:
        return [lowered.get(q.lower(), q) for q in quoted]
    named = [orig for low, orig in lowered.items() if re.search(rf"(?<![\w.]){re.escape(low)}(?![\w])", intent.lower())]
    if named:
        return named
    accept = _ACCEPTS.search(label)
    if accept:
        wanted = accept.group(1).lower()
        for orig in available:
            ctype, ext = guess_type(orig), "." + orig.rsplit(".", 1)[-1].lower()
            if ext in wanted or ctype in wanted or (ctype.split("/")[0] + "/*") in wanted:
                return [orig]
    return available[:1]


def payload(name: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
    """The shape Playwright's set_input_files takes for an in-memory file."""
    return {"name": name, "mimeType": content_type or guess_type(name), "buffer": data}


def is_upload(candidate: CandidateAction) -> bool:
    return candidate.action_type == "upload"
