"""Concrete storage backend selection for Flow Memory Compute Market.

SQLite remains the default local/single-node store.  The PostgreSQL store is an
optional managed-SQL adapter: it imports psycopg lazily so default installs do
not gain a hard database dependency, while production deployments can install
`flow-memory[postgres]` and point FLOW_MEMORY_COMPUTE_DATABASE_URL at managed
PostgreSQL.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Protocol

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.storage import (
    COMPUTE_MARKET_STORAGE_VERSION,
    APPEND_ONLY_COMPUTE_RECORD_TYPES,
    COMPUTE_RECORD_TYPES,
    AuditChainVerification,
    ComputeMarketStore,
    MigrationResult,
    POSTGRES_COMPUTE_RECORD_TABLES,
    RecordPage,
    audit_event_hash,
    canonical_audit_payload_hash,
    deterministic_id,
    schema_hash,
    utc_now_iso,
)

SQLiteComputeMarketStore = ComputeMarketStore

_POSTGRES_TABLES = POSTGRES_COMPUTE_RECORD_TABLES

_COMMON_COLUMNS = (
    "record_id",
    "tenant_id",
    "workspace_id",
    "agent_id",
    "goal_id",
    "provider_id",
    "route_id",
    "task_type",
    "task_hash",
    "request_id",
    "actor_id",
    "action",
    "status",
    "chain_id",
    "sequence_number",
    "event_hash",
    "previous_hash",
    "created_at",
    "updated_at",
    "expires_at",
    "idempotency_key",
    "archived",
    "payload",
)


class ComputeMarketStoreProtocol(Protocol):
    database_url: str
    backend: str

    def close(self) -> None: ...

    def migrate(self) -> MigrationResult: ...

    def migration_status(self) -> Mapping[str, Any]: ...

    def storage_status(self) -> Mapping[str, Any]: ...

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
        _allow_audit_event_mutation: bool = False,
    ) -> None: ...
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
        _allow_audit_event_mutation: bool = False,
    ) -> bool: ...

    def get_record(self, record_type: str, record_id: str) -> Mapping[str, Any] | None: ...

    def find_by_idempotency(self, record_type: str, idempotency_key: str) -> Mapping[str, Any] | None: ...

    def list_records(
        self,
        record_type: str,
        *,
        filters: Mapping[str, Any] | None = None,
        limit: int = 100,
        cursor: str = "",
        include_archived: bool = False,
    ) -> RecordPage: ...

    def delete_record(self, record_type: str, record_id: str, *, _allow_audit_event_mutation: bool = False) -> bool: ...

    def count_records(self, record_type: str) -> int: ...

    def quote_cache_key(self, provider_id: str, route_id: str, task_hash: str, policy_hash: str) -> str: ...

    def append_audit_event(self, payload: Mapping[str, Any], *, chain_id: str = "") -> Mapping[str, Any]: ...

    def verify_audit_chain(self, *, chain_id: str = "") -> AuditChainVerification: ...

    def audit_chain_ids(self) -> tuple[str, ...]: ...
    def migration_history(self) -> Mapping[str, Any]: ...

    def schema_verification(self) -> Mapping[str, Any]: ...

    def production_readiness_check(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PostgresSchemaStatement:
    name: str
    sql: str

    def as_record(self) -> dict[str, str]:
        return {"name": self.name, "sql": self.sql}


class PostgresComputeMarketStore:
    """PostgreSQL-backed compute-market store.

    The adapter uses one normalized JSONB record table per compute-market record
    family. Table names are compile-time constants and all user values are bound
    as query parameters.
    """

    def __init__(
        self,
        database_url: str,
        *,
        ssl_mode: str = "require",
        timeout_ms: int = 5_000,
        statement_timeout_ms: int = 5_000,
        pool_size: int = 4,
        max_overflow: int = 4,
        migrations_enabled: bool = True,
        auto_run_migrations: bool = True,
        connect: bool = True,
    ) -> None:
        self.database_url = database_url
        self.backend = "postgresql"
        self.ssl_mode = ssl_mode
        self.timeout_ms = timeout_ms
        self.statement_timeout_ms = statement_timeout_ms
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.migrations_enabled = migrations_enabled
        self.auto_run_migrations = auto_run_migrations
        self._connect_enabled = connect
        if connect and migrations_enabled and auto_run_migrations:
            self.migrate()

    @staticmethod
    def schema_statements() -> tuple[PostgresSchemaStatement, ...]:
        statements: list[PostgresSchemaStatement] = [
            PostgresSchemaStatement(
                "compute_migrations",
                "create table if not exists compute_migrations ("
                "version integer primary key, "
                "name text not null, "
                "applied_at timestamptz not null default now())",
            )
        ]
        for record_type in COMPUTE_RECORD_TYPES:
            table = _postgres_table(record_type)
            statements.append(
                PostgresSchemaStatement(
                    f"{table}_table",
                    f"create table if not exists {table} ("
                    "record_id text primary key, "
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
                    "created_at timestamptz not null, "
                    "updated_at timestamptz not null, "
                    "expires_at timestamptz null, "
                    "idempotency_key text not null default '', "
                    "archived boolean not null default false, "
                    "payload jsonb not null)",
                )
            )
            statements.extend(_postgres_index_statements(record_type))
        return tuple(statements)

    @staticmethod
    def schema_sql() -> tuple[str, ...]:
        return tuple(statement.sql for statement in PostgresComputeMarketStore.schema_statements())

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if not self._connect_enabled:
            raise RuntimeError("PostgreSQL store was created without an active connection")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except Exception as exc:  # pragma: no cover - exercised when optional extra is absent
            raise RuntimeError("PostgreSQL storage requires optional dependency: flow-memory[postgres]") from exc
        try:
            conn = psycopg.connect(
                self.database_url,
                connect_timeout=max(1, int(self.timeout_ms / 1000)),
                sslmode=self.ssl_mode,
                row_factory=dict_row,
            )
        except Exception as exc:
            raise RuntimeError(f"postgres connection failed for {_redact_url(self.database_url)}: {type(exc).__name__}") from None
        try:
            with conn:
                if self.statement_timeout_ms > 0:
                    statement_timeout_ms = max(1, int(self.statement_timeout_ms))
                    conn.execute(f"set local statement_timeout = {statement_timeout_ms}")
                yield conn
        finally:
            conn.close()

    def close(self) -> None:
        return None

    def migrate(self) -> MigrationResult:
        if not self.migrations_enabled:
            return MigrationResult(False, 0, (), schema_hash())
        applied: list[str] = []
        with self._connection() as conn:
            conn.execute("select pg_advisory_lock(%s)", (_POSTGRES_MIGRATION_LOCK_ID,))
            try:
                for statement in self.schema_statements():
                    conn.execute(statement.sql)
                row = conn.execute(
                    "select version from compute_migrations where version = %s",
                    (COMPUTE_MARKET_STORAGE_VERSION,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        "insert into compute_migrations(version, name, applied_at) values (%s, %s, %s) "
                        "on conflict (version) do nothing",
                        (COMPUTE_MARKET_STORAGE_VERSION, "compute_market_postgresql_records_v5_audit_operations", utc_now_iso()),
                    )
                    applied.append("compute_market_postgresql_records_v5_audit_operations")
            finally:
                conn.execute("select pg_advisory_unlock(%s)", (_POSTGRES_MIGRATION_LOCK_ID,))
        return MigrationResult(True, COMPUTE_MARKET_STORAGE_VERSION, tuple(applied), schema_hash())

    def migration_status(self) -> Mapping[str, Any]:
        if not self.migrations_enabled:
            return {"current": False, "version": 0, "expected_version": COMPUTE_MARKET_STORAGE_VERSION, "reason": "migrations_disabled"}
        try:
            with self._connection() as conn:
                row = conn.execute("select max(version) as version from compute_migrations").fetchone()
            version = int(row.get("version") or 0) if isinstance(row, Mapping) else 0
        except Exception as exc:
            return {
                "current": False,
                "version": 0,
                "expected_version": COMPUTE_MARKET_STORAGE_VERSION,
                "reason": f"migration_status_failed:{type(exc).__name__}",
            }
        return {"current": version >= COMPUTE_MARKET_STORAGE_VERSION, "version": version, "expected_version": COMPUTE_MARKET_STORAGE_VERSION, "reason": ""}

    def storage_status(self) -> Mapping[str, Any]:
        migration = self.migration_status()
        return {
            "backend": self.backend,
            "database_url": _redact_url(self.database_url),
            "postgres_ssl_mode": self.ssl_mode,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "timeout_ms": self.timeout_ms,
            "statement_timeout_ms": self.statement_timeout_ms,
            "migrations_enabled": self.migrations_enabled,
            "migrations_auto_run": self.auto_run_migrations,
            "migrations_current": migration.get("current", False),
            "migration_version": migration.get("version", 0),
            "schema_hash": schema_hash(),
            "managed_sql_ready": True,
            "production_note": "PostgreSQL storage is suitable for multi-node production when deployed with backups and migrations.",
        }

    def migration_history(self) -> Mapping[str, Any]:
        try:
            with self._connection() as conn:
                rows = conn.execute("select version, name, applied_at from compute_migrations order by version").fetchall()
        except Exception as exc:
            return {"ok": False, "backend": self.backend, "reason": f"migration_history_failed:{type(exc).__name__}", "history": ()}
        history = tuple(
            {
                "version": int(row.get("version") or 0),
                "name": str(row.get("name", "")),
                "applied_at": str(row.get("applied_at", "")),
            }
            for row in rows
            if isinstance(row, Mapping)
        )
        return {
            "ok": True,
            "backend": self.backend,
            "migration_lock": "postgres_advisory_lock",
            "migration_lock_id": _POSTGRES_MIGRATION_LOCK_ID,
            "history": history,
        }

    def schema_verification(self) -> Mapping[str, Any]:
        expected_tables = ("compute_migrations", *_POSTGRES_TABLES.values())
        expected_indexes = tuple(statement.name for record_type in COMPUTE_RECORD_TYPES for statement in _postgres_index_statements(record_type))
        try:
            with self._connection() as conn:
                table_rows = conn.execute(
                    "select table_name from information_schema.tables where table_schema = current_schema()"
                ).fetchall()
                index_rows = conn.execute(
                    "select indexname, indexdef from pg_indexes where schemaname = current_schema()"
                ).fetchall()
                lock_row = conn.execute("select pg_try_advisory_lock(%s) as locked", (_POSTGRES_MIGRATION_LOCK_ID,)).fetchone()
                lock_acquired = bool(lock_row.get("locked")) if isinstance(lock_row, Mapping) else False
                if lock_acquired:
                    conn.execute("select pg_advisory_unlock(%s)", (_POSTGRES_MIGRATION_LOCK_ID,))
        except Exception as exc:
            return {"ok": False, "backend": self.backend, "reason": f"schema_verification_failed:{type(exc).__name__}"}
        actual_tables = {str(row.get("table_name", "")) for row in table_rows if isinstance(row, Mapping)}
        actual_indexes = {str(row.get("indexname", "")) for row in index_rows if isinstance(row, Mapping)}
        index_definitions = {
            str(row.get("indexname", "")): str(row.get("indexdef", ""))
            for row in index_rows
            if isinstance(row, Mapping)
        }
        missing_tables = tuple(name for name in expected_tables if name not in actual_tables)
        missing_indexes = tuple(name for name in expected_indexes if name not in actual_indexes)
        expected_idempotency_indexes = tuple(name for name in expected_indexes if name.endswith("_idempotency_unique"))
        idempotency_nonunique_indexes = tuple(
            name
            for name in expected_idempotency_indexes
            if name in actual_indexes
            and not index_definitions.get(name, "").lstrip().lower().startswith("create unique index")
        )
        return {
            "ok": not missing_tables and not missing_indexes and not idempotency_nonunique_indexes,
            "backend": self.backend,
            "required_table_count": len(expected_tables),
            "missing_tables": missing_tables,
            "required_index_count": len(expected_indexes),
            "required_unique_idempotency_index_count": len(expected_idempotency_indexes),
            "idempotency_nonunique_indexes": idempotency_nonunique_indexes,
            "missing_indexes": missing_indexes,
            "advisory_lock_probe": {"lock_id": _POSTGRES_MIGRATION_LOCK_ID, "acquired": lock_acquired},
        }

    def production_readiness_check(self) -> Mapping[str, Any]:
        migration = self.migration_status()
        schema = self.schema_verification()
        return {
            "ok": bool(migration.get("current")) and bool(schema.get("ok")),
            "production_ready": bool(migration.get("current")) and bool(schema.get("ok")),
            "managed_sql_confirmed": True,
            "backend": self.backend,
            "migration_current": bool(migration.get("current")),
            "schema_ok": bool(schema.get("ok")),
            "postgres_ssl_mode": self.ssl_mode,
        }

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
        _allow_audit_event_mutation: bool = False,
    ) -> None:
        table = _postgres_table(record_type)
        now = utc_now_iso()
        existing = self.get_record(record_type, record_id)
        if record_type in APPEND_ONLY_COMPUTE_RECORD_TYPES and existing is not None and not _allow_audit_event_mutation:
            raise ValueError(f"{record_type} records are append-only and cannot be overwritten")
        created_at = str((existing or payload).get("created_at") or now)
        normalized = dict(payload)
        normalized.setdefault("record_id", record_id)
        normalized.setdefault("created_at", created_at)
        normalized["updated_at"] = now
        values = _record_values(
            normalized,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            agent_id=agent_id,
            goal_id=goal_id,
            provider_id=provider_id,
            route_id=route_id,
            task_type=task_type,
            task_hash=task_hash,
            status=status,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            request_id=request_id,
            actor_id=actor_id,
            action=action,
            archived=archived,
            created_at=created_at,
            updated_at=now,
        )
        assignments = ", ".join(f"{column} = excluded.{column}" for column in _COMMON_COLUMNS if column != "record_id")
        placeholders = ", ".join("%s" for _ in _COMMON_COLUMNS[:-1]) + ", %s::jsonb"
        sql = (
            f"insert into {table} ({', '.join(_COMMON_COLUMNS)}) values ({placeholders}) "
            f"on conflict (record_id) do update set {assignments}"
        )
        with self._connection() as conn:
            conn.execute(sql, values)

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
        _allow_audit_event_mutation: bool = False,
    ) -> bool:
        table = _postgres_table(record_type)
        if record_type in APPEND_ONLY_COMPUTE_RECORD_TYPES and not _allow_audit_event_mutation:
            raise ValueError(f"{record_type} records are append-only and cannot be updated")
        expected = tuple(str(item) for item in expected_statuses if str(item))
        if not expected:
            return False
        now = utc_now_iso()
        created_at = str(payload.get("created_at") or now)
        normalized = dict(payload)
        normalized.setdefault("record_id", record_id)
        normalized.setdefault("created_at", created_at)
        normalized["updated_at"] = now
        record_values = _record_values(
            normalized,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            agent_id=agent_id,
            goal_id=goal_id,
            provider_id=provider_id,
            route_id=route_id,
            task_type=task_type,
            task_hash=task_hash,
            status=status,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            request_id=request_id,
            actor_id=actor_id,
            action=action,
            archived=archived,
            created_at=created_at,
            updated_at=now,
        )
        assignments = ", ".join(f"{column} = %s::jsonb" if column == "payload" else f"{column} = %s" for column in _COMMON_COLUMNS[1:])
        status_placeholders = ", ".join("%s" for _ in expected)
        where = [f"record_id = %s and status in ({status_placeholders})"]
        values: list[Any] = [*record_values[1:], record_id, *expected]
        if expected_actor_id:
            where.append("actor_id = %s")
            values.append(expected_actor_id)
        if expires_at_before:
            where.append("expires_at is not null and expires_at <= %s")
            values.append(expires_at_before)
        sql = f"update {table} set {assignments} where {' and '.join(where)}"
        with self._connection() as conn:
            cursor = conn.execute(sql, tuple(values))
            return int(getattr(cursor, "rowcount", 0) or 0) == 1

    def get_record(self, record_type: str, record_id: str) -> Mapping[str, Any] | None:
        table = _postgres_table(record_type)
        with self._connection() as conn:
            row = conn.execute(f"select payload from {table} where record_id = %s", (record_id,)).fetchone()
        return _row_payload(row)

    def find_by_idempotency(self, record_type: str, idempotency_key: str) -> Mapping[str, Any] | None:
        if not idempotency_key:
            return None
        table = _postgres_table(record_type)
        with self._connection() as conn:
            row = conn.execute(
                f"select payload from {table} where idempotency_key = %s order by created_at desc, record_id desc limit 1",
                (idempotency_key,),
            ).fetchone()
        return _row_payload(row)

    def list_records(
        self,
        record_type: str,
        *,
        filters: Mapping[str, Any] | None = None,
        limit: int = 100,
        cursor: str = "",
        include_archived: bool = False,
    ) -> RecordPage:
        table = _postgres_table(record_type)
        offset = _cursor_to_offset(cursor)
        bounded_limit = min(max(1, int(limit)), 500)
        where = ["true"]
        values: list[Any] = []
        if not include_archived:
            where.append("archived = false")
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
            "chain_id",
        ):
            value = (filters or {}).get(column)
            if value not in (None, ""):
                where.append(f"{column} = %s")
                values.append(str(value))
        start_time = str((filters or {}).get("start_time", ""))
        end_time = str((filters or {}).get("end_time", ""))
        if start_time:
            where.append("created_at >= %s")
            values.append(start_time)
        if end_time:
            where.append("created_at <= %s")
            values.append(end_time)
        sql = f"select payload from {table} where {' and '.join(where)} order by created_at, record_id limit %s offset %s"
        values.extend((bounded_limit + 1, offset))
        with self._connection() as conn:
            rows = conn.execute(sql, tuple(values)).fetchall()
        payloads = tuple(_row_payload(row) or {} for row in rows[:bounded_limit])
        next_cursor = str(offset + bounded_limit) if len(rows) > bounded_limit else ""
        return RecordPage(records=payloads, next_cursor=next_cursor, limit=bounded_limit)

    def delete_record(self, record_type: str, record_id: str, *, _allow_audit_event_mutation: bool = False) -> bool:
        if record_type in APPEND_ONLY_COMPUTE_RECORD_TYPES and not _allow_audit_event_mutation:
            raise ValueError(f"{record_type} records are append-only and cannot be deleted")
        table = _postgres_table(record_type)
        with self._connection() as conn:
            cursor = conn.execute(f"delete from {table} where record_id = %s", (record_id,))
            rowcount = int(getattr(cursor, "rowcount", 0) or 0)
        return rowcount > 0

    def count_records(self, record_type: str) -> int:
        table = _postgres_table(record_type)
        with self._connection() as conn:
            row = conn.execute(f"select count(*) as count from {table}").fetchone()
        return int(row.get("count") or 0) if isinstance(row, Mapping) else 0

    def quote_cache_key(self, provider_id: str, route_id: str, task_hash: str, policy_hash: str) -> str:
        return deterministic_id("quote_cache", {"provider_id": provider_id, "route_id": route_id, "task_hash": task_hash, "policy_hash": policy_hash})

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
                    first_failure = first_failure or AuditChainVerification(False, chain, len(events), expected_sequence, "audit_sequence_gap", "audit chain has a missing or out-of-order event")
                    break
                if str(event.get("previous_hash", "")) != previous_hash:
                    first_failure = first_failure or AuditChainVerification(False, chain, len(events), sequence, "audit_previous_hash_mismatch", "audit event previous_hash does not match prior event_hash")
                    break
                canonical_hash = canonical_audit_payload_hash(event)
                if str(event.get("canonical_payload_hash", "")) != canonical_hash:
                    first_failure = first_failure or AuditChainVerification(False, chain, len(events), sequence, "audit_payload_hash_mismatch", "audit event payload was modified after append")
                    break
                event_hash = audit_event_hash(event)
                if str(event.get("event_hash", "")) != event_hash:
                    first_failure = first_failure or AuditChainVerification(False, chain, len(events), sequence, "audit_event_hash_mismatch", "audit event hash does not match canonical payload and previous_hash")
                    break
                previous_hash = event_hash
                expected_sequence += 1
        if first_failure is not None:
            return first_failure
        return AuditChainVerification(True, chain_id or "all", total)

    def audit_chain_ids(self) -> tuple[str, ...]:
        records = self._all_records("audit_event")
        return tuple(sorted({str(record.get("chain_id", "")) for record in records if record.get("chain_id")}))

    def _latest_audit_event(self, chain_id: str) -> Mapping[str, Any] | None:
        page = self.list_records("audit_event", filters={"chain_id": chain_id}, limit=500, include_archived=True)
        records = sorted(page.records, key=lambda event: int(event.get("sequence_number", 0) or 0), reverse=True)
        return records[0] if records else None

    def _audit_events_for_chain(self, chain_id: str) -> tuple[Mapping[str, Any], ...]:
        records = self.list_records("audit_event", filters={"chain_id": chain_id}, limit=500, include_archived=True).records
        return tuple(sorted(records, key=lambda event: (int(event.get("sequence_number", 0) or 0), str(event.get("created_at", "")), str(event.get("record_id", "")))))

    def _all_records(self, record_type: str) -> tuple[Mapping[str, Any], ...]:
        records: list[Mapping[str, Any]] = []
        cursor = ""
        while True:
            page = self.list_records(record_type, limit=500, cursor=cursor, include_archived=True)
            records.extend(page.records)
            if not page.next_cursor:
                break
            cursor = page.next_cursor
        return tuple(records)


def create_compute_market_store(config: ComputeMarketConfig, *, connect: bool = True) -> ComputeMarketStoreProtocol:
    backend = config.storage_backend_effective
    if backend == "postgresql":
        return PostgresComputeMarketStore(
            config.database_url,
            ssl_mode=config.postgres_ssl_mode,
            timeout_ms=config.storage_timeout_ms,
            statement_timeout_ms=config.storage_statement_timeout_ms,
            pool_size=config.storage_pool_size,
            max_overflow=config.storage_max_overflow,
            migrations_enabled=config.migrations_enabled,
            auto_run_migrations=config.migrations_auto_run,
            connect=connect,
        )
    return SQLiteComputeMarketStore(
        config.database_url,
        backend="sqlite",
        timeout_ms=config.storage_timeout_ms,
        pool_size=config.storage_pool_size,
        migrations_enabled=config.migrations_enabled,
    )


def postgres_schema_sql() -> tuple[str, ...]:
    return PostgresComputeMarketStore.schema_sql()


def _postgres_table(record_type: str) -> str:
    try:
        return _POSTGRES_TABLES[record_type]
    except KeyError as exc:
        raise ValueError(f"unknown compute market record type: {record_type}") from exc


def _postgres_index_statements(record_type: str) -> tuple[PostgresSchemaStatement, ...]:
    table = _postgres_table(record_type)
    indexes = [
        (f"idx_{table}_created", "created_at"),
        (f"idx_{table}_agent", "agent_id"),
        (f"idx_{table}_goal", "goal_id"),
        (f"idx_{table}_provider", "provider_id"),
        (f"idx_{table}_route", "route_id"),
        (f"idx_{table}_task", "task_type, task_hash"),
        (f"idx_{table}_status", "status"),
        (f"idx_{table}_expires", "expires_at"),
        (f"idx_{table}_request", "request_id"),
        (f"idx_{table}_actor", "actor_id"),
        (f"idx_{table}_tenant", "tenant_id, workspace_id"),
    ]
    statements = [PostgresSchemaStatement(name, f"create index if not exists {name} on {table} ({columns})") for name, columns in indexes]
    statements.append(
        PostgresSchemaStatement(
            f"idx_{table}_idempotency_unique",
            f"create unique index if not exists idx_{table}_idempotency_unique on {table} (idempotency_key) where idempotency_key <> ''",
        )
    )
    if record_type == "audit_event":
        statements.extend(
            (
                PostgresSchemaStatement("idx_compute_audit_events_chain", "create index if not exists idx_compute_audit_events_chain on compute_audit_events (chain_id, sequence_number)"),
                PostgresSchemaStatement("idx_compute_audit_events_hash", "create index if not exists idx_compute_audit_events_hash on compute_audit_events (event_hash)"),
                PostgresSchemaStatement("idx_compute_audit_events_action", "create index if not exists idx_compute_audit_events_action on compute_audit_events (action)"),
            )
        )
    return tuple(statements)


def _record_values(
    normalized: Mapping[str, Any],
    *,
    tenant_id: str,
    workspace_id: str,
    agent_id: str,
    goal_id: str,
    provider_id: str,
    route_id: str,
    task_type: str,
    task_hash: str,
    status: str,
    expires_at: str,
    idempotency_key: str,
    request_id: str,
    actor_id: str,
    action: str,
    archived: bool,
    created_at: str,
    updated_at: str,
) -> tuple[Any, ...]:
    return (
        str(normalized.get("record_id", "")),
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
        updated_at,
        expires_at or str(normalized.get("expires_at", "")) or None,
        idempotency_key or str(normalized.get("idempotency_key", "")),
        archived,
        json.dumps(dict(normalized), sort_keys=True, default=str),
    )


def _row_payload(row: object) -> Mapping[str, Any] | None:
    if row is None:
        return None
    payload = row.get("payload") if isinstance(row, Mapping) else None
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, str):
        decoded = json.loads(payload)
        return decoded if isinstance(decoded, Mapping) else {}
    return {}


def _audit_chain_id(event: Mapping[str, Any]) -> str:
    tenant = str(event.get("tenant_id") or event.get("workspace_id") or "")
    return f"compute-market-audit:{tenant or 'global'}"


def _cursor_to_offset(cursor: str) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(cursor))
    except ValueError:
        return 0


def _redact_url(value: str) -> str:
    if "://" not in value:
        return value
    scheme, _, rest = value.partition("://")
    if "@" not in rest:
        return f"{scheme}://***"
    return f"{scheme}://***@{rest.rsplit('@', 1)[-1]}"


_POSTGRES_MIGRATION_LOCK_ID = 860_240_517
