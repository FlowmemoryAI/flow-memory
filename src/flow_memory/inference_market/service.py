"""Dry-run Flow Memory Inference Market service."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields
from hashlib import sha256
from typing import Any, TypeVar, cast

from .models import (
    AgentInferenceDecision,
    CreditUnit,
    InferenceCreditAccount,
    InferenceCreditBalance,
    InferenceCreditLedgerEntry,
    InferenceCreditFill,
    InferenceCreditListing,
    InferenceCreditOrder,
    InferenceCreditSource,
    InferenceDemandSnapshot,
    InferenceMarketPolicy,
    InferencePriceSnapshot,
    InferenceQuote,
    InferenceRoute,
    InferenceUsageRecord,
    ListingStatus,
    OpportunityCostDecision,
    OrderStatus,
    RunVsSellAnalysis,
    SourceType,
)

UNSAFE_PAYLOAD_TOKENS: tuple[str, ...] = (
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

_T = TypeVar("_T")


def default_inference_market_service() -> "InferenceMarketService":
    return InferenceMarketService.seeded()


class InferenceMarketService:
    """Deterministic in-process inference resale market.

    The service is intentionally provider-SDK-free and payment-SDK-free. It is
    suitable for API tests, CLI smoke tests, and local planning while external
    provider credentials are absent.
    """

    def __init__(
        self,
        sources: Iterable[InferenceCreditSource] = (),
        accounts: Iterable[InferenceCreditAccount] = (),
        balances: Iterable[InferenceCreditBalance] = (),
        listings: Iterable[InferenceCreditListing] = (),
        *,
        store: Any | None = None,
    ) -> None:
        self.store = store
        self.sources: dict[str, InferenceCreditSource] = {source.source_id: source for source in sources}
        self.accounts: dict[str, InferenceCreditAccount] = {account.account_id: account for account in accounts}
        self.balances: dict[str, InferenceCreditBalance] = {balance.balance_id: balance for balance in balances}
        self.listings: dict[str, InferenceCreditListing] = {listing.listing_id: listing for listing in listings}
        self.orders: dict[str, InferenceCreditOrder] = {}
        self.fills: dict[str, InferenceCreditFill] = {}
        self.usage_records: dict[str, InferenceUsageRecord] = {}
        self.ledger_entries: dict[str, InferenceCreditLedgerEntry] = {}
        self.price_snapshots: dict[str, InferencePriceSnapshot] = {}
        self.audit_events: list[dict[str, Any]] = []
        self.demand_snapshots: dict[str, InferenceDemandSnapshot] = {}
        self._persist_seed_records()
        self._load_persisted_records()

    @classmethod
    def seeded(cls, *, store: Any | None = None) -> "InferenceMarketService":
        sources = (
            InferenceCreditSource(
                source_id="src-discount-openai-compatible",
                source_name="Discount OpenAI-compatible pool",
                source_type=SourceType.OPENAI_COMPATIBLE.value,
                status="active",
                verified=True,
                models=("gpt-4o-mini", "gpt-4.1-mini", "flow-local-small"),
                base_url="https://providers.flowmemory.ai/openai-compatible",
                credential_ref="secret://inference/src-discount-openai-compatible",
                transferable=True,
                seller_id="seller-unused-daily-credits",
                quality_score=0.92,
                reliability_score=0.98,
            ),
            InferenceCreditSource(
                source_id="src-discount-anthropic-compatible",
                source_name="Discount Anthropic-compatible pool",
                source_type=SourceType.ANTHROPIC_COMPATIBLE.value,
                status="active",
                verified=True,
                models=("claude-3-5-haiku", "flow-local-small"),
                base_url="https://providers.flowmemory.ai/anthropic-compatible",
                credential_ref="secret://inference/src-discount-anthropic-compatible",
                transferable=True,
                seller_id="seller-unused-anthropic-credits",
                quality_score=0.9,
                reliability_score=0.97,
            ),
            InferenceCreditSource(
                source_id="src-local-no-payment",
                source_name="Flow Memory local fake provider",
                source_type=SourceType.LOCAL.value,
                status="active",
                verified=True,
                models=("flow-local-small",),
                transferable=False,
                seller_id="flow-memory-local",
                quality_score=0.72,
                reliability_score=1.0,
            ),
            InferenceCreditSource(
                source_id="src-disabled-seller",
                source_name="Disabled seller pool",
                source_type=SourceType.CUSTOM.value,
                status="disabled",
                models=("gpt-4o-mini",),
                transferable=True,
                seller_id="seller-disabled",
            ),
        )
        accounts = (
            InferenceCreditAccount(
                account_id="acct-seller-unused-daily-credits",
                owner_id="seller-unused-daily-credits",
                source_id="src-discount-openai-compatible",
                sell_enabled=True,
            ),
            InferenceCreditAccount(
                account_id="acct-seller-unused-anthropic-credits",
                owner_id="seller-unused-anthropic-credits",
                source_id="src-discount-anthropic-compatible",
                sell_enabled=True,
            ),
            InferenceCreditAccount(
                account_id="acct-local-no-payment",
                owner_id="flow-memory-local",
                source_id="src-local-no-payment",
            ),
            InferenceCreditAccount(
                account_id="acct-disabled-seller",
                owner_id="seller-disabled",
                source_id="src-disabled-seller",
                status="disabled",
                sell_enabled=True,
            ),
        )
        balances = (
            InferenceCreditBalance(
                balance_id="bal-seller-gpt4o-mini-token",
                account_id="acct-seller-unused-daily-credits",
                source_id="src-discount-openai-compatible",
                owner_id="seller-unused-daily-credits",
                model="gpt-4o-mini",
                unit_type=CreditUnit.TOKEN.value,
                available_units=250_000,
                expires_at="2026-05-27T00:00:00Z",
                transferable=True,
            ),
            InferenceCreditBalance(
                balance_id="bal-seller-claude-haiku-request",
                account_id="acct-seller-unused-anthropic-credits",
                source_id="src-discount-anthropic-compatible",
                owner_id="seller-unused-anthropic-credits",
                model="claude-3-5-haiku",
                unit_type=CreditUnit.REQUEST.value,
                available_units=12_000,
                expires_at="2026-05-27T00:00:00Z",
                transferable=True,
            ),
            InferenceCreditBalance(
                balance_id="bal-local-flow-small-request",
                account_id="acct-local-no-payment",
                source_id="src-local-no-payment",
                owner_id="flow-memory-local",
                model="flow-local-small",
                unit_type=CreditUnit.REQUEST.value,
                available_units=10_000,
                transferable=False,
            ),
        )
        listings = (
            InferenceCreditListing(
                listing_id="lst-discount-gpt4o-mini-token",
                seller_id="seller-unused-daily-credits",
                account_id="acct-seller-unused-daily-credits",
                source_id="src-discount-openai-compatible",
                model="gpt-4o-mini",
                unit_type=CreditUnit.TOKEN.value,
                available_units=100_000,
                unit_price=0.00000075,
                currency="USD_CREDIT",
                expires_at="2026-05-27T00:00:00Z",
                transferable=True,
                metadata={"reference_unit_price": 0.000001, "discount_bps": 2500},
            ),
            InferenceCreditListing(
                listing_id="lst-discount-claude-haiku-request",
                seller_id="seller-unused-anthropic-credits",
                account_id="acct-seller-unused-anthropic-credits",
                source_id="src-discount-anthropic-compatible",
                model="claude-3-5-haiku",
                unit_type=CreditUnit.REQUEST.value,
                available_units=12_000,
                unit_price=0.00018,
                currency="USD_CREDIT",
                expires_at="2026-05-27T00:00:00Z",
                transferable=True,
                metadata={"reference_unit_price": 0.00025, "discount_bps": 2800},
            ),
            InferenceCreditListing(
                listing_id="lst-stale-gpt4o-mini-token",
                seller_id="seller-unused-daily-credits",
                account_id="acct-seller-unused-daily-credits",
                source_id="src-discount-openai-compatible",
                model="gpt-4o-mini",
                unit_type=CreditUnit.TOKEN.value,
                available_units=5_000,
                unit_price=0.0000012,
                status=ListingStatus.EXPIRED.value,
                expires_at="2026-05-25T00:00:00Z",
                transferable=True,
            ),
            InferenceCreditListing(
                listing_id="lst-local-flow-small-request",
                seller_id="flow-memory-local",
                account_id="acct-local-no-payment",
                source_id="src-local-no-payment",
                model="flow-local-small",
                unit_type=CreditUnit.REQUEST.value,
                available_units=10_000,
                unit_price=0.0,
                currency="NO_PAYMENT",
                transferable=False,
            ),
        )
        return cls(sources=sources, accounts=accounts, balances=balances, listings=listings, store=store)

    def _persist_seed_records(self) -> None:
        for source in self.sources.values():
            if self._record_exists("inference_credit_source", source.source_id):
                continue
            self._persist(
                "inference_credit_source",
                source.source_id,
                source.as_record(),
                provider_id=source.source_id,
                actor_id=source.seller_id,
                status=source.status,
            )
        for account in self.accounts.values():
            if self._record_exists("inference_credit_account", account.account_id):
                continue
            self._persist(
                "inference_credit_account",
                account.account_id,
                account.as_record(),
                workspace_id=account.workspace_id,
                provider_id=account.source_id,
                actor_id=account.owner_id,
                status=account.status,
            )
        for balance in self.balances.values():
            if self._record_exists("inference_credit_balance", balance.balance_id):
                continue
            self._persist(
                "inference_credit_balance",
                balance.balance_id,
                balance.as_record(),
                provider_id=balance.source_id,
                actor_id=balance.owner_id,
                status="active",
                expires_at=balance.expires_at,
            )
        for listing in self.listings.values():
            if self._record_exists("inference_credit_listing", listing.listing_id):
                continue
            self._persist_listing(listing)

    def _record_exists(self, record_type: str, record_id: str) -> bool:
        if self.store is None:
            return False
        get_record = getattr(self.store, "get_record", None)
        return bool(callable(get_record) and get_record(record_type, record_id) is not None)

    def _load_persisted_records(self) -> None:
        for source in self._load_records("inference_credit_source", InferenceCreditSource):
            self.sources[source.source_id] = source
        for account in self._load_records("inference_credit_account", InferenceCreditAccount):
            self.accounts[account.account_id] = account
        for balance in self._load_records("inference_credit_balance", InferenceCreditBalance):
            self.balances[balance.balance_id] = balance
        for listing in self._load_records("inference_credit_listing", InferenceCreditListing):
            self.listings[listing.listing_id] = listing
        for order in self._load_records("inference_credit_order", InferenceCreditOrder):
            self.orders[order.order_id] = order
        for fill in self._load_records("inference_credit_fill", InferenceCreditFill):
            self.fills[fill.fill_id] = fill
        for ledger_entry in self._load_records("inference_credit_ledger_entry", InferenceCreditLedgerEntry):
            self.ledger_entries[ledger_entry.ledger_entry_id] = ledger_entry
        for usage in self._load_records("inference_usage_record", InferenceUsageRecord):
            self.usage_records[usage.usage_id] = usage
        for snapshot in self._load_records("inference_price_snapshot", InferencePriceSnapshot):
            self.price_snapshots[snapshot.snapshot_id] = snapshot
        for demand_snapshot in self._load_records("inference_demand_snapshot", InferenceDemandSnapshot):
            self.demand_snapshots[demand_snapshot.snapshot_id] = demand_snapshot

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
            "audit_event_id": _stable_id("infaud", event_type, str(sequence_hint), str(fields)),
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
                append_audit_event(event, chain_id="inference-market")

    def _persist_listing(self, listing: InferenceCreditListing) -> None:
        self._persist(
            "inference_credit_listing",
            listing.listing_id,
            listing.as_record(),
            provider_id=listing.source_id,
            actor_id=listing.seller_id,
            status=listing.status,
            expires_at=listing.expires_at,
        )

    def _persist_ledger_entry(self, ledger_entry: InferenceCreditLedgerEntry) -> None:
        self.ledger_entries[ledger_entry.ledger_entry_id] = ledger_entry
        self._persist(
            "inference_credit_ledger_entry",
            ledger_entry.ledger_entry_id,
            ledger_entry.as_record(),
            provider_id=ledger_entry.source_id,
            actor_id=ledger_entry.owner_id,
            status=ledger_entry.event_type,
            idempotency_key=ledger_entry.ledger_entry_id,
        )

    def _decrement_seller_balance(self, listing: InferenceCreditListing, units: float) -> float:
        for balance_id, balance in tuple(self.balances.items()):
            if (
                balance.account_id == listing.account_id
                and balance.source_id == listing.source_id
                and balance.model == listing.model
                and balance.unit_type == listing.unit_type
            ):
                remaining = max(0.0, round(balance.available_units - units, 8))
                updated = InferenceCreditBalance(
                    **{
                        **balance.as_record(),
                        "available_units": remaining,
                        "used_units": round(balance.used_units + units, 8),
                    }
                )
                self.balances[balance_id] = updated
                self._persist(
                    "inference_credit_balance",
                    updated.balance_id,
                    updated.as_record(),
                    provider_id=updated.source_id,
                    actor_id=updated.owner_id,
                    status="active",
                    expires_at=updated.expires_at,
                )
                return remaining
        return max(0.0, listing.available_units)

    def create_account(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        account = InferenceCreditAccount(
            account_id=str(payload.get("account_id") or _stable_id("acct", str(payload.get("owner_id") or payload.get("agent_id") or "agent"))),
            owner_id=str(payload.get("owner_id") or payload.get("agent_id") or "agent-simulated"),
            source_id=str(payload.get("source_id") or "src-discount-openai-compatible"),
            workspace_id=str(payload.get("workspace_id") or "default"),
            status=str(payload.get("status") or "active"),
            credential_ref=str(payload.get("credential_ref") or ""),
            sell_enabled=bool(payload.get("sell_enabled", False)),
            buy_enabled=bool(payload.get("buy_enabled", True)),
        )
        self.accounts[account.account_id] = account
        self._persist(
            "inference_credit_account",
            account.account_id,
            account.as_record(),
            workspace_id=account.workspace_id,
            provider_id=account.source_id,
            actor_id=account.owner_id,
            status=account.status,
        )
        return {"ok": True, "account": account.as_record(), "dry_run_only": True, "funds_moved": False}

    def create_source(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        _reject_raw_provider_credentials(payload)
        source = InferenceCreditSource(
            source_id=str(payload.get("source_id") or _stable_id("src", str(payload.get("source_name") or "source"))),
            source_name=str(payload.get("source_name") or payload.get("name") or "Simulated inference source"),
            source_type=str(payload.get("source_type") or SourceType.OPENAI_COMPATIBLE.value),
            status=str(payload.get("status") or "active"),
            verified=bool(payload.get("verified", False)),
            models=_tuple_str(payload.get("models"), ("gpt-4o-mini",)),
            supported_units=_tuple_str(payload.get("supported_units"), (CreditUnit.TOKEN.value, CreditUnit.REQUEST.value)),
            base_url=str(payload.get("base_url") or ""),
            credential_ref=str(payload.get("credential_ref") or ""),
            transferable=bool(payload.get("transferable", True)),
            seller_id=str(payload.get("seller_id") or payload.get("owner_id") or "seller-simulated"),
            quality_score=_positive_float(payload.get("quality_score"), 1.0),
            reliability_score=_positive_float(payload.get("reliability_score"), 1.0),
        )
        self.sources[source.source_id] = source
        self._persist(
            "inference_credit_source",
            source.source_id,
            source.as_record(),
            provider_id=source.source_id,
            actor_id=source.seller_id,
            status=source.status,
        )
        return {
            "ok": True,
            "source": source.as_record(),
            "credential_storage": "secret_reference_only",
            "dry_run_only": True,
            "funds_moved": False,
        }

    def update_source(self, source_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        _reject_raw_provider_credentials(payload)
        existing = self.sources.get(source_id)
        if existing is None:
            return self._policy_denial("unknown_source", "Unknown inference credit source.", "Create the source first.")
        record = existing.as_record()
        for key in (
            "source_name",
            "source_type",
            "status",
            "verified",
            "base_url",
            "credential_ref",
            "transferable",
            "seller_id",
            "quality_score",
            "reliability_score",
        ):
            if key in payload:
                record[key] = payload[key]
        if "models" in payload:
            record["models"] = _tuple_str(payload.get("models"), ())
        if "supported_units" in payload:
            record["supported_units"] = _tuple_str(payload.get("supported_units"), ())
        updated = InferenceCreditSource(**{key: record[key] for key in InferenceCreditSource.__dataclass_fields__})
        self.sources[source_id] = updated
        self._persist(
            "inference_credit_source",
            source_id,
            updated.as_record(),
            provider_id=source_id,
            actor_id=updated.seller_id,
            status=updated.status,
        )
        return {"ok": True, "source": updated.as_record(), "dry_run_only": True, "funds_moved": False}

    def disable_source(self, source_id: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        return self.update_source(source_id, {**dict(data), "status": "disabled"})

    def source_health(self, source_id: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._assert_safe_payload(payload or {})
        source = self.sources.get(source_id)
        health = "simulated_healthy" if source is not None and source.status == "active" else "disabled_or_unknown"
        return {"ok": source is not None, "source_id": source_id, "health": health, "dry_run_only": True}

    def cancel_listing(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        listing_id = str(payload.get("listing_id") or "")
        listing = self.listings.get(listing_id)
        if listing is None:
            return self._policy_denial("unknown_listing", "Unknown inference credit listing.", "List active listings first.")
        cancelled = InferenceCreditListing(**{**listing.as_record(), "status": ListingStatus.CANCELLED.value})
        self.listings[listing_id] = cancelled
        self._persist_listing(cancelled)
        return {
            "ok": True,
            "listing": cancelled.as_record(),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def demand(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        snapshot = InferenceDemandSnapshot(
            snapshot_id=_stable_id(
                "infdem",
                str(data.get("workspace_id") or "default"),
                str(data.get("agent_id") or "agent-default"),
                str(data.get("requested_model") or data.get("model") or "gpt-4o-mini"),
                str(data.get("estimated_units") or data.get("units_requested") or "1000"),
            ),
            requested_model=str(data.get("requested_model") or data.get("model") or "gpt-4o-mini"),
            provider_class=str(data.get("provider_class") or "openai_compatible"),
            unit_type=str(data.get("unit_type") or CreditUnit.TOKEN.value),
            units_requested=_positive_float(data.get("units_requested", data.get("estimated_units")), 1_000.0),
            max_price=_nonnegative_float(data.get("max_price"), 0.0),
            urgency=str(data.get("urgency") or "normal"),
            workspace_id=str(data.get("workspace_id") or "default"),
            agent_id=str(data.get("agent_id") or "agent-default"),
            accepted_route=str(data.get("accepted_route") or data.get("route_id") or ""),
            rejected_reason=str(data.get("rejected_reason") or ""),
        )
        self.demand_snapshots[snapshot.snapshot_id] = snapshot
        self._persist(
            "inference_demand_snapshot",
            snapshot.snapshot_id,
            snapshot.as_record(),
            workspace_id=snapshot.workspace_id,
            agent_id=snapshot.agent_id,
            route_id=snapshot.accepted_route,
            status="recorded",
        )
        return {
            "ok": True,
            "demand": (snapshot.as_record(),),
            "dry_run_only": True,
            "funds_moved": False,
        }

    def demand_summary(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        if not self.demand_snapshots and data:
            self.demand(data)
        snapshots = tuple(snapshot.as_record() for snapshot in self.demand_snapshots.values())
        by_model: dict[str, float] = {}
        by_agent: dict[str, float] = {}
        for snapshot in snapshots:
            model = str(snapshot.get("requested_model", ""))
            agent_id = str(snapshot.get("agent_id", ""))
            units = float(snapshot.get("units_requested", 0.0) or 0.0)
            by_model[model] = by_model.get(model, 0.0) + units
            by_agent[agent_id] = by_agent.get(agent_id, 0.0) + units
        return {
            "ok": True,
            "summary": {
                "snapshot_count": len(snapshots),
                "total_units_requested": round(sum(by_model.values()), 8),
                "models": tuple({"model": model, "units_requested": units} for model, units in sorted(by_model.items())),
                "agents": tuple({"agent_id": agent_id, "units_requested": units} for agent_id, units in sorted(by_agent.items())),
                "deferred_due_to_price_count": sum(1 for item in snapshots if str(item.get("rejected_reason", ""))),
            },
            "dry_run_only": True,
            "funds_moved": False,
        }

    def demand_forecast(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        if data:
            self.demand(data)
        summary = self.demand_summary(data)["summary"]
        total_units = float(summary.get("total_units_requested", 0.0) or 0.0)
        return {
            "ok": True,
            "forecast": {
                "forecast_id": _stable_id("infdemf", str(data), str(total_units)),
                "horizon_seconds": int(data.get("horizon_seconds", 86_400) or 86_400),
                "expected_units_requested": round(total_units * 1.1 if total_units else 1_000.0, 8),
                "recommended_next_action": "onboard_more_supply" if total_units > 0 else "collect_more_demand",
                "confidence": "simulated",
            },
            "dry_run_only": True,
            "funds_moved": False,
        }

    def credits(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        owner_id = str(data.get("owner_id") or data.get("agent_id") or "")
        balances = tuple(
            balance.as_record()
            for balance in self.balances.values()
            if not owner_id or balance.owner_id == owner_id
        )
        return {
            "ok": True,
            "credit_balances": balances,
            "dry_run_only": True,
            "funds_moved": False,
            "private_key_required": False,
        }

    def sources_list(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        return {
            "ok": True,
            "sources": tuple(source.as_record() for source in self.sources.values()),
            "dry_run_only": True,
        }

    def order_book(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        model = str(data.get("model", ""))
        listings = tuple(
            listing.as_record()
            for listing in self._active_listings(model=model)
        )
        best_ask = min((float(listing["unit_price"]) for listing in listings), default=0.0)
        return {
            "ok": True,
            "listings": listings,
            "summary": {"active_listing_count": len(listings), "best_ask": best_ask},
            "dry_run_only": True,
            "funds_moved": False,
        }

    def quote(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        model = str(payload.get("model") or payload.get("requested_model") or "gpt-4o-mini")
        unit_type = str(payload.get("unit_type") or CreditUnit.TOKEN.value)
        units = _positive_float(payload.get("estimated_units"), 1_000.0)
        policy = _policy_from_payload(payload)
        quotes: list[InferenceQuote] = []
        rejected: list[dict[str, Any]] = []
        for listing in self._active_listings(model=model, unit_type=unit_type):
            source = self.sources.get(listing.source_id)
            if source is None or source.status != "active":
                rejected.append({"listing_id": listing.listing_id, "code": "source_disabled"})
                continue
            if policy.allowed_models and listing.model not in policy.allowed_models:
                rejected.append({"listing_id": listing.listing_id, "code": "model_disallowed"})
                continue
            if policy.max_unit_price and listing.unit_price > policy.max_unit_price:
                rejected.append({"listing_id": listing.listing_id, "code": "max_unit_price_exceeded"})
                continue
            route = InferenceRoute(
                route_id=_stable_id("infr", listing.listing_id, model, unit_type),
                source_id=listing.source_id,
                listing_id=listing.listing_id,
                model=listing.model,
                unit_type=listing.unit_type,
                unit_price=listing.unit_price,
                quality_score=source.quality_score,
                latency_ms=350 if source.source_type != SourceType.LOCAL.value else 25,
                compatible_api="openai" if source.source_type != SourceType.ANTHROPIC_COMPATIBLE.value else "anthropic",
            )
            reference = float(listing.metadata.get("reference_unit_price", listing.unit_price) or listing.unit_price)
            discount_bps = int(max(0.0, (reference - listing.unit_price) / reference * 10_000)) if reference else 0
            if discount_bps < policy.min_discount_bps:
                rejected.append({"listing_id": listing.listing_id, "code": "min_discount_not_met"})
                continue
            quote = InferenceQuote(
                quote_id=_stable_id("infq", listing.listing_id, str(units), str(listing.unit_price)),
                route=route,
                estimated_units=units,
                estimated_total_cost=round(units * listing.unit_price, 8),
                discount_bps=discount_bps,
                expires_at=listing.expires_at,
                assumptions=("dry_run_quote", "provider_credentials_not_exposed"),
            )
            quotes.append(quote)
            self._persist(
                "inference_route",
                route.route_id,
                route.as_record(),
                provider_id=route.source_id,
                route_id=route.route_id,
                status="available",
            )
            self._persist(
                "inference_credit_quote",
                quote.quote_id,
                quote.as_record(),
                provider_id=route.source_id,
                route_id=route.route_id,
                status="quoted",
                expires_at=quote.expires_at,
            )
        return {
            "ok": True,
            "quotes": tuple(quote.as_record() for quote in quotes),
            "rejected_routes": tuple(rejected),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def route(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        quoted = self.quote(payload)
        quotes_raw = quoted.get("quotes", ())
        quotes = tuple(item for item in quotes_raw if isinstance(item, Mapping))
        selected = min(quotes, key=lambda item: float(item.get("estimated_total_cost", 0.0)), default=None)
        if selected is None:
            return {
                "ok": False,
                "error": {
                    "code": "no_valid_inference_route",
                    "message": "No valid dry-run inference route matched the request.",
                    "next_safe_action": "Enable fallback or lower policy constraints.",
                },
                "rejected_routes": quoted.get("rejected_routes", ()),
                "dry_run_only": True,
                "funds_moved": False,
            }
        decision = {
            "decision_id": _stable_id("infd", str(selected.get("quote_id", ""))),
            "decision": AgentInferenceDecision.BUY_DISCOUNT_INFERENCE.value,
            "selected_quote": dict(selected),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }
        route_record = selected.get("route") if isinstance(selected.get("route"), Mapping) else {}
        self._persist(
            "inference_market_decision",
            str(decision["decision_id"]),
            decision,
            provider_id=str(route_record.get("source_id", "")) if isinstance(route_record, Mapping) else "",
            route_id=str(route_record.get("route_id", "")) if isinstance(route_record, Mapping) else "",
            status=str(decision["decision"]),
        )
        return {
            "ok": True,
            "route_decision": decision,
            "dry_run_only": True,
            "funds_moved": False,
        }

    def buy(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        buyer_id = str(payload.get("buyer_id") or payload.get("agent_id") or "agent-buyer")
        listing_id = str(payload.get("listing_id") or "lst-discount-gpt4o-mini-token")
        units = _positive_float(payload.get("units"), 1_000.0)
        listing = self._listing(listing_id)
        if listing.status != ListingStatus.ACTIVE.value:
            return self._policy_denial("listing_inactive", "Listing is not active.", "Choose an active listing.")
        raw_max_price = payload.get("max_unit_price")
        max_unit_price = listing.unit_price if raw_max_price is None else _nonnegative_float(raw_max_price, 0.0)
        if listing.unit_price > max_unit_price:
            return self._policy_denial(
                "max_unit_price_exceeded",
                "Listing unit price exceeds max_unit_price.",
                "Choose a cheaper listing or raise max_unit_price.",
            )
        fill_units = min(units, listing.available_units)
        if fill_units <= 0:
            return self._policy_denial(
                "zero_fill_rejected",
                "Requested units cannot be filled from this listing.",
                "Choose a listing with available units or request fewer units.",
            )
        total = round(fill_units * listing.unit_price, 8)
        order = InferenceCreditOrder(
            order_id=_stable_id("info", buyer_id, listing_id, str(units), str(listing.available_units)),
            buyer_id=buyer_id,
            model=listing.model,
            unit_type=listing.unit_type,
            requested_units=units,
            max_unit_price=max_unit_price,
            status=OrderStatus.FILLED.value if fill_units == units else OrderStatus.PARTIALLY_FILLED.value,
            selected_listing_id=listing_id,
            filled_units=fill_units,
            average_unit_price=listing.unit_price,
        )
        fill = InferenceCreditFill(
            fill_id=_stable_id("inff", order.order_id, listing_id, str(fill_units)),
            order_id=order.order_id,
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=listing.seller_id,
            unit_type=listing.unit_type,
            units=fill_units,
            unit_price=listing.unit_price,
            total_price=total,
        )
        remaining_units = round(listing.available_units - fill_units, 8)
        updated_listing = InferenceCreditListing(
            **{
                **listing.as_record(),
                "available_units": remaining_units,
                "status": ListingStatus.FILLED.value if remaining_units <= 0 else listing.status,
            }
        )
        self.listings[listing_id] = updated_listing
        self._persist_listing(updated_listing)
        seller_balance_after = self._decrement_seller_balance(updated_listing, fill_units)
        buyer_ledger = InferenceCreditLedgerEntry(
            ledger_entry_id=_stable_id("infled", "buyer", order.order_id),
            account_id=str(payload.get("buyer_account_id") or ""),
            source_id=listing.source_id,
            owner_id=buyer_id,
            event_type="buy_debit",
            unit_type=listing.unit_type,
            units=fill_units,
            balance_after=0.0,
            related_id=order.order_id,
        )
        seller_ledger = InferenceCreditLedgerEntry(
            ledger_entry_id=_stable_id("infled", "seller", order.order_id),
            account_id=listing.account_id,
            source_id=listing.source_id,
            owner_id=listing.seller_id,
            event_type="sell_credit",
            unit_type=listing.unit_type,
            units=fill_units,
            balance_after=seller_balance_after,
            related_id=order.order_id,
        )
        self.orders[order.order_id] = order
        self.fills[fill.fill_id] = fill
        self._persist(
            "inference_credit_order",
            order.order_id,
            order.as_record(),
            actor_id=order.buyer_id,
            status=order.status,
            idempotency_key=str(payload.get("idempotency_key") or order.order_id),
        )
        self._persist(
            "inference_credit_fill",
            fill.fill_id,
            fill.as_record(),
            actor_id=fill.buyer_id,
            status="simulated",
            idempotency_key=str(payload.get("idempotency_key") or fill.fill_id),
        )
        self._persist_ledger_entry(buyer_ledger)
        self._persist_ledger_entry(seller_ledger)
        self._audit("inference.buy.simulated", order_id=order.order_id, fill_id=fill.fill_id, actor_id=order.buyer_id)
        return {
            "ok": True,
            "order": order.as_record(),
            "fill": fill.as_record(),
            "listing": updated_listing.as_record(),
            "ledger_entries": (buyer_ledger.as_record(), seller_ledger.as_record()),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def sell(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        seller_id = str(payload.get("seller_id") or payload.get("agent_id") or "agent-seller")
        model = str(payload.get("model") or "gpt-4o-mini")
        unit_type = str(payload.get("unit_type") or CreditUnit.TOKEN.value)
        units = _positive_float(payload.get("units"), 1_000.0)
        unit_price = _positive_float(payload.get("unit_price"), 0.0000008)
        listing = InferenceCreditListing(
            listing_id=_stable_id("lst", seller_id, model, unit_type, str(units), str(unit_price)),
            seller_id=seller_id,
            account_id=str(payload.get("account_id") or f"acct-{seller_id}"),
            source_id=str(payload.get("source_id") or "src-discount-openai-compatible"),
            model=model,
            unit_type=unit_type,
            available_units=units,
            unit_price=unit_price,
            currency=str(payload.get("currency") or "USD_CREDIT"),
            expires_at=str(payload.get("expires_at") or "2026-05-27T00:00:00Z"),
            transferable=True,
        )
        self.listings[listing.listing_id] = listing
        self._persist_listing(listing)
        self._audit("inference.sell.listed", listing_id=listing.listing_id, actor_id=listing.seller_id)
        return {
            "ok": True,
            "listing": listing.as_record(),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def opportunity_cost(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        task = str(payload.get("task") or "agent task")
        agent_id = str(payload.get("agent_id") or "agent-default")
        goal_id = str(payload.get("goal_id") or "goal-default")
        estimated_task_value_raw = payload.get("estimated_value", payload.get("estimated_task_value"))
        value_unknown = estimated_task_value_raw is None
        estimated_task_value = _nonnegative_float(estimated_task_value_raw, 0.0)
        budget = _nonnegative_float(payload.get("budget"), 1.0)
        units = _positive_float(payload.get("estimated_units"), 1_000.0)
        urgency = str(payload.get("urgency") or "normal")
        allow_sell = bool(payload.get("allow_sell_unused", False))
        allow_defer = bool(payload.get("allow_defer", True))
        allow_downgrade = bool(payload.get("allow_downgrade", True))
        quote_result = self.quote({**dict(payload), "estimated_units": units})
        quote_items = tuple(item for item in quote_result.get("quotes", ()) if isinstance(item, Mapping))
        selected = min(quote_items, key=lambda item: float(item.get("estimated_total_cost", 0.0)), default=None)
        estimated_run_cost = float(selected.get("estimated_total_cost", 0.0)) if selected is not None else budget + 1.0
        sellable_units = _sellable_units(self.balances.values(), owner_id=agent_id)
        market_bid_price = _nonnegative_float(payload.get("market_bid_price"), 0.0000007)
        estimated_sell_value = round(sellable_units * market_bid_price, 8) if allow_sell else 0.0
        opportunity_cost = max(0.0, estimated_sell_value - estimated_task_value)
        expected_roi_if_run = estimated_task_value - estimated_run_cost
        expected_roi_if_sell = estimated_sell_value
        urgent = urgency in {"urgent", "immediate", "now"}
        decision = self._choose_decision(
            value_unknown=value_unknown,
            estimated_task_value=estimated_task_value,
            estimated_run_cost=estimated_run_cost,
            estimated_sell_value=estimated_sell_value,
            budget=budget,
            allow_sell=allow_sell,
            allow_defer=allow_defer,
            allow_downgrade=allow_downgrade,
            urgent=urgent,
            has_route=selected is not None,
            payload=payload,
        )
        rationale = _rationale(
            decision=decision,
            value_unknown=value_unknown,
            estimated_task_value=estimated_task_value,
            estimated_run_cost=estimated_run_cost,
            estimated_sell_value=estimated_sell_value,
            budget=budget,
            urgent=urgent,
        )
        analysis = RunVsSellAnalysis(
            analysis_id=_stable_id("infa", agent_id, goal_id, task, str(estimated_task_value), str(estimated_run_cost)),
            estimated_task_value=estimated_task_value,
            estimated_run_cost=estimated_run_cost,
            estimated_sell_value=estimated_sell_value,
            opportunity_cost=opportunity_cost,
            expected_roi_if_run=expected_roi_if_run,
            expected_roi_if_sell=expected_roi_if_sell,
            urgent=urgent,
            value_unknown=value_unknown,
            rationale=rationale,
        )
        route_record = selected.get("route") if isinstance(selected, Mapping) else None
        selected_route = _route_from_record(route_record) if isinstance(route_record, Mapping) else None
        listing_id = str(route_record.get("listing_id", "")) if isinstance(route_record, Mapping) else ""
        selected_listing = self.listings.get(listing_id)
        decision_record = OpportunityCostDecision(
            decision_id=_stable_id("infoc", analysis.analysis_id, decision.value),
            decision=decision.value,
            recommended_action=decision.value,
            analysis=analysis,
            selected_route=selected_route,
            selected_listing=selected_listing,
            rejected_routes=tuple(item for item in quote_result.get("rejected_routes", ()) if isinstance(item, Mapping)),
            rejected_reasons=tuple(str(item.get("code", "unknown")) for item in quote_result.get("rejected_routes", ()) if isinstance(item, Mapping)),
            rationale=rationale,
            next_safe_actions=_next_safe_actions(decision),
        )
        usage = InferenceUsageRecord(
            usage_id=_stable_id("infu", decision_record.decision_id),
            workspace_id=str(payload.get("workspace_id") or "default"),
            agent_id=agent_id,
            goal_id=goal_id,
            task_id=str(payload.get("task_id") or _stable_id("task", task)),
            model=str(payload.get("model") or "gpt-4o-mini"),
            source_id=selected_route.source_id if selected_route is not None else "",
            route_id=selected_route.route_id if selected_route is not None else "",
            unit_type=str(payload.get("unit_type") or CreditUnit.TOKEN.value),
            estimated_units=units,
            actual_units=0.0,
            estimated_cost=estimated_run_cost,
            actual_cost=0.0,
            credits_sold=estimated_sell_value if decision == AgentInferenceDecision.SELL_UNUSED_INFERENCE else 0.0,
            task_value=estimated_task_value,
            task_roi=expected_roi_if_run,
            selected_decision=decision.value,
            opportunity_cost=opportunity_cost,
        )
        self.usage_records[usage.usage_id] = usage
        self._persist(
            "opportunity_cost_decision",
            decision_record.decision_id,
            decision_record.as_record(),
            workspace_id=usage.workspace_id,
            agent_id=agent_id,
            goal_id=goal_id,
            route_id=usage.route_id,
            status=decision.value,
            idempotency_key=str(payload.get("idempotency_key") or decision_record.decision_id),
        )
        self._persist(
            "inference_usage_record",
            usage.usage_id,
            usage.as_record(),
            workspace_id=usage.workspace_id,
            agent_id=usage.agent_id,
            goal_id=usage.goal_id,
            route_id=usage.route_id,
            task_type=str(payload.get("task_type") or "inference"),
            status=usage.selected_decision,
            idempotency_key=str(payload.get("idempotency_key") or usage.usage_id),
        )
        self._audit(
            "inference.opportunity_cost",
            decision_id=decision_record.decision_id,
            actor_id=agent_id,
            goal_id=goal_id,
        )
        return {
            "ok": True,
            "decision": decision_record.as_record(),
            "usage_record": usage.as_record(),
            "warnings": ("estimated_task_value_unknown",) if value_unknown else (),
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def usage(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        agent_id = str(data.get("agent_id") or "")
        records = tuple(
            record.as_record()
            for record in self.usage_records.values()
            if not agent_id or record.agent_id == agent_id
        )
        return {
            "ok": True,
            "usage_records": records,
            "summary": _usage_summary(records),
            "dry_run_only": True,
            "funds_moved": False,
        }

    def statement(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        records = tuple(item for item in self.usage(data).get("usage_records", ()) if isinstance(item, Mapping))
        return {
            "ok": True,
            "statement": {
                "statement_id": _stable_id("infs", str(data.get("agent_id", "all")), str(len(records))),
                "agent_id": str(data.get("agent_id") or "all"),
                "usage_records": records,
                "summary": _usage_summary(records),
                "dry_run_only": True,
                "funds_moved": False,
            },
            "dry_run_only": True,
            "funds_moved": False,
        }

    def prices(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        snapshots = []
        for listing in self._active_listings(model=str(data.get("model", ""))):
            reference = float(listing.metadata.get("reference_unit_price", listing.unit_price) or listing.unit_price)
            discount_bps = int(max(0.0, (reference - listing.unit_price) / reference * 10_000)) if reference else 0
            snapshot = InferencePriceSnapshot(
                snapshot_id=_stable_id("infp", listing.listing_id, str(listing.unit_price)),
                source_id=listing.source_id,
                route_id=_stable_id("infr", listing.listing_id, listing.model, listing.unit_type),
                model=listing.model,
                unit_type=listing.unit_type,
                unit_price=listing.unit_price,
                reference_price=reference,
                discount_bps=discount_bps,
                available_units=listing.available_units,
            )
            snapshots.append(snapshot.as_record())
            self.price_snapshots[snapshot.snapshot_id] = snapshot
            self._persist(
                "inference_price_snapshot",
                snapshot.snapshot_id,
                snapshot.as_record(),
                provider_id=snapshot.source_id,
                route_id=snapshot.route_id,
                status="recorded",
            )
        return {"ok": True, "prices": tuple(snapshots), "dry_run_only": True, "funds_moved": False}

    def price_history(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        self._assert_safe_payload(data)
        self.prices(data)
        model = str(data.get("model") or "")
        records = tuple(
            snapshot.as_record()
            for snapshot in self.price_snapshots.values()
            if not model or snapshot.model == model
        )
        return {"ok": True, "price_history": records, "dry_run_only": True, "funds_moved": False}

    def price_spreads(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        history = self.price_history(payload)
        records = tuple(item for item in history.get("price_history", ()) if isinstance(item, Mapping))
        spreads = []
        for model in sorted({str(item.get("model", "")) for item in records}):
            model_records = tuple(item for item in records if str(item.get("model", "")) == model)
            prices = sorted(float(item.get("unit_price", 0.0) or 0.0) for item in model_records)
            if not prices:
                continue
            best = prices[0]
            worst = prices[-1]
            spread_bps = int(((worst - best) / best) * 10_000) if best else 0
            spreads.append({"model": model, "best_unit_price": best, "worst_unit_price": worst, "spread_bps": spread_bps})
        return {"ok": True, "spreads": tuple(spreads), "dry_run_only": True, "funds_moved": False}

    def price_anomalies(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        history = self.price_history(payload)
        records = tuple(item for item in history.get("price_history", ()) if isinstance(item, Mapping))
        anomalies = []
        for item in records:
            unit_price = float(item.get("unit_price", 0.0) or 0.0)
            reference_price = float(item.get("reference_price", 0.0) or 0.0)
            if reference_price and unit_price > reference_price * 1.2:
                anomalies.append({"snapshot_id": item.get("snapshot_id", ""), "code": "above_reference_price"})
        return {"ok": True, "anomalies": tuple(anomalies), "dry_run_only": True, "funds_moved": False}

    def price_forecast(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        history = self.price_history(payload)
        records = tuple(item for item in history.get("price_history", ()) if isinstance(item, Mapping))
        prices = sorted(float(item.get("unit_price", 0.0) or 0.0) for item in records)
        best = prices[0] if prices else 0.0
        return {
            "ok": True,
            "forecast": {
                "forecast_id": _stable_id("infpf", str(payload or {}), str(best)),
                "forecast_unit_price": best,
                "direction": "flat_simulated",
                "confidence": "simulated",
            },
            "dry_run_only": True,
            "funds_moved": False,
        }

    def proxy_chat_completion(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        model = str(payload.get("model") or "flow-local-small")
        route = self.route({"model": model, "unit_type": CreditUnit.REQUEST.value, "estimated_units": 1})
        if not route.get("ok"):
            return route
        usage = self._record_proxy_usage(payload, model=model, route_result=route, provider_api="openai")
        response_id = _stable_id("chatcmpl", model, str(payload.get("messages", ())))
        warnings = ("streaming_not_implemented",) if bool(payload.get("stream", False)) else ()
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": 1_779_753_600,
            "model": model,
            "request_id": str(payload.get("request_id") or _stable_id("req", "openai", response_id)),
            "choices": (
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Flow Memory fake provider response. External providers are disabled by default.",
                    },
                    "finish_reason": "stop",
                },
            ),
            "usage": {"prompt_tokens": 0, "completion_tokens": 10, "total_tokens": 10},
            "flow_memory": {
                "route_decision": route.get("route_decision", {}),
                "usage_record": usage.as_record(),
                "dry_run_only": True,
                "funds_moved": False,
                "broadcast_allowed": False,
                "private_key_required": False,
                "warnings": warnings,
            },
        }

    def proxy_response(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        model = str(payload.get("model") or "flow-local-small")
        input_text = _proxy_input_text(payload.get("input", payload.get("messages", "")))
        route = self.route({"model": model, "unit_type": CreditUnit.REQUEST.value, "estimated_units": 1})
        if not route.get("ok"):
            return route
        usage = self._record_proxy_usage({**dict(payload), "messages": input_text}, model=model, route_result=route, provider_api="openai_responses")
        response_id = _stable_id("resp", model, input_text)
        warnings = ("streaming_not_implemented",) if bool(payload.get("stream", False)) else ()
        return {
            "id": response_id,
            "object": "response",
            "created_at": 1_779_753_600,
            "status": "completed",
            "model": model,
            "request_id": str(payload.get("request_id") or _stable_id("req", "responses", response_id)),
            "output": (
                {
                    "id": _stable_id("msg", response_id),
                    "type": "message",
                    "role": "assistant",
                    "content": (
                        {
                            "type": "output_text",
                            "text": "Flow Memory fake provider response. External providers are disabled by default.",
                        },
                    ),
                },
            ),
            "usage": {"input_tokens": 0, "output_tokens": 10, "total_tokens": 10},
            "flow_memory": {
                "route_decision": route.get("route_decision", {}),
                "usage_record": usage.as_record(),
                "dry_run_only": True,
                "funds_moved": False,
                "broadcast_allowed": False,
                "private_key_required": False,
                "warnings": warnings,
            },
        }

    def proxy_embeddings(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        model = str(payload.get("model") or "flow-local-embedding")
        inputs = _proxy_embedding_inputs(payload.get("input", ""))
        route = self.route({"model": "flow-local-small", "unit_type": CreditUnit.REQUEST.value, "estimated_units": len(inputs) or 1})
        if not route.get("ok"):
            return route
        usage = self._record_proxy_usage(
            {**dict(payload), "messages": " ".join(inputs)},
            model=model,
            route_result=route,
            provider_api="openai_embeddings",
        )
        return {
            "object": "list",
            "model": model,
            "request_id": str(payload.get("request_id") or _stable_id("req", "embeddings", model, " ".join(inputs))),
            "data": tuple(
                {
                    "object": "embedding",
                    "index": index,
                    "embedding": _deterministic_embedding_vector(item),
                }
                for index, item in enumerate(inputs)
            ),
            "usage": {"prompt_tokens": 0, "total_tokens": max(1, len(inputs))},
            "flow_memory": {
                "route_decision": route.get("route_decision", {}),
                "usage_record": usage.as_record(),
                "dry_run_only": True,
                "funds_moved": False,
                "broadcast_allowed": False,
                "private_key_required": False,
            },
        }


    def proxy_anthropic_message(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_safe_payload(payload)
        model = str(payload.get("model") or "claude-3-5-haiku")
        route = self.route({"model": model, "unit_type": CreditUnit.REQUEST.value, "estimated_units": 1})
        if not route.get("ok"):
            return route
        usage = self._record_proxy_usage(payload, model=model, route_result=route, provider_api="anthropic")
        response_id = _stable_id("msg", model, str(payload.get("messages", ())))
        warnings = ("streaming_not_implemented",) if bool(payload.get("stream", False)) else ()
        return {
            "id": response_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "request_id": str(payload.get("request_id") or _stable_id("req", "anthropic", response_id)),
            "content": (
                {
                    "type": "text",
                    "text": "Flow Memory fake provider response. External providers are disabled by default.",
                },
            ),
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 10},
            "flow_memory": {
                "route_decision": route.get("route_decision", {}),
                "usage_record": usage.as_record(),
                "dry_run_only": True,
                "funds_moved": False,
                "broadcast_allowed": False,
                "private_key_required": False,
                "warnings": warnings,
            },
        }

    def models(self, _payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        names = sorted({model for source in self.sources.values() if source.status == "active" for model in source.models})
        return {"object": "list", "data": tuple({"id": name, "object": "model", "owned_by": "flow-memory"} for name in names)}

    def anthropic_models(self, _payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        names = sorted(
            {
                model
                for source in self.sources.values()
                if source.status == "active" and source.source_type == SourceType.ANTHROPIC_COMPATIBLE.value
                for model in source.models
            }
        )
        return {
            "data": tuple({"id": name, "type": "model", "display_name": name} for name in names),
            "has_more": False,
            "first_id": names[0] if names else "",
            "last_id": names[-1] if names else "",
        }

    def _record_proxy_usage(
        self,
        payload: Mapping[str, Any],
        *,
        model: str,
        route_result: Mapping[str, Any],
        provider_api: str,
    ) -> InferenceUsageRecord:
        decision = route_result.get("route_decision", {})
        selected_quote = decision.get("selected_quote", {}) if isinstance(decision, Mapping) else {}
        route = selected_quote.get("route", {}) if isinstance(selected_quote, Mapping) else {}
        estimated_cost = _nonnegative_float(selected_quote.get("estimated_total_cost") if isinstance(selected_quote, Mapping) else 0.0, 0.0)
        estimated_units = _positive_float(selected_quote.get("estimated_units") if isinstance(selected_quote, Mapping) else 1.0, 1.0)
        usage = InferenceUsageRecord(
            usage_id=_stable_id(
                "infu",
                provider_api,
                model,
                str(payload.get("agent_id", "agent-default")),
                str(payload.get("messages", ())),
            ),
            workspace_id=str(payload.get("workspace_id") or "workspace-default"),
            agent_id=str(payload.get("agent_id") or "agent-default"),
            goal_id=str(payload.get("goal_id") or "goal-default"),
            task_id=str(payload.get("task_id") or _stable_id("task", provider_api, model)),
            model=model,
            source_id=str(route.get("source_id", "")) if isinstance(route, Mapping) else "",
            route_id=str(route.get("route_id", "")) if isinstance(route, Mapping) else "",
            unit_type=str(route.get("unit_type", CreditUnit.REQUEST.value)) if isinstance(route, Mapping) else CreditUnit.REQUEST.value,
            estimated_units=estimated_units,
            actual_units=1.0,
            estimated_cost=estimated_cost,
            actual_cost=estimated_cost,
            credits_consumed=1.0,
            discount_bps=int(selected_quote.get("discount_bps", 0) or 0) if isinstance(selected_quote, Mapping) else 0,
            selected_decision=str(decision.get("decision", f"{provider_api}_proxy_fake_provider")) if isinstance(decision, Mapping) else f"{provider_api}_proxy_fake_provider",
            latency_ms=int(route.get("latency_ms", 25) or 25) if isinstance(route, Mapping) else 25,
            quality_score=float(route.get("quality_score", 1.0) or 1.0) if isinstance(route, Mapping) else 1.0,
        )
        self.usage_records[usage.usage_id] = usage
        self._persist(
            "inference_usage_record",
            usage.usage_id,
            usage.as_record(),
            workspace_id=usage.workspace_id,
            provider_id=usage.source_id,
            route_id=usage.route_id,
            actor_id=usage.agent_id,
            task_type=f"{provider_api}_proxy",
            status="completed",
            idempotency_key=str(payload.get("idempotency_key") or usage.usage_id),
        )
        self._audit(f"inference.proxy.{provider_api}", usage_id=usage.usage_id, actor_id=usage.agent_id, route_id=usage.route_id)
        return usage

    def _active_listings(self, model: str = "", unit_type: str = "") -> tuple[InferenceCreditListing, ...]:
        listings = []
        for listing in self.listings.values():
            if listing.status != ListingStatus.ACTIVE.value:
                continue
            if model and listing.model != model:
                continue
            if unit_type and listing.unit_type != unit_type:
                continue
            listings.append(listing)
        return tuple(listings)

    def _listing(self, listing_id: str) -> InferenceCreditListing:
        listing = self.listings.get(listing_id)
        if listing is None:
            raise KeyError(f"Unknown inference listing: {listing_id}")
        return listing

    def _choose_decision(
        self,
        *,
        value_unknown: bool,
        estimated_task_value: float,
        estimated_run_cost: float,
        estimated_sell_value: float,
        budget: float,
        allow_sell: bool,
        allow_defer: bool,
        allow_downgrade: bool,
        urgent: bool,
        has_route: bool,
        payload: Mapping[str, Any],
    ) -> AgentInferenceDecision:
        if bool(payload.get("simulate_futures_hedge", False)):
            return AgentInferenceDecision.SIMULATE_FUTURES_HEDGE
        if bool(payload.get("buy_forward_capacity", False)):
            return AgentInferenceDecision.BUY_FORWARD_CAPACITY
        if bool(payload.get("reserve_capacity", False)):
            return AgentInferenceDecision.RESERVE_CAPACITY
        if value_unknown and not urgent:
            return AgentInferenceDecision.DEFER_TASK if allow_defer else AgentInferenceDecision.REQUIRE_HUMAN_APPROVAL
        if estimated_task_value <= 0 and allow_sell and estimated_sell_value > 0:
            return AgentInferenceDecision.SELL_UNUSED_INFERENCE
        if allow_sell and not urgent and estimated_sell_value > estimated_task_value:
            return AgentInferenceDecision.SELL_UNUSED_INFERENCE
        if estimated_run_cost > budget:
            if allow_downgrade:
                return AgentInferenceDecision.DOWNGRADE_INTELLIGENCE_TIER
            if allow_defer:
                return AgentInferenceDecision.DEFER_TASK
            return AgentInferenceDecision.REJECT_NEGATIVE_ROI
        if not has_route:
            return AgentInferenceDecision.USE_FALLBACK_ROUTE
        if urgent:
            return AgentInferenceDecision.RUN_TASK_NOW
        if estimated_run_cost < estimated_task_value:
            return AgentInferenceDecision.BUY_DISCOUNT_INFERENCE
        if allow_defer:
            return AgentInferenceDecision.DEFER_TASK
        return AgentInferenceDecision.REJECT_NEGATIVE_ROI

    def _assert_safe_payload(self, payload: Mapping[str, Any]) -> None:
        flattened = _flatten_payload(payload).lower()
        for token in UNSAFE_PAYLOAD_TOKENS:
            if token in flattened:
                raise ValueError(f"unsafe inference market payload rejected: {token}")
        if bool(payload.get("broadcast", False)):
            raise ValueError("unsafe inference market payload rejected: broadcast")
        if bool(payload.get("live_settlement", False)):
            raise ValueError("unsafe inference market payload rejected: live_settlement")
        if bool(payload.get("live_futures", False)):
            raise ValueError("unsafe inference market payload rejected: live_futures")

    def _policy_denial(self, code: str, message: str, next_safe_action: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {"code": code, "message": message, "next_safe_action": next_safe_action},
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }


def _policy_from_payload(payload: Mapping[str, Any]) -> InferenceMarketPolicy:
    raw = payload.get("market_policy", {})
    policy = raw if isinstance(raw, Mapping) else {}
    allowed_models_raw = policy.get("allowed_models", payload.get("allowed_models", ()))
    allowed_models = tuple(str(item) for item in allowed_models_raw) if isinstance(allowed_models_raw, list | tuple) else ()
    return InferenceMarketPolicy(
        allowed_models=allowed_models,
        min_discount_bps=int(policy.get("min_discount_bps", payload.get("min_discount_bps", 0)) or 0),
        max_unit_price=float(policy.get("max_unit_price", payload.get("max_unit_price", 0.0)) or 0.0),
        allow_fallback=bool(policy.get("allow_fallback", payload.get("allow_fallback", True))),
        allow_sell_unused=bool(policy.get("allow_sell_unused", payload.get("allow_sell_unused", False))),
        allow_external_providers=bool(policy.get("allow_external_providers", False)),
    )


def _route_from_record(record: Mapping[str, Any]) -> InferenceRoute:
    return InferenceRoute(
        route_id=str(record.get("route_id", "")),
        source_id=str(record.get("source_id", "")),
        listing_id=str(record.get("listing_id", "")),
        model=str(record.get("model", "")),
        unit_type=str(record.get("unit_type", "")),
        unit_price=float(record.get("unit_price", 0.0) or 0.0),
        quality_score=float(record.get("quality_score", 1.0) or 1.0),
        latency_ms=int(record.get("latency_ms", 0) or 0),
        compatible_api=str(record.get("compatible_api", "openai")),
    )


def _usage_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = tuple(records)
    total_estimated_cost = sum(float(item.get("estimated_cost", 0.0) or 0.0) for item in items)
    total_task_value = sum(float(item.get("task_value", 0.0) or 0.0) for item in items)
    return {
        "record_count": len(items),
        "total_estimated_cost": round(total_estimated_cost, 8),
        "total_task_value": round(total_task_value, 8),
        "net_estimated_roi": round(total_task_value - total_estimated_cost, 8),
    }


def _sellable_units(balances: Iterable[InferenceCreditBalance], owner_id: str) -> float:
    return sum(balance.available_units for balance in balances if balance.owner_id == owner_id and balance.transferable)


def _rationale(
    *,
    decision: AgentInferenceDecision,
    value_unknown: bool,
    estimated_task_value: float,
    estimated_run_cost: float,
    estimated_sell_value: float,
    budget: float,
    urgent: bool,
) -> tuple[str, ...]:
    parts = [f"decision={decision.value}"]
    if value_unknown:
        parts.append("estimated_task_value_unknown")
    if urgent:
        parts.append("task_is_urgent")
    parts.append(f"estimated_task_value={estimated_task_value}")
    parts.append(f"estimated_run_cost={estimated_run_cost}")
    parts.append(f"estimated_sell_value={estimated_sell_value}")
    if estimated_run_cost > budget:
        parts.append("estimated_run_cost_exceeds_budget")
    return tuple(parts)


def _next_safe_actions(decision: AgentInferenceDecision) -> tuple[str, ...]:
    if decision == AgentInferenceDecision.SELL_UNUSED_INFERENCE:
        return ("create_dry_run_listing", "keep_provider_credentials_private", "audit_listing")
    if decision == AgentInferenceDecision.DEFER_TASK:
        return ("record_deferred_demand", "retry_when_price_falls")
    if decision == AgentInferenceDecision.DOWNGRADE_INTELLIGENCE_TIER:
        return ("request_lower_cost_model", "preserve_quality_floor")
    if decision == AgentInferenceDecision.SIMULATE_FUTURES_HEDGE:
        return ("run_simulation_only", "require_legal_and_compliance_review_before_live_use")
    return ("execute_dry_run_route", "record_usage", "audit_decision")


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _nonnegative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, parsed)


def _flatten_payload(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_flatten_payload(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_payload(item) for item in value)
    return str(value)


def _proxy_input_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _flatten_payload(value)
    if isinstance(value, (list, tuple)):
        return " ".join(_proxy_input_text(item) for item in value)
    return str(value)


def _proxy_embedding_inputs(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(_proxy_input_text(item) for item in value) or ("",)
    return (_proxy_input_text(value),)


def _deterministic_embedding_vector(value: str) -> tuple[float, ...]:
    digest = sha256(value.encode("utf-8")).digest()
    return tuple(round((byte / 255.0) * 2.0 - 1.0, 6) for byte in digest[:16])

def _tuple_str(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value in (None, ""):
        return default
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return default


def _reject_raw_provider_credentials(payload: Mapping[str, Any]) -> None:
    banned_keys = {
        "api_key",
        "provider_api_key",
        "raw_api_key",
        "access_token",
        "refresh_token",
        "authorization",
        "bearer_token",
        "credential",
        "credentials",
    }
    present = sorted(key for key in payload if str(key).lower() in banned_keys)
    if present:
        raise ValueError(f"raw inference provider credential rejected: {present[0]}")

def _dataclass_from_record(model_type: type[_T], record: Mapping[str, Any]) -> _T:
    allowed = {field.name for field in fields(cast(Any, model_type))}
    constructor = cast(Any, model_type)
    return cast(_T, constructor(**{key: value for key, value in record.items() if key in allowed}))

def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
