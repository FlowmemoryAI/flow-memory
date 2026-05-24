"""Typed records for the Flow Memory Compute Market.

All records are JSON-serializable and dry-run oriented. They describe local
intent and simulation state only; they are not live reservations, payments, or
provider calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class RouteStrategy(str, Enum):
    CHEAPEST_ELIGIBLE = "cheapest_eligible"
    LOWEST_LATENCY = "lowest_latency"
    HIGHEST_QUALITY = "highest_quality"


class PaymentRail(str, Enum):
    LOCAL_CREDITS = "local_credits"
    DRY_RUN_USDC = "dry_run_usdc"
    NOOP = "noop"


@dataclass(frozen=True)
class ComputeProvider:
    provider_id: str
    label: str
    provider_class: str
    reputation: float = 0.0
    trust_posture: str = "local_simulation"
    supports_reservations: bool = False
    live_or_dry_run: str = "dry_run"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeRoute:
    route_id: str
    provider_id: str
    provider_class: str
    model: str
    input_price_per_million: float
    output_price_per_million: float
    latency_ms: int = 0
    quality_score: float = 0.0
    capacity_units: float = 0.0
    fallback_route_id: str = ""
    dry_run_only: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def eligible_for(self, policy: "ComputeBudgetPolicy") -> bool:
        if not self.dry_run_only and policy.dry_run_required:
            return False
        if policy.marketplace_only and self.provider_class != "marketplace":
            return False
        if policy.allowed_providers and self.provider_id not in policy.allowed_providers:
            return False
        if policy.allowed_routes and self.route_id not in policy.allowed_routes:
            return False
        if policy.max_input_price_per_million and self.input_price_per_million > policy.max_input_price_per_million:
            return False
        if policy.max_output_price_per_million and self.output_price_per_million > policy.max_output_price_per_million:
            return False
        return True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class CapacityWindow:
    provider_id: str
    route_id: str
    starts_at: str = "dry-run-now"
    ends_at: str = "dry-run-window"
    capacity_units: float = 0.0
    price_per_unit: float = 0.0
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class TaskEconomicProfile:
    task_id: str = "local-task"
    goal_id: str = "local-goal"
    model_requested: str = "small-general"
    expected_input_tokens: int = 1000
    expected_output_tokens: int = 500
    quality_sensitive: bool = False
    latency_sensitive: bool = False
    requires_marketplace: bool = False
    max_budget: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeBudgetPolicy:
    max_total_cost: float = 0.0
    max_quote: float = 0.0
    max_input_price_per_million: float = 0.0
    max_output_price_per_million: float = 0.0
    strategy: str = RouteStrategy.CHEAPEST_ELIGIBLE.value
    allowed_providers: tuple[str, ...] = ()
    allowed_routes: tuple[str, ...] = ()
    marketplace_only: bool = False
    allow_fallback: bool = True
    dry_run_required: bool = True
    payment_rail: str = PaymentRail.LOCAL_CREDITS.value
    policy_id: str = "local-compute-policy"

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.dry_run_required:
            errors.append("compute market requires dry_run_required=true")
        if self.max_total_cost < 0 or self.max_quote < 0:
            errors.append("compute budget limits must be non-negative")
        if self.max_total_cost == 0 and self.max_quote == 0:
            errors.append("compute budget policy must set max_total_cost or max_quote")
        if self.strategy not in {item.value for item in RouteStrategy}:
            errors.append(f"unknown compute route strategy: {self.strategy}")
        if self.payment_rail not in {item.value for item in PaymentRail}:
            errors.append(f"unsupported dry-run payment rail: {self.payment_rail}")
        return tuple(errors)

    def ceiling(self) -> float:
        limits = [value for value in (self.max_total_cost, self.max_quote) if value > 0]
        return min(limits) if limits else 0.0

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeQuote:
    quote_id: str
    route_id: str
    provider_id: str
    task_id: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    currency: str = "LOCAL_CREDITS"
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ReservationIntent:
    reservation_id: str
    provider_id: str
    route_id: str
    capacity_units: float
    status: str = "simulated"
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PaymentIntent:
    payment_id: str
    task_id: str
    quote_id: str
    amount: float
    currency: str = "LOCAL_CREDITS"
    rail: str = PaymentRail.LOCAL_CREDITS.value
    status: str = "dry_run_planned"
    no_private_key_required: bool = True
    no_funds_moved: bool = True
    no_broadcast: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class SettlementSimulation:
    settlement_id: str
    payment_id: str
    provider_id: str
    worker_amount: float
    treasury_amount: float
    status: str = "simulated"
    no_live_settlement: bool = True
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeRouteDecision:
    ok: bool
    status: str
    reason: str
    task: TaskEconomicProfile
    policy: ComputeBudgetPolicy | None = None
    selected_route: ComputeRoute | None = None
    quote: ComputeQuote | None = None
    reservation: ReservationIntent | None = None
    fallback_used: bool = False
    safety_authority: str = "policy_engine_and_approval_gate"
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class EconomicMemoryRecord:
    record_id: str
    goal_id: str
    task_id: str
    route_mode: str
    provider_id: str
    provider_class: str
    route_id: str
    model_requested: str
    provider_model_id: str
    tokens_in: int
    tokens_out: int
    unit_price_input: float
    unit_price_output: float
    total_cost: float
    latency_ms: int
    fallback_used: bool
    quality_signal: float
    live_or_dry_run: str = "dry_run"
    no_funds_moved: bool = True
    no_broadcast: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record(self)


def _record(item: object) -> dict[str, Any]:
    data = dict(getattr(item, "__dict__"))
    for key, value in list(data.items()):
        data[key] = _nested(value)
    return data


def _nested(value: Any) -> Any:
    if hasattr(value, "as_record"):
        return value.as_record()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_nested(item) for item in value)
    if isinstance(value, Mapping):
        return {str(key): _nested(item) for key, item in value.items()}
    return value
