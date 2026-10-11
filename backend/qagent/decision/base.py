from typing import Protocol, runtime_checkable
from qagent.domain.schemas import DecisionRequest, DecisionResult


@runtime_checkable
class Decider(Protocol):
    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Make a decision for the given step and candidate actions."""
        ...
