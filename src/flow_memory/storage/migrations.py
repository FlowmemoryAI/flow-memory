"""SQLite migration metadata and schema verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.crypto.hashes import content_hash
from flow_memory.storage.sqlite_store import SCHEMA_VERSION, TABLES, SQLiteStore

MIGRATION_TABLES = TABLES


@dataclass(frozen=True)
class MigrationStep:
    version: int
    name: str
    creates_tables: tuple[str, ...]
    description: str
    reversible: bool = False

    def as_record(self) -> Mapping[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "creates_tables": self.creates_tables,
            "description": self.description,
            "reversible": self.reversible,
        }


@dataclass(frozen=True)
class MigrationPlan:
    current_version: int
    steps: tuple[MigrationStep, ...]
    schema_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "current_version": self.current_version,
            "steps": tuple(step.as_record() for step in self.steps),
            "schema_hash": self.schema_hash,
        }


@dataclass(frozen=True)
class SchemaVerification:
    ok: bool
    expected_version: int
    observed_version: int | None
    expected_tables: tuple[str, ...]
    observed_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]
    schema_hash: str

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "expected_version": self.expected_version,
            "observed_version": self.observed_version,
            "expected_tables": self.expected_tables,
            "observed_tables": self.observed_tables,
            "missing_tables": self.missing_tables,
            "schema_hash": self.schema_hash,
        }


def migration_plan() -> MigrationPlan:
    step = MigrationStep(
        version=1,
        name="initial_local_store",
        creates_tables=TABLES,
        description="Create generic JSON payload tables for agents, runtime, audit, skills, marketplace, reputation, and memory state.",
        reversible=False,
    )
    return MigrationPlan(current_version=SCHEMA_VERSION, steps=(step,), schema_hash=schema_fingerprint(TABLES, SCHEMA_VERSION))


def schema_fingerprint(tables: tuple[str, ...] = TABLES, version: int = SCHEMA_VERSION) -> str:
    return content_hash({"schema_version": version, "tables": tables})


def verify_schema(store: SQLiteStore) -> SchemaVerification:
    with store._connection() as conn:  # noqa: SLF001 - storage package internal verification helper
        version_row = conn.execute("select version from schema_version order by version desc limit 1").fetchone()
        observed_version = int(version_row["version"]) if version_row else None
        observed_tables = tuple(
            sorted(
                str(row["name"])
                for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()
                if str(row["name"]) != "sqlite_sequence"
            )
        )
    expected_tables = tuple(sorted(("schema_version", *TABLES)))
    missing_tables = tuple(table for table in expected_tables if table not in observed_tables)
    ok = observed_version == SCHEMA_VERSION and not missing_tables
    return SchemaVerification(
        ok=ok,
        expected_version=SCHEMA_VERSION,
        observed_version=observed_version,
        expected_tables=expected_tables,
        observed_tables=observed_tables,
        missing_tables=missing_tables,
        schema_hash=schema_fingerprint(TABLES, SCHEMA_VERSION),
    )
