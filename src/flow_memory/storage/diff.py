"""Deterministic diffs for local storage replay evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.storage.replay import ReplayResult


@dataclass(frozen=True)
class EventLogDiff:
    ok: bool
    expected_latest_hash: str
    actual_latest_hash: str
    expected_count: int
    actual_count: int
    errors: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "expected_latest_hash": self.expected_latest_hash,
            "actual_latest_hash": self.actual_latest_hash,
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "errors": self.errors,
            "scope": "local-prototype",
        }


def diff_replay_results(expected: ReplayResult, actual: ReplayResult) -> EventLogDiff:
    """Compare two replay results without inspecting non-deterministic process state."""

    errors: list[str] = []
    if not expected.ok:
        errors.append("expected replay is invalid")
    if not actual.ok:
        errors.append("actual replay is invalid")
    if expected.latest_hash != actual.latest_hash:
        errors.append("latest hash mismatch")
    if len(expected.records) != len(actual.records):
        errors.append("event count mismatch")
    return EventLogDiff(
        ok=not errors,
        expected_latest_hash=expected.latest_hash,
        actual_latest_hash=actual.latest_hash,
        expected_count=len(expected.records),
        actual_count=len(actual.records),
        errors=tuple(errors),
    )
