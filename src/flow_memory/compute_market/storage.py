"""Durable persistence for Flow Memory Compute Market records."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from flow_memory.compute_market.config import ensure_database_parent
from flow_memory.compute_market.models import SCHEMA_VERSION
from flow_memory.crypto.hashes import content_hash

COMPUTE_MARKET_STORAGE_VERSION = SCHEMA_VERSION
COMPUTE_RECORD_TYPES: tuple[str, ...] = (
    "compute_provider",
    "compute_route",
    "compute_quote",
    "compute_capacity_window",
    "compute_reservation",
    "capacity_auction",
    "intelligence_plan",
    "compute_price_snapshot",
    "route_price_index",
    "provider_price_index",
    "price_anomaly",
    "price_forecast",
    "intelligence_usage_record",
    "compute_statement",
    "compute_intent",
    "payment_intent",
    "payment_plan",
    "settlement_intent",
    "task_economic_profile",
    "agent_budget_policy",
    "compute_market_policy",
    "route_decision",
    "provider_capability",
    "unit_price_snapshot",
    "price_curve",
    "economic_memory",
    "audit_event",
    "provider_health_snapshot",
    "quote_cache_entry",
    "market_provider_application",
    "provider_secret_ref",
    "provider_reputation",
    "quote_replay_guard",
    "quote_drift_observation",
    "provider_fraud_signal",
    "provider_receipt_replay_guard",
    "provider_callback_replay_guard",
    "compute_job",
    "compute_job_event",
    "compute_job_artifact",
    "billing_account",
    "billing_quota",
    "credit_balance",
    "credit_transaction",
    "payment_event",
    "billing_invoice",
    "provider_payout",
    "usage_charge",
    "provider_sla_penalty",
    "refund",
    "reconciliation_run",
    "alert_acknowledgement",
    "alert_delivery",
    "error_tracking_event",
    "otlp_export_delivery",
    "audit_checkpoint_manifest",
    "audit_replay_run",
)


@dataclass(frozen=True)
class RecordPage:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str
    limit: int

    def as_record(self) -> dict[str, object]:
        return {"records": self.records, "next_cursor": self.next_cursor, "limit": self.limit}


@dataclass(frozen=True)
class AuditChainVerification:
    ok: bool
    chain_id: str
    event_count: int
    first_broken_sequence: int | None = None
    error_code: str = ""
    message: str = ""

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "chain_id": self.chain_id,
            "event_count": self.event_count,
            "first_broken_sequence": self.first_broken_sequence,
            "error_code": self.error_code,
            "message": self.message,
        }


@dataclass(frozen=True)
class MigrationResult:
    ok: bool
    version: int
    applied: tuple[str, ...]
    schema_hash: str

    def as_record(self) -> dict[str, object]:
        return {"ok": self.ok, "version": self.version, "applied": self.applied, "schema_hash": self.schema_hash}


class ComputeMarketStore:
    """SQLite-backed record store with a managed-SQL migration contract.

    The concrete implementation remains SQLite for local/single-node use.  The
    storage metadata and migration plan are explicit so production deployments
    can run the same schema on a managed SQL adapter without relying on process
    local state.
    """

    def __init__(
        self,
        path: str | Path = ".flow_memory/compute_market.sqlite3",
        *,
        backend: str = "sqlite",
        timeout_ms: int = 5_000,
        pool_size: int = 4,
        migrations_enabled: bool = True,
    ) -> None:
        self.database_url = str(path)
        self.backend = _resolve_backend(backend, self.database_url)
        if self.backend != "sqlite":
            raise ValueError("ComputeMarketStore currently requires sqlite backend; use migration_plan() for managed SQL schema deployment")
        self.path = _sqlite_path(self.database_url)
        self.timeout_ms = timeout_ms
        self.pool_size = pool_size
        self.migrations_enabled = migrations_enabled
        self._memory = self.path == ":memory:"
        ensure_database_parent(self.path)
        self.conn = self._open()
        if self.migrations_enabled:
            self.migrate()
        if not self._memory:
            self.conn.close()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=max(0.001, self.timeout_ms / 1000.0))
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma journal_mode = wal" if not self._memory else "pragma journal_mode = memory")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if self._memory:
            yield self.conn
            return
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    def migrate(self) -> MigrationResult:
        applied: list[str] = []
        with self._connection() as conn:
            conn.execute(
                "create table if not exists compute_market_migrations "
                "(version integer primary key, name text not null, applied_at text not null)"
            )
            conn.execute(
                "create table if not exists compute_market_records ("
                "record_type text not null, "
                "record_id text not null, "
                "tenant_id text not null default '', "
                "workspace_id text not null default '', "
                "agent_id text not null default '', "
                "goal_id text not null default '', "
                "provider_id text not null default '', "
                "route_id text not null default '', "
                "task_type text not null default '', "
                "task_hash text not null default '', "
                "request_id text not null default '', "
                "actor_id text not null default '', "
                "action text not null default '', "
                "status text not null default '', "
                "chain_id text not null default '', "
                "sequence_number integer not null default 0, "
                "event_hash text not null default '', "
                "previous_hash text not null default '', "
                "created_at text not null, "
                "updated_at text not null, "
                "expires_at text not null default '', "
                "idempotency_key text not null default '', "
                "archived integer not null default 0, "
                "payload text not null, "
                "primary key(record_type, record_id))"
            )
            existing_columns = {
                str(row["name"])
                for row in conn.execute("pragma table_info(compute_market_records)").fetchall()
            }
            for column, ddl in {
                "request_id": "text not null default ''",
                "actor_id": "text not null default ''",
                "action": "text not null default ''",
                "chain_id": "text not null default ''",
                "sequence_number": "integer not null default 0",
                "event_hash": "text not null default ''",
                "previous_hash": "text not null default ''",
            }.items():
                if column not in existing_columns:
                    conn.execute(f"alter table compute_market_records add column {column} {ddl}")
            indexes = (
                ("idx_compute_records_type_created", "record_type, created_at"),
                ("idx_compute_records_agent", "record_type, agent_id"),
                ("idx_compute_records_goal", "record_type, goal_id"),
                ("idx_compute_records_provider", "record_type, provider_id"),
                ("idx_compute_records_route", "record_type, route_id"),
                ("idx_compute_records_task", "record_type, task_type, task_hash"),
                ("idx_compute_records_status", "record_type, status"),
                ("idx_compute_records_expires", "record_type, expires_at"),
                ("idx_compute_records_idempotency", "record_type, idempotency_key"),
                ("idx_compute_records_request", "record_type, request_id"),
                ("idx_compute_records_actor", "record_type, actor_id"),
                ("idx_compute_records_chain", "record_type, chain_id, sequence_number"),
                ("idx_compute_records_event_hash", "record_type, event_hash"),
                ("idx_compute_records_action", "record_type, action"),
                ("idx_compute_records_tenant", "record_type, tenant_id, workspace_id"),
            )
            for name, columns in indexes:
                conn.execute(f"create index if not exists {name} on compute_market_records ({columns})")
            row = conn.execute(
                "select version from compute_market_migrations where version = ?",
                (COMPUTE_MARKET_STORAGE_VERSION,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "insert into compute_market_migrations(version, name, applied_at) values (?, ?, ?)",
                    (COMPUTE_MARKET_STORAGE_VERSION, "compute_market_production_records_v3_audit_chain", utc_now_iso()),
                )
                applied.append("compute_market_production_records_v3_audit_chain")
            conn.commit()
        return MigrationResult(
            ok=True,
            version=COMPUTE_MARKET_STORAGE_VERSION,
            applied=tuple(applied),
            schema_hash=schema_hash(),
        )

    def put_record(
        self,
        record_type: str,
        record_id: str,
        payload: Mapping[str, Any],
        *,
        tenant_id: str = "",
        workspace_id: str = "",
        agent_id: str = "",
        goal_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        task_type: str = "",
        task_hash: str = "",
        status: str = "",
        expires_at: str = "",
        idempotency_key: str = "",
        request_id: str = "",
        actor_id: str = "",
        action: str = "",
        archived: bool = False,
    ) -> None:
        if record_type not in COMPUTE_RECORD_TYPES:
            raise ValueError(f"unknown compute market record type: {record_type}")
        now = utc_now_iso()
        existing = self.get_record(record_type, record_id)
        created_at = str((existing or payload).get("created_at") or now)
        normalized = dict(payload)
        normalized.setdefault("record_id", record_id)
        normalized.setdefault("created_at", created_at)
        normalized["updated_at"] = now
        with self._connection() as conn:
            conn.execute(
                "insert or replace into compute_market_records("
                "record_type, record_id, tenant_id, workspace_id, agent_id, goal_id, provider_id, route_id, "
                "task_type, task_hash, request_id, actor_id, action, status, chain_id, sequence_number, "
                "event_hash, previous_hash, created_at, updated_at, expires_at, idempotency_key, archived, payload) "
                "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_type,
                    record_id,
                    tenant_id or str(normalized.get("tenant_id", "")),
                    workspace_id or str(normalized.get("workspace_id", "")),
                    agent_id or str(normalized.get("agent_id", "")),
                    goal_id or str(normalized.get("goal_id", "")),
                    provider_id or str(normalized.get("provider_id", "")),
                    route_id or str(normalized.get("route_id", "")),
                    task_type or str(normalized.get("task_type", "")),
                    task_hash or str(normalized.get("task_hash", "")),
                    request_id or str(normalized.get("request_id", "")),
                    actor_id or str(normalized.get("actor_id", "")),
                    action or str(normalized.get("action", "")),
                    status or str(normalized.get("status", normalized.get("policy_result", ""))),
                    str(normalized.get("chain_id", "")),
                    int(normalized.get("sequence_number", 0) or 0),
                    str(normalized.get("event_hash", "")),
                    str(normalized.get("previous_hash", "")),
                    created_at,
                    now,
                    expires_at or str(normalized.get("expires_at", "")),
                    idempotency_key or str(normalized.get("idempotency_key", "")),
                    1 if archived else 0,
                    json.dumps(normalized, sort_keys=True, default=str),
                ),
            )
            conn.commit()

    def put_record_if_state(
        self,
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        *,
        expected_actor_id: str = "",
        expires_at_before: str = "",
        tenant_id: str = "",
        workspace_id: str = "",
        agent_id: str = "",
        goal_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        task_type: str = "",
        task_hash: str = "",
        status: str = "",
        expires_at: str = "",
        idempotency_key: str = "",
        request_id: str = "",
        actor_id: str = "",
        action: str = "",
        archived: bool = False,
    ) -> bool:
        if record_type not in COMPUTE_RECORD_TYPES:
            raise ValueError(f"unknown compute market record type: {record_type}")
        expected = tuple(str(item) for item in expected_statuses if str(item))
        if not expected:
            return False
        now = utc_now_iso()
        created_at = str(payload.get("created_at") or now)
        normalized = dict(payload)
        normalized.setdefault("record_id", record_id)
        normalized.setdefault("created_at", created_at)
        normalized["updated_at"] = now
        status_placeholders = ", ".join("?" for _ in expected)
        where = [f"record_type = ? and record_id = ? and status in ({status_placeholders})"]
        where_values: list[Any] = [record_type, record_id, *expected]
        if expected_actor_id:
            where.append("actor_id = ?")
            where_values.append(expected_actor_id)
        if expires_at_before:
            where.append("expires_at <> '' and expires_at <= ?")
            where_values.append(expires_at_before)
        values: list[Any] = [
            tenant_id or str(normalized.get("tenant_id", "")),
            workspace_id or str(normalized.get("workspace_id", "")),
            agent_id or str(normalized.get("agent_id", "")),
            goal_id or str(normalized.get("goal_id", "")),
            provider_id or str(normalized.get("provider_id", "")),
            route_id or str(normalized.get("route_id", "")),
            task_type or str(normalized.get("task_type", "")),
            task_hash or str(normalized.get("task_hash", "")),
            request_id or str(normalized.get("request_id", "")),
            actor_id or str(normalized.get("actor_id", "")),
            action or str(normalized.get("action", "")),
            status or str(normalized.get("status", normalized.get("policy_result", ""))),
            str(normalized.get("chain_id", "")),
            int(normalized.get("sequence_number", 0) or 0),
            str(normalized.get("event_hash", "")),
            str(normalized.get("previous_hash", "")),
            created_at,
            now,
            expires_at or str(normalized.get("expires_at", "")),
            idempotency_key or str(normalized.get("idempotency_key", "")),
            1 if archived else 0,
            json.dumps(normalized, sort_keys=True, default=str),
            *where_values,
        ]
        sql = (
            "update compute_market_records set "
            "tenant_id = ?, workspace_id = ?, agent_id = ?, goal_id = ?, provider_id = ?, route_id = ?, "
            "task_type = ?, task_hash = ?, request_id = ?, actor_id = ?, action = ?, status = ?, "
            "chain_id = ?, sequence_number = ?, event_hash = ?, previous_hash = ?, created_at = ?, "
            "updated_at = ?, expires_at = ?, idempotency_key = ?, archived = ?, payload = ? "
            f"where {' and '.join(where)}"
        )
        with self._connection() as conn:
            cursor = conn.execute(sql, tuple(values))
            conn.commit()
            return cursor.rowcount == 1

    def get_record(self, record_type: str, record_id: str) -> Mapping[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "select payload from compute_market_records where record_type = ? and record_id = ?",
                (record_type, record_id),
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def find_by_idempotency(self, record_type: str, idempotency_key: str) -> Mapping[str, Any] | None:
        if not idempotency_key:
            return None
        with self._connection() as conn:
            row = conn.execute(
                "select payload from compute_market_records where record_type = ? and idempotency_key = ? "
                "order by created_at desc, record_id desc limit 1",
                (record_type, idempotency_key),
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def list_records(
        self,
        record_type: str,
        *,
        filters: Mapping[str, Any] | None = None,
        limit: int = 100,
        cursor: str = "",
        include_archived: bool = False,
    ) -> RecordPage:
        offset = _cursor_to_offset(cursor)
        bounded_limit = min(max(1, int(limit)), 500)
        where = ["record_type = ?"]
        values: list[Any] = [record_type]
        if not include_archived:
            where.append("archived = 0")
        for column in (
            "tenant_id",
            "workspace_id",
            "agent_id",
            "goal_id",
            "provider_id",
            "route_id",
            "task_type",
            "task_hash",
            "status",
            "request_id",
            "actor_id",
            "action",
        ):
            value = (filters or {}).get(column)
            if value not in (None, ""):
                where.append(f"{column} = ?")
                values.append(str(value))
        start_time = str((filters or {}).get("start_time", ""))
        end_time = str((filters or {}).get("end_time", ""))
        if start_time:
            where.append("created_at >= ?")
            values.append(start_time)
        if end_time:
            where.append("created_at <= ?")
            values.append(end_time)
        sql = (
            "select payload from compute_market_records where "
            + " and ".join(where)
            + " order by created_at, record_id limit ? offset ?"
        )
        values.extend((bounded_limit + 1, offset))
        with self._connection() as conn:
            rows = conn.execute(sql, tuple(values)).fetchall()
        payloads = tuple(json.loads(str(row["payload"])) for row in rows[:bounded_limit])
        next_cursor = str(offset + bounded_limit) if len(rows) > bounded_limit else ""
        return RecordPage(records=payloads, next_cursor=next_cursor, limit=bounded_limit)

    def delete_record(self, record_type: str, record_id: str) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "delete from compute_market_records where record_type = ? and record_id = ?",
                (record_type, record_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def count_records(self, record_type: str) -> int:
        with self._connection() as conn:
            row = conn.execute(
                "select count(*) as count from compute_market_records where record_type = ?",
                (record_type,),
            ).fetchone()
        return int(row["count"])

    def quote_cache_key(self, provider_id: str, route_id: str, task_hash: str, policy_hash: str) -> str:
        return deterministic_id("quote_cache", {
            "provider_id": provider_id,
            "route_id": route_id,
            "task_hash": task_hash,
            "policy_hash": policy_hash,
        })

    def append_audit_event(self, payload: Mapping[str, Any], *, chain_id: str = "") -> Mapping[str, Any]:
        event = dict(payload)
        resolved_chain = chain_id or _audit_chain_id(event)
        previous = self._latest_audit_event(resolved_chain)
        event.setdefault("record_id", str(event["audit_event_id"]))
        event.setdefault("created_at", utc_now_iso())
        previous_hash = str(previous.get("event_hash", "")) if previous else ""
        sequence_number = int(previous.get("sequence_number", 0) or 0) + 1 if previous else 1
        event["chain_id"] = resolved_chain
        event["sequence_number"] = sequence_number
        event["previous_hash"] = previous_hash
        event["hash_algorithm"] = "sha256"
        event["canonical_payload_hash"] = canonical_audit_payload_hash(event)
        event["event_hash"] = audit_event_hash(event)
        event.setdefault("verification_status", "unverified")
        self.put_record(
            "audit_event",
            str(event["audit_event_id"]),
            event,
            tenant_id=str(event.get("tenant_id", "")),
            workspace_id=str(event.get("workspace_id", "")),
            agent_id=str(event.get("agent_id", "")),
            goal_id=str(event.get("goal_id", "")),
            provider_id=str(event.get("provider_id", "")),
            route_id=str(event.get("route_id", "")),
            status=str(event.get("result", "")),
            request_id=str(event.get("request_id", "")),
            actor_id=str(event.get("actor_id", "")),
            action=str(event.get("action", "")),
        )
        return event

    def verify_audit_chain(self, *, chain_id: str = "") -> AuditChainVerification:
        requested_chain = "" if chain_id == "all" else chain_id
        chains = (requested_chain,) if requested_chain else self.audit_chain_ids()
        if not chains:
            return AuditChainVerification(True, chain_id or "compute-market-audit:global", 0)
        first_failure: AuditChainVerification | None = None
        total = 0
        for chain in chains:
            events = self._audit_events_for_chain(chain)
            total += len(events)
            previous_hash = ""
            expected_sequence = 1
            for event in events:
                sequence = int(event.get("sequence_number", 0) or 0)
                if sequence != expected_sequence:
                    result = AuditChainVerification(False, chain, len(events), expected_sequence, "audit_sequence_gap", "audit chain has a missing or out-of-order event")
                    first_failure = first_failure or result
                    break
                if str(event.get("previous_hash", "")) != previous_hash:
                    result = AuditChainVerification(False, chain, len(events), sequence, "audit_previous_hash_mismatch", "audit event previous_hash does not match prior event_hash")
                    first_failure = first_failure or result
                    break
                canonical_hash = canonical_audit_payload_hash(event)
                if str(event.get("canonical_payload_hash", "")) != canonical_hash:
                    result = AuditChainVerification(False, chain, len(events), sequence, "audit_payload_hash_mismatch", "audit event payload was modified after append")
                    first_failure = first_failure or result
                    break
                event_hash = audit_event_hash(event)
                if str(event.get("event_hash", "")) != event_hash:
                    result = AuditChainVerification(False, chain, len(events), sequence, "audit_event_hash_mismatch", "audit event hash does not match canonical payload and previous_hash")
                    first_failure = first_failure or result
                    break
                previous_hash = event_hash
                expected_sequence += 1
        if first_failure is not None:
            return first_failure
        return AuditChainVerification(True, chain_id or "all", total)

    def audit_chain_ids(self) -> tuple[str, ...]:
        records = self._all_records("audit_event")
        return tuple(sorted({str(record.get("chain_id", "")) for record in records if record.get("chain_id")}))

    def storage_status(self) -> Mapping[str, Any]:
        migration = self.migration_status()
        return {
            "backend": self.backend,
            "database_url": self.database_url if "://" not in self.database_url else self.database_url.split("://", 1)[0] + "://***",
            "sqlite_path": self.path,
            "pool_size": self.pool_size,
            "timeout_ms": self.timeout_ms,
            "migrations_enabled": self.migrations_enabled,
            "migrations_current": migration["current"],
            "migration_version": migration["version"],
            "schema_hash": schema_hash(),
            "managed_sql_ready": self.backend == "sqlite",
            "production_note": "SQLite is local/single-node; managed SQL deployments must run the schema from migration_plan().",
        }

    def migration_status(self) -> Mapping[str, Any]:
        if not self.migrations_enabled:
            return {"current": False, "version": 0, "expected_version": COMPUTE_MARKET_STORAGE_VERSION, "reason": "migrations_disabled"}
        try:
            with self._connection() as conn:
                row = conn.execute("select max(version) as version from compute_market_migrations").fetchone()
            version = int(row["version"] or 0) if row else 0
        except sqlite3.Error as exc:
            return {"current": False, "version": 0, "expected_version": COMPUTE_MARKET_STORAGE_VERSION, "reason": f"migration_status_failed:{type(exc).__name__}"}
        return {"current": version >= COMPUTE_MARKET_STORAGE_VERSION, "version": version, "expected_version": COMPUTE_MARKET_STORAGE_VERSION, "reason": ""}

    def _latest_audit_event(self, chain_id: str) -> Mapping[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "select payload from compute_market_records where record_type = 'audit_event' and chain_id = ? "
                "order by sequence_number desc, created_at desc limit 1",
                (chain_id,),
            ).fetchone()
        return json.loads(str(row["payload"])) if row else None

    def _audit_events_for_chain(self, chain_id: str) -> tuple[Mapping[str, Any], ...]:
        with self._connection() as conn:
            rows = conn.execute(
                "select payload from compute_market_records where record_type = 'audit_event' and chain_id = ? "
                "order by sequence_number asc, created_at asc, record_id asc",
                (chain_id,),
            ).fetchall()
        return tuple(json.loads(str(row["payload"])) for row in rows)

    def _all_records(self, record_type: str) -> tuple[Mapping[str, Any], ...]:
        with self._connection() as conn:
            rows = conn.execute(
                "select payload from compute_market_records where record_type = ? order by created_at asc, record_id asc",
                (record_type,),
            ).fetchall()
        return tuple(json.loads(str(row["payload"])) for row in rows)

    def migration_history(self) -> Mapping[str, Any]:
        with self._connection() as conn:
            rows = conn.execute(
                "select version, name, applied_at from compute_market_migrations order by version"
            ).fetchall()
        history = tuple({"version": int(row["version"]), "name": str(row["name"]), "applied_at": str(row["applied_at"])} for row in rows)
        return {
            "ok": True,
            "backend": self.backend,
            "migration_lock": "sqlite_single_writer",
            "history": history,
        }

    def schema_verification(self) -> Mapping[str, Any]:
        required_tables = ("compute_market_records", "compute_market_migrations")
        required_indexes = _sqlite_required_index_names()
        with self._connection() as conn:
            tables = {
                str(row["name"])
                for row in conn.execute(
                    "select name from sqlite_master where type = 'table' and name in (?, ?)",
                    required_tables,
                ).fetchall()
            }
            indexes = {
                str(row["name"])
                for row in conn.execute(
                    "select name from sqlite_master where type = 'index'"
                ).fetchall()
            }
        missing_tables = tuple(name for name in required_tables if name not in tables)
        missing_indexes = tuple(name for name in required_indexes if name not in indexes)
        return {
            "ok": not missing_tables and not missing_indexes,
            "backend": self.backend,
            "required_tables": required_tables,
            "missing_tables": missing_tables,
            "required_index_count": len(required_indexes),
            "missing_indexes": missing_indexes,
        }

    def production_readiness_check(self) -> Mapping[str, Any]:
        return {
            "ok": False,
            "production_ready": False,
            "managed_sql_confirmed": False,
            "backend": self.backend,
            "reason": "sqlite_disallowed_in_production",
            "requires": "postgresql",
        }
    def close(self) -> None:
        if self._memory:
            self.conn.close()


def deterministic_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return str(f"{prefix}_{content_hash(payload)[:24]}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

_AUDIT_INTEGRITY_FIELDS = frozenset(
    {
        "previous_hash",
        "event_hash",
        "hash_algorithm",
        "chain_id",
        "sequence_number",
        "canonical_payload_hash",
        "signed_at",
        "verification_status",
        "updated_at",
    }
)


def canonical_audit_payload_hash(event: Mapping[str, Any]) -> str:
    payload = {str(key): value for key, value in event.items() if str(key) not in _AUDIT_INTEGRITY_FIELDS}
    return str(content_hash(payload))


def audit_event_hash(event: Mapping[str, Any]) -> str:
    return str(
        content_hash(
            {
                "chain_id": str(event.get("chain_id", "")),
                "sequence_number": int(event.get("sequence_number", 0) or 0),
                "previous_hash": str(event.get("previous_hash", "")),
                "canonical_payload_hash": str(event.get("canonical_payload_hash", "")),
                "hash_algorithm": "sha256",
            }
        )
    )


def _audit_chain_id(event: Mapping[str, Any]) -> str:
    tenant = str(event.get("tenant_id") or event.get("workspace_id") or "")
    return f"compute-market-audit:{tenant or 'global'}"


def _resolve_backend(backend: str, database_url: str) -> str:
    normalized = (backend or "").strip().lower()
    if normalized:
        return "postgresql" if normalized in {"postgres", "postgresql"} else normalized
    if database_url.startswith(("postgres://", "postgresql://")):
        return "postgresql"
    return "sqlite"


def _sqlite_path(database_url: str) -> str:
    if database_url == ":memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        path = database_url[len("sqlite:///"):]
        return path or ":memory:"
    if database_url.startswith("sqlite://"):
        path = database_url[len("sqlite://"):]
        return path or ":memory:"
    return database_url


def schema_hash() -> str:
    return str(content_hash({"version": COMPUTE_MARKET_STORAGE_VERSION, "record_types": COMPUTE_RECORD_TYPES}))


def migration_plan() -> Mapping[str, Any]:
    return {
        "current_version": COMPUTE_MARKET_STORAGE_VERSION,
        "schema_hash": schema_hash(),
        "record_types": COMPUTE_RECORD_TYPES,
        "steps": (
            {
                "version": COMPUTE_MARKET_STORAGE_VERSION,
                "name": "compute_market_production_records_v6_intelligence_utility",
                "creates_tables": ("compute_market_records", "compute_market_migrations"),
                "postgres_tables": (
                    "compute_market_provider_applications",
                    "compute_provider_secret_refs",
                    "compute_provider_reputation",
                    "compute_quote_replay_guard",
                    "compute_provider_callback_replay_guard",
                    "compute_quote_drift_observations",
                    "compute_jobs",
                    "compute_job_events",
                    "compute_job_artifacts",
                    "compute_billing_accounts",
                    "compute_credit_balances",
                    "compute_credit_transactions",
                    "compute_payment_events",
                    "compute_provider_payouts",
                    "compute_usage_charges",
                    "compute_refunds",
                    "compute_reconciliation_runs",
                    "compute_audit_checkpoint_manifests",
                    "compute_audit_replay_runs",
                    "compute_intelligence_plans",
                    "compute_price_snapshots",
                    "compute_route_price_indexes",
                    "compute_provider_price_indexes",
                    "compute_price_anomalies",
                    "compute_price_forecasts",
                    "compute_intelligence_usage_records",
                    "compute_statements",
                ),
                "indexes": (
                    "economic_memory by agent_id",
                    "economic_memory by goal_id",
                    "economic_memory by provider_or_route/provider_id/route_id",
                    "economic_memory by created_at",
                    "economic_memory by task_type/task_hash",
                    "providers by status",
                    "provider applications by provider_id/status",
                    "quotes by provider_id",
                    "quotes by route_id",
                    "quotes by expires_at",
                    "quote replay guard by quote_id/hash",
                    "provider callback replay guard by provider_id/callback_id",
                    "capacity windows by provider_id/route_id/expires_at",
                    "reservations by provider_id/route_id/status",
                    "jobs by provider_id/route_id/status",
                    "job events by request_id/status",
                    "billing accounts by tenant/workspace",
                    "payment events by idempotency_key/status",
                    "audit events by actor_id via payload and request_id/created_at indexes",
                    "audit events by chain_id/sequence_number",
                    "audit events by event_hash",
                    "audit checkpoint manifests by chain_id/status",
                    "audit replay runs by request_id/status",
                    "intelligence plans by agent/goal/task",
                    "price snapshots by provider/route/unit",
                    "price anomalies by provider/route/status",
                    "intelligence usage by workspace/agent/goal",
                    "compute statements by workspace/period",
                ),
                "description": "Create durable typed JSON record storage, marketplace provider onboarding, quote replay protection, capacity reservations, dry-run job execution, no-custody billing ledgers, intelligence-tier utility planning, compute price history, usage statements, production query indexes, and tamper-evident audit chain columns for Flow Memory Compute Market.",
                "reversible": False,
                "managed_sql_notes": (
                    "SQLite stores all production primitive records in compute_market_records for local and test use.",
                    "PostgreSQL deployments create one jsonb-backed table per record type with the same primary key, idempotency, chain, provider, route, tenant, and status indexes.",
                    "Run migrations before serving traffic, use advisory migration locks, and restore from a database snapshot for rollback.",
                    "Live settlement, transaction broadcast, and private-key custody are intentionally not part of this schema.",
                ),
            },
        ),
    }


def migrate_alpha_memory(store: ComputeMarketStore, records: tuple[Mapping[str, Any], ...]) -> MigrationResult:
    for record in records:
        record_id = str(record.get("record_id") or deterministic_id("economic_memory", record))
        quote = record.get("quote_snapshot", {})
        quote_map = quote if isinstance(quote, Mapping) else {}
        store.put_record(
            "economic_memory",
            record_id,
            {**dict(record), "record_id": record_id, "schema_version": COMPUTE_MARKET_STORAGE_VERSION},
            agent_id=str(record.get("agent_id", "")),
            goal_id=str(record.get("goal_id", "")),
            provider_id=str(quote_map.get("provider_id", "")),
            route_id=str(quote_map.get("route_id", "")),
            task_type=str(record.get("task_type", "generic")),
            task_hash=str(record.get("task_hash", "")),
            status=str(record.get("policy_result", "")),
        )
    return MigrationResult(ok=True, version=COMPUTE_MARKET_STORAGE_VERSION, applied=("alpha_memory_import",), schema_hash=schema_hash())


def _sqlite_required_index_names() -> tuple[str, ...]:
    return (
        "idx_compute_records_type_created",
        "idx_compute_records_agent",
        "idx_compute_records_goal",
        "idx_compute_records_provider",
        "idx_compute_records_route",
        "idx_compute_records_task",
        "idx_compute_records_status",
        "idx_compute_records_expires",
        "idx_compute_records_idempotency",
        "idx_compute_records_request",
        "idx_compute_records_actor",
        "idx_compute_records_chain",
        "idx_compute_records_event_hash",
        "idx_compute_records_action",
        "idx_compute_records_tenant",
    )

def _cursor_to_offset(cursor: str) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(cursor))
    except ValueError:
        return 0
