"""Agent treasury."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class AgentTreasury:
    """Collective funds ledger for agents or DAOs."""

    balance: float = 0.0
    ledger: list[Mapping[str, Any]] = field(default_factory=list)

    def credit(self, amount: float, reason: str) -> None:
        if amount < 0:
            raise ValueError("Cannot credit negative amount")
        self.balance += amount
        self.ledger.append({"kind": "credit", "amount": amount, "reason": reason})

    def debit(self, amount: float, reason: str) -> None:
        if amount < 0:
            raise ValueError("Cannot debit negative amount")
        if amount > self.balance:
            raise ValueError("Treasury balance insufficient")
        self.balance -= amount
        self.ledger.append({"kind": "debit", "amount": amount, "reason": reason})
