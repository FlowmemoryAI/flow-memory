"""Circuit breaker for repeated failures/anomalies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    """Opens after too many consecutive unsafe/failing events."""

    max_failures: int = 3
    failures: int = 0
    opened: bool = False
    reasons: list[str] = field(default_factory=list)

    def record_success(self) -> None:
        self.failures = 0
        self.opened = False

    def record_failure(self, reason: str) -> None:
        self.failures += 1
        self.reasons.append(reason)
        if self.failures >= self.max_failures:
            self.opened = True

    def allow(self) -> bool:
        return not self.opened

    def reset(self) -> None:
        self.failures = 0
        self.opened = False
        self.reasons.clear()
