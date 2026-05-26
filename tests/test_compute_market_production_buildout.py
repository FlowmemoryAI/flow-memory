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
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
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

    verified = service.verify_market_provider("provider_live_gpu_1", {"verification_notes": "contract reviewed"})
    assert verified["ok"] is True
    assert verified["provider"]["verified"] is True
    assert verified["provider"]["dry_run_only"] is True

    fetched = service.market_provider("provider_live_gpu_1")
    assert fetched["provider_application"]["status"] == "verified"
    assert fetched["reputation"]["provider_id"] == "provider_live_gpu_1"


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


def test_provider_conformance_and_quote_ingest_verify_signed_quotes() -> None:
    signer = LocalTestSigner("provider_live_gpu_1_key", "provider-live-gpu-1-seed")
    service = _service()
    application = _provider_application()
    application["public_key"] = signer.public_record().public_key
    service.apply_market_provider(application)
    service.verify_market_provider("provider_live_gpu_1", {})

    unsigned_quote = _quote()
    signed_quote = {**unsigned_quote, "signature": signer.sign(unsigned_quote).as_record()}
    conformance = service.provider_conformance(
        "provider_live_gpu_1",
        {
            "sample_quote": signed_quote,
            "public_key": signer.public_record().as_record(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        },
    )
    ingested = service.broker_quote(
        {
            "quote": signed_quote,
            "public_key": signer.public_record().as_record(),
            "allowed_assets": ["USDC"],
            "allowed_networks": ["solana"],
        }
    )

    assert conformance["ok"] is True
    assert conformance["signed_quote_valid"] is True
    assert ingested["ok"] is True
    assert ingested["quote"]["signed_quote_valid"] is True


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

    try:
        service.confirm_capacity({"reservation_id": reservation_id})
    except ValueError as exc:
        assert "expected held" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("confirmed reservation was confirmed twice")

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
    assert service.release_capacity({"reservation_id": held["reservation"]["reservation_id"]})["ok"] is True


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

    assert completed["job"]["status"] == "succeeded"
    assert completed["artifact"]["artifact_ref"] == "s3://flow-memory-results/job-1.json"
    assert completed["usage_charge"]["amount"] == 0.18
    assert completed["usage_charge"]["funds_moved"] is False
    assert completed["credit_debit"] == {}
    assert completed["provider_payout"] == {}
    assert service.job_artifacts(job_id)["artifacts"]
    assert service.store.count_records("usage_charge") == 1
    assert any(event["event_type"] == "job.completed" for event in service.job_events(job_id)["events"])


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


def test_billing_ledger_requires_external_checkout_and_verifies_webhook_signature() -> None:
    service = _service()
    checkout = service.billing_checkout({"account_id": "acct_1", "amount": 100, "currency": "USD"})
    assert checkout["ok"] is False
    assert checkout["checkout"]["funds_moved"] is False
    assert checkout["checkout"]["status"] == "requires_external_checkout_provider"

    raw_event = {"id": "evt_1", "type": "checkout.session.completed", "amount_total": 10000, "currency": "usd", "metadata": {"account_id": "acct_1"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    assert webhook["ok"] is True
    assert webhook["payment_event"]["verified"] is True
    assert webhook["credit_transaction"]["amount"] == 100.0
    assert service.billing_balance({"account_id": "acct_1"})["balance"]["available_credits"] == 100.0


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
    assert service.billing_balance({"account_id": "acct_paid"})["balance"]["available_credits"] == 0.82


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

    assert service.billing_balance({"account_id": "acct_refund"})["balance"]["available_credits"] == 0.82
    refund = service.billing_refund({"usage_charge_id": usage_charge_id, "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"})

    assert refund["ok"] is True
    assert refund["refund"]["status"] == "recorded_no_custody"
    assert refund["refund"]["funds_moved"] is False
    assert refund["refund"]["external_refund_created"] is False
    assert refund["credit_transaction"]["transaction_type"] == "refund_credit"
    assert refund["credit_transaction"]["funds_moved"] is False
    assert service.billing_balance({"account_id": "acct_refund"})["balance"]["available_credits"] == 1.0

    replay = service.billing_refund({"usage_charge_id": usage_charge_id, "reason": "sla_credit", "idempotency_key": "refund-idempotent-1"})
    assert replay["idempotent_replay"] is True
    assert replay["refund"]["refund_id"] == refund["refund"]["refund_id"]
    assert service.store.count_records("refund") == 1
    assert service.reconciliation({})["reconciliation"]["refund_count"] == 1
    reputation = service.provider_reputation("provider_live_gpu_1")["reputation"]
    assert reputation["refund_count"] == 1
    assert reputation["refund_rate"] == 1.0

    try:
        service.billing_refund({"usage_charge_id": usage_charge_id, "amount": 0.01, "reason": "excess_refund"})
    except ValueError as exc:
        assert "exceeds remaining" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("over-refund was accepted")


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
    assert completed["provider_payout"]["status"] == "accrued"
    assert service.billing_balance({"account_id": "acct_tiny"})["balance"]["available_credits"] == 0.1
    assert (
        _metric_total(
            service,
            "billing_insufficient_credit_total",
            {"provider_id": "provider_live_gpu_1"},
        )
        == 0.18
    )


def test_marketplace_api_routes_and_scopes() -> None:
    reset_default_service(_service())
    router = create_default_router()
    try:
        assert required_scopes_for("POST", "/compute/jobs") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/dispatch") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/complete") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/claim") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/heartbeat") == ("compute:execute",)
        assert required_scopes_for("POST", "/compute/jobs/job_1/release-claim") == ("compute:execute",)
        assert required_scopes_for("POST", "/billing/checkout") == ("compute:billing",)
        assert required_scopes_for("POST", "/billing/refund") == ("compute:billing",)
        assert required_scopes_for("GET", "/billing/provider-payouts") == ("compute:billing",)
        assert required_scopes_for("POST", "/billing/provider-payouts/payout_1/settle") == ("compute:billing",)
        assert required_scopes_for("POST", "/market/providers/apply") == ("compute:provider-admin",)
        assert required_scopes_for("POST", "/market/providers/provider_live_gpu_1/conformance") == ("compute:provider-admin",)
        assert required_scopes_for("GET", "/market/prices") == ("compute:read",)

        applied = router.dispatch("POST", "/market/providers/apply", _provider_application())
        assert applied["ok"] is True
        verified = router.dispatch("POST", "/market/providers/provider_live_gpu_1/verify", {})
        assert verified["provider"]["verified"] is True
        fetched = router.dispatch("GET", "/market/providers/provider_live_gpu_1")
        assert fetched["provider"]["provider_id"] == "provider_live_gpu_1"
        job = router.dispatch("POST", "/compute/jobs", _job_payload())
        job_id = str(job["job"]["job_id"])
        claimed = router.dispatch("POST", "/compute/jobs/claim", {"worker_id": "worker_api"})
        dispatched = router.dispatch("POST", f"/compute/jobs/{job_id}/dispatch", {"worker_id": "worker_api"})
        completed = router.dispatch("POST", f"/compute/jobs/{job_id}/complete", {"actual_total_cost": 0.12, "worker_id": "worker_api"})
        telemetry = router.dispatch("GET", "/compute/telemetry")
        assert dispatched["job"]["status"] == "running"
        assert claimed["job"]["status"] == "dispatched"
        assert completed["job"]["status"] == "succeeded"
        assert telemetry["summary"]["metric_sample_count"] >= 1
    finally:
        reset_default_service(None)
