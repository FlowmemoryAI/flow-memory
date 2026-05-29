"""Flow Memory GPU Futures Simulator records.

These records are explicitly simulation-only. They do not represent live
financial products, margin accounts, collateral, or regulated trading.
"""
from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from typing import Any

UTC_EPOCH = "2026-05-26T00:00:00Z"
DEFAULT_SYMBOL = "FM-H100-USEAST-Q3-2027"


@dataclass(frozen=True)
class GPUFuturesContractSpec:
    symbol: str = DEFAULT_SYMBOL
    gpu_class: str = "H100"
    region: str = "us-east"
    contract_size_gpu_hours: float = 1.0
    delivery_start: str = "2027-07-01T00:00:00Z"
    delivery_end: str = "2027-09-30T23:59:59Z"
    settlement_type: str = "physical_delivery_simulated"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesMarket:
    market_id: str
    symbol: str
    status: str = "simulated"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesOrder:
    order_id: str
    symbol: str
    side: str
    quantity: float
    limit_price: float
    status: str = "simulated_open"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False
    margin_required: bool = False
    leverage_allowed: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesOrderBook:
    symbol: str
    bids: tuple[GPUFuturesOrder, ...] = ()
    asks: tuple[GPUFuturesOrder, ...] = ()
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesTrade:
    trade_id: str
    symbol: str
    buy_order_id: str
    sell_order_id: str
    quantity: float
    price: float
    notional_value: float
    status: str = "simulated"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesPosition:
    position_id: str
    symbol: str
    account_id: str
    quantity: float
    average_price: float
    mark_price: float
    unrealized_pnl: float
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False
    margin_required: bool = False
    leverage_allowed: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesMarkPrice:
    mark_price_id: str
    symbol: str
    mark_price: float
    index_price: float
    basis: float
    created_at: str = UTC_EPOCH
    dry_run_only: bool = True
    live_trading_enabled: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesIndexPrice:
    index_price_id: str
    symbol: str
    index_price: float
    sample_count: int
    created_at: str = UTC_EPOCH
    dry_run_only: bool = True
    live_trading_enabled: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesMarginAccount:
    margin_account_id: str
    account_id: str
    status: str = "simulation_only_not_collateralized"
    simulated_equity: float = 0.0
    live_margin_enabled: bool = False
    leverage_allowed: bool = False
    funds_moved: bool = False
    dry_run_only: bool = True
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesRiskCheck:
    risk_check_id: str
    symbol: str
    status: str = "passed_simulation"
    warnings: tuple[str, ...] = ("simulation_only", "no_live_trading", "legal_review_required")
    max_loss_simulated: float = 0.0
    live_trading_enabled: bool = False
    margin_allowed: bool = False
    leverage_allowed: bool = False
    funds_moved: bool = False
    dry_run_only: bool = True
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesExpiry:
    expiry_id: str
    symbol: str
    status: str = "simulated_expired"
    final_index_price: float = 0.0
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesDeliveryNotice:
    delivery_notice_id: str
    symbol: str
    scheduled_gpu_hours: float
    delivery_start: str
    delivery_end: str
    status: str = "simulated_delivery_notice"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False
    legally_binding: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUFuturesSettlementSimulation:
    settlement_simulation_id: str
    symbol: str
    settlement_type: str = "physical_delivery_simulated"
    settlement_value: float = 0.0
    status: str = "simulated"
    dry_run_only: bool = True
    live_trading_enabled: bool = False
    funds_moved: bool = False
    legal_review_required: bool = True
    compliance_review_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ComputeCapacityIndex:
    index_id: str
    gpu_class: str
    region: str
    index_price: float
    sample_count: int
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUCapacitySpotIndex:
    index_id: str
    gpu_class: str
    region: str
    spot_price: float
    available_units: float
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class GPUForwardCurve:
    curve_id: str
    gpu_class: str
    region: str
    tenors: tuple[str, ...]
    prices: tuple[float, ...]
    dry_run_only: bool = True
    live_trading_enabled: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class ImpliedForwardPrice:
    implied_price_id: str
    symbol: str
    spot_price: float
    carrying_cost: float
    implied_forward_price: float
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class BasisRiskModel:
    model_id: str
    symbol: str
    basis: float
    risk_level: str = "medium"
    dry_run_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class CapacityVolatilityEstimate:
    estimate_id: str
    gpu_class: str
    region: str
    annualized_volatility: float
    sample_count: int
    dry_run_only: bool = True

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
