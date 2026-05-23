"""Local storage retention and compaction policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.storage.sqlite_store import TABLES, SQLiteStore

PROTECTED_TABLES = frozenset({"audit_events", "settlements", "slashing_events", "reputation_updates"})


@dataclass(frozen=True)
class RetentionRule:
    table: str
    max_rows: int

    def __post_init__(self) -> None:
        if self.table not in TABLES:
            raise ValueError(f"unknown retention table: {self.table}")
        if self.max_rows < 0:
            raise ValueError("max_rows must be non-negative")

    def as_record(self) -> Mapping[str, Any]:
        return {"table": self.table, "max_rows": self.max_rows}


@dataclass(frozen=True)
class RetentionPolicy:
    rules: tuple[RetentionRule, ...]
    allow_protected_prune: bool = False
    vacuum_after: bool = False

    def as_record(self) -> Mapping[str, Any]:
        return {
            "rules": tuple(rule.as_record() for rule in self.rules),
            "allow_protected_prune": self.allow_protected_prune,
            "vacuum_after": self.vacuum_after,
        }


@dataclass(frozen=True)
class RetentionTableResult:
    table: str
    before_count: int
    after_count: int
    deleted_ids: tuple[str, ...] = ()
    skipped: bool = False
    reason: str = ""

    def as_record(self) -> Mapping[str, Any]:
        return {
            "table": self.table,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "deleted_ids": self.deleted_ids,
            "skipped": self.skipped,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RetentionReport:
    ok: bool
    table_results: tuple[RetentionTableResult, ...]
    vacuumed: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "vacuumed": self.vacuumed,
            "errors": self.errors,
            "table_results": tuple(result.as_record() for result in self.table_results),
        }


def apply_retention_policy(store: SQLiteStore, policy: RetentionPolicy) -> RetentionReport:
    """Apply deterministic row-count retention rules.

    Rows are pruned by SQLiteStore ID order because the generic store does not
    require a timestamp column in every table. Protected economic/audit tables are
    skipped unless the policy explicitly allows pruning them.
    """

    results: list[RetentionTableResult] = []
    errors: list[str] = []

    for rule in policy.rules:
        before = store.count(rule.table)
        if rule.table in PROTECTED_TABLES and not policy.allow_protected_prune:
            results.append(
                RetentionTableResult(
                    table=rule.table,
                    before_count=before,
                    after_count=before,
                    skipped=True,
                    reason="protected table requires allow_protected_prune",
                )
            )
            continue

        ids = store.ids(rule.table)
        delete_count = max(0, len(ids) - rule.max_rows)
        deleted = ids[:delete_count]
        for item_id in deleted:
            if not store.delete(rule.table, item_id):
                errors.append(f"failed to delete {rule.table}:{item_id}")
        results.append(
            RetentionTableResult(
                table=rule.table,
                before_count=before,
                after_count=store.count(rule.table),
                deleted_ids=tuple(deleted),
            )
        )

    vacuumed = False
    if policy.vacuum_after and not errors:
        store.vacuum()
        vacuumed = True

    return RetentionReport(ok=not errors, table_results=tuple(results), vacuumed=vacuumed, errors=tuple(errors))


def policy_from_mapping(value: Mapping[str, Any]) -> RetentionPolicy:
    rules = tuple(RetentionRule(table=str(rule["table"]), max_rows=int(rule["max_rows"])) for rule in value.get("rules", ()))
    return RetentionPolicy(
        rules=rules,
        allow_protected_prune=bool(value.get("allow_protected_prune", False)),
        vacuum_after=bool(value.get("vacuum_after", False)),
    )
