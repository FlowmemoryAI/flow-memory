import json
import time
import threading
import urllib.error
import urllib.request

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, create_http_server
from flow_memory.api.auth import api_key_hash
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore


def test_http_gateway_health_response():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response = gateway.handle("GET", "/health", {"x-flow-memory-scopes": "api:read"})
    assert response.status == 200
    assert response.body["data"]["ok"] is True
    assert response.headers["content-type"].startswith("application/json")


def test_http_gateway_api_key_auth_blocks_missing_key():
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
    assert root.body["data"]["auth"] == "API key required for /compute/* endpoints"


def test_http_gateway_nonce_check_blocks_replay_when_enabled():
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

def test_http_gateway_scope_enforcement():
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/health", {})
    allowed = gateway.handle("GET", "/health", {"x-flow-memory-scopes": "api:read"})
    assert denied.status == 403
    assert allowed.status == 200


def test_http_gateway_rate_limit():
    gateway = HttpApiGateway(config=HttpApiConfig(rate_limit=1, rate_limit_window_seconds=60))
    headers = {"x-flow-memory-scopes": "api:read", "x-flow-memory-principal": "alice"}
    assert gateway.handle("GET", "/health", headers).status == 200
    assert gateway.handle("GET", "/health", headers).status == 429


def test_http_gateway_invalid_json_error_contract():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response = gateway.handle("POST", "/runtime/tick", {"x-flow-memory-scopes": "api:write"}, b"{")
    assert response.status == 400
    assert response.body["error"]["code"] == "request.invalid"

def test_http_gateway_get_query_payload_reaches_router():
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


def test_http_gateway_tenant_api_key_supplies_scopes_without_scope_header():
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


def test_dependency_free_http_server_handles_local_request():
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
