"""Network-level receipts used by local orchestration scenarios."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class NetworkReceipt:
    receipt_type: str
    actor: str
    payload: Mapping[str, Any]
    receipt_id: str = field(default_factory=lambda: new_id("network_receipt"))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_record(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_type": self.receipt_type,
            "actor": self.actor,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }
