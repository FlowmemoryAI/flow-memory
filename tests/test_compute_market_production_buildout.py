from __future__ import annotations

import json
import hmac
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from collections.abc import Callable
from typing import Any, Mapping, cast

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.provider_contracts import QUOTE_SIGNATURE_CONTEXT
from flow_memory.compute_market.audit_export import audit_events_from_export_file, verify_exported_chain
from flow_memory.compute_market.service import (
    ComputeMarketService,
    _provider_quote_ingress_callback_signature_payload,
    _provider_state_callback_signature_payload,
    reset_default_service,
)
from flow_memory.compute_market.models import IntelligenceTier, ProviderClass, ReasoningBudget, RunDecision, TaskEconomicProfile
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.hashes import content_hash
from flow_memory.compute_market.provider_sandbox import create_provider_sandbox_server
from flow_memory.crypto.asymmetric import LocalTestSigner
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload


def _service() -> ComputeMarketService:
    return ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )


def _provider_application() -> dict[str, object]:
    return {
        "provider_id": "provider_live_gpu_1",
        "provider_name": "Live GPU Provider 1",
        "provider_type": "gpu",
        "supported_unit_types": ["gpu_minute", "gpu_hour", "request"],
        "supported_assets": ["USD", "USDC", "CREDITS"],
        "supported_networks": ["offchain", "solana", "base"],
        "quote_endpoint": "https://provider.example.com/quote",
        "health_endpoint": "https://provider.example.com/health",
        "credentials": {"secret_ref": "render/env/FLOW_MEMORY_PROVIDER_GPU_1_TOKEN"},
        "sla": {"uptime_target": 0.99, "max_latency_ms": 1000, "refund_policy": "credit"},
    }


def _quote(total: float = 0.18) -> dict[str, object]:
    return {
        "quote_id": "quote_live_gpu_1",
        "provider_id": "provider_live_gpu_1",
        "route_id": "route_live_gpu_1",
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2,
        "estimated_total_cost": total,
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


def _job_payload() -> dict[str, object]:
    return {
        "task_type": "inference",
        "input_ref": "s3://flow-memory-inputs/job-1.json",
        "model_or_runtime": "llama-runtime",
        "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
        "budget_policy_id": "policy_default",
        "route_id": "route_live_gpu_1",
        "provider_id": "provider_live_gpu_1",
    }


def _signed_state_callback(
    job: Mapping[str, Any],
    payload: Mapping[str, Any],
    key: LocalKeyPair,
    *,
    callback_action: str,
) -> dict[str, object]:
    signature_payload = _provider_state_callback_signature_payload(
        job,
        payload,
        callback_action=callback_action,
    )
    return {**dict(payload), "signature": sign_payload(signature_payload, key).as_record()}


def _signed_quote_ingress_callback(
    provider_id: str,
    route_id: str,
    payload: Mapping[str, Any],
    key: LocalKeyPair,
) -> dict[str, object]:
    signature_payload = _provider_quote_ingress_callback_signature_payload(provider_id, route_id, payload)
    return {**dict(payload), "callback_signature": sign_payload(signature_payload, key).as_record()}


def _metric_total(service: ComputeMarketService, name: str, labels: Mapping[str, str] | None = None) -> float:
    expected = dict(labels or {})
    total = 0.0
    for sample in cast(dict[str, Any], service.telemetry.snapshot(reset=False))["metrics"]:
        if not isinstance(sample, Mapping) or sample.get("name") != name:
            continue
        sample_labels = sample.get("labels", {})
        if not isinstance(sample_labels, Mapping):
            continue
        if all(str(sample_labels.get(key, "")) == value for key, value in expected.items()):
            total += float(sample.get("value", 0.0))
    return total


def _credit_account(service: ComputeMarketService, account_id: str, amount: float, *, event_id: str) -> None:
    raw_event = {
        "id": event_id,
        "type": "checkout.session.completed",
        "amount": amount,
        "currency": "usd",
        "metadata": {"account_id": account_id},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})


_STRIPE_CHECKOUT_REQUESTS: list[dict[str, object]] = []
_STRIPE_CHECKOUT_STATUS = 200


class _StripeCheckoutHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited name
        return

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8")
        _STRIPE_CHECKOUT_REQUESTS.append(
            {
                "path": self.path,
                "authorization": self.headers.get("authorization", ""),
                "idempotency_key": self.headers.get("idempotency-key", ""),
                "params": parse_qs(body),
            }
        )
        if self.path != "/v1/checkout/sessions":
            self.send_response(404)
            self.end_headers()
            return
        if _STRIPE_CHECKOUT_STATUS >= 400:
            self._send_json({"error": {"message": "stripe unavailable"}}, status=_STRIPE_CHECKOUT_STATUS)
            return
        self._send_json(
            {"id": "cs_test_flow_memory", "url": "https://checkout.stripe.test/session/cs_test_flow_memory"}
        )

    def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


def _stripe_checkout_server(*, status: int = 200) -> tuple[ThreadingHTTPServer, str]:
    global _STRIPE_CHECKOUT_STATUS
    _STRIPE_CHECKOUT_STATUS = status
    _STRIPE_CHECKOUT_REQUESTS.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StripeCheckoutHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    return server, f"http://{host}:{port}"


def _stripe_checkout_service(base_url: str) -> ComputeMarketService:
    return ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            stripe_checkout_enabled=True,
            stripe_secret_key="sk_test_flow_memory_checkout",
            stripe_webhook_secret="whsec_flow_memory_checkout",
            stripe_checkout_success_url="https://flow-memory.example/billing/success",
            stripe_checkout_cancel_url="https://flow-memory.example/billing/cancel",
            stripe_api_base_url=base_url,
        ),
    )


def test_provider_onboarding_verification_and_secret_reference_only() -> None:
    service = _service()

    applied = service.apply_market_provider(_provider_application())
    assert applied["ok"] is True
    assert applied["inline_secrets_stored"] is False
    assert applied["provider_application"]["status"] == "pending"
    assert service.store.count_records("provider_secret_ref") == 1
    assert applied["provider_application"]["credential_bindings"]["auth_header_value_env"] == "FLOW_MEMORY_PROVIDER_GPU_1_TOKEN"

    verified = service.verify_market_provider("provider_live_gpu_1", {"verification_notes": "contract reviewed"})
    assert verified["ok"] is True
    assert verified["provider"]["verified"] is True
    assert verified["provider"]["dry_run_only"] is True
    assert verified["provider"]["metadata"]["auth_header_value_env"] == "FLOW_MEMORY_PROVIDER_GPU_1_TOKEN"
    assert "FLOW_MEMORY_PROVIDER_GPU_1_TOKEN" not in json.dumps(verified["provider"].get("credential_bindings", {}))
    routes = tuple(verified["routes"])
    assert {route["unit_type"] for route in routes} == {"gpu_minute", "gpu_hour", "request"}
    assert {route["provider_id"] for route in routes} == {"provider_live_gpu_1"}
    assert all(route["dry_run_only"] is True for route in routes)
    assert all(route["verified_provider_required"] is True for route in routes)
    stored_routes = service.store.list_records(
        "compute_route",
        filters={"provider_id": "provider_live_gpu_1"},
        limit=10,
    ).records
    assert {route["route_id"] for route in stored_routes} == {route["route_id"] for route in routes}
    assert service.list_routes({"provider_id": "provider_live_gpu_1"})["routes"] == stored_routes

    fetched = service.market_provider("provider_live_gpu_1")
    assert fetched["provider_application"]["status"] == "verified"
    assert fetched["reputation"]["provider_id"] == "provider_live_gpu_1"

    disabled = service.disable_market_provider("provider_live_gpu_1", {"reason": "operator-disabled"})
    disabled_routes = service.store.list_records(
        "compute_route",
        filters={"provider_id": "provider_live_gpu_1"},
        limit=10,
    ).records

    assert disabled["provider_application"]["status"] == "disabled"
    assert disabled["provider"]["status"] == "disabled"
    assert {route["status"] for route in disabled["routes"]} == {"disabled"}
    assert all(route["enabled"] is False for route in disabled["routes"])
    assert all(route["enabled"] is False and route["status"] == "disabled" for route in disabled_routes)
    assert service.list_routes({"provider_id": "provider_live_gpu_1", "status": "enabled"})["routes"] == ()
    try:
        service.verify_market_provider("provider_live_gpu_1", {})
    except ValueError as exc:
        assert "pending or probation" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("disabled provider application re-verification succeeded")

def test_provider_reapplication_tracks_new_pending_version_without_settlement_side_effects() -> None:
    service = _service()
    original = {**_provider_application(), "request_id": "provider-apply-v1"}
    reapplied = {
        **_provider_application(),
        "provider_name": "Live GPU Provider 1 Updated",
        "supported_assets": ["USD", "CREDITS"],
        "supported_networks": ["offchain", "base"],
        "quote_endpoint": "https://provider.example.com/quote-v2",
        "health_endpoint": "https://provider.example.com/health-v2",
        "credentials": {"secret_ref": "render/env/FLOW_MEMORY_PROVIDER_GPU_1_TOKEN_V2"},
        "sla": {"uptime_target": 0.995, "max_latency_ms": 750, "refund_policy": "credit"},
        "request_id": "provider-apply-v2",
    }

    first = service.apply_market_provider(original)
    verified = service.verify_market_provider("provider_live_gpu_1", {"request_id": "provider-verify-v1"})
    second = service.apply_market_provider(reapplied)

    assert first["provider_application"]["status"] == "pending"
    assert verified["provider"]["provider_name"] == "Live GPU Provider 1"
    assert verified["provider"]["dry_run_only"] is True
    assert second["provider_application"]["status"] == "pending"
    assert second["provider_application"]["provider_name"] == "Live GPU Provider 1 Updated"
    assert second["provider_application"]["quote_endpoint"] == "https://provider.example.com/quote-v2"
    assert second["provider_application"]["supported_assets"] == ("USD", "CREDITS")
    assert second["provider_application"]["supported_networks"] == ("offchain", "base")
    assert second["inline_secrets_stored"] is False

    fetched = service.market_provider("provider_live_gpu_1")
    assert fetched["provider_application"]["status"] == "pending"
    assert fetched["provider_application"]["provider_name"] == "Live GPU Provider 1 Updated"
    assert fetched["provider"]["provider_name"] == "Live GPU Provider 1"
    assert fetched["provider"]["dry_run_only"] is True
    assert fetched["reputation"]["provider_id"] == "provider_live_gpu_1"

    applications = service.store.list_records(
        "market_provider_application",
        filters={"provider_id": "provider_live_gpu_1"},
        limit=10,
    ).records
    assert [application["request_id"] for application in applications] == [
        "provider-apply-v1",
        "provider-apply-v2",
    ]
    assert [application["status"] for application in applications] == ["verified", "pending"]
    assert applications[-1]["status"] == "pending"
    assert service.store.count_records("provider_secret_ref") == 2
    assert len(service.store.list_records("compute_provider", filters={"provider_id": "provider_live_gpu_1"}).records) == 1
    assert len(service.store.list_records("provider_reputation", filters={"provider_id": "provider_live_gpu_1"}).records) == 1
    assert len(service.store.list_records("compute_route", filters={"provider_id": "provider_live_gpu_1"}, limit=10).records) == 3
    assert service.store.count_records("compute_quote") == 0
    audit_events = service.store.list_records("audit_event", limit=10).records
    applied_events = sorted(
        (event for event in audit_events if event["action"] == "market.provider.applied"),
        key=lambda event: int(event["sequence_number"]),
    )
    verified_events = sorted(
        (event for event in audit_events if event["action"] == "market.provider.verified"),
        key=lambda event: int(event["sequence_number"]),
    )
    assert [event["request_id"] for event in applied_events] == ["provider-apply-v1", "provider-apply-v2"]
    assert [event["request_id"] for event in verified_events] == ["provider-verify-v1"]
    for event in (*applied_events, *verified_events):
        assert event["dry_run_only"] is True
        assert event["funds_moved"] is False
        assert event["broadcast_allowed"] is False
        assert event["private_key_required"] is False


def test_provider_application_revision_and_rejection_gate_verification() -> None:
    service = _service()
    service.apply_market_provider({**_provider_application(), "request_id": "provider-review-v1"})

    revision = service.request_market_provider_revision(
        "provider_live_gpu_1",
        {"revision_notes": "Add KYB evidence before verification.", "reviewed_by": "provider-admin"},
    )
    assert revision["provider_application"]["status"] == "revision_requested"
    assert revision["provider_application"]["verified"] is False
    assert revision["provider_application"]["revision_notes"] == "Add KYB evidence before verification."

    try:
        service.verify_market_provider("provider_live_gpu_1", {})
    except ValueError as exc:
        assert "pending or probation" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("revision-requested provider application was verified")

    service.apply_market_provider(
        {
            **_provider_application(),
            "provider_name": "Live GPU Provider 1 Revised",
            "quote_endpoint": "https://provider.example.com/quote-revised",
            "health_endpoint": "https://provider.example.com/health-revised",
            "request_id": "provider-review-v2",
        }
    )
    rejected = service.reject_market_provider(
        "provider_live_gpu_1",
        {"rejection_reason": "KYB evidence failed review.", "reviewed_by": "provider-admin"},
    )
    fetched = service.market_provider("provider_live_gpu_1")
    audit_actions = tuple(event["action"] for event in service.store.list_records("audit_event", limit=100).records)

    assert rejected["provider_application"]["status"] == "rejected"
    assert rejected["provider_application"]["verified"] is False
    assert rejected["provider_application"]["rejection_reason"] == "KYB evidence failed review."
    assert fetched["provider_application"]["status"] == "rejected"
    assert fetched["provider"] == {}
    assert "market.provider.revision_requested" in audit_actions
    assert "market.provider.rejected" in audit_actions
    try:
        service.verify_market_provider("provider_live_gpu_1", {})
    except ValueError as exc:
        assert "pending or probation" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("rejected provider application was verified")

def test_provider_onboarding_rejects_inline_credentials() -> None:
    service = _service()
    payload = _provider_application()
    payload["credentials"] = {"api_key": "do-not-store-inline"}

    try:
        service.apply_market_provider(payload)
    except ValueError as exc:
        assert "external secret references" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("inline provider credential was accepted")
    try:
        service.broker_quote({"quote": {**_quote(), "settlement_mode": "live_broadcast"}})
    except ValueError as exc:
        assert "settlement_mode" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unsafe settlement_mode quote was accepted")


def test_provider_admin_rejects_inline_credentials_and_stores_secret_refs_only() -> None:
    service = _service()

    try:
        service.create_provider({"provider_id": "admin-provider", "provider_name": "Admin Provider", "api_key": "do-not-store"})
    except ValueError as exc:
        assert "external secret references" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("inline provider admin credential was accepted")

    created = service.create_provider(
        {
            "provider_id": "admin-provider",
            "provider_name": "Admin Provider",
            "provider_type": "gpu",
            "credentials": {"secret_ref": "render/env/FLOW_MEMORY_PROVIDER_ADMIN_TOKEN"},
        }
    )
    assert created["inline_secrets_stored"] is False
    assert "credentials" not in created["provider"]
    assert service.store.count_records("provider_secret_ref") == 1


def test_direct_provider_disable_cascades_routes_out_of_planning_pool() -> None:
    service = _service()
    active_routes = service.list_routes({"provider_id": "direct-request-provider", "status": "enabled"})["routes"]

    disabled = service.disable_provider("direct-request-provider", {"request_id": "disable-direct-provider"})
    stored_routes = service.store.list_records(
        "compute_route",
        filters={"provider_id": "direct-request-provider"},
        limit=10,
    ).records

    assert active_routes
    assert disabled["provider"]["status"] == "disabled"
    assert disabled["routes"]
    assert {route["route_id"] for route in disabled["routes"]} == {route["route_id"] for route in active_routes}
    assert all(route["enabled"] is False and route["status"] == "disabled" for route in disabled["routes"])
    assert all(route["enabled"] is False and route["status"] == "disabled" for route in stored_routes)
    assert service.list_routes({"provider_id": "direct-request-provider", "status": "enabled"})["routes"] == ()


def test_provider_admin_status_cannot_bypass_onboarding_in_production_mode() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            require_managed_sql_in_production=False,
            rate_limits_enabled=False,
        ),
    )
    created = service.create_provider(
        {
            "provider_id": "direct-provider",
            "provider_name": "Direct Provider",
            "provider_type": "gpu",
            "status": "active",
        }
    )
    updated = service.update_provider("direct-provider", {"status": "active", "provider_name": "Updated Direct Provider"})
    applied = service.apply_market_provider({**_provider_application(), "provider_id": "verified-provider"})
    verified = service.verify_market_provider("verified-provider", {"verified_by": "ops"})

    assert created["provider"]["status"] == "probation"
    assert updated["provider"]["status"] == "probation"
    assert applied["provider_application"]["status"] == "pending"
    assert verified["provider"]["status"] == "active"

def test_provider_listing_includes_global_and_filters_cross_tenant_catalog_records() -> None:
    service = _service()
    service.create_provider({"provider_id": "global-provider", "provider_name": "Global Provider", "provider_type": "catalog_test"})
    service.create_provider(
        {
            "provider_id": "tenant-provider-a",
            "provider_name": "Tenant Provider A",
            "provider_type": "catalog_test",
            "tenant_id": "tenant_provider_a",
        }
    )
    service.create_provider(
        {
            "provider_id": "tenant-provider-b",
            "provider_name": "Tenant Provider B",
            "provider_type": "catalog_test",
            "tenant_id": "tenant_provider_b",
        }
    )

    tenant_a = service.list_providers({"tenant_id": "tenant_provider_a", "provider_type": "catalog_test"})
    tenant_b = service.list_providers({"tenant_id": "tenant_provider_b", "provider_type": "catalog_test"})
    active_tenant_a = service.list_providers({"tenant_id": "tenant_provider_a", "provider_type": "catalog_test", "status": "active"})

    assert {provider["provider_id"] for provider in tenant_a["providers"]} == {"global-provider", "tenant-provider-a"}
    assert {provider["provider_id"] for provider in tenant_b["providers"]} == {"global-provider", "tenant-provider-b"}
    assert {provider["provider_id"] for provider in active_tenant_a["providers"]} == {"global-provider", "tenant-provider-a"}
    assert service.get_provider("global-provider", {"tenant_id": "tenant_provider_a"})["provider"]["provider_id"] == "global-provider"
    try:
        service.get_provider("tenant-provider-b", {"tenant_id": "tenant_provider_a"})
    except KeyError as exc:
        assert "Unknown compute provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant provider lookup succeeded")


def test_provider_conformance_and_quote_ingest_verify_signed_quotes() -> None:
    signer = LocalTestSigner("provider_live_gpu_1_key", "provider-live-gpu-1-seed")
    service = _service()
    application = _provider_application()
    application["public_key"] = signer.public_record().public_key
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {})

    unsigned_quote = _quote()
    signed_quote = {**unsigned_quote, "signature": signer.sign({**unsigned_quote, "_signature_context": QUOTE_SIGNATURE_CONTEXT}).as_record()}
    conformance = service.provider_conformance(
        "provider_live_gpu_1",
        {
            "sample_quote": signed_quote,
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        },
    )
    ingested = service.broker_quote(
        {
            "quote": signed_quote,
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )

    assert conformance["ok"] is True
    assert conformance["signed_quote_valid"] is True
    assert ingested["ok"] is True
    assert ingested["quote"]["signed_quote_valid"] is True



def test_quote_ingest_enforces_provider_callback_ip_allowlist() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("203.0.113.0/24",),
        ),
    )

    blocked = service.broker_quote(
        {
            "quote": _quote(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
            "_flow_memory_client_ip": "198.51.100.77",
        }
    )
    allowed = service.broker_quote(
        {
            "quote": {**_quote(), "quote_id": "quote_live_gpu_allowed_ip"},
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
            "_flow_memory_client_ip": "203.0.113.10",
        }
    )

    assert blocked["ok"] is False
    assert blocked["error"]["error_code"] == "provider_callback.ip_not_allowed"
    assert blocked["error"]["details"]["callback_action"] == "quote_ingest"
    assert allowed["ok"] is True
    assert service.store.count_records("compute_quote") == 1
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"callback_action": "quote_ingest"}) == 1.0


def test_quote_ingest_verifies_provider_callback_signature_and_replay(monkeypatch: Any) -> None:
    service = _service()
    key = LocalKeyPair("provider-quote-callback-key", "provider-quote-callback-secret")
    monkeypatch.setenv("FLOW_MEMORY_PROVIDER_QUOTE_CALLBACK_SECRET", key.secret)
    service.create_provider(
        {
            "provider_id": "provider_live_gpu_1",
            "provider_name": "Live GPU Provider 1",
            "provider_type": "gpu",
            "metadata": {
                "callback_signing_key_id": key.key_id,
                "callback_signing_key_env": "FLOW_MEMORY_PROVIDER_QUOTE_CALLBACK_SECRET",
            },
        }
    )

    missing_payload = {
        "quote": {**_quote(), "quote_id": "quote_callback_missing"},
        "allowed_assets": ["USDC"],
        "allowed_networks": ["solana"],
        "callback_id": "quote-missing",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    missing = service.broker_quote(missing_payload)

    tampered_payload = {
        "quote": {**_quote(), "quote_id": "quote_callback_tampered"},
        "allowed_assets": ["USDC"],
        "allowed_networks": ["solana"],
        "callback_id": "quote-tampered",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    tampered_signature = sign_payload(
        _provider_quote_ingress_callback_signature_payload(
            "provider_live_gpu_1",
            "route_live_gpu_1",
            tampered_payload,
        ),
        key,
    ).as_record()
    tampered = service.broker_quote(
        {
            **tampered_payload,
            "quote": {**cast(Mapping[str, object], tampered_payload["quote"]), "estimated_total_cost": 9.99},
            "callback_signature": tampered_signature,
        }
    )

    valid_payload = {
        "quote": {**_quote(), "quote_id": "quote_callback_valid"},
        "allowed_assets": ["USDC"],
        "allowed_networks": ["solana"],
        "callback_id": "quote-valid",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    signed_valid = _signed_quote_ingress_callback(
        "provider_live_gpu_1",
        "route_live_gpu_1",
        valid_payload,
        key,
    )
    accepted = service.broker_quote(signed_valid)
    replayed = service.broker_quote(signed_valid)

    assert missing["ok"] is False
    assert missing["error"]["error_code"] == "provider_callback.signature_missing"
    assert tampered["ok"] is False
    assert tampered["error"]["error_code"] == "provider_callback.signature_invalid"
    assert accepted["ok"] is True
    assert accepted["quote"]["quote_id"] == "quote_callback_valid"
    assert accepted["provider_callback_verification"]["callback_id"] == "quote-valid"
    assert replayed["ok"] is False
    assert replayed["error"]["error_code"] == "provider_callback.replay_detected"
    assert service.store.count_records("compute_quote") == 1
    assert service.store.count_records("provider_callback_replay_guard") == 1
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"callback_action": "quote_ingest", "reason": "provider_callback.signature_missing"}) == 1.0
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"callback_action": "quote_ingest", "reason": "provider_callback.signature_invalid"}) == 1.0
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"callback_action": "quote_ingest", "reason": "provider_callback.replay_detected"}) == 1.0


def test_broker_quote_ignores_payload_public_key_when_stored_key_exists() -> None:
    trusted_signer = LocalTestSigner("provider_live_gpu_1_key", "provider-live-gpu-1-seed")
    spoofing_signer = LocalTestSigner("provider_live_gpu_1_spoof", "provider-spoof-seed")
    service = _service()
    application = _provider_application()
    application["public_key"] = trusted_signer.public_record().public_key
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {})

    quote = {**_quote(), "quote_id": "quote_payload_key_spoof"}
    spoofed_quote = {
        **quote,
        "signature": spoofing_signer.sign({**quote, "_signature_context": QUOTE_SIGNATURE_CONTEXT}).as_record(),
    }
    conformance = service.provider_conformance(
        "provider_live_gpu_1",
        {
            "sample_quote": spoofed_quote,
            "public_key": spoofing_signer.public_record().as_record(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        },
    )
    ingested = service.broker_quote(
        {
            "quote": spoofed_quote,
            "public_key": spoofing_signer.public_record().as_record(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )

    assert conformance["ok"] is False
    assert conformance["validation"]["error_codes"] == ("invalid_signature",)
    assert ingested["ok"] is False
    assert ingested["validation"]["error_codes"] == ("invalid_signature",)
    assert service.store.count_records("compute_quote") == 0

def test_provider_conformance_records_fraud_signal_on_invalid_quote() -> None:
    signer = LocalTestSigner("provider_live_gpu_1_key", "provider-live-gpu-1-seed")
    service = _service()
    application = _provider_application()
    application["public_key"] = signer.public_record().public_key
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {})

    rejected = service.provider_conformance(
        "provider_live_gpu_1",
        {
            "sample_quote": _quote(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        },
    )
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert rejected["ok"] is False
    assert rejected["validation"]["error_codes"] == ("missing_signature",)
    assert rejected["conformance"]["status"] == "failed"
    assert rejected["conformance"]["fraud_signal_count"] == 1
    assert rejected["fraud_signals"][0]["signal_type"] == "signature_failure"
    assert reputation["signature_failure_count"] == 1
    assert reputation["critical_fraud_signal_count"] == 1
    assert reputation["status"] == "degraded"


def test_quote_broker_records_missing_signature_fraud_signal_for_verified_provider() -> None:
    signer = LocalTestSigner("provider_live_gpu_1_key", "provider-live-gpu-1-seed")
    service = _service()
    application = _provider_application()
    application["public_key"] = signer.public_record().public_key
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {})

    rejected = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert rejected["ok"] is False
    assert rejected["validation"]["error_codes"] == ("missing_signature",)
    assert rejected["fraud_signals"][0]["signal_type"] == "signature_failure"
    assert reputation["signature_failure_count"] == 1
    assert reputation["critical_fraud_signal_count"] == 1
    assert reputation["status"] == "degraded"



def test_quote_broker_validates_replay_cache_and_drift() -> None:
    service = _service()

    accepted = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    assert accepted["ok"] is True
    assert accepted["quote"]["source"] == "live_provider"
    assert service.store.count_records("quote_replay_guard") == 1
    assert service.store.count_records("quote_cache_entry") == 1

    invalidated = service.invalidate_quote_cache(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "quote_id": "quote_live_gpu_1",
            "reason": "provider_refresh",
        }
    )
    cache_entry = service.store.get_record("quote_cache_entry", invalidated["invalidated_entries"][0]["cache_key"])

    assert invalidated["invalidated_count"] == 1
    assert cache_entry is not None
    assert cache_entry["status"] == "invalidated"
    assert cache_entry["invalidation_reason"] == "provider_refresh"
    assert _metric_total(
        service,
        "quote_cache_invalidated_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 1.0

    replay = service.broker_quote({"quote": {**_quote(), "estimated_total_cost": 0.27}})
    assert replay["ok"] is False
    assert replay["error"]["error_code"] == "quote.replay_detected"
    assert replay["fraud_signals"][0]["signal_type"] == "quote_replay"
    assert service.store.count_records("provider_fraud_signal") == 1

    drifted = service.broker_quote({"quote": {**_quote(0.27), "quote_id": "quote_live_gpu_2"}})
    assert drifted["ok"] is True
    assert drifted["drift"]["status"] == "review"
    assert drifted["fraud_signals"][0]["signal_type"] == "quote_price_manipulation"

    drift_analytics = service.quote_drift_analytics({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})
    observed_only = service.quote_drift_analytics({"provider_id": "provider_live_gpu_1", "status": "observed"})

    assert drift_analytics["summary"]["observation_count"] == 1
    assert drift_analytics["summary"]["review_count"] == 1


    assert drift_analytics["summary"]["max_drift_ratio"] == 0.5
    assert drift_analytics["summary"]["by_provider"]["provider_live_gpu_1"] == 1
    assert drift_analytics["drift_observations"][0]["previous_quote_id"] == "quote_live_gpu_1"
    assert drift_analytics["drift_observations"][0]["current_quote_id"] == "quote_live_gpu_2"
    assert observed_only["summary"]["observation_count"] == 0
    expired_quote = {**dict(accepted["quote"]), "expires_at": "2000-01-01T00:00:00Z", "status": "valid"}
    service.store.put_record(
        "compute_quote",
        str(expired_quote["quote_id"]),
        expired_quote,
        provider_id="provider_live_gpu_1",
        route_id="route_live_gpu_1",
        status="valid",
        expires_at=str(expired_quote["expires_at"]),
    )
    fresh = service.broker_quote(
        {
            "quote": {**_quote(), "quote_id": "quote_live_gpu_replacement"},
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )
    stale = service.store.get_record("compute_quote", str(expired_quote["quote_id"]))

    assert fresh["ok"] is True
    assert stale is not None
    assert stale["status"] == "stale"
    assert _metric_total(
        service,
        "quote_stale_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 1.0
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]
    assert reputation["quote_replay_count"] == 1
    assert reputation["quote_price_manipulation_count"] == 1
    assert reputation["fraud_signal_count"] == 2


def test_quote_broker_rejects_cross_provider_quote_id_replay() -> None:
    service = _service()

    accepted = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    replay = service.broker_quote(
        {
            "quote": {**_quote(), "provider_id": "provider_live_gpu_2"},
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )
    reputation = service.provider_reputation("provider_live_gpu_2")["reputation"]

    assert accepted["ok"] is True
    assert replay["ok"] is False
    assert replay["error"]["error_code"] == "quote.cross_provider_replay_detected"
    assert replay["fraud_signals"][0]["signal_type"] == "provider_spoofing_replay"
    assert replay["fraud_signals"][0]["severity"] == "critical"
    assert replay["fraud_signals"][0]["details"]["matched_provider_id"] == "provider_live_gpu_1"
    assert service.store.count_records("quote_replay_guard") == 1
    assert reputation["provider_spoofing_count"] == 1
    assert reputation["critical_fraud_signal_count"] == 1


def test_quote_broker_rejects_same_provider_stale_quote_replay() -> None:
    service = _service()
    accepted = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    assert accepted["ok"] is True

    stale_quote = {
        **dict(accepted["quote"]),
        "status": "stale",
        "stale": True,
        "expires_at": "2000-01-01T00:00:00Z",
    }
    service.store.put_record(
        "compute_quote",
        str(stale_quote["record_id"]),
        stale_quote,
        provider_id="provider_live_gpu_1",
        route_id="route_live_gpu_1",
        status="stale",
        expires_at=str(stale_quote["expires_at"]),
    )

    replay = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    stored_quote = service.store.get_record("compute_quote", str(stale_quote["record_id"]))
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert replay["ok"] is False
    assert replay["error"]["error_code"] == "quote.stale_replay_detected"
    assert replay["fraud_signals"][0]["signal_type"] == "stale_quote_submission"
    assert stored_quote is not None
    assert stored_quote["status"] == "stale"
    assert reputation["stale_quote_submission_count"] == 1
    assert service.store.count_records("compute_quote") == 1

def test_marketplace_plan_selects_verified_provider_cached_quote() -> None:
    service = _service()
    service.apply_market_provider(_provider_application())
    verified = service.verify_market_provider("provider_live_gpu_1", {"verification_notes": "contract reviewed"})
    route = next(route for route in verified["routes"] if route["unit_type"] == "gpu_minute")
    route_id = str(route["route_id"])
    quote_id = "quote_marketplace_plan_cached_provider"

    accepted = service.broker_quote(
        {
            "quote": {
                **_quote(0.04),
                "quote_id": quote_id,
                "route_id": route_id,
                "unit_price": 0.02,
                "estimated_units": 2,
                "estimated_total_cost": 0.04,
            },
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )
    planned = service.marketplace_plan(
        {
            "task": "gpu batch inference with verified provider",
            "provider_constraints": ["provider_live_gpu_1"],
            "estimated_units": {"gpu_minute": 2},
            "selection_strategy": "lowest_cost",
        }
    )

    compute_plan = planned["compute_plan"]
    selected_route = compute_plan["selected_route"]
    normalized_quote = compute_plan["normalized_quote"]
    route_metadata = normalized_quote["original_quote"]["route"]["metadata"]
    assert accepted["ok"] is True
    assert planned["ok"] is True
    assert selected_route["provider_id"] == "provider_live_gpu_1"
    assert selected_route["route_id"] == route_id
    assert normalized_quote["unit_price"] == 0.02
    assert normalized_quote["estimated_total_cost"] == 0.04
    assert route_metadata["latest_quote_id"] == quote_id
    assert compute_plan["provider_count"] >= 1
    assert compute_plan["route_count"] == 3

def test_quote_and_capacity_records_are_tenant_scoped() -> None:
    service = _service()
    tenant_a = "tenant_market_a"
    tenant_b = "tenant_market_b"
    application = {**_provider_application(), "tenant_id": tenant_a, "workspace_id": "workspace_market_a"}
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {"tenant_id": tenant_a})

    accepted = service.broker_quote(
        {
            "tenant_id": tenant_a,
            "workspace_id": "workspace_market_a",
            "quote": _quote(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )
    replay_guard = service.store.list_records("quote_replay_guard", filters={"tenant_id": tenant_a}).records[0]
    tenant_b_comparison = service.compare_quotes(
        {
            "tenant_id": tenant_b,
            "quote_ids": ["quote_live_gpu_1"],
            "task": "tenant b must not see tenant a quote",
        }
    )
    tenant_a_comparison = service.compare_quotes(
        {
            "tenant_id": tenant_a,
            "quote_ids": ["quote_live_gpu_1"],
            "task": "tenant a can compare own quote",
        }
    )

    assert accepted["quote"]["tenant_id"] == tenant_a
    assert accepted["quote"]["workspace_id"] == "workspace_market_a"
    assert service.store.get_record("compute_quote", str(accepted["quote"]["record_id"])) is not None
    assert replay_guard is not None
    assert replay_guard["tenant_id"] == tenant_a
    assert tenant_b_comparison["quote_comparison"]["summary"]["quote_count"] == 0
    assert tenant_a_comparison["quote_comparison"]["summary"]["quote_count"] == 1

    try:
        service.broker_quote(
            {
                "tenant_id": tenant_b,
                "quote": {**_quote(), "quote_id": "quote_tenant_b_rejected"},
                "allowed_assets": ["USDC"],
                "allowed_networks": ["solana"],
            }
        )
    except KeyError as exc:
        assert "Unknown compute provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant quote ingest was accepted")

    try:
        service.invalidate_quote_cache(
            {
                "tenant_id": tenant_b,
                "provider_id": "provider_live_gpu_1",
                "route_id": "route_live_gpu_1",
                "quote_id": "quote_live_gpu_1",
            }
        )
    except KeyError as exc:
        assert "Unknown compute provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant quote cache invalidation was accepted")

    window = service.list_capacity(
        {
            "tenant_id": tenant_a,
            "workspace_id": "workspace_market_a",
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )["capacity_window"]
    tenant_b_book = service.capacity_order_book({"tenant_id": tenant_b, "provider_id": "provider_live_gpu_1"})

    assert window["tenant_id"] == tenant_a
    assert window["workspace_id"] == "workspace_market_a"
    assert tenant_b_book["capacity_windows"] == ()
    assert tenant_b_book["summary"]["total_capacity_units"] == 0

    try:
        service.auction_capacity(
            {
                "tenant_id": tenant_b,
                "provider_id": "provider_live_gpu_1",
                "route_id": "route_live_gpu_1",
                "capacity_units": 1,
                "bids": [
                    {
                        "bid_id": "bid_tenant_b",
                        "account_id": "acct_tenant_b",
                        "capacity_units": 1,
                        "max_unit_price": 3.0,
                    }
                ],
            }
        )
    except KeyError as exc:
        assert "Unknown compute provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant capacity auction was accepted")

    try:
        service.reserve_capacity(
            {
                "tenant_id": tenant_b,
                "provider_id": "provider_live_gpu_1",
                "route_id": "route_live_gpu_1",
                "capacity_units": 1,
            }
        )
    except KeyError as exc:
        assert "Unknown compute provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant capacity reservation was accepted")

    held = service.reserve_capacity(
        {
            "tenant_id": tenant_a,
            "workspace_id": "workspace_market_a",
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 2,
        }
    )["reservation"]
    assert held["tenant_id"] == tenant_a

    try:
        service.confirm_capacity({"tenant_id": tenant_b, "reservation_id": held["reservation_id"]})
    except KeyError as exc:
        assert "Unknown capacity reservation" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant capacity confirmation was accepted")

    confirmed = service.confirm_capacity({"tenant_id": tenant_a, "reservation_id": held["reservation_id"]})[
        "reservation"
    ]
    assert confirmed["tenant_id"] == tenant_a

    try:
        service.release_capacity({"tenant_id": tenant_b, "reservation_id": held["reservation_id"]})
    except KeyError as exc:
        assert "Unknown capacity reservation" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant capacity release was accepted")

    released = service.release_capacity({"tenant_id": tenant_a, "reservation_id": held["reservation_id"]})[
        "reservation"
    ]
    assert released["tenant_id"] == tenant_a

    auction = service.auction_capacity(
        {
            "tenant_id": tenant_a,
            "workspace_id": "workspace_market_a",
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 1,
            "bids": [
                {
                    "bid_id": "bid_tenant_a",
                    "account_id": "acct_tenant_a",
                    "capacity_units": 1,
                    "max_unit_price": 3.0,
                }
            ],
        }
    )
    assert auction["clearing"]["tenant_id"] == tenant_a


def test_quote_records_use_tenant_scoped_identity_for_shared_providers() -> None:
    service = _service()
    tenant_a = "tenant_shared_quote_a"
    tenant_b = "tenant_shared_quote_b"

    tenant_a_quote = service.broker_quote(
        {
            "tenant_id": tenant_a,
            "quote": _quote(0.18),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )["quote"]
    tenant_b_quote = service.broker_quote(
        {
            "tenant_id": tenant_b,
            "quote": {**_quote(0.27), "unit_price": 0.135},
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )["quote"]
    tenant_a_comparison = service.compare_quotes(
        {"tenant_id": tenant_a, "quote_ids": ["quote_live_gpu_1"], "task": "tenant a quote lookup"}
    )
    tenant_b_comparison = service.compare_quotes(
        {"tenant_id": tenant_b, "quote_ids": ["quote_live_gpu_1"], "task": "tenant b quote lookup"}
    )

    assert tenant_a_quote["quote_id"] == tenant_b_quote["quote_id"] == "quote_live_gpu_1"
    assert tenant_a_quote["record_id"] != tenant_b_quote["record_id"]
    assert tenant_a_quote["tenant_id"] == tenant_a
    assert tenant_b_quote["tenant_id"] == tenant_b
    assert service.store.count_records("compute_quote") == 2
    assert service.store.count_records("quote_replay_guard") == 2
    assert service.store.count_records("quote_cache_entry") == 2
    assert tenant_a_comparison["quote_comparison"]["rows"][0]["estimated_total_cost"] == 0.18
    assert tenant_b_comparison["quote_comparison"]["rows"][0]["estimated_total_cost"] == 0.27


def test_quote_comparison_across_unit_types_and_assets() -> None:
    service = _service()
    token_quote = {
        **_quote(0.0054),
        "quote_id": "quote_token_compare",
        "provider_id": "provider_token_compare",
        "route_id": "route_token_compare",
        "unit_type": "token",
        "unit_price": 0.00000045,
        "estimated_units": 12000,
        "currency_or_asset": "USDC",
        "comparability_warnings": (),
    }
    request_quote = {
        **_quote(0.015),
        "quote_id": "quote_request_compare",
        "provider_id": "provider_request_compare",
        "route_id": "route_request_compare",
        "unit_type": "request",
        "unit_price": 0.015,
        "estimated_units": 1,
        "currency_or_asset": "USDC",
        "comparability_warnings": (),
    }
    reserved_quote = {
        **_quote(2.5),
        "quote_id": "quote_reserved_compare",
        "provider_id": "provider_reserved_compare",
        "route_id": "route_reserved_compare",
        "unit_type": "reserved_capacity_slot",
        "unit_price": 2.5,
        "estimated_units": 1,
        "currency_or_asset": "USD",
        "comparability_warnings": ("reserved capacity quote normalized as slot cost; unused capacity is not credited",),
    }

    compared = service.compare_quotes(
        {
            "quotes": [token_quote, request_quote, _quote(), reserved_quote],
            "task": "compare heterogeneous compute quotes",
            "estimated_units": {"token": 12000, "request": 1, "gpu_minute": 2, "reserved_capacity_slot": 1},
        }
    )
    comparison = compared["quote_comparison"]
    rows = {row["quote_id"]: row for row in comparison["rows"]}

    assert comparison["summary"]["quote_count"] == 4
    assert comparison["summary"]["comparable_quote_count"] == 4
    assert comparison["summary"]["cross_asset"] is True
    assert "cross-asset quotes require FX/treasury policy before direct price ranking" in comparison["summary"]["warnings"]
    assert set(comparison["summary"]["unit_types"]) == {"gpu_minute", "request", "reserved_capacity_slot", "token"}
    assert comparison["best_by_asset"]["USDC"]["quote_id"] == "quote_token_compare"
    assert rows["quote_token_compare"]["cost_per_1000_token_equivalent"] == 0.00045
    assert rows["quote_live_gpu_1"]["unit_family"] == "compute_time"
    assert rows["quote_reserved_compare"]["unit_family"] == "reserved_capacity"
    assert rows["quote_reserved_compare"]["comparability_warnings"]

def test_plan_records_route_rejection_metrics() -> None:
    service = _service()
    result = service.plan(
        {
            "task": "plan a gpu inference job",
            "estimated_units": {"gpu_minute": 2, "request": 1, "token": 1000},
            "policy": {"denied_providers": ["gpu-time-provider"]},
        }
    )
    rejected_routes = result["compute_plan"]["rejected_routes"]

    assert result["ok"] is True
    assert any(route["route_id"] == "gpu-minute-route" for route in rejected_routes)
    assert _metric_total(
        service,
        "compute_route_rejected_total",
        {"provider_id": "gpu-time-provider", "route_id": "gpu-minute-route", "reason": "provider_denied"},
    ) == 1.0

def test_capacity_reservation_hold_release_and_overbook_rejection() -> None:
    service = _service()
    window = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    assert window["capacity_window"]["capacity_units"] == 10

    held = service.reserve_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 4})
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]

    assert held["reservation"]["status"] == "held"
    assert summary["held_capacity_units"] == 4
    assert summary["available_capacity_units"] == 6
    assert summary["utilization_ratio"] == 0.4
    assert summary["utilization_by_provider"]["provider_live_gpu_1"]["utilization_ratio"] == 0.4

    partial = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 7, "allow_partial": True}
    )
    partial_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]

    assert partial["reservation"]["capacity_units"] == 6
    assert partial["reservation"]["requested_capacity_units"] == 7
    assert partial["reservation"]["partial_fill"] is True
    assert partial["reservation"]["partial_fill_reason"] == "capacity_shortfall"
    assert partial_summary["held_capacity_units"] == 10
    assert partial_summary["available_capacity_units"] == 0

    try:
        service.reserve_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 7})
    except ValueError as exc:
        assert "exceeds available" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("overbooked capacity was accepted")

    released_partial = service.release_capacity({"reservation_id": partial["reservation"]["reservation_id"]})
    assert released_partial["reservation"]["status"] == "released"

    released = service.release_capacity({"reservation_id": held["reservation"]["reservation_id"]})
    assert released["reservation"]["status"] == "released"
    released_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]
    assert released_summary["held_capacity_units"] == 0
    assert released_summary["utilization_ratio"] == 0.0

    stale_hold = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 10,
            "hold_expires_at": "2000-01-01T00:00:00Z",
        }
    )
    assert stale_hold["reservation"]["status"] == "held"

    expired = service.expire_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})
    assert expired["expired_count"] == 1
    assert expired["expired_reservations"][0]["status"] == "expired"
    assert _metric_total(
        service,
        "capacity_hold_expired_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 10.0

    expired_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]
    assert expired_summary["held_capacity_units"] == 0
    assert expired_summary["expired_capacity_units"] == 10
    assert expired_summary["available_capacity_units"] == 10

    replacement = service.reserve_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 10})
    assert replacement["reservation"]["status"] == "held"

def test_reserve_capacity_idempotency_replay_does_not_mutate_capacity_or_metrics() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )

    first = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 4,
            "idempotency_key": "reserve-capacity-replay-1",
        }
    )
    replay = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 4,
            "idempotency_key": "reserve-capacity-replay-1",
            "request_id": "reserve-capacity-replay-request-2",
        }
    )
    conflict = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 7,
            "allow_partial": True,
            "idempotency_key": "reserve-capacity-replay-1",
        }
    )
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert replay["idempotent_replay"] is True
    assert replay["reservation"]["reservation_id"] == first["reservation"]["reservation_id"]
    assert replay["reservation"]["capacity_units"] == 4
    assert conflict["ok"] is False
    assert conflict["idempotent_replay"] is False
    assert conflict["error"]["error_code"] == "capacity.reservation.idempotency_conflict"
    assert service.store.count_records("compute_reservation") == 1
    assert summary["held_capacity_units"] == 4
    assert summary["available_capacity_units"] == 6
    assert _metric_total(
        service,
        "capacity_reserved_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 4.0


def test_capacity_listing_rejects_shrinking_window_below_active_reservations() -> None:
    service = _service()
    window_payload = {
        "provider_id": "provider_live_gpu_1",
        "route_id": "route_live_gpu_1",
        "resource_type": "gpu_hour",
        "gpu_type": "H100",
        "available_units": 10,
        "region": "us-east",
        "starts_at": "2099-01-01T00:00:00Z",
        "ends_at": "2099-01-01T01:00:00Z",
        "price_floor": 2.4,
    }
    service.list_capacity(window_payload)
    held = service.reserve_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 4})

    try:
        service.list_capacity({**window_payload, "available_units": 3})
    except ValueError as exc:
        assert "active reservation commitments" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("capacity window shrank below active reservations")

    safe_shrink = service.list_capacity({**window_payload, "available_units": 5})
    expanded = service.list_capacity({**window_payload, "available_units": 12})
    service.release_capacity({"reservation_id": held["reservation"]["reservation_id"]})
    no_active_shrink = service.list_capacity({**window_payload, "available_units": 2})

    assert safe_shrink["capacity_window"]["capacity_units"] == 5
    assert expanded["capacity_window"]["capacity_units"] == 12
    assert no_active_shrink["capacity_window"]["capacity_units"] == 2


def test_expire_capacity_only_expires_elapsed_held_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    active = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 2,
            "hold_expires_at": "2099-01-01T00:00:00Z",
        }
    )["reservation"]
    released = service.release_capacity({"reservation_id": active["reservation_id"]})["reservation"]
    stale = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 3,
            "hold_expires_at": "2000-01-01T00:00:00Z",
        }
    )["reservation"]

    expired = service.expire_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})
    stale_after = service.store.get_record("compute_reservation", str(stale["reservation_id"]))
    released_after = service.store.get_record("compute_reservation", str(released["reservation_id"]))
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert expired["ok"] is True
    assert expired["expired_count"] == 1
    assert expired["expired_reservations"][0]["reservation_id"] == stale["reservation_id"]
    assert expired["expired_reservations"][0]["status"] == "expired"
    assert expired["expired_reservations"][0]["dry_run_only"] is True
    assert expired["expired_reservations"][0]["funds_moved"] is False
    assert stale_after is not None
    assert stale_after["status"] == "expired"
    assert released_after is not None
    assert released_after["status"] == "released"
    assert summary["expired_capacity_units"] == 3
    assert summary["reserved_capacity_units"] == 0
    assert summary["held_capacity_units"] == 0
    assert summary["available_capacity_units"] == 10
    assert _metric_total(
        service,
        "capacity_hold_expired_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 3.0


def test_release_capacity_is_safe_for_replay_and_unknown_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 4,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 4}
    )["reservation"]

    first_release_result = service.release_capacity({"reservation_id": held["reservation_id"]})
    second_release_result = service.release_capacity({"reservation_id": held["reservation_id"]})
    first_release = first_release_result["reservation"]
    second_release = second_release_result["reservation"]
    stored_after_second_release = service.store.get_record("compute_reservation", str(held["reservation_id"]))
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert first_release["status"] == "released"
    assert first_release["dry_run_only"] is True
    assert first_release["funds_moved"] is False
    assert second_release["reservation_id"] == first_release["reservation_id"]
    assert second_release["status"] == "released"
    assert second_release["dry_run_only"] is True
    assert second_release["funds_moved"] is False
    assert second_release_result["idempotent_replay"] is True
    assert first_release["released_at"] == second_release["released_at"]
    assert stored_after_second_release is not None
    assert stored_after_second_release["status"] == "released"
    assert summary["held_capacity_units"] == 0
    assert summary["reserved_capacity_units"] == 0
    assert summary["available_capacity_units"] == 4
    assert _metric_total(
        service,
        "capacity_released_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 4.0

    try:
        service.release_capacity({"reservation_id": "reservation_missing"})
    except KeyError as exc:
        assert "Unknown capacity reservation: reservation_missing" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown capacity reservation was released")

def test_release_capacity_reports_only_remaining_units_after_partial_consumption() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 5,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 3}
    )["reservation"]
    reservation_id = str(service.confirm_capacity({"reservation_id": held["reservation_id"]})["reservation"]["reservation_id"])
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_capacity_partial_release",
                "capacity_reservation_id": reservation_id,
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(job_id, {})
    service.complete_job(
        job_id,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "capacity_units_consumed": 2,
        },
    )

    released = service.release_capacity({"reservation_id": reservation_id})["reservation"]
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert released["status"] == "released"
    assert released["consumed_capacity_units"] == 2
    assert released["released_capacity_units"] == 1
    assert released["remaining_capacity_units"] == 0.0
    assert summary["consumed_capacity_units"] == 2
    assert summary["available_capacity_units"] == 3
    assert _metric_total(
        service,
        "capacity_released_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 1.0

def test_capacity_listing_expires_stale_holds_before_publishing_inventory() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    stale_hold = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 4,
            "hold_expires_at": "2000-01-01T00:00:00Z",
        }
    )

    relisted = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    expired = service.store.get_record("compute_reservation", str(stale_hold["reservation"]["reservation_id"]))

    assert relisted["expired_reservations"][0]["status"] == "expired"
    assert expired is not None
    assert expired["status"] == "expired"
    assert _metric_total(
        service,
        "capacity_hold_expired_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 4.0


def test_capacity_reservation_confirm_creates_dry_run_commitment() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 5,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 3}
    )
    reservation_id = str(held["reservation"]["reservation_id"])

    reset_default_service(service)
    router = create_default_router()
    try:
        confirmed = router.dispatch("POST", "/market/capacity/confirm", {"reservation_id": reservation_id})
    finally:
        reset_default_service(None)
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert confirmed["reservation"]["status"] == "confirmed"
    assert confirmed["reservation"]["confirmed_at"]
    assert confirmed["reservation"]["dry_run_only"] is True
    assert confirmed["reservation"]["funds_moved"] is False
    assert summary["reserved_capacity_units"] == 3
    assert summary["held_capacity_units"] == 0
    assert summary["confirmed_capacity_units"] == 3
    assert summary["available_capacity_units"] == 2
    assert summary["utilization_by_provider"]["provider_live_gpu_1"]["confirmed_capacity_units"] == 3
    assert _metric_total(
        service,
        "capacity_confirmed_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 3.0

    replay = service.confirm_capacity({"reservation_id": reservation_id})
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["reservation"]["status"] == "confirmed"
    assert replay["reservation"]["reservation_id"] == reservation_id

    released = service.release_capacity({"reservation_id": reservation_id})
    assert released["reservation"]["status"] == "released"
    released_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]
    assert released_summary["confirmed_capacity_units"] == 0

    stale_hold = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 1,
            "hold_expires_at": "2000-01-01T00:00:00Z",
        }
    )
    try:
        service.confirm_capacity({"reservation_id": stale_hold["reservation"]["reservation_id"]})
    except ValueError as exc:
        assert "hold is expired" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expired capacity hold was confirmed")



def test_compute_jobs_consume_confirmed_capacity_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 5,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 3}
    )["reservation"]
    confirmed = service.confirm_capacity({"reservation_id": held["reservation_id"]})["reservation"]
    reservation_id = str(confirmed["reservation_id"])

    first_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_capacity_consume_first",
                "capacity_reservation_id": reservation_id,
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(first_job_id, {})
    completed = service.complete_job(
        first_job_id,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "capacity_units_consumed": 2,
        },
    )
    stored_after_partial = service.store.get_record("compute_reservation", reservation_id)
    partial_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert dispatched["ok"] is True
    assert dispatched["job"]["reserved_capacity_units"] == 3
    assert completed["capacity_consumption"]["status"] == "confirmed"
    assert completed["capacity_consumption"]["consumed_capacity_units"] == 2
    assert completed["capacity_consumption"]["remaining_capacity_units"] == 1
    assert stored_after_partial is not None
    assert stored_after_partial["status"] == "confirmed"
    assert stored_after_partial["consumed_capacity_units"] == 2
    assert stored_after_partial["remaining_capacity_units"] == 1
    assert partial_summary["confirmed_capacity_units"] == 1
    assert partial_summary["consumed_capacity_units"] == 2
    assert partial_summary["available_capacity_units"] == 2
    assert partial_summary["utilization_ratio"] == 0.6

    second_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_capacity_consume_second",
                "capacity_reservation_id": reservation_id,
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(second_job_id, {})
    consumed = service.complete_job(
        second_job_id,
        {
            "actual_units": 1,
            "actual_total_cost": 0.09,
            "currency": "USD",
            "capacity_units_consumed": 1,
        },
    )
    stored_after_full = service.store.get_record("compute_reservation", reservation_id)
    final_summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert consumed["capacity_consumption"]["status"] == "consumed"
    assert stored_after_full is not None
    assert stored_after_full["status"] == "consumed"
    assert stored_after_full["consumed_capacity_units"] == 3
    assert stored_after_full["remaining_capacity_units"] == 0.0
    assert final_summary["confirmed_capacity_units"] == 0
    assert final_summary["consumed_capacity_units"] == 3
    assert final_summary["available_capacity_units"] == 2
    assert _metric_total(
        service,
        "capacity_consumed_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 3.0


def test_dispatch_rejects_unconfirmed_or_mismatched_capacity_reservation_before_credit_hold() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 5,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    raw_event = {
        "id": "evt_capacity_reject_credit",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_capacity_reject"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 1}
    )["reservation"]

    unconfirmed_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_unconfirmed_capacity",
                "account_id": "acct_capacity_reject",
                "estimated_total_cost": 0.18,
                "capacity_reservation_id": str(held["reservation_id"]),
            }
        )["job"]["job_id"]
    )
    rejected = service.dispatch_job(unconfirmed_job_id, {})

    assert rejected["ok"] is False
    assert rejected["error"]["error_code"] == "capacity.reservation_unconfirmed"
    assert rejected["job"]["status"] == "queued"
    assert service.store.get_record("compute_job", unconfirmed_job_id)["status"] == "queued"
    balance = service.billing_balance({"account_id": "acct_capacity_reject"})["balance"]
    assert balance["available_credits"] == 1.0
    assert balance["reserved_credits"] == 0.0

    confirmed = service.confirm_capacity({"reservation_id": held["reservation_id"]})["reservation"]
    mismatch_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_mismatched_capacity",
                "provider_id": "other_provider",
                "capacity_reservation_id": str(confirmed["reservation_id"]),
            }
        )["job"]["job_id"]
    )
    mismatch = service.dispatch_job(mismatch_job_id, {})

    assert mismatch["ok"] is False
    assert mismatch["error"]["error_code"] == "capacity.reservation_route_mismatch"
    assert mismatch["job"]["status"] == "queued"
    assert any(
        event["event_type"] == "job.capacity_reservation_rejected"
        for event in service.job_events(mismatch_job_id)["events"]
    )

def test_expire_capacity_transitions_elapsed_confirmed_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 5,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 3}
    )["reservation"]
    confirmed = service.confirm_capacity({"reservation_id": held["reservation_id"]})["reservation"]
    elapsed = {**dict(confirmed), "reserved_until": "2000-01-01T00:00:00Z", "updated_at": "2000-01-01T00:00:00Z"}
    reservation_id = str(confirmed["reservation_id"])
    service.store.put_record(
        "compute_reservation",
        reservation_id,
        elapsed,
        provider_id="provider_live_gpu_1",
        route_id="route_live_gpu_1",
        status="confirmed",
    )

    expired = service.expire_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})
    stored = service.store.get_record("compute_reservation", reservation_id)
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert expired["expired_count"] == 1
    assert expired["expired_reservations"][0]["reservation_id"] == reservation_id
    assert expired["expired_reservations"][0]["status"] == "expired"
    assert expired["expired_reservations"][0]["expiration_reason"] == "reservation_window_elapsed"
    assert stored is not None
    assert stored["status"] == "expired"
    assert stored["expiration_reason"] == "reservation_window_elapsed"
    assert summary["confirmed_capacity_units"] == 0
    assert summary["expired_capacity_units"] == 3
    assert summary["available_capacity_units"] == 5
    assert _metric_total(
        service,
        "capacity_reservation_expired_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 3.0
    assert _metric_total(
        service,
        "capacity_hold_expired_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 0.0

def test_capacity_auction_clears_highest_bids_without_mutating_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 8,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.5,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 2}
    )
    payload = {
        "provider_id": "provider_live_gpu_1",
        "route_id": "route_live_gpu_1",
        "capacity_units": 5,
        "reserve_price": 2.7,
        "idempotency_key": "auction-idempotent-1",
        "bids": [
            {"bid_id": "bid_low", "account_id": "acct_low", "capacity_units": 4, "max_unit_price": 2.6},
            {"bid_id": "bid_high", "account_id": "acct_high", "capacity_units": 4, "max_unit_price": 3.2},
            {"bid_id": "bid_mid", "account_id": "acct_mid", "capacity_units": 4, "max_unit_price": 3.0},
            {"bid_id": "bid_tail", "account_id": "acct_tail", "capacity_units": 2, "max_unit_price": 2.9},
        ],
    }
    reset_default_service(service)
    router = create_default_router()
    try:
        auction = router.dispatch("POST", "/market/capacity/auction", payload)
    finally:
        reset_default_service(None)
    clearing = auction["clearing"]
    summary = service.capacity_order_book({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"})[
        "summary"
    ]

    assert auction["ok"] is True
    assert clearing["status"] == "cleared"
    assert clearing["dry_run_only"] is True
    assert clearing["funds_moved"] is False
    assert clearing["reservations_created"] is False
    assert clearing["available_capacity_units"] == 6
    assert clearing["total_units_cleared"] == 5
    assert clearing["clearing_unit_price"] == 3.0
    assert [bid["bid_id"] for bid in clearing["winning_bids"]] == ["bid_high", "bid_mid"]
    assert clearing["winning_bids"][1]["partial_fill"] is True
    assert {bid["rejection_reason"] for bid in clearing["rejected_bids"]} == {
        "below_reserve_price",
        "capacity_exhausted",
    }
    assert summary["reserved_capacity_units"] == 2
    assert summary["available_capacity_units"] == 6
    assert service.store.count_records("capacity_auction") == 1
    assert _metric_total(
        service,
        "capacity_auction_cleared_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 5.0

    replay = service.auction_capacity(payload)
    assert replay["idempotent_replay"] is True
    assert replay["clearing"]["auction_id"] == clearing["auction_id"]
    assert service.store.count_records("capacity_auction") == 1
    conflict = service.auction_capacity({**payload, "capacity_units": 4})
    assert conflict["ok"] is False
    assert conflict["idempotent_replay"] is False
    assert conflict["clearing"]["auction_id"] == clearing["auction_id"]
    assert conflict["error"]["error_code"] == "capacity.auction.idempotency_conflict"
    assert conflict["next_safe_actions"] == ("use a new idempotency_key for different auction parameters",)
    assert service.store.count_records("capacity_auction") == 1
    assert _metric_total(
        service,
        "capacity_auction_cleared_total",
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1"},
    ) == 5.0
    assert service.release_capacity({"reservation_id": held["reservation"]["reservation_id"]})["ok"] is True


def test_capacity_auction_tie_breaks_by_submission_time_then_bid_id() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 4,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )

    auction = service.auction_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 3,
            "reserve_price": 2.4,
            "bids": [
                {
                    "bid_id": "bid_z_late",
                    "account_id": "acct_z",
                    "capacity_units": 2,
                    "max_unit_price": 3.0,
                    "submitted_at": "2099-01-01T00:00:03Z",
                },
                {
                    "bid_id": "bid_b",
                    "account_id": "acct_b",
                    "capacity_units": 2,
                    "max_unit_price": 3.0,
                    "submitted_at": "2099-01-01T00:00:01Z",
                },
                {
                    "bid_id": "bid_a",
                    "account_id": "acct_a",
                    "capacity_units": 2,
                    "max_unit_price": 3.0,
                    "submitted_at": "2099-01-01T00:00:01Z",
                },
            ],
        }
    )
    clearing = auction["clearing"]

    assert clearing["status"] == "cleared"
    assert clearing["dry_run_only"] is True
    assert clearing["funds_moved"] is False
    assert clearing["reservations_created"] is False
    assert clearing["total_units_cleared"] == 3
    assert clearing["clearing_unit_price"] == 3.0
    assert [bid["bid_id"] for bid in clearing["winning_bids"]] == ["bid_a", "bid_b"]
    assert clearing["winning_bids"][1]["partial_fill"] is True
    assert clearing["rejected_bids"][0]["bid_id"] == "bid_z_late"
    assert clearing["rejected_bids"][0]["rejection_reason"] == "capacity_exhausted"


def test_capacity_auction_rejects_when_requested_interval_has_no_window() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 4,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )

    try:
        service.auction_capacity(
            {
                "provider_id": "provider_live_gpu_1",
                "route_id": "route_live_gpu_1",
                "capacity_units": 1,
                "reserve_price": 2.4,
                "starts_at": "2099-01-02T00:00:00Z",
                "ends_at": "2099-01-02T01:00:00Z",
                "bids": [{"bid_id": "bid_1", "account_id": "acct_1", "capacity_units": 1, "max_unit_price": 3.0}],
            }
        )
    except ValueError as exc:
        assert "no unexpired active capacity window overlaps requested auction interval" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("capacity auction cleared without a suitable window")

def test_capacity_reservations_only_consume_overlapping_windows() -> None:
    service = _service()
    first = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )["capacity_window"]
    second = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T01:00:00Z",
            "ends_at": "2099-01-01T02:00:00Z",
            "price_floor": 2.4,
        }
    )["capacity_window"]

    first_hold = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 10,
            "reserved_from": first["starts_at"],
            "reserved_until": first["ends_at"],
        }
    )
    second_hold = service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 10,
            "reserved_from": second["starts_at"],
            "reserved_until": second["ends_at"],
        }
    )

    first_summary = service.capacity_order_book(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "starts_at": first["starts_at"],
            "ends_at": first["ends_at"],
        }
    )["summary"]
    second_summary = service.capacity_order_book(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "starts_at": second["starts_at"],
            "ends_at": second["ends_at"],
        }
    )["summary"]

    assert first_hold["reservation"]["window_id"] == first["window_id"]
    assert second_hold["reservation"]["window_id"] == second["window_id"]
    assert first_summary["held_capacity_units"] == 10
    assert first_summary["available_capacity_units"] == 0
    assert second_summary["held_capacity_units"] == 10
    assert second_summary["available_capacity_units"] == 0


def test_capacity_auction_uses_target_interval_capacity() -> None:
    service = _service()
    first = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )["capacity_window"]
    second = service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T01:00:00Z",
            "ends_at": "2099-01-01T02:00:00Z",
            "price_floor": 2.4,
        }
    )["capacity_window"]
    service.reserve_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 10,
            "reserved_from": second["starts_at"],
            "reserved_until": second["ends_at"],
        }
    )

    try:
        service.auction_capacity(
            {
                "provider_id": "provider_live_gpu_1",
                "route_id": "route_live_gpu_1",
                "capacity_units": 1,
                "starts_at": second["starts_at"],
                "ends_at": second["ends_at"],
                "bids": [
                    {"bid_id": "bid_target_reserved", "account_id": "acct_reserved", "capacity_units": 1, "max_unit_price": 3.0}
                ],
            }
        )
    except ValueError as exc:
        assert "no available capacity" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("auction cleared against capacity outside the requested interval")

    auction = service.auction_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "capacity_units": 5,
            "reserved_from": first["starts_at"],
            "reserved_until": first["ends_at"],
            "bids": [
                {"bid_id": "bid_target_free", "account_id": "acct_free", "capacity_units": 5, "max_unit_price": 3.0}
            ],
        }
    )

    assert auction["clearing"]["available_capacity_units"] == 10
    assert auction["clearing"]["total_units_cleared"] == 5
    assert auction["clearing"]["winning_bids"][0]["bid_id"] == "bid_target_free"


def test_dispatch_job_claim_race_does_not_start_or_reserve_credit(monkeypatch: Any) -> None:
    service = _service()
    account_id = "acct_dispatch_claim_race"
    _credit_account(service, account_id, 1.0, event_id="evt_dispatch_claim_race")
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_dispatch_claim_race",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
            }
        )["job"]["job_id"]
    )
    original_put_record_if_state = service.store.put_record_if_state

    def fail_dispatch_claim(
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> bool:
        if record_type == "compute_job" and record_id == job_id and expected_statuses == ("queued",):
            return False
        return original_put_record_if_state(record_type, record_id, expected_statuses, payload, **kwargs)

    monkeypatch.setattr(service.store, "put_record_if_state", fail_dispatch_claim)

    dispatched = service.dispatch_job(job_id, {"account_id": account_id})

    assert dispatched["ok"] is False
    assert dispatched["error"]["error_code"] == "job.status_changed"
    assert dispatched["job"]["status"] == "queued"
    assert service.get_job(job_id)["job"]["status"] == "queued"
    assert service.store.count_records("credit_transaction") == 1
    assert not any(event["event_type"] == "job.started" for event in service.job_events(job_id)["events"])

def test_compute_job_lifecycle_records_dispatch_completion_artifact_and_usage() -> None:
    service = _service()
    created = service.create_job(_job_payload())
    job_id = str(created["job"]["job_id"])
    assert created["job"]["dry_run_only"] is True
    assert created["job"]["funds_moved"] is False

    dispatched = service.dispatch_job(job_id, {})
    assert dispatched["job"]["status"] == "running"
    completed = service.complete_job(
        job_id,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "artifact_ref": "s3://flow-memory-results/job-1.json",
            "artifact_data": {"result": "ok"},
        },
    )

    for extra_id in ("artifact_extra_1", "artifact_extra_2"):
        extra_artifact = {
            **dict(completed["artifact"]),
            "artifact_id": extra_id,
            "artifact_ref": f"s3://flow-memory-results/{extra_id}.json",
            "artifact_hash": content_hash({"artifact_id": extra_id}),
        }
        service.store.put_record(
            "compute_job_artifact",
            extra_id,
            extra_artifact,
            provider_id=str(completed["job"]["provider_id"]),
            route_id=str(completed["job"]["route_id"]),
            task_type=str(completed["job"]["task_type"]),
            status="available",
            request_id="artifact-pagination-test",
            tenant_id=str(completed["job"].get("tenant_id", "")),
            workspace_id=str(completed["job"].get("workspace_id", "")),
        )

    assert completed["job"]["status"] == "succeeded"
    assert completed["artifact"]["artifact_ref"] == "s3://flow-memory-results/job-1.json"
    assert completed["usage_charge"]["amount"] == 0.18
    assert completed["usage_charge"]["funds_moved"] is False
    assert completed["credit_debit"] == {}
    assert completed["provider_payout"] == {}
    first_artifact_page = service.job_artifacts(job_id, {"limit": 1})
    second_artifact_page = service.job_artifacts(job_id, {"limit": 2, "cursor": first_artifact_page["next_cursor"]})
    artifact_ids = {
        str(artifact["artifact_id"])
        for artifact in (*first_artifact_page["artifacts"], *second_artifact_page["artifacts"])
    }
    assert first_artifact_page["next_cursor"]
    assert len(first_artifact_page["artifacts"]) == 1
    assert len(second_artifact_page["artifacts"]) == 2
    assert {str(completed["artifact"]["artifact_id"]), "artifact_extra_1", "artifact_extra_2"} == artifact_ids
    assert completed["artifact"]["dry_run_only"] is completed["job"]["dry_run_only"]
    assert service.store.count_records("usage_charge") == 1
    assert any(event["event_type"] == "job.completed" for event in service.job_events(job_id)["events"])


def test_complete_job_status_race_does_not_record_usage_or_debit(monkeypatch: Any) -> None:
    service = _service()
    account_id = "acct_complete_status_race"
    _credit_account(service, account_id, 1.0, event_id="evt_complete_status_race")
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_complete_status_race",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {"account_id": account_id})
    original_put_record_if_state = service.store.put_record_if_state

    def fail_completion_transition(
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> bool:
        if record_type == "compute_job" and record_id == job_id and expected_statuses == ("running",):
            return False
        return original_put_record_if_state(record_type, record_id, expected_statuses, payload, **kwargs)

    monkeypatch.setattr(service.store, "put_record_if_state", fail_completion_transition)

    completed = service.complete_job(
        job_id,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "artifact_ref": "s3://flow-memory-results/job-race.json",
            "artifact_data": {"result": "late"},
        },
    )
    balance = service.billing_balance({"account_id": account_id})["balance"]
    transactions = service.store.list_records(
        "credit_transaction",
        filters={"tenant_id": account_id},
        limit=10,
    ).records

    assert dispatched["ok"] is True
    assert completed["ok"] is False
    assert completed["error"]["error_code"] == "job.status_changed"
    assert completed["job"]["status"] == "running"
    assert service.get_job(job_id)["job"]["status"] == "running"
    assert service.store.count_records("usage_charge") == 0
    assert service.store.count_records("billing_invoice") == 0
    assert service.store.count_records("compute_job_artifact") == 0
    assert service.store.count_records("provider_payout") == 0
    assert not any(record["transaction_type"] == "debit" for record in transactions)
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18
    assert not any(event["event_type"] == "job.completed" for event in service.job_events(job_id)["events"])

def test_compute_job_expire_leases_requeues_claims_and_expires_running_jobs() -> None:
    service = _service()
    expired_at = "2000-01-01T00:00:00Z"
    claimed_id = str(service.create_job({**_job_payload(), "job_id": "job_expired_claim"})["job"]["job_id"])
    running_id = str(service.create_job({**_job_payload(), "job_id": "job_expired_running"})["job"]["job_id"])
    service.claim_job({"job_id": claimed_id, "worker_id": "worker_old"})
    service.dispatch_job(running_id, {"worker_id": "worker_running"})

    claimed = dict(service.store.get_record("compute_job", claimed_id) or {})
    claimed["lease_expires_at"] = expired_at
    service.store.put_record(
        "compute_job",
        claimed_id,
        claimed,
        provider_id=str(claimed.get("provider_id", "")),
        route_id=str(claimed.get("route_id", "")),
        task_type=str(claimed.get("task_type", "")),
        status="dispatched",
        expires_at=expired_at,
        actor_id="worker_old",
    )
    running = dict(service.store.get_record("compute_job", running_id) or {})
    running["lease_expires_at"] = expired_at
    running["claimed_by"] = "worker_running"
    service.store.put_record(
        "compute_job",
        running_id,
        running,
        provider_id=str(running.get("provider_id", "")),
        route_id=str(running.get("route_id", "")),
        task_type=str(running.get("task_type", "")),
        status="running",
        expires_at=expired_at,
        actor_id="worker_running",
    )

    result = service.expire_job_leases({"limit": 10})
    requeued = service.get_job(claimed_id)["job"]
    expired = service.get_job(running_id)["job"]
    reclaimed = service.claim_job({"job_id": claimed_id, "worker_id": "worker_new"})

    assert result["ok"] is True
    assert result["expired_count"] == 2
    assert requeued["status"] == "queued"
    assert requeued["claimed_by"] == ""
    assert requeued["lease_expires_at"] == ""
    assert requeued["last_expired_lease"]["claimed_by"] == "worker_old"
    assert expired["status"] == "expired"
    assert expired["error_code"] == "worker_heartbeat_timeout"
    assert "expired" in expired["lifecycle"]
    assert reclaimed["job"]["status"] == "dispatched"
    assert any(event["event_type"] == "job.lease_expired" for event in service.job_events(running_id)["events"])
    assert any(event["event_type"] == "job.lease_expired_requeued" for event in service.job_events(claimed_id)["events"])
    try:
        service.complete_job(running_id, {"worker_id": "worker_running", "actual_units": 1})
    except ValueError as exc:
        assert "status expired" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expired running job accepted completion")


def test_compute_job_expires_after_max_dispatch_attempts() -> None:
    service = _service()
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_dispatch_attempt_limit",
                "max_dispatch_attempts": 1,
            }
        )["job"]["job_id"]
    )

    claimed = service.claim_job({"job_id": job_id, "worker_id": "worker_limit", "ttl_seconds": 30})
    expired_at = "2000-01-01T00:00:00Z"
    claimed_job = dict(claimed["job"])
    claimed_job["lease_expires_at"] = expired_at
    service.store.put_record(
        "compute_job",
        job_id,
        claimed_job,
        provider_id=str(claimed_job.get("provider_id", "")),
        route_id=str(claimed_job.get("route_id", "")),
        task_type=str(claimed_job.get("task_type", "")),
        status="dispatched",
        expires_at=expired_at,
        actor_id="worker_limit",
    )

    expired = service.expire_job_leases({"job_id": job_id})

    job = service.get_job(job_id)["job"]
    event_types = {event["event_type"] for event in service.job_events(job_id)["events"]}
    assert expired["expired_count"] == 1
    assert job["status"] == "expired"
    assert job["error_code"] == "max_dispatch_attempts_exceeded"
    assert job["dispatch_attempt"] == 1
    assert "job.dispatch_attempts_exhausted" in event_types
    assert "job.lease_expired_requeued" not in event_types


def test_compute_job_listing_filters_by_tenant_status_and_paginates() -> None:
    service = _service()
    first = service.create_job(
        {**_job_payload(), "job_id": "job_list_a1", "tenant_id": "tenant_job_list_a"}
    )
    second = service.create_job(
        {**_job_payload(), "job_id": "job_list_a2", "tenant_id": "tenant_job_list_a"}
    )
    service.create_job(
        {**_job_payload(), "job_id": "job_list_b1", "tenant_id": "tenant_job_list_b"}
    )
    running_id = str(
        service.create_job(
            {**_job_payload(), "job_id": "job_list_a_running", "tenant_id": "tenant_job_list_a"}
        )["job"]["job_id"]
    )
    service.dispatch_job(running_id, {"tenant_id": "tenant_job_list_a"})

    first_page = service.list_jobs(
        {"tenant_id": "tenant_job_list_a", "status": "queued", "limit": 1}
    )
    second_page = service.list_jobs(
        {
            "tenant_id": "tenant_job_list_a",
            "status": "queued",
            "limit": 10,
            "cursor": str(first_page["next_cursor"]),
        }
    )
    tenant_b = service.list_jobs({"tenant_id": "tenant_job_list_b"})

    paged_jobs = (*first_page["jobs"], *second_page["jobs"])
    paged_ids = {str(job["job_id"]) for job in paged_jobs}
    assert paged_ids == {str(first["job"]["job_id"]), str(second["job"]["job_id"])}
    assert first_page["next_cursor"]
    assert all(str(job["tenant_id"]) == "tenant_job_list_a" for job in paged_jobs)
    assert all(str(job["status"]) == "queued" for job in paged_jobs)
    assert tuple(str(job["job_id"]) for job in tenant_b["jobs"]) == ("job_list_b1",)


def test_compute_job_completion_rejects_cross_tenant_billing_account_before_state_change() -> None:
    service = _service()
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_tenant_billing_guard",
                "tenant_id": "tenant_job_billing_a",
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(job_id, {})

    try:
        service.complete_job(
            job_id,
            {
                "tenant_id": "tenant_job_billing_a",
                "account_id": "tenant_job_billing_b",
                "actual_units": 2,
                "actual_total_cost": 0.18,
                "currency": "USD",
            },
        )
    except ValueError as exc:
        assert "account_id must match tenant_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cross-tenant billing account was accepted")

    assert service.get_job(job_id)["job"]["status"] == "running"
    assert service.store.count_records("usage_charge") == 0
    assert not any(event["event_type"] == "job.completed" for event in service.job_events(job_id)["events"])


def test_provider_reputation_tracks_sla_latency_breaches() -> None:
    service = _service()
    service.apply_market_provider(_provider_application())
    service.verify_market_provider("provider_live_gpu_1", {})

    job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(
        job_id,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "actual_latency_ms": 1500,
            "currency": "USD",
        },
    )
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert completed["job"]["provider_sla_max_latency_ms"] == 1000.0
    assert completed["job"]["provider_sla_latency_breached"] is True
    assert completed["event"]["details"]["provider_sla_latency_breached"] is True
    assert reputation["sla_max_latency_ms"] == 1000.0
    assert reputation["sla_latency_breach_count"] == 1
    assert reputation["sla_breach_count"] == 1
    assert reputation["latency_reliability"] == 0.0
    penalty = completed["provider_sla_penalty"]
    assert completed["event"]["details"]["provider_sla_penalty_recorded"] is True
    assert penalty["status"] == "pending_reconciliation"
    assert penalty["refund_policy"] == "credit"
    assert penalty["recommended_credit_amount"] == 0.18
    assert penalty["provider_payout_adjustment_amount"] == 0.18
    assert penalty["funds_moved"] is False
    assert service.store.count_records("provider_sla_penalty") == 1
    assert service.reconciliation({})["reconciliation"]["provider_sla_penalty_count"] == 1
    assert _metric_total(service, "provider_sla_penalty_total", {"provider_id": "provider_live_gpu_1"}) == 0.18


def test_reconciliation_applies_provider_sla_credit_and_payout_adjustment_without_custody() -> None:
    service = _service()
    service.apply_market_provider(_provider_application())
    service.verify_market_provider("provider_live_gpu_1", {})
    raw_event = {
        "id": "evt_sla_credit",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_sla"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_sla_reconciled"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(
        job_id,
        {
            "account_id": "acct_sla",
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "actual_latency_ms": 1500,
            "currency": "USD",
        },
    )
    payout_id = str(completed["provider_payout"]["provider_payout_id"])
    reconciliation = service.reconciliation({})["reconciliation"]
    penalty = service.store.get_record(
        "provider_sla_penalty",
        str(completed["provider_sla_penalty"]["sla_penalty_id"]),
    )
    payout = service.store.get_record("provider_payout", payout_id)
    balance = service.billing_balance({"account_id": "acct_sla"})["balance"]

    assert reconciliation["provider_sla_penalty_reconciled_this_run"] == 1
    assert reconciliation["provider_sla_penalty_reconciled_count"] == 1
    assert reconciliation["ledger_balanced"] is True
    assert penalty is not None
    assert penalty["status"] == "reconciled_dry_run"
    assert penalty["refund_id"]
    assert penalty["credit_transaction_id"]
    assert penalty["provider_payout_adjustment"]["adjusted"] is True
    assert penalty["provider_payout_adjustment"]["remaining_payout_amount"] == 0.0
    assert payout is not None
    assert payout["status"] == "adjusted_no_payout_due"
    assert payout["amount"] == 0.0
    assert payout["sla_penalty_adjustment_amount"] == 0.18
    assert balance["available_credits"] == 1.0
    assert balance["reserved_credits"] == 0.0
    assert penalty["funds_moved"] is False
    assert payout["funds_moved"] is False


def test_reconciliation_skips_sla_refund_when_credit_debit_did_not_post() -> None:
    service = _service()
    service.apply_market_provider(_provider_application())
    service.verify_market_provider("provider_live_gpu_1", {})
    raw_event = {
        "id": "evt_sla_insufficient_credit",
        "type": "checkout.session.completed",
        "amount": 0.1,
        "currency": "usd",
        "metadata": {"account_id": "acct_sla_insufficient"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_sla_insufficient_credit"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(
        job_id,
        {
            "account_id": "acct_sla_insufficient",
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "actual_latency_ms": 1500,
            "currency": "USD",
        },
    )
    reconciliation = service.reconciliation({})["reconciliation"]
    penalty = service.store.get_record(
        "provider_sla_penalty",
        str(completed["provider_sla_penalty"]["sla_penalty_id"]),
    )

    assert completed["credit_debit"]["status"] == "insufficient_credit"
    assert completed["provider_payout"] == {}
    assert service.store.count_records("refund") == 0
    assert penalty is not None
    assert penalty["status"] == "pending_reconciliation"
    assert not penalty.get("refund_id")
    assert reconciliation["provider_sla_penalty_reconciled_this_run"] == 0
    assert reconciliation["provider_sla_penalty_reconciled_count"] == 0
    assert reconciliation["refund_count"] == 0
    assert reconciliation["ledger_balanced"] is False
    assert reconciliation["ledger_balance_delta"] == 0.18
    assert (
        _metric_total(
            service,
            "billing_refund_skipped_no_debit_total",
            {"provider_id": "provider_live_gpu_1", "debit_status": "insufficient_credit"},
        )
        == 0.18
    )

def test_provider_reputation_uses_capacity_fulfillment_from_confirmed_reservations() -> None:
    service = _service()
    service.list_capacity(
        {
            "provider_id": "provider_live_gpu_1",
            "route_id": "route_live_gpu_1",
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 4,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        }
    )
    held = service.reserve_capacity(
        {"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 4}
    )["reservation"]
    reservation_id = str(service.confirm_capacity({"reservation_id": held["reservation_id"]})["reservation"]["reservation_id"])
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_capacity_reputation_partial",
                "capacity_reservation_id": reservation_id,
            }
        )["job"]["job_id"]
    )

    service.dispatch_job(job_id, {})
    service.complete_job(
        job_id,
        {
            "actual_units": 1,
            "actual_total_cost": 0.09,
            "capacity_units_consumed": 1,
            "currency": "USD",
        },
    )
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert reputation["capacity_fulfillment_rate"] == 0.25
    assert reputation["score"] < 0.4


def test_signed_provider_receipt_callback_completes_job_and_blocks_replay(monkeypatch: Any) -> None:
    service = _service()
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
    job_id = str(service.create_job({**_job_payload(), "provider_id": "receipt-provider", "route_id": "receipt-route"})["job"]["job_id"])
    service.dispatch_job(job_id, {})

    receipt = {
        "receipt_id": "receipt-001",
        "timestamp": "2099-01-01T00:00:00Z",
        "job_id": job_id,
        "provider_id": "receipt-provider",
        "route_id": "receipt-route",
        "status": "succeeded",
        "actual_units": 2,
        "actual_total_cost": 0.18,
        "actual_latency_ms": 1200,
        "artifact_data": {"result": "ok"},
        "funds_moved": False,
    }
    payload = {"receipt": receipt, "signature": sign_payload(receipt, key).as_record(), "request_id": "receipt-request-1"}

    accepted = service.provider_job_receipt(job_id, payload)
    replayed = service.provider_job_receipt(job_id, payload)

    assert accepted["ok"] is True
    assert accepted["job"]["status"] == "succeeded"
    assert accepted["completion"]["artifact"]["metadata"] == {"result": "ok"}
    assert accepted["verification"]["receipt_id"] == "receipt-001"
    assert service.store.count_records("provider_receipt_replay_guard") == 1
    assert replayed["ok"] is False
    assert replayed["error"]["error_code"] == "provider_receipt.replay_detected"
    assert _metric_total(service, "compute_provider_receipt_accepted_total", {"provider_id": "receipt-provider", "status": "succeeded"}) == 1.0
    assert _metric_total(service, "compute_provider_receipt_rejected_total", {"provider_id": "receipt-provider", "reason": "provider_receipt.replay_detected"}) == 1.0


def test_provider_receipt_callback_rejects_tampered_signature(monkeypatch: Any) -> None:
    service = _service()
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
    job_id = str(service.create_job({**_job_payload(), "provider_id": "receipt-provider", "route_id": "receipt-route"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    receipt = {
        "receipt_id": "receipt-002",
        "timestamp": "2099-01-01T00:00:00Z",
        "job_id": job_id,
        "provider_id": "receipt-provider",
        "route_id": "receipt-route",
        "status": "succeeded",
        "actual_total_cost": 0.18,
    }
    signature = sign_payload(receipt, key).as_record()
    tampered = {**receipt, "actual_total_cost": 99.0}

    rejected = service.provider_job_receipt(job_id, {"receipt": tampered, "signature": signature})

    assert rejected["ok"] is False
    assert rejected["error"]["error_code"] == "provider_receipt.signature_invalid"
    assert service.get_job(job_id)["job"]["status"] == "running"
    assert _metric_total(service, "compute_provider_receipt_accepted_total") == 0.0
    assert _metric_total(service, "compute_provider_receipt_rejected_total", {"provider_id": "receipt-provider", "reason": "provider_receipt.signature_invalid"}) == 1.0


def test_provider_receipt_callback_enforces_ip_allowlist(monkeypatch: Any) -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("203.0.113.0/24",),
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

    blocked_job_id = str(service.create_job({**_job_payload(), "provider_id": "receipt-provider", "route_id": "receipt-route"})["job"]["job_id"])
    allowed_job_id = str(service.create_job({**_job_payload(), "provider_id": "receipt-provider", "route_id": "receipt-route"})["job"]["job_id"])
    service.dispatch_job(blocked_job_id, {})
    service.dispatch_job(allowed_job_id, {})
    blocked_receipt = {
        "receipt_id": "receipt-ip-blocked",
        "timestamp": "2099-01-01T00:00:00Z",
        "job_id": blocked_job_id,
        "provider_id": "receipt-provider",
        "route_id": "receipt-route",
        "status": "succeeded",
        "actual_units": 2,
        "actual_total_cost": 0.18,
    }
    allowed_receipt = {**blocked_receipt, "receipt_id": "receipt-ip-allowed", "job_id": allowed_job_id}

    blocked = service.provider_job_receipt(
        blocked_job_id,
        {
            "receipt": blocked_receipt,
            "signature": sign_payload(blocked_receipt, key).as_record(),
            "_flow_memory_client_ip": "198.51.100.10",
        },
    )
    allowed = service.provider_job_receipt(
        allowed_job_id,
        {
            "receipt": allowed_receipt,
            "signature": sign_payload(allowed_receipt, key).as_record(),
            "_flow_memory_client_ip": "203.0.113.42",
        },
    )

    assert blocked["ok"] is False
    assert blocked["error"]["error_code"] == "provider_receipt.ip_not_allowed"
    assert service.get_job(blocked_job_id)["job"]["status"] == "running"
    assert allowed["ok"] is True
    assert allowed["job"]["status"] == "succeeded"
    assert _metric_total(service, "compute_provider_receipt_rejected_total", {"reason": "provider_receipt.ip_not_allowed"}) == 1.0


def test_provider_job_state_callbacks_enforce_ip_allowlist() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            provider_callback_ip_allowlist=("203.0.113.0/24",),
        ),
    )

    blocked_complete_job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    allowed_complete_job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    fail_job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    heartbeat_job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    service.dispatch_job(blocked_complete_job_id, {})
    service.dispatch_job(allowed_complete_job_id, {})
    service.dispatch_job(heartbeat_job_id, {})

    blocked_complete = service.complete_job(
        blocked_complete_job_id,
        {"actual_total_cost": 0.2, "_flow_memory_client_ip": "198.51.100.10"},
    )
    allowed_complete = service.complete_job(
        allowed_complete_job_id,
        {"actual_total_cost": 0.2, "_flow_memory_client_ip": "203.0.113.42"},
    )
    blocked_fail = service.fail_job(
        fail_job_id,
        {"error_code": "provider_execution_failed", "reason": "blocked by callback allowlist", "_flow_memory_client_ip": "198.51.100.10"},
    )
    blocked_heartbeat = service.heartbeat_job(
        heartbeat_job_id,
        {"worker_id": "worker_1", "ttl_seconds": 60, "_flow_memory_client_ip": "198.51.100.10"},
    )

    for callback_action, result in {
        "complete": blocked_complete,
        "fail": blocked_fail,
        "heartbeat": blocked_heartbeat,
    }.items():
        assert result["ok"] is False
        assert result["error"]["error_code"] == "provider_callback.ip_not_allowed"
        assert result["error"]["details"]["callback_action"] == callback_action

    assert service.get_job(blocked_complete_job_id)["job"]["status"] == "running"
    assert allowed_complete["ok"] is True
    assert allowed_complete["job"]["status"] == "succeeded"
    assert service.get_job(fail_job_id)["job"]["status"] == "queued"
    assert service.get_job(heartbeat_job_id)["job"]["status"] == "running"
    assert "heartbeat_count" not in service.get_job(heartbeat_job_id)["job"]
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"reason": "provider_callback.ip_not_allowed"}) == 3.0


def test_provider_job_state_callbacks_verify_signature_and_replay(monkeypatch: Any) -> None:
    service = _service()
    key = LocalKeyPair("provider-state-callback-key", "provider-state-callback-secret")
    monkeypatch.setenv("FLOW_MEMORY_PROVIDER_STATE_CALLBACK_SECRET", key.secret)
    service.create_provider(
        {
            "provider_id": "state-callback-provider",
            "provider_name": "State Callback Provider",
            "provider_type": "gpu",
            "metadata": {
                "callback_signing_key_id": key.key_id,
                "callback_signing_key_env": "FLOW_MEMORY_PROVIDER_STATE_CALLBACK_SECRET",
            },
        }
    )

    missing_job_id = str(service.create_job({**_job_payload(), "provider_id": "state-callback-provider", "route_id": "state-route"})["job"]["job_id"])
    tampered_job_id = str(service.create_job({**_job_payload(), "provider_id": "state-callback-provider", "route_id": "state-route"})["job"]["job_id"])
    complete_job_id = str(service.create_job({**_job_payload(), "provider_id": "state-callback-provider", "route_id": "state-route"})["job"]["job_id"])
    fail_job_id = str(service.create_job({**_job_payload(), "provider_id": "state-callback-provider", "route_id": "state-route"})["job"]["job_id"])
    heartbeat_job_id = str(service.create_job({**_job_payload(), "provider_id": "state-callback-provider", "route_id": "state-route"})["job"]["job_id"])

    service.dispatch_job(missing_job_id, {})
    service.dispatch_job(tampered_job_id, {})
    service.dispatch_job(complete_job_id, {})
    service.claim_job({"job_id": heartbeat_job_id, "worker_id": "worker_state_callback", "ttl_seconds": 60})

    missing = service.complete_job(
        missing_job_id,
        {"actual_total_cost": 0.2, "callback_id": "state-missing", "timestamp": "2099-01-01T00:00:00Z"},
    )

    original_tampered_payload = {
        "actual_total_cost": 0.2,
        "callback_id": "state-tampered",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    tampered_signature = sign_payload(
        _provider_state_callback_signature_payload(
            service.get_job(tampered_job_id)["job"],
            original_tampered_payload,
            callback_action="complete",
        ),
        key,
    ).as_record()
    tampered = service.complete_job(
        tampered_job_id,
        {**original_tampered_payload, "actual_total_cost": 0.4, "signature": tampered_signature},
    )

    complete_payload = {
        "actual_total_cost": 0.2,
        "actual_units": 2,
        "callback_id": "state-complete",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    complete = service.complete_job(
        complete_job_id,
        _signed_state_callback(
            service.get_job(complete_job_id)["job"],
            complete_payload,
            key,
            callback_action="complete",
        ),
    )
    replayed = service.complete_job(
        complete_job_id,
        _signed_state_callback(
            service.get_job(complete_job_id)["job"],
            complete_payload,
            key,
            callback_action="complete",
        ),
    )

    fail_payload = {
        "error_code": "provider_timeout",
        "reason": "signed provider failure",
        "callback_id": "state-fail",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    failed = service.fail_job(
        fail_job_id,
        _signed_state_callback(
            service.get_job(fail_job_id)["job"],
            fail_payload,
            key,
            callback_action="fail",
        ),
    )

    heartbeat_payload = {
        "worker_id": "worker_state_callback",
        "ttl_seconds": 120,
        "callback_id": "state-heartbeat",
        "timestamp": "2099-01-01T00:00:00Z",
    }
    heartbeat = service.heartbeat_job(
        heartbeat_job_id,
        _signed_state_callback(
            service.get_job(heartbeat_job_id)["job"],
            heartbeat_payload,
            key,
            callback_action="heartbeat",
        ),
    )

    assert missing["ok"] is False
    assert missing["error"]["error_code"] == "provider_callback.signature_missing"
    assert service.get_job(missing_job_id)["job"]["status"] == "running"
    assert tampered["ok"] is False
    assert tampered["error"]["error_code"] == "provider_callback.signature_invalid"
    assert service.get_job(tampered_job_id)["job"]["status"] == "running"
    assert complete["ok"] is True
    assert complete["job"]["status"] == "succeeded"
    assert replayed["ok"] is False
    assert replayed["error"]["error_code"] == "provider_callback.replay_detected"
    assert failed["ok"] is True
    assert failed["job"]["status"] == "failed"
    assert heartbeat["ok"] is True
    assert heartbeat["job"]["heartbeat_count"] == 1
    assert service.store.count_records("provider_callback_replay_guard") == 3
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"reason": "provider_callback.signature_missing"}) == 1.0
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"reason": "provider_callback.signature_invalid"}) == 1.0
    assert _metric_total(service, "compute_provider_callback_rejected_total", {"reason": "provider_callback.replay_detected"}) == 1.0


def test_compute_worker_claim_heartbeat_dispatch_and_complete() -> None:
    service = _service()
    job_id = str(service.create_job(_job_payload())["job"]["job_id"])

    claimed = service.claim_job({"worker_id": "worker_1", "ttl_seconds": 60, "capabilities": ["gpu:H100"]})
    assert claimed["job"]["job_id"] == job_id
    assert claimed["job"]["status"] == "dispatched"
    assert claimed["job"]["claimed_by"] == "worker_1"
    assert claimed["job"]["lease_expires_at"]
    assert service.claim_job({"worker_id": "worker_2"})["ok"] is False

    try:
        service.dispatch_job(job_id, {"worker_id": "worker_2"})
    except ValueError as exc:
        assert "does not own claim" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("non-owning worker dispatched a claimed job")

    heartbeat = service.heartbeat_job(job_id, {"worker_id": "worker_1", "ttl_seconds": 120})
    assert heartbeat["job"]["heartbeat_count"] == 1
    dispatched = service.dispatch_job(job_id, {"worker_id": "worker_1"})
    assert dispatched["job"]["status"] == "running"
    completed = service.complete_job(job_id, {"worker_id": "worker_1", "actual_total_cost": 0.2})
    assert completed["job"]["status"] == "succeeded"
    assert completed["job"]["completed_by_worker_id"] == "worker_1"
    event_types = {event["event_type"] for event in service.job_events(job_id)["events"]}
    assert {"job.claimed", "job.heartbeat", "job.started", "job.completed"}.issubset(event_types)


def test_compute_worker_dispatch_calls_provider_execution_adapter() -> None:
    server = create_provider_sandbox_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    endpoint = f"http://{host}:{port}/execute"
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            external_provider_allowlist=("127.0.0.1",),
            external_provider_execution_enabled=True,
            provider_callback_ip_allowlist=("127.0.0.1",),
            external_provider_execution_timeout_ms=1_000,
        ),
    )
    service.store.put_record(
        "compute_provider",
        "sandbox-provider",
        {
            "provider_id": "sandbox-provider",
            "provider_name": "Sandbox Provider",
            "provider_type": "gpu",
            "market_type": "marketplace",
            "network": "offchain",
            "payment_asset": "USDC",
            "status": "active",
            "supported_unit_types": ("gpu_minute",),
            "supported_assets": ("USDC",),
            "supported_networks": ("offchain",),
            "metadata": {"execution_endpoint": endpoint},
        },
        provider_id="sandbox-provider",
        status="active",
    )
    try:
        job_id = str(
            service.create_job(
                {
                    **_job_payload(),
                    "provider_id": "sandbox-provider",
                    "route_id": "sandbox-gpu-route",
                    "job_id": "job_provider_execution",
                }
            )["job"]["job_id"]
        )
        service.claim_job({"worker_id": "worker_1", "job_id": job_id})
        dispatched = service.dispatch_job(job_id, {"worker_id": "worker_1"})
    finally:
        server.shutdown()
        server.server_close()

    assert dispatched["ok"] is True
    assert dispatched["job"]["status"] == "running"
    assert dispatched["job"]["provider_dispatch"] == "external_provider_execution"
    assert dispatched["event"]["details"]["external_provider_called"] is True
    assert dispatched["event"]["details"]["provider_execution"]["status"] == "running"
    assert dispatched["event"]["details"]["provider_execution"]["funds_moved"] is False
    assert dispatched["event"]["details"]["provider_execution"]["broadcast_allowed"] is False


def test_provider_execution_fails_closed_when_configured_without_endpoint() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            external_provider_allowlist=("127.0.0.1",),
            external_provider_execution_enabled=True,
            provider_callback_ip_allowlist=("127.0.0.1",),
        ),
    )
    service.store.put_record(
        "compute_provider",
        "provider_without_execution",
        {
            "provider_id": "provider_without_execution",
            "provider_name": "Provider Without Execution",
            "provider_type": "gpu",
            "market_type": "marketplace",
            "status": "active",
            "metadata": {},
        },
        provider_id="provider_without_execution",
        status="active",
    )
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "provider_id": "provider_without_execution",
                "route_id": "route_without_execution",
                "job_id": "job_missing_execution_endpoint",
            }
        )["job"]["job_id"]
    )
    service.claim_job({"worker_id": "worker_1", "job_id": job_id})

    result = service.dispatch_job(job_id, {"worker_id": "worker_1"})

    assert result["ok"] is False
    assert result["error"]["error_code"] == "provider_execution.disabled"
    assert result["event"]["event_type"] == "job.external_execution_failed"
    assert result["event"]["details"]["error"]["error_code"] == "provider_execution.disabled"
    assert any(
        event["event_type"] == "job.external_execution_failed"
        and event["details"]["error"]["error_code"] == "provider_execution.disabled"
        for event in service.job_events(job_id)["events"]
    )
    assert service.get_job(job_id)["job"]["status"] == "dispatched"


def test_compute_worker_release_and_expired_lease_reclaim() -> None:
    service = _service()
    first_job_id = str(service.create_job(_job_payload())["job"]["job_id"])
    released_claim = service.claim_job({"worker_id": "worker_1"})
    assert released_claim["job"]["job_id"] == first_job_id

    released = service.release_job_claim(first_job_id, {"worker_id": "worker_1", "reason": "worker shutdown"})
    assert released["job"]["status"] == "queued"
    reclaimed = service.claim_job({"worker_id": "worker_2"})
    assert reclaimed["job"]["job_id"] == first_job_id
    assert reclaimed["job"]["claimed_by"] == "worker_2"

    second_job_id = str(service.create_job({**_job_payload(), "job_id": "job_expired_claim"})["job"]["job_id"])
    expired = service.claim_job({"worker_id": "worker_3", "job_id": second_job_id})
    stale_job = dict(expired["job"])
    stale_job["lease_expires_at"] = "2000-01-01T00:00:00Z"
    service.store.put_record(
        "compute_job",
        second_job_id,
        stale_job,
        provider_id=str(stale_job["provider_id"]),
        route_id=str(stale_job["route_id"]),
        task_type=str(stale_job["task_type"]),
        status="dispatched",
        expires_at="2000-01-01T00:00:00Z",
        actor_id="worker_3",
    )

    expired_reclaim = service.claim_job({"worker_id": "worker_4", "job_id": second_job_id})
    assert expired_reclaim["job"]["claimed_by"] == "worker_4"
    assert expired_reclaim["job"]["dispatch_attempt"] == 2


def test_compute_job_failure_and_invalid_transitions_are_rejected() -> None:
    service = _service()
    job_id = str(service.create_job(_job_payload())["job"]["job_id"])

    failed = service.fail_job(job_id, {"error_code": "provider_timeout", "reason": "timeout"})
    assert failed["job"]["status"] == "failed"
    assert failed["event"]["details"]["error_code"] == "provider_timeout"

    try:
        service.dispatch_job(job_id, {})
    except ValueError as exc:
        assert "cannot dispatch compute job" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("failed job was dispatched")

    queued_job_id = str(service.create_job({**_job_payload(), "job_id": "job_complete_from_queued"})["job"]["job_id"])
    try:
        service.complete_job(queued_job_id, {"actual_total_cost": 0.1})
    except ValueError as exc:
        assert "cannot complete compute job" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("queued job completed without dispatch")


def test_fail_job_status_race_does_not_release_reserved_credit(monkeypatch: Any) -> None:
    service = _service()
    account_id = "acct_fail_status_race"
    _credit_account(service, account_id, 1.0, event_id="evt_fail_status_race")
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_fail_status_race",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {"account_id": account_id})
    reservation_id = str(dispatched["credit_reservation"]["credit_transaction_id"])
    original_put_record_if_state = service.store.put_record_if_state

    def fail_failure_transition(
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> bool:
        if record_type == "compute_job" and record_id == job_id and expected_statuses == (
            "queued",
            "dispatched",
            "running",
        ):
            return False
        return original_put_record_if_state(record_type, record_id, expected_statuses, payload, **kwargs)

    monkeypatch.setattr(service.store, "put_record_if_state", fail_failure_transition)

    failed = service.fail_job(job_id, {"error_code": "provider_timeout", "reason": "late failure"})
    balance = service.billing_balance({"account_id": account_id})["balance"]
    transactions = service.store.list_records(
        "credit_transaction",
        filters={"tenant_id": account_id},
        limit=10,
    ).records

    assert failed["ok"] is False
    assert failed["error"]["error_code"] == "job.status_changed"
    assert failed["job"]["status"] == "running"
    assert service.get_job(job_id)["job"]["status"] == "running"
    assert service.store.get_record("credit_transaction", reservation_id)["status"] == "reserved"
    assert not any(record["transaction_type"] == "reserve_release" for record in transactions)
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18
    assert not any(event["event_type"] == "job.failed" for event in service.job_events(job_id)["events"])

def test_cancel_job_status_race_does_not_release_reserved_credit(monkeypatch: Any) -> None:
    service = _service()
    account_id = "acct_cancel_status_race"
    _credit_account(service, account_id, 1.0, event_id="evt_cancel_status_race")
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_cancel_status_race",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {"account_id": account_id})
    reservation_id = str(dispatched["credit_reservation"]["credit_transaction_id"])
    original_put_record_if_state = service.store.put_record_if_state

    def fail_cancel_transition(
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> bool:
        if record_type == "compute_job" and record_id == job_id and expected_statuses == (
            "queued",
            "dispatched",
            "running",
        ):
            return False
        return original_put_record_if_state(record_type, record_id, expected_statuses, payload, **kwargs)

    monkeypatch.setattr(service.store, "put_record_if_state", fail_cancel_transition)

    cancelled = service.cancel_job(job_id, {"reason": "late cancel"})
    balance = service.billing_balance({"account_id": account_id})["balance"]
    transactions = service.store.list_records(
        "credit_transaction",
        filters={"tenant_id": account_id},
        limit=10,
    ).records

    assert cancelled["ok"] is False
    assert cancelled["error"]["error_code"] == "job.status_changed"
    assert cancelled["job"]["status"] == "running"
    assert service.get_job(job_id)["job"]["status"] == "running"
    assert service.store.get_record("credit_transaction", reservation_id)["status"] == "reserved"
    assert not any(record["transaction_type"] == "reserve_release" for record in transactions)
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18
    assert not any(event["event_type"] == "job.cancelled" for event in service.job_events(job_id)["events"])

def test_retry_job_status_race_does_not_release_reserved_credit(monkeypatch: Any) -> None:
    service = _service()
    account_id = "acct_retry_status_race"
    _credit_account(service, account_id, 1.0, event_id="evt_retry_status_race")
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_retry_status_race",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {"account_id": account_id})
    reservation_id = str(dispatched["credit_reservation"]["credit_transaction_id"])
    original_put_record_if_state = service.store.put_record_if_state

    def fail_retry_transition(
        record_type: str,
        record_id: str,
        expected_statuses: tuple[str, ...],
        payload: Mapping[str, Any],
        **kwargs: Any,
    ) -> bool:
        if record_type == "compute_job" and record_id == job_id and expected_statuses == ("running",):
            return False
        return original_put_record_if_state(record_type, record_id, expected_statuses, payload, **kwargs)

    monkeypatch.setattr(service.store, "put_record_if_state", fail_retry_transition)

    retried = service.retry_job(job_id, {"reason": "late retry"})
    balance = service.billing_balance({"account_id": account_id})["balance"]
    transactions = service.store.list_records(
        "credit_transaction",
        filters={"tenant_id": account_id},
        limit=10,
    ).records

    assert retried["ok"] is False
    assert retried["error"]["error_code"] == "job.status_changed"
    assert retried["job"]["status"] == "running"
    assert service.get_job(job_id)["job"]["status"] == "running"
    assert service.store.get_record("credit_transaction", reservation_id)["status"] == "reserved"
    assert not any(record["transaction_type"] == "reserve_release" for record in transactions)
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18
    assert not any(event["event_type"] == "job.retry_queued" for event in service.job_events(job_id)["events"])

def test_compute_job_retry_and_cancel_remain_dry_run_safe() -> None:
    service = _service()
    tenant_id = "tenant_job_state"
    workspace_id = "workspace_job_state"
    job_id = str(
        service.create_job({**_job_payload(), "tenant_id": tenant_id, "workspace_id": workspace_id})["job"][
            "job_id"
        ]
    )

    retried = service.retry_job(job_id, {"tenant_id": tenant_id})
    assert retried["job"]["attempt"] == 1
    cancelled = service.cancel_job(job_id, {"tenant_id": tenant_id, "reason": "operator test"})
    tenant_jobs = service.store.list_records("compute_job", filters={"tenant_id": tenant_id}).records
    tenant_events = service.store.list_records("compute_job_event", filters={"tenant_id": tenant_id}).records

    assert cancelled["job"]["status"] == "cancelled"
    assert service.job_events(job_id, {"tenant_id": tenant_id})["events"]
    assert len(tenant_jobs) == 1
    assert tenant_jobs[0]["status"] == "cancelled"
    assert {event["event_type"] for event in tenant_events} == {"job.queued", "job.retry_queued", "job.cancelled"}


def test_compute_job_retry_respects_max_retries() -> None:
    service = _service()
    job_id = str(
        service.create_job({**_job_payload(), "job_id": "job_retry_limit", "max_retries": 1})["job"]["job_id"]
    )

    retried = service.retry_job(job_id, {})
    rejected = service.retry_job(job_id, {})

    assert retried["ok"] is True
    assert retried["job"]["attempt"] == 1
    assert rejected["ok"] is False
    assert rejected["error"]["error_code"] == "policy.max_retries_exceeded"
    assert rejected["job"]["attempt"] == 1
    event_types = {event["event_type"] for event in service.job_events(job_id)["events"]}
    assert "job.max_retries_exceeded" in event_types


def test_billing_ledger_requires_external_checkout_and_verifies_webhook_signature() -> None:
    service = _service()
    checkout = service.billing_checkout({"account_id": "acct_1", "amount": 100, "currency": "USD"})
    assert checkout["ok"] is False
    assert checkout["checkout"]["funds_moved"] is False
    assert checkout["checkout"]["status"] == "requires_external_checkout_provider"
    assert checkout["invoice"]["source_type"] == "checkout"
    assert checkout["invoice"]["status"] == "requires_external_checkout_provider"
    assert checkout["invoice"]["amount"] == 100
    assert checkout["invoice"]["funds_moved"] is False
    assert checkout["checkout"]["invoice_id"] == checkout["invoice"]["invoice_id"]

    raw_event = {"id": "evt_1", "type": "checkout.session.completed", "amount_total": 10000, "currency": "usd", "metadata": {"account_id": "acct_1"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    assert webhook["ok"] is True
    assert webhook["payment_event"]["verified"] is True
    assert webhook["credit_transaction"]["amount"] == 100.0
    assert service.billing_balance({"account_id": "acct_1"})["balance"]["available_credits"] == 100.0

def test_billing_checkout_idempotent_replay() -> None:
    service = _service()
    first = service.billing_checkout(
        {
            "account_id": "acct_checkout_idempotent",
            "amount": 25,
            "currency": "USD",
            "idempotency_key": "checkout-idem-1",
            "request_id": "checkout-idem-request-1",
        }
    )
    replay = service.billing_checkout(
        {
            "account_id": "acct_checkout_idempotent",
            "amount": 25,
            "currency": "USD",
            "idempotency_key": "checkout-idem-1",
            "request_id": "checkout-idem-request-2",
        }
    )
    conflict = service.billing_checkout(
        {
            "account_id": "acct_checkout_idempotent",
            "amount": 30,
            "currency": "USD",
            "idempotency_key": "checkout-idem-1",
            "request_id": "checkout-idem-request-3",
        }
    )

    assert first["ok"] is False
    assert replay["ok"] is False
    assert replay["idempotent_replay"] is True
    assert replay["checkout"]["payment_event_id"] == first["checkout"]["payment_event_id"]
    assert replay["invoice"]["invoice_id"] == first["invoice"]["invoice_id"]
    assert conflict["ok"] is False
    assert conflict["error"]["error_code"] == "billing.checkout.idempotency_conflict"
    assert service.store.count_records("payment_event") == 1
    assert service.store.count_records("billing_invoice") == 1



def test_billing_webhook_converts_sub_dollar_stripe_minor_units() -> None:
    service = _service()
    raw_event = {
        "id": "evt_sub_dollar_checkout",
        "type": "checkout.session.completed",
        "amount_total": 50,
        "currency": "usd",
        "metadata": {"account_id": "acct_sub_dollar"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()

    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    balance = service.billing_balance({"account_id": "acct_sub_dollar"})["balance"]

    assert webhook["ok"] is True
    assert webhook["payment_event"]["amount"] == 0.5
    assert webhook["credit_transaction"]["amount"] == 0.5
    assert balance["available_credits"] == 0.5


def test_billing_webhook_duplicate_delivery_is_idempotent() -> None:
    service = _service()
    raw_event = {
        "id": "evt_duplicate_delivery",
        "type": "checkout.session.completed",
        "amount_total": 4200,
        "currency": "usd",
        "metadata": {"account_id": "acct_duplicate"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()

    first = service.billing_webhook_stripe(
        {"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature}
    )
    replay = service.billing_webhook_stripe(
        {"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature}
    )
    tampered_replay = service.billing_webhook_stripe(
        {
            "raw_event": {**raw_event, "amount_total": 9900},
            "webhook_secret": secret,
            "stripe_signature": hmac.new(
                secret.encode("utf-8"),
                content_hash({**raw_event, "amount_total": 9900}).encode("utf-8"),
                "sha256",
            ).hexdigest(),
        }
    )

    assert first["ok"] is True
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["credit_transaction"]["credit_transaction_id"] == first["credit_transaction"]["credit_transaction_id"]
    assert tampered_replay["ok"] is False
    assert tampered_replay["error"]["error_code"] == "billing.webhook.event_id_hash_mismatch"
    assert service.store.count_records("payment_event") == 1
    assert service.store.count_records("credit_transaction") == 1
    assert service.billing_balance({"account_id": "acct_duplicate"})["balance"]["available_credits"] == 42.0


def test_billing_webhook_accepts_stripe_v1_signature_header() -> None:
    service = _service()
    raw_event = {"id": "evt_stripe_header", "type": "checkout.session.completed", "amount_total": 2500, "currency": "usd", "metadata": {"account_id": "acct_header"}}
    raw_event_body = json.dumps(raw_event, separators=(",", ":"), sort_keys=True)
    secret = "whsec_test_secret"
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}.{raw_event_body}".encode("utf-8"), "sha256").hexdigest()
    stripe_signature = f"t={timestamp},v1=bad-signature,v1={digest}"

    webhook = service.billing_webhook_stripe(
        {
            "raw_event": raw_event,
            "raw_event_body": raw_event_body,
            "webhook_secret": secret,
            "stripe_signature": stripe_signature,
        }
    )
    missing_body = service.billing_webhook_stripe(
        {
            "raw_event": {**raw_event, "id": "evt_stripe_header_missing_body"},
            "webhook_secret": secret,
            "stripe_signature": stripe_signature,
        }
    )
    expired_event = {**raw_event, "id": "evt_stripe_header_expired"}
    expired_body = json.dumps(expired_event, separators=(",", ":"), sort_keys=True)
    expired_timestamp = str(int(time.time()) - 301)
    expired_digest = hmac.new(
        secret.encode("utf-8"),
        f"{expired_timestamp}.{expired_body}".encode("utf-8"),
        "sha256",
    ).hexdigest()
    expired = service.billing_webhook_stripe(
        {
            "raw_event": expired_event,
            "raw_event_body": expired_body,
            "webhook_secret": secret,
            "stripe_signature": f"t={expired_timestamp},v1={expired_digest}",
        }
    )

    assert webhook["ok"] is True
    assert webhook["payment_event"]["verified"] is True
    assert webhook["credit_transaction"]["amount"] == 25.0
    assert missing_body["ok"] is False
    assert missing_body["payment_event"]["status"] == "rejected_unverified"
    assert expired["ok"] is False
    assert expired["payment_event"]["status"] == "rejected_unverified"


def test_billing_webhook_v1_signature_rejects_processed_dict_mismatch() -> None:
    service = _service()
    signed_event = {
        "id": "evt_stripe_signed_body_mismatch",
        "type": "checkout.session.completed",
        "amount_total": 2500,
        "currency": "usd",
        "metadata": {"account_id": "acct_signed_body"},
    }
    tampered_event = {
        **signed_event,
        "amount_total": 999900,
        "metadata": {"account_id": "acct_tampered_body"},
    }
    raw_event_body = json.dumps(signed_event, separators=(",", ":"), sort_keys=True)
    secret = "whsec_signed_body_mismatch"
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}.{raw_event_body}".encode("utf-8"), "sha256").hexdigest()

    webhook = service.billing_webhook_stripe(
        {
            "raw_event": tampered_event,
            "raw_event_body": raw_event_body,
            "webhook_secret": secret,
            "stripe_signature": f"t={timestamp},v1={digest}",
        }
    )
    signed_balance = service.billing_balance({"account_id": "acct_signed_body"})["balance"]
    tampered_balance = service.billing_balance({"account_id": "acct_tampered_body"})["balance"]

    assert webhook["ok"] is False
    assert webhook["error"]["error_code"] == "billing.webhook.signed_body_mismatch"
    assert webhook["payment_event"]["status"] == "rejected_signed_body_mismatch"
    assert webhook["payment_event"]["amount"] == 0.0
    assert webhook["credit_transaction"] == {}
    assert signed_balance["available_credits"] == 0.0
    assert tampered_balance["available_credits"] == 0.0


def test_billing_webhook_v1_signature_replay_beyond_tolerance_is_idempotent() -> None:
    service = _service()
    raw_event = {
        "id": "evt_stripe_header_idempotent_replay",
        "type": "checkout.session.completed",
        "amount_total": 3300,
        "currency": "usd",
        "metadata": {"account_id": "acct_header_replay"},
    }
    raw_event_body = json.dumps(raw_event, separators=(",", ":"), sort_keys=True)
    secret = "whsec_test_secret"
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}.{raw_event_body}".encode("utf-8"), "sha256").hexdigest()
    expired_timestamp = str(int(time.time()) - 1_000)
    expired_digest = hmac.new(
        secret.encode("utf-8"),
        f"{expired_timestamp}.{raw_event_body}".encode("utf-8"),
        "sha256",
    ).hexdigest()

    first = service.billing_webhook_stripe(
        {
            "raw_event": raw_event,
            "raw_event_body": raw_event_body,
            "webhook_secret": secret,
            "stripe_signature": f"t={timestamp},v1={digest}",
        }
    )
    replay = service.billing_webhook_stripe(
        {
            "raw_event": raw_event,
            "raw_event_body": raw_event_body,
            "webhook_secret": secret,
            "stripe_signature": f"t={expired_timestamp},v1={expired_digest}",
        }
    )

    assert first["ok"] is True
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["credit_transaction"]["credit_transaction_id"] == first["credit_transaction"]["credit_transaction_id"]
    assert service.store.count_records("payment_event") == 1
    assert service.store.count_records("credit_transaction") == 1
    assert service.billing_balance({"account_id": "acct_header_replay"})["balance"]["available_credits"] == 33.0


def test_billing_webhook_records_verified_payment_failure_without_crediting_balance() -> None:
    service = _service()
    raw_event = {
        "id": "evt_payment_failed",
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "customer": "acct_failed_payment",
                "amount": 1234,
                "currency": "usd",
                "last_payment_error": {"code": "card_declined", "message": "The card was declined."},
            }
        },
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()

    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    balance = service.billing_balance({"account_id": "acct_failed_payment"})["balance"]

    assert webhook["ok"] is True
    assert webhook["payment_event"]["status"] == "verified_payment_failed"
    assert webhook["payment_event"]["failure_recorded"] is True
    assert webhook["payment_event"]["failure_code"] == "card_declined"
    assert webhook["payment_event"]["amount"] == 12.34
    assert webhook["credit_transaction"] == {}
    assert balance["available_credits"] == 0.0
    assert (
        _metric_total(
            service,
            "billing_payment_failed_total",
            {"provider": "stripe", "event_type": "payment_intent.payment_failed"},
        )
        == 1.0
    )


def test_billing_checkout_creates_external_stripe_session_when_enabled() -> None:
    server, base_url = _stripe_checkout_server()
    try:
        service = _stripe_checkout_service(base_url)
        checkout = service.billing_checkout(
            {
                "account_id": "acct_checkout",
                "amount": 12.34,
                "currency": "USD",
                "request_id": "checkout-request-1",
                "idempotency_key": "checkout-idempotency-1",
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    assert checkout["ok"] is True
    assert checkout["checkout"]["status"] == "checkout_redirect_pending"
    assert checkout["checkout"]["external_checkout_session_id"] == "cs_test_flow_memory"
    assert checkout["checkout"]["external_checkout_url"].startswith("https://checkout.stripe.test/")
    assert checkout["checkout"]["funds_moved"] is False
    assert checkout["checkout"]["dry_run_only"] is True
    assert service.store.count_records("payment_event") == 1
    assert _STRIPE_CHECKOUT_REQUESTS[0]["authorization"] == "Bearer sk_test_flow_memory_checkout"
    assert _STRIPE_CHECKOUT_REQUESTS[0]["idempotency_key"] == "checkout-idempotency-1"
    params = cast(dict[str, list[str]], _STRIPE_CHECKOUT_REQUESTS[0]["params"])
    assert params["client_reference_id"] == ["acct_checkout"]
    assert params["line_items[0][price_data][unit_amount]"] == ["1234"]
    assert params["metadata[account_id]"] == ["acct_checkout"]


def test_stripe_checkout_webhook_requires_server_checkout_amount_match() -> None:
    server, base_url = _stripe_checkout_server()
    try:
        service = _stripe_checkout_service(base_url)
        checkout = service.billing_checkout(
            {
                "account_id": "acct_checkout_webhook",
                "amount": 12.34,
                "currency": "USD",
                "request_id": "checkout-webhook-request",
                "idempotency_key": "checkout-webhook-idem",
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    payment_event_id = str(checkout["checkout"]["payment_event_id"])
    session_id = str(checkout["checkout"]["external_checkout_session_id"])
    secret = service.config.stripe_webhook_secret
    mismatched_event = {
        "id": "evt_checkout_amount_mismatch",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "amount_total": 9999,
                "currency": "usd",
                "metadata": {"account_id": "acct_checkout_webhook", "payment_event_id": payment_event_id},
            }
        },
    }
    missing_reference_event = {
        "id": "evt_checkout_missing_reference",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "amount_total": 1234,
                "currency": "usd",
                "metadata": {"account_id": "acct_checkout_webhook"},
            }
        },
    }
    accepted_event = {
        "id": "evt_checkout_amount_match",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "amount_total": 1234,
                "currency": "usd",
                "metadata": {"account_id": "acct_checkout_webhook", "payment_event_id": payment_event_id},
            }
        },
    }

    mismatch = service.billing_webhook_stripe(
        {
            "raw_event": mismatched_event,
            "stripe_signature": hmac.new(secret.encode("utf-8"), content_hash(mismatched_event).encode("utf-8"), "sha256").hexdigest(),
        }
    )
    missing_reference = service.billing_webhook_stripe(
        {
            "raw_event": missing_reference_event,
            "stripe_signature": hmac.new(secret.encode("utf-8"), content_hash(missing_reference_event).encode("utf-8"), "sha256").hexdigest(),
        }
    )
    accepted = service.billing_webhook_stripe(
        {
            "raw_event": accepted_event,
            "stripe_signature": hmac.new(secret.encode("utf-8"), content_hash(accepted_event).encode("utf-8"), "sha256").hexdigest(),
        }
    )
    balance = service.billing_balance({"account_id": "acct_checkout_webhook"})["balance"]

    assert mismatch["ok"] is False
    assert mismatch["error"]["error_code"] == "billing.webhook.checkout_amount_mismatch"
    assert mismatch["payment_event"]["status"] == "rejected_untrusted_checkout"
    assert missing_reference["ok"] is False
    assert missing_reference["error"]["error_code"] == "billing.webhook.checkout_reference_required"
    assert accepted["ok"] is True
    assert accepted["credit_transaction"]["amount"] == 12.34
    assert balance["available_credits"] == 12.34
    assert service.store.count_records("credit_transaction") == 1

def test_stripe_checkout_webhook_rejects_unknown_invalid_session_and_currency_references() -> None:
    server, base_url = _stripe_checkout_server()
    try:
        service = _stripe_checkout_service(base_url)
        checkout = service.billing_checkout(
            {
                "account_id": "acct_checkout_rejections",
                "amount": 12.34,
                "currency": "USD",
                "request_id": "checkout-rejection-request",
                "idempotency_key": "checkout-rejection-idem",
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    payment_event_id = str(checkout["checkout"]["payment_event_id"])
    session_id = str(checkout["checkout"]["external_checkout_session_id"])
    secret = str(service.config.stripe_webhook_secret)

    def _signed_webhook(raw_event: Mapping[str, object]) -> Mapping[str, object]:
        return service.billing_webhook_stripe(
            {
                "raw_event": raw_event,
                "stripe_signature": hmac.new(
                    secret.encode("utf-8"),
                    content_hash(raw_event).encode("utf-8"),
                    "sha256",
                ).hexdigest(),
            }
        )

    def _checkout_event(
        event_id: str,
        *,
        checkout_payment_event_id: str,
        checkout_session_id: str = session_id,
        amount_total: int = 1234,
        currency: str = "usd",
    ) -> dict[str, object]:
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": checkout_session_id,
                    "amount_total": amount_total,
                    "currency": currency,
                    "metadata": {
                        "account_id": "acct_checkout_rejections",
                        "payment_event_id": checkout_payment_event_id,
                    },
                }
            },
        }

    invalid_reference_seed = _signed_webhook(
        {
            "id": "evt_checkout_invalid_reference_seed",
            "type": "payment_intent.payment_failed",
            "amount": 0,
            "currency": "usd",
            "metadata": {"account_id": "acct_checkout_rejections"},
        }
    )
    unknown = _signed_webhook(
        _checkout_event(
            "evt_checkout_unknown_reference",
            checkout_payment_event_id="payment_event_missing_checkout_reference",
        )
    )
    invalid = _signed_webhook(
        _checkout_event(
            "evt_checkout_invalid_reference",
            checkout_payment_event_id="evt_checkout_invalid_reference_seed",
        )
    )
    session_mismatch = _signed_webhook(
        _checkout_event(
            "evt_checkout_session_mismatch",
            checkout_payment_event_id=payment_event_id,
            checkout_session_id="cs_test_wrong_session",
        )
    )
    currency_mismatch = _signed_webhook(
        _checkout_event(
            "evt_checkout_currency_mismatch",
            checkout_payment_event_id=payment_event_id,
            currency="eur",
        )
    )
    balance = service.billing_balance({"account_id": "acct_checkout_rejections"})["balance"]

    assert invalid_reference_seed["ok"] is True
    assert unknown["ok"] is False
    assert unknown["error"]["error_code"] == "billing.webhook.checkout_reference_unknown"
    assert unknown["payment_event"]["status"] == "rejected_untrusted_checkout"
    assert invalid["ok"] is False
    assert invalid["error"]["error_code"] == "billing.webhook.checkout_reference_invalid"
    assert session_mismatch["ok"] is False
    assert session_mismatch["error"]["error_code"] == "billing.webhook.checkout_session_mismatch"
    assert currency_mismatch["ok"] is False
    assert currency_mismatch["error"]["error_code"] == "billing.webhook.checkout_currency_mismatch"
    assert balance["available_credits"] == 0.0
    assert service.store.count_records("credit_transaction") == 0

def test_billing_checkout_fails_closed_when_stripe_api_fails() -> None:
    server, base_url = _stripe_checkout_server(status=500)
    try:
        service = _stripe_checkout_service(base_url)
        checkout = service.billing_checkout({"account_id": "acct_failed", "amount": 10, "currency": "USD"})
    finally:
        server.shutdown()
        server.server_close()

    assert checkout["ok"] is False
    assert checkout["checkout"]["status"] == "external_checkout_failed"
    assert checkout["checkout"]["funds_moved"] is False
    assert "external_checkout_url" not in checkout["checkout"]
    event = service.store.get_record("payment_event", str(checkout["checkout"]["payment_event_id"]))
    assert event is not None
    assert event["status"] == "external_checkout_failed"


def test_billing_checkout_requires_complete_stripe_configuration() -> None:
    errors = ComputeMarketConfig(database_url=":memory:", stripe_checkout_enabled=True).validate()

    assert "stripe_checkout_enabled requires stripe_secret_key" in errors
    assert "stripe_checkout_enabled requires stripe_webhook_secret" in errors
    assert "stripe_checkout_enabled requires https stripe_checkout_success_url" in errors
    assert "stripe_checkout_enabled requires https stripe_checkout_cancel_url" in errors


def test_prepaid_credits_debit_usage_and_accrue_provider_payout() -> None:
    service = _service()
    raw_event = {"id": "evt_credit_1", "type": "checkout.session.completed", "amount": 1.0, "currency": "usd", "metadata": {"account_id": "acct_paid"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_paid_compute"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(job_id, {"account_id": "acct_paid", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"})

    assert completed["credit_debit"]["status"] == "posted"
    assert completed["credit_debit"]["transaction_type"] == "debit"
    assert completed["provider_payout"]["status"] == "accrued"
    assert completed["provider_payout"]["provider_id"] == "provider_live_gpu_1"
    assert completed["provider_payout"]["funds_moved"] is False
    assert completed["usage_invoice"]["source_type"] == "usage_charge"
    assert completed["usage_invoice"]["source_id"] == completed["usage_charge"]["usage_charge_id"]
    assert completed["usage_charge"]["invoice_id"] == completed["usage_invoice"]["invoice_id"]
    assert completed["usage_invoice"]["funds_moved"] is False
    usage = service.billing_usage({"account_id": "acct_paid"})
    assert usage["billing_invoices"][0]["invoice_id"] == completed["usage_invoice"]["invoice_id"]
    assert service.reconciliation()["reconciliation"]["billing_invoice_count"] == 1
    assert service.billing_balance({"account_id": "acct_paid"})["balance"]["available_credits"] == 0.82


def test_reconciliation_detects_credit_balance_drift_and_emits_alert_metric() -> None:
    service = _service()
    raw_event = {
        "id": "evt_credit_balance_drift",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_drift"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_credit_balance_drift",
                "account_id": "acct_drift",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(job_id, {})
    service.complete_job(job_id, {"account_id": "acct_drift", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"})
    balanced = service.reconciliation({})["reconciliation"]

    assert balanced["ledger_balanced"] is True
    assert balanced["credit_ledger_integrity"]["ok"] is True

    balance = dict(service.store.get_record("credit_balance", "acct_drift") or {})
    balance["available_credits"] = 0.12
    service.store.put_record(
        "credit_balance",
        "acct_drift",
        balance,
        tenant_id="acct_drift",
        status="active",
    )

    drifted = service.reconciliation({})["reconciliation"]
    mismatch = drifted["credit_ledger_integrity"]["mismatches"][0]

    assert drifted["ledger_balanced"] is False
    assert drifted["status"] == "dry_run_reconciliation_attention"
    assert drifted["credit_ledger_integrity"]["mismatch_count"] == 1
    assert mismatch["account_id"] == "acct_drift"
    assert mismatch["expected_available_credits"] == 0.82
    assert mismatch["actual_available_credits"] == 0.12
    assert _metric_total(service, "billing_ledger_mismatch_total") == 1.0

def test_prepaid_credit_preauthorization_blocks_dispatch_without_credit() -> None:
    service = _service()
    raw_event = {
        "id": "evt_credit_tiny_preauth",
        "type": "checkout.session.completed",
        "amount": 0.1,
        "currency": "usd",
        "metadata": {"account_id": "acct_preauth_low"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_paid_compute_preauth_low",
                "account_id": "acct_preauth_low",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )

    dispatched = service.dispatch_job(job_id, {})

    assert dispatched["ok"] is False
    assert dispatched["error"]["error_code"] == "billing.credit_preauthorization_failed"
    assert dispatched["credit_reservation"]["status"] == "insufficient_credit"
    assert dispatched["job"]["status"] == "queued"
    assert service.store.get_record("compute_job", job_id)["status"] == "queued"
    balance = service.billing_balance({"account_id": "acct_preauth_low"})["balance"]
    assert balance["available_credits"] == 0.1
    assert balance["reserved_credits"] == 0.0
    assert any(
        event["event_type"] == "job.credit_preauthorization_failed"
        for event in service.job_events(job_id)["events"]
    )
    assert (
        _metric_total(
            service,
            "billing_insufficient_credit_total",
            {"provider_id": "provider_live_gpu_1"},
        )
        == 0.18
    )

    topup_event = {
        "id": "evt_credit_tiny_preauth_topup",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_preauth_low"},
    }
    topup_signature = hmac.new(
        secret.encode("utf-8"),
        content_hash(topup_event).encode("utf-8"),
        "sha256",
    ).hexdigest()
    service.billing_webhook_stripe(
        {"raw_event": topup_event, "webhook_secret": secret, "stripe_signature": topup_signature}
    )
    retried = service.dispatch_job(job_id, {})

    assert retried["ok"] is True
    assert retried["credit_reservation"]["status"] == "reserved"
    retried_balance = service.billing_balance({"account_id": "acct_preauth_low"})["balance"]
    assert retried_balance["available_credits"] == 0.92
    assert retried_balance["reserved_credits"] == 0.18


def test_billing_spending_quota_rejects_dispatch_above_daily_limit() -> None:
    service = _service()
    account_id = "acct_quota_daily"
    _credit_account(service, account_id, 1.0, event_id="evt_quota_daily_credit")
    quota = service.set_billing_quota(
        {
            "account_id": account_id,
            "daily_spend_limit": 0.1,
            "monthly_spend_limit": 10.0,
        }
    )

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_quota_daily_reject",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {})

    assert quota["quota"]["funds_moved"] is False
    assert dispatched["ok"] is False
    assert dispatched["error"]["error_code"] == "billing.spending_quota_exceeded"
    assert dispatched["event"]["event_type"] == "job.spending_quota_exceeded"
    assert dispatched["job"]["status"] == "queued"
    assert dispatched["quota"]["daily_spend_limit"] == 0.1
    assert service.store.get_record("compute_job", job_id)["status"] == "queued"
    balance = service.billing_balance({"account_id": account_id})["balance"]
    assert balance["available_credits"] == 1.0
    assert balance["reserved_credits"] == 0.0
    assert any(event["event_type"] == "job.spending_quota_exceeded" for event in service.job_events(job_id)["events"])
    transactions = service.store.list_records("credit_transaction", filters={"tenant_id": account_id}, limit=10).records
    assert all(record["transaction_type"] != "reserve" for record in transactions)


def test_billing_spending_quota_allows_dispatch_within_limit() -> None:
    service = _service()
    account_id = "acct_quota_ok"
    _credit_account(service, account_id, 1.0, event_id="evt_quota_ok_credit")
    service.set_billing_quota(
        {
            "account_id": account_id,
            "daily_spend_limit": 1.0,
            "monthly_spend_limit": 10.0,
        }
    )

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_quota_dispatch_ok",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {})

    assert dispatched["ok"] is True
    assert dispatched["credit_reservation"]["status"] == "reserved"
    assert dispatched["job"]["status"] == "running"
    balance = service.billing_balance({"account_id": account_id})["balance"]
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18


def test_billing_spending_quota_counts_active_credit_reserves() -> None:
    service = _service()
    account_id = "acct_quota_reserved"
    _credit_account(service, account_id, 1.0, event_id="evt_quota_reserved_credit")
    service.set_billing_quota(
        {
            "account_id": account_id,
            "daily_spend_limit": 0.3,
            "monthly_spend_limit": 10.0,
        }
    )

    first_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_quota_reserved_first",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    second_job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_quota_reserved_second",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )

    first_dispatch = service.dispatch_job(first_job_id, {})
    second_dispatch = service.dispatch_job(second_job_id, {})

    assert first_dispatch["ok"] is True
    assert second_dispatch["ok"] is False
    assert second_dispatch["error"]["error_code"] == "billing.spending_quota_exceeded"
    assert second_dispatch["error"]["details"]["daily_spent"] == 0.18
    assert second_dispatch["error"]["details"]["projected_daily_spend"] == 0.36
    balance = service.billing_balance({"account_id": account_id})["balance"]
    assert balance["available_credits"] == 0.82
    assert balance["reserved_credits"] == 0.18


def test_billing_spending_quota_defaults_to_unlimited_when_not_configured() -> None:
    service = _service()
    account_id = "acct_quota_default"
    _credit_account(service, account_id, 1.0, event_id="evt_quota_default_credit")

    quota = service.billing_quota({"account_id": account_id})
    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_quota_default_ok",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {})

    assert quota["quota"]["source"] == "config_default"
    assert quota["quota"]["daily_spend_limit"] == 0.0
    assert dispatched["ok"] is True
    assert dispatched["credit_reservation"]["status"] == "reserved"


def test_prepaid_credit_preauthorization_reserves_and_settles_usage() -> None:
    service = _service()
    raw_event = {
        "id": "evt_credit_preauth",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_preauth_ok"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_paid_compute_preauth_ok",
                "account_id": "acct_preauth_ok",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )

    dispatched = service.dispatch_job(job_id, {})
    reservation_id = str(dispatched["credit_reservation"]["credit_transaction_id"])

    assert dispatched["ok"] is True
    assert dispatched["credit_reservation"]["status"] == "reserved"
    assert dispatched["job"]["credit_reservation_id"] == reservation_id
    reserved_balance = service.billing_balance({"account_id": "acct_preauth_ok"})["balance"]
    assert reserved_balance["available_credits"] == 0.82
    assert reserved_balance["reserved_credits"] == 0.18

    completed = service.complete_job(
        job_id,
        {
            "account_id": "acct_preauth_ok",
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
        },
    )

    assert completed["credit_debit"]["status"] == "posted"
    assert completed["credit_debit"]["reservation_transaction_id"] == reservation_id
    assert service.store.get_record("credit_transaction", reservation_id)["status"] == "settled"
    settled_balance = service.billing_balance({"account_id": "acct_preauth_ok"})["balance"]
    assert settled_balance["available_credits"] == 0.82
    assert settled_balance["reserved_credits"] == 0.0
    assert completed["provider_payout"]["status"] == "accrued"


def test_prepaid_credit_preauthorization_releases_hold_on_cancel() -> None:
    service = _service()
    raw_event = {
        "id": "evt_credit_preauth_cancel",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_preauth_cancel"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_paid_compute_preauth_cancel",
                "account_id": "acct_preauth_cancel",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )

    dispatched = service.dispatch_job(job_id, {})
    cancelled = service.cancel_job(job_id, {"reason": "user_cancelled"})

    assert dispatched["credit_reservation"]["status"] == "reserved"
    assert cancelled["credit_release"]["transaction_type"] == "reserve_release"
    assert cancelled["credit_release"]["reservation_transaction_id"] == dispatched["credit_reservation"]["credit_transaction_id"]
    balance = service.billing_balance({"account_id": "acct_preauth_cancel"})["balance"]
    assert balance["available_credits"] == 1.0
    assert balance["reserved_credits"] == 0.0


def test_prepaid_credit_preauthorization_releases_hold_on_retry() -> None:
    service = _service()
    raw_event = {
        "id": "evt_credit_preauth_retry",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_preauth_retry"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_paid_compute_preauth_retry",
                "account_id": "acct_preauth_retry",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )

    dispatched = service.dispatch_job(job_id, {})
    reservation_id = str(dispatched["credit_reservation"]["credit_transaction_id"])
    retried = service.retry_job(job_id, {})

    assert retried["job"]["status"] == "queued"
    assert retried["job"]["attempt"] == 1
    assert "credit_reservation_id" not in retried["job"]
    assert retried["credit_release"]["reservation_transaction_id"] == reservation_id
    assert service.store.get_record("credit_transaction", reservation_id)["status"] == "released"
    released_balance = service.billing_balance({"account_id": "acct_preauth_retry"})["balance"]
    assert released_balance["available_credits"] == 1.0
    assert released_balance["reserved_credits"] == 0.0

    redispatched = service.dispatch_job(job_id, {})
    assert redispatched["credit_reservation"]["status"] == "reserved"
    assert redispatched["credit_reservation"]["credit_transaction_id"] != reservation_id
    redispatched_balance = service.billing_balance({"account_id": "acct_preauth_retry"})["balance"]
    assert redispatched_balance["available_credits"] == 0.82
    assert redispatched_balance["reserved_credits"] == 0.18

def test_provider_payout_lifecycle_lists_settles_and_reconciles_without_custody() -> None:
    service = _service()
    raw_event = {"id": "evt_credit_payout", "type": "checkout.session.completed", "amount": 1.0, "currency": "usd", "metadata": {"account_id": "acct_payout"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_paid_compute_payout"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(job_id, {"account_id": "acct_payout", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"})
    payout_id = str(completed["provider_payout"]["provider_payout_id"])

    accrued = service.billing_provider_payouts({"account_id": "acct_payout", "provider_id": "provider_live_gpu_1", "status": "accrued"})
    before_reconciliation = service.reconciliation({})["reconciliation"]

    assert accrued["summary"]["accrued_total"] == 0.18
    assert accrued["provider_payouts"][0]["provider_payout_id"] == payout_id
    assert before_reconciliation["provider_payout_total"] == 0.18
    assert before_reconciliation["ledger_balanced"] is True
    assert before_reconciliation["ledger_balance_delta"] == 0.0

    reset_default_service(service)
    router = create_default_router()
    try:
        routed_list = router.dispatch("GET", "/billing/provider-payouts", {"account_id": "acct_payout", "status": "accrued"})
        routed_settle = router.dispatch(
            "POST",
            f"/billing/provider-payouts/{payout_id}/settle",
            {"external_payout_reference": "stripe_transfer_test_1", "settled_by": "ops"},
        )
    finally:
        reset_default_service(None)

    assert routed_list["provider_payouts"][0]["provider_payout_id"] == payout_id
    assert routed_settle["provider_payout"]["status"] == "settled"
    assert routed_settle["provider_payout"]["external_disbursement_recorded"] is True
    assert routed_settle["provider_payout"]["funds_moved"] is False
    replayed_settle = service.settle_provider_payout(
        payout_id,
        {"external_payout_reference": "stripe_transfer_test_1", "settled_by": "ops"},
    )
    conflicting_settle = service.settle_provider_payout(
        payout_id,
        {"external_payout_reference": "stripe_transfer_test_2", "settled_by": "ops"},
    )

    assert replayed_settle["ok"] is True
    assert replayed_settle["idempotent_replay"] is True
    assert replayed_settle["provider_payout"]["provider_payout_id"] == payout_id
    assert conflicting_settle["ok"] is False
    assert conflicting_settle["error"]["error_code"] == "billing.provider_payout.settlement_conflict"
    assert conflicting_settle["error"]["details"]["conflicts"]

    settled = service.billing_provider_payouts({"account_id": "acct_payout", "provider_id": "provider_live_gpu_1", "status": "settled"})
    after_reconciliation = service.reconciliation({})["reconciliation"]

    assert settled["summary"]["settled_total"] == 0.18
    assert after_reconciliation["provider_payout_summary"]["settled_count"] == 1
    assert after_reconciliation["ledger_balanced"] is True

    operations: tuple[tuple[Callable[[], Any], str], ...] = (
        (lambda: service.settle_provider_payout(payout_id, {}), "not accrued"),
        (lambda: service.settle_provider_payout("payout_missing", {}), "Unknown provider payout"),
    )
    for operation, expected in operations:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            assert expected in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"invalid payout settlement succeeded: {expected}")


def test_billing_refund_records_no_custody_credit_adjustment_and_reconciliation() -> None:
    service = _service()
    raw_event = {"id": "evt_credit_refund", "type": "checkout.session.completed", "amount": 1.0, "currency": "usd", "metadata": {"account_id": "acct_refund"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_paid_compute_refund"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(job_id, {"account_id": "acct_refund", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"})
    usage_charge_id = str(completed["usage_charge"]["usage_charge_id"])
    payout_id = str(completed["provider_payout"]["provider_payout_id"])

    assert service.billing_balance({"account_id": "acct_refund"})["balance"]["available_credits"] == 0.82
    refund = service.billing_refund({"usage_charge_id": usage_charge_id, "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"})

    assert refund["ok"] is True
    assert refund["refund"]["status"] == "recorded_no_custody"
    assert refund["refund"]["funds_moved"] is False
    assert refund["refund"]["external_refund_created"] is False
    assert refund["credit_transaction"]["transaction_type"] == "refund_credit"
    assert refund["credit_transaction"]["funds_moved"] is False
    assert service.billing_balance({"account_id": "acct_refund"})["balance"]["available_credits"] == 1.0
    assert refund["provider_payout_adjustment"]["adjusted"] is True
    assert refund["provider_payout_adjustment"]["applied_adjustment_amount"] == 0.18
    adjusted_payout = service.store.get_record("provider_payout", payout_id)
    assert adjusted_payout["amount"] == 0.0
    assert adjusted_payout["status"] == "adjusted_no_payout_due"
    assert adjusted_payout["refund_adjustment_amount"] == 0.18

    replay = service.billing_refund({"usage_charge_id": usage_charge_id, "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"})
    assert replay["idempotent_replay"] is True
    assert replay["refund"]["refund_id"] == refund["refund"]["refund_id"]
    assert replay["provider_payout_adjustment"]["reason"] == "already_adjusted"
    idempotency_conflicts = (
        {"usage_charge_id": usage_charge_id, "reason": "different_reason", "idempotency_key": "refund-idempotent-1"},
        {"usage_charge_id": usage_charge_id, "amount": 0.01, "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"},
        {"usage_charge_id": usage_charge_id, "account_id": "acct_other", "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"},
        {"usage_charge_id": usage_charge_id, "provider_id": "provider_other", "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"},
        {"usage_charge_id": usage_charge_id, "source_event_id": "evt_other", "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"},
    )
    for conflict_payload in idempotency_conflicts:
        conflict = service.billing_refund(conflict_payload)
        assert conflict["ok"] is False
        assert conflict["idempotent_replay"] is False
        assert conflict["error"]["error_code"] == "billing.refund.idempotency_conflict"
        assert conflict["error"]["details"]["conflicts"]
    assert service.store.count_records("refund") == 1
    reconciliation = service.reconciliation({})["reconciliation"]
    assert reconciliation["refund_count"] == 1
    assert reconciliation["provider_payout_total"] == 0.0
    assert reconciliation["ledger_balanced"] is True
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]
    assert reputation["refund_count"] == 1
    assert reputation["refund_rate"] == 1.0
    assert reputation["dispute_count"] == 0
    assert reputation["dispute_rate"] == 0.0

    try:
        service.billing_refund({"usage_charge_id": usage_charge_id, "amount": 0.01, "reason": "excess_refund"})
    except ValueError as exc:
        assert "exceeds remaining" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("over-refund was accepted")


def test_provider_reputation_counts_dispute_refunds_and_signals() -> None:
    service = _service()
    account_id = "acct_dispute"
    _credit_account(service, account_id, 1.0, event_id="evt_dispute_credit")

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_dispute_reputation",
                "account_id": account_id,
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    service.dispatch_job(job_id, {})
    completed = service.complete_job(
        job_id,
        {
            "account_id": account_id,
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
        },
    )
    refund = service.billing_refund(
        {
            "usage_charge_id": completed["usage_charge"]["usage_charge_id"],
            "reason": "customer_dispute",
            "idempotency_key": "refund-dispute-idempotent",
        }
    )
    service.store.put_record(
        "provider_fraud_signal",
        "fraud_dispute_signal",
        {
            "fraud_signal_id": "fraud_dispute_signal",
            "provider_id": "provider_live_gpu_1",
            "signal_type": "payment_dispute",
            "severity": "review",
            "status": "open",
            "created_at": "2026-05-26T00:00:00Z",
        },
        provider_id="provider_live_gpu_1",
        status="open",
    )

    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]

    assert refund["refund"]["reason"] == "customer_dispute"
    assert reputation["dispute_count"] == 2
    assert reputation["dispute_refund_count"] == 1
    assert reputation["dispute_signal_count"] == 1
    assert reputation["dispute_rate"] == 1.0
    assert "payment_dispute" in reputation["manual_review_flags"]


def test_billing_ledger_audit_export_readback_verifies_custody_safety(tmp_path: Any) -> None:
    service = _service()
    raw_event = {
        "id": "evt_billing_audit_export",
        "type": "checkout.session.completed",
        "amount": 1.0,
        "currency": "usd",
        "metadata": {"account_id": "acct_billing_audit"},
    }
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(
        service.create_job(
            {
                **_job_payload(),
                "job_id": "job_billing_audit_export",
                "account_id": "acct_billing_audit",
                "estimated_total_cost": 0.18,
                "currency": "USD",
            }
        )["job"]["job_id"]
    )
    dispatched = service.dispatch_job(job_id, {})
    completed = service.complete_job(
        job_id,
        {
            "account_id": "acct_billing_audit",
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
        },
    )
    usage_charge_id = str(completed["usage_charge"]["usage_charge_id"])
    provider_payout_id = str(completed["provider_payout"]["provider_payout_id"])

    refund = service.billing_refund(
        {"usage_charge_id": usage_charge_id, "amount": 0.05, "reason": "sla_credit", "idempotency_key": "refund-billing-audit"}
    )
    settled = service.settle_provider_payout(
        provider_payout_id,
        {"external_payout_reference": "ops-ledger-audit-1", "settled_by": "ops"},
    )
    export_path = tmp_path / "billing-audit.ndjson"

    exported = service.audit_export({"out": str(export_path), "chain_id": "all"})
    verified = service.audit_verify_export({"path": str(export_path)})
    exported_events = audit_events_from_export_file(export_path)
    chain = verify_exported_chain(exported_events)
    actions = {str(event.get("action", "")) for event in exported_events}
    billing_events = tuple(event for event in exported_events if str(event.get("action", "")).startswith("billing."))

    assert dispatched["credit_reservation"]["status"] == "reserved"
    assert completed["credit_debit"]["status"] == "posted"
    assert completed["provider_payout"]["funds_moved"] is False
    assert refund["refund"]["funds_moved"] is False
    assert settled["provider_payout"]["funds_moved"] is False
    assert exported["ok"] is True
    assert exported["manifest_hash"]
    assert exported["checkpoint"]["checkpoint_hash"]
    assert exported["checkpoint_record"]["manifest_hash"] == exported["manifest_hash"]
    assert verified["ok"] is True
    assert verified["checkpoint_hash"] == exported["checkpoint"]["checkpoint_hash"]
    assert chain["ok"] is True
    assert chain["event_count"] == exported["event_count"]
    assert {
        "billing.credit.added",
        "billing.webhook.received",
        "billing.usage.debited",
        "billing.provider_payout.accrued",
        "billing.refund.recorded",
        "billing.provider_payout.adjusted_for_refund",
        "billing.provider_payout.settled",
    }.issubset(actions)
    assert billing_events
    assert all(event["funds_moved"] is False for event in billing_events)
    assert all(event["broadcast_allowed"] is False for event in billing_events)
    assert all(event["private_key_required"] is False for event in billing_events)
    assert all(event["dry_run_only"] is True for event in billing_events)

def test_billing_refund_rejects_invalid_or_unowned_requests() -> None:
    service = _service()

    for payload, expected in (
        ({"account_id": "acct_refund_invalid", "amount": 0}, "amount must be positive"),
        ({"amount": 1}, "account_id or tenant_id is required"),
        ({"account_id": "acct_refund_invalid", "usage_charge_id": "usage_missing", "amount": 1}, "Unknown usage charge"),
    ):
        try:
            service.billing_refund(payload)
        except ValueError as exc:
            assert expected in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"invalid refund payload was accepted: {payload}")



def test_prepaid_credit_debit_insufficient_balance_does_not_overdraw() -> None:
    service = _service()
    raw_event = {"id": "evt_credit_tiny", "type": "checkout.session.completed", "amount": 0.1, "currency": "usd", "metadata": {"account_id": "acct_tiny"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})

    job_id = str(service.create_job({**_job_payload(), "job_id": "job_paid_compute_insufficient"})["job"]["job_id"])
    service.dispatch_job(job_id, {})
    completed = service.complete_job(job_id, {"account_id": "acct_tiny", "actual_units": 2, "actual_total_cost": 0.18, "currency": "USD"})

    assert completed["credit_debit"]["status"] == "insufficient_credit"
    assert completed["provider_payout"] == {}
    assert service.store.count_records("provider_payout") == 0
    assert service.billing_balance({"account_id": "acct_tiny"})["balance"]["available_credits"] == 0.1
    assert (
        _metric_total(
            service,
            "billing_insufficient_credit_total",
            {"provider_id": "provider_live_gpu_1"},
        )
        == 0.18
    )


def test_intelligence_tier_reasoning_budget_serialization() -> None:
    budget = ReasoningBudget(reasoning_level="high", max_reasoning_steps=32, max_tool_calls=12)
    profile = TaskEconomicProfile(
        task_id="compute_task_research",
        task_description="research competitor repo",
        agent_id="agent_researcher",
        goal_id="goal_architecture",
        intelligence_tier=IntelligenceTier.DEEP_REASONING.value,
        reasoning_level="high",
        reasoning_budget=budget.as_record(),
    )

    record = profile.as_record()
    assert record["intelligence_tier"] == "deep_reasoning"
    assert record["reasoning_budget"]["max_reasoning_steps"] == 32
    assert budget.as_record()["max_tool_calls"] == 12

def test_provider_class_registry_and_intelligence_filtering() -> None:
    from flow_memory.compute_market.registry import default_compute_routes, metadata_registry

    routes = {route.route_id: route for route in default_compute_routes()}
    classes = {record["provider_class"] for record in metadata_registry()["provider_classes"]}
    service = _service()

    assert routes["gpu-minute-route"].provider_class == ProviderClass.GPU_CLUSTER.value
    assert routes["reserved-slot-route"].provider_class == ProviderClass.RESERVED_CAPACITY_POOL.value
    assert ProviderClass.REASONING_MODEL.value in classes

    result = service.intelligence_plan(
        {
            "task": "background agent research run",
            "agent_id": "agent_provider_class",
            "estimated_value": 50.0,
            "budget": 5.0,
            "allow_background": True,
        }
    )
    plan = result["intelligence_plan"]
    selected_route = plan["compute_plan"]["selected_route"]
    assert ProviderClass.GPU_CLUSTER.value in plan["recommended_provider_classes"]
    assert selected_route["provider_class"] in plan["recommended_provider_classes"]
    assert selected_route["route_id"] == "gpu-minute-route"

    application = _provider_application()
    application["provider_class"] = ProviderClass.REASONING_MODEL.value
    applied = service.apply_market_provider(application)
    assert applied["provider_application"]["provider_class"] == ProviderClass.REASONING_MODEL.value
    verified = service.verify_market_provider("provider_live_gpu_1", {})
    assert verified["provider"]["provider_class"] == ProviderClass.REASONING_MODEL.value

    invalid = dict(application, provider_id="provider_bad_class", provider_class="unsupported_class")
    try:
        service.apply_market_provider(invalid)
    except ValueError as exc:
        assert "unsupported provider_class" in str(exc)
    else:
        raise AssertionError("unsupported provider class must be rejected")


def test_intelligence_plan_run_now_and_usage_ledger() -> None:
    service = _service()

    result = service.intelligence_plan(
        {
            "task": "research competitor repo and produce architecture plan",
            "agent_id": "agent_researcher",
            "goal_id": "goal_architecture",
            "estimated_value": 50.0,
            "budget": 5.0,
            "allow_background": True,
            "dry_run": True,
        }
    )

    plan = result["intelligence_plan"]
    usage = result["usage_record"]
    assert result["ok"] is True
    assert plan["recommended_intelligence_tier"] == "background_agent"
    assert plan["recommended_reasoning_budget"]["reasoning_level"] == "high"
    assert plan["run_decision"] == RunDecision.RUN_NOW.value
    assert usage["agent_id"] == "agent_researcher"
    assert usage["intelligence_tier"] == "background_agent"
    assert usage["actual_cost"] is None
    assert result["funds_moved"] is False
    assert result["broadcast_allowed"] is False
    assert result["private_key_required"] is False

    ledger = service.compute_usage_by_agent("agent_researcher")
    assert tuple(record["usage_record_id"] for record in ledger["usage_records"]) == (usage["usage_record_id"],)


def test_intelligence_plan_run_decision_variants() -> None:
    service = _service()
    direct = {"provider_constraints": ("direct-request-provider",), "estimated_units": {"request": 1}}

    negative_roi = service.intelligence_plan({**direct, "task": "direct paid request", "estimated_value": 0.001, "budget": 1.0})
    assert negative_roi["intelligence_plan"]["run_decision"] == RunDecision.REJECT_NEGATIVE_ROI.value

    approval = service.intelligence_plan({**direct, "task": "direct approval request", "estimated_value": 10.0, "budget": 1.0, "require_human_approval_above": 0.01})
    assert approval["intelligence_plan"]["run_decision"] == RunDecision.REQUIRE_HUMAN_APPROVAL.value

    downgrade = service.intelligence_plan(
        {
            **direct,
            "task": "deep but too cheap",
            "intelligence_tier": "deep_reasoning",
            "estimated_value": 10.0,
            "budget": 0.001,
        }
    )
    assert downgrade["intelligence_plan"]["run_decision"] == RunDecision.DOWNGRADE_TIER.value

    reserved = service.intelligence_plan(
        {
            "task": "reserve capacity for long background run",
            "intelligence_tier": "reserved_capacity",
            "provider_constraints": ("reserved-capacity-provider",),
            "allow_reserved_capacity": True,
            "estimated_value": 100.0,
            "budget": 10.0,
            "human_approval_granted": True,
        }
    )
    assert reserved["intelligence_plan"]["run_decision"] == RunDecision.RESERVE_CAPACITY.value
    assert reserved["intelligence_plan"]["reserve_capacity_recommended"] is True

    for index in range(5):
        service.store.put_record(
            "compute_price_snapshot",
            f"direct_low_{index}",
            {
                "price_snapshot_id": f"direct_low_{index}",
                "provider_id": "direct-request-provider",
                "route_id": "direct-request-route",
                "unit_type": "request",
                "unit_price": 0.001,
                "payment_asset": "USD",
                "network": "offchain",
                "created_at": f"2026-05-24T00:00:0{index}Z",
            },
            provider_id="direct-request-provider",
            route_id="direct-request-route",
            task_type="request",
        )
    defer = service.intelligence_plan(
        {
            **direct,
            "task": "defer direct request until cheaper",
            "estimated_value": 10.0,
            "budget": 1.0,
            "urgency": {"defer_allowed": True},
        }
    )
    assert defer["intelligence_plan"]["run_decision"] == RunDecision.DEFER_UNTIL_CHEAPER.value
    assert defer["intelligence_plan"]["defer_until"]


def test_compute_price_history_anomalies_forecast_and_usage_statement() -> None:
    service = _service()
    for snapshot_id, price in (("price_base_1", 0.09), ("price_base_2", 0.09), ("price_spike", 0.9)):
        service.store.put_record(
            "compute_price_snapshot",
            snapshot_id,
            {
                "price_snapshot_id": snapshot_id,
                "provider_id": "gpu-time-provider",
                "route_id": "gpu-minute-route",
                "unit_type": "gpu_minute",
                "unit_price": price,
                "payment_asset": "USDC",
                "network": "solana",
                "created_at": "2026-05-24T00:00:00Z",
            },
            provider_id="gpu-time-provider",
            route_id="gpu-minute-route",
            task_type="gpu_minute",
        )

    history = service.compute_price_history({"provider_id": "gpu-time-provider", "route_id": "gpu-minute-route", "unit_type": "gpu_minute"})
    prices = service.compute_prices({"provider_id": "gpu-time-provider", "route_id": "gpu-minute-route", "unit_type": "gpu_minute"})
    anomalies = service.compute_price_anomalies({"provider_id": "gpu-time-provider", "route_id": "gpu-minute-route", "unit_type": "gpu_minute"})
    forecast = service.compute_price_forecast({"provider_id": "gpu-time-provider", "route_id": "gpu-minute-route", "unit_type": "gpu_minute"})

    assert tuple(record["price_snapshot_id"] for record in history["price_history"]) == ("price_base_1", "price_base_2", "price_spike")
    assert prices["prices"][0]["median_unit_price"] == 0.09
    assert anomalies["anomaly_count"] == 1
    assert anomalies["price_anomalies"][0]["direction"] == "above_median"
    assert forecast["price_forecast"]["forecast_unit_price"] == 0.09

    service.intelligence_plan({"task": "standard usage statement", "workspace_id": "workspace_utility", "agent_id": "agent_utility", "goal_id": "goal_utility", "estimated_value": 5.0, "budget": 1.0})
    usage = service.compute_usage({"workspace_id": "workspace_utility"})
    statement = service.compute_usage_statement({"workspace_id": "workspace_utility", "period": "2026-05"})

    assert usage["summary"]["record_count"] == 1
    assert statement["statement"]["workspace_id"] == "workspace_utility"
    assert statement["statement"]["record_count"] == 1

def test_marketplace_api_routes_and_scopes() -> None:
    reset_default_service(_service())
    router = create_default_router()
    try:
        assert required_scopes_for("POST", "/compute/jobs") == ("compute:execute",)
        assert required_scopes_for("GET", "/compute/jobs") == ("compute:read",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/dispatch") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/complete") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/claim") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/expire-leases") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/heartbeat") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/release-claim") == ("compute:execute",)
        assert required_scopes_for("POST", "/billing/checkout") == ("compute:billing",)
        assert required_scopes_for("GET", "/billing/quota") == ("compute:billing",)
        assert required_scopes_for("POST", "/billing/quota") == ("compute:billing",)
        assert required_scopes_for("POST", "/billing/refund") == ("compute:billing",)
        assert required_scopes_for("GET", "/billing/provider-payouts") == ("compute:billing",)
        assert required_scopes_for("POST", "/billing/provider-payouts/payout_1/settle") == ("compute:billing",)
        assert required_scopes_for("POST", "/admin/providers/provider_admin_api/approve") == ("compute:admin",)
        assert required_scopes_for("POST", "/admin/providers/provider_admin_api/suspend") == ("compute:admin",)
        assert required_scopes_for("POST", "/admin/routes/route_live_gpu_1/disable") == ("compute:admin",)
        assert required_scopes_for("POST", "/admin/policies/policy_admin/publish") == ("compute:admin",)
        assert required_scopes_for("POST", "/market/providers/apply") == ("compute:provider-admin",)
        assert required_scopes_for("POST", "/market/providers/provider_live_gpu_1/conformance") == ("compute:provider-admin",)
        assert required_scopes_for("POST", "/market/providers/provider_live_gpu_1/reject") == ("compute:provider-admin",)
        assert required_scopes_for("POST", "/market/providers/provider_live_gpu_1/request-revision") == ("compute:provider-admin",)
        assert required_scopes_for("GET", "/market/prices") == ("compute:read",)
        assert required_scopes_for("POST", "/compute/intelligence-plan") == ("compute:plan",)
        assert required_scopes_for("GET", "/compute/prices") == ("compute:read",)
        assert required_scopes_for("POST", "/compute/prices/forecast") == ("compute:read",)
        assert required_scopes_for("GET", "/compute/usage") == ("compute:read",)

        applied = router.dispatch("POST", "/market/providers/apply", _provider_application())
        assert applied["ok"] is True
        verified = router.dispatch("POST", "/market/providers/provider_live_gpu_1/verify", {})
        assert verified["provider"]["verified"] is True
        fetched = router.dispatch("GET", "/market/providers/provider_live_gpu_1")
        assert fetched["provider"]["provider_id"] == "provider_live_gpu_1"
        router.dispatch(
            "POST",
            "/market/providers/apply",
            {**_provider_application(), "provider_id": "provider_review_api", "provider_name": "Review API Provider", "request_id": "api-review-v1"},
        )
        revision = router.dispatch(
            "POST",
            "/market/providers/provider_review_api/request-revision",
            {"revision_notes": "Need updated compliance package."},
        )
        router.dispatch(
            "POST",
            "/market/providers/apply",
            {**_provider_application(), "provider_id": "provider_review_api", "provider_name": "Review API Provider Revised", "request_id": "api-review-v2"},
        )
        rejected = router.dispatch(
            "POST",
            "/market/providers/provider_review_api/reject",
            {"rejection_reason": "Compliance package rejected."},
        )
        job = router.dispatch("POST", "/compute/jobs", _job_payload())
        job_id = str(job["job"]["job_id"])
        claimed = router.dispatch("POST", "/compute/jobs/claim", {"worker_id": "worker_api"})
        dispatched = router.dispatch("POST", f"/compute/jobs/{job_id}/dispatch", {"worker_id": "worker_api"})
        completed = router.dispatch("POST", f"/compute/jobs/{job_id}/complete", {"actual_total_cost": 0.12, "worker_id": "worker_api"})
        expired_leases = router.dispatch("POST", "/compute/jobs/expire-leases", {})
        telemetry = router.dispatch("GET", "/compute/telemetry")
        jobs = router.dispatch("GET", "/compute/jobs", {"status": "succeeded"})
        intelligence = router.dispatch("POST", "/compute/intelligence-plan", {"task": "research route api", "agent_id": "agent_api", "estimated_value": 5.0, "budget": 1.0})
        price_index = router.dispatch("GET", "/compute/prices")
        price_history = router.dispatch("GET", "/compute/prices/history")
        price_forecast = router.dispatch("POST", "/compute/prices/forecast", {})
        usage = router.dispatch("GET", "/compute/usage/by-agent/agent_api")
        statement = router.dispatch("GET", "/compute/usage/statement")
        quota_set = router.dispatch(
            "POST",
            "/billing/quota",
            {"account_id": "acct_api_quota", "daily_spend_limit": 0.5, "monthly_spend_limit": 5.0},
        )
        quota_get = router.dispatch("GET", "/billing/quota", {"account_id": "acct_api_quota"})
        router.dispatch(
            "POST",
            "/market/providers/apply",
            {**_provider_application(), "provider_id": "provider_admin_api", "provider_name": "Admin API Provider", "request_id": "admin-api-v1"},
        )
        admin_approved = router.dispatch("POST", "/admin/providers/provider_admin_api/approve", {"verification_notes": "approved by admin API"})
        admin_route_id = str(admin_approved["routes"][0]["route_id"])
        admin_route_disabled = router.dispatch("POST", f"/admin/routes/{admin_route_id}/disable", {"reason": "maintenance"})
        admin_suspended = router.dispatch("POST", "/admin/providers/provider_admin_api/suspend", {"reason": "operator review"})
        policy = router.dispatch("POST", "/compute/policies", {"policy_id": "policy_admin_publish", "max_total_cost": 1.0, "dry_run_required": True})
        published_policy = router.dispatch("POST", "/admin/policies/policy_admin_publish/publish", {"published_by": "ops"})
        assert dispatched["job"]["status"] == "running"
        assert claimed["job"]["status"] == "dispatched"
        assert completed["job"]["status"] == "succeeded"
        assert expired_leases["expired_count"] == 0
        assert revision["provider_application"]["status"] == "revision_requested"
        assert rejected["provider_application"]["status"] == "rejected"
        assert tuple(str(item["job_id"]) for item in jobs["jobs"]) == (job_id,)
        assert telemetry["summary"]["metric_sample_count"] >= 1
        assert intelligence["intelligence_plan"]["recommended_intelligence_tier"]
        assert price_index["ok"] is True
        assert price_history["ok"] is True
        assert price_forecast["ok"] is True
        assert tuple(record["agent_id"] for record in usage["usage_records"]) == ("agent_api",)
        assert statement["statement"]["record_count"] >= 1
        assert quota_set["quota"]["daily_spend_limit"] == 0.5
        assert quota_get["quota"]["monthly_spend_limit"] == 5.0
        assert admin_approved["provider_application"]["status"] == "verified"
        assert admin_route_disabled["route"]["enabled"] is False
        assert admin_suspended["provider_application"]["status"] == "suspended"
        assert admin_suspended["provider"]["status"] == "suspended"
        assert policy["policy"]["policy_id"] == "policy_admin_publish"
        assert published_policy["policy"]["status"] == "published"
    finally:
        reset_default_service(None)
