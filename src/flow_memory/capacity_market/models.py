"""Flow Memory Capacity Market and Forward Capacity simulator records."""
from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from enum import Enum
from typing import Any

UTC_EPOCH = "2026-05-26T00:00:00Z"


class GPUClass(str, Enum):
    H100 = "H100"
    A100 = "A100"
    L40S = "L40S"
    A10 = "A10"
    B200 = "B200"
    EQUIVALENT = "equivalent"


class ComputeRegion(str, Enum):
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    AP_SOUTH = "ap-south"
    ANY = "any"


@dataclass(frozen=True)
class StandardizedComputeUnit:
    unit_id: str
    unit_type: str
    gpu_class: str = GPUClass.H100.value
    seconds_per_unit: int = 3600
    benchmark_floor: str = "fm-gpu-unit-v1"
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ComputeDeliveryWindow:
    delivery_window_id: str
    starts_at: str
    ends_at: str
    region: str = ComputeRegion.US_EAST.value

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ComputeQualitySpec:
    gpu_class: str = GPUClass.H100.value
    gpu_count: int = 1
    memory_gb: int = 80
    max_interruption_minutes: int = 0
    min_uptime_target: float = 0.99

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityWindow:
    capacity_window_id: str
    provider_id: str
    resource_type: str = "gpu_hour"
    gpu_class: str = GPUClass.H100.value
    available_units: float = 0.0
    region: str = ComputeRegion.US_EAST.value
    starts_at: str = UTC_EPOCH
    ends_at: str = UTC_EPOCH
    price_floor: float = 0.0
    reservation_required: bool = True
    status: str = "available"
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityInventory:
    inventory_id: str
    windows: tuple[CapacityWindow, ...] = ()
    total_available_units: float = 0.0
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityHold:
    hold_id: str
    capacity_window_id: str
    provider_id: str
    route_id: str
    capacity_units: float
    unit_type: str = "gpu_hour"
    hold_expires_at: str = "2026-05-26T01:00:00Z"
    status: str = "held"
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityReservation:
    reservation_id: str
    hold_id: str
    provider_id: str
    route_id: str
    capacity_units: float
    unit_type: str = "gpu_hour"
    reserved_from: str = UTC_EPOCH
    reserved_until: str = UTC_EPOCH
    status: str = "held"
    hold_expires_at: str = "2026-05-26T01:00:00Z"
    dry_run_only: bool = True
    funds_moved: bool = False
    legally_binding: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityUtilizationRecord:
    utilization_id: str
    provider_id: str
    capacity_window_id: str
    reserved_units: float
    consumed_units: float
    released_units: float
    utilization_rate: float
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityProviderOffer:
    offer_id: str
    provider_id: str
    gpu_class: str
    region: str
    unit_type: str
    available_units: float
    unit_price: float
    delivery_window: ComputeDeliveryWindow
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityDemandIntent:
    intent_id: str
    buyer_id: str
    gpu_class: str
    region: str
    unit_type: str
    requested_units: float
    max_unit_price: float
    deadline: str = ""
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityOffer:
    offer_id: str
    provider_id: str
    gpu_class: str
    region: str
    unit_type: str
    capacity_units: float
    unit_price: float
    delivery_start: str
    delivery_end: str
    transferability: str = "non_transferable"
    settlement_type: str = "physical_delivery_simulated"
    dry_run_only: bool = True
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityBid:
    bid_id: str
    buyer_id: str
    gpu_class: str
    region: str
    unit_type: str
    capacity_units: float
    max_unit_price: float
    delivery_start: str
    delivery_end: str
    dry_run_only: bool = True
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityTrade:
    trade_id: str
    offer_id: str
    bid_id: str
    capacity_units: float
    unit_price: float
    notional_value: float
    status: str = "simulated"
    dry_run_only: bool = True
    funds_moved: bool = False
    legally_binding: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityDeliverySchedule:
    schedule_id: str
    contract_id: str
    delivery_start: str
    delivery_end: str
    scheduled_units: float
    status: str = "delivery_scheduled"
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacitySettlementPlan:
    settlement_plan_id: str
    contract_id: str
    settlement_type: str = "physical_delivery_simulated"
    estimated_notional_value: float = 0.0
    status: str = "simulated"
    dry_run_only: bool = True
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityRiskAssessment:
    risk_assessment_id: str
    contract_id: str
    delivery_risk: str = "medium"
    compliance_risk: str = "requires_review"
    market_risk: str = "simulated_only"
    warnings: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ForwardCapacityContract:
    contract_id: str
    contract_type: str
    buyer_id: str
    provider_id: str
    gpu_class: str
    region: str
    unit_type: str
    capacity_units: float
    unit_price: float
    delivery_start: str
    delivery_end: str
    transferability: str = "non_transferable"
    settlement_type: str = "physical_delivery_simulated"
    status: str = "draft"
    dry_run_only: bool = True
    funds_moved: bool = False
    legally_binding: bool = False
    live_trading_enabled: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


def _record_dict(value: Any) -> dict[str, Any]:
    record = _record(value)
    if not isinstance(record, dict):
        raise TypeError("expected dataclass record")
    return record


def _record(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _record(val) for key, val in value.__dict__.items()}
    if isinstance(value, tuple):
        return tuple(_record(item) for item in value)
    if isinstance(value, list):
        return [_record(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _record(val) for key, val in value.items()}
    return value
