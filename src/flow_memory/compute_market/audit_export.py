"""Tamper-evident audit export and checkpointing for Compute Market."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse
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
    object_lock_mode: str = ""
    retention_until: str = ""
    storage_uri: str = ""

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
            parsed = read_export_file(self.path)
            manifest = parsed[0]
            checkpoint_line = parsed[-1]
            events = tuple(_event_from_line(item) for item in parsed[1:-1])
            if str(manifest.get("format", "")) != _EXPORT_FORMAT:
                return AuditExportVerification(False, str(self.path), 0, error_code="invalid_format", message="audit export format is invalid")
            manifest_error = _verify_manifest_hash(manifest)
            if manifest_error:
                return AuditExportVerification(False, str(self.path), 0, error_code=manifest_error[0], message=manifest_error[1])
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


@dataclass
class S3WormAuditExporter:
    """S3 Object Lock audit exporter.

    The implementation is dependency-optional: production deployments install
    boto3 and grant put/head/get permissions on an Object-Lock-enabled bucket;
    tests inject a small client with the same methods. Writes always include
    object-lock headers and fail closed if the client or bucket is unavailable.
    """

    bucket: str
    prefix: str
    object_lock_mode: str = "COMPLIANCE"
    retention_days: int = 365
    client: Any | None = None
    region_name: str = ""
    endpoint_url: str = ""
    _last_export_key: str = field(default="", init=False, repr=False)

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
        object_id = content_hash(
            {
                "bucket": self.bucket,
                "prefix": self.prefix,
                "chain_id": chain_id,
                "from_sequence": from_sequence,
                "to_sequence": to_sequence,
                "event_hashes": tuple(str(event.get("event_hash", "")) for event in events),
            }
        )[:32]
        key = self._key(f"exports/{chain_id or 'all'}-{object_id}.ndjson")
        export_uri = f"s3://{self.bucket}/{key}"
        retention_until = _retention_until(self.retention_days)
        checkpoint = build_checkpoint(
            events,
            chain_id=chain_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            export_uri=export_uri,
            exported_to="s3_object_lock",
            object_lock_mode=self.object_lock_mode,
            retention_until=_iso_timestamp(retention_until),
        )
        manifest = {
            "type": "manifest",
            "format": _EXPORT_FORMAT,
            "created_at": checkpoint.created_at,
            "chain_id": chain_id,
            "event_count": len(events),
            "checkpoint_hash": checkpoint.checkpoint_hash,
            "storage_uri": export_uri,
            "object_lock_mode": self.object_lock_mode,
            "retention_until": checkpoint.retention_until,
        }
        manifest_hash = content_hash(manifest)
        manifest = {**manifest, "manifest_hash": manifest_hash}
        body = "\n".join(
            [
                _canonical_json(manifest),
                *(_canonical_json({"type": "audit_event", "event": event}) for event in events),
                _canonical_json({"type": "checkpoint", "checkpoint": checkpoint.as_record()}),
            ]
        ) + "\n"
        self._assert_bucket_object_lock_enabled()
        client = self._client()
        metadata = {
            "manifest-hash": manifest_hash,
            "checkpoint-id": checkpoint.checkpoint_id,
            "audit-format": _EXPORT_FORMAT,
        }
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/x-ndjson",
            Metadata=metadata,
            ObjectLockMode=self.object_lock_mode,
            ObjectLockRetainUntilDate=retention_until,
        )
        self._assert_object_lock_readback(client, key, expected_metadata=metadata)
        self._last_export_key = key
        return AuditExportResult(True, export_uri, checkpoint, manifest_hash, len(events))

    def write_checkpoint(self, checkpoint: AuditCheckpoint) -> Mapping[str, Any]:
        retention_until = _retention_until(self.retention_days)
        key = self._key(f"checkpoints/{checkpoint.checkpoint_id}.json")
        body = _canonical_json(
            {
                **checkpoint.as_record(),
                "storage_uri": f"s3://{self.bucket}/{key}",
                "object_lock_mode": self.object_lock_mode,
                "retention_until": checkpoint.retention_until or _iso_timestamp(retention_until),
            }
        ) + "\n"
        self._assert_bucket_object_lock_enabled()
        client = self._client()
        metadata = {"checkpoint-id": checkpoint.checkpoint_id, "audit-format": _EXPORT_FORMAT}
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
            Metadata=metadata,
            ObjectLockMode=self.object_lock_mode,
            ObjectLockRetainUntilDate=retention_until,
        )
        self._assert_object_lock_readback(client, key, expected_metadata=metadata)
        return {"ok": True, "path": f"s3://{self.bucket}/{key}", "checkpoint": checkpoint.as_record(), "object_lock_mode": self.object_lock_mode}

    def verify_export(self) -> AuditExportVerification:
        if not self._last_export_key:
            return AuditExportVerification(False, f"s3://{self.bucket}/{self.prefix}", 0, error_code="missing_export_key", message="no export has been written by this exporter instance")
        try:
            response = self._client().get_object(Bucket=self.bucket, Key=self._last_export_key)
            parsed = tuple(json.loads(line) for line in _object_body_text(response.get("Body")).splitlines() if line.strip())
            manifest = parsed[0]
            checkpoint_line = parsed[-1]
            events = tuple(_event_from_line(item) for item in parsed[1:-1])
            if str(manifest.get("format", "")) != _EXPORT_FORMAT:
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", 0, error_code="invalid_format", message="audit export format is invalid")
            manifest_error = _verify_manifest_hash(manifest)
            if manifest_error:
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", 0, error_code=manifest_error[0], message=manifest_error[1])
            if any(event is None for event in events):
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", 0, error_code="invalid_event_line", message="audit export contains a malformed event line")
            event_records = tuple(event for event in events if event is not None)
            _assert_no_exported_secrets(event_records)
            checkpoint_map = checkpoint_line.get("checkpoint") if isinstance(checkpoint_line, Mapping) else None
            if not isinstance(checkpoint_map, Mapping):
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", len(event_records), error_code="missing_checkpoint", message="audit export is missing checkpoint")
            expected = _checkpoint_hash(event_records, str(checkpoint_map.get("chain_id", "all")), str(checkpoint_map.get("export_uri", "")))
            checkpoint_hash = str(checkpoint_map.get("checkpoint_hash", ""))
            if checkpoint_hash != expected:
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", len(event_records), checkpoint_hash, "checkpoint_hash_mismatch", "checkpoint hash does not match exported events")
            chain_error = _verify_exported_chain(event_records)
            if chain_error:
                return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", len(event_records), checkpoint_hash, chain_error[0], chain_error[1])
            return AuditExportVerification(True, f"s3://{self.bucket}/{self._last_export_key}", len(event_records), checkpoint_hash)
        except Exception as exc:
            return AuditExportVerification(False, f"s3://{self.bucket}/{self._last_export_key}", 0, error_code=type(exc).__name__, message=str(exc))

    def get_status(self) -> Mapping[str, object]:
        client_available = self._client_available()
        object_lock_enabled = self._bucket_object_lock_enabled() if client_available else False
        configured = bool(self.bucket) and client_available and object_lock_enabled
        return {
            "configured": configured,
            "exporter": "s3_object_lock",
            "bucket": self.bucket,
            "prefix": self.prefix,
            "object_lock_mode": self.object_lock_mode,
            "retention_days": self.retention_days,
            "region_configured": bool(self.region_name),
            "endpoint_configured": bool(self.endpoint_url),
            "object_lock_enabled": object_lock_enabled,
            "immutable": configured and self.object_lock_mode in {"COMPLIANCE", "GOVERNANCE"} and self.retention_days >= 1,
        }

    def _key(self, suffix: str) -> str:
        prefix = self.prefix.strip("/")
        clean_suffix = suffix.strip("/")
        return f"{prefix}/{clean_suffix}" if prefix else clean_suffix

    def _client_available(self) -> bool:
        if self.client is not None:
            return True
        try:
            import boto3  # noqa: F401
        except Exception:
            return False
        return True

    def _bucket_object_lock_enabled(self) -> bool:
        if not self.bucket:
            return False
        try:
            client = self._client()
            if not hasattr(client, "get_bucket_object_lock_configuration"):
                return False
            response = client.get_bucket_object_lock_configuration(Bucket=self.bucket)
        except Exception:
            return False
        config = response.get("ObjectLockConfiguration") if isinstance(response, Mapping) else None
        if not isinstance(config, Mapping):
            return False
        return str(config.get("ObjectLockEnabled", "")).lower() == "enabled"

    def _assert_bucket_object_lock_enabled(self) -> None:
        if not self._bucket_object_lock_enabled():
            raise RuntimeError("S3 audit exporter requires bucket Object Lock to be enabled")

    def _assert_object_lock_readback(self, client: Any, key: str, *, expected_metadata: Mapping[str, str]) -> None:
        if not hasattr(client, "head_object"):
            raise RuntimeError("S3 audit exporter requires head_object readback")
        response = client.head_object(Bucket=self.bucket, Key=key)
        if not isinstance(response, Mapping):
            raise RuntimeError("S3 audit exporter head_object readback returned an invalid response")
        metadata = response.get("Metadata", {})
        if not isinstance(metadata, Mapping):
            raise RuntimeError("S3 audit exporter head_object readback returned invalid metadata")
        for metadata_key, expected_value in expected_metadata.items():
            if str(metadata.get(metadata_key, "")) != str(expected_value):
                raise RuntimeError(f"S3 audit exporter readback metadata mismatch for {metadata_key}")
        object_lock_mode = str(response.get("ObjectLockMode", ""))
        if object_lock_mode != self.object_lock_mode:
            raise RuntimeError("S3 audit exporter readback Object Lock mode mismatch")
        if not response.get("ObjectLockRetainUntilDate"):
            raise RuntimeError("S3 audit exporter readback retention timestamp is missing")

    def _client(self) -> Any:
        if not self.bucket:
            raise RuntimeError("S3 audit exporter requires a bucket")
        if self.client is not None:
            return self.client
        try:
            import boto3
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("S3 audit export requires optional dependency: boto3") from exc
        kwargs: dict[str, str] = {}
        if self.region_name:
            kwargs["region_name"] = self.region_name
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        self.client = boto3.client("s3", **kwargs)
        return self.client


def create_audit_exporter(
    uri: str | Path | None,
    *,
    s3_region: str = "",
    s3_endpoint_url: str = "",
    object_lock_mode: str = "",
    retention_days: int = 0,
) -> AuditExporterProtocol:
    """Resolve a deployment audit-export URI to a concrete exporter.

    Bare paths and file:// URIs write local tamper-evident NDJSON exports.
    s3:// URIs resolve to an optional boto3-backed Object Lock writer. The
    writer fails closed when the S3 client or dependency is unavailable.
    """

    raw = str(uri or "").strip()
    if not raw:
        return NoopAuditExporter()
    parsed = urlparse(raw)
    if parsed.scheme in {"", "file"} or (len(parsed.scheme) == 1 and len(raw) >= 3 and raw[1] == ":" and raw[2] in {"\\", "/"}):
        if parsed.scheme == "file":
            path = unquote(parsed.path)
            if parsed.netloc:
                path = f"//{parsed.netloc}{path}"
            if len(path) >= 3 and path[0] == "/" and path[2] == ":":
                path = path[1:]
        else:
            path = raw
        return LocalFileAuditExporter(Path(path))
    if parsed.scheme == "s3":
        query = parse_qs(parsed.query)
        object_lock_mode_resolved = (object_lock_mode or str(query.get("object_lock_mode", query.get("mode", ["COMPLIANCE"]))[0])).upper()
        retention_days_resolved = retention_days or _int_query_value(query.get("retention_days", query.get("retention", ["365"]))[0], default=365)
        return S3WormAuditExporter(
            bucket=parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            object_lock_mode=object_lock_mode_resolved,
            retention_days=retention_days_resolved,
            region_name=s3_region,
            endpoint_url=s3_endpoint_url,
        )
    return NoopAuditExporter(f"unsupported_audit_export_uri:{parsed.scheme}")


def build_checkpoint(
    events: tuple[Mapping[str, Any], ...],
    *,
    chain_id: str,
    from_sequence: int,
    to_sequence: int,
    export_uri: str,
    exported_to: str,
    object_lock_mode: str = "",
    retention_until: str = "",
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
        object_lock_mode=object_lock_mode,
        retention_until=retention_until,
        storage_uri=export_uri,
    )


def verify_audit_export(path: str | Path) -> AuditExportVerification:
    return LocalFileAuditExporter(Path(path)).verify_export()


def read_export_file(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    return tuple(json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip())


def audit_events_from_export_file(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    parsed = read_export_file(path)
    events = tuple(_event_from_line(item) for item in parsed[1:-1])
    if any(event is None for event in events):
        raise ValueError("audit export contains a malformed event line")
    return tuple(event for event in events if event is not None)


def verify_exported_chain(events: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    error = _verify_exported_chain(events)
    if error:
        return {"ok": False, "event_count": len(events), "error_code": error[0], "message": error[1]}
    return {"ok": True, "event_count": len(events), "error_code": "", "message": ""}


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


def _verify_manifest_hash(manifest: Mapping[str, Any]) -> tuple[str, str] | None:
    manifest_hash = str(manifest.get("manifest_hash", ""))
    if not manifest_hash:
        return ("missing_manifest_hash", "audit export manifest is missing manifest_hash")
    expected = content_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    if manifest_hash != expected:
        return ("manifest_hash_mismatch", "manifest hash does not match manifest payload")
    return None


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
    return read_export_file(path)


def _event_from_line(item: Mapping[str, Any]) -> Mapping[str, Any] | None:
    event = item.get("event") if item.get("type") == "audit_event" else None
    return event if isinstance(event, Mapping) else None


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _retention_until(retention_days: int) -> datetime:
    days = max(1, int(retention_days))
    return datetime.now(timezone.utc) + timedelta(days=days)


def _iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_query_value(value: object, *, default: int) -> int:
    try:
        return max(1, int(str(value)))
    except (TypeError, ValueError):
        return default


def _object_body_text(body: object) -> str:
    if body is None:
        return ""
    if hasattr(body, "read"):
        body = body.read()
    if isinstance(body, bytes):
        return body.decode("utf-8", "replace")
    return str(body)


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
