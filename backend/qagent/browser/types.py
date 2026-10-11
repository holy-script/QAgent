from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from qagent.domain.schemas import BoundingRect, CandidateAction, BrowserObservation

__all__ = [
    "BoundingRect",
    "CandidateAction",
    "BrowserObservation",
]
