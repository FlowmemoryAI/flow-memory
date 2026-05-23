"""Signed audit checkpoint helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload
from flow_memory.storage.replay import ReplayResult


@dataclass(frozen=True)
class AuditCheckpoint:
    """Signed summary of an audit replay chain at a point in time."""

    checkpoint_id: str
    latest_hash: str
    event_count: int
    signer: str
    signature: SignatureEnvelope

    def unsigned_payload(self) -> Mapping[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "latest_hash": self.latest_hash,
            "event_count": self.event_count,
            "signer": self.signer,
        }

    def as_record(self) -> Mapping[str, Any]:
        return {**self.unsigned_payload(), "signature": self.signature.as_record()}


def create_audit_checkpoint(result: ReplayResult, key: LocalKeyPair) -> AuditCheckpoint:
    """Create a local development signature over a replay result summary."""

    payload = {
        "latest_hash": result.latest_hash,
        "event_count": len(result.records),
        "signer": key.public_id(),
    }
    checkpoint_id = "audit_checkpoint_" + content_hash(payload)[:24]
    unsigned = {"checkpoint_id": checkpoint_id, **payload}
    return AuditCheckpoint(
        checkpoint_id=checkpoint_id,
        latest_hash=result.latest_hash,
        event_count=len(result.records),
        signer=key.public_id(),
        signature=sign_payload(unsigned, key),
    )


def verify_audit_checkpoint(
    checkpoint: AuditCheckpoint | Mapping[str, Any],
    key: LocalKeyPair,
    *,
    expected_latest_hash: str | None = None,
    expected_event_count: int | None = None,
) -> bool:
    """Verify a signed audit checkpoint against optional replay expectations."""

    record = checkpoint.as_record() if isinstance(checkpoint, AuditCheckpoint) else dict(checkpoint)
    signature = record.get("signature")
    if not isinstance(signature, Mapping):
        return False
    unsigned = {
        "checkpoint_id": record.get("checkpoint_id"),
        "latest_hash": record.get("latest_hash"),
        "event_count": record.get("event_count"),
        "signer": record.get("signer"),
    }
    if expected_latest_hash is not None and unsigned["latest_hash"] != expected_latest_hash:
        return False
    if expected_event_count is not None and int(unsigned["event_count"] or -1) != expected_event_count:
        return False
    return verify_payload(unsigned, signature, key)
