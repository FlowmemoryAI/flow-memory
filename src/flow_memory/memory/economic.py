"""Economic memory: transaction and reputation event history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class EconomicMemory:
    """Transactions, task outcomes, and reputation-relevant records."""

    transactions: list[Mapping[str, Any]] = field(default_factory=list)
    reputation_events: list[Mapping[str, Any]] = field(default_factory=list)

    def record_transaction(self, event: Mapping[str, Any]) -> None:
        self.transactions.append(dict(event))

    def record_reputation_event(self, event: Mapping[str, Any]) -> None:
        self.reputation_events.append(dict(event))
