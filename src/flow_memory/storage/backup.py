"""Portable SQLiteStore backup and restore helpers."""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from flow_memory.crypto.hashes import content_hash
from flow_memory.storage.sqlite_store import SCHEMA_VERSION, TABLES, SQLiteStore

BACKUP_FORMAT = "flow-memory-storage-backup-v1"


@dataclass(frozen=True)
class BackupTableSummary:
    name: str
    row_count: int
    content_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {"name": self.name, "row_count": self.row_count, "content_hash": self.content_hash}


@dataclass(frozen=True)
class BackupManifest:
    format: str
    schema_version: int
    table_summaries: tuple[BackupTableSummary, ...]
    root_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "format": self.format,
            "schema_version": self.schema_version,
            "table_summaries": tuple(summary.as_record() for summary in self.table_summaries),
            "root_hash": self.root_hash,
        }


def create_backup(store: SQLiteStore) -> Mapping[str, Any]:
    """Return a deterministic JSON-serializable backup bundle."""

    tables = {table: tuple(store.list(table)) for table in TABLES}
    summaries = tuple(
        BackupTableSummary(name=table, row_count=len(rows), content_hash=content_hash(rows))
        for table, rows in tables.items()
    )
    root_hash = content_hash({"format": BACKUP_FORMAT, "schema_version": SCHEMA_VERSION, "tables": tables})
    manifest = BackupManifest(
        format=BACKUP_FORMAT,
        schema_version=SCHEMA_VERSION,
        table_summaries=summaries,
        root_hash=root_hash,
    )
    return {"manifest": manifest.as_record(), "tables": tables}


def write_backup(store: SQLiteStore, path: str | Path) -> Path:
    """Write a deterministic storage backup JSON file."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(create_backup(store), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return output


def read_backup(path: str | Path) -> Mapping[str, Any]:
    """Read and validate a storage backup JSON file."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("backup must be a JSON object")
    bundle = cast(Mapping[str, Any], raw)
    validate_backup(bundle)
    return bundle


def validate_backup(bundle: Mapping[str, Any]) -> BackupManifest:
    """Validate backup hashes and return its manifest."""

    manifest_record = bundle.get("manifest")
    tables = bundle.get("tables")
    if not isinstance(manifest_record, Mapping) or not isinstance(tables, Mapping):
        raise ValueError("backup must contain manifest and tables")
    if manifest_record.get("format") != BACKUP_FORMAT:
        raise ValueError("unsupported backup format")
    if int(manifest_record.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError("unsupported backup schema version")

    missing = tuple(table for table in TABLES if table not in tables)
    if missing:
        raise ValueError("backup missing tables: " + ", ".join(missing))

    summaries = tuple(_summary_from_record(record) for record in manifest_record.get("table_summaries", ()))
    summary_by_name = {summary.name: summary for summary in summaries}
    for table in TABLES:
        rows = tuple(tables.get(table, ()))
        summary = summary_by_name.get(table)
        if summary is None:
            raise ValueError(f"backup missing summary for table {table}")
        if summary.row_count != len(rows):
            raise ValueError(f"backup row count mismatch for table {table}")
        if summary.content_hash != content_hash(rows):
            raise ValueError(f"backup content hash mismatch for table {table}")

    expected_root = content_hash({"format": BACKUP_FORMAT, "schema_version": SCHEMA_VERSION, "tables": {table: tuple(tables[table]) for table in TABLES}})
    if manifest_record.get("root_hash") != expected_root:
        raise ValueError("backup root hash mismatch")

    return BackupManifest(format=BACKUP_FORMAT, schema_version=SCHEMA_VERSION, table_summaries=summaries, root_hash=expected_root)


def restore_backup(bundle: Mapping[str, Any], target: SQLiteStore, *, overwrite: bool = False) -> BackupManifest:
    """Restore a validated backup into a target store.

    When ``overwrite`` is false, the restore fails if any target table already has
    rows. This prevents accidentally merging or replacing live state.
    """

    manifest = validate_backup(bundle)
    tables = bundle["tables"]
    if not overwrite:
        populated = tuple(table for table in TABLES if target.list(table))
        if populated:
            raise ValueError("target store is not empty: " + ", ".join(populated))
    for table in TABLES:
        for index, row in enumerate(tables[table]):
            item_id = _row_id(table, row, index)
            target.put(table, item_id, row)
    return manifest


def restore_backup_file(path: str | Path, target: SQLiteStore, *, overwrite: bool = False) -> BackupManifest:
    return restore_backup(read_backup(path), target, overwrite=overwrite)


def _summary_from_record(record: object) -> BackupTableSummary:
    if not isinstance(record, Mapping):
        raise ValueError("backup table summary must be an object")
    return BackupTableSummary(
        name=str(record.get("name")),
        row_count=int(record.get("row_count", -1)),
        content_hash=str(record.get("content_hash")),
    )


def _row_id(table: str, row: object, index: int) -> str:
    if isinstance(row, Mapping):
        for key in ("id", "agent_id", "state_id", "goal_id", "plan_id", "graph_id", "event_id", "audit_id", "skill_id", "task_id", "bid_id", "escrow_id", "settlement_id", "dispute_id", "slashing_id", "reputation_id", "record_id"):
            value = row.get(key)
            if value:
                return str(value)
    return f"{table}_{index:06d}_{content_hash(row)[:12]}"
