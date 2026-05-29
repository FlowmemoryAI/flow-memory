"""Simulation-only Flow Memory GPU futures service."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from hashlib import sha256
from typing import Any, TypeVar, cast

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
    "wallet_private_key",
    "private_key",
    "seed_phrase",
    "seed phrase",
    "mnemonic",
    "secret_key",
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

_T = TypeVar("_T")


def default_futures_market_service() -> "FuturesMarketService":
    return FuturesMarketService()


class FuturesMarketService:
    def __init__(self, *, store: Any | None = None) -> None:
        self.store = store
        self.contracts: dict[str, GPUFuturesContractSpec] = {DEFAULT_SYMBOL: GPUFuturesContractSpec()}
        self.orders: dict[str, GPUFuturesOrder] = {}
        self.positions: dict[str, GPUFuturesPosition] = {}
        self.audit_events: list[dict[str, Any]] = []
        self._persist_seed_records()
        self._load_persisted_records()

    def _persist_seed_records(self) -> None:
        for contract in self.contracts.values():
            self._persist(
                "futures_contract_spec",
                contract.symbol,
                contract.as_record(),
                route_id=contract.symbol,
                status="simulated",
                expires_at=contract.delivery_end,
            )

    def _load_persisted_records(self) -> None:
        for contract in self._load_records("futures_contract_spec", GPUFuturesContractSpec):
            self.contracts[contract.symbol] = contract
        for order in self._load_records("futures_order_simulated", GPUFuturesOrder):
            self.orders[order.order_id] = order
        for position in self._load_records("futures_position_simulated", GPUFuturesPosition):
            self.positions[position.position_id] = position

    def _load_records(self, record_type: str, model_type: type[_T]) -> tuple[_T, ...]:
        if self.store is None:
            return ()
        page = self.store.list_records(record_type, limit=500, include_archived=True)
        return tuple(_dataclass_from_record(model_type, record) for record in page.records if isinstance(record, Mapping))

    def _persist(self, record_type: str, record_id: str, payload: Mapping[str, Any], **metadata: Any) -> None:
        if self.store is None:
            return
        self.store.put_record(record_type, record_id, payload, **metadata)

    def _audit(self, event_type: str, **fields: Any) -> None:
        sequence_hint = len(self.audit_events)
        if self.store is not None:
            count_records = getattr(self.store, "count_records", None)
            if callable(count_records):
                sequence_hint = int(count_records("audit_event"))
        event = {
            "audit_event_id": _stable_id("futaud", event_type, str(sequence_hint), str(fields)),
            "event_type": event_type,
            "action": event_type,
            "result": str(fields.pop("result", "simulated")),
            "dry_run_only": True,
            "funds_moved": False,
            "live_trading_enabled": False,
            **fields,
        }
        self.audit_events.append(event)
        if self.store is not None:
            append_audit_event = getattr(self.store, "append_audit_event", None)
            if callable(append_audit_event):
                append_audit_event(event, chain_id="futures-simulator")

    def markets(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        market_records = []
        for symbol in self.contracts:
            market = GPUFuturesMarket(market_id=_stable_id("fmm", symbol), symbol=symbol)
            market_records.append(market.as_record())
            self._persist("futures_market", market.market_id, market.as_record(), route_id=symbol, status="simulated")
        return _safe({"ok": True, "markets": tuple(market_records)})

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
        self._persist(
            "futures_contract_spec",
            contract.symbol,
            contract.as_record(),
            route_id=contract.symbol,
            status="simulated",
            expires_at=contract.delivery_end,
        )
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
        self._persist(
            "futures_order_simulated",
            order.order_id,
            order.as_record(),
            route_id=order.symbol,
            actor_id=position.account_id,
            status=order.status,
            idempotency_key=str(payload.get("idempotency_key") or order.order_id),
        )
        self._persist(
            "futures_position_simulated",
            position.position_id,
            position.as_record(),
            route_id=position.symbol,
            actor_id=position.account_id,
            status="simulated",
        )
        self._audit(
            "futures.order.simulated",
            order_id=order.order_id,
            position_id=position.position_id,
            route_id=order.symbol,
            actor_id=position.account_id,
        )
        return _safe({"ok": True, "order": order.as_record(), "position": position.as_record()})

    def cancel_order(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        order_id = str(payload.get("order_id") or "")
        order = self.orders.get(order_id)
        if order is None:
            return _denial("unknown_order", "Unknown simulated futures order.", "List the order book before cancelling.")
        cancelled = GPUFuturesOrder(**{**order.as_record(), "status": "simulated_cancelled"})
        self.orders[order_id] = cancelled
        self._persist(
            "futures_order_simulated",
            cancelled.order_id,
            cancelled.as_record(),
            route_id=cancelled.symbol,
            status=cancelled.status,
        )
        self._audit("futures.order.cancelled", order_id=cancelled.order_id, route_id=cancelled.symbol)
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
        self._persist(
            "futures_mark_price",
            price.mark_price_id,
            price.as_record(),
            route_id=price.symbol,
            status="simulated",
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
        self._persist(
            "futures_index_price",
            price.index_price_id,
            price.as_record(),
            route_id=price.symbol,
            status="simulated",
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
        self._persist(
            "futures_risk_check",
            risk.risk_check_id,
            risk.as_record(),
            route_id=risk.symbol,
            status="simulated",
        )
        self._persist(
            "futures_margin_account_simulated",
            margin.margin_account_id,
            margin.as_record(),
            actor_id=margin.account_id,
            status="simulated",
        )
        self._audit(
            "futures.risk_check.simulated",
            risk_check_id=risk.risk_check_id,
            margin_account_id=margin.margin_account_id,
            route_id=risk.symbol,
            actor_id=margin.account_id,
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
        self._persist(
            "futures_expiry",
            expiry.expiry_id,
            expiry.as_record(),
            route_id=expiry.symbol,
            status="simulated",
        )
        self._audit("futures.expiry.simulated", expiry_id=expiry.expiry_id, route_id=expiry.symbol)
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
        self._persist(
            "futures_delivery_notice",
            notice.delivery_notice_id,
            notice.as_record(),
            route_id=notice.symbol,
            status="simulated",
            expires_at=notice.delivery_end,
        )
        self._audit(
            "futures.delivery.simulated",
            delivery_notice_id=notice.delivery_notice_id,
            route_id=notice.symbol,
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
        self._persist(
            "futures_settlement_simulation",
            settlement.settlement_simulation_id,
            settlement.as_record(),
            route_id=settlement.symbol,
            status="simulated",
        )
        self._audit(
            "futures.settlement.simulated",
            settlement_simulation_id=settlement.settlement_simulation_id,
            route_id=settlement.symbol,
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
        self._persist(
            "compute_capacity_index",
            capacity.index_id,
            capacity.as_record(),
            status="simulated",
        )
        self._persist(
            "gpu_capacity_spot_index",
            spot.index_id,
            spot.as_record(),
            status="simulated",
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
        self._persist(
            "gpu_forward_curve",
            curve.curve_id,
            curve.as_record(),
            status="simulated",
        )
        self._persist(
            "implied_forward_price",
            implied.implied_price_id,
            implied.as_record(),
            route_id=implied.symbol,
            status="simulated",
        )
        self._persist(
            "basis_risk_model",
            basis.model_id,
            basis.as_record(),
            route_id=basis.symbol,
            status="simulated",
        )
        self._persist(
            "capacity_volatility_estimate",
            vol.estimate_id,
            vol.as_record(),
            status="simulated",
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


def _dataclass_from_record(model_type: type[_T], record: Mapping[str, Any]) -> _T:
    allowed = {field.name for field in fields(cast(Any, model_type))}
    constructor = cast(Any, model_type)
    return cast(_T, constructor(**{key: value for key, value in record.items() if key in allowed}))

def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
