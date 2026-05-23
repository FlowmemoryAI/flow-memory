"""Storage integrity checks against deterministic backups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.storage.backup import BackupManifest, create_backup, read_backup, validate_backup
from flow_memory.storage.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class StorageIntegrityReport:
    ok: bool
    live_root_hash: str
    backup_root_hash: str
    errors: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "live_root_hash": self.live_root_hash,
            "backup_root_hash": self.backup_root_hash,
            "errors": self.errors,
        }


def live_backup_manifest(store: SQLiteStore) -> BackupManifest:
    """Return the backup manifest that represents the current store state."""

    return validate_backup(create_backup(store))


def compare_store_to_backup(store: SQLiteStore, backup: Mapping[str, Any]) -> StorageIntegrityReport:
    """Compare live store root hash to a validated backup root hash."""

    backup_manifest = validate_backup(backup)
    live_manifest = live_backup_manifest(store)
    errors = []
    if live_manifest.schema_version != backup_manifest.schema_version:
        errors.append("schema version mismatch")
    if live_manifest.root_hash != backup_manifest.root_hash:
        errors.append("root hash mismatch")
    return StorageIntegrityReport(
        ok=not errors,
        live_root_hash=live_manifest.root_hash,
        backup_root_hash=backup_manifest.root_hash,
        errors=tuple(errors),
    )


def compare_store_to_backup_file(store: SQLiteStore, backup_path: str | Path) -> StorageIntegrityReport:
    return compare_store_to_backup(store, read_backup(backup_path))
