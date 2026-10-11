from qagent.config import settings
from qagent.domain.schemas import ConfidenceTier


def evaluate_gate(confidence: float, auto_min: float = 0.75, escalate_min: float = 0.45) -> ConfidenceTier:
    """
    Tiered confidence gating:
    - Confidence >= auto_min -> AUTO
    - escalate_min <= Confidence < auto_min -> ESCALATE
    - Confidence < escalate_min -> STOP
    """
    if confidence >= auto_min:
        return ConfidenceTier.AUTO
    elif confidence >= escalate_min:
        return ConfidenceTier.ESCALATE
    return ConfidenceTier.STOP
