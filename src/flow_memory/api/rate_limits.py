"""Local deterministic rate-limit seam for public-alpha preflight tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flow_memory.api.errors import ApiError, rate_limited_error
from flow_memory.api.request_context import RequestContext


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("Rate limit must be positive")
        if self.window_seconds < 1:
            raise ValueError("Rate limit window must be positive")


@dataclass(frozen=True)
class RateLimitDecision:
    ok: bool
    limit: int
    remaining: int
    reset_at: int
    key: str
    error: ApiError | None = None

    def as_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "ok": self.ok,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "key": self.key,
        }
        if self.error is not None:
            record["error"] = self.error.as_record()["error"]
        return record


@dataclass
class LocalRateLimiter:
    """In-memory fixed-window limiter; local seam, not distributed enforcement."""

    default_rule: RateLimitRule
    route_rules: dict[str, RateLimitRule] = field(default_factory=dict)
    _counts: dict[tuple[str, int], int] = field(default_factory=dict)

    def check(self, context: RequestContext, *, now: int, cost: int = 1) -> RateLimitDecision:
        if cost < 1:
            raise ValueError("Rate limit cost must be positive")
        rule = self.route_rules.get(context.path, self.default_rule)
        window = now // rule.window_seconds
        reset_at = (window + 1) * rule.window_seconds
        key = _rate_key(context)
        counter_key = (key, window)
        current = self._counts.get(counter_key, 0)
        next_count = current + cost
        if next_count > rule.limit:
            details = {"limit": rule.limit, "remaining": 0, "reset_at": reset_at, "key": key}
            return RateLimitDecision(
                ok=False,
                limit=rule.limit,
                remaining=0,
                reset_at=reset_at,
                key=key,
                error=rate_limited_error(details=details),
            )
        self._counts[counter_key] = next_count
        return RateLimitDecision(
            ok=True,
            limit=rule.limit,
            remaining=rule.limit - next_count,
            reset_at=reset_at,
            key=key,
        )

    def reset(self) -> None:
        self._counts.clear()


def _rate_key(context: RequestContext) -> str:
    principal = context.principal or "anonymous"
    client_id = context.client_id or "local"
    return f"{principal}:{client_id}:{context.method}:{context.path}"
