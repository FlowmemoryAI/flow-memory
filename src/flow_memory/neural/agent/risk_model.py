"""Tiny advisory risk model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NeuralRiskScore:
    unsafe_action_likelihood: float
    approval_required_likelihood: float
    economic_loss_proxy: float
    failure_probability: float

    def as_record(self) -> Mapping[str, float]:
        return {
            "unsafe_action_likelihood": self.unsafe_action_likelihood,
            "approval_required_likelihood": self.approval_required_likelihood,
            "economic_loss_proxy": self.economic_loss_proxy,
            "failure_probability": self.failure_probability,
        }


class TinyRiskModel:
    def score(self, item: Any) -> NeuralRiskScore:
        text = repr(item).lower()
        unsafe_terms = sum(term in text for term in ("wallet", "delete", "execute", "shell", "private", "transfer"))
        economic_terms = sum(term in text for term in ("settle", "escrow", "bid", "pay", "marketplace"))
        high_terms = sum(term in text for term in ("high", "critical", "unsafe"))
        unsafe = min(1.0, unsafe_terms * 0.3 + high_terms * 0.2)
        economic = min(1.0, economic_terms * 0.25)
        approval = max(unsafe, economic)
        failure = min(1.0, 0.1 + high_terms * 0.2 + unsafe * 0.3)
        return NeuralRiskScore(unsafe, approval, economic, failure)
