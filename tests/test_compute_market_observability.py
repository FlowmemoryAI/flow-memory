from __future__ import annotations

import json
from pathlib import Path


from flow_memory.api.router import create_default_router
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.observability import AlertEvaluator, ComputeMarketTelemetry, MetricSample, TraceSpanRecord, metric_names, span_names
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import ComputeMarketStore


def _service() -> ComputeMarketService:
    return ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test", rate_limits_enabled=False),
    )


def test_metric_and_trace_records_serialize() -> None:
    assert MetricSample("compute_plan_requests_total", 2, {"route": "a"}).as_record() == {
        "name": "compute_plan_requests_total",
        "value": 2,
        "labels": {"route": "a"},
    }
    assert TraceSpanRecord("compute.plan_request", 1.23456, {"request_id": "req"}).as_record() == {
        "name": "compute.plan_request",
        "latency_ms": 1.235,
        "attributes": {"request_id": "req"},
    }


def test_telemetry_snapshot_reset_and_prometheus_text() -> None:
    telemetry = ComputeMarketTelemetry()
    telemetry.increment("compute_plan_requests_total", {"strategy": "balanced"})
    with telemetry.span("compute.plan_request", {"request_id": "req_1"}):
        pass

    snapshot = telemetry.snapshot(reset=False)
    assert len(snapshot["metrics"]) == 1
    assert len(snapshot["traces"]) == 1
    text = telemetry.prometheus_text()
    assert "# TYPE compute_plan_requests_total gauge" in text
    assert 'strategy="balanced"' in text

    drained = telemetry.snapshot(reset=True)
    assert len(drained["metrics"]) == 1
    assert telemetry.summary()["metric_sample_count"] == 0


def test_metric_and_span_catalogs_include_production_backlog_names() -> None:
    names = set(metric_names())
    assert "compute_job_completed_total" in names
    assert "billing_debit_total" in names
    assert "audit_chain_verify_fail_total" in names
    assert "billing_webhook_failures_total" in names
    assert "provider_execution_failure_total" in names
    assert "redis_unavailable_total" in names
    assert "external_provider_allowlist_missing_total" in names
    assert "compute_provider_receipt_accepted_total" in names
    assert "compute_provider_receipt_rejected_total" in names
    assert "capacity_hold_expired_total" in names
    assert "quote_cache_invalidated_total" in names
    assert "capacity_confirmed_total" in names
    assert "capacity_auction_cleared_total" in names
    assert "compute.provider_discovery" in set(span_names())


def test_alert_evaluator_fires_on_audit_failures_and_acknowledges_route() -> None:
    service = _service()
    reset_default_service(service)
    router = create_default_router()
    try:
        service.telemetry.increment("audit_chain_verify_fail_total")
        evaluation = AlertEvaluator().evaluate(service.telemetry).as_record()
        alerts = router.dispatch("GET", "/compute/alerts")
        ack = router.dispatch("POST", "/compute/alerts/audit-chain-verify-failure/ack", {"acknowledged_by": "test"})
        acknowledged = router.dispatch("GET", "/compute/alerts")
    finally:
        reset_default_service(None)

    assert evaluation["ok"] is False
    assert evaluation["firing"][0]["rule_name"] == "audit-chain-verify-failure"
    assert alerts["alerts"]["firing_count"] == 1
    assert ack["ok"] is True
    assert acknowledged["alerts"]["firing"][0]["acknowledged"] is True


def test_billing_webhook_failure_and_readiness_failures_emit_alert_metrics() -> None:
    service = _service()
    webhook = service.billing_webhook_stripe(
        {
            "raw_event": {
                "id": "evt_bad_signature",
                "type": "checkout.session.completed",
                "amount": 100,
                "currency": "usd",
                "metadata": {"account_id": "acct_bad"},
            },
            "webhook_secret": "whsec_test_secret",
            "stripe_signature": "not-valid",
        }
    )
    assert webhook["ok"] is False

    allowlist_service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limits_enabled=False,
            external_provider_quotes_enabled=True,
        ),
    )
    readiness = allowlist_service.readiness()

    assert "external_provider_allowlist_missing" in readiness["readiness_failures"]
    assert service.telemetry.summary()["metric_totals"]["billing_webhook_failures_total"] == 1.0
    assert allowlist_service.telemetry.summary()["metric_totals"]["external_provider_allowlist_missing_total"] == 1.0

    service.telemetry.increment("redis_unavailable_total")
    alerts = AlertEvaluator().evaluate(service.telemetry).as_record()
    rule_names = {item["rule_name"] for item in alerts["firing"]}
    assert "billing-webhook-failures" in rule_names
    assert "redis-unavailable" in rule_names

def test_compute_telemetry_and_metrics_routes_expose_service_samples() -> None:
    service = _service()
    reset_default_service(service)
    router = create_default_router()
    try:
        service.telemetry.increment("compute_plan_requests_total", {"strategy": "test"})
        telemetry = router.dispatch("GET", "/compute/telemetry")
        metrics = router.dispatch("GET", "/compute/metrics")
        assert telemetry["ok"] is True
        assert telemetry["summary"]["metric_sample_count"] == 1
        assert "compute_plan_requests_total" in metrics["metrics"]
    finally:
        reset_default_service(None)


def test_grafana_dashboard_covers_compute_market_production_metrics() -> None:
    dashboard_path = Path("deployments/compute-market/grafana-dashboard.json")
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    panels = dashboard["panels"]
    expressions = "\n".join(
        target["expr"]
        for panel in panels
        for target in panel.get("targets", ())
        if isinstance(target, dict)
    )

    required_metrics = {
        "compute_plan_requests_total",
        "route_selected_total",
        "policy_denied_total",
        "compute_job_started_total",
        "compute_job_completed_total",
        "compute_job_failed_total",
        "provider_quote_latency_ms",
        "provider_quote_failure_total",
        "provider_circuit_open_total",
        "quote_stale_total",
        "capacity_reserved_total",
        "capacity_confirmed_total",
        "capacity_auction_cleared_total",
        "quote_cache_invalidated_total",
        "capacity_released_total",
        "capacity_hold_expired_total",
        "billing_debit_total",
        "billing_payment_failed_total",
        "billing_webhook_failures_total",
        "audit_chain_verify_fail_total",
        "settlement_attempt_total",
        "unexpected_live_settlement_config_total",
        "redis_unavailable_total",
        "postgres_unavailable_total",
        "external_provider_allowlist_missing_total",
    }

    assert dashboard["uid"] == "flow-memory-compute-market-prod"
    assert len(panels) >= 8
    for metric in required_metrics:
        assert metric in expressions
