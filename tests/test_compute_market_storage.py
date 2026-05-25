from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from flow_memory.compute_market.config import ComputeMarketConfig, config_from_env
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore, deterministic_id, migration_plan
from flow_memory.compute_market.storage_backends import (
    PostgresComputeMarketStore,
    SQLiteComputeMarketStore,
    create_compute_market_store,
    postgres_schema_sql,
)


def test_sqlite_url_storage_survives_restart_and_migrations_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "compute_market.sqlite3"
    store = ComputeMarketStore(f"sqlite:///{db_path}")
    first = store.migrate()
    second = store.migrate()

    assert first.ok is True
    assert second.ok is True
    assert second.applied == ()
    assert store.migration_status()["current"] is True

    provider = {"provider_id": "persistent-provider", "provider_name": "Persistent Provider", "status": "active"}
    route = {"route_id": "persistent-route", "provider_id": "persistent-provider", "enabled": True}
    policy = {"policy_id": "persistent-policy", "dry_run_required": True}
    quote = {"quote_id": "persistent-quote", "provider_id": "persistent-provider", "route_id": "persistent-route", "expires_at": "2099-01-01T00:00:00Z"}
    memory = {"record_id": "persistent-memory", "agent_id": "agent", "goal_id": "goal", "provider_id": "persistent-provider", "route_id": "persistent-route", "task_type": "inference"}
    decision = {"decision_id": "persistent-decision", "request_id": "req", "idempotency_key": "idem-persist"}
    audit = {"audit_event_id": "persistent-audit", "request_id": "req", "actor_id": "actor", "actor_type": "user", "action": "compute.test", "resource_type": "compute_market", "resource_id": "persistent-route", "result": "ok"}
    cache = {"cache_key": "persistent-cache", "provider_id": "persistent-provider", "route_id": "persistent-route", "task_hash": "task", "policy_hash": "policy", "quote": quote, "source": "test"}

    store.put_record("compute_provider", "persistent-provider", provider, provider_id="persistent-provider", status="active")
    store.put_record("compute_route", "persistent-route", route, provider_id="persistent-provider", route_id="persistent-route", status="enabled")
    store.put_record("compute_market_policy", "persistent-policy", policy, status="active")
    store.put_record("compute_quote", "persistent-quote", quote, provider_id="persistent-provider", route_id="persistent-route", expires_at="2099-01-01T00:00:00Z")
    store.put_record("economic_memory", "persistent-memory", memory, agent_id="agent", goal_id="goal", provider_id="persistent-provider", route_id="persistent-route", task_type="inference")
    store.put_record("route_decision", "persistent-decision", decision, idempotency_key="idem-persist", request_id="req")
    store.append_audit_event(audit)
    store.put_record("quote_cache_entry", "persistent-cache", cache, provider_id="persistent-provider", route_id="persistent-route", task_hash="task")
    store.close()

    reopened = ComputeMarketStore(f"sqlite:///{db_path}")
    provider_record = reopened.get_record("compute_provider", "persistent-provider")
    route_record = reopened.get_record("compute_route", "persistent-route")
    policy_record = reopened.get_record("compute_market_policy", "persistent-policy")
    quote_record = reopened.get_record("compute_quote", "persistent-quote")
    decision_record = reopened.find_by_idempotency("route_decision", "idem-persist")
    cache_record = reopened.get_record("quote_cache_entry", "persistent-cache")

    assert provider_record is not None
    assert route_record is not None
    assert policy_record is not None
    assert quote_record is not None
    assert decision_record is not None
    assert cache_record is not None
    assert provider_record["provider_name"] == "Persistent Provider"
    assert route_record["provider_id"] == "persistent-provider"
    assert policy_record["dry_run_required"] is True
    assert quote_record["route_id"] == "persistent-route"
    assert reopened.list_records("economic_memory", filters={"agent_id": "agent"}).records[0]["goal_id"] == "goal"
    assert decision_record["decision_id"] == "persistent-decision"
    assert reopened.verify_audit_chain().ok is True
    assert cache_record["task_hash"] == "task"


def test_compute_database_config_supports_explicit_storage_settings() -> None:
    config = config_from_env(
        {
            "FLOW_MEMORY_COMPUTE_DATABASE_URL": "sqlite:///tmp/compute-market.sqlite3",
            "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND": "sqlite",
            "FLOW_MEMORY_COMPUTE_STORAGE_POOL_SIZE": "8",
            "FLOW_MEMORY_COMPUTE_STORAGE_TIMEOUT_MS": "7000",
            "FLOW_MEMORY_COMPUTE_MIGRATIONS_ENABLED": "true",
        }
    )

    assert config.database_url == "sqlite:///tmp/compute-market.sqlite3"
    assert config.storage_backend_effective == "sqlite"
    assert config.storage_pool_size == 8
    assert config.storage_timeout_ms == 7000
    assert config.migrations_enabled is True
    assert "managed_sql_notes" in migration_plan()["steps"][0]
    plan = migration_plan()
    assert "market_provider_application" in plan["record_types"]
    assert "compute_jobs" in plan["steps"][0]["postgres_tables"]
    assert "quote replay guard by quote_id/hash" in plan["steps"][0]["indexes"]
    assert "Live settlement" in plan["steps"][0]["managed_sql_notes"][3]


def test_backend_factory_selects_sqlite_and_postgres_without_connecting() -> None:
    sqlite_config = ComputeMarketConfig(database_url=":memory:", storage_backend="sqlite", compute_market_mode="test")
    sqlite_store = create_compute_market_store(sqlite_config)
    assert isinstance(sqlite_store, SQLiteComputeMarketStore)

    postgres_config = ComputeMarketConfig(
        database_url="postgresql://user:pass@db.example/flow_memory",
        storage_backend="postgres",
        compute_market_mode="test",
        migrations_auto_run=False,
    )
    postgres_store = create_compute_market_store(postgres_config, connect=False)
    assert isinstance(postgres_store, PostgresComputeMarketStore)
    status = postgres_store.storage_status()
    assert status["backend"] == "postgresql"
    assert status["managed_sql_ready"] is True


def test_postgres_schema_generation_contains_required_tables_indexes_and_jsonb() -> None:
    sql = "\n".join(postgres_schema_sql())

    for table in (
        "compute_providers",
        "compute_routes",
        "compute_policies",
        "compute_quote_cache",
        "compute_decisions",
        "compute_economic_memory",
        "compute_audit_events",
        "compute_provider_health",
        "compute_market_provider_applications",
        "compute_quote_replay_guard",
        "compute_provider_fraud_signals",
        "compute_provider_receipt_replay_guard",
        "compute_jobs",
        "compute_billing_accounts",
        "compute_migrations",
    ):
        assert table in sql
    assert "payload jsonb not null" in sql
    assert "idx_compute_decisions_idempotency_unique" in sql
    assert "idx_compute_audit_events_chain" in sql
    assert "%(" not in sql
    assert "?" not in sql


def test_production_can_require_managed_sql() -> None:
    errors = ComputeMarketConfig(
        database_url="sqlite:///.flow_memory/local.sqlite3",
        storage_backend="sqlite",
        require_managed_sql_in_production=True,
    ).validate()

    assert "production_planning requires managed SQL when require_managed_sql_in_production=true" in errors


def test_storage_failure_fails_closed_when_plan_requires_persistence() -> None:
    class FailingStore(ComputeMarketStore):
        fail_writes = False

        def put_record(self, record_type: str, record_id: str, payload: Mapping[str, Any], **kwargs: Any) -> None:
            if self.fail_writes:
                raise RuntimeError("database unavailable")
            super().put_record(record_type, record_id, payload, **kwargs)

    store = FailingStore(":memory:")
    service = ComputeMarketService(store=store, config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))
    store.fail_writes = True

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.plan({"task": "must persist", "idempotency_key": "db-fail"})


def test_readiness_reports_safe_config_migration_and_audit_chain() -> None:
    service = ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))
    service.plan({"task": "readiness verification"})

    readiness = service.readiness()

    assert readiness["ready"] is True
    assert readiness["migration_status"]["current"] is True
    assert readiness["audit_chain"]["ok"] is True
    assert readiness["rate_limiter_active"] is True
    assert readiness["circuit_breaker_active"] is True


def test_unsafe_runtime_configs_are_rejected_before_readiness() -> None:
    assert "live_settlement_enabled requires settlement_environment" in ComputeMarketConfig(database_url=":memory:", live_settlement_enabled=True).validate()
    assert "broadcast_enabled requires live_settlement_enabled" in ComputeMarketConfig(database_url=":memory:", broadcast_enabled=True).validate()
    assert "private_key_inputs_allowed is prohibited" in ComputeMarketConfig(database_url=":memory:", private_key_inputs_allowed=True).validate()


def test_idempotency_key_returns_original_decision() -> None:
    service = ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))
    first = service.plan({"task": "first", "idempotency_key": "idem-duplicate"})
    second = service.plan({"task": "second", "idempotency_key": "idem-duplicate"})

    assert second["idempotent_replay"] is True
    assert second["compute_plan"]["decision_id"] == first["compute_plan"]["decision_id"]


def test_quote_cache_key_is_retry_safe_and_deterministic() -> None:
    payload = {"provider_id": "p", "route_id": "r", "task_hash": "t", "policy_hash": "policy"}
    store = ComputeMarketStore(":memory:")
    assert store.quote_cache_key(**payload) == deterministic_id("quote_cache", payload)


def test_readiness_reports_multi_node_required_controls() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            require_managed_sql_in_production=True,
            audit_export_required=True,
            external_provider_quotes_enabled=True,
            provider_contracts_required=True,
        ),
    )

    readiness = service.readiness()

    assert readiness["ready"] is False
    assert "sqlite_disallowed_in_production" in readiness["readiness_failures"]
    assert "audit_export_unavailable" in readiness["readiness_failures"]
    assert "external_provider_allowlist_missing" in readiness["readiness_failures"]
    assert "provider_contracts_unverified" in readiness["readiness_failures"]


def test_storage_diagnostics_report_schema_migrations_and_sqlite_production_guard() -> None:
    store = ComputeMarketStore(":memory:")
    diagnostics = store.schema_verification()
    history = store.migration_history()
    production = store.production_readiness_check()

    assert diagnostics["ok"] is True
    assert diagnostics["missing_tables"] == ()
    assert diagnostics["missing_indexes"] == ()
    assert history["ok"] is True
    assert history["migration_lock"] == "sqlite_single_writer"
    assert production["production_ready"] is False
    assert production["reason"] == "sqlite_disallowed_in_production"


def test_admin_storage_diagnostics_exposes_authoritative_readiness_evidence() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"),
    )
    service.plan({"task": "diagnostic audit chain coverage"})

    diagnostics = service.admin_storage_diagnostics({})

    assert diagnostics["ok"] is False
    assert diagnostics["migration_status"]["current"] is True
    assert diagnostics["schema_verification"]["ok"] is True
    assert diagnostics["production_readiness"]["production_ready"] is False
    assert diagnostics["audit_chain"]["ok"] is True
    assert diagnostics["schema_hash"]
