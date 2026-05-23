"""Self-improvement changelog records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class ImprovementChange:
    target_id: str
    summary: str
    approved: bool = False
    change_id: str = field(default_factory=lambda: new_id("improvement_change"))
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, object]:
        return {"change_id": self.change_id, "target_id": self.target_id, "summary": self.summary, "approved": self.approved, "created_at": self.created_at.isoformat(), "metadata": dict(self.metadata)}
