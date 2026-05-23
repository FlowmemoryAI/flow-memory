"""Immutable hash-chained audit logging."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return repr(value)


@dataclass
class ImmutableAuditLog:
    """Hash-chained append-only audit log."""

    path: Path | None = None
    _events: list[Mapping[str, Any]] = field(default_factory=list, init=False, repr=False)
    _last_hash: str = field(default="GENESIS", init=False, repr=False)

    def append(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = dict(event)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload["previous_hash"] = self._last_hash
        encoded = json.dumps(payload, sort_keys=True, default=_json_default).encode("utf-8")
        payload["hash"] = hashlib.sha256(encoded).hexdigest()
        self._last_hash = str(payload["hash"])
        self._events.append(payload)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")
        return payload

    def events(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._events)

    @property
    def tip_hash(self) -> str:
        return self._last_hash

    @staticmethod
    def _verify_events(events: list[Mapping[str, Any]]) -> bool:
        previous = "GENESIS"
        for event in events:
            payload = dict(event)
            event_hash = payload.pop("hash", None)
            if payload.get("previous_hash") != previous:
                return False
            encoded = json.dumps(payload, sort_keys=True, default=_json_default).encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != event_hash:
                return False
            previous = str(event_hash)
        return True

    def verify(self) -> bool:
        return self._verify_events(list(self._events))

    def verify_file(self, path: Path | None = None) -> bool:
        source = path or self.path
        if source is None or not source.exists():
            return False
        events = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        return self._verify_events(events)
