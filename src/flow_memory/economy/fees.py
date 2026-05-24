"""Local fee calculation for simulated Flow Memory payments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FeeSchedule:
    verifier_fee_rate: float = 0.05
    treasury_fee_rate: float = 0.02
    max_total_fee_rate: float = 0.25

    def calculate(self, amount: float, *, include_verifier: bool = True) -> Mapping[str, float]:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        verifier_fee = amount * self.verifier_fee_rate if include_verifier else 0.0
        treasury_fee = amount * self.treasury_fee_rate
        total_fee = verifier_fee + treasury_fee
        max_fee = amount * self.max_total_fee_rate
        if total_fee > max_fee:
            scale = 0.0 if total_fee == 0 else max_fee / total_fee
            verifier_fee *= scale
            treasury_fee *= scale
            total_fee = verifier_fee + treasury_fee
        return {
            "amount": round(amount, 8),
            "verifier_fee": round(verifier_fee, 8),
            "treasury_fee": round(treasury_fee, 8),
            "worker_net_amount": round(amount - total_fee, 8),
            "total_fee": round(total_fee, 8),
        }
