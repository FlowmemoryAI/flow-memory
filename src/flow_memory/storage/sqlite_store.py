"""SQLite storage base for Flow Memory local state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = 1
_TABLES = (
    "agents",
    "agent_state",
    "goals",
    "plans",
    "task_graphs",
    "runtime_events",
    "audit_events",
    "skills",
    "marketplace_tasks",
    "bids",
    "escrows",
    "settlements",
    "disputes",
    "slashing_events",
    "reputation_updates",
    "memory_records",
)

TABLES = _TABLES


class SQLiteStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._memory = self.path == ":memory:"
        self.conn = self._open()
        self.migrate()
        if not self._memory:
            self.conn.close()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
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

    def migrate(self) -> None:
        with self._connection() as conn:
            conn.execute("create table if not exists schema_version (version integer not null)")
            row = conn.execute("select version from schema_version order by version desc limit 1").fetchone()
            if row is None:
                conn.execute("insert into schema_version(version) values (?)", (SCHEMA_VERSION,))
            for table in _TABLES:
                conn.execute(f"create table if not exists {table} (id text primary key, payload text not null)")
            conn.commit()

    def put(self, table: str, item_id: str, payload: Mapping[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                f"insert or replace into {table}(id, payload) values (?, ?)",
                (item_id, json.dumps(payload, sort_keys=True)),
            )
            conn.commit()

    def get(self, table: str, item_id: str) -> Mapping[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(f"select payload from {table} where id = ?", (item_id,)).fetchone()
            return json.loads(row["payload"]) if row else None

    def list(self, table: str) -> tuple[Mapping[str, Any], ...]:
        with self._connection() as conn:
            rows = conn.execute(f"select payload from {table} order by id").fetchall()
            return tuple(json.loads(row["payload"]) for row in rows)

    def ids(self, table: str) -> tuple[str, ...]:
        with self._connection() as conn:
            rows = conn.execute(f"select id from {table} order by id").fetchall()
            return tuple(str(row["id"]) for row in rows)

    def delete(self, table: str, item_id: str) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(f"delete from {table} where id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count(self, table: str) -> int:
        with self._connection() as conn:
            row = conn.execute(f"select count(*) as count from {table}").fetchone()
            return int(row["count"])

    def vacuum(self) -> None:
        with self._connection() as conn:
            conn.execute("vacuum")

    def tables(self) -> tuple[str, ...]:
        return TABLES

    def close(self) -> None:
        if self._memory:
            self.conn.close()
