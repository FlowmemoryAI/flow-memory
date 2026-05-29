"""Simulation-only Flow Memory GPU futures service."""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from .models import (
    DEFAULT_SYMBOL,
    BasisRiskModel,
    CapacityVolatilityEstimate,
    ComputeCapacityIndex,
    GPUCapacitySpotIndex,
    GPUForwardCurve,
    GPUFuturesContractSpec,
    GPUFuturesDeliveryNotice,
    GPUFuturesExpiry,
    GPUFuturesIndexPrice,
    GPUFuturesMarginAccount,
    GPUFuturesMarkPrice,
    GPUFuturesMarket,
    GPUFuturesOrder,
    GPUFuturesOrderBook,
    GPUFuturesPosition,
    GPUFuturesRiskCheck,
    GPUFuturesSettlementSimulation,
    ImpliedForwardPrice,
)

UNSAFE_TOKENS: tuple[str, ...] = (
    "private_key",
    "seed_phrase",
    "seed phrase",
    "mnemonic",
    "secret_key",
    "wallet_private_key",
    "broadcast=true",
    "live_settlement=true",
    "sendtransaction",
    "signtransaction",
    "transfer",
    "withdraw",
    "deposit",
    "custody",
    "mainnet settlement",
    "live futures",
    "leverage",
    "margin",
    "collateral",
)


def default_futures_market_service() -> "FuturesMarketService":
    return FuturesMarketService()


class FuturesMarketService:
    def __init__(self) -> None:
        self.contracts: dict[str, GPUFuturesContractSpec] = {DEFAULT_SYMBOL: GPUFuturesContractSpec()}
        self.orders: dict[str, GPUFuturesOrder] = {}
        self.positions: dict[str, GPUFuturesPosition] = {}

    def markets(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        markets = tuple(
            GPUFuturesMarket(market_id=_stable_id("fmm", symbol), symbol=symbol).as_record()
            for symbol in self.contracts
        )
        return _safe({"ok": True, "markets": markets})

    def contracts_list(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        return _safe({"ok": True, "contracts": tuple(contract.as_record() for contract in self.contracts.values())})

    def contract_create(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        contract = GPUFuturesContractSpec(
            symbol=symbol,
            gpu_class=str(payload.get("gpu_class") or "H100"),
            region=str(payload.get("region") or "us-east"),
            contract_size_gpu_hours=_positive_float(payload.get("contract_size_gpu_hours"), 1.0),
            delivery_start=str(payload.get("delivery_start") or "2027-07-01T00:00:00Z"),
            delivery_end=str(payload.get("delivery_end") or "2027-09-30T23:59:59Z"),
        )
        self.contracts[symbol] = contract
        return _safe({"ok": True, "contract": contract.as_record()})

    def order_book(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        symbol = str(data.get("symbol") or DEFAULT_SYMBOL)
        bids = tuple(order for order in self.orders.values() if order.symbol == symbol and order.side == "buy")
        asks = tuple(order for order in self.orders.values() if order.symbol == symbol and order.side == "sell")
        return _safe({"ok": True, "order_book": GPUFuturesOrderBook(symbol=symbol, bids=bids, asks=asks).as_record()})

    def simulate_order(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        side = str(payload.get("side") or "buy")
        if side not in {"buy", "sell"}:
            return _denial("invalid_side", "Futures simulator side must be buy or sell.", "Use side=buy or side=sell.")
        order = GPUFuturesOrder(
            order_id=_stable_id("fmo", symbol, side, str(payload.get("quantity", "1")), str(payload.get("limit_price", "2.5"))),
            symbol=symbol,
            side=side,
            quantity=_positive_float(payload.get("quantity"), 1.0),
            limit_price=_positive_float(payload.get("limit_price"), 2.5),
        )
        self.orders[order.order_id] = order
        position = GPUFuturesPosition(
            position_id=_stable_id("fmp", symbol, str(payload.get("account_id", "simulated-account"))),
            symbol=symbol,
            account_id=str(payload.get("account_id") or "simulated-account"),
            quantity=order.quantity if side == "buy" else -order.quantity,
            average_price=order.limit_price,
            mark_price=order.limit_price,
            unrealized_pnl=0.0,
        )
        self.positions[position.position_id] = position
        return _safe({"ok": True, "order": order.as_record(), "position": position.as_record()})

    def cancel_order(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        order_id = str(payload.get("order_id") or "")
        order = self.orders.get(order_id)
        if order is None:
            return _denial("unknown_order", "Unknown simulated futures order.", "List the order book before cancelling.")
        cancelled = GPUFuturesOrder(**{**order.as_record(), "status": "simulated_cancelled"})
        self.orders[order_id] = cancelled
        return _safe({"ok": True, "order": cancelled.as_record()})

    def positions_list(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        return _safe({"ok": True, "positions": tuple(position.as_record() for position in self.positions.values())})

    def mark_price(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        index_price = _positive_float(payload.get("index_price"), 2.4)
        mark = _positive_float(payload.get("mark_price"), index_price + 0.1)
        price = GPUFuturesMarkPrice(
            mark_price_id=_stable_id("fmmark", symbol, str(mark), str(index_price)),
            symbol=symbol,
            mark_price=mark,
            index_price=index_price,
            basis=round(mark - index_price, 8),
        )
        return _safe({"ok": True, "mark_price": price.as_record()})

    def index_price(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        price = GPUFuturesIndexPrice(
            index_price_id=_stable_id("fmidx", symbol, str(payload.get("index_price", "2.4"))),
            symbol=symbol,
            index_price=_positive_float(payload.get("index_price"), 2.4),
            sample_count=int(payload.get("sample_count", 3) or 3),
        )
        return _safe({"ok": True, "index_price": price.as_record()})

    def risk_check(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        symbol = str(data.get("symbol") or DEFAULT_SYMBOL)
        risk = GPUFuturesRiskCheck(risk_check_id=_stable_id("fmrisk", symbol), symbol=symbol, max_loss_simulated=0.0)
        margin = GPUFuturesMarginAccount(
            margin_account_id=_stable_id("fmmargin", str(data.get("account_id", "simulated-account"))),
            account_id=str(data.get("account_id") or "simulated-account"),
            simulated_equity=_positive_float(data.get("simulated_equity"), 0.0),
        )
        return _safe({"ok": True, "risk_check": risk.as_record(), "margin_account": margin.as_record()})

    def expiry_simulate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        expiry = GPUFuturesExpiry(
            expiry_id=_stable_id("fmexp", symbol),
            symbol=symbol,
            final_index_price=_positive_float(payload.get("final_index_price"), 2.4),
        )
        return _safe({"ok": True, "expiry": expiry.as_record()})

    def delivery_simulate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        notice = GPUFuturesDeliveryNotice(
            delivery_notice_id=_stable_id("fmdel", symbol),
            symbol=symbol,
            scheduled_gpu_hours=_positive_float(payload.get("scheduled_gpu_hours"), 1.0),
            delivery_start=str(payload.get("delivery_start") or "2027-07-01T00:00:00Z"),
            delivery_end=str(payload.get("delivery_end") or "2027-09-30T23:59:59Z"),
        )
        return _safe({"ok": True, "delivery_notice": notice.as_record()})

    def settlement_simulate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        symbol = str(payload.get("symbol") or DEFAULT_SYMBOL)
        settlement = GPUFuturesSettlementSimulation(
            settlement_simulation_id=_stable_id("fmsettle", symbol),
            symbol=symbol,
            settlement_value=_positive_float(payload.get("settlement_value"), 0.0),
        )
        return _safe({"ok": True, "settlement_simulation": settlement.as_record()})

    def indexes(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        gpu_class = str(data.get("gpu_class") or "H100")
        region = str(data.get("region") or "us-east")
        capacity = ComputeCapacityIndex(
            index_id=_stable_id("capidx", gpu_class, region),
            gpu_class=gpu_class,
            region=region,
            index_price=2.4,
            sample_count=3,
        )
        spot = GPUCapacitySpotIndex(
            index_id=_stable_id("spotidx", gpu_class, region),
            gpu_class=gpu_class,
            region=region,
            spot_price=2.35,
            available_units=128.0,
        )
        return _safe({"ok": True, "capacity_index": capacity.as_record(), "spot_index": spot.as_record()})

    def forward_curve(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        gpu_class = str(data.get("gpu_class") or "H100")
        region = str(data.get("region") or "us-east")
        curve = GPUForwardCurve(
            curve_id=_stable_id("fmcurve", gpu_class, region),
            gpu_class=gpu_class,
            region=region,
            tenors=("spot", "1m", "3m", "6m", "12m"),
            prices=(2.35, 2.42, 2.50, 2.68, 2.9),
        )
        implied = ImpliedForwardPrice(
            implied_price_id=_stable_id("fmifp", gpu_class, region),
            symbol=DEFAULT_SYMBOL,
            spot_price=2.35,
            carrying_cost=0.15,
            implied_forward_price=2.50,
        )
        basis = BasisRiskModel(model_id=_stable_id("fmbasis", gpu_class, region), symbol=DEFAULT_SYMBOL, basis=0.15)
        vol = CapacityVolatilityEstimate(
            estimate_id=_stable_id("fmvol", gpu_class, region),
            gpu_class=gpu_class,
            region=region,
            annualized_volatility=0.42,
            sample_count=12,
        )
        return _safe(
            {
                "ok": True,
                "forward_curve": curve.as_record(),
                "implied_forward_price": implied.as_record(),
                "basis_risk": basis.as_record(),
                "volatility": vol.as_record(),
            }
        )

    def _assert_safe_payload(self, payload: Mapping[str, Any]) -> None:
        flattened = _flatten_payload(payload).lower()
        for token in UNSAFE_TOKENS:
            if token in flattened:
                raise ValueError(f"unsafe futures simulator payload rejected: {token}")
        if bool(payload.get("live_futures", False)):
            raise ValueError("unsafe futures simulator payload rejected: live_futures")
        if bool(payload.get("margin", False)):
            raise ValueError("unsafe futures simulator payload rejected: margin")
        if bool(payload.get("leverage", False)):
            raise ValueError("unsafe futures simulator payload rejected: leverage")


def _safe(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(payload),
        "dry_run_only": True,
        "live_trading_enabled": False,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "legal_review_required": True,
        "compliance_review_required": True,
        "not_investment_advice": True,
    }


def _denial(code: str, message: str, next_safe_action: str) -> dict[str, Any]:
    return _safe({"ok": False, "error": {"code": code, "message": message, "next_safe_action": next_safe_action}})


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _flatten_payload(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_flatten_payload(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_payload(item) for item in value)
    return str(value)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
