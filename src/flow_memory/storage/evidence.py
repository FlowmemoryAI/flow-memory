"""Local event-log evidence helpers for storage audit replay.

This module is intentionally offline-only: it produces deterministic JSON-serializable
records for local preflight evidence without claiming production-grade anchoring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from flow_memory.crypto.hashes import content_hash
from flow_memory.storage.replay import ReplayResult, verify_chained_events
from flow_memory.storage.sqlite_store import SQLiteStore

EVENT_LOG_FORMAT = "flow-memory-audit-event-log-v1"


@dataclass(frozen=True)
class EventLogEvidence:
    """Deterministic summary of a local audit event log."""

    format: str
    event_count: int
    latest_hash: str
    content_hash: str
    replay_ok: bool
    errors: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {
            "format": self.format,
            "event_count": self.event_count,
            "latest_hash": self.latest_hash,
            "content_hash": self.content_hash,
            "replay_ok": self.replay_ok,
            "errors": self.errors,
            "scope": "local-prototype",
        }


def read_jsonl_events(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    """Read JSONL events, failing closed on blank-free malformed lines."""

    events: list[Mapping[str, Any]] = []
    for line_number, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise ValueError(f"event log line {line_number} is not a JSON object")
        events.append(dict(value))
    return tuple(events)


def write_jsonl_events(events: Iterable[Mapping[str, Any]], path: str | Path) -> EventLogEvidence:
    """Write deterministic JSONL and return replay evidence for the written events."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    materialized = tuple(dict(event) for event in events)
    output.write_text(
        "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in materialized),
        encoding="utf-8",
        newline="\n",
    )
    return event_log_evidence(materialized)


def export_audit_event_log(store: SQLiteStore, path: str | Path) -> EventLogEvidence:
    """Export chained audit events from a store as canonical JSONL."""

    events = tuple(sorted((event for event in store.list("audit_events") if "chain_hash" in event), key=lambda event: int(event["chain_index"])))
    return write_jsonl_events(events, path)


def event_log_evidence(events: Iterable[Mapping[str, Any]]) -> EventLogEvidence:
    """Return local preflight replay evidence for event-log contents."""

    materialized = tuple(dict(event) for event in events)
    replay = verify_chained_events(materialized)
    return _evidence_from_replay(materialized, replay)


def evidence_from_jsonl(path: str | Path) -> EventLogEvidence:
    """Read a JSONL log and return its deterministic local evidence summary."""

    return event_log_evidence(read_jsonl_events(path))


def _evidence_from_replay(events: tuple[Mapping[str, Any], ...], replay: ReplayResult) -> EventLogEvidence:
    return EventLogEvidence(
        format=EVENT_LOG_FORMAT,
        event_count=len(events),
        latest_hash=replay.latest_hash,
        content_hash=content_hash(events),
        replay_ok=replay.ok,
        errors=tuple(replay.errors),
    )
