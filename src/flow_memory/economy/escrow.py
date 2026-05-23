"""Local escrow ledger for Agent Economy v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class EscrowAccount:
    escrow_id: str
    task_id: str
    payer: str
    payee: str
    amount: float
    status: str = "funded"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "escrow_id": self.escrow_id,
            "task_id": self.task_id,
            "payer": self.payer,
            "payee": self.payee,
            "amount": self.amount,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass
class LocalEscrow:
    """In-memory escrow with no external funds or keys."""

    accounts: dict[str, EscrowAccount] = field(default_factory=dict)
    task_index: dict[str, str] = field(default_factory=dict)
    releases: dict[str, float] = field(default_factory=dict)
    refunds: dict[str, float] = field(default_factory=dict)

    def fund(
        self,
        task_id: str,
        payer: str,
        payee: str,
        amount: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> EscrowAccount:
        if amount < 0:
            raise ValueError("Escrow amount must be non-negative")
        if task_id in self.task_index:
            raise ValueError(f"Task already has escrow: {task_id}")
        escrow = EscrowAccount(
            escrow_id=new_id("escrow"),
            task_id=task_id,
            payer=payer,
            payee=payee,
            amount=amount,
            metadata=dict(metadata or {}),
        )
        self.accounts[escrow.escrow_id] = escrow
        self.task_index[task_id] = escrow.escrow_id
        return escrow

    def for_task(self, task_id: str) -> EscrowAccount:
        escrow_id = self.task_index.get(task_id)
        if escrow_id is None:
            raise KeyError(f"Task has no escrow: {task_id}")
        return self.accounts[escrow_id]

    def release(self, task_id: str, actor: str) -> EscrowAccount:
        escrow = self.for_task(task_id)
        if actor != escrow.payer:
            raise PermissionError("Only the payer can release escrow")
        if escrow.status != "funded":
            raise ValueError(f"Escrow already closed: {task_id}")
        closed = EscrowAccount(
            escrow_id=escrow.escrow_id,
            task_id=escrow.task_id,
            payer=escrow.payer,
            payee=escrow.payee,
            amount=escrow.amount,
            status="released",
            metadata=escrow.metadata,
        )
        self.accounts[closed.escrow_id] = closed
        self.releases[closed.payee] = self.releases.get(closed.payee, 0.0) + closed.amount
        return closed

    def refund(self, task_id: str, actor: str) -> EscrowAccount:
        escrow = self.for_task(task_id)
        if actor != escrow.payer:
            raise PermissionError("Only the payer can refund escrow")
        if escrow.status != "funded":
            raise ValueError(f"Escrow already closed: {task_id}")
        closed = EscrowAccount(
            escrow_id=escrow.escrow_id,
            task_id=escrow.task_id,
            payer=escrow.payer,
            payee=escrow.payee,
            amount=escrow.amount,
            status="refunded",
            metadata=escrow.metadata,
        )
        self.accounts[closed.escrow_id] = closed
        self.refunds[closed.payer] = self.refunds.get(closed.payer, 0.0) + closed.amount
        return closed
