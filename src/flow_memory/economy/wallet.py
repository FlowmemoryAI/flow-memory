"""Smart-wallet and treasury accounting."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class LedgerEntry:
    kind: str
    amount: float
    reason: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UserOperation:
    operation_id: str
    to: str
    value: float
    data: Mapping[str, Any] = field(default_factory=dict)
    status: str = "queued"


@dataclass
class SmartWallet:
    """ERC-4337-like local smart-wallet model."""

    address: str = field(default_factory=lambda: "0x" + secrets.token_hex(20))
    balance: float = 0.0
    ledger: list[LedgerEntry] = field(default_factory=list)
    operations: list[UserOperation] = field(default_factory=list)

    def deposit(self, amount: float, reason: str = "deposit") -> None:
        if amount < 0:
            raise ValueError("Cannot deposit a negative amount")
        self.balance += amount
        self.ledger.append(LedgerEntry(kind="credit", amount=amount, reason=reason))

    def debit(self, amount: float, reason: str = "debit") -> None:
        if amount < 0:
            raise ValueError("Cannot debit a negative amount")
        if amount > self.balance:
            raise ValueError("Insufficient balance")
        self.balance -= amount
        self.ledger.append(LedgerEntry(kind="debit", amount=amount, reason=reason))

    def queue_operation(self, to: str, value: float, data: Mapping[str, Any] | None = None) -> UserOperation:
        if value < 0:
            raise ValueError("UserOperation value must be non-negative")
        op = UserOperation(operation_id=new_id("userop"), to=to, value=value, data=dict(data or {}))
        self.operations.append(op)
        return op


@dataclass
class AgentTreasury:
    balance: float = 0.0
    ledger: list[LedgerEntry] = field(default_factory=list)

    def credit(self, amount: float, reason: str) -> None:
        self.balance += amount
        self.ledger.append(LedgerEntry(kind="credit", amount=amount, reason=reason))

    def debit(self, amount: float, reason: str) -> None:
        if amount > self.balance:
            raise ValueError("Treasury balance insufficient")
        self.balance -= amount
        self.ledger.append(LedgerEntry(kind="debit", amount=amount, reason=reason))
