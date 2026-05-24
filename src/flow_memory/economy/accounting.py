"""Local simulated accounting ledger for Flow Memory's agent economy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id
from flow_memory.economy.payment_model import PaymentLifecycleResult, PaymentTerms


@dataclass(frozen=True)
class LedgerEntry:
    entry_type: str
    account_id: str
    amount: float
    task_id: str = ""
    counterparty_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: new_id("ledger"))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_record(self) -> Mapping[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type,
            "account_id": self.account_id,
            "amount": self.amount,
            "task_id": self.task_id,
            "counterparty_id": self.counterparty_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class LocalAccountingLedger:
    balances: dict[str, float] = field(default_factory=dict)
    escrow_balances: dict[str, float] = field(default_factory=dict)
    entries: list[LedgerEntry] = field(default_factory=list)

    def credit(self, account_id: str, amount: float, *, task_id: str = "", metadata: Mapping[str, Any] | None = None) -> LedgerEntry:
        self._validate_amount(amount)
        self.balances[account_id] = self.balances.get(account_id, 0.0) + amount
        return self._entry("credit", account_id, amount, task_id=task_id, metadata=metadata or {})

    def debit(self, account_id: str, amount: float, *, task_id: str = "", metadata: Mapping[str, Any] | None = None) -> LedgerEntry:
        self._validate_amount(amount)
        if self.balances.get(account_id, 0.0) < amount:
            raise ValueError(f"insufficient local balance for {account_id}")
        self.balances[account_id] -= amount
        return self._entry("debit", account_id, -amount, task_id=task_id, metadata=metadata or {})

    def lock_escrow(self, escrow_id: str, payer_id: str, amount: float, *, task_id: str = "") -> LedgerEntry:
        self.debit(payer_id, amount, task_id=task_id, metadata={"escrow_id": escrow_id})
        self.escrow_balances[escrow_id] = self.escrow_balances.get(escrow_id, 0.0) + amount
        return self._entry("escrow_lock", escrow_id, amount, task_id=task_id, counterparty_id=payer_id)

    def settle_escrow(self, escrow_id: str, terms: PaymentTerms, *, task_id: str = "") -> PaymentLifecycleResult:
        errors = terms.validate()
        if errors:
            return PaymentLifecycleResult(False, "invalid_terms", tuple(entry.as_record() for entry in self.entries), self.balances, escrow_id, "; ".join(errors))
        locked = self.escrow_balances.get(escrow_id, 0.0)
        if locked < terms.amount:
            return PaymentLifecycleResult(False, "insufficient_escrow", tuple(entry.as_record() for entry in self.entries), self.balances, escrow_id, "escrow balance below payment amount")
        self.escrow_balances[escrow_id] = locked - terms.amount
        self.credit(terms.worker_id, terms.worker_net_amount, task_id=task_id, metadata={"escrow_id": escrow_id, "kind": "worker_payment"})
        if terms.verifier_id and terms.verifier_fee:
            self.credit(terms.verifier_id, terms.verifier_fee, task_id=task_id, metadata={"escrow_id": escrow_id, "kind": "verifier_fee"})
        if terms.treasury_fee:
            self.credit("treasury", terms.treasury_fee, task_id=task_id, metadata={"escrow_id": escrow_id, "kind": "treasury_fee"})
        self._entry("escrow_settle", escrow_id, -terms.amount, task_id=task_id, counterparty_id=terms.worker_id, metadata=terms.as_record())
        return PaymentLifecycleResult(True, "settled", tuple(entry.as_record() for entry in self.entries), self.balances, escrow_id)

    def refund_escrow(self, escrow_id: str, requester_id: str, *, task_id: str = "") -> PaymentLifecycleResult:
        amount = self.escrow_balances.get(escrow_id, 0.0)
        if amount <= 0:
            return PaymentLifecycleResult(False, "empty_escrow", tuple(entry.as_record() for entry in self.entries), self.balances, escrow_id, "no escrow balance to refund")
        self.escrow_balances[escrow_id] = 0.0
        self.credit(requester_id, amount, task_id=task_id, metadata={"escrow_id": escrow_id, "kind": "refund"})
        self._entry("escrow_refund", escrow_id, -amount, task_id=task_id, counterparty_id=requester_id)
        return PaymentLifecycleResult(True, "refunded", tuple(entry.as_record() for entry in self.entries), self.balances, escrow_id)

    def slash(self, account_id: str, amount: float, *, task_id: str = "", reason: str = "") -> LedgerEntry:
        available = self.balances.get(account_id, 0.0)
        penalty = min(max(amount, 0.0), available)
        self.balances[account_id] = available - penalty
        self.balances["treasury"] = self.balances.get("treasury", 0.0) + penalty
        return self._entry("slash", account_id, -penalty, task_id=task_id, counterparty_id="treasury", metadata={"reason": reason})

    def as_record(self) -> Mapping[str, Any]:
        return {
            "balances": dict(self.balances),
            "escrow_balances": dict(self.escrow_balances),
            "entries": tuple(entry.as_record() for entry in self.entries),
            "simulated_today": True,
            "real_funds_used": False,
        }

    def _entry(self, entry_type: str, account_id: str, amount: float, *, task_id: str = "", counterparty_id: str = "", metadata: Mapping[str, Any] | None = None) -> LedgerEntry:
        entry = LedgerEntry(entry_type, account_id, amount, task_id, counterparty_id, metadata or {})
        self.entries.append(entry)
        return entry

    @staticmethod
    def _validate_amount(amount: float) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
