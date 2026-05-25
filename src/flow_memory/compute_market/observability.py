"""Structured observability hooks for Flow Memory Compute Market."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterator, Mapping

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
    "compute_job_started_total",
    "compute_job_completed_total",
    "compute_job_failed_total",
    "provider_quote_latency_ms",
    "provider_quote_failure_total",
    "provider_circuit_open_total",
    "route_selected_total",
    "policy_denied_total",
    "quote_stale_total",
    "capacity_reserved_total",
    "capacity_released_total",
    "billing_debit_total",
    "settlement_attempt_total",
    "audit_chain_verify_fail_total",
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


def metric_names() -> tuple[str, ...]:
    return _METRIC_NAMES


def span_names() -> tuple[str, ...]:
    return _SPAN_NAMES
