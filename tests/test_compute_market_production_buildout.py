from __future__ import annotations

import hmac

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.asymmetric import LocalTestSigner


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
    assert service.job_artifacts(job_id)["artifacts"]
    assert service.billing_usage({})["usage_charges"]
    assert any(event["event_type"] == "job.completed" for event in service.job_events(job_id)["events"])


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
    job_id = str(service.create_job(_job_payload())["job"]["job_id"])

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

    raw_event = {"id": "evt_1", "type": "checkout.session.completed", "amount_total": 10000, "currency": "usd", "metadata": {"account_id": "acct_1"}}
    secret = "whsec_test_secret"
    signature = hmac.new(secret.encode("utf-8"), content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    webhook = service.billing_webhook_stripe({"raw_event": raw_event, "webhook_secret": secret, "stripe_signature": signature})
    assert webhook["ok"] is True
    assert webhook["payment_event"]["verified"] is True
    assert webhook["credit_transaction"]["amount"] == 100.0
    assert service.billing_balance({"account_id": "acct_1"})["balance"]["available_credits"] == 100.0


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
