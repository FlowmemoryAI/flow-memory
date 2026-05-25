"""Tamper-evident audit export and checkpointing for Compute Market."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from flow_memory.compute_market.storage import audit_event_hash, canonical_audit_payload_hash, utc_now_iso
from flow_memory.compute_market.storage_backends import ComputeMarketStoreProtocol
from flow_memory.crypto.hashes import content_hash

_EXPORT_FORMAT = "flow-memory-compute-market-audit-export-v1"
_SECRET_KEY_FRAGMENTS = (
    "private_key",
    "secret_key",
    "seed_phrase",
    "seed phrase",
    "mnemonic",
    "wallet_private_key",
)
_ALLOWED_SAFETY_FLAG_KEYS = frozenset(
    {
        "private_key_required",
        "broadcast_allowed",
        "funds_moved",
        "dry_run_only",
    }
)



@dataclass(frozen=True)
class AuditCheckpoint:
    checkpoint_id: str
    chain_id: str
    from_sequence: int
    to_sequence: int
    from_event_hash: str
    to_event_hash: str
    event_count: int
    checkpoint_hash: str
    hash_algorithm: str
    created_at: str
    exported_to: str
    export_uri: str
    export_status: str
    verification_status: str

    def as_record(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class AuditExportResult:
    ok: bool
    path: str
    checkpoint: AuditCheckpoint
    manifest_hash: str
    event_count: int
    warnings: tuple[str, ...] = ()

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "path": self.path,
            "checkpoint": self.checkpoint.as_record(),
            "manifest_hash": self.manifest_hash,
            "event_count": self.event_count,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class AuditExportVerification:
    ok: bool
    path: str
    event_count: int
    checkpoint_hash: str = ""
    error_code: str = ""
    message: str = ""

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "path": self.path,
            "event_count": self.event_count,
            "checkpoint_hash": self.checkpoint_hash,
            "error_code": self.error_code,
            "message": self.message,
        }


class AuditExporterProtocol(Protocol):
    def export_events(
        self,
        store: ComputeMarketStoreProtocol,
        *,
        chain_id: str = "all",
        from_sequence: int = 1,
        to_sequence: int = 0,
    ) -> AuditExportResult: ...

    def write_checkpoint(self, checkpoint: AuditCheckpoint) -> Mapping[str, Any]: ...

    def verify_export(self) -> AuditExportVerification: ...

    def get_status(self) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class NoopAuditExporter:
    reason: str = "audit_export_not_configured"

    def export_events(
        self,
        store: ComputeMarketStoreProtocol,
        *,
        chain_id: str = "all",
        from_sequence: int = 1,
        to_sequence: int = 0,
    ) -> AuditExportResult:
        checkpoint = AuditCheckpoint(
            checkpoint_id="",
            chain_id=chain_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            from_event_hash="",
            to_event_hash="",
            event_count=0,
            checkpoint_hash="",
            hash_algorithm="sha256",
            created_at=utc_now_iso(),
            exported_to="none",
            export_uri="",
            export_status="disabled",
            verification_status="not_configured",
        )
        return AuditExportResult(False, "", checkpoint, "", 0, (self.reason,))

    def write_checkpoint(self, checkpoint: AuditCheckpoint) -> Mapping[str, Any]:
        return {"ok": False, "reason": self.reason, "checkpoint": checkpoint.as_record()}

    def verify_export(self) -> AuditExportVerification:
        return AuditExportVerification(False, "", 0, error_code=self.reason, message="audit export is not configured")

    def get_status(self) -> Mapping[str, object]:
        return {"configured": False, "exporter": "none", "reason": self.reason}


@dataclass(frozen=True)
class LocalFileAuditExporter:
    path: Path

    def export_events(
        self,
        store: ComputeMarketStoreProtocol,
        *,
        chain_id: str = "all",
        from_sequence: int = 1,
        to_sequence: int = 0,
    ) -> AuditExportResult:
        events = _select_events(store, chain_id=chain_id, from_sequence=from_sequence, to_sequence=to_sequence)
        _assert_no_exported_secrets(events)
        checkpoint = build_checkpoint(
            events,
            chain_id=chain_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            export_uri=str(self.path),
            exported_to="local_file",
        )
        manifest = {
            "type": "manifest",
            "format": _EXPORT_FORMAT,
            "created_at": checkpoint.created_at,
            "chain_id": chain_id,
            "event_count": len(events),
            "checkpoint_hash": checkpoint.checkpoint_hash,
        }
        manifest_hash = content_hash(manifest)
        manifest = {**manifest, "manifest_hash": manifest_hash}
        lines = [
            _canonical_json(manifest),
            *(_canonical_json({"type": "audit_event", "event": event}) for event in events),
            _canonical_json({"type": "checkpoint", "checkpoint": checkpoint.as_record()}),
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return AuditExportResult(True, str(self.path), checkpoint, manifest_hash, len(events))

    def write_checkpoint(self, checkpoint: AuditCheckpoint) -> Mapping[str, Any]:
        checkpoint_path = self.path.with_suffix(self.path.suffix + ".checkpoint.json")
        checkpoint_path.write_text(_canonical_json(checkpoint.as_record()) + "\n", encoding="utf-8")
        return {"ok": True, "path": str(checkpoint_path), "checkpoint": checkpoint.as_record()}

    def verify_export(self) -> AuditExportVerification:
        try:
            parsed = _read_export(self.path)
            manifest = parsed[0]
            checkpoint_line = parsed[-1]
            events = tuple(_event_from_line(item) for item in parsed[1:-1])
            if str(manifest.get("format", "")) != _EXPORT_FORMAT:
                return AuditExportVerification(False, str(self.path), 0, error_code="invalid_format", message="audit export format is invalid")
            if any(event is None for event in events):
                return AuditExportVerification(False, str(self.path), 0, error_code="invalid_event_line", message="audit export contains a malformed event line")
            event_records = tuple(event for event in events if event is not None)
            _assert_no_exported_secrets(event_records)
            checkpoint_map = checkpoint_line.get("checkpoint") if isinstance(checkpoint_line, Mapping) else None
            if not isinstance(checkpoint_map, Mapping):
                return AuditExportVerification(False, str(self.path), len(event_records), error_code="missing_checkpoint", message="audit export is missing checkpoint")
            expected = _checkpoint_hash(event_records, str(checkpoint_map.get("chain_id", "all")), str(checkpoint_map.get("export_uri", "")))
            checkpoint_hash = str(checkpoint_map.get("checkpoint_hash", ""))
            if checkpoint_hash != expected:
                return AuditExportVerification(False, str(self.path), len(event_records), checkpoint_hash, "checkpoint_hash_mismatch", "checkpoint hash does not match exported events")
            chain_error = _verify_exported_chain(event_records)
            if chain_error:
                return AuditExportVerification(False, str(self.path), len(event_records), checkpoint_hash, chain_error[0], chain_error[1])
            if int(manifest.get("event_count", -1)) != len(event_records):
                return AuditExportVerification(False, str(self.path), len(event_records), checkpoint_hash, "manifest_count_mismatch", "manifest event_count does not match export")
            return AuditExportVerification(True, str(self.path), len(event_records), checkpoint_hash)
        except Exception as exc:
            return AuditExportVerification(False, str(self.path), 0, error_code=type(exc).__name__, message=str(exc))

    def get_status(self) -> Mapping[str, object]:
        return {"configured": True, "exporter": "local_file", "path": str(self.path)}


@dataclass(frozen=True)
class S3WormAuditExporter:
    """Configuration scaffold for object-lock/WORM deployments.

    This class intentionally does not perform cloud writes without a project-wide
    object-storage dependency and credential model. Operators should bind a real
    implementation behind AuditExporterProtocol.
    """

    bucket: str
    prefix: str

    def export_events(
        self,
        store: ComputeMarketStoreProtocol,
        *,
        chain_id: str = "all",
        from_sequence: int = 1,
        to_sequence: int = 0,
    ) -> AuditExportResult:
        return NoopAuditExporter("s3_worm_exporter_requires_deployment_binding").export_events(
            store,
            chain_id=chain_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
        )

    def write_checkpoint(self, checkpoint: AuditCheckpoint) -> Mapping[str, Any]:
        return {"ok": False, "reason": "s3_worm_exporter_requires_deployment_binding", "checkpoint": checkpoint.as_record()}

    def verify_export(self) -> AuditExportVerification:
        return AuditExportVerification(False, f"s3://{self.bucket}/{self.prefix}", 0, error_code="not_bound", message="S3/WORM exporter requires deployment binding")

    def get_status(self) -> Mapping[str, object]:
        return {"configured": False, "exporter": "s3_worm_ready", "bucket": self.bucket, "prefix": self.prefix}


def build_checkpoint(
    events: tuple[Mapping[str, Any], ...],
    *,
    chain_id: str,
    from_sequence: int,
    to_sequence: int,
    export_uri: str,
    exported_to: str,
) -> AuditCheckpoint:
    event_count = len(events)
    first_event = events[0] if events else {}
    last_event = events[-1] if events else {}
    resolved_to_sequence = to_sequence or int(last_event.get("sequence_number", 0) or 0)
    checkpoint_payload = {
        "chain_id": chain_id,
        "from_sequence": from_sequence,
        "to_sequence": resolved_to_sequence,
        "from_event_hash": str(first_event.get("event_hash", "")),
        "to_event_hash": str(last_event.get("event_hash", "")),
        "event_count": event_count,
        "event_hashes": tuple(str(event.get("event_hash", "")) for event in events),
        "export_uri": export_uri,
    }
    checkpoint_hash = content_hash(checkpoint_payload)
    return AuditCheckpoint(
        checkpoint_id=f"audit_checkpoint_{checkpoint_hash[:24]}",
        chain_id=chain_id,
        from_sequence=from_sequence,
        to_sequence=resolved_to_sequence,
        from_event_hash=str(first_event.get("event_hash", "")),
        to_event_hash=str(last_event.get("event_hash", "")),
        event_count=event_count,
        checkpoint_hash=checkpoint_hash,
        hash_algorithm="sha256",
        created_at=utc_now_iso(),
        exported_to=exported_to,
        export_uri=export_uri,
        export_status="exported" if event_count else "empty",
        verification_status="unverified",
    )


def verify_audit_export(path: str | Path) -> AuditExportVerification:
    return LocalFileAuditExporter(Path(path)).verify_export()


def _select_events(
    store: ComputeMarketStoreProtocol,
    *,
    chain_id: str,
    from_sequence: int,
    to_sequence: int,
) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    cursor = ""
    while True:
        page = store.list_records("audit_event", limit=500, cursor=cursor, include_archived=True)
        records.extend(page.records)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    selected = []
    for event in records:
        sequence = int(event.get("sequence_number", 0) or 0)
        matches_chain = chain_id in {"", "all"} or str(event.get("chain_id", "")) == chain_id
        if matches_chain and sequence >= from_sequence and (to_sequence <= 0 or sequence <= to_sequence):
            selected.append(event)
    return tuple(sorted(selected, key=lambda item: (str(item.get("chain_id", "")), int(item.get("sequence_number", 0) or 0), str(item.get("audit_event_id", "")))))


def _checkpoint_hash(events: tuple[Mapping[str, Any], ...], chain_id: str, export_uri: str) -> str:
    checkpoint = build_checkpoint(
        events,
        chain_id=chain_id,
        from_sequence=int(events[0].get("sequence_number", 1) or 1) if events else 1,
        to_sequence=int(events[-1].get("sequence_number", 0) or 0) if events else 0,
        export_uri=export_uri,
        exported_to="local_file",
    )
    return checkpoint.checkpoint_hash


def _verify_exported_chain(events: tuple[Mapping[str, Any], ...]) -> tuple[str, str] | None:
    previous_by_chain: dict[str, str] = {}
    expected_sequence_by_chain: dict[str, int] = {}
    for event in sorted(events, key=lambda item: (str(item.get("chain_id", "")), int(item.get("sequence_number", 0) or 0))):
        chain_id = str(event.get("chain_id", ""))
        expected = expected_sequence_by_chain.get(chain_id, int(event.get("sequence_number", 1) or 1))
        sequence = int(event.get("sequence_number", 0) or 0)
        if sequence != expected:
            return ("audit_sequence_gap", "exported audit chain has a missing or out-of-order event")
        if str(event.get("previous_hash", "")) != previous_by_chain.get(chain_id, ""):
            return ("audit_previous_hash_mismatch", "exported audit chain previous_hash is broken")
        canonical_hash = canonical_audit_payload_hash(event)
        if str(event.get("canonical_payload_hash", "")) != canonical_hash:
            return ("audit_payload_hash_mismatch", "exported audit event payload was modified")
        event_hash = audit_event_hash(event)
        if str(event.get("event_hash", "")) != event_hash:
            return ("audit_event_hash_mismatch", "exported audit event hash is invalid")
        previous_by_chain[chain_id] = event_hash
        expected_sequence_by_chain[chain_id] = sequence + 1
    return None


def _read_export(path: Path) -> tuple[Mapping[str, Any], ...]:
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _event_from_line(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    event = item.get("event") if item.get("type") == "audit_event" else None
    return event if isinstance(event, Mapping) else None


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _assert_no_exported_secrets(events: tuple[Mapping[str, Any], ...]) -> None:
    for event in events:
        for key, value in _walk(event):
            lowered = key.lower()
            if key not in _ALLOWED_SAFETY_FLAG_KEYS and any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS):
                raise ValueError("audit export refused to write secret-bearing payload")
            if isinstance(value, str) and any(fragment in value.lower() for fragment in _SECRET_KEY_FRAGMENTS):
                raise ValueError("audit export refused to write secret-bearing payload")


def _walk(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, Mapping):
        items: list[tuple[str, object]] = []
        for key, nested in value.items():
            items.append((str(key), nested))
            items.extend(_walk(nested))
        return tuple(items)
    if isinstance(value, (tuple, list)):
        items = []
        for nested in value:
            items.extend(_walk(nested))
        return tuple(items)
    return ()
