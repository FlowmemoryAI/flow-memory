"""Non-transferable reputation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class NonTransferableReputation:
    """Soulbound / DID-bound reputation model."""

    score: float = 0.0
    events: list[Mapping[str, Any]] = field(default_factory=list)

    def record(self, event: Mapping[str, Any], delta: float) -> None:
        self.events.append(dict(event, delta=delta))
        self.score = max(-100.0, min(100.0, self.score + delta))
