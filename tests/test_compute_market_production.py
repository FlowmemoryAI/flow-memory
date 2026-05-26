import json
from typing import Any

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.scopes import required_scopes_for
from flow_memory.compute_market.adapters import HTTPQuoteProvider, LocalMockComputeProvider, ProviderCircuitBreaker, ReservedCapacityProvider
from flow_memory.compute_market.config import ComputeMarketConfig, config_from_env
from flow_memory.compute_market.models import ComputeMarketPolicy
from flow_memory.compute_market.planner import build_compute_plan, build_task_profile
from flow_memory.compute_market.registry import default_compute_providers, default_compute_routes
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore, migrate_alpha_memory, migration_plan


def test_compute_market_store_persists_required_records_and_migrates_alpha_memory() -> None:
    store = ComputeMarketStore(":memory:")
    plan = migration_plan()
    assert plan["current_version"] >= 2
    assert "economic_memory by agent_id" in plan["steps"][0]["indexes"]

    record = build_compute_plan({"task": "durable planning", "agent_id": "agent-a", "goal_id": "goal-a"}).economic_memory_preview
    migration = migrate_alpha_memory(store, (record,))
    page = store.list_records("economic_memory", filters={"agent_id": "agent-a"})

    assert migration.ok is True
    assert page.records[0]["agent_id"] == "agent-a"
    assert page.records[0]["goal_id"] == "goal-a"
    assert store.count_records("economic_memory") == 1


def test_service_persists_decision_audit_memory_and_replays_without_mutation() -> None:
    service = ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))
    result = service.plan({"task": "production planning", "agent_id": "agent-a", "goal_id": "goal-a", "idempotency_key": "idem-1"})
    plan = result["compute_plan"]
    decision_id = plan["decision_id"]

    assert service.store.get_record("route_decision", decision_id)
    assert service.store.list_records("economic_memory", filters={"agent_id": "agent-a"}).records
    assert service.audit({})["audit_events"]

    replay = service.replay_decision(decision_id, {"request_id": "replay-1"})
    stored_after = service.store.get_record("route_decision", decision_id)
    assert stored_after is not None

    assert replay["ok"] is True
    assert replay["mutated_original"] is False
    assert stored_after["decision_id"] == decision_id

    idempotent = service.plan({"task": "changed", "idempotency_key": "idem-1"})
    assert idempotent["idempotent_replay"] is True


def test_compute_admin_scope_enforcement_and_new_endpoints() -> None:
    reset_default_service(ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test")))
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    body = json.dumps({"provider_id": "admin-provider", "provider_name": "Admin Provider", "provider_type": "static"}).encode()

    denied = gateway.handle("POST", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:read"}, body)
    allowed = gateway.handle("POST", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:provider-admin"}, body)
    health = gateway.handle("GET", "/compute/readiness", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:read"})

    assert required_scopes_for("POST", "/compute/providers") == ("compute:provider-admin",)
    assert required_scopes_for("GET", "/compute/audit") == ("compute:audit",)
    assert denied.status == 403
    assert allowed.status == 200
    assert health.status == 200
    assert json.loads(health.to_bytes())["data"]["database_reachable"] is True


def test_unsafe_payloads_fail_closed_before_planning() -> None:
    service = ComputeMarketService(store=ComputeMarketStore(":memory:"), config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"))
    for payload in (
        {"task": "unsafe", "private_key": "x"},
        {"task": "unsafe", "mnemonic": "one two three"},
        {"task": "unsafe", "broadcast": True},
        {"task": "unsafe", "transfer": {"amount": 1}},
    ):
        try:
            service.plan(payload)
        except ValueError as exc:
            assert "Unsafe" in str(exc) or "dry-run" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"unsafe payload accepted: {payload}")


def test_provider_adapters_bound_failures_and_disabled_http_quotes() -> None:
    providers = default_compute_providers()
    routes = default_compute_routes()
    local = LocalMockComputeProvider(
        providers[-2],
        tuple(route for route in routes if route.provider_id == providers[-2].provider_id),
    )
    reserved = ReservedCapacityProvider(
        providers[3],
        tuple(route for route in routes if route.provider_id == providers[3].provider_id),
    )
    http = HTTPQuoteProvider(
        providers[0],
        tuple(route for route in routes if route.provider_id == providers[0].provider_id),
        enabled=False,
    )
    task_profile = build_task_profile({"task": "adapter test"})

    local_quotes = local.quote(task_profile, ComputeMarketPolicy())
    disabled_quotes = http.quote(task_profile, ComputeMarketPolicy())

    assert local.health_check().status == "healthy"
    assert reserved.health_check().provider_id == providers[3].provider_id
    assert all(quote.status == "disabled_provider" for quote in disabled_quotes)
    assert local_quotes


def test_circuit_breaker_opens_and_resets_provider_failures() -> None:
    breaker = ProviderCircuitBreaker(failure_threshold=2, reset_after_seconds=10)
    assert breaker.allow("provider", now=0.0) is True
    breaker.record_failure("provider", now=1.0)
    assert breaker.allow("provider", now=2.0) is True
    breaker.record_failure("provider", now=3.0)
    assert breaker.allow("provider", now=4.0) is False
    assert breaker.allow("provider", now=14.0) is True


def test_live_settlement_config_gates_fail_closed() -> None:
    errors = ComputeMarketConfig(
        database_url=":memory:",
        live_settlement_enabled=True,
        broadcast_enabled=True,
        settlement_environment="",
        settlement_security_review_id="",
    ).validate()

    assert "live_settlement_enabled requires settlement_environment" in errors
    assert "live_settlement_enabled requires settlement_security_review_id" in errors
    assert ComputeMarketConfig(database_url=":memory:").private_key_inputs_allowed is False


def test_production_redis_config_requires_fail_closed_backends() -> None:
    base: dict[str, Any] = {
        "database_url": "postgresql://db/flow_memory",
        "storage_backend": "postgres",
        "compute_market_mode": "production_planning",
        "require_managed_redis_in_production": True,
        "rate_limit_backend": "redis",
        "circuit_breaker_backend": "redis",
        "redis_url": "rediss://redis.example.com:6379/0",
    }

    rate_errors = ComputeMarketConfig(**base, rate_limit_fail_closed=False).validate()
    circuit_errors = ComputeMarketConfig(**base, circuit_breaker_fail_closed=False).validate()

    assert (
        "production_planning requires fail-closed Redis rate limiting "
        "when require_managed_redis_in_production=true"
    ) in rate_errors
    assert (
        "production_planning requires fail-closed Redis circuit breaking "
        "when require_managed_redis_in_production=true"
    ) in circuit_errors


def test_provider_callback_ip_allowlist_config_from_env() -> None:
    config = ComputeMarketConfig(
        database_url=":memory:",
        compute_market_mode="test",
        provider_callback_ip_allowlist=("203.0.113.0/24", "2001:db8::1"),
    )
    from_env = config_from_env(
        {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "203.0.113.0/24,2001:db8::1"}
    )

    assert config.as_record()["provider_callback_ip_allowlist_configured"] is True
    assert from_env.provider_callback_ip_allowlist == ("203.0.113.0/24", "2001:db8::1")

def test_stripe_webhook_tolerance_config_from_env_and_validation() -> None:
    config = config_from_env({"FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS": "600"})
    invalid = ComputeMarketConfig(database_url=":memory:", stripe_webhook_tolerance_seconds=0)

    assert config.stripe_webhook_tolerance_seconds == 600
    assert config.as_record()["stripe_webhook_tolerance_seconds"] == 600
    assert "stripe_webhook_tolerance_seconds must be positive" in invalid.validate()
