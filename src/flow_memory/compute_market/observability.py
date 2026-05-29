"""Structured observability hooks for Flow Memory Compute Market."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterator, Mapping, SupportsFloat, cast

_METRIC_NAMES: tuple[str, ...] = (
    "compute_plan_requests_total",
    "compute_plan_fail_closed_total",
    "compute_quote_requests_total",
    "compute_quote_provider_timeouts_total",
    "compute_quote_provider_errors_total",
    "compute_route_selected_total",
    "compute_route_rejected_total",
    "compute_policy_denials_total",
    "compute_fallback_used_total",
    "compute_payment_plan_created_total",
    "compute_settlement_simulated_total",
    "compute_economic_memory_writes_total",
    "compute_economic_memory_query_total",
    "compute_provider_health_status",
    "compute_provider_latency_ms",
    "compute_quote_latency_ms",
    "compute_plan_latency_ms",
    "compute_estimated_cost",
    "compute_actual_cost",
    "compute_roi",
    "compute_intelligence_plan_created_total",
    "compute_job_started_total",
    "compute_job_completed_total",
    "compute_job_failed_total",
    "compute_job_lease_expired_total",
    "provider_execution_request_total",
    "provider_execution_failure_total",
    "provider_quote_latency_ms",
    "provider_quote_failure_total",
    "provider_fraud_signal_total",
    "provider_circuit_open_total",
    "route_selected_total",
    "policy_denied_total",
    "quote_stale_total",
    "capacity_reserved_total",
    "capacity_confirmed_total",
    "capacity_auction_cleared_total",
    "quote_cache_invalidated_total",
    "capacity_released_total",
    "capacity_reservation_expired_total",
    "capacity_hold_expired_total",
    "capacity_consumed_total",
    "billing_debit_total",
    "billing_payout_settled_total",
    "billing_insufficient_credit_total",
    "billing_refund_skipped_no_debit_total",
    "billing_checkout_created_total",
    "billing_checkout_failed_total",
    "billing_webhook_failures_total",
    "billing_payment_failed_total",
    "billing_webhook_duplicate_terminal_total",
    "billing_ledger_mismatch_total",
    "provider_sla_penalty_total",
    "postgres_unavailable_total",
    "redis_unavailable_total",
    "external_provider_allowlist_missing_total",
    "unexpected_live_settlement_config_total",
    "settlement_attempt_total",
    "audit_chain_verify_fail_total",
    "audit_checkpoint_stale_total",
    "compute_provider_receipt_accepted_total",
    "compute_provider_receipt_rejected_total",
    "compute_provider_callback_rejected_total",
    "error_tracking_pending_total",
    "error_tracking_sent_total",
    "error_tracking_failed_total",
    "otlp_export_attempt_total",
    "otlp_export_sent_total",
    "otlp_export_failed_total",
    "alert_delivery_pending_total",
    "alert_delivery_sent_total",
    "alert_delivery_failed_total",
)

_SPAN_NAMES: tuple[str, ...] = (
    "compute.plan_request",
    "compute.provider_discovery",
    "compute.quote_collection",
    "compute.quote_normalization",
    "compute.policy_evaluation",
    "compute.route_selection",
    "compute.payment_planning",
    "compute.economic_memory_write",
    "compute.audit_write",
)


@dataclass(frozen=True)
class MetricSample:
    name: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)

    def as_record(self) -> dict[str, object]:
        return {"name": self.name, "value": self.value, "labels": dict(self.labels)}


@dataclass(frozen=True)
class TraceSpanRecord:
    name: str
    latency_ms: float
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, object]:
        return {"name": self.name, "latency_ms": round(self.latency_ms, 3), "attributes": dict(self.attributes)}


@dataclass(frozen=True)
class AlertRule:
    name: str
    metric_name: str
    threshold: float
    comparison: str = ">="
    severity: str = "warning"
    description: str = ""

    def as_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass(frozen=True)
class AlertFiringState:
    rule_name: str
    metric_name: str
    value: float
    threshold: float
    severity: str
    description: str
    fired_at: str

    def as_record(self) -> dict[str, object]:
        return {
            "rule_name": self.rule_name,
            "metric_name": self.metric_name,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity,
            "description": self.description,
            "fired_at": self.fired_at,
        }


@dataclass(frozen=True)
class AlertEvaluationResult:
    ok: bool
    rules_evaluated: int
    firing: tuple[AlertFiringState, ...]
    evaluated_at: str

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "rules_evaluated": self.rules_evaluated,
            "firing_count": len(self.firing),
            "firing": tuple(state.as_record() for state in self.firing),
            "evaluated_at": self.evaluated_at,
        }


DEFAULT_ALERT_RULES: tuple[AlertRule, ...] = (
    AlertRule("audit-chain-verify-failure", "audit_chain_verify_fail_total", 1.0, ">=", "critical", "Tamper-evident audit chain verification failed."),
    AlertRule("audit-checkpoint-stale", "audit_checkpoint_stale_total", 1.0, ">=", "warning", "Audit checkpoint scheduler is stale."),
    AlertRule("provider-circuit-open", "provider_circuit_open_total", 1.0, ">=", "warning", "Provider circuit breaker opened."),
    AlertRule("provider-quote-failures", "provider_quote_failure_total", 3.0, ">=", "warning", "Provider quote failures exceeded the public alpha threshold."),
    AlertRule("provider-fraud-signal", "provider_fraud_signal_total", 1.0, ">=", "critical", "Provider fraud or quote-manipulation signal was recorded."),
    AlertRule("provider-receipt-rejected", "compute_provider_receipt_rejected_total", 1.0, ">=", "critical", "Provider execution receipt verification or replay protection rejected a callback."),
    AlertRule("provider-callback-rejected", "compute_provider_callback_rejected_total", 1.0, ">=", "critical", "Provider callback source IP or gateway trust check rejected a callback."),
    AlertRule("provider-execution-failure", "provider_execution_failure_total", 1.0, ">=", "warning", "External provider execution dispatch failed."),
    AlertRule("provider-sla-penalty", "provider_sla_penalty_total", 1.0, ">=", "warning", "Provider SLA penalty was recorded for breached execution terms."),
    AlertRule("policy-denial-spike", "compute_policy_denials_total", 10.0, ">=", "warning", "Policy/rate-limit denials spiked."),
    AlertRule("compute-plan-fail-closed", "compute_plan_fail_closed_total", 1.0, ">=", "warning", "Compute planning failed closed due to safety, policy, or provider controls."),
    AlertRule("unexpected-settlement-attempt", "settlement_attempt_total", 1.0, ">=", "critical", "Settlement path was touched while live settlement remains disabled."),
    AlertRule("billing-webhook-failures", "billing_webhook_failures_total", 1.0, ">=", "critical", "Billing webhook verification failed."),
    AlertRule("billing-checkout-failures", "billing_checkout_failed_total", 1.0, ">=", "critical", "Billing checkout provider failed to create prepaid-credit sessions."),
    AlertRule("billing-payment-failures", "billing_payment_failed_total", 1.0, ">=", "warning", "Stripe reported failed customer payment events."),
    AlertRule("billing-ledger-mismatch", "billing_ledger_mismatch_total", 1.0, ">=", "critical", "Credit balance ledger drift was detected during reconciliation."),
    AlertRule("billing-refund-skipped-no-debit", "billing_refund_skipped_no_debit_total", 1.0, ">=", "critical", "Refund or SLA credit reconciliation was skipped because no posted debit exists."),
    AlertRule("billing-insufficient-credit", "billing_insufficient_credit_total", 1.0, ">=", "warning", "Compute usage completed without enough prepaid credit to debit."),
    AlertRule("redis-unavailable", "redis_unavailable_total", 1.0, ">=", "critical", "Managed Redis backend is unavailable or unconfigured."),
    AlertRule("postgres-unavailable", "postgres_unavailable_total", 1.0, ">=", "critical", "Managed PostgreSQL backend is unavailable."),
    AlertRule("external-provider-allowlist-missing", "external_provider_allowlist_missing_total", 1.0, ">=", "critical", "External provider mode is enabled without an allowlist."),
    AlertRule("unexpected-live-settlement-config", "unexpected_live_settlement_config_total", 1.0, ">=", "critical", "Live settlement configuration failed safety gates."),
)


class AlertEvaluator:
    def __init__(self, rules: tuple[AlertRule, ...] = DEFAULT_ALERT_RULES) -> None:
        self.rules = rules

    def evaluate(self, telemetry: "ComputeMarketTelemetry") -> AlertEvaluationResult:
        summary = telemetry.summary()
        totals = summary.get("metric_totals", {})
        metric_totals = totals if isinstance(totals, Mapping) else {}
        evaluated_at = _utc_now_iso()
        firing = tuple(
            AlertFiringState(
                rule_name=rule.name,
                metric_name=rule.metric_name,
                value=value,
                threshold=rule.threshold,
                severity=rule.severity,
                description=rule.description,
                fired_at=evaluated_at,
            )
            for rule in self.rules
            for value in (_metric_value(metric_totals, rule.metric_name),)
            if _compare(value, rule.comparison, rule.threshold)
        )
        return AlertEvaluationResult(ok=not firing, rules_evaluated=len(self.rules), firing=firing, evaluated_at=evaluated_at)


@dataclass
class ComputeMarketTelemetry:
    metrics: list[MetricSample] = field(default_factory=list)
    logs: list[Mapping[str, Any]] = field(default_factory=list)
    traces: list[TraceSpanRecord] = field(default_factory=list)

    def increment(self, name: str, labels: Mapping[str, str] | None = None, value: float = 1.0) -> None:
        self.observe(name, value, labels=labels)

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        if name not in _METRIC_NAMES:
            raise ValueError(f"Unknown compute market metric: {name}")
        self.metrics.append(MetricSample(name=name, value=float(value), labels=labels or {}))

    def log(self, event: str, fields: Mapping[str, Any]) -> None:
        self.logs.append({"event": event, **dict(fields)})

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[None]:
        if name not in _SPAN_NAMES:
            raise ValueError(f"Unknown compute market span: {name}")
        start = perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (perf_counter() - start) * 1000.0
            self.traces.append(TraceSpanRecord(name=name, latency_ms=elapsed_ms, attributes=attributes or {}))

    def as_record(self) -> dict[str, object]:
        return {
            "metrics": tuple(sample.as_record() for sample in self.metrics),
            "logs": tuple(dict(item) for item in self.logs),
            "traces": tuple(span.as_record() for span in self.traces),
            "metric_names": _METRIC_NAMES,
            "span_names": _SPAN_NAMES,
        }
    def snapshot(self, *, reset: bool = False) -> dict[str, object]:
        record = self.as_record()
        if reset:
            self.reset()
        return record

    def reset(self) -> None:
        self.metrics.clear()
        self.logs.clear()
        self.traces.clear()

    def summary(self) -> dict[str, object]:
        metric_totals: dict[str, float] = {}
        for sample in self.metrics:
            metric_totals[sample.name] = metric_totals.get(sample.name, 0.0) + sample.value
        error_metric_total = sum(
            value
            for name, value in metric_totals.items()
            if "fail" in name or "error" in name or "denial" in name
        )
        return {
            "metric_sample_count": len(self.metrics),
            "log_count": len(self.logs),
            "trace_count": len(self.traces),
            "metric_totals": metric_totals,
            "error_metric_total": error_metric_total,
        }

    def prometheus_text(self) -> str:
        lines: list[str] = []
        emitted: set[str] = set()
        for sample in self.metrics:
            if sample.name not in emitted:
                emitted.add(sample.name)
                lines.append(f"# TYPE {sample.name} gauge")
            lines.append(f"{sample.name}{_prometheus_labels(sample.labels)} {sample.value:g}")
        return "\n".join(lines) + ("\n" if lines else "")


def _prometheus_labels(labels: Mapping[str, str]) -> str:
    if not labels:
        return ""
    parts = tuple(f'{key}="{_prometheus_escape(value)}"' for key, value in sorted(labels.items()))
    return "{" + ",".join(parts) + "}"


def _prometheus_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric_value(metric_totals: Mapping[str, object], name: str) -> float:
    try:
        value = metric_totals.get(name, 0.0) or 0.0
        return float(cast(SupportsFloat | str | bytes | bytearray, value))
    except (TypeError, ValueError):
        return 0.0


def _compare(value: float, comparison: str, threshold: float) -> bool:
    if comparison == ">=":
        return value >= threshold
    if comparison == ">":
        return value > threshold
    if comparison == "<=":
        return value <= threshold
    if comparison == "<":
        return value < threshold
    if comparison == "==":
        return value == threshold
    raise ValueError(f"Unsupported alert comparison: {comparison}")


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def metric_names() -> tuple[str, ...]:
    return _METRIC_NAMES


def span_names() -> tuple[str, ...]:
    return _SPAN_NAMES
