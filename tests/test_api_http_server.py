import json
import threading
import urllib.error
import urllib.request

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway, create_http_server


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
