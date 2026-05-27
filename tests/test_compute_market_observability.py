from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
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

_ALERT_WEBHOOK_POSTS: list[dict[str, object]] = []


class _AlertWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited API
        return

    def do_POST(self) -> None:  # noqa: N802 - inherited API
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8")
        _ALERT_WEBHOOK_POSTS.append(
            {
                "path": self.path,
                "signature": self.headers.get("x-flow-memory-alert-signature", ""),
                "authorization": self.headers.get("authorization", ""),
                "body": json.loads(body),
                "raw_body": body,
            }
        )
        status_code = 503 if self.path == "/fail" else 202
        self.send_response(status_code)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def _alert_webhook_server() -> tuple[ThreadingHTTPServer, str]:
    _ALERT_WEBHOOK_POSTS.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _AlertWebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    return server, f"http://{host}:{port}/alerts"


class _FakeWebhookResponse:
    status = 202

    def __enter__(self) -> "_FakeWebhookResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, _size: int = -1) -> bytes:
        return b'{"ok":true}'


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

    snapshot = cast(dict[str, Any], telemetry.snapshot(reset=False))
    assert len(snapshot["metrics"]) == 1
    assert len(snapshot["traces"]) == 1
    text = telemetry.prometheus_text()
    assert "# TYPE compute_plan_requests_total gauge" in text
    assert 'strategy="balanced"' in text

    drained = cast(dict[str, Any], telemetry.snapshot(reset=True))
    assert len(drained["metrics"]) == 1
    assert telemetry.summary()["metric_sample_count"] == 0


def test_metric_and_span_catalogs_include_production_backlog_names() -> None:
    names = set(metric_names())
    assert "compute_job_completed_total" in names
    assert "compute_job_lease_expired_total" in names
    assert "billing_debit_total" in names
    assert "billing_payout_settled_total" in names
    assert "billing_insufficient_credit_total" in names
    assert "audit_chain_verify_fail_total" in names
    assert "billing_webhook_failures_total" in names
    assert "provider_execution_failure_total" in names
    assert "provider_fraud_signal_total" in names
    assert "redis_unavailable_total" in names
    assert "external_provider_allowlist_missing_total" in names
    assert "compute_provider_receipt_accepted_total" in names
    assert "compute_provider_receipt_rejected_total" in names
    assert "capacity_hold_expired_total" in names
    assert "capacity_reservation_expired_total" in names
    assert "quote_cache_invalidated_total" in names
    assert "capacity_confirmed_total" in names
    assert "capacity_auction_cleared_total" in names
    assert "provider_sla_penalty_total" in names
    assert "alert_delivery_pending_total" in names
    assert "alert_delivery_sent_total" in names
    assert "alert_delivery_failed_total" in names
    assert "error_tracking_pending_total" in names
    assert "error_tracking_sent_total" in names
    assert "error_tracking_failed_total" in names
    assert "otlp_export_attempt_total" in names
    assert "otlp_export_sent_total" in names
    assert "otlp_export_failed_total" in names
    assert "compute.provider_discovery" in set(span_names())


def test_alert_evaluator_fires_on_audit_failures_and_acknowledges_route() -> None:
    service = _service()
    reset_default_service(service)
    router = create_default_router()
    try:
        service.telemetry.increment("audit_chain_verify_fail_total")
        evaluation = cast(dict[str, Any], AlertEvaluator().evaluate(service.telemetry).as_record())
        alerts = cast(dict[str, Any], router.dispatch("GET", "/compute/alerts"))
        ack = cast(dict[str, Any], router.dispatch("POST", "/compute/alerts/audit-chain-verify-failure/ack", {"acknowledged_by": "test"}))
        acknowledged = cast(dict[str, Any], router.dispatch("GET", "/compute/alerts"))
    finally:
        reset_default_service(None)

    assert evaluation["ok"] is False
    assert evaluation["firing"][0]["rule_name"] == "audit-chain-verify-failure"
    assert alerts["alerts"]["firing_count"] == 1
    assert ack["ok"] is True
    assert acknowledged["alerts"]["firing"][0]["acknowledged"] is True

def test_alert_routing_noops_without_firing_alerts_or_when_disabled() -> None:
    service = _service()
    reset_default_service(service)
    router = create_default_router()
    try:
        no_alerts = router.dispatch("POST", "/compute/alerts/route", {})
        service.telemetry.increment("audit_chain_verify_fail_total")
        disabled = router.dispatch("POST", "/compute/alerts/route", {})
    finally:
        reset_default_service(None)

    assert no_alerts["ok"] is True
    assert no_alerts["delivery_count"] == 0
    assert no_alerts["skipped_reason"] == "no_firing_alerts"
    assert disabled["ok"] is True
    assert disabled["delivery_count"] == 0
    assert disabled["skipped_reason"] == "alert_routing_disabled"
    assert service.store.count_records("alert_delivery") == 0


def test_alert_routing_delivers_configured_webhook_and_records_evidence() -> None:
    server, url = _alert_webhook_server()
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                alert_routing_enabled=True,
                alert_webhook_url=url,
                alert_webhook_secret="alert-routing-secret",
            ),
        )
        service.telemetry.increment("audit_chain_verify_fail_total")
        routed = service.route_alerts({})
    finally:
        server.shutdown()
        server.server_close()

    assert routed["ok"] is True
    assert routed["delivery_count"] == 1
    delivery = routed["deliveries"][0]
    assert delivery["status"] == "delivered"
    assert delivery["target"].endswith("/alerts")
    assert "alert-routing-secret" not in json.dumps(delivery)
    assert service.store.count_records("alert_delivery") == 1
    assert _ALERT_WEBHOOK_POSTS[0]["path"] == "/alerts"
    assert _ALERT_WEBHOOK_POSTS[0]["signature"]
    alert_body = cast(Any, _ALERT_WEBHOOK_POSTS[0]["body"])
    assert alert_body["alert"]["rule_name"] == "audit-chain-verify-failure"
    assert "alert-routing-secret" not in str(_ALERT_WEBHOOK_POSTS[0]["raw_body"])
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["alert_delivery_pending_total"] == 1.0
    assert metric_totals["alert_delivery_sent_total"] == 1.0


def test_alert_routing_retries_transient_delivery_error(monkeypatch: Any) -> None:
    attempts = 0

    def fake_urlopen(_request: object, **_kwargs: object) -> _FakeWebhookResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary alert webhook failure")
        return _FakeWebhookResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            alert_routing_enabled=True,
            alert_webhook_url="https://alerts.example.test/flow-memory",
            alert_webhook_secret="alert-routing-secret",
        ),
    )

    service.telemetry.increment("audit_chain_verify_fail_total")
    routed = service.route_alerts({})

    assert attempts == 2
    assert routed["ok"] is True
    assert routed["delivery_count"] == 1
    assert routed["deliveries"][0]["status"] == "delivered"
    assert routed["deliveries"][0]["http_status"] == 202
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["alert_delivery_sent_total"] == 1.0


def test_alert_routing_records_failed_webhook_without_leaking_secret() -> None:
    server, url = _alert_webhook_server()
    failing_url = url.replace("/alerts", "/fail")
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                alert_routing_enabled=True,
                alert_webhook_url=failing_url,
                alert_webhook_secret="alert-routing-secret",
            ),
        )
        service.telemetry.increment("audit_chain_verify_fail_total")
        routed = service.route_alerts({})
    finally:
        server.shutdown()
        server.server_close()

    assert routed["ok"] is False
    assert routed["failed_count"] == 1
    delivery = routed["deliveries"][0]
    assert delivery["status"] == "failed"
    assert delivery["http_status"] == 503
    assert "alert-routing-secret" not in json.dumps(delivery)
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["alert_delivery_failed_total"] == 1.0


def test_alert_routing_enabled_readiness_requires_usable_webhook_url() -> None:
    missing = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            alert_routing_enabled=True,
        ),
    )
    unsafe = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            alert_routing_enabled=True,
            alert_webhook_url="http://example.com/alerts",
        ),
    )

    assert "alert_webhook_unavailable" in missing.readiness()["readiness_failures"]
    assert "alert_webhook_url_not_allowed" in unsafe.readiness()["readiness_failures"]


def test_error_tracking_disabled_noops() -> None:
    service = _service()

    tracked = service.track_error({"error_code": "test.error", "message": "ignored"})

    assert tracked["ok"] is False
    assert tracked["error"] == "error_tracking_disabled"
    assert service.store.count_records("error_tracking_event") == 0


def test_error_tracking_records_delivery_and_metrics() -> None:
    server, url = _alert_webhook_server()
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                error_tracking_enabled=True,
                error_tracking_webhook_url=url,
                error_tracking_webhook_secret="error-track-secret",
            ),
        )
        tracked = service.track_error(
            {
                "error_code": "storage.write_failed",
                "message": "failed to persist record",
                "details": {"table": "compute_jobs", "password": "must-not-persist"},
            }
        )
    finally:
        server.shutdown()
        server.server_close()

    assert tracked["ok"] is True
    assert tracked["status"] == "delivered"
    assert service.store.count_records("error_tracking_event") == 1
    event = tracked["event"]
    assert event["details"]["password"] == "[redacted]"
    assert "error-track-secret" not in json.dumps(event)
    error_body = cast(Any, _ALERT_WEBHOOK_POSTS[0]["body"])
    assert error_body["type"] == "flow_memory.compute_market.error"
    assert error_body["details"]["password"] == "[redacted]"
    assert _ALERT_WEBHOOK_POSTS[0]["signature"]
    assert "error-track-secret" not in str(_ALERT_WEBHOOK_POSTS[0]["raw_body"])
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["error_tracking_pending_total"] == 1.0
    assert metric_totals["error_tracking_sent_total"] == 1.0


def test_error_tracking_records_failed_webhook_without_leaking_secret() -> None:
    server, url = _alert_webhook_server()
    failing_url = url.replace("/alerts", "/fail")
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                error_tracking_enabled=True,
                error_tracking_webhook_url=failing_url,
                error_tracking_webhook_secret="error-track-secret",
            ),
        )
        tracked = service.track_error({"error_code": "provider.timeout", "message": "provider timed out"})
    finally:
        server.shutdown()
        server.server_close()

    assert tracked["ok"] is False
    assert tracked["status"] == "failed"
    assert tracked["event"]["http_status"] == 503
    assert "error-track-secret" not in json.dumps(tracked)
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["error_tracking_failed_total"] == 1.0


def test_error_tracking_enabled_readiness_requires_usable_webhook_url() -> None:
    missing = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            error_tracking_enabled=True,
        ),
    )
    unsafe = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            error_tracking_enabled=True,
            error_tracking_webhook_url="http://example.com/errors",
        ),
    )

    assert "error_tracking_webhook_unavailable" in missing.readiness()["readiness_failures"]
    assert "error_tracking_webhook_url_not_allowed" in unsafe.readiness()["readiness_failures"]


def test_error_tracking_integrates_via_http_gateway() -> None:
    server, url = _alert_webhook_server()
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            error_tracking_enabled=True,
            error_tracking_webhook_url=url,
            error_tracking_webhook_secret="error-track-secret",
        ),
    )
    reset_default_service(service)
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-key", require_scopes=True, enable_rate_limit=False))
    try:
        response = gateway.handle(
            "POST",
            "/compute/errors/track",
            {"x-flow-memory-api-key": "dev-key", "x-flow-memory-scopes": "compute:admin"},
            json.dumps({"error_code": "gateway.error", "message": "gateway observed error"}).encode("utf-8"),
        )
    finally:
        reset_default_service(None)
        server.shutdown()
        server.server_close()

    body = json.loads(response.to_bytes())
    assert response.status == 200
    assert body["data"]["status"] == "delivered"
    assert body["data"]["event"]["error_code"] == "gateway.error"


def test_otlp_export_noops_when_disabled() -> None:
    service = _service()
    service.telemetry.increment("compute_plan_requests_total", {"strategy": "test"})

    exported = service.export_telemetry_otlp({})

    assert exported["ok"] is False
    assert exported["error"] == "telemetry_export_disabled"
    assert service.store.count_records("otlp_export_delivery") == 0


def test_otlp_export_delivers_to_collector_and_records_evidence() -> None:
    server, url = _alert_webhook_server()
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                telemetry_export_enabled=True,
                otlp_endpoint_url=url,
                otlp_headers=("authorization: Bearer otlp-secret",),
            ),
        )
        service.telemetry.increment("compute_plan_requests_total", {"strategy": "otlp"})
        with service.telemetry.span("compute.plan_request", {"request_id": "req_otlp"}):
            pass
        exported = service.export_telemetry_otlp({})
    finally:
        server.shutdown()
        server.server_close()

    assert exported["ok"] is True
    assert exported["status"] == "delivered"
    delivery = exported["delivery"]
    assert delivery["metric_count"] == 1
    assert delivery["trace_count"] == 1
    assert "otlp-secret" not in json.dumps(delivery)
    assert service.store.count_records("otlp_export_delivery") == 1
    assert _ALERT_WEBHOOK_POSTS[0]["authorization"] == "Bearer otlp-secret"
    otlp_body = cast(Any, _ALERT_WEBHOOK_POSTS[0]["body"])
    assert otlp_body["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]["name"] == "compute_plan_requests_total"
    assert otlp_body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == "compute.plan_request"
    assert "otlp-secret" not in str(_ALERT_WEBHOOK_POSTS[0]["raw_body"])
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["otlp_export_attempt_total"] == 1.0
    assert metric_totals["otlp_export_sent_total"] == 1.0


def test_otlp_export_retries_transient_collector_error(monkeypatch: Any) -> None:
    attempts = 0

    def fake_urlopen(_request: object, **_kwargs: object) -> _FakeWebhookResponse:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary otlp collector failure")
        return _FakeWebhookResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            telemetry_export_enabled=True,
            otlp_endpoint_url="https://otel.example.test/v1/traces",
            otlp_headers=("authorization: Bearer otlp-secret",),
        ),
    )
    service.telemetry.increment("compute_plan_requests_total", {"strategy": "otlp"})

    exported = service.export_telemetry_otlp({})

    assert attempts == 2
    assert exported["ok"] is True
    assert exported["status"] == "delivered"
    assert exported["delivery"]["http_status"] == 202
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["otlp_export_sent_total"] == 1.0


def test_otlp_export_records_failed_collector_without_leaking_headers() -> None:
    server, url = _alert_webhook_server()
    failing_url = url.replace("/alerts", "/fail")
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                telemetry_export_enabled=True,
                otlp_endpoint_url=failing_url,
                otlp_headers=("authorization: Bearer otlp-secret",),
            ),
        )
        service.telemetry.increment("compute_plan_requests_total")
        exported = service.export_telemetry_otlp({})
    finally:
        server.shutdown()
        server.server_close()

    assert exported["ok"] is False
    assert exported["status"] == "failed"
    assert exported["delivery"]["http_status"] == 503
    assert "otlp-secret" not in json.dumps(exported["delivery"])
    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    assert metric_totals["otlp_export_failed_total"] == 1.0


def test_otlp_export_enabled_readiness_requires_usable_endpoint_url() -> None:
    missing = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            telemetry_export_enabled=True,
        ),
    )
    unsafe = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            telemetry_export_enabled=True,
            otlp_endpoint_url="http://example.com/v1/metrics",
        ),
    )

    assert "otlp_endpoint_unavailable" in missing.readiness()["readiness_failures"]
    assert "otlp_endpoint_url_not_allowed" in unsafe.readiness()["readiness_failures"]


def test_otlp_export_integrates_via_admin_gateway() -> None:
    server, url = _alert_webhook_server()
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning",
            rate_limits_enabled=False,
            telemetry_export_enabled=True,
            otlp_endpoint_url=url,
        ),
    )
    reset_default_service(service)
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-key", require_scopes=True, enable_rate_limit=False))
    try:
        service.telemetry.increment("compute_plan_requests_total")
        response = gateway.handle(
            "POST",
            "/admin/compute/otlp/export",
            {"x-flow-memory-api-key": "dev-key", "x-flow-memory-scopes": "compute:admin"},
            b"{}",
        )
    finally:
        reset_default_service(None)
        server.shutdown()
        server.server_close()

    body = json.loads(response.to_bytes())
    assert response.status == 200
    assert body["data"]["status"] == "delivered"
    assert body["data"]["delivery"]["metric_count"] == 1

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
    assert cast(dict[str, float], service.telemetry.summary()["metric_totals"])["billing_webhook_failures_total"] == 1.0
    assert cast(dict[str, float], allowlist_service.telemetry.summary()["metric_totals"])["external_provider_allowlist_missing_total"] == 1.0

    service.telemetry.increment("redis_unavailable_total")
    alerts = cast(dict[str, Any], AlertEvaluator().evaluate(service.telemetry).as_record())
    rule_names = {item["rule_name"] for item in alerts["firing"]}
    assert "billing-webhook-failures" in rule_names
    assert "redis-unavailable" in rule_names

def test_provider_fraud_signal_metric_alert_and_route_on_quote_drift() -> None:
    server, url = _alert_webhook_server()
    try:
        service = ComputeMarketService(
            store=ComputeMarketStore(":memory:"),
            config=ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="production_planning",
                rate_limits_enabled=False,
                alert_routing_enabled=True,
                alert_webhook_url=url,
                alert_webhook_secret="alert-routing-secret",
            ),
        )
        base_quote = {
            "quote_id": "quote_observability_drift_1",
            "provider_id": "provider_observability_gpu",
            "route_id": "route_observability_gpu",
            "unit_type": "gpu_minute",
            "unit_price": 0.09,
            "estimated_units": 2,
            "estimated_total_cost": 0.18,
            "confidence": 0.93,
            "currency_or_asset": "USDC",
            "network": "solana",
            "capacity_available": True,
            "quote_ttl_seconds": 300,
            "expires_at": "2099-01-01T00:00:00Z",
            "settlement_modes": ["generic_dry_run"],
            "dry_run_supported": True,
            "assumptions": [],
        }
        accepted = service.broker_quote({"quote": base_quote})
        drifted = service.broker_quote(
            {"quote": {**base_quote, "quote_id": "quote_observability_drift_2", "estimated_total_cost": 0.27}}
        )
        evaluated = cast(dict[str, Any], AlertEvaluator().evaluate(service.telemetry).as_record())
        routed = service.route_alerts({})
    finally:
        server.shutdown()
        server.server_close()

    metric_totals = cast(dict[str, float], service.telemetry.summary()["metric_totals"])
    rule_names = {item["rule_name"] for item in evaluated["firing"]}
    alert_body = cast(dict[str, Any], _ALERT_WEBHOOK_POSTS[0]["body"])

    assert accepted["ok"] is True
    assert drifted["ok"] is True
    assert drifted["fraud_signals"][0]["signal_type"] == "quote_price_manipulation"
    assert metric_totals["provider_fraud_signal_total"] == 1.0
    assert "provider-fraud-signal" in rule_names
    assert routed["ok"] is True
    assert routed["delivery_count"] == 1
    assert alert_body["alert"]["rule_name"] == "provider-fraud-signal"

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
        "compute_job_lease_expired_total",
        "provider_quote_latency_ms",
        "provider_quote_failure_total",
        "provider_circuit_open_total",
        "provider_fraud_signal_total",
        "quote_stale_total",
        "capacity_reserved_total",
        "capacity_confirmed_total",
        "capacity_auction_cleared_total",
        "quote_cache_invalidated_total",
        "capacity_released_total",
        "capacity_hold_expired_total",
        "capacity_reservation_expired_total",
        "billing_debit_total",
        "billing_payout_settled_total",
        "billing_insufficient_credit_total",
        "billing_payment_failed_total",
        "billing_webhook_failures_total",
        "provider_sla_penalty_total",
        "alert_delivery_pending_total",
        "alert_delivery_sent_total",
        "alert_delivery_failed_total",
        "error_tracking_pending_total",
        "error_tracking_sent_total",
        "error_tracking_failed_total",
        "audit_chain_verify_fail_total",
        "settlement_attempt_total",
        "unexpected_live_settlement_config_total",
        "redis_unavailable_total",
        "postgres_unavailable_total",
        "external_provider_allowlist_missing_total",
        "otlp_export_attempt_total",
        "otlp_export_sent_total",
        "otlp_export_failed_total",
    }

    assert dashboard["uid"] == "flow-memory-compute-market-prod"
    assert len(panels) >= 8
    for metric in required_metrics:
        assert metric in expressions


def test_prometheus_alert_rules_cover_public_production_failures() -> None:
    rules_path = Path("deployments/compute-market/prometheus-alerts.yml")
    rules = rules_path.read_text(encoding="utf-8")

    required_alerts = {
        "FlowMemoryComputeMarketReadinessUnavailable",
        "FlowMemoryComputeMarketAuditChainBreak",
        "FlowMemoryComputeMarketProviderQuoteErrorSpike",
        "FlowMemoryComputeMarketProviderCircuitOpen",
        "FlowMemoryComputeMarketProviderFraudSignal",
        "FlowMemoryComputeMarketStaleQuotes",
        "FlowMemoryComputeMarketBillingWebhookFailures",
        "FlowMemoryComputeMarketPolicyDenialSpike",
        "FlowMemoryComputeMarketBillingInsufficientCredit",
        "FlowMemoryComputeMarketUnexpectedSettlementConfig",
        "FlowMemoryComputeMarketProviderAllowlistMissing",
        "FlowMemoryComputeMarketComputeJobFailures",
        "FlowMemoryComputeMarketAlertDeliveryFailure",
    }
    required_metrics = {
        "postgres_unavailable_total",
        "redis_unavailable_total",
        "audit_chain_verify_fail_total",
        "provider_quote_failure_total",
        "provider_circuit_open_total",
        "provider_fraud_signal_total",
        "quote_stale_total",
        "billing_webhook_failures_total",
        "billing_insufficient_credit_total",
        "compute_policy_denials_total",
        "policy_denied_total",
        "unexpected_live_settlement_config_total",
        "settlement_attempt_total",
        "external_provider_allowlist_missing_total",
        "compute_job_failed_total",
        "compute_job_lease_expired_total",
        "alert_delivery_failed_total",
        "error_tracking_failed_total",
        "otlp_export_failed_total",
    }

    assert "flow-memory-compute-market-public-production" in rules
    for alert_name in required_alerts:
        assert f"alert: {alert_name}" in rules
    for metric_name in required_metrics:
        assert metric_name in rules
