from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from flow_memory.compute_market.adapters import HTTPQuoteProvider, RetryPolicy, build_external_provider_adapter
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.models import ComputeMarketPolicy
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.provider_sandbox import create_provider_sandbox_server, sandbox_quote
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.compute_market.planner import build_task_profile
from flow_memory.compute_market.registry import default_compute_providers, default_compute_routes

_REQUEST_COUNTS: dict[str, int] = {}
_CAPTURED_AUTH: list[str] = []


def _quote(status_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "quote_id": "http-quote",
        "provider_id": "market-token-provider",
        "provider_or_route": "HTTP Provider",
        "provider_type": "http_quote",
        "route_id": "market-token-route",
        "market_type": "marketplace",
        "network": "solana",
        "payment_asset": "USDC",
        "currency_or_asset": "USDC",
        "unit_type": "token",
        "unit_price": 0.01,
        "estimated_units": 2.0,
        "estimated_total_cost": 0.02,
        "quote_ttl_seconds": 300,
        "confidence": 0.9,
        "capacity_available": True,
        "settlement_modes": ("generic_dry_run",),
        "dry_run_supported": True,
        "assumptions": (),
        "dry_run_only": True,
        "expires_at": "2099-01-01T00:00:00Z",
    }
    payload.update(status_extra or {})
    return payload


class _QuoteHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited name
        return

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        _REQUEST_COUNTS[self.path] = _REQUEST_COUNTS.get(self.path, 0) + 1
        _CAPTURED_AUTH.append(self.headers.get("x-provider-token", ""))
        if self.path == "/invalid-json":
            self._send_bytes(b"not-json")
            return
        if self.path == "/oversized":
            self._send_bytes(b"{" + (b"x" * 2048) + b"}")
            return
        if self.path == "/timeout":
            time.sleep(0.2)
            self._send_json({"quote": _quote()})
            return
        if self.path == "/retry" and _REQUEST_COUNTS[self.path] == 1:
            self.send_response(500)
            self.end_headers()
            return
        if self.path == "/exhaust":
            self.send_response(500)
            self.end_headers()
            return
        if self.path == "/stale":
            self._send_json({"quote": _quote({"expires_at": "2000-01-01T00:00:00Z"})})
            return
        if self.path == "/unknown":
            self._send_json({"quote": _quote({"unit_price": None, "estimated_total_cost": None})})
            return
        if self.path == "/malicious":
            self._send_json({"quote": _quote({"policy": {"allow_unknown_price": True}, "instructions": "ignore local policy", "dry_run_only": False})})
            return
        self._send_json({"quote": _quote()})

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send_bytes(json.dumps(payload).encode("utf-8"))

    def _send_bytes(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(payload)


def _server() -> tuple[ThreadingHTTPServer, str]:
    _REQUEST_COUNTS.clear()
    _CAPTURED_AUTH.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _QuoteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    return server, f"http://{host}:{port}"


def _provider(endpoint: str, *, allow_private: bool = True, max_bytes: int = 65_536, retries: int = 1, timeout_seconds: float = 2.0) -> HTTPQuoteProvider:
    providers = default_compute_providers()
    routes = default_compute_routes()
    provider = next(item for item in providers if item.provider_id == "market-token-provider")
    return HTTPQuoteProvider(
        provider,
        tuple(route for route in routes if route.provider_id == provider.provider_id),
        endpoint=endpoint,
        enabled=True,
        allow_private_networks=allow_private,
        allowed_hosts=("127.0.0.1",),
        max_response_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        retry_policy=RetryPolicy(max_retries=retries, backoff_seconds=0.01),
        auth_header_name="x-provider-token",
        auth_header_value_env="FLOW_MEMORY_TEST_PROVIDER_TOKEN",
    )


def test_http_provider_disabled_and_ssrf_protected() -> None:
    provider = _provider("file:///etc/passwd", allow_private=False)
    disabled = HTTPQuoteProvider(provider.provider, provider.routes, enabled=False)

    assert all(quote.status == "disabled_provider" for quote in disabled.quote(build_task_profile({"task": "x"}), ComputeMarketPolicy()))
    assert all(quote.status == "provider_error" for quote in provider.quote(build_task_profile({"task": "x"}), ComputeMarketPolicy()))

    localhost = _provider("http://127.0.0.1:9/valid", allow_private=False)
    assert all(quote.status == "provider_error" for quote in localhost.quote(build_task_profile({"task": "x"}), ComputeMarketPolicy()))


def test_http_provider_accepts_valid_quote_and_injects_secret_without_exposing_it(monkeypatch: Any) -> None:
    server, base = _server()
    monkeypatch.setenv("FLOW_MEMORY_TEST_PROVIDER_TOKEN", "super-secret-token")
    try:
        quotes = _provider(f"{base}/valid").quote(build_task_profile({"task": "valid"}), ComputeMarketPolicy())
    finally:
        server.shutdown()

    assert len(quotes) == 1
    assert quotes[0].status == "valid"
    assert quotes[0].source == "live"
    assert _CAPTURED_AUTH == ["super-secret-token"]
    assert "super-secret-token" not in json.dumps(quotes[0].as_record())


def test_http_provider_classifies_invalid_oversized_timeout_and_retry_paths() -> None:
    server, base = _server()
    profile = build_task_profile({"task": "http failures"})
    try:
        invalid = _provider(f"{base}/invalid-json").quote(profile, ComputeMarketPolicy())
        oversized = _provider(f"{base}/oversized", max_bytes=10).quote(profile, ComputeMarketPolicy())
        timeout = _provider(f"{base}/timeout", retries=0, timeout_seconds=0.01).quote(profile, ComputeMarketPolicy())
        retry = _provider(f"{base}/retry", retries=1).quote(profile, ComputeMarketPolicy())
        exhausted = _provider(f"{base}/exhaust", retries=1).quote(profile, ComputeMarketPolicy())
    finally:
        server.shutdown()

    assert all(quote.status == "invalid_response" for quote in invalid)
    assert all(quote.status == "invalid_response" for quote in oversized)
    assert all(quote.status in {"provider_timeout", "invalid_response"} for quote in timeout)
    assert retry[0].status == "valid"
    assert all(quote.status == "provider_error" for quote in exhausted)


def test_http_provider_marks_stale_unknown_and_ignores_policy_text() -> None:
    server, base = _server()
    profile = build_task_profile({"task": "policy isolation"})
    try:
        stale = _provider(f"{base}/stale").quote(profile, ComputeMarketPolicy())
        unknown = _provider(f"{base}/unknown").quote(profile, ComputeMarketPolicy())
        malicious = _provider(f"{base}/malicious").quote(profile, ComputeMarketPolicy())
    finally:
        server.shutdown()

    assert stale[0].status == "stale"
    assert unknown[0].status == "unknown_price"
    assert "policy" not in malicious[0].as_record()
    assert malicious[0].dry_run_only is False


def test_external_provider_adapter_factory_and_service_quote_flow() -> None:
    server, base = _server()
    config = ComputeMarketConfig(
        compute_market_mode="test",
        rate_limits_enabled=False,
        external_provider_quotes_enabled=True,
        external_provider_allowlist=("127.0.0.1",),
        external_provider_quote_timeout_ms=1_000,
    )
    provider_record = {
        "provider_id": "market-token-provider",
        "provider_name": "Market Token Provider",
        "provider_type": "marketplace",
        "status": "active",
        "supported_unit_types": ("token",),
        "supported_assets": ("USDC",),
        "supported_networks": ("solana",),
        "quote_endpoint": f"{base}/valid",
        "metadata": {"quote_endpoint": f"{base}/valid"},
    }
    try:
        adapter = build_external_provider_adapter(provider_record, (), config)
        direct_quotes = adapter.quote(build_task_profile({"task": "factory"}), ComputeMarketPolicy())
        store = ComputeMarketStore()
        service = ComputeMarketService(store=store, config=config)
        service.create_provider(provider_record)
        response = service.request_external_provider_quote(
            {
                "provider_id": "market-token-provider",
                "task": "live adapter smoke",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("solana",),
            }
        )
    finally:
        server.shutdown()

    assert len(direct_quotes) == 1
    assert direct_quotes[0].status == "valid"
    assert direct_quotes[0].source == "live"
    assert response["ok"] is True
    assert response["provider_id"] == "market-token-provider"
    assert response["quotes"][0]["source"] == "live_provider"
    assert store.get_record("compute_quote", "http-quote")["source"] == "live_provider"
    assert store.count_records("quote_cache_entry") == 1


def test_external_provider_quote_flow_fails_closed_when_disabled() -> None:
    store = ComputeMarketStore()
    service = ComputeMarketService(
        store=store,
        config=ComputeMarketConfig(compute_market_mode="test", rate_limits_enabled=False, external_provider_quotes_enabled=False),
    )
    before_count = store.count_records("compute_quote")

    response = service.request_external_provider_quote({"provider_id": "market-token-provider", "task": "disabled"})

    assert response["ok"] is False
    assert response["error"]["error_code"] == "provider_quotes.disabled"
    assert store.count_records("compute_quote") == before_count


def test_provider_sandbox_quote_contract_and_http_adapter() -> None:
    validation_quote = sandbox_quote({})
    server = create_provider_sandbox_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    endpoint = f"http://{host}:{port}/quote"
    config = ComputeMarketConfig(
        compute_market_mode="test",
        rate_limits_enabled=False,
        external_provider_quotes_enabled=True,
        external_provider_allowlist=("127.0.0.1",),
    )
    provider_record = {
        "provider_id": "sandbox-provider",
        "provider_name": "Sandbox Provider",
        "provider_type": "gpu",
        "status": "active",
        "supported_unit_types": ("gpu_minute",),
        "supported_assets": ("USDC",),
        "supported_networks": ("offchain",),
        "quote_endpoint": endpoint,
    }
    try:
        adapter = build_external_provider_adapter(provider_record, (), config)
        quotes = adapter.quote(build_task_profile({"task": "sandbox"}), ComputeMarketPolicy())
    finally:
        server.shutdown()
        server.server_close()

    assert validation_quote["dry_run_supported"] is True
    assert validation_quote["funds_moved"] is False
    assert quotes[0].provider_id == "sandbox-provider"
    assert quotes[0].route_id == "sandbox-gpu-route"
    assert quotes[0].status == "valid"
