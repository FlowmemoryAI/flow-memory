"""Rate limiting and circuit breakers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RateLimiter:
    """Simple sliding-window per-agent rate limiter."""

    max_events: int = 100
    window_seconds: int = 60
    events: list[datetime] = field(default_factory=list)

    def allow(self) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.events = [event for event in self.events if event >= cutoff]
        if len(self.events) >= self.max_events:
            return False
        self.events.append(now)
        return True

    def reset(self) -> None:
        self.events.clear()
