"""Local settlement records for Agent Economy v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class SettlementRecord:
    task_id: str
    payer: str
    payee: str
    amount: float
    status: str
    settlement_id: str = field(default_factory=lambda: new_id("settlement"))
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, object]:
        return {
            "settlement_id": self.settlement_id,
            "task_id": self.task_id,
            "payer": self.payer,
            "payee": self.payee,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
