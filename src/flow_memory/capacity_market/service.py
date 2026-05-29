"""Dry-run capacity and forward-capacity market simulator."""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from .models import (
    CapacityHold,
    CapacityInventory,
    CapacityReservation,
    CapacityUtilizationRecord,
    CapacityWindow,
    ForwardCapacityContract,
    ForwardCapacityDeliverySchedule,
    ForwardCapacityRiskAssessment,
    ForwardCapacitySettlementPlan,
    GPUClass,
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
)


def default_capacity_market_service() -> "CapacityMarketService":
    return CapacityMarketService.seeded()


class CapacityMarketService:
    def __init__(self, windows: tuple[CapacityWindow, ...] = ()) -> None:
        self.windows: dict[str, CapacityWindow] = {window.capacity_window_id: window for window in windows}
        self.holds: dict[str, CapacityHold] = {}
        self.reservations: dict[str, CapacityReservation] = {}
        self.forward_contracts: dict[str, ForwardCapacityContract] = {}
        self.audit_events: list[dict[str, Any]] = []

    @classmethod
    def seeded(cls) -> "CapacityMarketService":
        return cls(
            windows=(
                CapacityWindow(
                    capacity_window_id="capwin-h100-useast-001",
                    provider_id="gpu-provider-1",
                    gpu_class=GPUClass.H100.value,
                    available_units=128.0,
                    region="us-east",
                    starts_at="2026-06-01T00:00:00Z",
                    ends_at="2026-06-08T00:00:00Z",
                    price_floor=2.4,
                ),
                CapacityWindow(
                    capacity_window_id="capwin-l40s-useast-001",
                    provider_id="gpu-provider-2",
                    gpu_class=GPUClass.L40S.value,
                    available_units=320.0,
                    region="us-east",
                    starts_at="2026-06-01T00:00:00Z",
                    ends_at="2026-06-08T00:00:00Z",
                    price_floor=0.8,
                ),
            )
        )

    def inventory(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        gpu_class = str(data.get("gpu_class") or data.get("gpu_type") or "")
        region = str(data.get("region") or "")
        windows = tuple(
            window for window in self.windows.values()
            if (not gpu_class or window.gpu_class == gpu_class) and (not region or window.region == region)
        )
        inventory = CapacityInventory(
            inventory_id=_stable_id("capinv", gpu_class, region, str(len(windows))),
            windows=windows,
            total_available_units=sum(window.available_units for window in windows),
        )
        return {"ok": True, "inventory": inventory.as_record(), "dry_run_only": True, "funds_moved": False}

    def quote(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        gpu_class = str(payload.get("gpu_class") or payload.get("gpu_type") or GPUClass.H100.value)
        region = str(payload.get("region") or "us-east")
        units = _positive_float(payload.get("hours", payload.get("capacity_units")), 1.0)
        candidates = [
            window for window in self.windows.values()
            if window.gpu_class == gpu_class and window.region == region and window.available_units >= units
        ]
        if not candidates:
            return _denial("insufficient_capacity", "No dry-run capacity window can satisfy the request.", "Try a smaller size or different GPU class.")
        window = min(candidates, key=lambda item: item.price_floor)
        return {
            "ok": True,
            "quote": {
                "quote_id": _stable_id("capq", window.capacity_window_id, str(units)),
                "capacity_window_id": window.capacity_window_id,
                "provider_id": window.provider_id,
                "gpu_class": window.gpu_class,
                "region": window.region,
                "unit_type": window.resource_type,
                "capacity_units": units,
                "unit_price": window.price_floor,
                "estimated_total_cost": round(units * window.price_floor, 8),
                "dry_run_only": True,
                "funds_moved": False,
                "legally_binding": False,
            },
            "dry_run_only": True,
            "funds_moved": False,
        }

    def hold(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        quote = self.quote(payload)
        if not bool(quote.get("ok", False)):
            return quote
        raw_quote = quote.get("quote", {})
        quote_data = raw_quote if isinstance(raw_quote, Mapping) else {}
        hold = CapacityHold(
            hold_id=_stable_id("caph", str(quote_data.get("quote_id", ""))),
            capacity_window_id=str(quote_data.get("capacity_window_id", "")),
            provider_id=str(quote_data.get("provider_id", "")),
            route_id=str(payload.get("route_id") or "capacity-route"),
            capacity_units=float(quote_data.get("capacity_units", 0.0) or 0.0),
            unit_type=str(quote_data.get("unit_type", "gpu_hour")),
        )
        self.holds[hold.hold_id] = hold
        self.audit_events.append({"event_type": "capacity.hold.simulated", "hold_id": hold.hold_id})
        return {"ok": True, "hold": hold.as_record(), "dry_run_only": True, "funds_moved": False}

    def reserve(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        held = self.hold(payload)
        if not bool(held.get("ok", False)):
            return held
        raw_hold = held.get("hold", {})
        hold_data = raw_hold if isinstance(raw_hold, Mapping) else {}
        reservation = CapacityReservation(
            reservation_id=_stable_id("capr", str(hold_data.get("hold_id", ""))),
            hold_id=str(hold_data.get("hold_id", "")),
            provider_id=str(hold_data.get("provider_id", "")),
            route_id=str(hold_data.get("route_id", "")),
            capacity_units=float(hold_data.get("capacity_units", 0.0) or 0.0),
            unit_type=str(hold_data.get("unit_type", "gpu_hour")),
            reserved_from=str(payload.get("reserved_from") or payload.get("starts_at") or "2026-06-01T00:00:00Z"),
            reserved_until=str(payload.get("reserved_until") or payload.get("ends_at") or "2026-06-08T00:00:00Z"),
        )
        self.reservations[reservation.reservation_id] = reservation
        self.audit_events.append({"event_type": "capacity.reserve.simulated", "reservation_id": reservation.reservation_id})
        return {"ok": True, "reservation": reservation.as_record(), "dry_run_only": True, "funds_moved": False}

    def release(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        reservation_id = str(payload.get("reservation_id") or "")
        reservation = self.reservations.get(reservation_id)
        if reservation is None:
            return _denial("unknown_reservation", "Unknown dry-run reservation.", "List reservations before release.")
        released = CapacityReservation(**{**reservation.as_record(), "status": "released"})
        self.reservations[reservation_id] = released
        return {"ok": True, "reservation": released.as_record(), "dry_run_only": True, "funds_moved": False}

    def reservations_list(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        return {
            "ok": True,
            "reservations": tuple(item.as_record() for item in self.reservations.values()),
            "dry_run_only": True,
            "funds_moved": False,
        }

    def utilization(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        records = []
        for window in self.windows.values():
            reserved = sum(item.capacity_units for item in self.reservations.values() if item.provider_id == window.provider_id)
            records.append(
                CapacityUtilizationRecord(
                    utilization_id=_stable_id("capu", window.capacity_window_id, str(reserved)),
                    provider_id=window.provider_id,
                    capacity_window_id=window.capacity_window_id,
                    reserved_units=reserved,
                    consumed_units=0.0,
                    released_units=0.0,
                    utilization_rate=reserved / window.available_units if window.available_units else 0.0,
                ).as_record()
            )
        return {"ok": True, "utilization": tuple(records), "dry_run_only": True, "funds_moved": False}

    def order_book(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        inventory = self.inventory(payload)
        return {
            "ok": True,
            "capacity_windows": tuple(window.as_record() for window in self.windows.values()),
            "reservations": tuple(item.as_record() for item in self.reservations.values()),
            "summary": inventory.get("inventory", {}),
            "dry_run_only": True,
            "funds_moved": False,
        }

    def forward_quote(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        units = _positive_float(payload.get("hours", payload.get("capacity_units")), 100.0)
        unit_price = _positive_float(payload.get("unit_price"), 2.5)
        return {
            "ok": True,
            "forward_quote": {
                "quote_id": _stable_id("fwq", str(payload.get("gpu_class", GPUClass.H100.value)), str(units), str(unit_price)),
                "gpu_class": str(payload.get("gpu_class") or payload.get("gpu_type") or GPUClass.H100.value),
                "region": str(payload.get("region") or "us-east"),
                "capacity_units": units,
                "unit_type": str(payload.get("unit_type") or "gpu_hour"),
                "unit_price": unit_price,
                "estimated_notional_value": round(units * unit_price, 8),
                "delivery_start": str(payload.get("delivery_start") or "2027-07-01T00:00:00Z"),
                "delivery_end": str(payload.get("delivery_end") or "2027-09-30T23:59:59Z"),
                "dry_run_only": True,
                "funds_moved": False,
                "legally_binding": False,
                "legal_review_required": True,
                "compliance_review_required": True,
            },
            "dry_run_only": True,
            "funds_moved": False,
            "legal_review_required": True,
            "compliance_review_required": True,
        }

    def forward_draft(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        quote = self.forward_quote(payload)
        raw_quote = quote.get("forward_quote", {})
        quote_data = raw_quote if isinstance(raw_quote, Mapping) else {}
        contract = ForwardCapacityContract(
            contract_id=_stable_id("fwc", str(quote_data.get("quote_id", "")), str(payload.get("buyer_id", "buyer"))),
            contract_type=str(payload.get("contract_type") or "bilateral_forward"),
            buyer_id=str(payload.get("buyer_id") or "buyer-simulated"),
            provider_id=str(payload.get("provider_id") or "gpu-provider-1"),
            gpu_class=str(quote_data.get("gpu_class", GPUClass.H100.value)),
            region=str(quote_data.get("region", "us-east")),
            unit_type=str(quote_data.get("unit_type", "gpu_hour")),
            capacity_units=float(quote_data.get("capacity_units", 0.0) or 0.0),
            unit_price=float(quote_data.get("unit_price", 0.0) or 0.0),
            delivery_start=str(quote_data.get("delivery_start", "")),
            delivery_end=str(quote_data.get("delivery_end", "")),
        )
        self.forward_contracts[contract.contract_id] = contract
        return {"ok": True, "contract": contract.as_record(), "dry_run_only": True, "funds_moved": False}

    def forward_simulate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        drafted = self.forward_draft(payload)
        contract_raw = drafted.get("contract", {})
        contract = contract_raw if isinstance(contract_raw, Mapping) else {}
        contract_id = str(contract.get("contract_id", ""))
        settlement = ForwardCapacitySettlementPlan(
            settlement_plan_id=_stable_id("fws", contract_id),
            contract_id=contract_id,
            estimated_notional_value=round(float(contract.get("capacity_units", 0.0) or 0.0) * float(contract.get("unit_price", 0.0) or 0.0), 8),
        )
        risk = ForwardCapacityRiskAssessment(
            risk_assessment_id=_stable_id("fwr", contract_id),
            contract_id=contract_id,
            warnings=("simulation_only", "legal_review_required", "compliance_review_required"),
        )
        return {
            "ok": True,
            "contract": contract,
            "settlement_plan": settlement.as_record(),
            "risk_assessment": risk.as_record(),
            "dry_run_only": True,
            "funds_moved": False,
            "live_trading_enabled": False,
            "legal_review_required": True,
            "compliance_review_required": True,
        }

    def forward_simulate_delivery(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        contract_id = str(payload.get("contract_id") or "contract-simulated")
        schedule = ForwardCapacityDeliverySchedule(
            schedule_id=_stable_id("fwd", contract_id),
            contract_id=contract_id,
            delivery_start=str(payload.get("delivery_start") or "2027-07-01T00:00:00Z"),
            delivery_end=str(payload.get("delivery_end") or "2027-09-30T23:59:59Z"),
            scheduled_units=_positive_float(payload.get("capacity_units"), 100.0),
        )
        return {"ok": True, "delivery_schedule": schedule.as_record(), "dry_run_only": True, "funds_moved": False}

    def _assert_safe_payload(self, payload: Mapping[str, Any]) -> None:
        flattened = _flatten_payload(payload).lower()
        for token in UNSAFE_TOKENS:
            if token in flattened:
                raise ValueError(f"unsafe capacity market payload rejected: {token}")
        if bool(payload.get("live_futures", False)) or bool(payload.get("live_settlement", False)):
            raise ValueError("unsafe capacity market payload rejected: live mode")


def _denial(code: str, message: str, next_safe_action: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "next_safe_action": next_safe_action},
        "dry_run_only": True,
        "funds_moved": False,
        "legally_binding": False,
    }


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
