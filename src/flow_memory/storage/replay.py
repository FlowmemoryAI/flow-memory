"""Replay and hash-chain verification for local event streams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from flow_memory.crypto.hashes import content_hash

GENESIS_HASH = "genesis"
_CHAIN_FIELDS = frozenset({"chain_index", "previous_hash", "payload_hash", "chain_hash"})


@dataclass(frozen=True)
class ReplayRecord:
    """Canonical replay record derived from an event payload."""

    index: int
    event_id: str
    event_type: str
    payload: Mapping[str, Any]
    payload_hash: str
    previous_hash: str
    chain_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "index": self.index,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "payload_hash": self.payload_hash,
            "previous_hash": self.previous_hash,
            "chain_hash": self.chain_hash,
        }


@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying or verifying an event stream."""

    ok: bool
    records: tuple[ReplayRecord, ...]
    errors: tuple[str, ...] = ()

    @property
    def latest_hash(self) -> str:
        return self.records[-1].chain_hash if self.records else GENESIS_HASH

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "latest_hash": self.latest_hash,
            "errors": self.errors,
            "records": tuple(record.as_record() for record in self.records),
        }


def replay_events(events: Iterable[Mapping[str, Any]]) -> ReplayResult:
    """Build a deterministic replay chain from event payloads.

    The input order is authoritative. This is used for offline replay/export where
    a stream did not already store chain fields.
    """

    records: list[ReplayRecord] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    previous_hash = GENESIS_HASH

    for index, event in enumerate(events):
        payload = _strip_chain_fields(event)
        event_id = _event_id(payload, index)
        event_type = _event_type(payload)
        if event_id in seen_ids:
            errors.append(f"duplicate event id at index {index}: {event_id}")
        seen_ids.add(event_id)
        payload_hash = content_hash(payload)
        chain_hash = _chain_hash(index=index, event_id=event_id, payload_hash=payload_hash, previous_hash=previous_hash)
        records.append(
            ReplayRecord(
                index=index,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                payload_hash=payload_hash,
                previous_hash=previous_hash,
                chain_hash=chain_hash,
            )
        )
        previous_hash = chain_hash

    return ReplayResult(ok=not errors, records=tuple(records), errors=tuple(errors))


def verify_chained_events(events: Iterable[Mapping[str, Any]]) -> ReplayResult:
    """Verify events that already include chain fields.

    Events are sorted by ``chain_index`` before verification. Any payload tamper,
    missing chain field, duplicate event id, broken index, or broken previous hash
    makes the result fail closed.
    """

    materialized = tuple(events)
    ordered = tuple(sorted(materialized, key=lambda event: int(event.get("chain_index", -1))))
    records: list[ReplayRecord] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    previous_hash = GENESIS_HASH

    for expected_index, event in enumerate(ordered):
        missing = tuple(field for field in _CHAIN_FIELDS if field not in event)
        if missing:
            errors.append(f"missing chain fields at index {expected_index}: {', '.join(missing)}")
            continue

        stored_index = int(event["chain_index"])
        payload = _strip_chain_fields(event)
        event_id = _event_id(payload, expected_index)
        event_type = _event_type(payload)
        payload_hash = content_hash(payload)
        chain_hash = _chain_hash(
            index=stored_index,
            event_id=event_id,
            payload_hash=payload_hash,
            previous_hash=str(event["previous_hash"]),
        )

        if stored_index != expected_index:
            errors.append(f"broken chain index for {event_id}: expected {expected_index}, got {stored_index}")
        if event_id in seen_ids:
            errors.append(f"duplicate event id at index {expected_index}: {event_id}")
        if str(event["previous_hash"]) != previous_hash:
            errors.append(f"broken previous hash for {event_id}")
        if str(event["payload_hash"]) != payload_hash:
            errors.append(f"payload hash mismatch for {event_id}")
        if str(event["chain_hash"]) != chain_hash:
            errors.append(f"chain hash mismatch for {event_id}")

        seen_ids.add(event_id)
        records.append(
            ReplayRecord(
                index=stored_index,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                payload_hash=payload_hash,
                previous_hash=str(event["previous_hash"]),
                chain_hash=chain_hash,
            )
        )
        previous_hash = str(event["chain_hash"])

    return ReplayResult(ok=not errors, records=tuple(records), errors=tuple(errors))


def chained_payload(event: Mapping[str, Any], *, index: int, previous_hash: str) -> Mapping[str, Any]:
    """Return a stored event payload with deterministic chain fields."""

    payload = _strip_chain_fields(event)
    event_id = _event_id(payload, index)
    payload_hash = content_hash(payload)
    return {
        **payload,
        "chain_index": index,
        "previous_hash": previous_hash,
        "payload_hash": payload_hash,
        "chain_hash": _chain_hash(index=index, event_id=event_id, payload_hash=payload_hash, previous_hash=previous_hash),
    }


def _strip_chain_fields(event: Mapping[str, Any]) -> Mapping[str, Any]:
    return {str(key): value for key, value in event.items() if key not in _CHAIN_FIELDS}


def _event_id(event: Mapping[str, Any], index: int) -> str:
    value = event.get("audit_id") or event.get("event_id") or event.get("receipt_id") or event.get("id")
    return str(value or f"event_{index:06d}")


def _event_type(event: Mapping[str, Any]) -> str:
    value = event.get("event") or event.get("event_type") or event.get("receipt_type") or event.get("type")
    return str(value or "unknown")


def _chain_hash(*, index: int, event_id: str, payload_hash: str, previous_hash: str) -> str:
    return content_hash(
        {
            "chain_index": index,
            "event_id": event_id,
            "payload_hash": payload_hash,
            "previous_hash": previous_hash,
        }
    )
