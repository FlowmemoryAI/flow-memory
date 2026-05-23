"""Runtime lifecycle event and health records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now() -> datetime:
    """Return an aware UTC timestamp for runtime records."""

    return datetime.now(timezone.utc)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return repr(value)


@dataclass(frozen=True)
class RuntimeEvent:
    """Hash-chained runtime event suitable for local audit trails."""

    sequence: int
    kind: str
    manager: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)
    previous_hash: str = "GENESIS"
    event_hash: str = ""

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "manager": self.manager,
            "payload": dict(self.payload),
            "previous_hash": self.previous_hash,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
        }

    def compute_hash(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, default=_json_default).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def with_hash(self) -> "RuntimeEvent":
        return RuntimeEvent(
            sequence=self.sequence,
            kind=self.kind,
            manager=self.manager,
            payload=dict(self.payload),
            timestamp=self.timestamp,
            previous_hash=self.previous_hash,
            event_hash=self.compute_hash(),
        )

    def verifies(self) -> bool:
        return self.event_hash == self.compute_hash()


@dataclass(frozen=True)
class RuntimeStatus:
    """Point-in-time lifecycle status for one runtime manager."""

    name: str
    running: bool
    ticks: int = 0
    handled_events: int = 0
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class RuntimeHealth:
    """Health summary for a manager or orchestrator."""

    name: str
    ok: bool
    running: bool
    ticks: int = 0
    checks: Mapping[str, bool] = field(default_factory=dict)
    messages: tuple[str, ...] = ()

    @classmethod
    def from_status(cls, status: RuntimeStatus) -> "RuntimeHealth":
        checks = {
            "started": status.started_at is not None,
            "no_last_error": status.last_error is None,
            "running": status.running,
        }
        messages = () if all(checks.values()) else tuple(key for key, value in checks.items() if not value)
        return cls(
            name=status.name,
            ok=all(checks.values()),
            running=status.running,
            ticks=status.ticks,
            checks=checks,
            messages=messages,
        )
