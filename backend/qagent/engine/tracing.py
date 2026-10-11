import secrets
import time
from typing import Any, Dict, Optional

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger("qagent")


class Span:
    """Minimal OTel-shaped span (hex trace/span ids, ns timestamps) persisted via SPAN_ENDED events."""

    def __init__(self, name: str, kind: str, trace_id: str, parent: Optional["Span"] = None, **attributes: Any):
        self.name = name
        self.kind = kind
        self.trace_id = trace_id
        self.span_id = secrets.token_hex(8)
        self.parent_span_id = parent.span_id if parent else None
        self.attributes: Dict[str, Any] = dict(attributes)
        self.status = "ok"
        self.start_ns = time.time_ns()

    def end(self, status: Optional[str] = None) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "start_ns": self.start_ns,
            "end_ns": time.time_ns(),
            "attributes": self.attributes,
            "status": status or self.status,
        }
