"""Dry-run capacity and forward-capacity market simulator."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from hashlib import sha256
from typing import Any, TypeVar, cast

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
)
UNSAFE_WORD_TOKENS = frozenset(("transfer", "withdraw", "deposit", "custody", "leverage", "margin"))


_T = TypeVar("_T")


def default_capacity_market_service() -> "CapacityMarketService":
    return CapacityMarketService.seeded()


class CapacityMarketService:
    def __init__(self, windows: tuple[CapacityWindow, ...] = (), *, store: Any | None = None) -> None:
        self.store = store
        self.windows: dict[str, CapacityWindow] = {window.capacity_window_id: window for window in windows}
        self.holds: dict[str, CapacityHold] = {}
        self.reservations: dict[str, CapacityReservation] = {}
        self.forward_contracts: dict[str, ForwardCapacityContract] = {}
        self.audit_events: list[dict[str, Any]] = []
        self._persist_seed_records()
        self._load_persisted_records()

    @classmethod
    def seeded(cls, *, store: Any | None = None) -> "CapacityMarketService":
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
            ),
            store=store,
        )

    def _persist_seed_records(self) -> None:
        for window in self.windows.values():
            if self._record_exists("capacity_window", window.capacity_window_id):
                continue
            self._persist_window(window)

    def _record_exists(self, record_type: str, record_id: str) -> bool:
        if self.store is None:
            return False
        get_record = getattr(self.store, "get_record", None)
        return bool(callable(get_record) and get_record(record_type, record_id) is not None)

    def _persist_window(self, window: CapacityWindow) -> None:
        self._persist(
            "capacity_window",
            window.capacity_window_id,
            window.as_record(),
            provider_id=window.provider_id,
            status=window.status,
            expires_at=window.ends_at,
        )

    def _load_persisted_records(self) -> None:
        for window in self._load_records("capacity_window", CapacityWindow):
            self.windows[window.capacity_window_id] = window
        for hold in self._load_records("capacity_hold", CapacityHold):
            self.holds[hold.hold_id] = hold
        for reservation in self._load_records("capacity_reservation", CapacityReservation):
            self.reservations[reservation.reservation_id] = reservation
        for contract in self._load_records("forward_capacity_contract", ForwardCapacityContract):
            self.forward_contracts[contract.contract_id] = contract

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
            "audit_event_id": _stable_id("capaud", event_type, str(sequence_hint), str(fields)),
            "event_type": event_type,
            "action": event_type,
            "result": str(fields.pop("result", "simulated")),
            "dry_run_only": True,
            "funds_moved": False,
            **fields,
        }
        self.audit_events.append(event)
        if self.store is not None:
            append_audit_event = getattr(self.store, "append_audit_event", None)
            if callable(append_audit_event):
                append_audit_event(event, chain_id="capacity-market")

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
        self._persist(
            "capacity_inventory",
            inventory.inventory_id,
            inventory.as_record(),
            status="recorded",
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
        quote_data = {
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
        }
        self._persist(
            "capacity_quote",
            str(quote_data["quote_id"]),
            quote_data,
            provider_id=window.provider_id,
            status="quoted",
            expires_at=window.ends_at,
        )
        return {
            "ok": True,
            "quote": quote_data,
            "dry_run_only": True,
            "funds_moved": False,
        }

    def hold(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        requested_gpu_class = str(payload.get("gpu_class") or payload.get("gpu_type") or GPUClass.H100.value)
        requested_region = str(payload.get("region") or "us-east")
        requested_units = _positive_float(payload.get("hours", payload.get("capacity_units")), 1.0)
        requested_route_id = str(payload.get("route_id") or "capacity-route")
        for existing_hold in self.holds.values():
            if existing_hold.status != "held" or existing_hold.route_id != requested_route_id:
                continue
            existing_window = self.windows.get(existing_hold.capacity_window_id)
            if (
                existing_window is not None
                and existing_window.gpu_class == requested_gpu_class
                and existing_window.region == requested_region
                and existing_hold.capacity_units == requested_units
            ):
                return {"ok": True, "hold": existing_hold.as_record(), "dry_run_only": True, "funds_moved": False}
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
        duplicate_hold = self.holds.get(hold.hold_id)
        if duplicate_hold is not None and duplicate_hold.status == "held":
            return {"ok": True, "hold": duplicate_hold.as_record(), "dry_run_only": True, "funds_moved": False}

        window = self.windows.get(hold.capacity_window_id)
        if window is None:
            return _denial("unknown_capacity_window", "Quoted capacity window is no longer available.", "Request a fresh capacity quote.")
        if hold.capacity_units <= 0:
            return _denial("invalid_capacity_units", "Capacity hold must reserve positive units.", "Request at least one capacity unit.")
        if window.available_units < hold.capacity_units:
            return _denial("insufficient_capacity", "Capacity was consumed before the hold could be created.", "Request a fresh quote for a smaller size.")

        remaining_units = round(window.available_units - hold.capacity_units, 8)
        updated_window = CapacityWindow(
            **{
                **window.as_record(),
                "available_units": remaining_units,
                "status": "held" if remaining_units <= 0 else "available",
            }
        )
        self.windows[updated_window.capacity_window_id] = updated_window
        self._persist_window(updated_window)
        self.holds[hold.hold_id] = hold
        self._persist(
            "capacity_hold",
            hold.hold_id,
            hold.as_record(),
            provider_id=hold.provider_id,
            route_id=hold.route_id,
            status=hold.status,
            expires_at=hold.hold_expires_at,
        )
        self._audit("capacity.hold.simulated", hold_id=hold.hold_id, provider_id=hold.provider_id, route_id=hold.route_id)
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
        self._persist(
            "capacity_reservation",
            reservation.reservation_id,
            reservation.as_record(),
            provider_id=reservation.provider_id,
            route_id=reservation.route_id,
            status=reservation.status,
            expires_at=reservation.reserved_until,
        )
        self._audit(
            "capacity.reserve.simulated",
            reservation_id=reservation.reservation_id,
            provider_id=reservation.provider_id,
            route_id=reservation.route_id,
        )
        return {"ok": True, "reservation": reservation.as_record(), "dry_run_only": True, "funds_moved": False}

    def release(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        reservation_id = str(payload.get("reservation_id") or "")
        reservation = self.reservations.get(reservation_id)
        if reservation is None:
            return _denial("unknown_reservation", "Unknown dry-run reservation.", "List reservations before release.")
        if reservation.status == "released":
            return {"ok": True, "reservation": reservation.as_record(), "dry_run_only": True, "funds_moved": False}

        hold = self.holds.get(reservation.hold_id)
        if hold is None:
            return _denial("unknown_hold", "Reservation hold is missing, so capacity cannot be safely restored.", "Inspect reservation history before retrying release.")

        window = self.windows.get(hold.capacity_window_id)
        if window is None:
            return _denial("unknown_capacity_window", "Reservation capacity window is missing, so capacity cannot be safely restored.", "Inspect capacity window history before retrying release.")

        restored_units = round(window.available_units + reservation.capacity_units, 8)
        restored_window = CapacityWindow(
            **{
                **window.as_record(),
                "available_units": restored_units,
                "status": "available",
            }
        )
        released_hold = CapacityHold(**{**hold.as_record(), "status": "released"})
        released = CapacityReservation(**{**reservation.as_record(), "status": "released"})
        self.windows[restored_window.capacity_window_id] = restored_window
        self.holds[released_hold.hold_id] = released_hold
        self.reservations[reservation_id] = released
        self._persist_window(restored_window)
        self._persist(
            "capacity_hold",
            released_hold.hold_id,
            released_hold.as_record(),
            provider_id=released_hold.provider_id,
            route_id=released_hold.route_id,
            status=released_hold.status,
            expires_at=released_hold.hold_expires_at,
        )
        self._persist(
            "capacity_reservation",
            released.reservation_id,
            released.as_record(),
            provider_id=released.provider_id,
            route_id=released.route_id,
            status=released.status,
            expires_at=released.reserved_until,
        )
        self._audit(
            "capacity.release.simulated",
            reservation_id=released.reservation_id,
            provider_id=released.provider_id,
            route_id=released.route_id,
        )
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
            active_reservations = tuple(
                item for item in self.reservations.values()
                if item.provider_id == window.provider_id and item.status not in {"released", "cancelled", "expired"}
            )
            released_reservations = tuple(
                item for item in self.reservations.values()
                if item.provider_id == window.provider_id and item.status == "released"
            )
            reserved = sum(item.capacity_units for item in active_reservations)
            released = sum(item.capacity_units for item in released_reservations)
            total_booked = reserved + window.available_units
            record = CapacityUtilizationRecord(
                utilization_id=_stable_id("capu", window.capacity_window_id, str(reserved), str(released)),
                provider_id=window.provider_id,
                capacity_window_id=window.capacity_window_id,
                reserved_units=reserved,
                consumed_units=0.0,
                released_units=released,
                utilization_rate=reserved / total_booked if total_booked else 0.0,
            )
            records.append(record.as_record())
            self._persist(
                "capacity_utilization_record",
                record.utilization_id,
                record.as_record(),
                provider_id=record.provider_id,
                status="recorded",
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
        quote_data = {
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
        }
        self._persist(
            "forward_capacity_quote",
            str(quote_data["quote_id"]),
            quote_data,
            status="quoted",
            expires_at=str(quote_data["delivery_end"]),
        )
        return {
            "ok": True,
            "forward_quote": quote_data,
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
        self._persist(
            "forward_capacity_contract",
            contract.contract_id,
            contract.as_record(),
            provider_id=contract.provider_id,
            actor_id=contract.buyer_id,
            status=contract.status,
            expires_at=contract.delivery_end,
        )
        self._audit(
            "capacity.forward.drafted",
            contract_id=contract.contract_id,
            provider_id=contract.provider_id,
            actor_id=contract.buyer_id,
        )
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
        self._persist(
            "forward_capacity_settlement_plan",
            settlement.settlement_plan_id,
            settlement.as_record(),
            status="simulated",
        )
        self._persist(
            "forward_capacity_risk_assessment",
            risk.risk_assessment_id,
            risk.as_record(),
            status="simulated",
        )
        self._audit(
            "capacity.forward.simulated",
            contract_id=contract_id,
            settlement_plan_id=settlement.settlement_plan_id,
            risk_assessment_id=risk.risk_assessment_id,
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
        self._persist(
            "forward_capacity_delivery_schedule",
            schedule.schedule_id,
            schedule.as_record(),
            status="simulated",
            expires_at=schedule.delivery_end,
        )
        self._audit("capacity.forward.delivery_simulated", schedule_id=schedule.schedule_id, contract_id=contract_id)
        return {"ok": True, "delivery_schedule": schedule.as_record(), "dry_run_only": True, "funds_moved": False}

    def _assert_safe_payload(self, payload: Mapping[str, Any]) -> None:
        flattened = _flatten_payload(payload).lower()
        padded_flattened = f" {flattened} "
        for token in UNSAFE_TOKENS:
            if _contains_unsafe_token(flattened, padded_flattened, token):
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

def _contains_unsafe_token(flattened: str, padded_flattened: str, token: str) -> bool:
    if token in UNSAFE_WORD_TOKENS:
        return f" {token} " in padded_flattened
    return token in flattened


def _dataclass_from_record(model_type: type[_T], record: Mapping[str, Any]) -> _T:
    allowed = {field.name for field in fields(cast(Any, model_type))}
    constructor = cast(Any, model_type)
    return cast(_T, constructor(**{key: value for key, value in record.items() if key in allowed}))

def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
