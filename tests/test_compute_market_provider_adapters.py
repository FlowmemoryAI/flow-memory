from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, cast

from flow_memory.compute_market.adapters import HTTPQuoteProvider, QuoteCollector, RetryPolicy, build_external_provider_adapter, signed_provider_request_headers
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.models import ComputeMarketPolicy
from flow_memory.compute_market.provider_contracts import EXECUTION_RESULT_SIGNATURE_CONTEXT, QUOTE_SIGNATURE_CONTEXT
from flow_memory.compute_market.provider_sandbox import create_provider_sandbox_server, sandbox_execute, sandbox_quote, verify_provider_sandbox_request
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.compute_market.planner import build_task_profile
from flow_memory.compute_market.registry import default_compute_providers, default_compute_routes
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.asymmetric import LocalTestSigner
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import verify_payload

_REQUEST_COUNTS: dict[str, int] = {}
_CAPTURED_AUTH: list[str] = []
_CAPTURED_SIGNATURE_HEADERS: list[dict[str, str]] = []
_CAPTURED_REQUEST_BODIES: list[dict[str, Any]] = []
_SIGNED_QUOTE_RESPONSE: dict[str, Any] | None = None

def _signed_provider_payload(payload: Mapping[str, Any], signer: LocalTestSigner, signature_context: str) -> dict[str, Any]:
    signed_payload = {**dict(payload), "_signature_context": signature_context}
    return {**dict(payload), "signature": signer.sign(signed_payload).as_record()}


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
        request_length = int(self.headers.get("content-length", "0") or "0")
        request_body = self.rfile.read(request_length) if request_length else b""
        try:
            decoded_body = json.loads(request_body.decode("utf-8")) if request_body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            decoded_body = {}
        _CAPTURED_REQUEST_BODIES.append(decoded_body if isinstance(decoded_body, dict) else {})
        _CAPTURED_SIGNATURE_HEADERS.append(
            {
                "signature": self.headers.get("x-flow-memory-provider-signature", ""),
                "signature_payload": self.headers.get("x-flow-memory-provider-signature-payload", ""),
                "key_id": self.headers.get("x-flow-memory-provider-signature-key-id", ""),
                "timestamp": self.headers.get("x-flow-memory-provider-request-timestamp", ""),
                "nonce": self.headers.get("x-flow-memory-provider-request-nonce", ""),
                "idempotency_key": self.headers.get("idempotency-key", ""),
                "provider_idempotency_key": self.headers.get("x-flow-memory-provider-idempotency-key", ""),
            }
        )
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
        if self.path == "/spoofed-provider":
            self._send_json({"quote": _quote({"provider_id": "spoofed-provider"})})
            return
        if self.path == "/wrong-route":
            self._send_json({"quote": _quote({"route_id": "unconfigured-route"})})
            return
        if self.path == "/missing-expiry":
            quote = _quote()
            quote.pop("expires_at", None)
            self._send_json({"quote": quote})
            return
        if self.path == "/marked-stale":
            self._send_json({"quote": _quote({"stale": True})})
            return
        if self.path == "/signed":
            self._send_json({"quote": dict(_SIGNED_QUOTE_RESPONSE or _quote())})
            return
        if self.path == "/execute-capture":
            job = decoded_body.get("job", {}) if isinstance(decoded_body.get("job"), Mapping) else {}
            self._send_json(
                {
                    "execution": {
                        "execution_id": "exec-captured-idempotency",
                        "provider_job_id": "exec-captured-idempotency",
                        "job_id": str(job.get("job_id", "")),
                        "provider_id": "market-token-provider",
                        "status": "running",
                        "artifact_ref": "",
                        "artifact_data": {},
                        "actual_units": 0.0,
                        "actual_total_cost": 0.0,
                        "actual_latency_ms": 0.0,
                    }
                }
            )
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
    global _SIGNED_QUOTE_RESPONSE
    _REQUEST_COUNTS.clear()
    _CAPTURED_AUTH.clear()
    _CAPTURED_SIGNATURE_HEADERS.clear()
    _SIGNED_QUOTE_RESPONSE = None
    _CAPTURED_REQUEST_BODIES.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _QuoteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    return server, f"http://{host}:{port}"


def _provider(
    endpoint: str,
    *,
    allow_private: bool = True,
    max_bytes: int = 65_536,
    retries: int = 1,
    timeout_seconds: float = 2.0,
    signing_key: LocalKeyPair | None = None,
    verification_public_key: str | Mapping[str, Any] = "",
) -> HTTPQuoteProvider:
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
        signing_key=signing_key,
        verification_public_key=verification_public_key,
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

def test_http_provider_rejects_unconfigured_route_and_missing_expiry() -> None:
    server, base = _server()
    try:
        wrong_route = _provider(f"{base}/wrong-route").quote(build_task_profile({"task": "wrong route"}), ComputeMarketPolicy())
        missing_expiry = _provider(f"{base}/missing-expiry").quote(build_task_profile({"task": "missing expiry"}), ComputeMarketPolicy())
    finally:
        server.shutdown()

    assert all(quote.status == "invalid_response" for quote in wrong_route)
    assert all(quote.status == "invalid_response" for quote in missing_expiry)


def test_http_provider_honors_provider_marked_stale_quote() -> None:
    server, base = _server()
    try:
        quotes = _provider(f"{base}/marked-stale").quote(build_task_profile({"task": "stale flag"}), ComputeMarketPolicy())
    finally:
        server.shutdown()

    assert quotes[0].route_id == "market-token-route"
    assert quotes[0].status == "stale"
    assert quotes[0].stale is True


def test_service_external_quote_uses_provider_secret_ref_env_binding(monkeypatch: Any) -> None:
    server, base = _server()
    store = ComputeMarketStore(":memory:")
    service = ComputeMarketService(
        store=store,
        config=ComputeMarketConfig(
            compute_market_mode="test",
            rate_limits_enabled=False,
            external_provider_quotes_enabled=True,
            external_provider_allowlist=("127.0.0.1",),
            external_provider_quote_timeout_ms=1_000,
        ),
    )
    monkeypatch.setenv("FLOW_MEMORY_TEST_PROVIDER_TOKEN", "super-secret-token")
    try:
        created = service.create_provider(
            {
                "provider_id": "market-token-provider",
                "provider_name": "Market Token Provider",
                "provider_type": "marketplace",
                "status": "active",
                "supported_unit_types": ("token",),
                "supported_assets": ("USDC",),
                "supported_networks": ("solana",),
                "quote_endpoint": f"{base}/valid",
                "credentials": {
                    "secret_ref": "render/env/FLOW_MEMORY_TEST_PROVIDER_TOKEN",
                    "auth_header_name": "x-provider-token",
                },
            }
        )
        result = service.request_external_provider_quote(
            {
                "provider_id": "market-token-provider",
                "task": "credential-bound quote",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("solana",),
            }
        )
    finally:
        server.shutdown()

    provider = cast(Mapping[str, Any], created["provider"])
    metadata = cast(Mapping[str, Any], provider["metadata"])
    secret_ref = store.list_records("provider_secret_ref", filters={"provider_id": "market-token-provider"}).records[0]
    assert result["ok"] is True
    assert _CAPTURED_AUTH == ["super-secret-token"]
    assert metadata["auth_header_name"] == "x-provider-token"
    assert metadata["auth_header_value_env"] == "FLOW_MEMORY_TEST_PROVIDER_TOKEN"
    assert secret_ref["credential_bindings"]["auth_header_value_env"] == "FLOW_MEMORY_TEST_PROVIDER_TOKEN"
    assert "super-secret-token" not in json.dumps(provider)
    assert "super-secret-token" not in json.dumps(result)



def test_http_provider_signs_outbound_quote_requests() -> None:
    server, base = _server()
    key = LocalKeyPair("flow-memory-provider-test", "shared-provider-secret")
    profile = build_task_profile({"task": "signed quote"})
    policy = ComputeMarketPolicy()
    try:
        quotes = _provider(f"{base}/valid", signing_key=key).quote(profile, policy)
    finally:
        server.shutdown()

    captured = _CAPTURED_SIGNATURE_HEADERS[0]
    signature_payload = json.loads(captured["signature_payload"])
    envelope = json.loads(captured["signature"])
    expected_payload = {"profile": profile.as_record(), "policy_hash": content_hash(policy.as_record())}

    assert quotes[0].status == "valid"
    assert captured["key_id"] == key.key_id
    assert signature_payload["kind"] == "quote"
    assert signature_payload["provider_id"] == "market-token-provider"
    assert signature_payload["payload_hash"] == content_hash(expected_payload)
    assert captured["timestamp"]
    assert captured["nonce"]
    assert verify_payload(signature_payload, envelope, key) is True


def test_external_provider_adapter_verifies_signed_quote_responses() -> None:
    global _SIGNED_QUOTE_RESPONSE
    signer = LocalTestSigner("provider-response-key", "provider-response-seed")
    unsigned = _quote()
    signed = _signed_provider_payload(unsigned, signer, QUOTE_SIGNATURE_CONTEXT)
    provider_public_key: Mapping[str, Any] = signer.public_record().as_record()
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
        "quote_endpoint": f"{base}/signed",
        "metadata": {"quote_endpoint": f"{base}/signed", "public_key": provider_public_key},
    }
    try:
        _SIGNED_QUOTE_RESPONSE = signed
        adapter = build_external_provider_adapter(provider_record, (), config)
        quotes = adapter.quote(build_task_profile({"task": "signed provider response"}), ComputeMarketPolicy())

        _SIGNED_QUOTE_RESPONSE = {**signed, "estimated_total_cost": 9.99}
        tampered = adapter.quote(build_task_profile({"task": "tampered provider response"}), ComputeMarketPolicy())
    finally:
        _SIGNED_QUOTE_RESPONSE = None
        server.shutdown()

    assert quotes[0].status == "valid"
    assert quotes[0].signed_quote_valid is True
    assert quotes[0].signed_quote
    assert all(quote.status == "invalid_response" for quote in tampered)


def test_service_external_provider_quote_preserves_signed_payload_for_broker_validation() -> None:
    global _SIGNED_QUOTE_RESPONSE
    signer = LocalTestSigner("provider-response-key", "provider-response-seed")
    unsigned = _quote()
    signed = _signed_provider_payload(unsigned, signer, QUOTE_SIGNATURE_CONTEXT)
    provider_public_key: Mapping[str, Any] = signer.public_record().as_record()
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
        "quote_endpoint": f"{base}/signed",
        "metadata": {"quote_endpoint": f"{base}/signed", "public_key": provider_public_key},
    }
    store = ComputeMarketStore(":memory:")
    service = ComputeMarketService(store=store, config=config)

    try:
        _SIGNED_QUOTE_RESPONSE = signed
        service.create_provider(provider_record)
        response = service.request_external_provider_quote(
            {
                "provider_id": "market-token-provider",
                "task": "signed provider response",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("solana",),
            }
        )
    finally:
        _SIGNED_QUOTE_RESPONSE = None
        server.shutdown()

    quote_record = store.get_record("compute_quote", "http-quote")
    assert response["ok"] is True
    assert response["validations"][0]["ok"] is True
    assert response["quotes"][0]["signed_quote_valid"] is True
    assert quote_record is not None
    assert quote_record["signed_quote_valid"] is True
    assert json.loads(str(quote_record["signed_quote"])) == signed["signature"]


def test_http_provider_verifies_signed_execution_results() -> None:
    signer = LocalTestSigner("provider-execution-response-key", "provider-execution-response-seed")
    unsigned = {
        "execution_id": "exec-signed-1",
        "provider_job_id": "exec-signed-1",
        "job_id": "job_signed_exec",
        "provider_id": "market-token-provider",
        "status": "running",
        "artifact_ref": "s3://flow-memory-results/job_signed_exec.json",
        "artifact_data": {"ok": True},
        "actual_units": 2.0,
        "actual_total_cost": 0.18,
        "actual_latency_ms": 450.0,
    }
    signed = _signed_provider_payload(unsigned, signer, EXECUTION_RESULT_SIGNATURE_CONTEXT)
    adapter = _provider(
        "http://127.0.0.1:9/valid",
        verification_public_key=signer.public_record().as_record(),
    )
    plan = {
        "job_id": "job_signed_exec",
        "provider_id": "market-token-provider",
        "route_id": "market-token-route",
    }

    verified = adapter.normalize_execution_result({"execution": signed}, plan)
    tampered = adapter.normalize_execution_result({"execution": {**signed, "actual_total_cost": 9.99}}, plan)
    unsigned_result = adapter.normalize_execution_result({"execution": unsigned}, plan)

    assert verified["ok"] is True
    assert verified["provider_execution_signature_valid"] is True
    assert verified["provider_execution_signature"]
    assert tampered["ok"] is False
    assert tampered["error_code"] == "provider_execution.signature_invalid"
    assert unsigned_result["ok"] is False
    assert unsigned_result["error_code"] == "provider_execution.signature_invalid"


def test_quote_signature_cannot_be_replayed_as_execution_result() -> None:
    signer = LocalTestSigner("provider-replay-key", "provider-replay-seed")
    quote_payload = {
        **_quote(),
        "job_id": "job_replayed_quote",
        "status": "running",
        "artifact_ref": "s3://flow-memory-results/job_replayed_quote.json",
    }
    signed_quote = _signed_provider_payload(quote_payload, signer, QUOTE_SIGNATURE_CONTEXT)
    adapter = _provider(
        "http://127.0.0.1:9/valid",
        verification_public_key=signer.public_record().as_record(),
    )

    result = adapter.normalize_execution_result(
        {"execution": signed_quote},
        {
            "job_id": "job_replayed_quote",
            "provider_id": "market-token-provider",
            "route_id": "market-token-route",
        },
    )

    assert result["ok"] is False
    assert result["error_code"] == "provider_execution.signature_invalid"


def test_signed_provider_request_headers_are_payload_bound() -> None:
    key = LocalKeyPair("provider-key", "provider-secret")
    payload = {"job": {"job_id": "job-1"}, "dry_run_only": True}
    headers = signed_provider_request_headers(
        payload,
        provider_id="provider-a",
        signing_key=key,
        kind="execution",
        timestamp="1234567890",
        nonce="nonce-1",
    )
    signature_payload = json.loads(headers["x-flow-memory-provider-signature-payload"])
    envelope = json.loads(headers["x-flow-memory-provider-signature"])

    assert signature_payload["payload_hash"] == content_hash(payload)
    assert signature_payload["timestamp"] == "1234567890"
    assert signature_payload["nonce"] == "nonce-1"
    assert verify_payload(signature_payload, envelope, key) is True

def test_http_provider_execution_sends_stable_idempotency_contract() -> None:
    server, base = _server()
    seed_provider = _provider(f"{base}/valid")
    adapter = HTTPQuoteProvider(
        seed_provider.provider,
        seed_provider.routes,
        execution_endpoint=f"{base}/execute-capture",
        execution_enabled=True,
        allow_private_networks=True,
        allowed_hosts=("127.0.0.1",),
        retry_policy=RetryPolicy(max_retries=0, backoff_seconds=0.01),
    )
    plan = {
        "job_id": "job_exec_idempotent",
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/job.json",
        "model_or_runtime": "sandbox-runtime",
        "resource_request": {"gpu_type": "H100"},
        "budget_policy_id": "policy_default",
        "route_id": "market-token-route",
        "provider_id": "market-token-provider",
        "attempt": 2,
    }

    try:
        first = adapter.execute_plan(plan)
        second = adapter.execute_plan(plan)
    finally:
        server.shutdown()
        server.server_close()

    first_body = _CAPTURED_REQUEST_BODIES[0]
    second_body = _CAPTURED_REQUEST_BODIES[1]
    first_key = str(first_body["job"]["execution_idempotency_key"])
    second_key = str(second_body["job"]["execution_idempotency_key"])

    assert first["ok"] is True
    assert first["execution_idempotency_key"] == first_key
    assert second["execution_idempotency_key"] == first_key
    assert first_key
    assert first_key == second_key
    assert first_body["job"]["attempt"] == 2
    assert first_body["job"]["dry_run_only"] is True
    assert first_body["job"]["funds_moved"] is False
    assert first_body["job"]["broadcast_allowed"] is False
    assert first_body["job"]["private_key_required"] is False
    assert _CAPTURED_SIGNATURE_HEADERS[0]["idempotency_key"] == first_key
    assert _CAPTURED_SIGNATURE_HEADERS[0]["provider_idempotency_key"] == first_key
    assert _CAPTURED_SIGNATURE_HEADERS[1]["idempotency_key"] == first_key
    assert _CAPTURED_SIGNATURE_HEADERS[1]["provider_idempotency_key"] == first_key

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


def test_quote_collector_ignores_invalidated_cache_entries() -> None:
    server, base = _server()
    store = ComputeMarketStore(":memory:")
    provider = _provider(f"{base}/valid")
    profile = build_task_profile({"task": "cache invalidation"})
    policy = ComputeMarketPolicy()
    collector = QuoteCollector((provider,), store=store)
    try:
        first = collector.collect(profile, policy)
        second = collector.collect(profile, policy)
        cache_key = store.quote_cache_key(
            "market-token-provider",
            "market-token-route",
            profile.task_hash,
            content_hash(policy.as_record()),
        )
        cache_entry = dict(store.get_record("quote_cache_entry", cache_key) or {})
        store.put_record(
            "quote_cache_entry",
            cache_key,
            {**cache_entry, "status": "invalidated"},
            provider_id="market-token-provider",
            route_id="market-token-route",
            task_hash=profile.task_hash,
            status="invalidated",
            expires_at=str(cache_entry.get("expires_at", "")),
        )
        refreshed = collector.collect(profile, policy)
    finally:
        server.shutdown()

    assert first[0].source == "live"
    assert second[0].source == "cache"
    assert refreshed[0].source == "live"
    assert _REQUEST_COUNTS["/valid"] == 2

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
        store = ComputeMarketStore(":memory:")
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
    assert direct_quotes[0].dry_run_only is True
    assert direct_quotes[0].provider_id == "market-token-provider"
    assert direct_quotes[0].route_id == "market-token-route"
    assert direct_quotes[0].network == "solana"
    assert direct_quotes[0].payment_asset == "USDC"
    assert response["ok"] is True
    assert response["provider_id"] == "market-token-provider"
    assert response["dry_run_only"] is True
    assert response["funds_moved"] is False
    assert response["broadcast_allowed"] is False
    assert response["private_key_required"] is False
    assert response["quotes"][0]["source"] == "live_provider"
    assert response["quotes"][0]["dry_run_only"] is True
    assert response["quotes"][0]["provider_id"] == "market-token-provider"
    assert response["quotes"][0]["route_id"] == "market-token-route"
    assert response["quotes"][0]["settlement_mode"] == "generic_dry_run"
    assert response["quotes"][0]["settlement_options"] == ("generic_dry_run",)
    assert response["raw_quotes"][0]["dry_run_only"] is True
    assert response["raw_quotes"][0]["provider_id"] == "market-token-provider"
    assert response["raw_quotes"][0]["route_id"] == "market-token-route"
    quote_record = store.get_record("compute_quote", "http-quote")
    assert quote_record is not None
    assert quote_record["source"] == "live_provider"
    assert quote_record["dry_run_only"] is True
    assert quote_record["provider_id"] == "market-token-provider"
    assert quote_record["route_id"] == "market-token-route"
    assert quote_record["settlement_mode"] == "generic_dry_run"
    assert tuple(quote_record["settlement_options"]) == ("generic_dry_run",)
    cache_entry = store.list_records("quote_cache_entry", filters={"provider_id": "market-token-provider"}, limit=1).records[0]
    cached_quote = cache_entry["quote"]
    assert cache_entry["source"] == "live_provider"
    assert cache_entry["route_id"] == "market-token-route"
    assert cached_quote["dry_run_only"] is True
    assert cached_quote["provider_id"] == "market-token-provider"
    assert cached_quote["route_id"] == "market-token-route"
    assert store.count_records("quote_cache_entry") == 1


def test_external_provider_quote_flow_rejects_provider_id_spoofing() -> None:
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
        "quote_endpoint": f"{base}/spoofed-provider",
        "metadata": {"quote_endpoint": f"{base}/spoofed-provider"},
    }
    try:
        adapter = build_external_provider_adapter(provider_record, (), config)
        direct_quotes = adapter.quote(build_task_profile({"task": "spoofed provider"}), ComputeMarketPolicy())
        store = ComputeMarketStore(":memory:")
        service = ComputeMarketService(store=store, config=config)
        service.create_provider(provider_record)
        response = service.request_external_provider_quote(
            {
                "provider_id": "market-token-provider",
                "task": "spoofed provider",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("solana",),
            }
        )
    finally:
        server.shutdown()

    assert len(direct_quotes) == 1
    assert direct_quotes[0].status == "invalid_response"
    assert response["ok"] is False
    assert response["raw_quotes"][0]["status"] == "invalid_response"
    assert store.count_records("compute_quote") == 0
    assert store.count_records("quote_replay_guard") == 0


def test_external_provider_quote_flow_fails_closed_when_disabled() -> None:
    store = ComputeMarketStore(":memory:")
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


def test_provider_sandbox_signed_quote_response_flows_through_service() -> None:
    signer = LocalTestSigner("sandbox-quote-response-key", "sandbox-quote-response-seed")
    provider_public_key: Mapping[str, Any] = signer.public_record().as_record()
    server = create_provider_sandbox_server("127.0.0.1", 0, quote_signer=signer)
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
        "metadata": {"quote_endpoint": endpoint, "public_key": provider_public_key},
    }
    store = ComputeMarketStore(":memory:")
    service = ComputeMarketService(store=store, config=config)

    try:
        adapter = build_external_provider_adapter(provider_record, (), config)
        direct_quotes = adapter.quote(build_task_profile({"task": "signed sandbox"}), ComputeMarketPolicy())
        service.create_provider(provider_record)
        response = service.request_external_provider_quote(
            {
                "provider_id": "sandbox-provider",
                "task": "signed sandbox",
                "allowed_assets": ("USDC",),
                "allowed_networks": ("offchain",),
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    quote_record = store.get_record("compute_quote", direct_quotes[0].quote_id)
    assert direct_quotes[0].status == "valid"
    assert direct_quotes[0].signed_quote_valid is True
    assert "broadcast_allowed" not in direct_quotes[0].original_quote
    assert "private_key_required" not in direct_quotes[0].original_quote
    assert response["ok"] is True
    assert response["validations"][0]["ok"] is True
    assert response["quotes"][0]["signed_quote_valid"] is True
    assert quote_record is not None
    assert quote_record["signed_quote_valid"] is True
    assert quote_record["dry_run_only"] is True
    assert response["funds_moved"] is False
    assert response["broadcast_allowed"] is False
    assert response["private_key_required"] is False


def test_provider_health_pings_sandbox_health_endpoint_and_records_snapshot() -> None:
    store = ComputeMarketStore(":memory:")
    server = create_provider_sandbox_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    base_url = f"http://{host}:{port}"
    service = ComputeMarketService(
        store=store,
        config=ComputeMarketConfig(
            compute_market_mode="test",
            rate_limits_enabled=False,
            external_provider_allowlist=("127.0.0.1",),
            provider_timeout_ms=1_000,
        ),
    )
    try:
        service.create_provider(
            {
                "provider_id": "sandbox-provider",
                "provider_name": "Sandbox Provider",
                "provider_type": "gpu",
                "status": "active",
                "supported_unit_types": ("gpu_minute",),
                "supported_assets": ("USDC",),
                "supported_networks": ("offchain",),
                "quote_endpoint": f"{base_url}/quote",
                "health_endpoint": f"{base_url}/health",
                "reliability_score": 0.99,
            }
        )

        result = service.provider_health("sandbox-provider")
    finally:
        server.shutdown()
        server.server_close()

    health = cast(Mapping[str, Any], result["provider_health"])
    metadata = cast(Mapping[str, Any], health["metadata"])
    snapshots = store.list_records("provider_health_snapshot", filters={"provider_id": "sandbox-provider"}).records

    assert result["ok"] is True
    assert health["status"] == "healthy"
    assert health["error_code"] == ""
    assert metadata["endpoint_checked"] is True
    assert metadata["http_status"] == 200
    assert metadata["capacity_available"] is True
    assert len(snapshots) == 1
    assert snapshots[0]["status"] == "healthy"


def test_provider_onboarding_blocks_private_endpoint_outside_test_mode() -> None:
    store = ComputeMarketStore(":memory:")
    service = ComputeMarketService(
        store=store,
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            provider_timeout_ms=1_000,
        ),
    )

    blocked_endpoints = (
        "https://127.0.0.1:9/health",
        "https://0.0.0.0:9/health",
        "https://provider-node.local/health",
        "https://metadata.google.internal/computeMetadata/v1",
    )
    for index, health_endpoint in enumerate(blocked_endpoints):
        try:
            service.apply_market_provider(
                {
                    "provider_id": f"private-provider-{index}",
                    "provider_name": "Private Provider",
                    "provider_type": "gpu",
                    "supported_unit_types": ("gpu_minute",),
                    "supported_assets": ("USDC",),
                    "supported_networks": ("offchain",),
                    "quote_endpoint": "https://providers.flowmemory.ai/private-endpoint-test/quote",
                    "health_endpoint": health_endpoint,
                }
            )
        except ValueError as exc:
            assert "private or local network" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"private provider endpoint application was accepted: {health_endpoint}")

    assert service.store.count_records("market_provider_application") == 0


def test_provider_sandbox_rejects_unsigned_requests_when_signing_key_configured(monkeypatch: Any) -> None:
    key = LocalKeyPair("sandbox-provider-signing", "sandbox-provider-shared-secret")
    server = create_provider_sandbox_server("127.0.0.1", 0, signing_key=key)
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
    signed_provider_record = {
        **provider_record,
        "metadata": {
            "outbound_signing_key_id": key.key_id,
            "outbound_signing_key_env": "FLOW_MEMORY_SANDBOX_PROVIDER_SIGNING_SECRET",
        },
    }
    monkeypatch.setenv("FLOW_MEMORY_SANDBOX_PROVIDER_SIGNING_SECRET", key.secret)
    try:
        unsigned_adapter = build_external_provider_adapter(provider_record, (), config)
        signed_adapter = build_external_provider_adapter(signed_provider_record, (), config)
        unsigned_quotes = unsigned_adapter.quote(build_task_profile({"task": "unsigned sandbox"}), ComputeMarketPolicy())
        signed_quotes = signed_adapter.quote(build_task_profile({"task": "signed sandbox"}), ComputeMarketPolicy())
    finally:
        server.shutdown()
        server.server_close()

    assert all(quote.status == "provider_error" for quote in unsigned_quotes)
    assert signed_quotes[0].status == "valid"
    assert signed_quotes[0].provider_id == "sandbox-provider"


def test_provider_sandbox_signature_verifier_is_payload_bound() -> None:
    key = LocalKeyPair("sandbox-provider-signing", "sandbox-provider-shared-secret")
    payload = {"profile": {"task_hash": "task-1"}, "policy_hash": "policy-1"}
    headers = signed_provider_request_headers(
        payload,
        provider_id="sandbox-provider",
        signing_key=key,
        kind="quote",
        timestamp="1234567890",
        nonce="nonce-1",
    )

    assert verify_provider_sandbox_request(headers, payload, signing_key=key, kind="quote") is True
    assert verify_provider_sandbox_request(headers, {**payload, "policy_hash": "tampered"}, signing_key=key, kind="quote") is False
    assert verify_provider_sandbox_request(headers, payload, signing_key=key, kind="execution") is False


def test_provider_sandbox_execution_adapter_dispatches_without_settlement() -> None:
    expected = sandbox_execute({"job": {"job_id": "job_sandbox_exec"}})
    server = create_provider_sandbox_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    endpoint = f"http://{host}:{port}/execute"
    config = ComputeMarketConfig(
        compute_market_mode="test",
        rate_limits_enabled=False,
        external_provider_allowlist=("127.0.0.1",),
        external_provider_execution_enabled=True,
        provider_callback_ip_allowlist=("127.0.0.1",),
        external_provider_execution_timeout_ms=1_000,
    )
    provider_record = {
        "provider_id": "sandbox-provider",
        "provider_name": "Sandbox Provider",
        "provider_type": "gpu",
        "status": "active",
        "supported_unit_types": ("gpu_minute",),
        "supported_assets": ("USDC",),
        "supported_networks": ("offchain",),
        "execution_endpoint": endpoint,
    }
    try:
        adapter = build_external_provider_adapter(provider_record, (), config)
        result = adapter.execute_plan(
            {
                "job_id": "job_sandbox_exec",
                "task_type": "inference",
                "input_ref": "s3://flow-memory-inputs/job.json",
                "model_or_runtime": "sandbox-runtime",
                "resource_request": {"gpu_type": "H100"},
                "budget_policy_id": "policy_default",
                "route_id": "sandbox-gpu-route",
                "provider_id": "sandbox-provider",
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    assert expected["dry_run_only"] is True
    assert result["ok"] is True
    assert result["external_provider_called"] is True
    assert result["status"] == "running"
    assert result["funds_moved"] is False
    assert result["broadcast_allowed"] is False
    assert result["private_key_required"] is False
    assert result["execution_idempotency_key"]

def test_provider_sandbox_execution_adapter_signs_dispatch_when_key_configured(monkeypatch: Any) -> None:
    key = LocalKeyPair("sandbox-provider-exec-signing", "sandbox-provider-exec-shared-secret")
    server = create_provider_sandbox_server("127.0.0.1", 0, signing_key=key)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    endpoint = f"http://{host}:{port}/execute"
    config = ComputeMarketConfig(
        compute_market_mode="test",
        rate_limits_enabled=False,
        external_provider_allowlist=("127.0.0.1",),
        external_provider_execution_enabled=True,
        provider_callback_ip_allowlist=("127.0.0.1",),
        external_provider_execution_timeout_ms=1_000,
    )
    provider_record = {
        "provider_id": "sandbox-provider",
        "provider_name": "Sandbox Provider",
        "provider_type": "gpu",
        "status": "active",
        "supported_unit_types": ("gpu_minute",),
        "supported_assets": ("USDC",),
        "supported_networks": ("offchain",),
        "execution_endpoint": endpoint,
    }
    signed_provider_record = {
        **provider_record,
        "metadata": {
            "execution_outbound_signing_key_id": key.key_id,
            "execution_outbound_signing_key_env": "FLOW_MEMORY_SANDBOX_PROVIDER_EXEC_SIGNING_SECRET",
        },
    }

    def _execution_plan(job_id: str) -> dict[str, object]:
        return {
            "job_id": job_id,
            "task_type": "inference",
            "input_ref": "s3://flow-memory-inputs/job.json",
            "model_or_runtime": "sandbox-runtime",
            "resource_request": {"gpu_type": "H100"},
            "budget_policy_id": "policy_default",
            "route_id": "sandbox-gpu-route",
            "provider_id": "sandbox-provider",
        }

    monkeypatch.setenv("FLOW_MEMORY_SANDBOX_PROVIDER_EXEC_SIGNING_SECRET", key.secret)
    try:
        unsigned_adapter = build_external_provider_adapter(provider_record, (), config)
        signed_adapter = build_external_provider_adapter(signed_provider_record, (), config)
        unsigned_result = unsigned_adapter.execute_plan(_execution_plan("job_unsigned_exec"))
        signed_result = signed_adapter.execute_plan(_execution_plan("job_signed_exec"))
    finally:
        server.shutdown()
        server.server_close()

    assert unsigned_result["ok"] is False
    assert unsigned_result["error_code"] == "provider_execution.provider_error"
    assert signed_result["ok"] is True
    assert signed_result["external_provider_called"] is True
    assert signed_result["job_id"] == "job_signed_exec"
    assert signed_result["provider_id"] == "sandbox-provider"
    assert signed_result["status"] == "running"
    assert signed_result["dry_run_only"] is True
    assert signed_result["funds_moved"] is False
    assert signed_result["execution_idempotency_key"]
    assert signed_result["broadcast_allowed"] is False
    assert signed_result["private_key_required"] is False
