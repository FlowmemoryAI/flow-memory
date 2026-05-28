import json
import hmac
import time
import threading
import urllib.error
import urllib.request
from typing import Any

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, create_http_server
from flow_memory.api.auth import RedisNonceReplayStore, api_key_hash
from flow_memory.compute_market.controls import InMemoryCircuitBreaker
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload
from flow_memory.crypto.hashes import content_hash


def test_http_gateway_health_response() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response = gateway.handle("GET", "/health", {"x-flow-memory-scopes": "api:read"})
    assert response.status == 200
    assert response.body["data"]["ok"] is True
    assert response.headers["content-type"].startswith("application/json")


def test_http_gateway_api_key_auth_blocks_missing_key() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", enable_rate_limit=False))
    denied = gateway.handle("GET", "/health", {})
    allowed = gateway.handle("GET", "/health", {"x-flow-memory-api-key": "dev"})
    assert denied.status == 401
    assert denied.body["error"]["code"] == "auth.invalid"
    assert allowed.status == 200
    healthz = gateway.handle("GET", "/healthz", {})
    assert healthz.status == 200
    assert healthz.body["data"]["endpoint"] == "healthz"
    root = gateway.handle("GET", "/", {})
    assert root.status == 200
    assert root.body["data"]["service"] == "Flow Memory Compute Market"
    assert root.body["data"]["auth"] == "API key or JWT bearer required for /compute/* endpoints"
    assert root.body["data"]["endpoints"]["metrics"] == "/metrics"
    assert root.body["data"]["endpoints"]["alerts"] == "/compute/alerts"


def test_http_gateway_nonce_check_blocks_replay_when_enabled() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", enable_rate_limit=False, enable_nonce_check=True))
    headers = {
        "x-flow-memory-api-key": "dev",
        "x-flow-memory-timestamp": str(time.time()),
        "x-flow-memory-nonce": "nonce-http-test-1",
    }

    first = gateway.handle("GET", "/health", headers)
    replay = gateway.handle("GET", "/health", headers)

    assert first.status == 200
    assert replay.status == 401
    assert "replayed request nonce" in replay.body["error"]["details"]["reasons"]

def test_http_gateway_nonce_check_shares_redis_replay_state_across_instances() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True

    redis_client = FakeRedis()
    config = HttpApiConfig(api_key="dev", enable_rate_limit=False, enable_nonce_check=True)
    first_gateway = HttpApiGateway(
        config=config,
        nonce_replay_store=RedisNonceReplayStore("rediss://cache.example:6379/0", client=redis_client, require_tls=True),
    )
    second_gateway = HttpApiGateway(
        config=config,
        nonce_replay_store=RedisNonceReplayStore("rediss://cache.example:6379/0", client=redis_client, require_tls=True),
    )
    headers = {
        "x-flow-memory-api-key": "dev",
        "x-flow-memory-timestamp": str(time.time()),
        "x-flow-memory-nonce": "nonce-http-redis-shared-1",
    }

    first = first_gateway.handle("GET", "/health", headers)
    replay = second_gateway.handle("GET", "/health", headers)

    assert first.status == 200
    assert replay.status == 401
    assert "replayed request nonce" in replay.body["error"]["details"]["reasons"]

def test_http_gateway_scope_enforcement() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/health", {})
    allowed = gateway.handle("GET", "/health", {"x-flow-memory-scopes": "api:read"})
    assert denied.status == 403
    assert allowed.status == 200


def test_http_gateway_prometheus_metrics_alias_returns_text_and_requires_compute_read_scope() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    service.telemetry.increment("compute_plan_requests_total", {"strategy": "balanced"})
    reset_default_service(service)
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    try:
        denied = gateway.handle("GET", "/metrics", {"x-flow-memory-scopes": "api:read"})
        allowed = gateway.handle("GET", "/metrics", {"x-flow-memory-scopes": "compute:read"})
    finally:
        reset_default_service(None)

    assert denied.status == 403
    assert allowed.status == 200
    assert allowed.headers["content-type"] == "text/plain; version=0.0.4"
    assert "# TYPE compute_plan_requests_total gauge" in allowed.to_bytes().decode("utf-8")
    assert 'strategy="balanced"' in allowed.to_bytes().decode("utf-8")

def test_http_gateway_rate_limit() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(rate_limit=1, rate_limit_window_seconds=60))
    headers = {"x-flow-memory-scopes": "api:read", "x-flow-memory-principal": "alice"}
    assert gateway.handle("GET", "/health", headers).status == 200
    assert gateway.handle("GET", "/health", headers).status == 429


def test_http_gateway_invalid_json_error_contract() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response = gateway.handle("POST", "/runtime/tick", {"x-flow-memory-scopes": "api:write"}, b"{")
    assert response.status == 400
    assert response.body["error"]["code"] == "request.invalid"

def test_http_gateway_get_query_payload_reaches_router() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    try:
        gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
        response = gateway.handle(
            "GET",
            "/billing/balance?account_id=acct_query",
            {"x-flow-memory-scopes": "compute:billing"},
        )
    finally:
        reset_default_service(None)

    assert response.status == 200
    assert response.body["data"]["balance"]["account_id"] == "acct_query"


def test_http_gateway_tenant_api_key_supplies_scopes_without_scope_header() -> None:
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-key",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash("fmk_tenant_http"),
                    "tenant_id": "tenant_http",
                    "principal": "svc-http",
                    "scopes": "compute:read",
                    "enabled": True,
                },
            ),
        )
    )

    response = gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": "fmk_tenant_http"})

    assert response.status == 200
    assert gateway.audit_sink.events[-1]["principal"] == "svc-http"
    assert gateway.audit_sink.events[-1]["tenant_id"] == "tenant_http"

def test_http_gateway_rejects_mismatched_tenant_header_for_tenant_key() -> None:
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-key",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash("fmk_tenant_http"),
                    "tenant_id": "tenant_http",
                    "principal": "svc-http",
                    "scopes": "compute:read",
                    "enabled": True,
                },
            ),
        )
    )

    response = gateway.handle(
        "GET",
        "/compute/health",
        {
            "x-flow-memory-api-key": "fmk_tenant_http",
            "x-flow-memory-tenant": "tenant_other",
        },
    )

    assert response.status == 403
    assert response.body["error"]["code"] == "auth.forbidden"
    assert response.body["error"]["details"]["key_id"] == "tenant-key"
    assert response.body["error"]["details"]["tenant_id"] == "tenant_http"
    assert response.body["error"]["details"]["requested_tenant_id"] == "tenant_other"

def test_http_gateway_rejects_scope_header_escalation_for_unscoped_key_record() -> None:
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "unscoped-key",
                    "key_prefix": "fmk_unscoped_",
                    "key_hash": api_key_hash("fmk_unscoped_secret"),
                    "tenant_id": "tenant_unscoped",
                    "principal": "svc-unscoped",
                    "enabled": True,
                },
            ),
        )
    )
    denied = gateway.handle(
        "GET",
        "/compute/health",
        {"x-flow-memory-api-key": "fmk_unscoped_secret", "x-flow-memory-scopes": "compute:read"},
    )
    local_dev = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    local_allowed = local_dev.handle("GET", "/compute/health", {"x-flow-memory-scopes": "compute:read"})

    assert denied.status == 403
    assert denied.body["error"]["details"]["unauthorized"] == ("compute:read",)
    assert local_allowed.status == 200


def test_http_gateway_uses_requested_scope_subset_from_credential_grants() -> None:
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            api_key="dev",
            api_key_scopes=("compute:read", "compute:plan"),
            require_scopes=True,
            enable_rate_limit=False,
        )
    )

    wrong_scope = gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "compute:plan"})
    allowed = gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "compute:read"})

    assert wrong_scope.status == 403
    assert wrong_scope.body["error"]["details"]["missing"] == ("compute:read",)
    assert allowed.status == 200


def test_http_gateway_enforces_credential_scopes_without_scope_header() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    read_key = "fmk_read_only_jobs"
    execute_key = "fmk_execute_jobs"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=False,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "read-only-jobs-key",
                    "key_prefix": "fmk_read_",
                    "key_hash": api_key_hash(read_key),
                    "tenant_id": "tenant_scoped_auth",
                    "principal": "svc-read-only",
                    "scopes": "compute:read",
                    "enabled": True,
                },
                {
                    "key_id": "execute-jobs-key",
                    "key_prefix": "fmk_execute_",
                    "key_hash": api_key_hash(execute_key),
                    "tenant_id": "tenant_scoped_auth",
                    "principal": "svc-execute",
                    "scopes": "compute:execute",
                    "enabled": True,
                },
            ),
        )
    )
    job_payload = {
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/scope-guard.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "route_scope_guard",
        "provider_id": "provider_scope_guard",
    }

    try:
        denied = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": read_key},
            json.dumps(job_payload).encode("utf-8"),
        )
        allowed = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": execute_key},
            json.dumps(job_payload).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert denied.status == 403
    assert denied.body["error"]["details"]["missing"] == ("compute:execute",)
    assert allowed.status == 200
    assert allowed.body["data"]["job"]["tenant_id"] == "tenant_scoped_auth"


def test_http_gateway_provider_health_store_audit_keeps_tenant_context() -> None:
    breaker = InMemoryCircuitBreaker(failure_threshold=1, reset_after_seconds=60)
    breaker.record_failure("tenant-provider", adapter_type="health_check", error_class="provider_timeout")
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
        circuit_breaker=breaker,
    )
    reset_default_service(service)
    key = "fmk_tenant_provider_admin"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-provider-admin-key",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash(key),
                    "tenant_id": "tenant_provider",
                    "principal": "svc-provider-admin",
                    "scopes": "compute:provider-admin",
                    "enabled": True,
                },
            ),
        )
    )
    try:
        response = gateway.handle(
            "POST",
            "/compute/providers/tenant-provider/health-check",
            {"x-flow-memory-api-key": key},
            b"{}",
        )
    finally:
        reset_default_service(None)

    audit_events = service.store.list_records(
        "audit_event",
        filters={"tenant_id": "tenant_provider"},
    ).records

    assert response.status == 200
    assert response.body["data"]["ok"] is False
    assert response.body["data"]["provider_health"]["error_code"] == "circuit_open"
    assert any(event["action"] == "compute.provider.circuit_open" for event in audit_events)
    assert all(event["tenant_id"] == "tenant_provider" for event in audit_events)


def test_http_gateway_provider_market_records_are_tenant_isolated() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    key_a = "fmk_tenant_provider_a"
    key_b = "fmk_tenant_provider_b"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-provider-a-key",
                    "key_prefix": "fmk_tenant_provider_a",
                    "key_hash": api_key_hash(key_a),
                    "tenant_id": "tenant_provider_a",
                    "principal": "svc-provider-a",
                    "scopes": ("compute:provider-admin", "compute:read"),
                    "enabled": True,
                },
                {
                    "key_id": "tenant-provider-b-key",
                    "key_prefix": "fmk_tenant_provider_b",
                    "key_hash": api_key_hash(key_b),
                    "tenant_id": "tenant_provider_b",
                    "principal": "svc-provider-b",
                    "scopes": ("compute:provider-admin", "compute:read"),
                    "enabled": True,
                },
            ),
        )
    )
    provider_application = {
        "provider_id": "tenant-provider-a",
        "provider_name": "Tenant Provider A",
        "provider_type": "gpu",
        "supported_unit_types": ["gpu_minute"],
        "supported_assets": ["USDC"],
        "supported_networks": ["offchain"],
        "quote_endpoint": "https://provider-a.example/quote",
        "health_endpoint": "https://provider-a.example/health",
        "sla": {"uptime_target": 0.99, "max_latency_ms": 1000, "refund_policy": "credit"},
    }

    try:
        applied = gateway.handle(
            "POST",
            "/market/providers/apply",
            {"x-flow-memory-api-key": key_a},
            json.dumps(provider_application).encode("utf-8"),
        )
        tenant_a_market = gateway.handle("GET", "/market/providers/tenant-provider-a", {"x-flow-memory-api-key": key_a})
        tenant_b_market = gateway.handle("GET", "/market/providers/tenant-provider-a", {"x-flow-memory-api-key": key_b})
        tenant_b_verify = gateway.handle(
            "POST",
            "/market/providers/tenant-provider-a/verify",
            {"x-flow-memory-api-key": key_b},
            b"{}",
        )
        tenant_a_verify = gateway.handle(
            "POST",
            "/market/providers/tenant-provider-a/verify",
            {"x-flow-memory-api-key": key_a},
            b"{}",
        )
        tenant_b_compute = gateway.handle("GET", "/compute/providers/tenant-provider-a", {"x-flow-memory-api-key": key_b})
        tenant_b_reputation = gateway.handle(
            "GET",
            "/market/providers/tenant-provider-a/reputation",
            {"x-flow-memory-api-key": key_b},
        )
    finally:
        reset_default_service(None)

    assert applied.status == 200
    assert applied.body["data"]["provider_application"]["tenant_id"] == "tenant_provider_a"
    assert tenant_a_market.status == 200
    assert tenant_a_market.body["data"]["provider_application"]["provider_id"] == "tenant-provider-a"
    assert tenant_b_market.status == 404
    assert tenant_b_verify.status == 404
    assert tenant_a_verify.status == 200
    assert tenant_b_compute.status == 404
    assert tenant_b_reputation.status == 404


def test_http_gateway_rejects_scope_header_escalation_for_scoped_key() -> None:
    key = "fmk_tenant_read"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-read-key",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash(key),
                    "tenant_id": "tenant_read",
                    "principal": "svc-read",
                    "scopes": "compute:read",
                    "enabled": True,
                },
            ),
        )
    )

    escalated = gateway.handle(
        "GET",
        "/admin/storage/diagnostics",
        {"x-flow-memory-api-key": key, "x-flow-memory-scopes": "compute:admin"},
    )
    allowed_subset = gateway.handle(
        "GET",
        "/compute/health",
        {"x-flow-memory-api-key": key, "x-flow-memory-scopes": "compute:read"},
    )

    assert escalated.status == 403
    assert escalated.body["error"]["code"] == "auth.forbidden"
    assert escalated.body["error"]["details"]["unauthorized"] == ("compute:admin",)
    assert escalated.body["error"]["details"]["granted"] == ("compute:read",)
    assert allowed_subset.status == 200
    denied_execute = gateway.handle(
        "POST",
        "/compute/jobs",
        {"x-flow-memory-api-key": key, "x-flow-memory-scopes": "compute:execute"},
        json.dumps({"job_id": "job_scope_escalation"}).encode("utf-8"),
    )

    assert denied_execute.status == 403
    assert denied_execute.body["error"]["code"] == "auth.forbidden"
    assert denied_execute.body["error"]["details"]["unauthorized"] == ("compute:execute",)
    assert denied_execute.body["error"]["details"]["granted"] == ("compute:read",)


def test_http_gateway_injects_authenticated_tenant_and_rejects_mismatch() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    key = "fmk_tenant_billing"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-billing-key",
                    "key_prefix": "fmk_tenant_",
                    "key_hash": api_key_hash(key),
                    "tenant_id": "tenant_billing",
                    "principal": "svc-billing",
                    "scopes": "compute:billing",
                    "enabled": True,
                },
            ),
        )
    )
    try:
        scoped = gateway.handle("GET", "/billing/balance", {"x-flow-memory-api-key": key})
        mismatch = gateway.handle("GET", "/billing/balance?tenant_id=tenant_other", {"x-flow-memory-api-key": key})
    finally:
        reset_default_service(None)

    assert scoped.status == 200
    assert scoped.body["data"]["balance"]["account_id"] == "tenant_billing"
    assert mismatch.status == 403
    assert mismatch.body["error"]["code"] == "auth.forbidden"
    assert mismatch.body["error"]["details"]["tenant_id"] == "tenant_billing"
    assert mismatch.body["error"]["details"]["requested_tenant_id"] == "tenant_other"


def test_http_gateway_tenantless_non_admin_key_rejects_tenant_header() -> None:
    key = "fmk_global_read_secret"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenantless-read-key",
                    "key_prefix": "fmk_global_",
                    "key_hash": api_key_hash(key),
                    "tenant_id": "",
                    "principal": "svc-global-read",
                    "scopes": "compute:read",
                    "enabled": True,
                },
            ),
        )
    )

    without_tenant_header = gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": key})
    with_tenant_header = gateway.handle(
        "GET",
        "/compute/health",
        {"x-flow-memory-api-key": key, "x-flow-memory-tenant": "tenant_other"},
    )

    assert without_tenant_header.status == 200
    assert with_tenant_header.status == 403
    assert with_tenant_header.body["error"]["code"] == "auth.forbidden"
    assert with_tenant_header.body["error"]["details"]["key_id"] == "tenantless-read-key"
    assert with_tenant_header.body["error"]["details"]["requested_tenant_id"] == "tenant_other"


def test_http_gateway_legacy_key_still_accepts_tenant_header() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            api_key="dev",
            api_key_scopes=("compute:billing",),
            require_scopes=True,
            enable_rate_limit=False,
        )
    )
    try:
        response = gateway.handle(
            "GET",
            "/billing/balance",
            {"x-flow-memory-api-key": "dev", "x-flow-memory-tenant": "tenant_legacy", "x-flow-memory-scopes": "compute:billing"},
        )
    finally:
        reset_default_service(None)

    assert response.status == 200
    assert response.body["data"]["balance"]["account_id"] == "tenant_legacy"


def test_http_gateway_billing_reads_are_tenant_scoped_and_fail_closed() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    service.store.put_record(
        "usage_charge",
        "usage_tenant_a",
        {"usage_charge_id": "usage_tenant_a", "account_id": "tenant_billing_a", "amount": 1.0, "currency": "USD"},
        tenant_id="tenant_billing_a",
    )
    service.store.put_record(
        "usage_charge",
        "usage_tenant_b",
        {"usage_charge_id": "usage_tenant_b", "account_id": "tenant_billing_b", "amount": 2.0, "currency": "USD"},
        tenant_id="tenant_billing_b",
    )
    service.store.put_record(
        "provider_payout",
        "payout_tenant_a",
        {
            "provider_payout_id": "payout_tenant_a",
            "account_id": "tenant_billing_a",
            "provider_id": "provider_a",
            "amount": 1.0,
            "currency": "USD",
            "status": "accrued",
        },
        tenant_id="tenant_billing_a",
        provider_id="provider_a",
        status="accrued",
    )
    service.store.put_record(
        "provider_payout",
        "payout_tenant_b",
        {
            "provider_payout_id": "payout_tenant_b",
            "account_id": "tenant_billing_b",
            "provider_id": "provider_b",
            "amount": 2.0,
            "currency": "USD",
            "status": "accrued",
        },
        tenant_id="tenant_billing_b",
        provider_id="provider_b",
        status="accrued",
    )
    reset_default_service(service)
    tenant_key = "fmk_tenant_billing_a"
    unbound_key = "fmk_unbound_billing"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-billing-a-key",
                    "key_prefix": "fmk_tenant_billing_a",
                    "key_hash": api_key_hash(tenant_key),
                    "tenant_id": "tenant_billing_a",
                    "principal": "svc-billing-a",
                    "scopes": "compute:billing",
                    "enabled": True,
                },
                {
                    "key_id": "unbound-billing-key",
                    "key_prefix": "fmk_unbound_billing",
                    "key_hash": api_key_hash(unbound_key),
                    "principal": "svc-billing-unbound",
                    "scopes": "compute:billing",
                    "enabled": True,
                },
            ),
        )
    )
    try:
        scoped_usage = gateway.handle("GET", "/billing/usage", {"x-flow-memory-api-key": tenant_key})
        scoped_payouts = gateway.handle("GET", "/billing/provider-payouts?status=accrued", {"x-flow-memory-api-key": tenant_key})
        mismatched_account = gateway.handle(
            "GET",
            "/billing/usage?account_id=tenant_billing_b",
            {"x-flow-memory-api-key": tenant_key},
        )
        unbound_usage = gateway.handle("GET", "/billing/usage", {"x-flow-memory-api-key": unbound_key})
        unbound_payouts = gateway.handle("GET", "/billing/provider-payouts?status=accrued", {"x-flow-memory-api-key": unbound_key})
        explicit_unbound_usage = gateway.handle(
            "GET",
            "/billing/usage?account_id=tenant_billing_b",
            {"x-flow-memory-api-key": unbound_key},
        )
    finally:
        reset_default_service(None)

    assert scoped_usage.status == 200
    assert [charge["usage_charge_id"] for charge in scoped_usage.body["data"]["usage_charges"]] == ["usage_tenant_a"]
    assert scoped_payouts.status == 200
    assert [payout["provider_payout_id"] for payout in scoped_payouts.body["data"]["provider_payouts"]] == ["payout_tenant_a"]
    assert mismatched_account.status == 400
    assert mismatched_account.body["error"]["message"] == "account_id must match tenant_id"
    assert unbound_usage.status == 400
    assert unbound_usage.body["error"]["message"] == "account_id or tenant_id is required"
    assert unbound_payouts.status == 400
    assert unbound_payouts.body["error"]["message"] == "account_id or tenant_id is required"
    assert explicit_unbound_usage.status == 200
    assert [charge["usage_charge_id"] for charge in explicit_unbound_usage.body["data"]["usage_charges"]] == ["usage_tenant_b"]


def test_http_gateway_billing_writes_are_tenant_scoped_and_fail_closed() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    service.store.put_record(
        "usage_charge",
        "usage_tenant_write_b",
        {
            "usage_charge_id": "usage_tenant_write_b",
            "account_id": "tenant_billing_write_b",
            "amount": 2.0,
            "currency": "USD",
            "status": "dry_run_recorded",
        },
        tenant_id="tenant_billing_write_b",
    )
    service.store.put_record(
        "provider_payout",
        "payout_tenant_write_b",
        {
            "provider_payout_id": "payout_tenant_write_b",
            "account_id": "tenant_billing_write_b",
            "provider_id": "provider_write_b",
            "amount": 2.0,
            "currency": "USD",
            "status": "accrued",
        },
        tenant_id="tenant_billing_write_b",
        provider_id="provider_write_b",
        status="accrued",
    )
    reset_default_service(service)
    tenant_key = "fmk_tenant_billing_write_a"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-billing-write-a-key",
                    "key_prefix": "fmk_tenant_billing_write_a",
                    "key_hash": api_key_hash(tenant_key),
                    "tenant_id": "tenant_billing_write_a",
                    "principal": "svc-billing-write-a",
                    "scopes": "compute:billing",
                    "enabled": True,
                },
            ),
        )
    )
    try:
        checkout = gateway.handle(
            "POST",
            "/billing/checkout",
            {"x-flow-memory-api-key": tenant_key},
            json.dumps({"account_id": "tenant_billing_write_b", "amount": 10, "currency": "USD"}).encode("utf-8"),
        )
        webhook = gateway.handle(
            "POST",
            "/billing/webhooks/stripe",
            {"x-flow-memory-api-key": tenant_key},
            json.dumps(
                {
                    "raw_event": {
                        "id": "evt_tenant_write_b",
                        "type": "checkout.session.completed",
                        "amount": 100,
                        "currency": "usd",
                        "metadata": {"account_id": "tenant_billing_write_b"},
                    }
                }
            ).encode("utf-8"),
        )
        refund = gateway.handle(
            "POST",
            "/billing/refund",
            {"x-flow-memory-api-key": tenant_key},
            json.dumps({"usage_charge_id": "usage_tenant_write_b", "reason": "cross-tenant-attempt"}).encode("utf-8"),
        )
        settle = gateway.handle(
            "POST",
            "/billing/provider-payouts/payout_tenant_write_b/settle",
            {"x-flow-memory-api-key": tenant_key},
            json.dumps({"external_payout_reference": "cross-tenant-attempt"}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert checkout.status == 400
    assert checkout.body["error"]["message"] == "account_id must match tenant_id"
    assert webhook.status == 400
    assert webhook.body["error"]["message"] == "tenant_id must match billing record account_id"
    assert refund.status == 400
    assert refund.body["error"]["message"] == "tenant_id must match billing record account_id"
    assert settle.status == 400
    assert settle.body["error"]["message"] == "tenant_id must match billing record account_id"
    assert service.store.count_records("payment_event") == 0
    assert service.store.count_records("refund") == 0
    payout = service.store.get_record("provider_payout", "payout_tenant_write_b")
    assert payout is not None
    assert payout["status"] == "accrued"


def test_http_gateway_job_reads_and_claims_are_tenant_isolated() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    key_a = "fmk_tenant_job_a"
    key_b = "fmk_tenant_job_b"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-job-a-key",
                    "key_prefix": "fmk_tenant_job_a",
                    "key_hash": api_key_hash(key_a),
                    "tenant_id": "tenant_job_a",
                    "principal": "svc-job-a",
                    "scopes": ("compute:execute", "compute:read"),
                    "enabled": True,
                },
                {
                    "key_id": "tenant-job-b-key",
                    "key_prefix": "fmk_tenant_job_b",
                    "key_hash": api_key_hash(key_b),
                    "tenant_id": "tenant_job_b",
                    "principal": "svc-job-b",
                    "scopes": ("compute:execute", "compute:read"),
                    "enabled": True,
                },
            ),
        )
    )
    job_payload = {
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/tenant-job.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "tenant-job-route",
        "provider_id": "tenant-job-provider",
    }
    try:
        created = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": key_a},
            json.dumps(job_payload).encode("utf-8"),
        )
        job_id = str(created.body["data"]["job"]["job_id"])
        gateway.handle("POST", f"/compute/jobs/{job_id}/dispatch", {"x-flow-memory-api-key": key_a})
        completed = gateway.handle(
            "POST",
            f"/compute/jobs/{job_id}/complete",
            {"x-flow-memory-api-key": key_a},
            json.dumps({"actual_total_cost": 0.12, "artifact_ref": "s3://flow-memory-results/tenant-job.json", "artifact_data": {"tenant": "a"}}).encode("utf-8"),
        )
        allowed_job = gateway.handle("GET", f"/compute/jobs/{job_id}", {"x-flow-memory-api-key": key_a})
        allowed_events = gateway.handle("GET", f"/compute/jobs/{job_id}/events", {"x-flow-memory-api-key": key_a})
        allowed_artifacts = gateway.handle("GET", f"/compute/jobs/{job_id}/artifacts", {"x-flow-memory-api-key": key_a})
        allowed_artifacts_page = gateway.handle("GET", f"/compute/jobs/{job_id}/artifacts?limit=1", {"x-flow-memory-api-key": key_a})
        denied_job = gateway.handle("GET", f"/compute/jobs/{job_id}", {"x-flow-memory-api-key": key_b})
        denied_events = gateway.handle("GET", f"/compute/jobs/{job_id}/events", {"x-flow-memory-api-key": key_b})
        denied_artifacts = gateway.handle("GET", f"/compute/jobs/{job_id}/artifacts", {"x-flow-memory-api-key": key_b})
        denied_cancel = gateway.handle("POST", f"/compute/jobs/{job_id}/cancel", {"x-flow-memory-api-key": key_b})

        queued = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": key_a},
            json.dumps({**job_payload, "job_id": "job_tenant_a_claim"}).encode("utf-8"),
        )
        queued_job_id = str(queued.body["data"]["job"]["job_id"])
        denied_claim = gateway.handle(
            "POST",
            "/compute/jobs/claim",
            {"x-flow-memory-api-key": key_b},
            json.dumps({"job_id": queued_job_id, "worker_id": "worker_b"}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert created.status == 200
    assert created.body["data"]["job"]["tenant_id"] == "tenant_job_a"
    assert completed.status == 200
    assert allowed_job.status == 200
    assert allowed_events.status == 200
    assert allowed_events.body["data"]["events"]
    assert allowed_artifacts.status == 200
    assert allowed_artifacts_page.status == 200
    assert len(allowed_artifacts_page.body["data"]["artifacts"]) == 1
    assert "next_cursor" in allowed_artifacts_page.body["data"]
    assert allowed_artifacts.body["data"]["artifacts"]
    assert denied_job.status == 404
    assert denied_events.status == 404
    assert denied_artifacts.status == 404
    assert denied_cancel.status == 404
    assert denied_claim.status == 400
    assert service.get_job(queued_job_id)["job"]["status"] == "queued"


def test_http_gateway_full_billing_lifecycle_is_tenant_scoped() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )
    reset_default_service(service)
    key_a = "fmk_tenant_billing_lifecycle_a"
    key_b = "fmk_tenant_billing_lifecycle_b"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-billing-lifecycle-a-key",
                    "key_prefix": "fmk_tenant_billing_lifecycle_a",
                    "key_hash": api_key_hash(key_a),
                    "tenant_id": "tenant_billing_lifecycle_a",
                    "principal": "svc-billing-lifecycle-a",
                    "scopes": ("compute:billing", "compute:execute", "compute:read"),
                    "enabled": True,
                },
                {
                    "key_id": "tenant-billing-lifecycle-b-key",
                    "key_prefix": "fmk_tenant_billing_lifecycle_b",
                    "key_hash": api_key_hash(key_b),
                    "tenant_id": "tenant_billing_lifecycle_b",
                    "principal": "svc-billing-lifecycle-b",
                    "scopes": ("compute:billing", "compute:execute", "compute:read"),
                    "enabled": True,
                },
            ),
        )
    )
    job_payload = {
        "job_id": "job_gateway_paid_compute_a",
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/gateway-paid.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "route_gateway_paid",
        "provider_id": "provider_gateway_paid",
        "account_id": "tenant_billing_lifecycle_a",
        "estimated_total_cost": 0.18,
        "currency": "USD",
    }
    raw_event = {
        "id": "evt_gateway_paid_compute_a",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "tenant_billing_lifecycle_a"},
    }
    webhook_secret = "whsec_gateway_lifecycle"
    stripe_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        content_hash(raw_event).encode("utf-8"),
        "sha256",
    ).hexdigest()
    try:
        webhook = gateway.handle(
            "POST",
            "/billing/webhooks/stripe",
            {"x-flow-memory-api-key": key_a},
            json.dumps(
                {
                    "raw_event": raw_event,
                    "webhook_secret": webhook_secret,
                    "stripe_signature": stripe_signature,
                }
            ).encode("utf-8"),
        )
        created = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": key_a},
            json.dumps(job_payload).encode("utf-8"),
        )
        job_id = str(created.body["data"]["job"]["job_id"])
        dispatched = gateway.handle("POST", f"/compute/jobs/{job_id}/dispatch", {"x-flow-memory-api-key": key_a})
        completed = gateway.handle(
            "POST",
            f"/compute/jobs/{job_id}/complete",
            {"x-flow-memory-api-key": key_a},
            json.dumps(
                {
                    "account_id": "tenant_billing_lifecycle_a",
                    "actual_units": 2,
                    "actual_total_cost": 0.18,
                    "currency": "USD",
                }
            ).encode("utf-8"),
        )
        balance = gateway.handle("GET", "/billing/balance", {"x-flow-memory-api-key": key_a})
        payouts = gateway.handle("GET", "/billing/provider-payouts?status=accrued", {"x-flow-memory-api-key": key_a})
        payout_id = str(completed.body["data"]["provider_payout"]["provider_payout_id"])
        settled = gateway.handle(
            "POST",
            f"/billing/provider-payouts/{payout_id}/settle",
            {"x-flow-memory-api-key": key_a},
            json.dumps(
                {
                    "external_payout_reference": "manual-ledger-gateway-1",
                    "settled_by": "ops",
                }
            ).encode("utf-8"),
        )
        tenant_b_job = gateway.handle("GET", f"/compute/jobs/{job_id}", {"x-flow-memory-api-key": key_b})
        tenant_b_dispatch = gateway.handle("POST", f"/compute/jobs/{job_id}/dispatch", {"x-flow-memory-api-key": key_b})
        tenant_b_mismatched_job = gateway.handle(
            "POST",
            "/compute/jobs",
            {"x-flow-memory-api-key": key_b},
            json.dumps({**job_payload, "job_id": "job_gateway_paid_compute_b_mismatch"}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert webhook.status == 200
    assert created.status == 200
    assert created.body["data"]["job"]["tenant_id"] == "tenant_billing_lifecycle_a"
    assert dispatched.status == 200
    assert dispatched.body["data"]["credit_reservation"]["status"] == "reserved"
    assert completed.status == 200
    assert completed.body["data"]["credit_debit"]["status"] == "posted"
    assert completed.body["data"]["provider_payout"]["status"] == "accrued"
    assert completed.body["data"]["provider_payout"]["funds_moved"] is False
    assert balance.status == 200
    assert balance.body["data"]["balance"]["available_credits"] == 0.82
    assert balance.body["data"]["balance"]["reserved_credits"] == 0.0
    assert payouts.status == 200
    assert [payout["provider_payout_id"] for payout in payouts.body["data"]["provider_payouts"]] == [payout_id]
    assert settled.status == 200
    assert settled.body["data"]["provider_payout"]["status"] == "settled"
    assert settled.body["data"]["provider_payout"]["funds_moved"] is False
    assert tenant_b_job.status == 404
    assert tenant_b_dispatch.status == 404
    assert tenant_b_mismatched_job.status == 400
    assert tenant_b_mismatched_job.body["error"]["message"] == "account_id must match tenant_id"
    assert any(
        metric.get("name") == "billing_payout_settled_total"
        and metric.get("labels", {}).get("provider_id") == "provider_gateway_paid"
        and metric.get("value") == 0.18
        for metric in service.telemetry.snapshot(reset=False)["metrics"]
    )


def test_http_gateway_accepts_direct_stripe_webhook_body_with_signature_header() -> None:
    secret = "whsec_http_gateway_secret"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            stripe_webhook_secret=secret,
        ),
    )
    reset_default_service(service)
    raw_event = {
        "id": "evt_http_stripe",
        "type": "checkout.session.completed",
        "amount_total": 3300,
        "currency": "usd",
        "metadata": {"account_id": "acct_http_stripe"},
    }
    raw_body = json.dumps(raw_event, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = str(int(time.time()))
    signed_body = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_body, "sha256").hexdigest()
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    try:
        response = gateway.handle(
            "POST",
            "/billing/webhooks/stripe",
            {"Stripe-Signature": f"t={timestamp},v1={digest}"},
            raw_body,
        )
    finally:
        reset_default_service(None)

    assert response.status == 200
    assert response.body["data"]["payment_event"]["verified"] is True
    assert response.body["data"]["credit_transaction"]["amount"] == 33.0


def test_http_gateway_accepts_stripe_signature_auth_when_scopes_required() -> None:
    secret = "whsec_http_gateway_scoped_secret"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            stripe_webhook_secret=secret,
        ),
    )
    reset_default_service(service)
    raw_event = {
        "id": "evt_http_stripe_scoped",
        "type": "checkout.session.completed",
        "amount_total": 1700,
        "currency": "usd",
        "metadata": {"account_id": "acct_http_stripe_scoped"},
    }
    raw_body = json.dumps(raw_event, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = str(int(time.time()))
    signed_body = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_body, "sha256").hexdigest()
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            api_key="flow-memory-api-key",
            require_scopes=True,
            enable_rate_limit=False,
        )
    )
    try:
        allowed = gateway.handle(
            "POST",
            "/billing/webhooks/stripe",
            {"Stripe-Signature": f"t={timestamp},v1={digest}"},
            raw_body,
        )
        denied = gateway.handle(
            "POST",
            "/billing/webhooks/stripe",
            {"Stripe-Signature": f"t={timestamp},v1=bad"},
            raw_body,
        )
    finally:
        reset_default_service(None)

    assert allowed.status == 200
    assert allowed.body["data"]["payment_event"]["verified"] is True
    assert allowed.body["data"]["credit_transaction"]["amount"] == 17.0
    assert denied.status == 401
    assert denied.body["error"]["code"] == "auth.invalid"


def test_http_gateway_api_key_management_rotates_active_tenant_key() -> None:
    admin_key = "fmk_admin_secret"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "admin-key",
                    "key_prefix": "fmk_admin_",
                    "key_hash": api_key_hash(admin_key),
                    "tenant_id": "",
                    "principal": "svc-admin",
                    "scopes": "api:admin",
                    "enabled": True,
                },
            ),
        )
    )
    create_response = gateway.handle(
        "POST",
        "/auth/api-keys",
        {"x-flow-memory-api-key": admin_key},
        json.dumps(
            {
                "key_id": "tenant-compute-key-v1",
                "tenant_id": "tenant_compute",
                "principal": "svc-compute",
                "scopes": ["compute:read"],
                "key_prefix": "fmk_compute_",
            }
        ).encode("utf-8"),
    )
    assert create_response.status == 200
    issued_key = create_response.body["data"]["api_key"]
    public_record = create_response.body["data"]["record"]
    assert "key_hash" not in public_record
    assert public_record["key_hash_configured"] is True
    assert gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": issued_key}).status == 200

    rotate_response = gateway.handle(
        "POST",
        "/auth/api-keys/tenant-compute-key-v1/rotate",
        {"x-flow-memory-api-key": admin_key},
        json.dumps({"key_id": "tenant-compute-key-v2"}).encode("utf-8"),
    )
    assert rotate_response.status == 200
    rotated_key = rotate_response.body["data"]["api_key"]
    assert rotate_response.body["data"]["previous_record"]["status"] == "rotated"
    assert gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": issued_key}).status == 401
    assert gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": rotated_key}).status == 200

    disable_response = gateway.handle(
        "POST",
        "/auth/api-keys/tenant-compute-key-v2/disable",
        {"x-flow-memory-api-key": admin_key},
        json.dumps({"reason": "operator_rotation_test"}).encode("utf-8"),
    )
    assert disable_response.status == 200
    assert disable_response.body["data"]["record"]["status"] == "disabled"
    assert gateway.handle("GET", "/compute/health", {"x-flow-memory-api-key": rotated_key}).status == 401


def test_http_gateway_tenant_bound_admin_cannot_manage_other_tenant() -> None:
    admin_key = "fmk_tenant_admin_secret"
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            require_scopes=True,
            enable_rate_limit=False,
            api_key_records=(
                {
                    "key_id": "tenant-admin-key",
                    "key_prefix": "fmk_tenant_admin_",
                    "key_hash": api_key_hash(admin_key),
                    "tenant_id": "tenant_a",
                    "principal": "svc-tenant-admin",
                    "scopes": "api:admin",
                    "enabled": True,
                },
            ),
        )
    )
    gateway.router.api_key_records["tenant-b-existing"] = {
        "key_id": "tenant-b-existing",
        "key_prefix": "fmk_tenant_b_",
        "key_hash": api_key_hash("fmk_existing_tenant_b"),
        "tenant_id": "tenant_b",
        "principal": "svc-tenant-b-existing",
        "scopes": "compute:read",
        "enabled": True,
    }
    gateway.router.api_key_records["tenant-a-existing"] = {
        "key_id": "tenant-a-existing",
        "key_prefix": "fmk_tenant_a_",
        "key_hash": api_key_hash("fmk_existing_tenant_a"),
        "tenant_id": "tenant_a",
        "principal": "svc-tenant-a-existing",
        "scopes": "compute:read",
        "enabled": True,
    }

    denied = gateway.handle(
        "POST",
        "/auth/api-keys",
        {"x-flow-memory-api-key": admin_key},
        json.dumps(
            {
                "key_id": "tenant-b-key",
                "tenant_id": "tenant_b",
                "principal": "svc-tenant-b",
                "scopes": ["compute:read"],
                "key_prefix": "fmk_tenant_b_",
            }
        ).encode("utf-8"),
    )
    allowed = gateway.handle(
        "POST",
        "/auth/api-keys",
        {"x-flow-memory-api-key": admin_key},
        json.dumps(
            {
                "key_id": "tenant-a-key",
                "principal": "svc-tenant-a",
                "scopes": ["compute:read"],
                "key_prefix": "fmk_tenant_a_",
            }
        ).encode("utf-8"),
    )
    listed = gateway.handle("GET", "/auth/api-keys", {"x-flow-memory-api-key": admin_key})
    rotate_other = gateway.handle(
        "POST",
        "/auth/api-keys/tenant-b-existing/rotate",
        {"x-flow-memory-api-key": admin_key},
        json.dumps({"key_id": "tenant-b-rotated"}).encode("utf-8"),
    )
    disable_other = gateway.handle(
        "POST",
        "/auth/api-keys/tenant-b-existing/disable",
        {"x-flow-memory-api-key": admin_key},
        json.dumps({"reason": "tenant_boundary_test"}).encode("utf-8"),
    )

    assert denied.status == 403
    assert denied.body["error"]["code"] == "auth.forbidden"
    assert denied.body["error"]["details"]["tenant_id"] == "tenant_a"
    assert denied.body["error"]["details"]["requested_tenant_id"] == "tenant_b"
    assert allowed.status == 200
    assert allowed.body["data"]["record"]["tenant_id"] == "tenant_a"
    listed_key_ids = {record["key_id"] for record in listed.body["data"]["api_keys"]}
    assert listed.status == 200
    assert "tenant-a-existing" in listed_key_ids
    assert "tenant-a-key" in listed_key_ids
    assert "tenant-b-existing" not in listed_key_ids
    assert rotate_other.status == 403
    assert rotate_other.body["error"]["details"]["tenant_id"] == "tenant_a"
    assert rotate_other.body["error"]["details"]["requested_tenant_id"] == "tenant_b"
    assert disable_other.status == 403
    assert disable_other.body["error"]["details"]["tenant_id"] == "tenant_a"
    assert disable_other.body["error"]["details"]["requested_tenant_id"] == "tenant_b"


def test_http_gateway_injects_provider_receipt_client_ip(monkeypatch: Any) -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("127.0.0.1",),
        ),
    )
    key = LocalKeyPair("provider-receipt-key", "provider-receipt-secret")
    monkeypatch.setenv("FLOW_MEMORY_PROVIDER_RECEIPT_SECRET", key.secret)
    service.create_provider(
        {
            "provider_id": "receipt-provider",
            "provider_name": "Receipt Provider",
            "provider_type": "gpu",
            "metadata": {
                "callback_signing_key_id": key.key_id,
                "callback_signing_key_env": "FLOW_MEMORY_PROVIDER_RECEIPT_SECRET",
            },
        }
    )
    job_id = str(
        service.create_job(
            {
                "task_type": "inference",
                "input_ref": "s3://flow-memory-inputs/job-http.json",
                "model_or_runtime": "llama-runtime",
                "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
                "budget_policy_id": "policy_default",
                "route_id": "receipt-route",
                "provider_id": "receipt-provider",
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(job_id, {})
    receipt = {
        "receipt_id": "receipt-http-ip-blocked",
        "timestamp": "2099-01-01T00:00:00Z",
        "job_id": job_id,
        "provider_id": "receipt-provider",
        "route_id": "receipt-route",
        "status": "succeeded",
        "actual_total_cost": 0.18,
    }
    reset_default_service(service)
    try:
        gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))
        response = gateway.handle(
            "POST",
            f"/compute/jobs/{job_id}/receipt",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:execute",
                "x-flow-memory-client-ip": "198.51.100.77",
            },
            json.dumps({"receipt": receipt, "signature": sign_payload(receipt, key).as_record()}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert response.status == 200
    assert response.body["data"]["ok"] is False
    assert response.body["data"]["error"]["error_code"] == "provider_receipt.ip_not_allowed"


def test_http_gateway_injects_provider_state_callback_client_ip() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("127.0.0.1",),
        ),
    )
    service.create_provider(
        {
            "provider_id": "callback-provider",
            "provider_name": "Callback Provider",
            "provider_type": "gpu",
        }
    )
    base_job = {
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/job-http.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "callback-route",
        "provider_id": "callback-provider",
    }
    callback_payloads: dict[str, dict[str, Any]] = {
        "complete": {"actual_total_cost": 0.18},
        "fail": {"error_code": "provider_execution_failed", "reason": "blocked by callback allowlist"},
        "heartbeat": {"worker_id": "worker_1", "ttl_seconds": 60},
    }
    job_ids: dict[str, str] = {}
    responses: dict[str, Any] = {}

    reset_default_service(service)
    try:
        gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))
        for callback_action, payload in callback_payloads.items():
            job_id = str(service.create_job({**base_job, "job_id": f"job_{callback_action}_ip_blocked"})["job"]["job_id"])
            if callback_action in {"complete", "heartbeat"}:
                service.dispatch_job(job_id, {})
            job_ids[callback_action] = job_id
            responses[callback_action] = gateway.handle(
                "POST",
                f"/compute/jobs/{job_id}/{callback_action}",
                {
                    "x-flow-memory-api-key": "dev",
                    "x-flow-memory-scopes": "compute:execute",
                    "x-flow-memory-client-ip": "198.51.100.77",
                },
                json.dumps(payload).encode("utf-8"),
            )
    finally:
        reset_default_service(None)

    for callback_action, response in responses.items():
        assert response.status == 200
        assert response.body["data"]["ok"] is False
        assert response.body["data"]["error"]["error_code"] == "provider_callback.ip_not_allowed"
        assert response.body["data"]["error"]["details"]["callback_action"] == callback_action
    assert service.get_job(job_ids["complete"])["job"]["status"] == "running"
    assert service.get_job(job_ids["fail"])["job"]["status"] == "queued"
    assert service.get_job(job_ids["heartbeat"])["job"]["status"] == "running"
    assert "heartbeat_count" not in service.get_job(job_ids["heartbeat"])["job"]


def test_http_gateway_rejects_provider_callback_ip_before_router() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("203.0.113.0/24",),
        ),
    )
    service.create_provider(
        {
            "provider_id": "gateway-callback-provider",
            "provider_name": "Gateway Callback Provider",
            "provider_type": "gpu",
        }
    )
    base_job = {
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/job-gateway-callback.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "gateway-callback-route",
        "provider_id": "gateway-callback-provider",
    }
    allowed_job_id = str(service.create_job({**base_job, "job_id": "job_gateway_callback_allowed"})["job"]["job_id"])
    blocked_job_id = str(service.create_job({**base_job, "job_id": "job_gateway_callback_blocked"})["job"]["job_id"])
    missing_ip_job_id = str(service.create_job({**base_job, "job_id": "job_gateway_callback_missing_ip"})["job"]["job_id"])
    service.dispatch_job(allowed_job_id, {})
    service.dispatch_job(blocked_job_id, {})
    service.dispatch_job(missing_ip_job_id, {})

    reset_default_service(service)
    try:
        gateway = HttpApiGateway(
            config=HttpApiConfig(
                api_key="dev",
                require_scopes=True,
                enable_rate_limit=False,
                provider_callback_ip_allowlist=("203.0.113.0/24",),
            )
        )
        blocked = gateway.handle(
            "POST",
            f"/compute/jobs/{blocked_job_id}/complete",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:execute",
                "x-flow-memory-client-ip": "198.51.100.77",
            },
            json.dumps({"actual_total_cost": 0.18}).encode("utf-8"),
        )
        missing_ip = gateway.handle(
            "POST",
            f"/compute/jobs/{missing_ip_job_id}/heartbeat",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:execute",
            },
            json.dumps({"worker_id": "worker_missing_ip", "ttl_seconds": 60}).encode("utf-8"),
        )
        allowed = gateway.handle(
            "POST",
            f"/compute/jobs/{allowed_job_id}/complete",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:execute",
                "x-flow-memory-client-ip": "203.0.113.42",
            },
            json.dumps({"actual_total_cost": 0.18}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert blocked.status == 403
    assert blocked.body["error"]["code"] == "auth.forbidden"
    assert blocked.body["error"]["details"]["callback_action"] == "complete"
    assert blocked.body["error"]["details"]["client_ip"] == "198.51.100.77"
    assert missing_ip.status == 403
    assert missing_ip.body["error"]["details"]["callback_action"] == "heartbeat"
    assert missing_ip.body["error"]["details"]["client_ip"] == ""
    assert allowed.status == 200
    assert allowed.body["data"]["job"]["status"] == "succeeded"
    assert service.get_job(blocked_job_id)["job"]["status"] == "running"
    assert service.get_job(missing_ip_job_id)["job"]["status"] == "running"
    assert "heartbeat_count" not in service.get_job(missing_ip_job_id)["job"]


def test_http_gateway_enforces_provider_callback_allowlist_for_quote_ingest() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("203.0.113.0/24",),
        ),
    )
    quote = {
        "quote_id": "quote_http_ingest_allowed",
        "provider_id": "provider_http_ingest",
        "route_id": "route_http_ingest",
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2,
        "estimated_total_cost": 0.18,
        "currency_or_asset": "USDC",
        "network": "solana",
        "confidence": 0.93,
        "capacity_available": True,
        "quote_ttl_seconds": 300,
        "expires_at": "2099-01-01T00:00:00Z",
        "settlement_modes": ["generic_dry_run"],
        "dry_run_supported": True,
        "assumptions": [],
    }

    reset_default_service(service)
    try:
        gateway = HttpApiGateway(
            config=HttpApiConfig(
                api_key="dev",
                require_scopes=True,
                enable_rate_limit=False,
                provider_callback_ip_allowlist=("203.0.113.0/24",),
            )
        )
        blocked = gateway.handle(
            "POST",
            "/market/quotes/ingest",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:provider-admin",
                "x-flow-memory-client-ip": "198.51.100.77",
            },
            json.dumps({"quote": quote}).encode("utf-8"),
        )
        missing_ip = gateway.handle(
            "POST",
            "/market/quotes/ingest",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:provider-admin",
            },
            json.dumps({"quote": {**quote, "quote_id": "quote_http_ingest_missing"}}).encode("utf-8"),
        )
        allowed = gateway.handle(
            "POST",
            "/market/quotes/ingest",
            {
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:provider-admin",
                "x-flow-memory-client-ip": "203.0.113.42",
            },
            json.dumps({"quote": quote}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)

    assert blocked.status == 403
    assert blocked.body["error"]["details"]["callback_action"] == "ingest"
    assert blocked.body["error"]["details"]["client_ip"] == "198.51.100.77"
    assert missing_ip.status == 403
    assert missing_ip.body["error"]["details"]["callback_action"] == "ingest"
    assert missing_ip.body["error"]["details"]["client_ip"] == ""
    assert allowed.status == 200
    assert allowed.body["data"]["ok"] is True
    assert service.store.count_records("compute_quote") == 1


def test_dependency_free_http_server_uses_socket_client_ip_over_spoofed_header(tmp_path: Any) -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(str(tmp_path / "socket-ip.sqlite3")),
        config=ComputeMarketConfig(
            database_url=str(tmp_path / "socket-ip.sqlite3"),
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("127.0.0.1",),
        ),
    )
    quote = {
        "quote_id": "quote_http_socket_ip",
        "provider_id": "provider_http_socket_ip",
        "route_id": "route_http_socket_ip",
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2,
        "estimated_total_cost": 0.18,
        "currency_or_asset": "USDC",
        "network": "solana",
        "confidence": 0.93,
        "capacity_available": True,
        "quote_ttl_seconds": 300,
        "expires_at": "2099-01-01T00:00:00Z",
        "settlement_modes": ["generic_dry_run"],
        "dry_run_supported": True,
        "assumptions": [],
    }
    data: dict[str, Any] = {}

    reset_default_service(service)
    gateway = HttpApiGateway(
        config=HttpApiConfig(
            api_key="dev",
            require_scopes=True,
            enable_rate_limit=False,
            provider_callback_ip_allowlist=("127.0.0.1",),
        )
    )
    server = create_http_server(gateway, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/market/quotes/ingest",
            data=json.dumps({"quote": quote}).encode("utf-8"),
            headers={
                "x-flow-memory-api-key": "dev",
                "x-flow-memory-scopes": "compute:provider-admin",
                "x-flow-memory-client-ip": "203.0.113.42",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        reset_default_service(None)

    assert data["data"]["ok"] is True
    assert service.store.count_records("compute_quote") == 1


def test_dependency_free_http_server_handles_local_request() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    server = create_http_server(gateway, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"x-flow-memory-scopes": "api:read"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        assert data["data"]["service"] == "flow-memory"
    finally:
        server.shutdown()
        server.server_close()
