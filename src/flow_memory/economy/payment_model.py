"""Explicit payment model for Flow Memory's local agent economy.

This module models who pays whom without touching real funds. The default mode is
local simulated accounting; Base Sepolia / ERC-4337 remain dry-run adapter seams.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class EconomyRole(str, Enum):
    AGENT_OWNER = "agent_owner"
    TASK_REQUESTER = "task_requester"
    WORKER_AGENT = "worker_agent"
    VERIFIER_AGENT = "verifier_agent"
    MARKETPLACE_OPERATOR = "marketplace_operator"
    TREASURY = "treasury"
    SAFETY_COUNCIL = "safety_council"


@dataclass(frozen=True)
class EconomyActor:
    actor_id: str
    role: EconomyRole
    owner_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {"actor_id": self.actor_id, "role": self.role.value, "owner_id": self.owner_id, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class PaymentTerms:
    requester_id: str
    worker_id: str
    amount: float
    verifier_id: str = ""
    verifier_fee: float = 0.0
    treasury_fee: float = 0.0
    currency: str = "LOCAL_CREDITS"
    simulated: bool = True

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.requester_id:
            errors.append("requester_id is required")
        if not self.worker_id:
            errors.append("worker_id is required")
        if self.amount < 0:
            errors.append("amount must be non-negative")
        if self.verifier_fee < 0 or self.treasury_fee < 0:
            errors.append("fees must be non-negative")
        if self.verifier_fee + self.treasury_fee > self.amount:
            errors.append("fees cannot exceed payment amount")
        if not self.simulated:
            errors.append("real funds are disabled by default")
        return tuple(errors)

    @property
    def worker_net_amount(self) -> float:
        return self.amount - self.verifier_fee - self.treasury_fee

    def as_record(self) -> Mapping[str, Any]:
        return {
            "requester_id": self.requester_id,
            "worker_id": self.worker_id,
            "amount": self.amount,
            "verifier_id": self.verifier_id,
            "verifier_fee": self.verifier_fee,
            "treasury_fee": self.treasury_fee,
            "worker_net_amount": self.worker_net_amount,
            "currency": self.currency,
            "simulated": self.simulated,
        }


@dataclass(frozen=True)
class PaymentLifecycleResult:
    ok: bool
    status: str
    ledger_entries: tuple[Mapping[str, Any], ...]
    balances: Mapping[str, float]
    escrow_id: str = ""
    reason: str = ""

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "ledger_entries": self.ledger_entries,
            "balances": dict(self.balances),
            "escrow_id": self.escrow_id,
            "reason": self.reason,
            "simulated_today": True,
            "real_funds_used": False,
        }
