import json
import hmac
import time
import threading
import urllib.error
import urllib.request
from typing import Any

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, create_http_server
from flow_memory.api.auth import RedisNonceReplayStore, api_key_hash
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload


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
