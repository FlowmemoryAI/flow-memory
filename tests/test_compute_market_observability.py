from __future__ import annotations

from flow_memory.api.router import create_default_router
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.observability import ComputeMarketTelemetry, MetricSample, TraceSpanRecord, metric_names, span_names
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
    assert "compute.provider_discovery" in set(span_names())


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
