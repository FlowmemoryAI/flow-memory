"""Local slashing event model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class SlashingEvent:
    agent_did: str
    task_id: str
    reason: str
    reputation_delta: float = -10.0
    event_id: str = field(default_factory=lambda: new_id("slash"))
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, object]:
        return {
            "event_id": self.event_id,
            "agent_did": self.agent_did,
            "task_id": self.task_id,
            "reason": self.reason,
            "reputation_delta": self.reputation_delta,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
