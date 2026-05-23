"""Economic slashing hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class EconomicSlashing:
    """Records penalties for bad behavior; settlement adapters can enforce them on-chain."""

    events: list[Mapping[str, Any]] = field(default_factory=list)

    def slash(self, agent_did: str, amount: float, reason: str) -> Mapping[str, Any]:
        if amount < 0:
            raise ValueError("Slashing amount cannot be negative")
        event = {"agent_did": agent_did, "amount": amount, "reason": reason}
        self.events.append(event)
        return event
