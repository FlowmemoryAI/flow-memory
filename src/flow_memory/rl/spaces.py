"""Tiny dependency-free RL spaces."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class DiscreteSpace:
    n: int
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("DiscreteSpace n must be positive")

    def sample(self, seed: int | None = None) -> int:
        return random.Random(seed).randrange(self.n)

    def contains(self, value: Any) -> bool:
        return isinstance(value, int) and 0 <= value < self.n

    def label(self, action: int) -> str:
        return self.labels[action] if self.labels and self.contains(action) else str(action)

    def as_record(self) -> dict[str, Any]:
        return {"type": "discrete", "n": self.n, "labels": tuple(self.labels)}


@dataclass(frozen=True)
class BoxSpace:
    shape: tuple[int, ...]
    low: float = 0.0
    high: float = 1.0

    def contains(self, value: Any) -> bool:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return False
        if len(value) != (self.shape[0] if self.shape else 0):
            return False
        try:
            return all(self.low <= float(item) <= self.high for item in value)
        except (TypeError, ValueError):
            return False

    def as_record(self) -> dict[str, Any]:
        return {"type": "box", "shape": tuple(self.shape), "low": self.low, "high": self.high}


@dataclass(frozen=True)
class DictSpace:
    fields: tuple[str, ...]

    def contains(self, value: Any) -> bool:
        return isinstance(value, dict) and all(field in value for field in self.fields)

    def as_record(self) -> dict[str, Any]:
        return {"type": "dict", "fields": tuple(self.fields)}
