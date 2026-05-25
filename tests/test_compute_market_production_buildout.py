from __future__ import annotations

import hmac

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.hashes import content_hash


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



def test_quote_broker_validates_replay_cache_and_drift() -> None:
    service = _service()

    accepted = service.broker_quote({"quote": _quote(), "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    assert accepted["ok"] is True
    assert accepted["quote"]["source"] == "live_provider"
    assert service.store.count_records("quote_replay_guard") == 1
    assert service.store.count_records("quote_cache_entry") == 1

    replay = service.broker_quote({"quote": {**_quote(), "estimated_total_cost": 0.27}})
    assert replay["ok"] is False
    assert replay["error"]["error_code"] == "quote.replay_detected"

    drifted = service.broker_quote({"quote": {**_quote(0.27), "quote_id": "quote_live_gpu_2"}})
    assert drifted["ok"] is True
    assert drifted["drift"]["status"] in {"observed", "review"}


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
    assert held["reservation"]["status"] == "held"
    assert service.capacity_order_book({"provider_id": "provider_live_gpu_1"})["summary"]["held_capacity_units"] == 4

    try:
        service.reserve_capacity({"provider_id": "provider_live_gpu_1", "route_id": "route_live_gpu_1", "capacity_units": 7})
    except ValueError as exc:
        assert "exceeds available" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("overbooked capacity was accepted")

    released = service.release_capacity({"reservation_id": held["reservation"]["reservation_id"]})
    assert released["reservation"]["status"] == "released"


def test_compute_job_lifecycle_is_dry_run_safe_and_audited() -> None:
    service = _service()
    created = service.create_job(
        {
            "task_type": "inference",
            "input_ref": "s3://flow-memory-inputs/job-1.json",
            "model_or_runtime": "llama-runtime",
            "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
            "budget_policy_id": "policy_default",
            "route_id": "route_live_gpu_1",
            "provider_id": "provider_live_gpu_1",
        }
    )
    job_id = created["job"]["job_id"]
    assert created["job"]["dry_run_only"] is True
    assert created["job"]["funds_moved"] is False

    retried = service.retry_job(job_id, {})
    assert retried["job"]["attempt"] == 1
    cancelled = service.cancel_job(job_id, {"reason": "operator test"})
    assert cancelled["job"]["status"] == "cancelled"
    assert service.job_events(job_id)["events"]


def test_billing_ledger_requires_external_checkout_and_verifies_webhook_signature() -> None:
    service = _service()
    checkout = service.billing_checkout({"account_id": "acct_1", "amount": 100, "currency": "USD"})
    assert checkout["ok"] is False
    assert checkout["checkout"]["funds_moved"] is False
    assert checkout["checkout"]["status"] == "requires_external_checkout_provider"

    raw_event = {"id": "evt_1", "type": "checkout.session.completed", "amount_total": 10000}
    secret = "whsec_test"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    assert webhook["ok"] is True
    assert webhook["payment_event"]["verified"] is True
    assert service.billing_balance({"account_id": "acct_1"})["balance"]["available_credits"] == 0.0


def test_marketplace_api_routes_and_scopes() -> None:
    reset_default_service(_service())
    router = create_default_router()
    try:
        assert required_scopes_for("POST", "/compute/jobs") == ("compute:execute",)
        assert required_scopes_for("POST", "/billing/checkout") == ("compute:billing",)
        assert required_scopes_for("POST", "/market/providers/apply") == ("compute:provider-admin",)
        assert required_scopes_for("GET", "/market/prices") == ("compute:read",)

        applied = router.dispatch("POST", "/market/providers/apply", _provider_application())
        assert applied["ok"] is True
        verified = router.dispatch("POST", "/market/providers/provider_live_gpu_1/verify", {})
        assert verified["provider"]["verified"] is True
        fetched = router.dispatch("GET", "/market/providers/provider_live_gpu_1")
        assert fetched["provider"]["provider_id"] == "provider_live_gpu_1"
    finally:
        reset_default_service(None)
