"""Production-planning service layer for Flow Memory Compute Market."""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from flow_memory.compute_market.config import ComputeMarketConfig, config_from_env
from flow_memory.compute_market.adapters import build_external_provider_adapter
from flow_memory.compute_market.audit_export import AuditExporterProtocol, LocalFileAuditExporter, audit_events_from_export_file, build_checkpoint, create_audit_exporter, verify_audit_export, verify_exported_chain
from flow_memory.compute_market.controls import CircuitBreaker, RateLimiter, RedisCircuitBreaker, RedisRateLimiter, create_circuit_breaker, create_rate_limiter
from flow_memory.compute_market.errors import compute_error, policy_denial_error
from flow_memory.compute_market.provider_contracts import validate_provider_quote_contract, verify_provider_quote_signature
from flow_memory.compute_market.memory import query_economic_memory_typed, query_request_from_payload
from flow_memory.compute_market.models import (
    AuditEvent,
    ComputeMarketHealth,
    ComputeMarketPolicy,
    ComputePriceSnapshot,
    ComputeProvider,
    ComputeStatement,
    IntelligencePlan,
    IntelligenceTier,
    IntelligenceUsageRecord,
    PriceAnomaly,
    PriceForecast,
    ProviderHealthSnapshot,
    ProviderPriceIndex,
    ProviderClass,
    RoutePriceIndex,
    RunDecision,
)
from flow_memory.compute_market.observability import AlertEvaluator, ComputeMarketTelemetry
from flow_memory.compute_market.planner import build_compute_plan, build_task_profile, replay_decision
from flow_memory.compute_market.pricing import compute_quote_comparison
from flow_memory.compute_market.registry import default_compute_providers, default_compute_routes
from flow_memory.compute_market.storage import deterministic_id, migration_plan, schema_hash, utc_now_iso
from flow_memory.compute_market.storage_backends import ComputeMarketStoreProtocol, create_compute_market_store
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import verify_payload
from flow_memory.core.types import new_id

_UNSAFE_KEYS = frozenset(
    {
        "private_key",
        "privateKey",
        "seed_phrase",
        "seedPhrase",
        "seed phrase",
        "mnemonic",
        "secret_key",
        "wallet_private_key",
        "live_settlement",
        "live_settlement_required",
        "broadcast",
        "broadcast_allowed",
        "sendTransaction",
        "signTransaction",
        "custody",
        "transfer",
        "withdraw",
        "deposit",
        "settle",
        "settlement_broadcast",
        "settlement_mode",
    }
)
_SAFE_DRY_RUN_SETTLEMENT_MODES = frozenset(
    {
        "generic_dry_run",
        "http_402_dry_run",
        "solana_usdc_dry_run",
        "base_sepolia_erc4337_dry_run",
        "no_payment",
        "dry_run",
    }
)



class ComputeMarketService:
    def __init__(
        self,
        store: ComputeMarketStoreProtocol | None = None,
        config: ComputeMarketConfig | None = None,
        telemetry: ComputeMarketTelemetry | None = None,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        audit_exporter: AuditExporterProtocol | None = None,
    ) -> None:
        self.config = config or config_from_env()
        errors = self.config.validate()
        if errors:
            raise ValueError("; ".join(errors))
        self.store = store or create_compute_market_store(self.config)
        self.telemetry = telemetry or ComputeMarketTelemetry()
        self.rate_limiter = rate_limiter or create_rate_limiter(self.config)
        self.circuit_breaker = circuit_breaker or create_circuit_breaker(self.config)
        self.audit_exporter = audit_exporter or create_audit_exporter(
            self.config.audit_export_uri,
            s3_region=self.config.audit_export_s3_region,
            s3_endpoint_url=self.config.audit_export_s3_endpoint_url,
            object_lock_mode=self.config.audit_export_object_lock_mode,
            retention_days=self.config.audit_export_retention_days,
        )
        self.seed_defaults()

    def seed_defaults(self) -> None:
        for provider in default_compute_providers():
            enriched = _enrich_provider(provider)
            self.store.put_record(
                "compute_provider",
                enriched.provider_id,
                enriched.as_record(),
                provider_id=enriched.provider_id,
                status=enriched.status,
            )
        for route in default_compute_routes():
            self.store.put_record(
                "compute_route",
                route.route_id,
                route.as_record(),
                provider_id=route.provider_id,
                route_id=route.route_id,
                status="enabled" if route.enabled else "disabled",
            )
        policy = ComputeMarketPolicy()
        self.store.put_record("compute_market_policy", policy.policy_id, policy.as_record(), status="active")

    def plan(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/plan", request_id=request_id)
        if limited is not None:
            return limited
        idempotency_key = str(payload.get("idempotency_key", ""))
        if idempotency_key:
            existing = self.store.find_by_idempotency("route_decision", idempotency_key)
            if existing:
                return {"ok": True, "compute_plan": existing.get("compute_plan", {}), "idempotent_replay": True}
        payload_for_plan = self._payload_with_circuit_denials(payload, request_id=request_id)
        self.telemetry.increment("compute_plan_requests_total", {"strategy": str(payload_for_plan.get("selection_strategy", "balanced"))})
        self._audit("compute.plan.requested", payload_for_plan, request_id=request_id, result="requested")
        with self.telemetry.span("compute.plan_request", {"request_id": request_id}):
            plan = build_compute_plan({**dict(payload_for_plan), "request_id": request_id, "idempotency_key": idempotency_key})
        record = plan.as_record()
        self._persist_plan(record)
        for rejected_route in plan.rejected_routes:
            route_id = str(rejected_route.get("route_id", ""))
            reasons = tuple(plan.rejected_reasons.get(route_id, ()))
            self.telemetry.increment(
                "compute_route_rejected_total",
                {
                    "route_id": route_id,
                    "provider_id": str(rejected_route.get("provider_id", "")),
                    "reason": "|".join(reasons) or "policy_rejected",
                },
            )
        if plan.fail_closed_errors:
            self.telemetry.increment("compute_plan_fail_closed_total")
            self.telemetry.increment("compute_policy_denials_total")
            self._audit(
                "compute.plan.failed_closed",
                payload_for_plan,
                request_id=request_id,
                result="fail_closed",
                reason_codes=plan.fail_closed_errors,
                decision_id=plan.decision_id,
            )
            error = policy_denial_error(request_id, plan.fail_closed_errors)
            record["error"] = error.as_record()
        else:
            self.telemetry.increment("compute_route_selected_total")
            self.telemetry.observe(
                "compute_estimated_cost",
                float((plan.normalized_quote or {}).get("estimated_total_cost") or 0.0),
                labels={"route_id": str((plan.selected_route or {}).get("route_id", ""))},
            )
            self._audit(
                "compute.plan.completed",
                payload_for_plan,
                request_id=request_id,
                result="completed",
                decision_id=plan.decision_id,
                route_id=str((plan.selected_route or {}).get("route_id", "")),
                provider_id=str((plan.selected_route or {}).get("provider_id", "")),
            )
        self.telemetry.log("compute.plan", _log_fields(record))
        return {"ok": plan.ok, "compute_plan": record}

    def marketplace_plan(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.plan({**dict(payload), "marketplace_only": True, "selection_strategy": payload.get("selection_strategy", "marketplace_preferred")})

    def intelligence_plan(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/intelligence-plan", request_id=request_id)
        if limited is not None:
            return limited
        idempotency_key = str(payload.get("idempotency_key", ""))
        if idempotency_key:
            existing = self.store.find_by_idempotency("intelligence_plan", idempotency_key)
            if existing:
                return {"ok": True, "intelligence_plan": existing, "idempotent_replay": True}
        profile = build_task_profile({**dict(payload), "request_id": request_id})
        tier = _recommended_intelligence_tier(payload, profile.as_record())
        reasoning_budget = _recommended_reasoning_budget(payload, tier)
        urgency = _intelligence_urgency(payload)
        quality_target = _intelligence_quality_target(payload)
        plan_payload = _intelligence_plan_payload(payload, tier, reasoning_budget, urgency, quality_target)
        compute_result = self.plan({**plan_payload, "request_id": request_id, "idempotency_key": idempotency_key})
        compute_plan = compute_result.get("compute_plan", {}) if isinstance(compute_result.get("compute_plan"), Mapping) else {}
        price_context = self._price_context(compute_plan, payload)
        run_decision = _intelligence_run_decision(payload, tier, reasoning_budget, urgency, compute_plan, price_context)
        intelligence_plan = IntelligencePlan(
            intelligence_plan_id=deterministic_id("intelligence_plan", {"request_id": request_id, "task_id": profile.task_id, "tier": tier, "decision": run_decision}),
            task_id=profile.task_id,
            agent_id=profile.agent_id,
            goal_id=profile.goal_id,
            recommended_intelligence_tier=tier,
            recommended_reasoning_budget=reasoning_budget,
            recommended_route_types=_recommended_route_types(tier, payload),
            recommended_provider_classes=_recommended_provider_classes(tier),
            max_recommended_spend=_max_recommended_spend(payload, tier, profile.estimated_value),
            run_decision=run_decision,
            defer_until=_defer_until(payload, urgency, run_decision),
            downgrade_options=_downgrade_options(tier, compute_plan),
            reserve_capacity_recommended=run_decision == RunDecision.RESERVE_CAPACITY.value or tier == IntelligenceTier.RESERVED_CAPACITY.value,
            rationale=_intelligence_rationale(tier, run_decision, compute_plan, price_context),
            next_safe_actions=_intelligence_next_safe_actions(run_decision, compute_plan),
            compute_plan=compute_plan,
            price_context=price_context,
            dry_run_only=True,
            funds_moved=False,
            broadcast_allowed=False,
            private_key_required=False,
            created_at=utc_now_iso(),
            tenant_id=profile.tenant_id,
            workspace_id=profile.workspace_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        ).as_record()
        self.store.put_record(
            "intelligence_plan",
            str(intelligence_plan["intelligence_plan_id"]),
            intelligence_plan,
            tenant_id=str(intelligence_plan.get("tenant_id", "")),
            workspace_id=str(intelligence_plan.get("workspace_id", "")),
            agent_id=profile.agent_id,
            goal_id=profile.goal_id,
            task_type=profile.task_type,
            task_hash=profile.task_hash,
            status=run_decision,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        usage_record = _intelligence_usage_record(intelligence_plan, compute_plan).as_record()
        self.store.put_record(
            "intelligence_usage_record",
            str(usage_record["usage_record_id"]),
            usage_record,
            tenant_id=str(usage_record.get("tenant_id", "")),
            workspace_id=str(usage_record.get("workspace_id", "")),
            agent_id=profile.agent_id,
            goal_id=profile.goal_id,
            provider_id=str(usage_record.get("provider_id", "")),
            route_id=str(usage_record.get("route_id", "")),
            task_hash=profile.task_hash,
            status="planned",
            request_id=request_id,
        )
        self.telemetry.increment("compute_intelligence_plan_created_total", {"tier": tier, "run_decision": run_decision})
        selected_route_raw = compute_plan.get("selected_route")
        selected_route = selected_route_raw if isinstance(selected_route_raw, Mapping) else {}
        self._audit(
            "compute.intelligence_plan.created",
            payload,
            request_id=request_id,
            result=run_decision,
            decision_id=str(compute_plan.get("decision_id", "")),
            route_id=str(selected_route.get("route_id", "")),
        )
        return {
            "ok": True,
            "intelligence_plan": intelligence_plan,
            "usage_record": usage_record,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def compute_prices(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = dict(payload or {})
        snapshots = self._price_snapshots(filters)
        route_indexes = tuple(_route_price_index(group).as_record() for group in _price_groups(snapshots, "route_id") if group)
        provider_indexes = tuple(_provider_price_index(group).as_record() for group in _price_groups(snapshots, "provider_id") if group)
        for index in route_indexes:
            self.store.put_record("route_price_index", deterministic_id("route_price_index", index), index, provider_id=str(index.get("provider_id", "")), route_id=str(index.get("route_id", "")), task_type=str(index.get("unit_type", "")))
        for index in provider_indexes:
            self.store.put_record("provider_price_index", deterministic_id("provider_price_index", index), index, provider_id=str(index.get("provider_id", "")), task_type=str(index.get("unit_type", "")))
        return {"ok": True, "prices": route_indexes, "provider_prices": provider_indexes, "snapshot_count": len(snapshots)}

    def compute_price_history(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = dict(payload or {})
        limit = int(filters.get("limit", 100) or 100)
        page = self.store.list_records("compute_price_snapshot", filters=filters, limit=limit, cursor=str(filters.get("cursor", "")))
        return {"ok": True, "price_history": page.records, "next_cursor": page.next_cursor}

    def compute_price_anomalies(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = dict(payload or {})
        snapshots = self._price_snapshots(filters)
        anomalies = tuple(_price_anomaly(snapshot, _median_price_for_snapshot(snapshot, snapshots)).as_record() for snapshot in snapshots if _price_is_anomalous(snapshot, _median_price_for_snapshot(snapshot, snapshots)))
        for anomaly in anomalies:
            self.store.put_record("price_anomaly", str(anomaly["anomaly_id"]), anomaly, provider_id=str(anomaly.get("provider_id", "")), route_id=str(anomaly.get("route_id", "")), task_type=str(anomaly.get("unit_type", "")), status=str(anomaly.get("severity", "")))
        return {"ok": True, "price_anomalies": anomalies, "anomaly_count": len(anomalies)}

    def compute_price_forecast(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        filters = {key: value for key, value in dict(payload).items() if key in {"tenant_id", "workspace_id", "provider_id", "route_id", "task_type"} and value not in (None, "")}
        snapshots = self._price_snapshots(filters)
        forecast = _price_forecast(payload, snapshots).as_record()
        self.store.put_record("price_forecast", str(forecast["forecast_id"]), forecast, provider_id=str(forecast.get("provider_id", "")), route_id=str(forecast.get("route_id", "")), task_type=str(forecast.get("unit_type", "")), request_id=str(payload.get("request_id", "")))
        return {"ok": True, "price_forecast": forecast}

    def compute_usage(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = _usage_filters(payload or {})
        page = self.store.list_records("intelligence_usage_record", filters=filters, limit=int((payload or {}).get("limit", 100) or 100), cursor=str((payload or {}).get("cursor", "")))
        summary = _usage_summary(page.records)
        return {"ok": True, "usage_records": page.records, "summary": summary, "next_cursor": page.next_cursor}

    def compute_usage_by_agent(self, agent_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        return self.compute_usage({**dict(payload or {}), "agent_id": agent_id})

    def compute_usage_by_goal(self, goal_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        return self.compute_usage({**dict(payload or {}), "goal_id": goal_id})

    def compute_usage_statement(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        request = dict(payload or {})
        filters = _usage_filters(request)
        records = self._all_records("intelligence_usage_record", filters=filters)
        period = str(request.get("period") or utc_now_iso()[:7])
        workspace_id = str(request.get("workspace_id", request.get("tenant_id", "")))
        statement = _compute_statement(records, workspace_id=workspace_id, period=period).as_record()
        self.store.put_record("compute_statement", str(statement["statement_id"]), statement, tenant_id=str(request.get("tenant_id", "")), workspace_id=workspace_id, status=period)
        return {"ok": True, "statement": statement}

    def quote(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/quote", request_id=request_id)
        if limited is not None:
            return limited
        self.telemetry.increment("compute_quote_requests_total")
        plan = build_compute_plan({**dict(self._payload_with_circuit_denials(payload, request_id=request_id)), "request_id": request_id})
        decision = plan.route_decision
        quotes = tuple(decision.get("normalized_quotes", ())) if isinstance(decision, Mapping) else ()
        for quote in quotes:
            if isinstance(quote, Mapping):
                self.store.put_record(
                    "compute_quote",
                    str(quote.get("quote_id", deterministic_id("quote", quote))),
                    quote,
                    provider_id=str(quote.get("provider_id", "")),
                    route_id=str(quote.get("route_id", "")),
                    task_hash=str(plan.profile.get("task_hash", "")),
                    status=str(quote.get("status", "")),
                    expires_at=str(quote.get("expires_at", "")),
                    request_id=request_id,
                )
        self._audit("compute.quote.completed", payload, request_id=request_id, result="completed")
        return {"ok": True, "profile": plan.profile, "quotes": quotes, "request_id": request_id}

    def route(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        limited = self._rate_limit_response(payload, "POST /compute/route", request_id=_request_id(payload))
        if limited is not None:
            return limited
        result = self.plan(payload)
        plan = result.get("compute_plan", {}) if isinstance(result.get("compute_plan"), Mapping) else {}
        return {"ok": bool(plan.get("ok")), "route_decision": plan.get("route_decision", {}), "error": result.get("error", {})}

    def payment_plan(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = self.plan(payload)
        if "compute_plan" not in result:
            return result
        plan = result["compute_plan"]
        self.telemetry.increment("compute_payment_plan_created_total")
        self._audit("compute.payment_plan.created", payload, request_id=str(plan.get("request_id", "")), result="created")
        return {
            "ok": bool(plan.get("ok")),
            "payment_plan": plan.get("payment_plan", {}),
            "settlement_intent": plan.get("settlement_intent", {}),
            "fail_closed_errors": plan.get("fail_closed_errors", ()),
            "dry_run_only": True,
            "safety": "dry-run only; no private keys, no funds moved, no transaction broadcast",
        }

    def simulate_settlement(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = self.plan(payload)
        if "compute_plan" not in result:
            return result
        plan = result["compute_plan"]
        self.telemetry.increment("compute_settlement_simulated_total")
        self.telemetry.increment("settlement_attempt_total")
        self._audit("compute.settlement.simulated", payload, request_id=str(plan.get("request_id", "")), result="simulated")
        return {
            "ok": bool(plan.get("ok")),
            "settlement_intent": plan.get("settlement_intent", {}),
            "payment_plan": plan.get("payment_plan", {}),
            "fail_closed_errors": plan.get("fail_closed_errors", ()),
            "dry_run_only": True,
        }

    def list_providers(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        page = self.store.list_records("compute_provider", filters=payload or {}, limit=int((payload or {}).get("limit", 100)), cursor=str((payload or {}).get("cursor", "")))
        return {"ok": True, "providers": page.records, "next_cursor": page.next_cursor}

    def get_provider(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is None or not _tenant_can_access_catalog_record(payload or {}, provider):
            raise KeyError(f"Unknown compute provider: {provider_id}")
        return {"ok": True, "provider": provider}

    def create_provider(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        _assert_no_inline_credentials(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/providers", request_id=request_id, provider_id=str(payload.get("provider_id", "")))
        if limited is not None:
            return limited
        provider_id = str(payload.get("provider_id") or deterministic_id("provider", payload))
        provider_payload = _provider_admin_payload(payload)
        provider = _provider_with_credential_bindings({**provider_payload, "provider_id": provider_id, "status": str(provider_payload.get("status", "active"))}, payload)
        self.store.put_record("compute_provider", provider_id, provider, provider_id=provider_id, status=str(provider["status"]), request_id=request_id)
        secret_ref = _provider_secret_reference(payload, provider_id=provider_id, request_id=request_id)
        if secret_ref:
            self.store.put_record("provider_secret_ref", str(secret_ref["secret_ref_id"]), secret_ref, provider_id=provider_id, status="active", request_id=request_id)
        self._audit("compute.provider.created", payload, request_id=request_id, result="created", provider_id=provider_id)
        return {"ok": True, "provider": provider, "credential_storage": "external_secret_reference_only", "inline_secrets_stored": False}

    def update_provider(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        _assert_no_inline_credentials(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "PATCH /compute/providers/{provider_id}", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        current = dict(self.get_provider(provider_id, payload)["provider"])
        updated = _provider_with_credential_bindings({**current, **_provider_admin_payload(payload), "provider_id": provider_id}, payload)
        for key in ("credentials", *_CREDENTIAL_VALUE_KEYS):
            updated.pop(key, None)
        self.store.put_record("compute_provider", provider_id, updated, provider_id=provider_id, status=str(updated.get("status", "")), request_id=request_id)
        secret_ref = _provider_secret_reference(payload, provider_id=provider_id, request_id=request_id)
        if secret_ref:
            self.store.put_record("provider_secret_ref", str(secret_ref["secret_ref_id"]), secret_ref, provider_id=provider_id, status="active", request_id=request_id)
        self._audit("compute.provider.updated", payload, request_id=request_id, result="updated", provider_id=provider_id)
        return {"ok": True, "provider": updated, "credential_storage": "external_secret_reference_only", "inline_secrets_stored": False}

    def disable_provider(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/providers/{provider_id}/disable", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        current = dict(self.get_provider(provider_id, payload)["provider"])
        current["status"] = "disabled"
        current["disabled_at"] = utc_now_iso()
        self.store.put_record("compute_provider", provider_id, current, provider_id=provider_id, status="disabled", request_id=request_id)
        invalidated_cache = self._invalidate_quote_cache_entries({"provider_id": provider_id, "reason": "provider_disabled"}, request_id=request_id)
        self._audit("compute.provider.disabled", payload, request_id=request_id, result="disabled", provider_id=provider_id)
        return {"ok": True, "provider": current, "invalidated_quote_cache_entries": invalidated_cache}

    def provider_health(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/providers/{provider_id}/health-check", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        provider_record = self.store.get_record("compute_provider", provider_id)
        if provider_record is not None and not _tenant_can_access_catalog_record(payload, provider_record):
            raise KeyError(f"Unknown compute provider: {provider_id}")
        circuit = self.circuit_breaker.allow_request(provider_id, adapter_type="health_check")
        if not circuit.ok:
            self._audit("compute.provider.circuit_open", payload, request_id=request_id, result="skipped", reason_codes=("circuit_open",), provider_id=provider_id)
            return {
                "ok": False,
                "provider_health": {
                    "provider_id": provider_id,
                    "status": "temporarily_disabled",
                    "error_code": "circuit_open",
                    "circuit": circuit.as_record(),
                },
            }
        provider = self.get_provider(provider_id, payload)["provider"]
        routes = tuple(route for route in self.store.list_records("compute_route", filters={"provider_id": provider_id}).records)
        checked_at = utc_now_iso()
        provider_active = provider.get("status") == "active"
        probe = _probe_provider_health_endpoint(provider, self.config) if provider_active else _disabled_provider_health_probe(provider)
        if provider_active and bool(probe.get("healthy")):
            self.circuit_breaker.record_success(provider_id, adapter_type="health_check")
        elif provider_active:
            self.circuit_breaker.record_failure(
                provider_id,
                adapter_type="health_check",
                error_class=str(probe.get("error_code") or "provider_health_unhealthy"),
            )
        snapshot = ProviderHealthSnapshot(
            health_snapshot_id=deterministic_id("provider_health", {"provider_id": provider_id, "created_at": checked_at}),
            provider_id=provider_id,
            status=str(probe.get("status") or ("healthy" if provider_active else "disabled")),
            reliability_score=float(provider.get("reliability_score", 0.0) or 0.0),
            latency_ms=int(probe.get("latency_ms", provider.get("average_latency_ms", 0) or 0) or 0),
            checked_at=checked_at,
            route_count=len(routes),
            error_code=str(probe.get("error_code", "")),
            message=str(probe.get("message", "")),
            rate_limits=provider.get("rate_limit_profile", {}) if isinstance(provider.get("rate_limit_profile"), Mapping) else {},
            metadata=dict(probe.get("metadata", {})) if isinstance(probe.get("metadata"), Mapping) else {},
        )
        record = snapshot.as_record()
        self.store.put_record(
            "provider_health_snapshot",
            snapshot.health_snapshot_id,
            record,
            tenant_id=str(provider.get("tenant_id", payload.get("tenant_id", ""))),
            workspace_id=str(provider.get("workspace_id", payload.get("workspace_id", ""))),
            provider_id=provider_id,
            status=snapshot.status,
        )
        self._audit(
            "compute.provider.health_checked",
            payload,
            request_id=request_id,
            result=snapshot.status,
            reason_codes=(snapshot.error_code,) if snapshot.error_code else (),
            provider_id=provider_id,
        )
        return {"ok": snapshot.status in {"healthy", "disabled"}, "provider_health": record}

    def apply_market_provider(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        _assert_no_inline_credentials(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/apply", request_id=request_id, provider_id=str(payload.get("provider_id", "")))
        if limited is not None:
            return limited
        application = _provider_application(payload, request_id=request_id)
        application_id = str(application["application_id"])
        provider_id = str(application["provider_id"])
        self.store.put_record(
            "market_provider_application",
            application_id,
            application,
            provider_id=provider_id,
            status=str(application["status"]),
            request_id=request_id,
            idempotency_key=str(payload.get("idempotency_key", "")),
        )
        secret_ref = _provider_secret_reference(payload, provider_id=provider_id, request_id=request_id)
        if secret_ref:
            self.store.put_record(
                "provider_secret_ref",
                str(secret_ref["secret_ref_id"]),
                secret_ref,
                provider_id=provider_id,
                status="active",
                request_id=request_id,
            )
        self._audit("market.provider.applied", payload, request_id=request_id, result="submitted", provider_id=provider_id)
        return {
            "ok": True,
            "provider_application": application,
            "credential_storage": "external_secret_reference_only",
            "inline_secrets_stored": False,
        }

    def market_provider(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        try:
            application = self._latest_provider_application(provider_id, payload)
        except KeyError:
            application = {}
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is not None and not _tenant_can_access_catalog_record(payload, provider):
            provider = None
        if not application and provider is None:
            raise KeyError(f"Unknown market provider: {provider_id}")
        return {
            "ok": True,
            "provider_application": application,
            "provider": provider or {},
            "reputation": self.provider_reputation(provider_id, payload)["reputation"],
        }

    def verify_market_provider(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/{provider_id}/verify", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        application = self._latest_provider_application(provider_id, payload)
        if str(application.get("status", "")) not in {"pending", "probation"}:
            raise ValueError("provider application must be pending or probation before verification")
        verified_at = utc_now_iso()
        updated_application = {
            **application,
            "status": "verified",
            "verified": True,
            "verified_at": verified_at,
            "verification_notes": str(payload.get("verification_notes", "")),
            "updated_at": verified_at,
        }
        self.store.put_record(
            "market_provider_application",
            str(updated_application["application_id"]),
            updated_application,
            provider_id=provider_id,
            status="verified",
            request_id=request_id,
            tenant_id=str(updated_application.get("tenant_id", "")),
            workspace_id=str(updated_application.get("workspace_id", "")),
        )
        provider = _provider_from_application(updated_application)
        self.store.put_record(
            "compute_provider",
            provider_id,
            provider,
            tenant_id=str(provider.get("tenant_id", "")),
            workspace_id=str(provider.get("workspace_id", "")),
            provider_id=provider_id,
            status="active",
            request_id=request_id,
        )
        routes = tuple(_provider_routes_from_application(updated_application, provider))
        for route in routes:
            self.store.put_record(
                "compute_route",
                str(route["route_id"]),
                route,
                tenant_id=str(route.get("tenant_id", "")),
                workspace_id=str(route.get("workspace_id", "")),
                provider_id=provider_id,
                route_id=str(route["route_id"]),
                task_type=str(route.get("unit_type", "")),
                status="enabled" if route.get("enabled", True) else "disabled",
                request_id=request_id,
            )
        reputation = _provider_reputation(provider_id, jobs=(), quotes=(), health=(), fraud_signals=(), provider=provider)
        self.store.put_record(
            "provider_reputation",
            provider_id,
            reputation,
            tenant_id=str(provider.get("tenant_id", "")),
            workspace_id=str(provider.get("workspace_id", "")),
            provider_id=provider_id,
            status="active",
            request_id=request_id,
        )
        self._audit("market.provider.verified", payload, request_id=request_id, result="verified", provider_id=provider_id)
        return {
            "ok": True,
            "provider_application": updated_application,
            "provider": provider,
            "routes": routes,
            "reputation": reputation,
        }

    def reject_market_provider(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/{provider_id}/reject", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        application = self._latest_provider_application(provider_id, payload)
        if str(application.get("status", "")) in {"verified", "disabled"}:
            raise ValueError("verified or disabled provider applications must be disabled, not rejected")
        rejected_at = utc_now_iso()
        reason = str(payload.get("rejection_reason", payload.get("reason", ""))).strip()
        updated_application = {
            **application,
            "status": "rejected",
            "verified": False,
            "rejected_at": rejected_at,
            "rejection_reason": reason,
            "review_notes": str(payload.get("review_notes", "")),
            "reviewed_by": str(payload.get("reviewed_by", payload.get("actor_id", ""))),
            "updated_at": rejected_at,
        }
        self.store.put_record(
            "market_provider_application",
            str(updated_application["application_id"]),
            updated_application,
            provider_id=provider_id,
            status="rejected",
            request_id=request_id,
            tenant_id=str(updated_application.get("tenant_id", "")),
            workspace_id=str(updated_application.get("workspace_id", "")),
        )
        self._audit("market.provider.rejected", payload, request_id=request_id, result="rejected", reason_codes=("provider_application_rejected",), provider_id=provider_id)
        return {"ok": True, "provider_application": updated_application}

    def request_market_provider_revision(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/{provider_id}/request-revision", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        application = self._latest_provider_application(provider_id, payload)
        if str(application.get("status", "")) in {"verified", "disabled", "rejected"}:
            raise ValueError("provider application revisions can only be requested for active pending reviews")
        revision_requested_at = utc_now_iso()
        revision_notes = str(payload.get("revision_notes", payload.get("review_notes", ""))).strip()
        updated_application = {
            **application,
            "status": "revision_requested",
            "verified": False,
            "revision_requested_at": revision_requested_at,
            "revision_notes": revision_notes,
            "reviewed_by": str(payload.get("reviewed_by", payload.get("actor_id", ""))),
            "updated_at": revision_requested_at,
        }
        self.store.put_record(
            "market_provider_application",
            str(updated_application["application_id"]),
            updated_application,
            provider_id=provider_id,
            status="revision_requested",
            request_id=request_id,
            tenant_id=str(updated_application.get("tenant_id", "")),
            workspace_id=str(updated_application.get("workspace_id", "")),
        )
        self._audit("market.provider.revision_requested", payload, request_id=request_id, result="revision_requested", reason_codes=("provider_application_revision_requested",), provider_id=provider_id)
        return {"ok": True, "provider_application": updated_application}

    def provider_conformance(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/{provider_id}/conformance", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        try:
            self._latest_provider_application(provider_id, payload)
        except KeyError:
            self.get_provider(provider_id, payload)
        quote = payload.get("sample_quote", payload.get("quote", {}))
        if not isinstance(quote, Mapping):
            raise ValueError("sample_quote must be an object")
        public_key = _provider_public_key(payload, provider_id, self)
        validation = validate_provider_quote_contract(
            quote,
            provider_id=provider_id,
            allowed_assets=_tuple(payload.get("allowed_assets", ())),
            allowed_networks=_tuple(payload.get("allowed_networks", ())),
            public_key=public_key,
        )
        signed_quote_valid = verify_provider_quote_signature(quote, public_key) if public_key else False
        fraud_signals: tuple[Mapping[str, Any], ...] = ()
        if not validation.ok:
            fraud_signals = _fraud_signals_from_validation(
                self.store,
                provider_id=provider_id,
                route_id=str(quote.get("route_id", "")),
                quote_id=str(quote.get("quote_id", "")),
                validation_errors=validation.error_codes,
                request_id=request_id,
                tenant_id=str(payload.get("tenant_id", "")),
                workspace_id=str(payload.get("workspace_id", "")),
            )
        status = "conformant" if validation.ok else "failed"
        snapshot = {
            "health_snapshot_id": deterministic_id("provider_conformance", {"provider_id": provider_id, "request_id": request_id}),
            "provider_id": provider_id,
            "status": status,
            "contract_ok": validation.ok,
            "signed_quote_valid": signed_quote_valid,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "created_at": utc_now_iso(),
            "request_id": request_id,
            "error_codes": validation.error_codes,
            "warnings": validation.warnings,
            "fraud_signal_count": len(fraud_signals),
        }
        self.store.put_record(
            "provider_health_snapshot",
            str(snapshot["health_snapshot_id"]),
            snapshot,
            tenant_id=str(payload.get("tenant_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            provider_id=provider_id,
            status=status,
            request_id=request_id,
        )
        self._audit("market.provider.conformance_checked", payload, request_id=request_id, result=status, reason_codes=validation.error_codes, provider_id=provider_id)
        return {
            "ok": validation.ok,
            "provider_id": provider_id,
            "validation": validation.as_record(),
            "signed_quote_valid": signed_quote_valid,
            "conformance": snapshot,
            "fraud_signals": fraud_signals,
        }

    def disable_market_provider(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/providers/{provider_id}/disable", request_id=request_id, provider_id=provider_id)
        if limited is not None:
            return limited
        disabled_at = utc_now_iso()
        application = self._latest_provider_application(provider_id, payload)
        updated_application = {**application, "status": "disabled", "disabled_at": disabled_at, "updated_at": disabled_at}
        self.store.put_record(
            "market_provider_application",
            str(updated_application["application_id"]),
            updated_application,
            provider_id=provider_id,
            status="disabled",
            request_id=request_id,
            tenant_id=str(updated_application.get("tenant_id", "")),
            workspace_id=str(updated_application.get("workspace_id", "")),
        )
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is not None:
            disabled_provider = {**dict(provider), "status": "disabled", "disabled_at": disabled_at, "updated_at": disabled_at}
            if not _tenant_can_access_catalog_record(payload, disabled_provider):
                raise KeyError(f"Unknown market provider: {provider_id}")
            self.store.put_record(
                "compute_provider",
                provider_id,
                disabled_provider,
                tenant_id=str(disabled_provider.get("tenant_id", "")),
                workspace_id=str(disabled_provider.get("workspace_id", "")),
                provider_id=provider_id,
                status="disabled",
                request_id=request_id,
            )
        invalidated_cache = self._invalidate_quote_cache_entries({"provider_id": provider_id, "reason": "provider_disabled"}, request_id=request_id)
        self._audit("market.provider.disabled", payload, request_id=request_id, result="disabled", provider_id=provider_id)
        return {"ok": True, "provider_application": updated_application, "invalidated_quote_cache_entries": invalidated_cache}

    def provider_reputation(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        filters: dict[str, Any] = {"provider_id": provider_id}
        tenant_id = _payload_tenant_id(payload)
        if tenant_id:
            filters["tenant_id"] = tenant_id
        jobs = tuple(self.store.list_records("compute_job", filters=filters, limit=500).records)
        quotes = tuple(self.store.list_records("compute_quote", filters=filters, limit=500).records)
        health = tuple(self.store.list_records("provider_health_snapshot", filters=filters, limit=100).records)
        fraud_signals = tuple(self.store.list_records("provider_fraud_signal", filters=filters, limit=500).records)
        refunds = tuple(self.store.list_records("refund", filters=filters, limit=500).records)
        provider = self.store.get_record("compute_provider", provider_id) or {}
        if isinstance(provider, Mapping) and provider and not _tenant_can_access_catalog_record(payload, provider):
            raise KeyError(f"Unknown compute provider: {provider_id}")
        reputation = _provider_reputation(provider_id, jobs=jobs, quotes=quotes, health=health, fraud_signals=fraud_signals, refunds=refunds, provider=provider if isinstance(provider, Mapping) else {})
        if not tenant_id:
            self.store.put_record("provider_reputation", provider_id, reputation, provider_id=provider_id, status=str(reputation["status"]))
        return {"ok": True, "reputation": reputation}

    def _latest_provider_application(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        applications = self.store.list_records("market_provider_application", filters={"provider_id": provider_id}, limit=500).records
        accessible = tuple(
            application for application in applications if _tenant_can_access_catalog_record(payload or {}, application)
        )
        if not accessible:
            raise KeyError(f"Unknown market provider application: {provider_id}")
        return max(
            accessible,
            key=lambda application: (
                str(application.get("updated_at", "")),
                str(application.get("created_at", "")),
                str(application.get("application_id", "")),
            ),
        )

    def list_routes(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        page = self.store.list_records("compute_route", filters=payload or {}, limit=int((payload or {}).get("limit", 100)), cursor=str((payload or {}).get("cursor", "")))
        return {"ok": True, "routes": page.records, "next_cursor": page.next_cursor}

    def get_route(self, route_id: str) -> Mapping[str, Any]:
        route = self.store.get_record("compute_route", route_id)
        if route is None:
            raise KeyError(f"Unknown compute route: {route_id}")
        return {"ok": True, "route": route}

    def create_route(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "POST /compute/routes", request_id=_request_id(payload), provider_id=str(payload.get("provider_id", "")), route_id=str(payload.get("route_id", "")))
        if limited is not None:
            return limited
        route_id = str(payload.get("route_id") or deterministic_id("route", payload))
        route = {**dict(payload), "route_id": route_id, "enabled": bool(payload.get("enabled", True))}
        self.store.put_record("compute_route", route_id, route, provider_id=str(route.get("provider_id", "")), route_id=route_id, status="enabled" if route["enabled"] else "disabled")
        self._audit("compute.route.created", payload, result="created", route_id=route_id)
        return {"ok": True, "route": route}

    def update_route(self, route_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "PATCH /compute/routes/{route_id}", request_id=_request_id(payload), route_id=route_id)
        if limited is not None:
            return limited
        current = dict(self.get_route(route_id)["route"])
        updated = {**current, **dict(payload), "route_id": route_id}
        self.store.put_record("compute_route", route_id, updated, provider_id=str(updated.get("provider_id", "")), route_id=route_id, status="enabled" if updated.get("enabled", True) else "disabled")
        self._audit("compute.route.updated", payload, result="updated", route_id=route_id)
        return {"ok": True, "route": updated}

    def disable_route(self, route_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/routes/{route_id}/disable", request_id=request_id, route_id=route_id)
        if limited is not None:
            return limited
        current = dict(self.get_route(route_id)["route"])
        current["enabled"] = False
        current["disabled_at"] = utc_now_iso()
        self.store.put_record("compute_route", route_id, current, provider_id=str(current.get("provider_id", "")), route_id=route_id, status="disabled", request_id=request_id)
        invalidated_cache = self._invalidate_quote_cache_entries({"provider_id": str(current.get("provider_id", "")), "route_id": route_id, "reason": "route_disabled"}, request_id=request_id)
        self._audit("compute.route.disabled", payload, request_id=request_id, result="disabled", route_id=route_id)
        return {"ok": True, "route": current, "invalidated_quote_cache_entries": invalidated_cache}

    def list_policies(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        page = self.store.list_records("compute_market_policy", filters=payload or {}, limit=int((payload or {}).get("limit", 100)), cursor=str((payload or {}).get("cursor", "")))
        return {"ok": True, "policies": page.records, "next_cursor": page.next_cursor, "default_market_policy": ComputeMarketPolicy().as_record()}

    def get_policy(self, policy_id: str) -> Mapping[str, Any]:
        policy = self.store.get_record("compute_market_policy", policy_id)
        if policy is None:
            raise KeyError(f"Unknown compute policy: {policy_id}")
        return {"ok": True, "policy": policy}

    def create_policy(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "POST /compute/policies", request_id=_request_id(payload))
        if limited is not None:
            return limited
        policy_id = str(payload.get("policy_id") or deterministic_id("policy", payload))
        policy = {**dict(payload), "policy_id": policy_id}
        self.store.put_record("compute_market_policy", policy_id, policy, status="active")
        self._audit("compute.policy.created", payload, result="created", policy_id=policy_id)
        return {"ok": True, "policy": policy}

    def update_policy(self, policy_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "PATCH /compute/policies/{policy_id}", request_id=_request_id(payload))
        if limited is not None:
            return limited
        current = dict(self.get_policy(policy_id)["policy"])
        updated = {**current, **dict(payload), "policy_id": policy_id}
        self.store.put_record("compute_market_policy", policy_id, updated, status=str(updated.get("status", "active")))
        self._audit("compute.policy.updated", payload, result="updated", policy_id=policy_id)
        return {"ok": True, "policy": updated}

    def validate_policy(self, policy_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        policy = self.get_policy(policy_id)["policy"]
        try:
            ComputeMarketPolicy(**{key: value for key, value in policy.items() if key in ComputeMarketPolicy().__dict__})
        except TypeError as exc:
            error = compute_error("configuration_error", str(exc))
            return {"ok": False, "error": error.as_record()}
        return {"ok": True, "policy_id": policy_id, "validation": "valid", "request": dict(payload)}

    def broker_quote(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        quote = payload.get("quote", payload)
        if not isinstance(quote, Mapping):
            raise ValueError("quote payload must be an object")
        provider_id = str(quote.get("provider_id", payload.get("provider_id", "")))
        route_id = str(quote.get("route_id", payload.get("route_id", "")))
        limited = self._rate_limit_response(payload, "POST /market/quotes/ingest", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        tenant_id = _payload_tenant_id(payload)
        workspace_id = str(payload.get("workspace_id", ""))
        _assert_provider_catalog_access(self.store, provider_id, payload)
        stale_marked = _mark_expired_quotes_stale(
            self.store,
            provider_id,
            route_id,
            request_id=request_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        public_key = _provider_public_key(payload, provider_id, self)
        validation = validate_provider_quote_contract(
            quote,
            provider_id=provider_id,
            allowed_assets=_tuple(payload.get("allowed_assets", ())),
            allowed_networks=_tuple(payload.get("allowed_networks", ())),
            public_key=public_key,
        )
        quote_id = str(quote.get("quote_id") or deterministic_id("quote", quote))
        quote_record_id = _quote_record_id(quote_id, tenant_id)
        quote_replay_record_id = _quote_replay_record_id(quote_id, tenant_id)
        quote_hash = content_hash(quote)
        cross_provider_replay = _cross_provider_quote_replay(self.store, quote_id, quote_hash, provider_id, payload)
        if cross_provider_replay:
            signal = _record_provider_fraud_signal(
                self.store,
                provider_id=provider_id,
                route_id=route_id,
                quote_id=quote_id,
                signal_type="provider_spoofing_replay",
                severity="critical",
                request_id=request_id,
                details={"quote_hash": quote_hash, "matched_provider_id": str(cross_provider_replay.get("provider_id", ""))},
                tenant_id=str(payload.get("tenant_id", "")),
                workspace_id=str(payload.get("workspace_id", "")),
            )
            error = compute_error(
                "quote.cross_provider_replay_detected",
                "Provider quote payload was already observed from a different provider.",
                details={"quote_id": quote_id, "provider_id": provider_id, "signal_id": signal["signal_id"]},
                request_id=request_id,
            )
            self._audit("market.quote.cross_provider_replay_rejected", payload, request_id=request_id, result="rejected", reason_codes=("cross_provider_replay_detected",), provider_id=provider_id, route_id=route_id)
            return {"ok": False, "error": error.as_record(), "validation": validation.as_record(), "fraud_signals": (signal,)}
        replay_guard = _get_tenant_scoped_record(
            self.store,
            "quote_replay_guard",
            quote_id,
            quote_replay_record_id,
            payload,
        )
        if replay_guard and str(replay_guard.get("quote_hash", "")) != quote_hash:
            error = compute_error(
                "quote.replay_detected",
                "Provider quote replay detected with a different payload hash.",
                details={"quote_id": quote_id, "provider_id": provider_id},
                request_id=request_id,
            )
            signal = _record_provider_fraud_signal(
                self.store,
                provider_id=provider_id,
                route_id=route_id,
                quote_id=quote_id,
                signal_type="quote_replay",
                severity="critical",
                request_id=request_id,
                details={"quote_hash": quote_hash, "previous_hash": str(replay_guard.get("quote_hash", ""))},
                tenant_id=str(payload.get("tenant_id", "")),
                workspace_id=str(payload.get("workspace_id", "")),
            )
            self._audit("market.quote.replay_rejected", payload, request_id=request_id, result="rejected", reason_codes=("quote_replay_detected",), provider_id=provider_id, route_id=route_id)
            return {"ok": False, "error": error.as_record(), "validation": validation.as_record(), "fraud_signals": (signal,)}
        if not validation.ok:
            validation_fraud_signals = _fraud_signals_from_validation(
                self.store,
                provider_id=provider_id,
                route_id=route_id,
                quote_id=quote_id,
                validation_errors=validation.error_codes,
                request_id=request_id,
                tenant_id=str(payload.get("tenant_id", "")),
                workspace_id=str(payload.get("workspace_id", "")),
            )
            self._audit("market.quote.rejected", payload, request_id=request_id, result="rejected", reason_codes=validation.error_codes, provider_id=provider_id, route_id=route_id)
            return {"ok": False, "validation": validation.as_record(), "quote_id": quote_id, "fraud_signals": validation_fraud_signals}
        signed_quote_valid = verify_provider_quote_signature(quote, public_key) if public_key else False
        record = {
            **_normalized_provider_quote(quote, quote_id=quote_id, quote_hash=quote_hash, signed_quote_valid=signed_quote_valid),
            "record_id": quote_record_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        }
        quote_filters = {"provider_id": provider_id, "route_id": route_id}
        if _payload_tenant_id(payload):
            quote_filters["tenant_id"] = _payload_tenant_id(payload)
        previous = self.store.list_records("compute_quote", filters=quote_filters, limit=1).records
        drift = _quote_drift(previous[0] if previous else {}, record)
        fraud_signals: tuple[Mapping[str, Any], ...] = ()
        self.store.put_record(
            "quote_replay_guard",
            quote_replay_record_id,
            {
                "quote_id": quote_id,
                "quote_hash": quote_hash,
                "provider_id": provider_id,
                "route_id": route_id,
                "created_at": utc_now_iso(),
                "record_id": quote_replay_record_id,
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
            },
            provider_id=provider_id,
            route_id=route_id,
            request_id=request_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        self.store.put_record(
            "compute_quote",
            quote_record_id,
            record,
            provider_id=provider_id,
            route_id=route_id,
            status=str(record.get("status", "valid")),
            expires_at=str(record.get("expires_at", "")),
            request_id=request_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            idempotency_key=str(payload.get("idempotency_key", "")),
        )
        if drift:
            self.store.put_record(
                "quote_drift_observation",
                str(drift["drift_id"]),
                drift,
                provider_id=provider_id,
                route_id=route_id,
                status=str(drift["status"]),
                request_id=request_id,
                tenant_id=str(payload.get("tenant_id", "")),
                workspace_id=str(payload.get("workspace_id", "")),
            )
            if str(drift.get("status", "")) == "review":
                fraud_signals = (
                    _record_provider_fraud_signal(
                        self.store,
                        provider_id=provider_id,
                        route_id=route_id,
                        quote_id=quote_id,
                        signal_type="quote_price_manipulation",
                        severity="review",
                        request_id=request_id,
                        details={"drift": drift},
                        tenant_id=str(payload.get("tenant_id", "")),
                        workspace_id=str(payload.get("workspace_id", "")),
                    ),
                )
        cache_key = _quote_cache_key(self.store, provider_id, route_id, str(record.get("task_hash", "")), str(record.get("policy_hash", "")), tenant_id)
        self.store.put_record(
            "quote_cache_entry",
            cache_key,
            {
                "cache_key": cache_key,
                "provider_id": provider_id,
                "route_id": route_id,
                "task_hash": str(record.get("task_hash", "")),
                "policy_hash": str(record.get("policy_hash", "")),
                "quote": record,
                "source": "live_provider",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "expires_at": str(record.get("expires_at", "")),
                "ttl_seconds": int(record.get("quote_ttl_seconds", 300) or 300),
                "status": str(record.get("status", "valid")),
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
            },
            provider_id=provider_id,
            route_id=route_id,
            task_hash=str(record.get("task_hash", "")),
            status=str(record.get("status", "valid")),
            expires_at=str(record.get("expires_at", "")),
            request_id=request_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id
        )
        self.telemetry.increment("provider_quote_latency_ms", {"provider_id": provider_id}, value=float(payload.get("latency_ms", 0) or 0))
        self._audit("market.quote.ingested", payload, request_id=request_id, result="accepted", provider_id=provider_id, route_id=route_id)
        if stale_marked:
            self.telemetry.increment(
                "quote_stale_total",
                {"provider_id": provider_id, "route_id": route_id},
                value=float(stale_marked),
            )
            self._audit("market.quote.expired_prior_quotes_marked_stale", payload, request_id=request_id, result="completed", reason_codes=("prior_quotes_expired",), provider_id=provider_id, route_id=route_id)
        return {"ok": True, "quote": record, "validation": validation.as_record(), "drift": drift or {}, "fraud_signals": fraud_signals}

    def invalidate_quote_cache(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        limited = self._rate_limit_response(payload, "POST /market/quotes/cache/invalidate", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        _assert_provider_catalog_access(self.store, provider_id, payload)
        invalidated = self._invalidate_quote_cache_entries(payload, request_id=request_id)
        self._audit(
            "market.quote.cache_invalidated",
            payload,
            request_id=request_id,
            result="invalidated" if invalidated else "noop",
            reason_codes=() if invalidated else ("quote_cache_entry_not_found",),
            provider_id=provider_id,
            route_id=route_id,
        )
        return {"ok": True, "invalidated_entries": invalidated, "invalidated_count": len(invalidated)}

    def quote_drift_analytics(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = payload or {}
        page = self.store.list_records(
            "quote_drift_observation",
            filters=filters,
            limit=int(filters.get("limit", 100) or 100),
            cursor=str(filters.get("cursor", "")),
        )
        observations = page.records
        ratios = tuple(float(item.get("drift_ratio", 0.0) or 0.0) for item in observations)
        review_count = sum(1 for item in observations if str(item.get("status", "")) == "review")
        observed_count = sum(1 for item in observations if str(item.get("status", "")) == "observed")
        by_provider: dict[str, int] = {}
        by_route: dict[str, int] = {}
        for item in observations:
            provider_id = str(item.get("provider_id", ""))
            route_id = str(item.get("route_id", ""))
            if provider_id:
                by_provider[provider_id] = by_provider.get(provider_id, 0) + 1
            if route_id:
                by_route[route_id] = by_route.get(route_id, 0) + 1
        return {
            "ok": True,
            "drift_observations": observations,
            "next_cursor": page.next_cursor,
            "summary": {
                "observation_count": len(observations),
                "review_count": review_count,
                "observed_count": observed_count,
                "max_drift_ratio": max(ratios) if ratios else 0.0,
                "average_drift_ratio": round(sum(ratios) / len(ratios), 6) if ratios else 0.0,
                "by_provider": by_provider,
                "by_route": by_route,
            },
        }

    def compare_quotes(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/quotes/compare", request_id=request_id, provider_id=str(payload.get("provider_id", "")), route_id=str(payload.get("route_id", "")))
        if limited is not None:
            return limited
        quotes_payload = payload.get("quotes")
        quotes: tuple[Mapping[str, Any], ...]
        if isinstance(quotes_payload, tuple | list):
            quotes = tuple(item for item in quotes_payload if isinstance(item, Mapping))
        else:
            quote_ids = _tuple(payload.get("quote_ids", ()))
            if quote_ids:
                records = tuple(_get_quote_record(self.store, quote_id, payload) for quote_id in quote_ids)
                quotes = tuple(record for record in records if isinstance(record, Mapping))
            else:
                quotes = tuple(
                    self.store.list_records(
                        "compute_quote",
                        filters=payload,
                        limit=int(payload.get("limit", 100) or 100),
                    ).records
                )
        profile = build_task_profile(payload)
        comparison = compute_quote_comparison(quotes, profile=profile)
        self._audit(
            "market.quote.compared",
            payload,
            request_id=request_id,
            result="completed",
            reason_codes=tuple(comparison.get("summary", {}).get("warnings", ())) if isinstance(comparison.get("summary"), Mapping) else (),
        )
        return {"ok": True, "quote_comparison": comparison, "request_id": request_id}

    def request_external_provider_quote(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", "")).strip()
        route_id = str(payload.get("route_id", "")).strip()
        if not provider_id:
            raise ValueError("provider_id is required")
        limited = self._rate_limit_response(payload, "POST /compute/providers/external/quote", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        if not self.config.external_provider_quotes_enabled:
            error = compute_error(
                "provider_quotes.disabled",
                "External provider quote requests are disabled.",
                details={"provider_id": provider_id, "next_safe_action": "set FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED=true after provider allowlist and contracts are configured"},
                request_id=request_id,
            )
            self._audit("market.quote.external_disabled", payload, request_id=request_id, result="rejected", reason_codes=("external_provider_quotes_disabled",), provider_id=provider_id, route_id=route_id)
            return {"ok": False, "error": error.as_record()}
        if not self.config.external_provider_allowlist:
            error = compute_error(
                "provider_quotes.allowlist_missing",
                "External provider quote requests require FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST.",
                details={"provider_id": provider_id},
                request_id=request_id,
            )
            self._audit("market.quote.external_allowlist_missing", payload, request_id=request_id, result="rejected", reason_codes=("external_provider_allowlist_missing",), provider_id=provider_id, route_id=route_id)
            return {"ok": False, "error": error.as_record()}
        circuit = self.circuit_breaker.allow_request(provider_id, route_id=route_id, adapter_type="external_quote")
        if not circuit.ok:
            self.telemetry.increment("provider_circuit_open_total", {"provider_id": provider_id})
            self._audit("market.quote.external_circuit_open", payload, request_id=request_id, result="rejected", reason_codes=("circuit_open",), provider_id=provider_id, route_id=route_id)
            return {"ok": False, "error": compute_error("provider.circuit_open", "Provider circuit is open.", details=circuit.as_record(), request_id=request_id).as_record()}
        _assert_provider_catalog_access(self.store, provider_id, payload)
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is None:
            raise KeyError(f"Unknown compute provider: {provider_id}")
        routes = tuple(self.store.list_records("compute_route", filters={"provider_id": provider_id}, limit=100).records)
        adapter = build_external_provider_adapter(provider, routes, self.config)
        profile = build_task_profile(payload)
        quotes = tuple(quote.as_record() for quote in adapter.quote(profile, ComputeMarketPolicy()))
        valid = tuple(quote for quote in quotes if str(quote.get("status", "")) == "valid")
        if valid:
            self.circuit_breaker.record_success(provider_id, route_id=route_id, adapter_type="external_quote")
        else:
            status = str(quotes[0].get("status", "provider_error")) if quotes else "provider_error"
            self.circuit_breaker.record_failure(provider_id, route_id=route_id, adapter_type="external_quote", error_class=status)
            self.telemetry.increment("provider_quote_failure_total", {"provider_id": provider_id, "status": status})
        accepted: list[Mapping[str, Any]] = []
        validations: list[Mapping[str, Any]] = []
        for quote in valid:
            brokered = self.broker_quote(
                {
                    "quote": _contract_quote_from_normalized(quote),
                    "allowed_assets": payload.get("allowed_assets", ()),
                    "allowed_networks": payload.get("allowed_networks", ()),
                    "request_id": request_id,
                    "tenant_id": str(payload.get("tenant_id", "")),
                    "workspace_id": str(payload.get("workspace_id", "")),
                }
            )
            validations.append(brokered.get("validation", {}) if isinstance(brokered, Mapping) else {})
            if brokered.get("ok") is True and isinstance(brokered.get("quote"), Mapping):
                accepted.append(brokered["quote"])
        result = "completed" if accepted else "failed"
        self._audit("market.quote.external_requested", payload, request_id=request_id, result=result, reason_codes=() if accepted else ("external_quote_failed",), provider_id=provider_id, route_id=route_id)
        return {
            "ok": bool(accepted),
            "provider_id": provider_id,
            "quotes": tuple(accepted),
            "raw_quotes": quotes,
            "validations": tuple(validations),
            "external_provider_quotes_enabled": True,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }

    def list_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /market/capacity/list", request_id=request_id, provider_id=str(payload.get("provider_id", "")), route_id=str(payload.get("route_id", "")))
        if limited is not None:
            return limited
        _assert_provider_catalog_access(self.store, str(payload.get("provider_id", "")), payload)
        expired_reservations = self._expire_capacity_holds(payload, request_id=request_id)
        window = _capacity_window(payload)
        self.store.put_record(
            "compute_capacity_window",
            str(window["window_id"]),
            window,
            provider_id=str(window["provider_id"]),
            route_id=str(window["route_id"]),
            status="active",
            expires_at=str(window["ends_at"]),
            request_id=request_id,
            tenant_id=str(payload.get("tenant_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
        )
        self._audit("market.capacity.listed", payload, request_id=request_id, result="listed", provider_id=str(window["provider_id"]), route_id=str(window["route_id"]))
        return {"ok": True, "capacity_window": window, "expired_reservations": expired_reservations}

    def capacity_order_book(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        filters = payload or {}
        request_id = _request_id(filters)
        expired_reservations = self._expire_capacity_holds(filters, request_id=request_id)
        windows = tuple(self.store.list_records("compute_capacity_window", filters=filters, limit=int(filters.get("limit", 100) or 100)).records)
        reservations = tuple(self.store.list_records("compute_reservation", filters=filters, limit=int(filters.get("limit", 100) or 100)).records)
        interval_start, interval_end = _capacity_time_range(filters)
        if _capacity_has_time_range(filters):
            windows = tuple(window for window in windows if _capacity_window_overlaps(window, interval_start, interval_end))
            reservations = tuple(
                reservation
                for reservation in reservations
                if _capacity_reservation_overlaps(reservation, interval_start, interval_end)
            )
        return {"ok": True, "capacity_windows": windows, "reservations": reservations, "expired_reservations": expired_reservations, "summary": _capacity_summary(windows, reservations)}

    def auction_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", "")).strip()
        route_id = str(payload.get("route_id", "")).strip()
        if not provider_id or not route_id:
            raise ValueError("provider_id and route_id are required")
        limited = self._rate_limit_response(
            payload,
            "POST /market/capacity/auction",
            request_id=request_id,
            provider_id=provider_id,
            route_id=route_id,
        )
        if limited is not None:
            return limited
        _assert_provider_catalog_access(self.store, provider_id, payload)
        idempotency_key = str(payload.get("idempotency_key", "")).strip()
        if idempotency_key:
            existing = self.store.find_by_idempotency("capacity_auction", idempotency_key)
            if existing is not None:
                return {"ok": True, "clearing": existing, "idempotent_replay": True}
        self._expire_capacity_holds(payload, request_id=request_id)
        capacity_filters = {"provider_id": provider_id, "route_id": route_id}
        if _payload_tenant_id(payload):
            capacity_filters["tenant_id"] = _payload_tenant_id(payload)
        windows = tuple(
            self.store.list_records(
                "compute_capacity_window",
                filters=capacity_filters,
                limit=100,
            ).records
        )
        reservations = tuple(
            self.store.list_records(
                "compute_reservation",
                filters=capacity_filters,
                limit=500,
            ).records
        )
        clearing = _capacity_auction_clearing(payload, windows, reservations, request_id=request_id)
        self.store.put_record(
            "capacity_auction",
            str(clearing["auction_id"]),
            clearing,
            provider_id=provider_id,
            route_id=route_id,
            status=str(clearing["status"]),
            idempotency_key=idempotency_key,
            request_id=request_id,
            tenant_id=str(payload.get("tenant_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
        )
        total_units_cleared = float(clearing.get("total_units_cleared", 0.0) or 0.0)
        self.telemetry.increment(
            "capacity_auction_cleared_total",
            {"provider_id": provider_id, "route_id": route_id},
            value=total_units_cleared,
        )
        self._audit(
            "market.capacity.auction.completed",
            payload,
            request_id=request_id,
            result=str(clearing["status"]),
            reason_codes=tuple(clearing.get("reason_codes", ())),
            provider_id=provider_id,
            route_id=route_id,
        )
        return {"ok": True, "clearing": clearing}

    def expire_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        limited = self._rate_limit_response(payload, "POST /market/capacity/expire", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        expired_reservations = self._expire_capacity_holds(payload, request_id=request_id)
        self._audit(
            "market.capacity.expired",
            payload,
            request_id=request_id,
            result="expired" if expired_reservations else "noop",
            reason_codes=() if expired_reservations else ("no_expired_holds",),
            provider_id=provider_id,
            route_id=route_id,
        )
        return {"ok": True, "expired_reservations": expired_reservations, "expired_count": len(expired_reservations)}

    def reserve_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        limited = self._rate_limit_response(payload, "POST /market/capacity/reserve", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        _assert_provider_catalog_access(self.store, provider_id, payload)
        capacity_filters = {"provider_id": provider_id, "route_id": route_id}
        if _payload_tenant_id(payload):
            capacity_filters["tenant_id"] = _payload_tenant_id(payload)
        self._expire_capacity_holds(payload, request_id=request_id)
        reservation = _capacity_reservation(payload, self.store.list_records("compute_capacity_window", filters=capacity_filters, limit=100).records, self.store.list_records("compute_reservation", filters=capacity_filters, limit=500).records)
        self.store.put_record(
            "compute_reservation",
            str(reservation["reservation_id"]),
            reservation,
            provider_id=provider_id,
            route_id=route_id,
            status=str(reservation["status"]),
            expires_at=str(reservation["hold_expires_at"]),
            idempotency_key=str(payload.get("idempotency_key", "")),
            request_id=request_id,
            tenant_id=str(payload.get("tenant_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
        )
        self.telemetry.increment("capacity_reserved_total", {"provider_id": provider_id, "route_id": route_id}, value=float(reservation.get("capacity_units", 0.0) or 0.0))
        self._audit("market.capacity.reserved", payload, request_id=request_id, result="held", provider_id=provider_id, route_id=route_id)
        return {"ok": True, "reservation": reservation}

    def confirm_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        reservation_id = str(payload.get("reservation_id", ""))
        if not reservation_id:
            raise ValueError("reservation_id is required")
        current = self.store.get_record("compute_reservation", reservation_id)
        if current is None:
            raise KeyError(f"Unknown capacity reservation: {reservation_id}")
        if not _tenant_can_access_record(payload, current):
            raise KeyError(f"Unknown capacity reservation: {reservation_id}")
        status = str(current.get("status", ""))
        if status != "held":
            raise ValueError(f"cannot confirm capacity reservation from status {status}; expected held")
        confirmed_at = utc_now_iso()
        if _capacity_hold_expired(current, confirmed_at):
            raise ValueError("capacity reservation hold is expired")
        reservation = {
            **dict(current),
            "status": "confirmed",
            "confirmed_at": confirmed_at,
            "updated_at": confirmed_at,
        }
        self.store.put_record(
            "compute_reservation",
            reservation_id,
            reservation,
            provider_id=str(reservation.get("provider_id", "")),
            route_id=str(reservation.get("route_id", "")),
            status="confirmed",
            request_id=request_id,
            tenant_id=str(reservation.get("tenant_id", "")),
            workspace_id=str(reservation.get("workspace_id", "")),
        )
        self.telemetry.increment(
            "capacity_confirmed_total",
            {
                "provider_id": str(reservation.get("provider_id", "")),
                "route_id": str(reservation.get("route_id", "")),
            },
            value=float(reservation.get("capacity_units", 0.0) or 0.0),
        )
        self._audit(
            "market.capacity.confirmed",
            payload,
            request_id=request_id,
            result="confirmed",
            provider_id=str(reservation.get("provider_id", "")),
            route_id=str(reservation.get("route_id", "")),
        )
        return {"ok": True, "reservation": reservation}

    def release_capacity(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        reservation_id = str(payload.get("reservation_id", ""))
        if not reservation_id:
            raise ValueError("reservation_id is required")
        current = self.store.get_record("compute_reservation", reservation_id)
        if current is None:
            raise KeyError(f"Unknown capacity reservation: {reservation_id}")
        if not _tenant_can_access_record(payload, current):
            raise KeyError(f"Unknown capacity reservation: {reservation_id}")
        released_at = utc_now_iso()
        reservation = {**dict(current), "status": "released", "released_at": released_at, "updated_at": released_at}
        self.store.put_record(
            "compute_reservation",
            reservation_id,
            reservation,
            provider_id=str(reservation.get("provider_id", "")),
            route_id=str(reservation.get("route_id", "")),
            status="released",
            request_id=request_id,
            tenant_id=str(reservation.get("tenant_id", "")),
            workspace_id=str(reservation.get("workspace_id", "")),
        )
        self.telemetry.increment("capacity_released_total", {"provider_id": str(reservation.get("provider_id", "")), "route_id": str(reservation.get("route_id", ""))}, value=float(reservation.get("capacity_units", 0.0) or 0.0))
        self._audit("market.capacity.released", payload, request_id=request_id, result="released", provider_id=str(reservation.get("provider_id", "")), route_id=str(reservation.get("route_id", "")))
        return {"ok": True, "reservation": reservation}

    def _expire_capacity_holds(self, payload: Mapping[str, Any], *, request_id: str) -> tuple[Mapping[str, Any], ...]:
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        filters: dict[str, str] = {}
        if provider_id:
            filters["provider_id"] = provider_id
        if route_id:
            filters["route_id"] = route_id
        if _payload_tenant_id(payload):
            filters["tenant_id"] = _payload_tenant_id(payload)
        page = self.store.list_records("compute_reservation", filters=filters, limit=500)
        now = utc_now_iso()
        interval_start, interval_end = _capacity_time_range(payload)
        restrict_to_interval = _capacity_has_time_range(payload)
        expired: list[Mapping[str, Any]] = []
        for current in page.records:
            if restrict_to_interval and not _capacity_reservation_overlaps(current, interval_start, interval_end):
                continue
            if not _capacity_hold_expired(current, now):
                continue
            reservation_id = str(current.get("reservation_id", current.get("record_id", "")))
            if not reservation_id:
                continue
            updated = {**dict(current), "status": "expired", "expired_at": now, "updated_at": now}
            self.store.put_record(
                "compute_reservation",
                reservation_id,
                updated,
                provider_id=str(updated.get("provider_id", "")),
                route_id=str(updated.get("route_id", "")),
                status="expired",
                request_id=request_id,
                tenant_id=str(updated.get("tenant_id", "")),
                workspace_id=str(updated.get("workspace_id", "")),
            )
            self.telemetry.increment(
                "capacity_hold_expired_total",
                {"provider_id": str(updated.get("provider_id", "")), "route_id": str(updated.get("route_id", ""))},
                value=float(updated.get("capacity_units", 0.0) or 0.0),
            )
            expired.append(updated)
        return tuple(expired)

    def _invalidate_quote_cache_entries(self, payload: Mapping[str, Any], *, request_id: str) -> tuple[Mapping[str, Any], ...]:
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        task_hash = str(payload.get("task_hash", ""))
        cache_key = str(payload.get("cache_key", ""))
        quote_id = str(payload.get("quote_id", ""))
        policy_hash = str(payload.get("policy_hash", ""))
        filters: dict[str, str] = {}
        if provider_id:
            filters["provider_id"] = provider_id
        if route_id:
            filters["route_id"] = route_id
        if task_hash:
            filters["task_hash"] = task_hash
        if _payload_tenant_id(payload):
            filters["tenant_id"] = _payload_tenant_id(payload)
        page = self.store.list_records("quote_cache_entry", filters=filters, limit=500)
        now = utc_now_iso()
        invalidated: list[Mapping[str, Any]] = []
        reason = str(payload.get("reason", "manual_invalidation"))
        for current in page.records:
            current_cache_key = str(current.get("cache_key", current.get("record_id", "")))
            if cache_key and current_cache_key != cache_key:
                continue
            if policy_hash and str(current.get("policy_hash", "")) != policy_hash:
                continue
            cached_quote = current.get("quote", {})
            if quote_id and (not isinstance(cached_quote, Mapping) or str(cached_quote.get("quote_id", "")) != quote_id):
                continue
            if str(current.get("status", "")) == "invalidated":
                continue
            updated = {
                **dict(current),
                "status": "invalidated",
                "invalidated_at": now,
                "invalidation_reason": reason,
                "updated_at": now,
            }
            self.store.put_record(
                "quote_cache_entry",
                current_cache_key,
                updated,
                provider_id=str(updated.get("provider_id", "")),
                route_id=str(updated.get("route_id", "")),
                task_hash=str(updated.get("task_hash", "")),
                status="invalidated",
                expires_at=now,
                request_id=request_id,
                tenant_id=str(updated.get("tenant_id", "")),
                workspace_id=str(updated.get("workspace_id", "")),
            )
            self.telemetry.increment(
                "quote_cache_invalidated_total",
                {"provider_id": str(updated.get("provider_id", "")), "route_id": str(updated.get("route_id", ""))},
            )
            invalidated.append(updated)
        return tuple(invalidated)

    def create_job(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        provider_id = str(payload.get("provider_id", ""))
        route_id = str(payload.get("route_id", ""))
        limited = self._rate_limit_response(payload, "POST /compute/jobs", request_id=request_id, provider_id=provider_id, route_id=route_id)
        if limited is not None:
            return limited
        _billing_account_id(
            payload,
            fallback_account_id=str(payload.get("tenant_id", "")).strip(),
            required=False,
        )
        job = _compute_job(payload, request_id=request_id)
        self.store.put_record(
            "compute_job",
            str(job["job_id"]),
            job,
            provider_id=provider_id,
            route_id=route_id,
            task_type=str(job["task_type"]),
            status=str(job["status"]),
            idempotency_key=str(payload.get("idempotency_key", "")),
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        event = _job_event(str(job["job_id"]), "job.queued", status=str(job["status"]), request_id=request_id, details={"dry_run_only": True})
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=provider_id,
            route_id=route_id,
            status=str(job["status"]),
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        self.telemetry.increment("compute_job_started_total", {"task_type": str(job["task_type"])})
        self._audit("compute.job.queued", payload, request_id=request_id, result="queued", provider_id=provider_id, route_id=route_id)
        return {"ok": True, "job": job, "event": event}

    def list_jobs(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        _assert_no_unsafe(payload)
        self._expire_job_leases(payload, request_id=_request_id(payload))
        filters = {
            key: value
            for key, value in payload.items()
            if key
            in {
                "tenant_id",
                "workspace_id",
                "provider_id",
                "route_id",
                "task_type",
                "status",
                "request_id",
                "actor_id",
                "start_time",
                "end_time",
            }
            and value not in (None, "")
        }
        page = self.store.list_records(
            "compute_job",
            filters=filters,
            limit=int(payload.get("limit", 100)),
            cursor=str(payload.get("cursor", "")),
        )
        return {"ok": True, "jobs": page.records, "next_cursor": page.next_cursor}

    def get_job(self, job_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        job = self.store.get_record("compute_job", job_id)
        if job is None or not _tenant_can_access_record(payload, job):
            raise KeyError(f"Unknown compute job: {job_id}")
        if str(job.get("status", "")) in {"dispatched", "running"} and _job_lease_expired(job, utc_now_iso()):
            self._expire_job_leases({**dict(payload), "job_id": job_id}, request_id=_request_id(payload))
            job = self.store.get_record("compute_job", job_id)
            if job is None or not _tenant_can_access_record(payload, job):
                raise KeyError(f"Unknown compute job: {job_id}")
        return {"ok": True, "job": job}

    def expire_job_leases(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        limited = self._rate_limit_response(payload, "POST /compute/jobs/expire-leases", request_id=request_id)
        if limited is not None:
            return limited
        expired_jobs, events = self._expire_job_leases(payload, request_id=request_id)
        return {"ok": True, "expired_jobs": expired_jobs, "events": events, "expired_count": len(expired_jobs)}

    def _mark_job_dispatch_attempts_exceeded(
        self,
        job: Mapping[str, Any],
        payload: Mapping[str, Any],
        *,
        request_id: str,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
        job_id = str(job.get("job_id", job.get("record_id", "")))
        exhausted_at = utc_now_iso()
        previous_status = str(job.get("status", ""))
        dispatch_attempts = int(job.get("dispatch_attempt", 0) or 0)
        max_dispatch_attempts = _job_max_dispatch_attempts(job)
        updated_job = dict(job)
        updated_job.update(
            {
                "status": "expired",
                "expired_at": exhausted_at,
                "updated_at": exhausted_at,
                "error_code": "max_dispatch_attempts_exceeded",
                "failure_reason": "Compute job exceeded its maximum dispatch attempts.",
                "lease_expires_at": "",
                "claimed_by": "",
                "claim_token": "",
                "worker_capabilities": (),
                "lifecycle": _append_lifecycle(job, "expired"),
            }
        )
        self.store.put_record_if_state(
            "compute_job",
            job_id,
            (previous_status,),
            updated_job,
            expires_at_before=utc_now_iso() if previous_status == "dispatched" else "",
            provider_id=str(updated_job.get("provider_id", "")),
            route_id=str(updated_job.get("route_id", "")),
            task_type=str(updated_job.get("task_type", "")),
            status="expired",
            expires_at="",
            request_id=request_id,
            tenant_id=str(updated_job.get("tenant_id", "")),
            workspace_id=str(updated_job.get("workspace_id", "")),
        )
        event = _job_event(
            job_id,
            "job.dispatch_attempts_exhausted",
            status="expired",
            request_id=request_id,
            details={
                "dispatch_attempts": dispatch_attempts,
                "max_dispatch_attempts": max_dispatch_attempts,
                "dry_run_only": True,
            },
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(updated_job.get("provider_id", "")),
            route_id=str(updated_job.get("route_id", "")),
            status="expired",
            request_id=request_id,
            tenant_id=str(updated_job.get("tenant_id", "")),
            workspace_id=str(updated_job.get("workspace_id", "")),
        )
        self.telemetry.increment(
            "compute_job_failed_total",
            {"task_type": str(updated_job.get("task_type", "")), "error_code": "max_dispatch_attempts_exceeded"},
        )
        self._audit(
            "compute.job.dispatch_attempts_exhausted",
            {**dict(payload), "job_id": job_id},
            request_id=request_id,
            result="expired",
            reason_codes=("max_dispatch_attempts_exceeded",),
            provider_id=str(updated_job.get("provider_id", "")),
            route_id=str(updated_job.get("route_id", "")),
        )
        error = compute_error(
            "policy.max_dispatch_attempts_exceeded",
            "Compute job exceeded its maximum dispatch attempts.",
            details={
                "job_id": job_id,
                "dispatch_attempts": dispatch_attempts,
                "max_dispatch_attempts": max_dispatch_attempts,
            },
            request_id=request_id,
            retryable=False,
        )
        return updated_job, event, error.as_record()

    def _expire_job_leases(self, payload: Mapping[str, Any], *, request_id: str) -> tuple[tuple[Mapping[str, Any], ...], tuple[Mapping[str, Any], ...]]:
        now = utc_now_iso()
        target_job_id = str(payload.get("job_id", "")).strip()
        limit = min(500, max(1, int(payload.get("limit", 100) or 100)))
        candidates: tuple[Mapping[str, Any], ...]
        if target_job_id:
            candidate = self.store.get_record("compute_job", target_job_id)
            candidates = (candidate,) if candidate is not None and _tenant_can_access_record(payload, candidate) else ()
        else:
            base_filters = {
                key: str(payload.get(key, ""))
                for key in ("tenant_id", "workspace_id", "provider_id", "route_id", "task_type")
                if str(payload.get(key, "")).strip()
            }
            dispatched = self.store.list_records("compute_job", filters={**base_filters, "status": "dispatched"}, limit=limit).records
            running = self.store.list_records("compute_job", filters={**base_filters, "status": "running"}, limit=limit).records
            candidates = (*dispatched, *running)

        expired_jobs: list[Mapping[str, Any]] = []
        events: list[Mapping[str, Any]] = []
        for candidate in candidates:
            job = dict(candidate)
            job_id = str(job.get("job_id", job.get("record_id", "")))
            status = str(job.get("status", ""))
            lease_expires_at = str(job.get("lease_expires_at", job.get("expires_at", "")))
            if not job_id or status not in {"dispatched", "running"} or not _job_lease_expired(job, now):
                continue
            previous_claim = {
                "claimed_by": str(job.get("claimed_by", "")),
                "claim_token": str(job.get("claim_token", "")),
                "lease_expires_at": lease_expires_at,
                "started_by_worker_id": str(job.get("started_by_worker_id", "")),
            }
            if status == "dispatched" and int(job.get("dispatch_attempt", 0) or 0) >= _job_max_dispatch_attempts(job):
                exhausted_job, event, _error = self._mark_job_dispatch_attempts_exceeded(
                    job,
                    {**dict(payload), "expired_lease": previous_claim},
                    request_id=request_id,
                )
                self.telemetry.increment("compute_job_lease_expired_total", {"status": status, "next_status": "expired"})
                expired_jobs.append(exhausted_job)
                events.append(event)
                continue
            if status == "dispatched":
                next_status = "queued"
                event_type = "job.lease_expired_requeued"
                job.update(
                    {
                        "status": next_status,
                        "claimed_by": "",
                        "claim_token": "",
                        "lease_expires_at": "",
                        "lease_expired_at": now,
                        "last_expired_lease": previous_claim,
                        "worker_capabilities": (),
                        "updated_at": now,
                        "lease_expiration_count": int(job.get("lease_expiration_count", 0) or 0) + 1,
                        "provider_dispatch": "worker_queue_claim_expired",
                    }
                )
            else:
                next_status = "expired"
                event_type = "job.lease_expired"
                job.update(
                    {
                        "status": next_status,
                        "expired_at": now,
                        "updated_at": now,
                        "error_code": "worker_heartbeat_timeout",
                        "failure_reason": "Worker lease expired before completion.",
                        "lease_expires_at": "",
                        "last_expired_lease": previous_claim,
                        "lease_expiration_count": int(job.get("lease_expiration_count", 0) or 0) + 1,
                        "lifecycle": _append_lifecycle(job, "expired"),
                    }
                )
            updated = self.store.put_record_if_state(
                "compute_job",
                job_id,
                (status,),
                job,
                expires_at_before=now,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                task_type=str(job.get("task_type", "")),
                status=next_status,
                expires_at="",
                request_id=request_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            if not updated:
                continue
            event = _job_event(
                job_id,
                event_type,
                status=next_status,
                request_id=request_id,
                details={"expired_lease": previous_claim, "dry_run_only": True},
            )
            self.store.put_record(
                "compute_job_event",
                str(event["event_id"]),
                event,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                status=next_status,
                request_id=request_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            self.telemetry.increment("compute_job_lease_expired_total", {"status": status, "next_status": next_status})
            if next_status == "expired":
                self.telemetry.increment("compute_job_failed_total", {"task_type": str(job.get("task_type", "")), "error_code": "worker_heartbeat_timeout"})
            self._audit(
                "compute.job.lease_expired",
                {**dict(payload), "job_id": job_id},
                request_id=request_id,
                result=next_status,
                reason_codes=("worker_lease_expired",),
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
            )
            expired_jobs.append(job)
            events.append(event)
        return tuple(expired_jobs), tuple(events)

    def job_events(self, job_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.get_job(job_id, payload)
        events = tuple(event for event in self.store.list_records("compute_job_event", limit=500).records if str(event.get("job_id", "")) == job_id)
        return {"ok": True, "events": events}

    def job_artifacts(self, job_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.get_job(job_id, payload)
        artifacts = tuple(artifact for artifact in self.store.list_records("compute_job_artifact", limit=500).records if str(artifact.get("job_id", "")) == job_id)
        return {"ok": True, "artifacts": artifacts}

    def provider_job_receipt(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        receipt = _provider_receipt_payload(payload)
        provider_id = str(receipt.get("provider_id", payload.get("provider_id", job.get("provider_id", ""))))
        route_id = str(job.get("route_id", receipt.get("route_id", "")))
        if str(receipt.get("job_id", "")) != job_id:
            error = compute_error(
                "provider_receipt.job_mismatch",
                "Provider receipt job_id does not match the requested job.",
                details={"job_id": job_id, "receipt_job_id": str(receipt.get("job_id", ""))},
                request_id=request_id,
            )
            self._audit("compute.job.provider_receipt_rejected", payload, request_id=request_id, result="rejected", reason_codes=("provider_receipt_job_mismatch",), provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_rejected_total", {"provider_id": provider_id, "route_id": route_id, "reason": "provider_receipt.job_mismatch"})
            return {"ok": False, "error": error.as_record()}
        if provider_id != str(job.get("provider_id", "")):
            error = compute_error(
                "provider_receipt.provider_mismatch",
                "Provider receipt provider_id does not match the compute job provider.",
                details={"job_id": job_id, "provider_id": str(job.get("provider_id", "")), "receipt_provider_id": provider_id},
                request_id=request_id,
            )
            self._audit("compute.job.provider_receipt_rejected", payload, request_id=request_id, result="rejected", reason_codes=("provider_receipt_provider_mismatch",), provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_rejected_total", {"provider_id": provider_id, "route_id": route_id, "reason": "provider_receipt.provider_mismatch"})
            return {"ok": False, "error": error.as_record()}
        client_ip = str(payload.get("_flow_memory_client_ip", ""))
        if not _provider_callback_ip_allowed(client_ip, self.config.provider_callback_ip_allowlist):
            error = compute_error(
                "provider_receipt.ip_not_allowed",
                "Provider receipt callback source IP is not allowlisted.",
                details={"provider_id": provider_id, "client_ip": client_ip, "allowlist_configured": bool(self.config.provider_callback_ip_allowlist)},
                request_id=request_id,
            )
            self._audit("compute.job.provider_receipt_rejected", payload, request_id=request_id, result="rejected", reason_codes=("provider_receipt_ip_not_allowed",), provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_rejected_total", {"provider_id": provider_id, "route_id": route_id, "reason": "provider_receipt.ip_not_allowed"})
            return {"ok": False, "error": error.as_record()}
        verification = _verify_provider_receipt(self.store, job, payload, receipt)
        if not verification["ok"]:
            reason = str(verification["error"].get("error_code", "provider_receipt.invalid"))
            error = compute_error(reason, str(verification["error"].get("message", "Provider receipt verification failed.")), details=verification["error"], request_id=request_id)
            self._audit("compute.job.provider_receipt_rejected", payload, request_id=request_id, result="rejected", reason_codes=(reason,), provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_rejected_total", {"provider_id": provider_id, "route_id": route_id, "reason": reason})
            return {"ok": False, "error": error.as_record(), "verification": verification}
        receipt_id = str(verification["receipt_id"])
        receipt_hash = str(verification["receipt_hash"])
        self.store.put_record(
            "provider_receipt_replay_guard",
            receipt_id,
            {
                "receipt_id": receipt_id,
                "receipt_hash": receipt_hash,
                "job_id": job_id,
                "provider_id": provider_id,
                "route_id": route_id,
                "created_at": utc_now_iso(),
                "request_id": request_id,
            },
            provider_id=provider_id,
            route_id=route_id,
            request_id=request_id,
        )
        status = str(receipt.get("status", "")).strip().lower()
        completion_payload = {
            **dict(receipt),
            "request_id": request_id,
            "tenant_id": str(payload.get("tenant_id", "")),
            "workspace_id": str(payload.get("workspace_id", payload.get("tenant_id", ""))),
            "_flow_memory_client_ip": client_ip,
        }
        if status in {"succeeded", "success", "completed", "complete"}:
            self._audit("compute.job.provider_receipt_accepted", payload, request_id=request_id, result=status, provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_accepted_total", {"provider_id": provider_id, "route_id": route_id, "status": status})
            completed = self.complete_job(job_id, completion_payload)
            return {"ok": True, "receipt": receipt, "verification": verification, "completion": completed, "job": completed["job"]}
        if status in {"failed", "failure", "error"}:
            self._audit("compute.job.provider_receipt_accepted", payload, request_id=request_id, result=status, provider_id=provider_id, route_id=route_id)
            self.telemetry.increment("compute_provider_receipt_accepted_total", {"provider_id": provider_id, "route_id": route_id, "status": status})
            failed = self.fail_job(job_id, completion_payload)
            return {"ok": True, "receipt": receipt, "verification": verification, "failure": failed, "job": failed["job"]}
        error = compute_error(
            "provider_receipt.unsupported_status",
            "Provider receipt status must be succeeded or failed.",
            details={"status": status, "job_id": job_id},
            request_id=request_id,
        )
        self._audit("compute.job.provider_receipt_rejected", payload, request_id=request_id, result="rejected", reason_codes=("provider_receipt.unsupported_status",), provider_id=provider_id, route_id=route_id)
        self.telemetry.increment("compute_provider_receipt_rejected_total", {"provider_id": provider_id, "route_id": route_id, "reason": "provider_receipt.unsupported_status", "status": status})
        return {"ok": False, "error": error.as_record(), "verification": verification}

    def _dispatch_external_provider_execution(
        self,
        job: Mapping[str, Any],
        payload: Mapping[str, Any],
        *,
        request_id: str,
    ) -> Mapping[str, Any]:
        provider_id = str(job.get("provider_id", ""))
        route_id = str(job.get("route_id", ""))
        if not self.config.external_provider_execution_enabled:
            return {"required": False, "ok": True, "external_provider_called": False}
        if not self.config.external_provider_allowlist:
            error = compute_error(
                "provider_execution.allowlist_missing",
                "External provider execution requires FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST.",
                details={"provider_id": provider_id, "route_id": route_id},
                request_id=request_id,
            )
            self.telemetry.increment("external_provider_allowlist_missing_total", {"provider_id": provider_id})
            self._audit("compute.job.external_execution_allowlist_missing", payload, request_id=request_id, result="rejected", reason_codes=("external_provider_allowlist_missing",), provider_id=provider_id, route_id=route_id)
            return {"required": True, "ok": False, "error": error.as_record(), "external_provider_called": False}
        circuit = self.circuit_breaker.allow_request(provider_id, route_id=route_id, adapter_type="external_execution")
        if not circuit.ok:
            self.telemetry.increment("provider_circuit_open_total", {"provider_id": provider_id})
            error = compute_error("provider.circuit_open", "Provider execution circuit is open.", details=circuit.as_record(), request_id=request_id)
            self._audit("compute.job.external_execution_circuit_open", payload, request_id=request_id, result="rejected", reason_codes=("circuit_open",), provider_id=provider_id, route_id=route_id)
            return {"required": True, "ok": False, "error": error.as_record(), "external_provider_called": False}
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is None:
            raise KeyError(f"Unknown compute provider: {provider_id}")
        routes = tuple(self.store.list_records("compute_route", filters={"provider_id": provider_id}, limit=100).records)
        adapter = build_external_provider_adapter(provider, routes, self.config)
        result = dict(adapter.execute_plan({**dict(job), "request_id": request_id, "worker_id": str(payload.get("worker_id", ""))}))
        if result.get("ok") is True:
            self.telemetry.increment("provider_execution_request_total", {"provider_id": provider_id})
            self.circuit_breaker.record_success(provider_id, route_id=route_id, adapter_type="external_execution")
            self._audit("compute.job.external_execution_requested", payload, request_id=request_id, result=str(result.get("status", "accepted")), provider_id=provider_id, route_id=route_id)
            return {"required": True, **result}
        error_code = str(result.get("error_code", "provider_execution.failed"))
        self.telemetry.increment("provider_execution_failure_total", {"provider_id": provider_id, "error_code": error_code})
        self.circuit_breaker.record_failure(provider_id, route_id=route_id, adapter_type="external_execution", error_class=error_code)
        self._audit("compute.job.external_execution_failed", payload, request_id=request_id, result="rejected", reason_codes=(error_code,), provider_id=provider_id, route_id=route_id)
        error = compute_error(error_code, str(result.get("message", "Provider execution request failed.")), details={"provider_id": provider_id, "route_id": route_id}, request_id=request_id)
        return {"required": True, "ok": False, "error": error.as_record(), "execution": result, "external_provider_called": bool(result.get("external_provider_called", False))}
    def dispatch_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        _assert_job_status(job, ("queued", "dispatched"), "dispatch")
        worker_id = _assert_claim_owner(job, payload, "dispatch")
        credit_reservation = _reserve_credit_for_job(self.store, job, payload, request_id=request_id)
        if str(credit_reservation.get("status", "")) == "insufficient_credit":
            amount = float(credit_reservation.get("amount", 0.0) or 0.0)
            currency = str(credit_reservation.get("currency", job.get("currency", "USD")))
            error = compute_error(
                "billing.credit_preauthorization_failed",
                "Insufficient prepaid credits to dispatch compute job.",
                details={
                    "job_id": job_id,
                    "account_id": str(credit_reservation.get("account_id", "")),
                    "amount": amount,
                    "currency": currency,
                },
                request_id=request_id,
            )
            event = _job_event(
                job_id,
                "job.credit_preauthorization_failed",
                status=str(job.get("status", "queued")),
                request_id=request_id,
                details={"credit_reservation": credit_reservation, "funds_moved": False},
            )
            self.store.put_record(
                "compute_job_event",
                str(event["event_id"]),
                event,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                status=str(job.get("status", "queued")),
                request_id=request_id,
                actor_id=worker_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            self.telemetry.increment(
                "billing_insufficient_credit_total",
                {"provider_id": str(job.get("provider_id", "")), "currency": currency},
                value=amount,
            )
            self._audit(
                "billing.credit_preauthorization_failed",
                {**dict(payload), "job_id": job_id},
                request_id=request_id,
                result="rejected",
                reason_codes=("insufficient_credit",),
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
            )
            return {"ok": False, "job": job, "event": event, "credit_reservation": credit_reservation, "error": error.as_record()}
        execution = self._dispatch_external_provider_execution(job, payload, request_id=request_id)
        if execution.get("required") is True and execution.get("ok") is not True:
            credit_release = _release_credit_reservation(
                self.store,
                {**dict(job), "credit_reservation_id": str(credit_reservation.get("credit_transaction_id", ""))},
                request_id=request_id,
                reason="external_execution_failed",
            )
            return {
                "ok": False,
                "job": job,
                "event": {},
                "execution": execution.get("execution", {}),
                "credit_reservation": credit_reservation,
                "credit_release": credit_release,
                "error": execution.get("error", {}),
            }
        dispatched_at = utc_now_iso()
        details: dict[str, Any] = {
            "provider_dispatch": "dry_run_provider_dispatch",
            "dry_run_only": True,
            "external_provider_called": False,
        }
        if worker_id:
            details["worker_id"] = worker_id
        if credit_reservation:
            details["credit_reservation"] = credit_reservation
        if execution.get("external_provider_called") is True:
            details.update(
                {
                    "provider_dispatch": "external_provider_execution",
                    "external_provider_called": True,
                    "provider_execution": {
                        key: value
                        for key, value in dict(execution).items()
                        if key not in {"required", "ok"}
                    },
                }
            )
        job.update(
            {
                "status": "running",
                "dispatched_at": dispatched_at,
                "started_at": dispatched_at,
                "updated_at": dispatched_at,
                "lifecycle": _append_lifecycle(job, "running"),
                "provider_dispatch": "external_provider_execution"
                if execution.get("external_provider_called") is True
                else "dry_run_provider_dispatch",
            }
        )
        if worker_id:
            job["started_by_worker_id"] = worker_id
        if credit_reservation:
            job["credit_reservation_id"] = str(credit_reservation.get("credit_transaction_id", ""))
            job["credit_reserved_amount"] = float(credit_reservation.get("amount", 0.0) or 0.0)
            job["account_id"] = str(credit_reservation.get("account_id", job.get("account_id", "")))
        if execution.get("external_provider_called") is True:
            job["provider_execution"] = details["provider_execution"]
        self.store.put_record(
            "compute_job",
            job_id,
            job,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="running",
            expires_at=str(job.get("lease_expires_at", "")),
            request_id=request_id,
            actor_id=worker_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        event = _job_event(
            job_id,
            "job.started",
            status="running",
            request_id=request_id,
            details=details,
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="running",
            request_id=request_id,
            actor_id=worker_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        self.telemetry.increment("compute_job_started_total", {"task_type": str(job.get("task_type", ""))})
        self._audit(
            "compute.job.dispatched",
            {**dict(payload), "job_id": job_id, "worker_id": worker_id},
            request_id=request_id,
            result="running",
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
        )
        return {"ok": True, "job": job, "event": event, "credit_reservation": credit_reservation}

    def complete_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        provider_id = str(job.get("provider_id", ""))
        route_id = str(job.get("route_id", ""))
        callback_rejection = self._provider_callback_ip_rejection(
            payload,
            request_id=request_id,
            job_id=job_id,
            provider_id=provider_id,
            route_id=route_id,
            callback_action="complete",
            audit_action="compute.job.complete_rejected",
        )
        if callback_rejection is not None:
            return callback_rejection
        _assert_job_status(job, ("running",), "complete")
        worker_id = _assert_claim_owner(job, payload, "complete")
        completed_at = utc_now_iso()
        cost = _job_cost(payload)
        actual_units = _non_negative_float(payload.get("actual_units", payload.get("units", 0.0)), "actual_units")
        actual_latency_ms = _non_negative_float(payload.get("actual_latency_ms", payload.get("latency_ms", 0.0)), "actual_latency_ms")
        usage_charge = _usage_charge(job, payload, request_id=request_id, amount=cost, units=actual_units)
        provider = self.store.get_record("compute_provider", str(job.get("provider_id", ""))) or {}
        sla_max_latency_ms = _provider_sla_max_latency_ms(provider if isinstance(provider, Mapping) else {})
        sla_latency_breached = bool(sla_max_latency_ms and actual_latency_ms and actual_latency_ms > sla_max_latency_ms)
        previous_lease_expires_at = str(job.get("lease_expires_at", ""))
        job.update(
            {
                "status": "succeeded",
                "completed_at": completed_at,
                "updated_at": completed_at,
                "actual_units": actual_units,
                "actual_total_cost": cost,
                "actual_latency_ms": actual_latency_ms,
                "provider_sla_max_latency_ms": sla_max_latency_ms,
                "provider_sla_latency_breached": sla_latency_breached,
                "lifecycle": _append_lifecycle(job, "succeeded"),
                "lease_expires_at": "",
            }
        )
        if previous_lease_expires_at:
            job["last_lease_expires_at"] = previous_lease_expires_at
        if worker_id:
            job["completed_by_worker_id"] = worker_id
        self.store.put_record(
            "compute_job",
            job_id,
            job,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="succeeded",
            request_id=request_id,
            actor_id=worker_id,
        )
        artifact = _job_artifact(job, payload, request_id=request_id)
        if artifact:
            self.store.put_record(
                "compute_job_artifact",
                str(artifact["artifact_id"]),
                artifact,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                task_type=str(job.get("task_type", "")),
                status="available",
                request_id=request_id,
            )
        credit_debit: Mapping[str, Any] = {}
        provider_payout: Mapping[str, Any] = {}
        provider_sla_penalty: Mapping[str, Any] = {}
        credit_release: Mapping[str, Any] = {}
        if usage_charge:
            self.store.put_record(
                "usage_charge",
                str(usage_charge["usage_charge_id"]),
                usage_charge,
                tenant_id=str(usage_charge.get("account_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                task_type=str(job.get("task_type", "")),
                status=str(usage_charge["status"]),
                request_id=request_id,
                idempotency_key=str(usage_charge["usage_charge_id"]),
            )
            self._audit(
                "billing.usage.charged",
                payload,
                request_id=request_id,
                result=str(usage_charge["status"]),
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
            )
            self.telemetry.increment("billing_debit_total", {"provider_id": str(job.get("provider_id", ""))}, value=float(usage_charge["amount"]))
            if sla_latency_breached:
                provider_sla_penalty = _provider_sla_penalty(
                    provider if isinstance(provider, Mapping) else {},
                    job,
                    usage_charge,
                    request_id=request_id,
                )
                if provider_sla_penalty:
                    self.store.put_record(
                        "provider_sla_penalty",
                        str(provider_sla_penalty["sla_penalty_id"]),
                        provider_sla_penalty,
                        tenant_id=str(provider_sla_penalty.get("account_id", "")),
                        provider_id=str(provider_sla_penalty.get("provider_id", "")),
                        route_id=str(provider_sla_penalty.get("route_id", "")),
                        status=str(provider_sla_penalty.get("status", "")),
                        request_id=request_id,
                        idempotency_key=str(provider_sla_penalty["sla_penalty_id"]),
                    )
                    self.telemetry.increment(
                        "provider_sla_penalty_total",
                        {"provider_id": str(provider_sla_penalty.get("provider_id", ""))},
                        value=float(provider_sla_penalty.get("recommended_credit_amount", 0.0) or 0.0),
                    )
                    self._audit(
                        "billing.provider_sla_penalty.recorded",
                        payload,
                        request_id=request_id,
                        result=str(provider_sla_penalty.get("status", "")),
                        provider_id=str(provider_sla_penalty.get("provider_id", "")),
                        route_id=str(provider_sla_penalty.get("route_id", "")),
                    )
            account_id = str(usage_charge.get("account_id", ""))
            if account_id:
                credit_debit = _debit_credit(
                    self.store,
                    account_id,
                    amount=float(usage_charge["amount"]),
                    currency=str(usage_charge["currency"]),
                    request_id=request_id,
                    usage_charge_id=str(usage_charge["usage_charge_id"]),
                    reservation_transaction_id=str(job.get("credit_reservation_id", "")),
                )
                if str(credit_debit.get("status", "")) == "insufficient_credit":
                    self.telemetry.increment(
                        "billing_insufficient_credit_total",
                        {
                            "provider_id": str(job.get("provider_id", "")),
                            "currency": str(usage_charge["currency"]),
                        },
                        value=float(usage_charge["amount"]),
                    )
                provider_payout = _accrue_provider_payout(
                    self.store,
                    provider_id=str(job.get("provider_id", "")),
                    job_id=job_id,
                    account_id=account_id,
                    route_id=str(job.get("route_id", "")),
                    amount=float(usage_charge["amount"]),
                    currency=str(usage_charge["currency"]),
                    request_id=request_id,
                    usage_charge_id=str(usage_charge["usage_charge_id"]),
                )
                if credit_debit:
                    self._audit("billing.usage.debited", payload, request_id=request_id, result=str(credit_debit.get("status", "")), provider_id=str(job.get("provider_id", "")), route_id=str(job.get("route_id", "")))
                if provider_payout:
                    self._audit("billing.provider_payout.accrued", payload, request_id=request_id, result=str(provider_payout.get("status", "")), provider_id=str(job.get("provider_id", "")), route_id=str(job.get("route_id", "")))
        if not usage_charge:
            credit_release = _release_credit_reservation(
                self.store,
                job,
                request_id=request_id,
                reason="job_completed_without_charge",
            )
        event = _job_event(
            job_id,
            "job.completed",
            status="succeeded",
            request_id=request_id,
            details={
                "artifact_recorded": bool(artifact),
                "usage_charge_recorded": bool(usage_charge),
                "credit_debit_recorded": bool(credit_debit),
                "credit_release_recorded": bool(credit_release),
                "provider_payout_recorded": bool(provider_payout),
                "provider_sla_penalty_recorded": bool(provider_sla_penalty),
                "actual_total_cost": cost,
                "funds_moved": False,
                "provider_sla_max_latency_ms": sla_max_latency_ms,
                "provider_sla_latency_breached": sla_latency_breached,
                "worker_id": worker_id,
            },
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="succeeded",
            request_id=request_id,
            actor_id=worker_id,
        )
        self.telemetry.increment("compute_job_completed_total", {"task_type": str(job.get("task_type", ""))})
        if cost:
            self.telemetry.observe("compute_actual_cost", cost, labels={"provider_id": str(job.get("provider_id", ""))})
        self._audit(
            "compute.job.completed",
            {**dict(payload), "job_id": job_id, "worker_id": worker_id},
            request_id=request_id,
            result="succeeded",
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
        )
        return {
            "ok": True,
            "job": job,
            "event": event,
            "artifact": artifact,
            "usage_charge": usage_charge,
            "credit_debit": credit_debit,
            "provider_payout": provider_payout,
            "provider_sla_penalty": provider_sla_penalty,
            "credit_release": credit_release,
        }

    def fail_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        provider_id = str(job.get("provider_id", ""))
        route_id = str(job.get("route_id", ""))
        callback_rejection = self._provider_callback_ip_rejection(
            payload,
            request_id=request_id,
            job_id=job_id,
            provider_id=provider_id,
            route_id=route_id,
            callback_action="fail",
            audit_action="compute.job.fail_rejected",
        )
        if callback_rejection is not None:
            return callback_rejection
        _assert_job_status(job, ("queued", "dispatched", "running"), "fail")
        worker_id = _assert_claim_owner(job, payload, "fail")
        credit_release = _release_credit_reservation(self.store, job, request_id=request_id, reason="job_failed")
        failed_at = utc_now_iso()
        error_code = str(payload.get("error_code", "provider_execution_failed"))
        previous_lease_expires_at = str(job.get("lease_expires_at", ""))
        job.update(
            {
                "status": "failed",
                "failed_at": failed_at,
                "updated_at": failed_at,
                "error_code": error_code,
                "failure_reason": str(payload.get("reason", "")),
                "lifecycle": _append_lifecycle(job, "failed"),
                "lease_expires_at": "",
            }
        )
        if previous_lease_expires_at:
            job["last_lease_expires_at"] = previous_lease_expires_at
        if worker_id:
            job["failed_by_worker_id"] = worker_id
        if credit_release:
            job["credit_release"] = credit_release
        self.store.put_record(
            "compute_job",
            job_id,
            job,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="failed",
            request_id=request_id,
            actor_id=worker_id,
        )
        event = _job_event(
            job_id,
            "job.failed",
            status="failed",
            request_id=request_id,
            details={
                "error_code": error_code,
                "reason": str(payload.get("reason", "")),
                "worker_id": worker_id,
                "credit_release": credit_release,
            },
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="failed",
            request_id=request_id,
            actor_id=worker_id,
        )
        self.telemetry.increment("compute_job_failed_total", {"task_type": str(job.get("task_type", "")), "error_code": error_code})
        self._audit(
            "compute.job.failed",
            {**dict(payload), "job_id": job_id, "worker_id": worker_id},
            request_id=request_id,
            result="failed",
            reason_codes=(error_code,),
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
        )
        return {"ok": True, "job": job, "event": event, "credit_release": credit_release}

    def cancel_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        if str(job.get("status", "")) in {"succeeded", "failed", "cancelled"}:
            return {"ok": True, "job": job, "unchanged": True}
        credit_release = _release_credit_reservation(self.store, job, request_id=request_id, reason="job_cancelled")
        cancelled_at = utc_now_iso()
        job.update(
            {
                "status": "cancelled",
                "cancelled_at": cancelled_at,
                "updated_at": cancelled_at,
                "lease_expires_at": "",
            }
        )
        if credit_release:
            job["credit_release"] = credit_release
        self.store.put_record(
            "compute_job",
            job_id,
            job,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="cancelled",
            expires_at="",
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        event = _job_event(
            job_id,
            "job.cancelled",
            status="cancelled",
            request_id=request_id,
            details={"reason": str(payload.get("reason", "")), "credit_release": credit_release},
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="cancelled",
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        self._audit("compute.job.cancelled", payload, request_id=request_id, result="cancelled", provider_id=str(job.get("provider_id", "")), route_id=str(job.get("route_id", "")))
        return {"ok": True, "job": job, "event": event, "credit_release": credit_release}

    def retry_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        current_attempts = int(job.get("attempt", 0) or 0)
        max_retries = _job_max_retries(job)
        if current_attempts >= max_retries:
            error = compute_error(
                "policy.max_retries_exceeded",
                "Compute job exceeded its maximum retry attempts.",
                details={"job_id": job_id, "attempt": current_attempts, "max_retries": max_retries},
                request_id=request_id,
                retryable=False,
            )
            event = _job_event(
                job_id,
                "job.max_retries_exceeded",
                status=str(job.get("status", "")),
                request_id=request_id,
                details={"attempt": current_attempts, "max_retries": max_retries},
            )
            self.store.put_record(
                "compute_job_event",
                str(event["event_id"]),
                event,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                status=str(job.get("status", "")),
                request_id=request_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            self._audit(
                "compute.job.max_retries_exceeded",
                payload,
                request_id=request_id,
                result="rejected",
                reason_codes=("max_retries_exceeded",),
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
            )
            return {"ok": False, "job": job, "event": event, "error": error.as_record()}
        credit_release = _release_credit_reservation(self.store, job, request_id=request_id, reason="job_retried")
        retry_at = utc_now_iso()
        attempts = current_attempts + 1
        job.update(
            {
                "status": "queued",
                "attempt": attempts,
                "retried_at": retry_at,
                "updated_at": retry_at,
                "claimed_by": "",
                "lease_expires_at": "",
                "worker_capabilities": (),
            }
        )
        job.pop("credit_reservation_id", None)
        job.pop("credit_reserved_amount", None)
        if credit_release:
            job["credit_release"] = credit_release
        self.store.put_record(
            "compute_job",
            job_id,
            job,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="queued",
            expires_at="",
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        event = _job_event(
            job_id,
            "job.retry_queued",
            status="queued",
            request_id=request_id,
            details={"attempt": attempts, "credit_release": credit_release},
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="queued",
            request_id=request_id,
            tenant_id=str(job.get("tenant_id", "")),
            workspace_id=str(job.get("workspace_id", "")),
        )
        self._audit("compute.job.retry_queued", payload, request_id=request_id, result="queued", provider_id=str(job.get("provider_id", "")), route_id=str(job.get("route_id", "")))
        return {"ok": True, "job": job, "event": event, "credit_release": credit_release}

    def claim_job(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        worker_id = _worker_id(payload)
        ttl_seconds = _lease_ttl_seconds(payload)
        lease_expires_at = _future_utc_iso(ttl_seconds)
        requested_job_id = str(payload.get("job_id", "")).strip()
        self._expire_job_leases(payload, request_id=request_id)
        candidates = _claim_candidates(self.store, requested_job_id=requested_job_id, tenant_id=_payload_tenant_id(payload))
        for candidate in candidates:
            job = dict(candidate)
            job_id = str(job.get("job_id", job.get("record_id", "")))
            if not job_id:
                continue
            status = str(job.get("status", ""))
            expires_at_before = ""
            if status == "queued":
                expected_statuses = ("queued",)
            elif status == "dispatched" and _job_lease_expired(job, utc_now_iso()):
                expected_statuses = ("dispatched",)
                expires_at_before = utc_now_iso()
            else:
                continue
            if status == "queued" and int(job.get("dispatch_attempt", 0) or 0) >= _job_max_dispatch_attempts(job):
                exhausted_job, event, error = self._mark_job_dispatch_attempts_exceeded(
                    job,
                    payload,
                    request_id=request_id,
                )
                if requested_job_id:
                    return {"ok": False, "job": exhausted_job, "event": event, "error": error}
                continue
            claimed_at = utc_now_iso()
            claim_token = deterministic_id(
                "job_claim",
                {"job_id": job_id, "worker_id": worker_id, "request_id": request_id, "claimed_at": claimed_at},
            )
            job.update(
                {
                    "status": "dispatched",
                    "claimed_by": worker_id,
                    "claim_token": claim_token,
                    "claimed_at": claimed_at,
                    "lease_expires_at": lease_expires_at,
                    "worker_capabilities": _worker_capabilities(payload),
                    "dispatch_attempt": int(job.get("dispatch_attempt", 0) or 0) + 1,
                    "updated_at": claimed_at,
                    "lifecycle": _append_lifecycle(job, "dispatched"),
                    "provider_dispatch": "worker_queue_claim",
                }
            )
            claimed = self.store.put_record_if_state(
                "compute_job",
                job_id,
                expected_statuses,
                job,
                expires_at_before=expires_at_before,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                task_type=str(job.get("task_type", "")),
                status="dispatched",
                expires_at=lease_expires_at,
                request_id=request_id,
                actor_id=worker_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            if not claimed:
                continue
            event = _job_event(
                job_id,
                "job.claimed",
                status="dispatched",
                request_id=request_id,
                details={
                    "worker_id": worker_id,
                    "lease_expires_at": lease_expires_at,
                    "claim_token": claim_token,
                    "dry_run_only": True,
                    "external_provider_called": False,
                },
            )
            self.store.put_record(
                "compute_job_event",
                str(event["event_id"]),
                event,
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
                status="dispatched",
                request_id=request_id,
                actor_id=worker_id,
                tenant_id=str(job.get("tenant_id", "")),
                workspace_id=str(job.get("workspace_id", "")),
            )
            self._audit(
                "compute.job.claimed",
                {**dict(payload), "job_id": job_id, "worker_id": worker_id},
                request_id=request_id,
                result="dispatched",
                provider_id=str(job.get("provider_id", "")),
                route_id=str(job.get("route_id", "")),
            )
            return {"ok": True, "job": job, "event": event, "lease_expires_at": lease_expires_at}
        if requested_job_id:
            raise ValueError(f"compute job is not available to claim: {requested_job_id}")
        return {"ok": False, "job": {}, "event": {}, "reason": "no_available_queued_job"}

    def heartbeat_job(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        provider_id = str(job.get("provider_id", ""))
        route_id = str(job.get("route_id", ""))
        callback_rejection = self._provider_callback_ip_rejection(
            payload,
            request_id=request_id,
            job_id=job_id,
            provider_id=provider_id,
            route_id=route_id,
            callback_action="heartbeat",
            audit_action="compute.job.heartbeat_rejected",
        )
        if callback_rejection is not None:
            return callback_rejection
        worker_id = _worker_id(payload)
        _assert_job_status(job, ("dispatched", "running"), "heartbeat")
        _assert_claim_owner(job, payload, "heartbeat")
        lease_expires_at = _future_utc_iso(_lease_ttl_seconds(payload))
        heartbeat_at = utc_now_iso()
        job.update(
            {
                "lease_expires_at": lease_expires_at,
                "last_heartbeat_at": heartbeat_at,
                "heartbeat_count": int(job.get("heartbeat_count", 0) or 0) + 1,
                "updated_at": heartbeat_at,
            }
        )
        updated = self.store.put_record_if_state(
            "compute_job",
            job_id,
            (str(job.get("status", "")),),
            job,
            expected_actor_id=worker_id,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status=str(job.get("status", "")),
            expires_at=lease_expires_at,
            request_id=request_id,
            actor_id=worker_id,
        )
        if not updated:
            raise ValueError(f"cannot heartbeat compute job {job_id}; worker lease changed")
        event = _job_event(
            job_id,
            "job.heartbeat",
            status=str(job.get("status", "")),
            request_id=request_id,
            details={"worker_id": worker_id, "lease_expires_at": lease_expires_at},
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status=str(job.get("status", "")),
            request_id=request_id,
            actor_id=worker_id,
        )
        self._audit(
            "compute.job.heartbeat",
            {**dict(payload), "job_id": job_id, "worker_id": worker_id},
            request_id=request_id,
            result=str(job.get("status", "")),
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
        )
        return {"ok": True, "job": job, "event": event, "lease_expires_at": lease_expires_at}

    def release_job_claim(self, job_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        worker_id = _worker_id(payload)
        job = dict(self.get_job(job_id, payload)["job"])
        _assert_job_status(job, ("dispatched",), "release claim")
        _assert_claim_owner(job, payload, "release claim")
        released_at = utc_now_iso()
        previous_claim = {
            "claimed_by": str(job.get("claimed_by", "")),
            "lease_expires_at": str(job.get("lease_expires_at", "")),
            "claim_token": str(job.get("claim_token", "")),
        }
        job.update(
            {
                "status": "queued",
                "claimed_by": "",
                "claim_token": "",
                "lease_expires_at": "",
                "released_at": released_at,
                "last_released_claim": previous_claim,
                "updated_at": released_at,
                "provider_dispatch": "",
            }
        )
        released = self.store.put_record_if_state(
            "compute_job",
            job_id,
            ("dispatched",),
            job,
            expected_actor_id=worker_id,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            task_type=str(job.get("task_type", "")),
            status="queued",
            expires_at="",
            request_id=request_id,
            actor_id="",
        )
        if not released:
            raise ValueError(f"cannot release compute job claim for {job_id}; worker lease changed")
        event = _job_event(
            job_id,
            "job.claim_released",
            status="queued",
            request_id=request_id,
            details={"worker_id": worker_id, "reason": str(payload.get("reason", ""))},
        )
        self.store.put_record(
            "compute_job_event",
            str(event["event_id"]),
            event,
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
            status="queued",
            request_id=request_id,
            actor_id=worker_id,
        )
        self._audit(
            "compute.job.claim_released",
            {**dict(payload), "job_id": job_id, "worker_id": worker_id},
            request_id=request_id,
            result="queued",
            provider_id=str(job.get("provider_id", "")),
            route_id=str(job.get("route_id", "")),
        )
        return {"ok": True, "job": job, "event": event}

    def billing_checkout(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        account_id = _billing_account_id(payload)
        amount = _positive_float(payload.get("amount"), "amount")
        currency = str(payload.get("currency", "USD")).upper()
        account = _billing_account(account_id, payload)
        self.store.put_record("billing_account", account_id, account, tenant_id=str(account.get("tenant_id", "")), workspace_id=str(account.get("workspace_id", "")), status="active", request_id=request_id)
        payment_event_id = deterministic_id(
            "payment_event",
            {"account_id": account_id, "amount": amount, "currency": currency, "request_id": request_id},
        )
        checkout = {
            "payment_event_id": payment_event_id,
            "account_id": account_id,
            "provider": str(payload.get("provider", "stripe")),
            "event_type": "checkout.requested",
            "amount": amount,
            "currency": currency,
            "status": "requires_external_checkout_provider",
            "dry_run_only": True,
            "funds_moved": False,
            "raw_event_hash": content_hash({"account_id": account_id, "amount": amount, "currency": currency, "request_id": request_id}),
            "created_at": utc_now_iso(),
        }
        ok = False
        audit_result = "requires_external_provider"
        reason_codes: tuple[str, ...] = ("external_checkout_provider_missing",)
        next_safe_actions: tuple[str, ...] = ("configure Stripe Checkout and webhook secret before accepting payments",)
        if str(checkout["provider"]).lower() == "stripe" and self.config.stripe_checkout_enabled:
            if not (self.config.stripe_secret_key and self.config.stripe_webhook_secret):
                checkout["status"] = "requires_stripe_checkout_config"
                checkout["reason_codes"] = ("stripe_checkout_config_missing",)
                audit_result = "requires_stripe_checkout_config"
                reason_codes = ("stripe_checkout_config_missing",)
            else:
                try:
                    stripe_session = _create_stripe_checkout_session(
                        self.config,
                        checkout,
                        payload,
                        request_id=request_id,
                        idempotency_key=str(payload.get("idempotency_key") or payment_event_id),
                    )
                except RuntimeError:
                    checkout["status"] = "external_checkout_failed"
                    checkout["reason_codes"] = ("stripe_checkout_failed",)
                    audit_result = "external_checkout_failed"
                    reason_codes = ("stripe_checkout_failed",)
                    next_safe_actions = ("retry with Stripe health verified; do not credit balance until webhook verifies",)
                else:
                    checkout.update(
                        {
                            "status": "checkout_redirect_pending",
                            "external_checkout_session_id": stripe_session["id"],
                            "external_checkout_url": stripe_session["url"],
                            "external_payment_provider": "stripe",
                            "external_payment_recorded": True,
                        }
                    )
                    ok = True
                    audit_result = "checkout_redirect_pending"
                    reason_codes = ()
                    next_safe_actions = ("redirect user to external_checkout_url", "credit balance only after verified Stripe webhook")

        if ok:
            self.telemetry.increment("billing_checkout_created_total", {"provider": str(checkout["provider"])})
        elif checkout["status"] in {"external_checkout_failed", "requires_stripe_checkout_config"}:
            self.telemetry.increment("billing_checkout_failed_total", {"provider": str(checkout["provider"])})
        self.store.put_record(
            "payment_event",
            payment_event_id,
            checkout,
            tenant_id=str(account.get("tenant_id", "")),
            workspace_id=str(account.get("workspace_id", "")),
            status=str(checkout["status"]),
            request_id=request_id,
            idempotency_key=str(payload.get("idempotency_key", "")),
        )
        self._audit(
            "billing.checkout.requested",
            {**dict(payload), "payment_event_id": payment_event_id, "checkout_status": checkout["status"]},
            request_id=request_id,
            result=audit_result,
            reason_codes=reason_codes,
        )
        return {"ok": ok, "checkout": checkout, "next_safe_actions": next_safe_actions}

    def billing_webhook_stripe(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        raw_event = payload.get("raw_event", {})
        if not isinstance(raw_event, Mapping):
            raise ValueError("raw_event must be an object")
        secret = self.config.stripe_webhook_secret
        if not secret and self.config.compute_market_mode == "test":
            secret = str(payload.get("webhook_secret", ""))
        signature = str(payload.get("stripe_signature", ""))
        raw_event_body = str(payload.get("raw_event_body", ""))
        verified = bool(secret) and _verify_webhook_signature(
            raw_event,
            secret,
            signature,
            raw_event_body=raw_event_body,
            tolerance_seconds=self.config.stripe_webhook_tolerance_seconds,
        )
        event_id = str(raw_event.get("id") or deterministic_id("payment_event", raw_event))
        event_type = str(raw_event.get("type", ""))
        account_id = _billing_account_id(payload, fallback_account_id=_stripe_account_id(raw_event, {}))
        credit = _stripe_credit(raw_event)
        credit_amount = _non_negative_float(credit["amount"], "amount")
        credit_currency = str(credit["currency"])
        failure = _stripe_failure(raw_event)
        status = _stripe_payment_event_status(event_type, verified)
        raw_event_hash = content_hash(raw_event)
        existing = self.store.get_record("payment_event", event_id)
        if existing is not None:
            if str(existing.get("raw_event_hash", "")) != raw_event_hash:
                error = compute_error(
                    "billing.webhook.event_id_hash_mismatch",
                    "Stripe webhook event_id replay used a different raw event hash.",
                    details={"payment_event_id": event_id, "provider": "stripe"},
                    request_id=request_id,
                )
                self.telemetry.increment("billing_webhook_failures_total", {"provider": "stripe"})
                self._audit(
                    "billing.webhook.replay_rejected",
                    payload,
                    request_id=request_id,
                    result="rejected",
                    reason_codes=("billing.webhook.event_id_hash_mismatch",),
                )
                return {"ok": False, "payment_event": existing, "credit_transaction": {}, "error": error.as_record(), "idempotent_replay": False}
            if not verified:
                error = compute_error(
                    "billing.webhook.signature_required",
                    "Stripe webhook replay requires a valid webhook signature.",
                    details={"payment_event_id": event_id, "provider": "stripe"},
                    request_id=request_id,
                )
                self.telemetry.increment("billing_webhook_failures_total", {"provider": "stripe"})
                self._audit(
                    "billing.webhook.replay_rejected",
                    payload,
                    request_id=request_id,
                    result="rejected",
                    reason_codes=("billing.webhook.signature_required",),
                )
                return {"ok": False, "payment_event": existing, "credit_transaction": {}, "error": error.as_record(), "idempotent_replay": True}
            if bool(existing.get("verified", False)):
                existing_account_id = str(existing.get("account_id", ""))
                credit_transaction: Mapping[str, Any] = {}
                if existing_account_id:
                    credit_transaction_id = deterministic_id(
                        "credit_transaction",
                        {"account_id": existing_account_id, "source_event_id": event_id, "type": "credit"},
                    )
                    credit_transaction = self.store.get_record("credit_transaction", credit_transaction_id) or {}
                self._audit("billing.webhook.replayed", payload, request_id=request_id, result=str(existing.get("status", "verified")))
                return {"ok": True, "payment_event": existing, "credit_transaction": credit_transaction, "idempotent_replay": True}
        reason_codes = _stripe_webhook_reason_codes(status, failure)
        record = {
            "payment_event_id": event_id,
            "account_id": account_id,
            "provider": "stripe",
            "event_type": event_type,
            "verified": verified,
            "status": status,
            "raw_event_hash": raw_event_hash,
            "amount": credit_amount,
            "currency": credit_currency,
            "failure_recorded": bool(failure),
            "failure_code": str(failure.get("code", "")),
            "failure_reason": str(failure.get("reason", "")),
            "dry_run_only": True,
            "funds_moved": False,
            "external_payment_recorded": verified,
            "created_at": utc_now_iso(),
        }
        if not verified:
            self.telemetry.increment("billing_webhook_failures_total", {"provider": "stripe"})
        elif _stripe_event_is_payment_failure(event_type):
            self.telemetry.increment("billing_payment_failed_total", {"provider": "stripe", "event_type": event_type})
        self.store.put_record("payment_event", event_id, record, tenant_id=account_id, status=str(record["status"]), request_id=request_id, idempotency_key=event_id)
        credit_record: Mapping[str, Any] = {}
        if verified and account_id and credit_amount > 0 and _stripe_event_posts_credit(raw_event):
            credit_record = _apply_credit(
                self.store,
                account_id,
                amount=credit_amount,
                currency=credit_currency,
                request_id=request_id,
                source_event_id=event_id,
            )
            self._audit("billing.credit.added", payload, request_id=request_id, result="credited")
        self._audit("billing.webhook.received", payload, request_id=request_id, result=str(record["status"]), reason_codes=reason_codes)
        return {"ok": verified, "payment_event": record, "credit_transaction": credit_record}

    def billing_balance(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        account_id = _billing_account_id(payload)
        balance = self.store.get_record("credit_balance", account_id) or {
            "account_id": account_id,
            "available_credits": 0.0,
            "reserved_credits": 0.0,
            "currency": "USD",
            "updated_at": utc_now_iso(),
        }
        return {"ok": True, "balance": balance}

    def billing_usage(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        account_id = _billing_account_id(payload)
        filters = {"tenant_id": account_id}
        charges = tuple(self.store.list_records("usage_charge", filters=filters, limit=int(payload.get("limit", 100) or 100)).records)
        return {"ok": True, "usage_charges": charges, "account_id": account_id}

    def billing_provider_payouts(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        filters: dict[str, Any] = {"tenant_id": _billing_account_id(payload)}
        provider_id = str(payload.get("provider_id", "")).strip()
        status = str(payload.get("status", "")).strip()
        if provider_id:
            filters["provider_id"] = provider_id
        if status:
            filters["status"] = status
        page = self.store.list_records(
            "provider_payout",
            filters=filters,
            limit=int(payload.get("limit", 100) or 100),
            cursor=str(payload.get("cursor", "")),
        )
        return {
            "ok": True,
            "provider_payouts": page.records,
            "next_cursor": page.next_cursor,
            "summary": _provider_payout_summary(page.records),
        }

    def settle_provider_payout(self, payout_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        payout = self.store.get_record("provider_payout", payout_id)
        if payout is None:
            raise KeyError(f"Unknown provider payout: {payout_id}")
        _billing_account_id(payload, fallback_account_id=str(payout.get("account_id", "")).strip())
        current_status = str(payout.get("status", ""))
        if current_status != "accrued":
            raise ValueError(f"provider payout is not accrued: {current_status}")
        now = utc_now_iso()
        settled = {
            **dict(payout),
            "status": "settled",
            "settled_at": now,
            "updated_at": now,
            "settled_by": str(payload.get("settled_by") or payload.get("actor_id") or "operator"),
            "external_payout_reference": str(payload.get("external_payout_reference", "")),
            "external_disbursement_recorded": True,
            "dry_run_only": True,
            "funds_moved": False,
        }
        self.store.put_record(
            "provider_payout",
            payout_id,
            settled,
            tenant_id=str(settled.get("account_id", "")),
            provider_id=str(settled.get("provider_id", "")),
            route_id=str(settled.get("route_id", "")),
            status="settled",
            request_id=request_id,
            actor_id=str(settled.get("settled_by", "")),
            idempotency_key=str(payload.get("idempotency_key", payout_id)),
        )
        self.telemetry.increment(
            "billing_payout_settled_total",
            {"provider_id": str(settled.get("provider_id", ""))},
            value=float(settled.get("amount", 0.0) or 0.0),
        )
        self._audit(
            "billing.provider_payout.settled",
            {**dict(payload), "provider_payout_id": payout_id},
            request_id=request_id,
            result="settled",
            provider_id=str(settled.get("provider_id", "")),
            route_id=str(settled.get("route_id", "")),
        )
        return {"ok": True, "provider_payout": settled}

    def billing_refund(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        request_id = _request_id(payload)
        idempotency_key = str(payload.get("idempotency_key", "")).strip()
        if idempotency_key:
            existing = self.store.find_by_idempotency("refund", idempotency_key)
            if existing is not None:
                replay_credit_transaction = _refund_credit_transaction(self.store, existing)
                return {"ok": True, "refund": existing, "credit_transaction": replay_credit_transaction, "idempotent_replay": True}

        usage_charge_id = str(payload.get("usage_charge_id", "")).strip()
        usage_charge = self.store.get_record("usage_charge", usage_charge_id) if usage_charge_id else None
        if usage_charge_id and usage_charge is None:
            raise ValueError(f"Unknown usage charge: {usage_charge_id}")

        account_id = _billing_account_id(payload, fallback_account_id=str((usage_charge or {}).get("account_id", "")).strip())
        if usage_charge is not None:
            usage_account_id = str(usage_charge.get("account_id", "")).strip()
            if usage_account_id and usage_account_id != account_id:
                raise ValueError("refund account_id does not match usage charge account_id")

        amount_source = payload.get("amount", (usage_charge or {}).get("amount"))
        amount = _positive_float(amount_source, "amount")
        currency = str(payload.get("currency") or (usage_charge or {}).get("currency", "USD")).upper()
        provider_id = str(payload.get("provider_id") or (usage_charge or {}).get("provider_id", ""))
        route_id = str(payload.get("route_id") or (usage_charge or {}).get("route_id", ""))

        if usage_charge is not None:
            original_amount = _positive_float(usage_charge.get("amount"), "usage_charge.amount")
            prior_refunds = self.store.list_records("refund", filters={"action": usage_charge_id}, limit=500).records
            already_refunded = sum(float(refund.get("amount", 0.0) or 0.0) for refund in prior_refunds)
            if already_refunded + amount > original_amount + 0.000001:
                raise ValueError("refund amount exceeds remaining usage charge amount")

        refund_id = str(
            payload.get("refund_id")
            or deterministic_id(
                "refund",
                {
                    "account_id": account_id,
                    "usage_charge_id": usage_charge_id,
                    "amount": amount,
                    "currency": currency,
                    "source_event_id": str(payload.get("source_event_id", "")),
                    "idempotency_key": idempotency_key,
                    "reason": str(payload.get("reason", "")),
                },
            )
        )
        existing_refund = self.store.get_record("refund", refund_id)
        if existing_refund is not None:
            existing_refund_credit_transaction = _refund_credit_transaction(self.store, existing_refund)
            return {"ok": True, "refund": existing_refund, "credit_transaction": existing_refund_credit_transaction, "idempotent_replay": True}

        now = utc_now_iso()
        refund = {
            "refund_id": refund_id,
            "usage_charge_id": usage_charge_id,
            "account_id": account_id,
            "provider_id": provider_id,
            "route_id": route_id,
            "amount": amount,
            "currency": currency,
            "reason": str(payload.get("reason", "")),
            "source_event_id": str(payload.get("source_event_id", usage_charge_id)),
            "status": "recorded_no_custody",
            "dry_run_only": True,
            "funds_moved": False,
            "external_refund_created": False,
            "created_at": now,
            "updated_at": now,
            "request_id": request_id,
        }
        self.store.put_record(
            "refund",
            refund_id,
            refund,
            tenant_id=account_id,
            provider_id=provider_id,
            route_id=route_id,
            status=str(refund["status"]),
            request_id=request_id,
            idempotency_key=idempotency_key or refund_id,
            action=usage_charge_id,
        )
        credit_transaction: Mapping[str, Any] = {}
        if usage_charge is not None:
            debit_id = deterministic_id("credit_transaction", {"account_id": account_id, "usage_charge_id": usage_charge_id, "type": "debit"})
            debit = self.store.get_record("credit_transaction", debit_id)
            if debit is not None and debit.get("status") == "posted":
                credit_transaction = _apply_refund_credit(
                    self.store,
                    account_id,
                    amount=amount,
                    currency=currency,
                    request_id=request_id,
                    refund_id=refund_id,
                    usage_charge_id=usage_charge_id,
                )
        self._audit(
            "billing.refund.recorded",
            payload,
            request_id=request_id,
            result=str(refund["status"]),
            provider_id=provider_id,
            route_id=route_id,
        )
        return {"ok": True, "refund": refund, "credit_transaction": credit_transaction, "idempotent_replay": False}


    def reconciliation(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        usage_charges = self._all_records("usage_charge")
        payment_events = self._all_records("payment_event")
        provider_payouts = self._all_records("provider_payout")
        refunds = self._all_records("refund")
        provider_sla_penalties = self._all_records("provider_sla_penalty")
        usage_total = _record_amount_total(usage_charges)
        refund_total = _record_amount_total(refunds)
        provider_payout_total = _record_amount_total(provider_payouts)
        ledger_balance_delta = round(usage_total - refund_total - provider_payout_total, 6)
        run_id = deterministic_id("reconciliation", {"created_at": utc_now_iso(), "scope": payload})
        run = {
            "reconciliation_run_id": run_id,
            "status": "dry_run_reconciled" if abs(ledger_balance_delta) <= 0.000001 else "dry_run_reconciliation_attention",
            "usage_charge_count": len(usage_charges),
            "payment_event_count": len(payment_events),
            "provider_payout_count": len(provider_payouts),
            "refund_count": len(refunds),
            "provider_sla_penalty_count": len(provider_sla_penalties),
            "usage_charge_total": usage_total,
            "refund_total": refund_total,
            "provider_payout_total": provider_payout_total,
            "provider_payout_summary": _provider_payout_summary(provider_payouts),
            "ledger_balance_delta": ledger_balance_delta,
            "ledger_balanced": abs(ledger_balance_delta) <= 0.000001,
            "funds_moved": False,
            "created_at": utc_now_iso(),
        }
        self.store.put_record("reconciliation_run", run_id, run, status=str(run["status"]))
        return {"ok": True, "reconciliation": run}

    def economic_memory(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        limited = self._rate_limit_response(payload or {}, "GET /compute/economic-memory", request_id=_request_id(payload or {}))
        if limited is not None:
            return limited
        request = query_request_from_payload(payload or {})
        page = self.store.list_records("economic_memory", filters=request.as_record(), limit=request.limit, cursor=request.cursor)
        self.telemetry.increment("compute_economic_memory_query_total")
        self._audit("compute.economic_memory.queried", payload or {}, result="completed")
        return {"ok": True, "schema_fields": tuple(page.records[0].keys()) if page.records else (), "records": page.records, "next_cursor": page.next_cursor}

    def economic_memory_query(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        limited = self._rate_limit_response(payload, "POST /compute/economic-memory/query", request_id=_request_id(payload), cost=max(1, int(payload.get("limit", 100) or 100) // 100))
        if limited is not None:
            return limited
        request = query_request_from_payload(payload)
        page = self.store.list_records("economic_memory", filters=request.as_record(), limit=request.limit, cursor=request.cursor)
        response = query_economic_memory_typed(page.records, request).as_record()
        return response | {"next_cursor": page.next_cursor}

    def decision(self, decision_id: str) -> Mapping[str, Any]:
        decision = self.store.get_record("route_decision", decision_id)
        if decision is None:
            raise KeyError(f"Unknown compute decision: {decision_id}")
        return {"ok": True, "route_decision": decision}

    def replay_decision(self, decision_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        limited = self._rate_limit_response(payload or {}, "POST /compute/decisions/{decision_id}/replay", request_id=_request_id(payload or {}))
        if limited is not None:
            return limited
        original = self.decision(decision_id)["route_decision"]
        result = replay_decision(original)
        self._audit("compute.decision.replayed", payload or {}, result="completed", decision_id=decision_id)
        return result

    def audit(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        page = self.store.list_records("audit_event", filters=payload or {}, limit=int((payload or {}).get("limit", 100)), cursor=str((payload or {}).get("cursor", "")))
        return {"ok": True, "audit_events": page.records, "next_cursor": page.next_cursor}

    def audit_event(self, audit_event_id: str) -> Mapping[str, Any]:
        event = self.store.get_record("audit_event", audit_event_id)
        if event is None:
            raise KeyError(f"Unknown compute audit event: {audit_event_id}")
        return {"ok": True, "audit_event": event}

    def audit_verify(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        chain_id = str((payload or {}).get("chain_id", ""))
        result = self.store.verify_audit_chain(chain_id=chain_id).as_record()
        ok = bool(result["ok"])
        if not ok:
            self.telemetry.increment("audit_chain_verify_fail_total")
        self._audit(
            "compute.audit.verified",
            payload or {},
            result="completed" if ok else "failed",
            reason_codes=() if ok else (str(result.get("error_code", "audit_chain_invalid")),),
        )
        return {"ok": ok, "audit_chain": result}
    def audit_export(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        out = str(payload.get("out") or payload.get("path") or "")
        exporter = LocalFileAuditExporter(Path(out)) if out else self.audit_exporter
        status = exporter.get_status()
        if not out and status.get("configured") is False:
            raise ValueError("audit export requires configured audit_export_uri or --out/path")
        try:
            result = exporter.export_events(
                self.store,
                chain_id=str(payload.get("chain_id", "all") or "all"),
                from_sequence=int(payload.get("from_sequence", 1) or 1),
                to_sequence=int(payload.get("to_sequence", 0) or 0),
            )
        except ValueError as exc:
            self._audit("compute.audit.export_failed", payload, result="failed", reason_codes=("audit_export_refused",))
            return {"ok": False, "path": out, "warnings": ("audit_export_refused",), "error": str(exc)}
        checkpoint_write = exporter.write_checkpoint(result.checkpoint)
        checkpoint_record = self._persist_audit_checkpoint(
            result.checkpoint,
            manifest_hash=result.manifest_hash,
            storage_uri=result.path,
            checkpoint_write=checkpoint_write,
        )
        self._audit("compute.audit.exported", payload, result="completed", reason_codes=())
        return {**result.as_record(), "checkpoint_record": checkpoint_record}

    def audit_checkpoint(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        chain_id = str(payload.get("chain_id", "all") or "all")
        from_sequence = int(payload.get("from_sequence", 1) or 1)
        to_sequence = int(payload.get("to_sequence", 0) or 0)
        events = self._all_audit_events()
        if chain_id not in {"", "all"}:
            events = tuple(event for event in events if isinstance(event, Mapping) and str(event.get("chain_id", "")) == chain_id)
        events = tuple(
            event
            for event in events
            if int(event.get("sequence_number", 0) or 0) >= from_sequence
            and (to_sequence <= 0 or int(event.get("sequence_number", 0) or 0) <= to_sequence)
        )
        checkpoint = build_checkpoint(
            tuple(event for event in events if isinstance(event, Mapping)),
            chain_id=chain_id,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            export_uri=str(payload.get("out", "")),
            exported_to="checkpoint_only",
        )
        manifest_hash = content_hash({"checkpoint": checkpoint.as_record(), "event_count": checkpoint.event_count})
        checkpoint_record = self._persist_audit_checkpoint(checkpoint, manifest_hash=manifest_hash, storage_uri=str(payload.get("out", "")))
        self._audit("compute.audit.checkpointed", payload, result="completed", reason_codes=())
        return {"ok": True, "checkpoint": checkpoint.as_record(), "checkpoint_record": checkpoint_record}

    def audit_checkpoint_schedule(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        chain_id = str(payload.get("chain_id", "all") or "all")
        min_events = max(1, int(payload.get("min_events", payload.get("checkpoint_min_events", 1000)) or 1000))
        interval_seconds = max(
            1,
            int(
                payload.get(
                    "interval_seconds",
                    payload.get("checkpoint_interval_seconds", self.config.audit_checkpoint_interval_seconds),
                )
                or self.config.audit_checkpoint_interval_seconds
            ),
        )
        force = bool(payload.get("force", False))
        export = bool(payload.get("export", False))
        events = self._audit_events_for_chain(chain_id)
        last_checkpoint = self._last_audit_checkpoint(chain_id)
        last_sequence = int((last_checkpoint or {}).get("to_sequence", 0) or 0)
        pending_events = tuple(event for event in events if int(event.get("sequence_number", 0) or 0) > last_sequence)
        interval_due = _checkpoint_interval_due(last_checkpoint, interval_seconds)
        due = force or len(pending_events) >= min_events or interval_due
        result: Mapping[str, Any] = {}
        if due:
            scheduled_payload = {**dict(payload), "chain_id": chain_id, "from_sequence": max(1, last_sequence + 1)}
            result = self.audit_export(scheduled_payload) if export else self.audit_checkpoint(scheduled_payload)
        else:
            self._audit("compute.audit.checkpoint_schedule_checked", payload, result="skipped", reason_codes=("not_due",))
        return {
            "ok": True,
            "due": due,
            "chain_id": chain_id,
            "min_events": min_events,
            "interval_seconds": interval_seconds,
            "interval_due": interval_due,
            "pending_event_count": len(pending_events),
            "last_checkpoint": last_checkpoint or {},
            "scheduled_result": result,
        }

    def audit_chain_monitor(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        requested_chain = str(payload.get("chain_id", ""))
        chain_ids = (requested_chain,) if requested_chain else (self.store.audit_chain_ids() or ("",))
        chains = tuple(self.store.verify_audit_chain(chain_id=chain_id).as_record() for chain_id in chain_ids)
        checkpoint_page = self.store.list_records("audit_checkpoint_manifest", filters={"chain_id": requested_chain} if requested_chain else {}, limit=100, include_archived=True)
        ok = all(bool(chain.get("ok")) for chain in chains)
        if not ok:
            self.telemetry.increment("audit_chain_verify_fail_total")
        self._audit("compute.audit.chain_monitored", payload, result="completed" if ok else "failed", reason_codes=() if ok else ("audit_chain_invalid",))
        return {
            "ok": ok,
            "chains": chains,
            "checkpoint_count": len(checkpoint_page.records),
            "latest_checkpoint": checkpoint_page.records[-1] if checkpoint_page.records else {},
            "audit_exporter_status": self.audit_exporter.get_status(),
        }

    def admin_audit_export_status(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        chain_id = str(payload.get("chain_id", ""))
        checkpoint_page = self.store.list_records("audit_checkpoint_manifest", filters={"chain_id": chain_id} if chain_id else {}, limit=100, include_archived=True)
        status = self.audit_exporter.get_status()
        immutable = bool(status.get("immutable", False))
        return {
            "ok": bool(status.get("configured")),
            "immutable": immutable,
            "audit_exporter_status": status,
            "checkpoint_count": len(checkpoint_page.records),
            "latest_checkpoint": checkpoint_page.records[-1] if checkpoint_page.records else {},
            "retention_policy": {
                "object_lock_mode": status.get("object_lock_mode", ""),
                "retention_days": status.get("retention_days", 0),
            },
        }

    def audit_forensic_replay(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        path = str(payload.get("path") or payload.get("out") or "")
        chain_id = str(payload.get("chain_id", ""))
        from_sequence = int(payload.get("from_sequence", 1) or 1)
        to_sequence = int(payload.get("to_sequence", 0) or 0)
        if path:
            events = audit_events_from_export_file(path)
            integrity = verify_exported_chain(events)
            export_verification = verify_audit_export(path).as_record()
            source = "export_file"
        else:
            events = self._audit_events_for_chain(chain_id or "all")
            integrity = self.store.verify_audit_chain(chain_id=chain_id).as_record()
            export_verification = {}
            source = "store"
        filtered = tuple(
            event
            for event in events
            if (chain_id in {"", "all"} or str(event.get("chain_id", "")) == chain_id)
            and int(event.get("sequence_number", 0) or 0) >= from_sequence
            and (to_sequence <= 0 or int(event.get("sequence_number", 0) or 0) <= to_sequence)
        )
        timeline = tuple(_audit_replay_event(event) for event in filtered)
        replay_id = deterministic_id("audit_replay", {"path": path, "chain_id": chain_id, "from_sequence": from_sequence, "to_sequence": to_sequence, "event_count": len(filtered)})
        replay = {
            "replay_id": replay_id,
            "source": source,
            "path": path,
            "chain_id": chain_id or "all",
            "from_sequence": from_sequence,
            "to_sequence": to_sequence or (int(filtered[-1].get("sequence_number", 0) or 0) if filtered else 0),
            "event_count": len(filtered),
            "timeline": timeline,
            "summary": _audit_replay_summary(filtered),
            "integrity": integrity,
            "export_verification": export_verification,
            "created_at": utc_now_iso(),
        }
        self.store.put_record("audit_replay_run", replay_id, replay, status="verified" if bool(integrity.get("ok")) else "failed", request_id=str(payload.get("request_id", "")))
        self._audit("compute.audit.replayed", payload, result="completed" if bool(integrity.get("ok")) else "failed", reason_codes=() if bool(integrity.get("ok")) else (str(integrity.get("error_code", "audit_replay_failed")),))
        return {"ok": bool(integrity.get("ok")), "replay": replay}

    def audit_verify_export(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        path = str(payload.get("path") or payload.get("out") or "")
        if not path:
            raise ValueError("audit verify-export requires --path")
        result = verify_audit_export(path)
        self._audit(
            "compute.audit.export_verified",
            payload,
            result="completed" if result.ok else "failed",
            reason_codes=() if result.ok else (result.error_code,),
        )
        return result.as_record()

    def _persist_audit_checkpoint(
        self,
        checkpoint: Any,
        *,
        manifest_hash: str,
        storage_uri: str,
        checkpoint_write: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        record = {
            **checkpoint.as_record(),
            "manifest_hash": manifest_hash,
            "storage_uri": storage_uri or str(checkpoint.as_record().get("storage_uri", "")),
            "checkpoint_write": dict(checkpoint_write or {}),
            "status": "completed",
            "updated_at": utc_now_iso(),
        }
        self.store.put_record(
            "audit_checkpoint_manifest",
            str(record["checkpoint_id"]),
            record,
            status="completed",
            request_id=str(record.get("checkpoint_id", "")),
        )
        return record

    def _last_audit_checkpoint(self, chain_id: str) -> Mapping[str, Any] | None:
        page = self.store.list_records(
            "audit_checkpoint_manifest",
            filters={"chain_id": chain_id} if chain_id not in {"", "all"} else {},
            limit=500,
            include_archived=True,
        )
        records = tuple(
            record for record in page.records
            if chain_id in {"", "all"} or str(record.get("chain_id", "")) == chain_id
        )
        if not records:
            return None
        return max(records, key=lambda record: int(record.get("to_sequence", 0) or 0))

    def _audit_events_for_chain(self, chain_id: str) -> tuple[Mapping[str, Any], ...]:
        events = self._all_audit_events()
        if chain_id in {"", "all"}:
            return events
        return tuple(event for event in events if str(event.get("chain_id", "")) == chain_id)

    def health(self) -> Mapping[str, Any]:
        provider_page = self.store.list_records("compute_provider", limit=50)
        summary = tuple(
            {"provider_id": provider.get("provider_id", ""), "status": provider.get("status", "unknown")}
            for provider in provider_page.records
        )
        audit_writable = self._audit_writable()
        rate_limiter_status = self.rate_limiter.get_status("readiness")
        circuit_breaker_status = self.circuit_breaker.get_state("readiness")
        health = ComputeMarketHealth(
            ok=self.config.compute_market_enabled,
            compute_market_enabled=self.config.compute_market_enabled,
            database_reachable=True,
            provider_registry_reachable=True,
            audit_log_writable=audit_writable,
            quote_cache_reachable=True,
            provider_health_summary=summary,
            mode=self.config.compute_market_mode,
            warnings=self.config.warnings(),
        ).as_record()
        health.update(
            {
                "service_alive": True,
                "storage": self.store.storage_status(),
                "rate_limiter_active": self.config.rate_limits_enabled and bool(rate_limiter_status.get("configured", True)),
                "circuit_breaker_active": bool(circuit_breaker_status.get("configured", True)),
                "rate_limiter_status": rate_limiter_status,
                "circuit_breaker_status": circuit_breaker_status,
                "external_provider_quotes_enabled": self.config.external_provider_quotes_enabled,
                "audit_export_configured": bool(self.config.audit_export_uri),
                "provider_contracts_verified": self.config.provider_contracts_verified,
                "external_provider_allowlist_configured": bool(self.config.external_provider_allowlist),
                "audit_exporter_status": self.audit_exporter.get_status(),
                "telemetry_status": self.telemetry.summary(),
            }
        )
        return health

    def readiness(self) -> Mapping[str, Any]:
        health = dict(self.health())
        migration_status = self.store.migration_status()
        audit_chain = self.store.verify_audit_chain().as_record()
        failures: list[str] = []
        if not health.get("database_reachable", False):
            failures.append("database_unavailable")
        if not migration_status.get("current", False):
            failures.append("migrations_pending")
        if not health.get("audit_log_writable", False):
            failures.append("audit_unwritable")
        if not audit_chain.get("ok", False):
            failures.append("audit_chain_invalid")
        if self.config.rate_limits_enabled and self.rate_limiter is None:
            failures.append("rate_limiter_unavailable")
        rate_limiter_status = health.get("rate_limiter_status", {})
        if (
            self.config.rate_limits_enabled
            and self.config.rate_limit_enabled
            and isinstance(rate_limiter_status, Mapping)
            and rate_limiter_status.get("configured") is False
        ):
            failures.append("rate_limiter_unavailable")
        circuit_breaker_status = health.get("circuit_breaker_status", {})
        if (
            self.config.circuit_breaker_enabled
            and isinstance(circuit_breaker_status, Mapping)
            and circuit_breaker_status.get("configured") is False
        ):
            failures.append("circuit_breaker_unavailable")
        if not health.get("provider_registry_reachable", False):
            failures.append("provider_registry_unavailable")
        if self.config.require_managed_sql_in_production and self.config.storage_backend_effective != "postgresql":
            failures.append("sqlite_disallowed_in_production")
        audit_exporter_status = health.get("audit_exporter_status", {})
        if self.config.audit_export_required and (
            not self.config.audit_export_uri
            or not isinstance(audit_exporter_status, Mapping)
            or audit_exporter_status.get("configured") is False
        ):
            failures.append("audit_export_unavailable")
        if (
            self.config.audit_export_required
            and isinstance(audit_exporter_status, Mapping)
            and audit_exporter_status.get("exporter") == "s3_object_lock"
            and not audit_exporter_status.get("immutable", False)
        ):
            failures.append("audit_immutable_retention_not_configured")
        if (
            self.config.audit_export_immutable_required
            and (
                not isinstance(audit_exporter_status, Mapping)
                or audit_exporter_status.get("exporter") != "s3_object_lock"
                or not audit_exporter_status.get("immutable", False)
            )
        ):
            failures.append("audit_immutable_storage_unavailable")
        if self.config.alert_routing_enabled and not self.config.alert_webhook_url.strip():
            failures.append("alert_webhook_unavailable")
        if self.config.alert_routing_enabled and self.config.alert_webhook_url.strip() and not _alert_webhook_url_allowed(self.config.alert_webhook_url.strip()):
            failures.append("alert_webhook_url_not_allowed")
        if self.config.error_tracking_enabled and not self.config.error_tracking_webhook_url.strip():
            failures.append("error_tracking_webhook_unavailable")
        if (
            self.config.error_tracking_enabled
            and self.config.error_tracking_webhook_url.strip()
            and not _alert_webhook_url_allowed(self.config.error_tracking_webhook_url.strip())
        ):
            failures.append("error_tracking_webhook_url_not_allowed")
        if self.config.telemetry_export_enabled and not self.config.otlp_endpoint_url.strip():
            failures.append("otlp_endpoint_unavailable")
        if (
            self.config.telemetry_export_enabled
            and self.config.otlp_endpoint_url.strip()
            and not _alert_webhook_url_allowed(self.config.otlp_endpoint_url.strip())
        ):
            failures.append("otlp_endpoint_url_not_allowed")
        if self.config.external_provider_quotes_enabled and not self.config.external_provider_allowlist:
            failures.append("external_provider_allowlist_missing")
        if self.config.external_provider_quotes_enabled and not health.get("circuit_breaker_active", False):
            failures.append("external_provider_circuit_breaker_missing")
        if self.config.provider_contracts_required and not self.config.provider_contracts_verified:
            failures.append("provider_contracts_unverified")
        config_errors = self.config.validate()
        if any("live_settlement_enabled" in error for error in config_errors):
            failures.append("unsafe_live_settlement_config")
        if self.config.broadcast_enabled:
            failures.append("unsafe_broadcast_config")
        if self.config.private_key_inputs_allowed:
            failures.append("unsafe_private_key_config")
        _record_readiness_failure_metrics(self.telemetry, tuple(dict.fromkeys(failures)))
        ready = not failures and bool(health.get("compute_market_enabled"))
        health["ready"] = ready
        health["ok"] = ready
        health["readiness_failures"] = tuple(dict.fromkeys(failures))
        health["migration_status"] = migration_status
        health["migration_plan"] = migration_plan()
        health["audit_chain"] = audit_chain
        health["production_safety_defaults"] = self.config.as_record()
        return health

    def telemetry_snapshot(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        reset = str(payload.get("reset", "")).strip().lower() in {"1", "true", "yes", "on"}
        return {"ok": True, "telemetry": self.telemetry.snapshot(reset=reset), "summary": self.telemetry.summary()}

    def prometheus_metrics(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        _ = payload
        return {
            "ok": True,
            "content_type": "text/plain; version=0.0.4",
            "metrics": self.telemetry.prometheus_text(),
        }

    def alert_status(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        _ = payload
        evaluation = AlertEvaluator().evaluate(self.telemetry).as_record()
        acknowledgements = tuple(self.store.list_records("alert_acknowledgement", limit=100).records)
        acknowledged = {str(item.get("rule_name", "")) for item in acknowledgements}
        raw_firing_items = evaluation.get("firing", ())
        firing_items = raw_firing_items if isinstance(raw_firing_items, (list, tuple)) else ()
        firing = tuple(
            {**dict(item), "acknowledged": str(item.get("rule_name", "")) in acknowledged}
            for item in firing_items
            if isinstance(item, Mapping)
        )
        return {
            "ok": True,
            "alerts": {**evaluation, "firing": firing},
            "acknowledgements": acknowledgements,
        }

    def route_alerts(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        evaluation = AlertEvaluator().evaluate(self.telemetry).as_record()
        raw_firing_items = evaluation.get("firing", ())
        firing_items = raw_firing_items if isinstance(raw_firing_items, (list, tuple)) else ()
        firing = tuple(item for item in firing_items if isinstance(item, Mapping))
        if not firing:
            return {
                "ok": True,
                "alerts": evaluation,
                "routing_enabled": self.config.alert_routing_enabled,
                "deliveries": (),
                "delivery_count": 0,
                "skipped_reason": "no_firing_alerts",
            }
        if not self.config.alert_routing_enabled:
            self._audit(
                "compute.alert.routing.attempted",
                payload,
                request_id=request_id,
                result="skipped",
                reason_codes=("alert_routing_disabled",),
            )
            return {
                "ok": True,
                "alerts": evaluation,
                "routing_enabled": False,
                "deliveries": (),
                "delivery_count": 0,
                "skipped_reason": "alert_routing_disabled",
            }
        webhook_url = self.config.alert_webhook_url.strip()
        if not webhook_url:
            self._audit(
                "compute.alert.routing.attempted",
                payload,
                request_id=request_id,
                result="failed",
                reason_codes=("alert_webhook_not_configured",),
            )
            return {
                "ok": False,
                "alerts": evaluation,
                "routing_enabled": True,
                "deliveries": (),
                "delivery_count": 0,
                "error": "alert_webhook_not_configured",
            }
        if not _alert_webhook_url_allowed(webhook_url):
            self._audit(
                "compute.alert.routing.attempted",
                payload,
                request_id=request_id,
                result="failed",
                reason_codes=("alert_webhook_url_not_allowed",),
            )
            return {
                "ok": False,
                "alerts": evaluation,
                "routing_enabled": True,
                "deliveries": (),
                "delivery_count": 0,
                "error": "alert_webhook_url_not_allowed",
            }
        deliveries: list[Mapping[str, Any]] = []
        for alert in firing:
            envelope = _alert_delivery_envelope(alert, request_id=request_id)
            delivery = _alert_delivery_record(alert, webhook_url=webhook_url, request_id=request_id)
            self.telemetry.increment("alert_delivery_pending_total", {"rule_name": str(alert.get("rule_name", ""))})
            if self.config.compute_market_mode == "test":
                delivery = {
                    **delivery,
                    "status": "dry_run_skipped",
                    "delivery_attempted": False,
                    "reason_codes": ("test_mode_no_external_webhook",),
                }
            else:
                sent = _post_alert_webhook(
                    webhook_url,
                    envelope,
                    secret=self.config.alert_webhook_secret,
                    timeout_ms=self.config.alert_webhook_timeout_ms,
                )
                delivery = {**delivery, **sent, "delivery_attempted": True}
            self.store.put_record(
                "alert_delivery",
                str(delivery["delivery_id"]),
                delivery,
                status=str(delivery["status"]),
                request_id=request_id,
                idempotency_key=str(delivery["delivery_id"]),
            )
            if str(delivery["status"]) == "delivered":
                self.telemetry.increment("alert_delivery_sent_total", {"rule_name": str(alert.get("rule_name", ""))})
                self._audit(
                    "compute.alert.delivered",
                    payload,
                    request_id=request_id,
                    result="delivered",
                    reason_codes=(str(alert.get("rule_name", "")),),
                )
            elif str(delivery["status"]) == "failed":
                self.telemetry.increment("alert_delivery_failed_total", {"rule_name": str(alert.get("rule_name", ""))})
                self._audit(
                    "compute.alert.delivery_failed",
                    payload,
                    request_id=request_id,
                    result="failed",
                    reason_codes=(str(alert.get("rule_name", "")),),
                )
            deliveries.append(delivery)
        failed = tuple(item for item in deliveries if str(item.get("status", "")) == "failed")
        self._audit(
            "compute.alert.routing.attempted",
            payload,
            request_id=request_id,
            result="failed" if failed else "routed",
            reason_codes=("alert_delivery_failed",) if failed else (),
        )
        return {
            "ok": not failed,
            "alerts": evaluation,
            "routing_enabled": True,
            "deliveries": tuple(deliveries),
            "delivery_count": len(deliveries),
            "failed_count": len(failed),
        }

    def acknowledge_alert(self, rule_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not rule_name:
            raise ValueError("rule_name is required")
        request_id = _request_id(payload)
        record = {
            "acknowledgement_id": deterministic_id("alert_acknowledgement", {"rule_name": rule_name, "request_id": request_id}),
            "rule_name": rule_name,
            "acknowledged_by": str(payload.get("acknowledged_by", payload.get("actor_id", "api"))),
            "status": "acknowledged",
            "created_at": utc_now_iso(),
            "request_id": request_id,
        }
        self.store.put_record("alert_acknowledgement", str(record["acknowledgement_id"]), record, status="acknowledged", request_id=request_id)
        self._audit("compute.alert.acknowledged", payload, request_id=request_id, result="acknowledged", reason_codes=(rule_name,))
        return {"ok": True, "acknowledgement": record}

    def track_error(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        error_code = str(payload.get("error_code", payload.get("code", ""))).strip()
        if not error_code:
            raise ValueError("error_code is required")
        message = str(payload.get("message", "")).strip()
        details = _safe_error_details(payload.get("details", {}))
        audit_payload = {"error_code": error_code, "message": message, "details": details, "request_id": request_id}
        if not self.config.error_tracking_enabled:
            return {"ok": False, "error": "error_tracking_disabled", "request_id": request_id}

        webhook_url = self.config.error_tracking_webhook_url.strip()
        if not webhook_url:
            self._audit(
                "compute.error.tracking_failed",
                audit_payload,
                request_id=request_id,
                result="failed",
                reason_codes=("error_tracking_webhook_unavailable",),
            )
            return {"ok": False, "error": "error_tracking_webhook_unavailable", "request_id": request_id}
        if not _alert_webhook_url_allowed(webhook_url):
            self._audit(
                "compute.error.tracking_failed",
                audit_payload,
                request_id=request_id,
                result="failed",
                reason_codes=("error_tracking_webhook_url_not_allowed",),
            )
            return {"ok": False, "error": "error_tracking_webhook_url_not_allowed", "request_id": request_id}

        record = _error_tracking_record(
            error_code,
            message,
            details,
            webhook_url=webhook_url,
            request_id=request_id,
        )
        envelope = _error_tracking_envelope(record)
        self.telemetry.increment("error_tracking_pending_total", {"error_code": error_code})
        if self.config.compute_market_mode == "test":
            record = {
                **record,
                "status": "dry_run_skipped",
                "delivery_attempted": False,
                "reason_codes": ("test_mode_no_external_webhook",),
                "updated_at": utc_now_iso(),
            }
        else:
            sent = _post_alert_webhook(
                webhook_url,
                envelope,
                secret=self.config.error_tracking_webhook_secret,
                timeout_ms=self.config.error_tracking_timeout_ms,
            )
            record = {**record, **sent, "delivery_attempted": True}

        status = str(record.get("status", ""))
        self.store.put_record(
            "error_tracking_event",
            str(record["event_id"]),
            record,
            status=status,
            request_id=request_id,
            idempotency_key=str(record["event_id"]),
        )
        if status == "delivered":
            self.telemetry.increment("error_tracking_sent_total", {"error_code": error_code})
        elif status == "failed":
            self.telemetry.increment("error_tracking_failed_total", {"error_code": error_code})
        self._audit(
            "compute.error.tracked",
            audit_payload,
            request_id=request_id,
            result=status or "failed",
            reason_codes=(error_code,),
        )
        return {
            "ok": status in {"delivered", "dry_run_skipped"},
            "event_id": str(record["event_id"]),
            "status": status,
            "request_id": request_id,
            "event": record,
        }

    def export_telemetry_otlp(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        request_id = _request_id(payload)
        if not self.config.telemetry_export_enabled:
            return {"ok": False, "error": "telemetry_export_disabled", "request_id": request_id}

        endpoint_url = self.config.otlp_endpoint_url.strip()
        if not endpoint_url:
            self._audit(
                "compute.telemetry.export_failed",
                {"request_id": request_id},
                request_id=request_id,
                result="failed",
                reason_codes=("otlp_endpoint_unavailable",),
            )
            return {"ok": False, "error": "otlp_endpoint_unavailable", "request_id": request_id}
        if not _alert_webhook_url_allowed(endpoint_url):
            self._audit(
                "compute.telemetry.export_failed",
                {"request_id": request_id},
                request_id=request_id,
                result="failed",
                reason_codes=("otlp_endpoint_url_not_allowed",),
            )
            return {"ok": False, "error": "otlp_endpoint_url_not_allowed", "request_id": request_id}

        snapshot = self.telemetry.snapshot(reset=False)
        metrics = snapshot.get("metrics", ())
        traces = snapshot.get("traces", ())
        metric_count = len(metrics) if isinstance(metrics, (list, tuple)) else 0
        trace_count = len(traces) if isinstance(traces, (list, tuple)) else 0
        export_id = deterministic_id(
            "otlp_export",
            {"request_id": request_id, "metric_count": metric_count, "trace_count": trace_count},
        )
        body = _otlp_export_body(snapshot, export_id=export_id, request_id=request_id)
        delivery = _otlp_export_record(
            export_id,
            endpoint_url=endpoint_url,
            metric_count=metric_count,
            trace_count=trace_count,
            request_id=request_id,
        )
        self.telemetry.increment("otlp_export_attempt_total")
        if self.config.compute_market_mode == "test":
            delivery = {
                **delivery,
                "status": "dry_run_skipped",
                "delivery_attempted": False,
                "reason_codes": ("test_mode_no_external_otlp",),
                "updated_at": utc_now_iso(),
            }
        else:
            sent = _post_otlp_collector(
                endpoint_url,
                body,
                headers=_otlp_headers(self.config.otlp_headers),
                timeout_ms=self.config.otlp_timeout_ms,
            )
            delivery = {**delivery, **sent, "delivery_attempted": True}

        status = str(delivery.get("status", ""))
        self.store.put_record(
            "otlp_export_delivery",
            export_id,
            delivery,
            status=status,
            request_id=request_id,
            idempotency_key=export_id,
        )
        if status == "delivered":
            self.telemetry.increment("otlp_export_sent_total")
        elif status == "failed":
            self.telemetry.increment("otlp_export_failed_total")
        self._audit(
            "compute.telemetry.exported",
            {"request_id": request_id, "metric_count": delivery["metric_count"], "trace_count": delivery["trace_count"]},
            request_id=request_id,
            result=status or "failed",
            reason_codes=tuple(delivery.get("reason_codes", ())),
        )
        if payload.get("reset") and status in {"delivered", "dry_run_skipped"}:
            self.telemetry.reset()
        return {"ok": status in {"delivered", "dry_run_skipped"}, "export_id": export_id, "status": status, "delivery": delivery}

    def admin_storage_diagnostics(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        _ = payload
        migration_status = self.store.migration_status()
        migration_history = self.store.migration_history()
        schema = self.store.schema_verification()
        production = self.store.production_readiness_check()
        audit_chain = self.store.verify_audit_chain().as_record()
        return {
            "ok": bool(schema.get("ok")) and bool(migration_status.get("current")) and bool(production.get("production_ready")) and bool(audit_chain.get("ok")),
            "storage": self.store.storage_status(),
            "migration_status": migration_status,
            "migration_history": migration_history,
            "schema_verification": schema,
            "production_readiness": production,
            "audit_chain": audit_chain,
            "schema_hash": schema_hash(),
        }

    def admin_redis_diagnostics(self, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        request_id = _request_id(payload or {})
        limiter_status = self.rate_limiter.get_status("diagnostics")
        circuit_status = self.circuit_breaker.get_state("diagnostics")
        rate_probe = _redis_rate_limit_probe(self.rate_limiter, request_id=request_id, redis_prefix=self.config.redis_prefix)
        circuit_probe = _redis_circuit_probe(self.circuit_breaker, request_id=request_id, redis_prefix=self.config.redis_prefix)
        expected_redis = (
            self.config.rate_limit_backend.strip().lower() == "redis"
            or self.config.circuit_breaker_backend.strip().lower() == "redis"
        )
        probes_ok = (
            (not expected_redis or bool(rate_probe.get("ok")))
            and (not expected_redis or bool(circuit_probe.get("ok")))
        )
        return {
            "ok": probes_ok,
            "expected_redis": expected_redis,
            "rate_limiter": limiter_status,
            "circuit_breaker": circuit_status,
            "rate_limit_probe": rate_probe,
            "circuit_breaker_probe": circuit_probe,
            "rate_limit_fail_closed": self.config.rate_limit_fail_closed,
            "circuit_breaker_fail_closed": self.config.circuit_breaker_fail_closed,
        }

    def _rate_limit_response(
        self,
        payload: Mapping[str, Any],
        endpoint: str,
        *,
        request_id: str,
        provider_id: str = "",
        route_id: str = "",
        cost: int = 1,
    ) -> Mapping[str, Any] | None:
        if not self.config.rate_limits_enabled:
            return None
        decision = self.rate_limiter.check_limit(
            str(payload.get("actor_id", payload.get("user_id", "local"))),
            endpoint,
            cost=cost,
            agent_id=str(payload.get("agent_id", "")),
            workspace_id=str(payload.get("workspace_id", payload.get("tenant_id", ""))),
            provider_id=provider_id or str(payload.get("provider_id", "")),
            route_id=route_id or str(payload.get("route_id", "")),
            api_key=str(payload.get("api_key_id", "")),
        )
        if decision.ok:
            self.rate_limiter.record_success(decision.key)
            return None
        self.rate_limiter.record_rejection(decision.key, "rate_limited")
        self.telemetry.increment("compute_policy_denials_total", {"reason": "rate_limited", "endpoint": endpoint})
        self._audit(
            "compute.rate_limited",
            payload,
            request_id=request_id,
            result="rejected",
            reason_codes=("rate_limited",),
            provider_id=provider_id,
            route_id=route_id,
        )
        error = compute_error(
            "rate_limit.exceeded",
            "Compute Market rate limit exceeded.",
            details=decision.as_record(),
            request_id=request_id,
            retryable=True,
        )
        return {"ok": False, "error": error.as_record(), "request_id": request_id}

    def _payload_with_circuit_denials(self, payload: Mapping[str, Any], *, request_id: str) -> Mapping[str, Any]:
        open_providers = self._open_circuit_provider_ids()
        if not open_providers:
            return payload
        policy = dict(payload.get("policy", {})) if isinstance(payload.get("policy"), Mapping) else {}
        denied = tuple(dict.fromkeys((*_tuple(policy.get("denied_providers", ())), *open_providers)))
        policy["denied_providers"] = denied
        for provider_id in open_providers:
            self.telemetry.increment("provider_circuit_open_total", {"provider_id": provider_id})
        self.telemetry.increment("compute_fallback_used_total", {"reason": "circuit_open"})
        self._audit(
            "compute.provider.circuit_open",
            payload,
            request_id=request_id,
            result="skipped",
            reason_codes=("circuit_open",),
        )
        return {**dict(payload), "policy": policy, "circuit_open_providers": open_providers}

    def _provider_callback_ip_rejection(
        self,
        payload: Mapping[str, Any],
        *,
        request_id: str,
        job_id: str,
        provider_id: str,
        route_id: str,
        callback_action: str,
        audit_action: str,
    ) -> Mapping[str, Any] | None:
        client_ip = str(payload.get("_flow_memory_client_ip", ""))
        if _provider_callback_ip_allowed(client_ip, self.config.provider_callback_ip_allowlist):
            return None
        error_code = "provider_callback.ip_not_allowed"
        error = compute_error(
            error_code,
            "Provider callback source IP is not allowlisted.",
            details={
                "job_id": job_id,
                "provider_id": provider_id,
                "route_id": route_id,
                "callback_action": callback_action,
                "client_ip": client_ip,
                "allowlist_configured": bool(self.config.provider_callback_ip_allowlist),
            },
            request_id=request_id,
        )
        self._audit(
            audit_action,
            payload,
            request_id=request_id,
            result="rejected",
            reason_codes=("provider_callback_ip_not_allowed",),
            provider_id=provider_id,
            route_id=route_id,
        )
        self.telemetry.increment(
            "compute_provider_callback_rejected_total",
            {"provider_id": provider_id, "route_id": route_id, "callback_action": callback_action, "reason": error_code},
        )
        return {"ok": False, "error": error.as_record()}

    def _open_circuit_provider_ids(self) -> tuple[str, ...]:
        open_ids = getattr(self.circuit_breaker, "open_provider_ids", None)
        if callable(open_ids):
            return tuple(str(provider_id) for provider_id in open_ids())
        return ()

    def _persist_price_snapshot(self, quote: Mapping[str, Any], *, request_id: str = "") -> None:
        if quote.get("unit_price") in (None, ""):
            return
        snapshot = _price_snapshot_from_quote(quote).as_record()
        self.store.put_record(
            "compute_price_snapshot",
            str(snapshot["price_snapshot_id"]),
            snapshot,
            tenant_id=str(snapshot.get("tenant_id", "")),
            workspace_id=str(snapshot.get("workspace_id", "")),
            provider_id=str(snapshot.get("provider_id", "")),
            route_id=str(snapshot.get("route_id", "")),
            task_type=str(snapshot.get("unit_type", "")),
            task_hash=str(snapshot.get("task_hash", "")),
            request_id=request_id,
        )

    def _price_snapshots(self, payload: Mapping[str, Any] | None = None) -> tuple[Mapping[str, Any], ...]:
        filters = _price_filters(payload or {})
        return self._all_records("compute_price_snapshot", filters=filters)

    def _price_context(self, compute_plan: Mapping[str, Any], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        quote = compute_plan.get("normalized_quote", {}) if isinstance(compute_plan.get("normalized_quote"), Mapping) else {}
        filters = _price_filters({**dict(payload), **_quote_price_filter(quote)})
        snapshots = self._price_snapshots(filters)
        median = _median_price_for_snapshot(quote, snapshots)
        unit_price = _optional_price(quote.get("unit_price"))
        ratio = _ratio(unit_price, median)
        return {
            "provider_id": str(quote.get("provider_id", "")),
            "route_id": str(quote.get("route_id", "")),
            "unit_type": str(quote.get("unit_type", "")),
            "unit_price": unit_price,
            "median_unit_price": median,
            "ratio_to_median": ratio,
            "sample_count": len(snapshots),
            "price_above_history": ratio >= 3.0,
            "capacity_available": bool(quote.get("capacity_available", False)),
            "quote_fresh": not bool(quote.get("stale", False) or quote.get("expired", False)),
        }
    def _persist_plan(self, plan: Mapping[str, Any]) -> None:
        profile = plan.get("profile", {}) if isinstance(plan.get("profile"), Mapping) else {}
        decision = plan.get("route_decision", {}) if isinstance(plan.get("route_decision"), Mapping) else {}
        selected_route = plan.get("selected_route", {}) if isinstance(plan.get("selected_route"), Mapping) else {}
        quote = plan.get("normalized_quote", {}) if isinstance(plan.get("normalized_quote"), Mapping) else {}
        payment_plan = plan.get("payment_plan", {}) if isinstance(plan.get("payment_plan"), Mapping) else {}
        settlement = plan.get("settlement_intent", {}) if isinstance(plan.get("settlement_intent"), Mapping) else {}
        memory = plan.get("economic_memory_preview", {}) if isinstance(plan.get("economic_memory_preview"), Mapping) else {}
        request_id = str(plan.get("request_id", ""))
        idempotency_key = str(plan.get("idempotency_key", ""))
        if profile:
            self.store.put_record("task_economic_profile", str(profile.get("task_id", deterministic_id("profile", profile))), profile, agent_id=str(profile.get("agent_id", "")), goal_id=str(profile.get("goal_id", "")), task_type=str(profile.get("task_type", "")), task_hash=str(profile.get("task_hash", "")), request_id=request_id)
        if quote:
            self.store.put_record("compute_quote", str(quote.get("quote_id", deterministic_id("quote", quote))), quote, provider_id=str(quote.get("provider_id", "")), route_id=str(quote.get("route_id", "")), status=str(quote.get("status", "")), expires_at=str(quote.get("expires_at", "")), request_id=request_id)
            self._persist_price_snapshot(quote, request_id=request_id)
        if decision:
            for candidate_quote in tuple(decision.get("normalized_quotes", ())):
                if isinstance(candidate_quote, Mapping):
                    self._persist_price_snapshot(candidate_quote, request_id=request_id)
        if payment_plan:
            self.store.put_record("payment_plan", str(payment_plan.get("payment_plan_id", deterministic_id("payment_plan", payment_plan))), payment_plan, request_id=request_id, idempotency_key=idempotency_key)
        if settlement:
            self.store.put_record("settlement_intent", str(settlement.get("settlement_intent_id", deterministic_id("settlement", settlement))), settlement, provider_id=str(settlement.get("provider_id", "")), route_id=str(settlement.get("route_id", "")), request_id=request_id, idempotency_key=idempotency_key, status=str(settlement.get("status", "")))
        if decision:
            stored_decision = {**decision, "compute_plan": dict(plan)}
            self.store.put_record("route_decision", str(decision.get("decision_id", plan.get("decision_id", deterministic_id("decision", decision)))), stored_decision, agent_id=str(profile.get("agent_id", "")), goal_id=str(profile.get("goal_id", "")), provider_id=str(selected_route.get("provider_id", "")), route_id=str(selected_route.get("route_id", "")), task_hash=str(profile.get("task_hash", "")), status=str(decision.get("policy_result", "")), idempotency_key=idempotency_key, request_id=request_id)
        if memory and self.config.economic_memory_writes_enabled:
            self.store.put_record("economic_memory", str(memory.get("record_id", deterministic_id("economic_memory", memory))), memory, agent_id=str(memory.get("agent_id", "")), goal_id=str(memory.get("goal_id", "")), provider_id=str(memory.get("provider_id", "")), route_id=str(memory.get("route_id", "")), task_type=str(memory.get("task_type", "")), task_hash=str(memory.get("task_hash", "")), status=str(memory.get("policy_result", "")), idempotency_key=idempotency_key, request_id=request_id)
            self.telemetry.increment("compute_economic_memory_writes_total")

    def _all_records(
        self,
        record_type: str,
        *,
        filters: Mapping[str, Any] | None = None,
        limit: int = 500,
        include_archived: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        records: list[Mapping[str, Any]] = []
        cursor = ""
        while True:
            page = self.store.list_records(
                record_type,
                filters=filters,
                limit=limit,
                cursor=cursor,
                include_archived=include_archived,
            )
            records.extend(page.records)
            if not page.next_cursor:
                break
            cursor = page.next_cursor
        return tuple(records)

    def _all_audit_events(self, *, limit: int = 500) -> tuple[Mapping[str, Any], ...]:
        records: list[Mapping[str, Any]] = []
        cursor = ""
        while True:
            page = self.store.list_records("audit_event", limit=limit, cursor=cursor, include_archived=True)
            records.extend(page.records)
            if not page.next_cursor:
                break
            cursor = page.next_cursor
        return tuple(records)

    def _audit(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        request_id: str = "",
        result: str,
        reason_codes: tuple[str, ...] = (),
        decision_id: str = "",
        policy_id: str = "",
        route_id: str = "",
        provider_id: str = "",
    ) -> str:
        audit_event = AuditEvent(
            audit_event_id=new_id("compute_audit"),
            request_id=request_id or str(payload.get("request_id", "")),
            actor_id=str(payload.get("actor_id", payload.get("user_id", "local"))),
            actor_type=str(payload.get("actor_type", "system")),
            tenant_id=str(payload.get("tenant_id", payload.get("workspace_id", ""))),
            workspace_id=str(payload.get("workspace_id", payload.get("tenant_id", ""))),
            agent_id=str(payload.get("agent_id", "")),
            goal_id=str(payload.get("goal_id", "")),
            action=action,
            resource_type="compute_market",
            resource_id=decision_id or route_id or provider_id,
            decision_id=decision_id,
            policy_id=policy_id,
            route_id=route_id,
            provider_id=provider_id,
            result=result,
            reason_codes=reason_codes,
            dry_run_only=True,
            funds_moved=False,
            broadcast_allowed=False,
            private_key_required=False,
            created_at=utc_now_iso(),
            user_agent=str(payload.get("user_agent", "")),
        )
        record = self.store.append_audit_event(audit_event.as_record())
        return str(record["audit_event_id"])

    def _audit_writable(self) -> bool:
        try:
            audit_id = self._audit("compute.audit.probe", {}, result="ok")
            self.store.delete_record("audit_event", audit_id)
            return True
        except Exception:
            return False


_default_service: ComputeMarketService | None = None


def default_service() -> ComputeMarketService:
    global _default_service
    if _default_service is None:
        _default_service = ComputeMarketService()
    return _default_service


def reset_default_service(service: ComputeMarketService | None = None) -> None:
    global _default_service
    _default_service = service


def _checkpoint_interval_due(last_checkpoint: Mapping[str, Any] | None, interval_seconds: int) -> bool:
    if not last_checkpoint:
        return False
    created_at = str(last_checkpoint.get("created_at", "")).strip()
    if not created_at:
        return False
    try:
        last_created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    elapsed = datetime.now(timezone.utc) - last_created.astimezone(timezone.utc)
    return elapsed.total_seconds() >= max(1, interval_seconds)

_READINESS_FAILURE_METRICS = {
    "database_unavailable": "postgres_unavailable_total",
    "rate_limiter_unavailable": "redis_unavailable_total",
    "circuit_breaker_unavailable": "redis_unavailable_total",
    "external_provider_allowlist_missing": "external_provider_allowlist_missing_total",
    "unsafe_live_settlement_config": "unexpected_live_settlement_config_total",
    "audit_immutable_retention_not_configured": "audit_chain_verify_fail_total",
    "audit_immutable_storage_unavailable": "audit_chain_verify_fail_total",
    "alert_webhook_unavailable": "alert_delivery_failed_total",
    "alert_webhook_url_not_allowed": "alert_delivery_failed_total",
    "error_tracking_webhook_unavailable": "error_tracking_failed_total",
    "error_tracking_webhook_url_not_allowed": "error_tracking_failed_total",
    "otlp_endpoint_unavailable": "otlp_export_failed_total",
    "otlp_endpoint_url_not_allowed": "otlp_export_failed_total",
}


def _record_readiness_failure_metrics(
    telemetry: ComputeMarketTelemetry,
    failures: tuple[str, ...],
) -> None:
    for failure in failures:
        metric_name = _READINESS_FAILURE_METRICS.get(failure)
        if metric_name:
            telemetry.increment(metric_name)


def _audit_replay_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chain_id": str(event.get("chain_id", "")),
        "sequence_number": int(event.get("sequence_number", 0) or 0),
        "audit_event_id": str(event.get("audit_event_id", "")),
        "action": str(event.get("action", "")),
        "result": str(event.get("result", "")),
        "actor_id": str(event.get("actor_id", "")),
        "resource_id": str(event.get("resource_id", "")),
        "event_hash": str(event.get("event_hash", "")),
        "previous_hash": str(event.get("previous_hash", "")),
        "created_at": str(event.get("created_at", "")),
    }


def _audit_replay_summary(events: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    actions: dict[str, int] = {}
    results: dict[str, int] = {}
    actors: dict[str, int] = {}
    for event in events:
        action = str(event.get("action", ""))
        result = str(event.get("result", ""))
        actor = str(event.get("actor_id", ""))
        if action:
            actions[action] = actions.get(action, 0) + 1
        if result:
            results[result] = results.get(result, 0) + 1
        if actor:
            actors[actor] = actors.get(actor, 0) + 1
    return {
        "event_count": len(events),
        "actions": tuple({"action": key, "count": value} for key, value in sorted(actions.items())),
        "results": tuple({"result": key, "count": value} for key, value in sorted(results.items())),
        "actors": tuple({"actor_id": key, "count": value} for key, value in sorted(actors.items())),
    }

def _request_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("request_id") or new_id("request"))


def _enrich_provider(provider: ComputeProvider) -> ComputeProvider:
    unit_types = tuple(dict.fromkeys(unit for capability in provider.capabilities for unit in capability.unit_types))
    networks = tuple(dict.fromkeys(network for capability in provider.capabilities for network in capability.networks)) or (provider.network,)
    assets = tuple(dict.fromkeys(asset for capability in provider.capabilities for asset in capability.payment_assets)) or (provider.payment_asset,)
    return replace(
        provider,
        status=provider.status or "active",
        supported_unit_types=provider.supported_unit_types or unit_types,
        supported_networks=provider.supported_networks or networks,
        supported_assets=provider.supported_assets or assets,
        average_latency_ms=provider.average_latency_ms or 750,
        supported_settlement_modes=provider.supported_settlement_modes or ("generic_dry_run",),
        verified=provider.verified or provider.provider_type == "local",
    )

_CREDENTIAL_VALUE_KEYS = frozenset({"api_key", "token", "access_token", "refresh_token", "password", "secret", "secret_key", "private_key"})
_ERROR_DETAIL_KEY_FRAGMENTS = ("api_key", "token", "password", "secret", "private_key", "seed", "mnemonic")


def _assert_no_inline_credentials(payload: Mapping[str, Any]) -> None:
    for key, value in _walk(payload):
        if key in _CREDENTIAL_VALUE_KEYS and value not in (None, ""):
            raise ValueError("provider credentials must be supplied as external secret references, not inline values")


def _provider_admin_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if str(key) != "credentials" and str(key) not in _CREDENTIAL_VALUE_KEYS
    }

def _provider_class_from_payload(provider_type: str, payload: Mapping[str, Any]) -> str:
    provider_class = str(payload.get("provider_class", "")).strip()
    if not provider_class:
        provider_class = {
            "gpu": ProviderClass.GPU_CLUSTER.value,
            "llm": ProviderClass.FOUNDATIONAL_MODEL.value,
            "batch": ProviderClass.BATCH_INFERENCE.value,
            "reserved_capacity": ProviderClass.RESERVED_CAPACITY_POOL.value,
            "marketplace": ProviderClass.MARKETPLACE_POOL.value,
            "agent_runtime": ProviderClass.AGENT_RUNTIME.value,
            "reasoning": ProviderClass.REASONING_MODEL.value,
        }.get(provider_type, ProviderClass.MARKETPLACE_POOL.value)
    allowed = {item.value for item in ProviderClass}
    if provider_class not in allowed:
        raise ValueError(f"unsupported provider_class: {provider_class}")
    return provider_class


def _provider_application(payload: Mapping[str, Any], *, request_id: str) -> dict[str, Any]:
    provider_id = str(payload.get("provider_id") or deterministic_id("provider", payload))
    provider_name = str(payload.get("provider_name", "")).strip()
    provider_type = str(payload.get("provider_type", "")).strip()
    provider_class = _provider_class_from_payload(provider_type, payload)
    quote_endpoint = str(payload.get("quote_endpoint", "")).strip()
    health_endpoint = str(payload.get("health_endpoint", "")).strip()
    execution_endpoint = str(payload.get("execution_endpoint", "")).strip()
    supported_unit_types = _tuple(payload.get("supported_unit_types", ()))
    supported_assets = _tuple(payload.get("supported_assets", ()))
    supported_networks = _tuple(payload.get("supported_networks", ()))
    missing = tuple(
        name
        for name, value in {
            "provider_name": provider_name,
            "provider_type": provider_type,
            "quote_endpoint": quote_endpoint,
            "health_endpoint": health_endpoint,
            "supported_unit_types": supported_unit_types,
            "supported_assets": supported_assets,
            "supported_networks": supported_networks,
        }.items()
        if not value
    )
    if missing:
        raise ValueError(f"provider application missing required fields: {', '.join(missing)}")
    if not quote_endpoint.startswith("https://") or not health_endpoint.startswith("https://"):
        raise ValueError("provider quote_endpoint and health_endpoint must be https:// URLs")
    if execution_endpoint and not execution_endpoint.startswith("https://"):
        raise ValueError("provider execution_endpoint must be an https:// URL")
    now = utc_now_iso()
    credential_bindings = _provider_credential_bindings(payload)
    return {
        "application_id": str(payload.get("application_id") or deterministic_id("provider_application", {"provider_id": provider_id, "request_id": request_id})),
        "provider_id": provider_id,
        "provider_name": provider_name,
        "provider_type": provider_type,
        "provider_class": provider_class,
        "status": "pending",
        "verified": False,
        "supported_unit_types": supported_unit_types,
        "supported_assets": supported_assets,
        "supported_networks": supported_networks,
        "quote_endpoint": quote_endpoint,
        "health_endpoint": health_endpoint,
        "execution_endpoint": execution_endpoint,
        "public_key": str(payload.get("public_key", "")),
        "sla": dict(payload.get("sla", {})) if isinstance(payload.get("sla"), Mapping) else {},
        "credential_bindings": credential_bindings,
        "tenant_id": str(payload.get("tenant_id", "")),
        "workspace_id": str(payload.get("workspace_id", "")),
        "configured_by": str(payload.get("configured_by", "provider-admin")),
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _provider_secret_reference(payload: Mapping[str, Any], *, provider_id: str, request_id: str) -> dict[str, Any]:
    credentials = payload.get("credentials", {})
    if not isinstance(credentials, Mapping):
        return {}
    secret_ref = str(credentials.get("secret_ref") or credentials.get("vault_path") or credentials.get("env_var") or "")
    if not secret_ref:
        return {}
    bindings = _provider_credential_bindings(payload)
    return {
        "secret_ref_id": deterministic_id("provider_secret_ref", {"provider_id": provider_id, "secret_ref": secret_ref}),
        "provider_id": provider_id,
        "secret_ref": secret_ref,
        "secret_ref_hash": content_hash({"provider_id": provider_id, "secret_ref": secret_ref}),
        "storage": "external_secret_manager",
        "credential_bindings": bindings,
        "tenant_id": str(payload.get("tenant_id", "")),
        "workspace_id": str(payload.get("workspace_id", "")),
        "created_at": utc_now_iso(),
        "request_id": request_id,
    }


_PROVIDER_CREDENTIAL_BINDING_KEYS = frozenset(
    {
        "auth_header_name",
        "auth_header_value_env",
        "execution_auth_header_name",
        "execution_auth_header_value_env",
        "outbound_signing_key_id",
        "outbound_signing_key_env",
        "execution_outbound_signing_key_id",
        "execution_outbound_signing_key_env",
        "outbound_signing_required",
        "execution_outbound_signing_required",
    }
)


def _provider_credential_bindings(payload: Mapping[str, Any]) -> dict[str, Any]:
    credentials = payload.get("credentials", {})
    if not isinstance(credentials, Mapping):
        return {}
    secret_ref = str(credentials.get("secret_ref") or credentials.get("vault_path") or credentials.get("env_var") or "").strip()
    env_var = _env_var_from_secret_ref(secret_ref)
    auth_header_name = str(credentials.get("auth_header_name", credentials.get("header_name", ""))).strip()
    execution_auth_header_name = str(credentials.get("execution_auth_header_name", auth_header_name)).strip()
    bindings: dict[str, Any] = {}
    if env_var:
        bindings["auth_header_value_env"] = env_var
        bindings["execution_auth_header_value_env"] = str(credentials.get("execution_env_var", env_var)).strip() or env_var
    if auth_header_name:
        bindings["auth_header_name"] = auth_header_name
    if execution_auth_header_name:
        bindings["execution_auth_header_name"] = execution_auth_header_name
    for key in (
        "outbound_signing_key_id",
        "outbound_signing_key_env",
        "execution_outbound_signing_key_id",
        "execution_outbound_signing_key_env",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            bindings[key] = value
    for key in ("outbound_signing_required", "execution_outbound_signing_required"):
        if key in credentials:
            bindings[key] = bool(credentials.get(key))
    return bindings


def _env_var_from_secret_ref(secret_ref: str) -> str:
    value = secret_ref.strip()
    if not value:
        return ""
    for prefix in ("render/env/", "env://", "env:"):
        if value.startswith(prefix):
            return value[len(prefix):].strip()
    if "/" not in value and ":" not in value:
        return value
    return ""


def _provider_with_credential_bindings(provider: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    bindings = _provider_credential_bindings(payload)
    updated = dict(provider)
    if not bindings:
        return updated
    metadata = dict(updated.get("metadata", {})) if isinstance(updated.get("metadata"), Mapping) else {}
    metadata.update(bindings)
    updated["metadata"] = metadata
    updated["credential_bindings"] = {key: bindings[key] for key in sorted(bindings)}
    return updated


def _provider_from_application(application: Mapping[str, Any]) -> dict[str, Any]:
    now = utc_now_iso()
    public_key = str(application.get("public_key", ""))
    metadata = {
        "quote_endpoint": str(application.get("quote_endpoint", "")),
        "health_endpoint": str(application.get("health_endpoint", "")),
        "execution_endpoint": str(application.get("execution_endpoint", "")),
        "sla": dict(application.get("sla", {})) if isinstance(application.get("sla"), Mapping) else {},
        "provider_class": str(application.get("provider_class", "")),
    }
    credential_bindings = application.get("credential_bindings", {})
    if isinstance(credential_bindings, Mapping):
        metadata.update({key: credential_bindings[key] for key in _PROVIDER_CREDENTIAL_BINDING_KEYS if key in credential_bindings})
    if public_key:
        metadata["public_key"] = public_key
    return {
        "provider_id": str(application["provider_id"]),
        "provider_name": str(application["provider_name"]),
        "provider_type": str(application["provider_type"]),
        "provider_class": str(application.get("provider_class", ProviderClass.MARKETPLACE_POOL.value)),
        "market_type": "marketplace",
        "network": str(_tuple(application.get("supported_networks", ("offchain",)))[0]),
        "payment_asset": str(_tuple(application.get("supported_assets", ("USD",)))[0]),
        "capabilities": (),
        "reliability_score": 1.0,
        "dry_run_only": True,
        "capacity_available": True,
        "metadata": metadata,
        "tenant_id": str(application.get("tenant_id", "")),
        "workspace_id": str(application.get("workspace_id", "")),
        "public_key": public_key,
        "created_at": str(application.get("created_at", now)),
        "updated_at": now,
        "status": "active",
        "supported_unit_types": _tuple(application.get("supported_unit_types", ())),
        "supported_networks": _tuple(application.get("supported_networks", ())),
        "supported_assets": _tuple(application.get("supported_assets", ())),
        "supported_settlement_modes": ("generic_dry_run",),
        "average_latency_ms": int((dict(application.get("sla", {})) if isinstance(application.get("sla"), Mapping) else {}).get("max_latency_ms", 1000) or 1000),
        "quote_ttl_seconds": 300,
        "health_check_url": str(application.get("health_endpoint", "")),
        "configured_by": str(application.get("configured_by", "provider-admin")),
        "verified": True,
        "config_version": 1,
    }


def _provider_routes_from_application(
    application: Mapping[str, Any],
    provider: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    provider_id = str(application["provider_id"])
    provider_type = str(application["provider_type"])
    provider_name = str(application["provider_name"])
    provider_class = str(provider.get("provider_class", application.get("provider_class", "")))
    supported_assets = _tuple(application.get("supported_assets", ())) or ("USD",)
    supported_networks = _tuple(application.get("supported_networks", ())) or ("offchain",)
    unit_types = _tuple(application.get("supported_unit_types", ()))
    now = utc_now_iso()
    quote_ttl_seconds = int(provider.get("quote_ttl_seconds", 300) or 300)
    average_latency_ms = int(provider.get("average_latency_ms", 1000) or 1000)
    routes: list[dict[str, Any]] = []
    for unit_type in unit_types:
        route_id = deterministic_id(
            "market_provider_route",
            {
                "provider_id": provider_id,
                "unit_type": unit_type,
                "tenant_id": str(application.get("tenant_id", "")),
                "workspace_id": str(application.get("workspace_id", "")),
            },
        )
        route = {
            "route_id": route_id,
            "provider_id": provider_id,
            "provider_or_route": provider_name,
            "provider_type": provider_type,
            "market_type": "marketplace",
            "network": str(supported_networks[0]),
            "payment_asset": str(supported_assets[0]),
            "unit_type": unit_type,
            "unit_price": None,
            "estimated_units": 0.0,
            "estimated_total_cost": None,
            "estimated_latency_ms": average_latency_ms,
            "capacity_available": True,
            "reservation_required": unit_type in {"gpu_hour", "reserved_capacity_slot"},
            "settlement_mode": "generic_dry_run",
            "settlement_modes": ("generic_dry_run",),
            "dry_run_only": True,
            "fallback_route": False,
            "quote_ttl_seconds": quote_ttl_seconds,
            "confidence": 1.0,
            "reliability_score": float(provider.get("reliability_score", 1.0) or 1.0),
            "metadata": {
                "provider_verified": True,
                "provider_class": provider_class,
                "quote_endpoint": str(application.get("quote_endpoint", "")),
                "health_endpoint": str(application.get("health_endpoint", "")),
                "execution_endpoint": str(application.get("execution_endpoint", "")),
            },
            "created_at": now,
            "updated_at": now,
            "tenant_id": str(application.get("tenant_id", "")),
            "workspace_id": str(application.get("workspace_id", "")),
            "route_type": "provider_quote",
            "pricing_model": "external_quote",
            "supported_assets": supported_assets,
            "supported_networks": supported_networks,
            "fallback_priority": 100,
            "enabled": True,
            "verified_provider_required": True,
            "provider_class": provider_class,
            "config_version": 1,
        }
        routes.append(route)
    return tuple(routes)


def _provider_public_key(payload: Mapping[str, Any], provider_id: str, service: ComputeMarketService) -> str | Mapping[str, Any]:
    for key in ("provider_public_key", "public_key"):
        value = payload.get(key)
        if isinstance(value, Mapping) or str(value or ""):
            return value  # type: ignore[return-value]
    provider = service.store.get_record("compute_provider", provider_id) or {}
    provider_key = provider.get("public_key") if isinstance(provider, Mapping) else ""
    if provider_key:
        return str(provider_key)
    metadata = provider.get("metadata", {}) if isinstance(provider, Mapping) else {}
    if isinstance(metadata, Mapping) and metadata.get("public_key"):
        return str(metadata["public_key"])
    try:
        application = service._latest_provider_application(provider_id)
    except KeyError:
        return ""
    if application.get("public_key"):
        return str(application["public_key"])
    return ""


def _provider_receipt_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt = payload.get("receipt", {})
    if isinstance(receipt, Mapping):
        return {str(key): value for key, value in receipt.items() if str(key) not in {"signature", "verification"}}
    return {str(key): value for key, value in payload.items() if str(key) not in {"signature", "verification"}}


def _provider_callback_ip_allowed(client_ip: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    candidate_ip = client_ip.strip()
    if not candidate_ip:
        return False
    try:
        parsed_ip = ipaddress.ip_address(candidate_ip)
    except ValueError:
        return False
    for item in allowlist:
        allowed = item.strip()
        if not allowed:
            continue
        try:
            if "/" in allowed:
                if parsed_ip in ipaddress.ip_network(allowed, strict=False):
                    return True
            elif parsed_ip == ipaddress.ip_address(allowed):
                return True
        except ValueError:
            if candidate_ip == allowed:
                return True
    return False


class _ProviderHealthNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _provider_health_endpoint(provider: Mapping[str, Any]) -> str:
    for key in ("health_endpoint", "health_check_url"):
        value = str(provider.get(key, "")).strip()
        if value:
            return value
    metadata = provider.get("metadata", {})
    if isinstance(metadata, Mapping):
        for key in ("health_endpoint", "health_check_url"):
            value = str(metadata.get(key, "")).strip()
            if value:
                return value
    return ""


def _provider_health_endpoint_block_reason(endpoint: str, config: ComputeMarketConfig) -> str:
    if not endpoint:
        return "missing"
    parsed = urllib.parse.urlparse(endpoint)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return "unsupported_scheme"
    if scheme == "http" and config.compute_market_mode != "test":
        return "insecure_scheme"
    if not parsed.hostname:
        return "missing_host"
    if parsed.username or parsed.password:
        return "userinfo_disallowed"
    if not _provider_health_host_allowed(parsed.hostname, config.external_provider_allowlist):
        return "host_not_allowlisted"
    if config.compute_market_mode != "test" and _provider_health_private_or_local_host(parsed.hostname):
        return "private_network_disallowed"
    return ""


def _provider_health_host_allowed(host: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    normalized_host = host.strip().strip("[]").lower().rstrip(".")
    for item in allowlist:
        raw = item.strip()
        if not raw:
            continue
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"//{raw}")
        candidate = (parsed.hostname or raw).strip().strip("[]").lower().rstrip(".")
        if candidate == normalized_host:
            return True
    return False


def _provider_health_private_or_local_host(host: str) -> bool:
    normalized_host = host.strip().strip("[]").lower().rstrip(".")
    if normalized_host in {"localhost", "ip6-localhost", "ip6-loopback"} or normalized_host.endswith(".localhost"):
        return True
    try:
        parsed_ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        return False
    return (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
        or parsed_ip.is_multicast
    )


def _disabled_provider_health_probe(provider: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "healthy": True,
        "status": "disabled",
        "latency_ms": int(provider.get("average_latency_ms", 0) or 0),
        "metadata": {"endpoint_checked": False},
    }


def _probe_provider_health_endpoint(provider: Mapping[str, Any], config: ComputeMarketConfig) -> Mapping[str, Any]:
    endpoint = _provider_health_endpoint(provider)
    block_reason = _provider_health_endpoint_block_reason(endpoint, config)
    if block_reason:
        return {
            "healthy": False,
            "status": "unhealthy",
            "error_code": f"provider_health_endpoint_{block_reason}",
            "message": "Provider health endpoint is not configured safely for health checks.",
            "metadata": {
                "endpoint": _redacted_url(endpoint) if endpoint else "",
                "endpoint_checked": False,
                "block_reason": block_reason,
            },
        }

    timeout_seconds = max(config.provider_timeout_ms / 1000.0, 0.001)
    request = urllib.request.Request(
        endpoint,
        headers={"accept": "application/json", "user-agent": "flow-memory-compute-market-health/1"},
        method="GET",
    )
    opener = urllib.request.build_opener(_ProviderHealthNoRedirect())
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", response.getcode()))
            body = response.read(8193)
    except urllib.error.HTTPError as exc:
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return {
            "healthy": False,
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error_code": "provider_health_http_error",
            "message": f"Provider health endpoint returned HTTP {exc.code}.",
            "metadata": {
                "endpoint": _redacted_url(endpoint),
                "endpoint_checked": True,
                "http_status": int(exc.code),
            },
        }
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return {
            "healthy": False,
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error_code": "provider_health_unreachable",
            "message": "Provider health endpoint could not be reached.",
            "metadata": {
                "endpoint": _redacted_url(endpoint),
                "endpoint_checked": True,
                "error_class": exc.__class__.__name__,
            },
        }

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    if len(body) > 8192:
        return {
            "healthy": False,
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error_code": "provider_health_response_too_large",
            "message": "Provider health endpoint response exceeded the health payload limit.",
            "metadata": {"endpoint": _redacted_url(endpoint), "endpoint_checked": True, "http_status": status_code},
        }
    try:
        decoded = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "healthy": False,
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error_code": "provider_health_invalid_json",
            "message": "Provider health endpoint did not return valid JSON.",
            "metadata": {"endpoint": _redacted_url(endpoint), "endpoint_checked": True, "http_status": status_code},
        }

    payload = decoded if isinstance(decoded, Mapping) else {}
    health_payload_raw = payload.get("health", payload)
    health_payload = health_payload_raw if isinstance(health_payload_raw, Mapping) else {}
    response_ok_raw = payload.get("ok", True)
    response_ok = response_ok_raw is not False and str(response_ok_raw).lower() not in {"0", "false", "no"}
    health_status = str(health_payload.get("status", "healthy" if response_ok else "unhealthy")).strip().lower()
    unhealthy_statuses = {"unhealthy", "down", "degraded", "error", "failed", "unavailable"}
    healthy = 200 <= status_code < 300 and response_ok and health_status not in unhealthy_statuses
    metadata: dict[str, Any] = {
        "endpoint": _redacted_url(endpoint),
        "endpoint_checked": True,
        "http_status": status_code,
        "response_ok": response_ok,
    }
    if "capacity_available" in health_payload:
        metadata["capacity_available"] = bool(health_payload.get("capacity_available"))
    return {
        "healthy": healthy,
        "status": "healthy" if healthy else "unhealthy",
        "latency_ms": latency_ms,
        "error_code": "" if healthy else "provider_health_unhealthy",
        "message": "" if healthy else f"Provider health endpoint reported status {health_status or status_code}.",
        "metadata": metadata,
    }


def _verify_provider_receipt(
    store: ComputeMarketStoreProtocol,
    job: Mapping[str, Any],
    payload: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    provider_id = str(job.get("provider_id", ""))
    provider = store.get_record("compute_provider", provider_id) or {}
    key = _provider_callback_signing_key(provider)
    if key is None:
        return {
            "ok": False,
            "error": {
                "error_code": "provider_receipt.signing_key_missing",
                "message": "Provider receipt callbacks require a configured callback signing key reference.",
                "provider_id": provider_id,
            },
        }
    signature = payload.get("signature", payload.get("verification", receipt.get("signature", receipt.get("verification", {}))))
    if not isinstance(signature, Mapping):
        return {
            "ok": False,
            "error": {
                "error_code": "provider_receipt.signature_missing",
                "message": "Provider receipt callback signature is required.",
                "provider_id": provider_id,
            },
        }
    receipt_id = str(receipt.get("receipt_id") or receipt.get("nonce") or "").strip()
    timestamp = str(receipt.get("timestamp") or receipt.get("created_at") or "").strip()
    if not receipt_id or not timestamp:
        return {
            "ok": False,
            "error": {
                "error_code": "provider_receipt.replay_fields_missing",
                "message": "Provider receipt callbacks require receipt_id or nonce plus timestamp.",
                "provider_id": provider_id,
            },
        }
    receipt_hash = content_hash(receipt)
    replay_guard = store.get_record("provider_receipt_replay_guard", receipt_id)
    if replay_guard is not None:
        return {
            "ok": False,
            "receipt_id": receipt_id,
            "receipt_hash": receipt_hash,
            "error": {
                "error_code": "provider_receipt.replay_detected",
                "message": "Provider receipt callback replay detected.",
                "provider_id": provider_id,
                "receipt_id": receipt_id,
            },
        }
    if not verify_payload(receipt, signature, key):
        return {
            "ok": False,
            "receipt_id": receipt_id,
            "receipt_hash": receipt_hash,
            "error": {
                "error_code": "provider_receipt.signature_invalid",
                "message": "Provider receipt callback signature is invalid.",
                "provider_id": provider_id,
                "receipt_id": receipt_id,
            },
        }
    return {"ok": True, "receipt_id": receipt_id, "receipt_hash": receipt_hash, "key_id": key.key_id}


def _provider_callback_signing_key(provider: Mapping[str, Any]) -> LocalKeyPair | None:
    metadata = provider.get("metadata", {})
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    key_id = str(
        provider.get("callback_signing_key_id")
        or metadata_map.get("callback_signing_key_id")
        or provider.get("outbound_signing_key_id")
        or metadata_map.get("outbound_signing_key_id")
        or ""
    ).strip()
    env_name = str(
        provider.get("callback_signing_key_env")
        or metadata_map.get("callback_signing_key_env")
        or provider.get("outbound_signing_key_env")
        or metadata_map.get("outbound_signing_key_env")
        or ""
    ).strip()
    secret = os.environ.get(env_name, "") if env_name else ""
    if not key_id or not secret:
        return None
    return LocalKeyPair(key_id=key_id, secret=secret)


def _record_provider_fraud_signal(
    store: ComputeMarketStoreProtocol,
    *,
    provider_id: str,
    route_id: str,
    quote_id: str,
    signal_type: str,
    severity: str,
    request_id: str,
    details: Mapping[str, Any],
    tenant_id: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    now = utc_now_iso()
    signal = {
        "signal_id": deterministic_id(
            "provider_fraud_signal",
            {
                "provider_id": provider_id,
                "route_id": route_id,
                "quote_id": quote_id,
                "signal_type": signal_type,
                "request_id": request_id,
            },
        ),
        "provider_id": provider_id,
        "route_id": route_id,
        "quote_id": quote_id,
        "signal_type": signal_type,
        "severity": severity,
        "status": "open",
        "details": dict(details),
        "dry_run_only": True,
        "funds_moved": False,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }
    store.put_record(
        "provider_fraud_signal",
        str(signal["signal_id"]),
        signal,
        provider_id=provider_id,
        route_id=route_id,
        status="open",
        request_id=request_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    return signal


def _cross_provider_quote_replay(
    store: ComputeMarketStoreProtocol,
    quote_id: str,
    quote_hash: str,
    provider_id: str,
    payload: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    access_payload = payload or {}
    tenant_id = _payload_tenant_id(access_payload)
    existing = _get_tenant_scoped_record(
        store,
        "quote_replay_guard",
        quote_id,
        _quote_replay_record_id(quote_id, tenant_id),
        access_payload,
    )
    if (
        existing
        and _tenant_can_access_record(access_payload, existing)
        and str(existing.get("provider_id", ""))
        and str(existing.get("provider_id", "")) != provider_id
    ):
        return existing
    for observed in store.list_records("quote_replay_guard", limit=1000).records:
        if not _tenant_can_access_record(access_payload, observed):
            continue
        observed_provider_id = str(observed.get("provider_id", ""))
        if observed_provider_id and observed_provider_id != provider_id and str(observed.get("quote_hash", "")) == quote_hash:
            return observed
    return {}


def _mark_expired_quotes_stale(
    store: ComputeMarketStoreProtocol,
    provider_id: str,
    route_id: str,
    *,
    request_id: str,
    tenant_id: str = "",
    workspace_id: str = "",
) -> int:
    now = utc_now_iso()
    marked = 0
    filters = {"provider_id": provider_id, "route_id": route_id}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    for quote in store.list_records("compute_quote", filters=filters, limit=500).records:
        expires_at = str(quote.get("expires_at", ""))
        if not expires_at or expires_at > now or str(quote.get("status", "")) != "valid":
            continue
        updated = {**dict(quote), "status": "stale", "stale": True, "updated_at": now}
        store.put_record(
            "compute_quote",
            str(updated.get("record_id", "") or _quote_record_id(str(updated["quote_id"]), tenant_id)),
            updated,
            provider_id=provider_id,
            route_id=route_id,
            status="stale",
            expires_at=expires_at,
            request_id=request_id,
            tenant_id=tenant_id or str(updated.get("tenant_id", "")),
            workspace_id=workspace_id or str(updated.get("workspace_id", "")),
        )
        marked += 1
    return marked


_VALIDATION_FRAUD_SIGNALS: dict[str, tuple[str, str]] = {
    "expired_quote": ("stale_quote_submission", "warning"),
    "stale_quote": ("stale_quote_submission", "warning"),
    "missing_signature": ("signature_failure", "critical"),
    "invalid_signature": ("signature_failure", "critical"),
    "policy_override_attempt": ("quote_policy_override", "critical"),
    "provider_id_mismatch": ("provider_spoofing_replay", "critical"),
}


def _fraud_signals_from_validation(
    store: ComputeMarketStoreProtocol,
    *,
    provider_id: str,
    route_id: str,
    quote_id: str,
    validation_errors: tuple[str, ...],
    request_id: str,
    tenant_id: str = "",
    workspace_id: str = "",
) -> tuple[Mapping[str, Any], ...]:
    signals: list[Mapping[str, Any]] = []
    for error_code in tuple(dict.fromkeys(validation_errors)):
        signal_definition = _VALIDATION_FRAUD_SIGNALS.get(error_code)
        if signal_definition is None:
            continue
        signal_type, severity = signal_definition
        signals.append(
            _record_provider_fraud_signal(
                store,
                provider_id=provider_id,
                route_id=route_id,
                quote_id=quote_id,
                signal_type=signal_type,
                severity=severity,
                request_id=request_id,
                details={"validation_error": error_code, "validation_errors": validation_errors},
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
        )
    return tuple(signals)


def _fraud_signal_counts(fraud_signals: tuple[Mapping[str, Any], ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in fraud_signals:
        signal_type = str(signal.get("signal_type", ""))
        if signal_type:
            counts[signal_type] = counts.get(signal_type, 0) + 1
    return counts


def _safe_non_negative_float(value: object) -> float:
    try:
        amount = float(str(value if value not in (None, "") else 0.0))
    except (TypeError, ValueError):
        return 0.0
    return amount if amount > 0.0 else 0.0


def _provider_sla_max_latency_ms(provider: Mapping[str, Any]) -> float:
    metadata = provider.get("metadata", {})
    sla: Mapping[str, Any] = {}
    if isinstance(metadata, Mapping):
        metadata_sla = metadata.get("sla", {})
        if isinstance(metadata_sla, Mapping):
            sla = metadata_sla
    provider_sla = provider.get("sla", {})
    if not sla and isinstance(provider_sla, Mapping):
        sla = provider_sla
    return _safe_non_negative_float(
        sla.get("max_latency_ms", provider.get("sla_max_latency_ms", provider.get("average_latency_ms", 0.0)))
    )


def _provider_reputation(
    provider_id: str,
    *,
    jobs: tuple[Mapping[str, Any], ...],
    quotes: tuple[Mapping[str, Any], ...],
    health: tuple[Mapping[str, Any], ...],
    fraud_signals: tuple[Mapping[str, Any], ...],
    refunds: tuple[Mapping[str, Any], ...] = (),
    provider: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    completed_jobs = tuple(job for job in jobs if str(job.get("status", "")) == "succeeded")
    completed = len(completed_jobs)
    failed = sum(1 for job in jobs if str(job.get("status", "")) == "failed")
    valid_quotes = sum(1 for quote in quotes if str(quote.get("status", "")) == "valid")
    stale_quotes = sum(1 for quote in quotes if quote.get("stale") is True or str(quote.get("status", "")) == "stale")
    total_jobs = max(1, completed + failed)
    total_quotes = max(1, len(quotes))
    uptime = sum(1 for item in health if str(item.get("status", "")) in {"healthy", "configured"}) / max(1, len(health))
    sla_max_latency_ms = _provider_sla_max_latency_ms(provider or {})
    latency_samples = tuple(_safe_non_negative_float(job.get("actual_latency_ms", 0.0)) for job in completed_jobs)
    observed_latency_samples = tuple(value for value in latency_samples if value > 0.0)
    latency_breaches = sum(
        1
        for job, latency_ms in zip(completed_jobs, latency_samples)
        if job.get("provider_sla_latency_breached") is True
        or (
            "provider_sla_latency_breached" not in job
            and sla_max_latency_ms > 0.0
            and latency_ms > sla_max_latency_ms
        )
    )
    latency_reliability = (
        1.0
        if not observed_latency_samples
        else max(0.0, 1.0 - (latency_breaches / len(observed_latency_samples)))
    )
    sla_breach_count = failed + latency_breaches
    fraud_counts = _fraud_signal_counts(fraud_signals)
    fraud_signal_count = sum(fraud_counts.values())
    critical_fraud_signal_count = sum(1 for signal in fraud_signals if str(signal.get("severity", "")) == "critical")
    fraud_penalty = min(1.0, fraud_signal_count / total_quotes)
    stale_quote_rate = stale_quotes / total_quotes
    refund_count = sum(1 for refund in refunds if str(refund.get("status", "")) not in {"cancelled", "rejected"})
    refund_rate = refund_count / total_jobs
    sla_breach_penalty = min(1.0, sla_breach_count / total_jobs)
    score = max(
        0.0,
        min(
            1.0,
            (completed / total_jobs * 0.3)
            + (valid_quotes / total_quotes * 0.25)
            + (uptime * 0.25)
            + (latency_reliability * 0.1)
            - (stale_quote_rate * 0.1)
            - (fraud_penalty * 0.2)
            - (sla_breach_penalty * 0.1)
            - (min(1.0, refund_rate) * 0.05)
        ),
    )
    manual_review_flags = tuple(
        sorted(
            {
                str(signal.get("signal_type", ""))
                for signal in fraud_signals
                if str(signal.get("severity", "")) in {"review", "critical"} and str(signal.get("signal_type", ""))
            }
        )
    )
    status = "degraded" if critical_fraud_signal_count else ("active" if score >= 0.8 else "probation")
    return {
        "provider_id": provider_id,
        "quote_accuracy_score": round(valid_quotes / total_quotes, 4),
        "execution_success_rate": round(completed / total_jobs, 4),
        "latency_reliability": round(latency_reliability, 4),
        "capacity_fulfillment_rate": 1.0,
        "refund_rate": round(refund_rate, 4),
        "dispute_rate": 0.0,
        "stale_quote_rate": round(stale_quote_rate, 4),
        "provider_uptime": round(uptime, 4),
        "sla_max_latency_ms": sla_max_latency_ms,
        "sla_latency_breach_count": latency_breaches,
        "sla_breach_count": sla_breach_count,
        "refund_count": refund_count,
        "quote_replay_count": fraud_counts.get("quote_replay", 0),
        "stale_quote_submission_count": fraud_counts.get("stale_quote_submission", 0),
        "signature_failure_count": fraud_counts.get("signature_failure", 0),
        "quote_price_manipulation_count": fraud_counts.get("quote_price_manipulation", 0),
        "provider_spoofing_count": fraud_counts.get("provider_spoofing_replay", 0),
        "fraud_signal_count": fraud_signal_count,
        "critical_fraud_signal_count": critical_fraud_signal_count,
        "manual_review_flags": manual_review_flags,
        "status": status,
        "score": round(score, 4),
        "updated_at": utc_now_iso(),
    }


def _contract_quote_from_normalized(quote: Mapping[str, Any]) -> dict[str, Any]:
    original = quote.get("original_quote", {})
    record = dict(original) if isinstance(original, Mapping) else {}
    record.update(dict(quote))
    for unsafe_key in ("broadcast", "broadcast_allowed", "broadcast_required", "sendTransaction", "signTransaction", "private_key", "private_key_required"):
        record.pop(unsafe_key, None)
    record.pop("original_quote", None)
    record.setdefault("currency_or_asset", record.get("payment_asset", "USD"))
    record.setdefault("settlement_modes", record.get("settlement_options", ("generic_dry_run",)))
    record.setdefault("dry_run_supported", bool(record.get("dry_run_only", True)))
    record.setdefault("assumptions", ())
    record.setdefault("quote_ttl_seconds", int(record.get("quote_ttl_seconds", 300) or 300))
    record.setdefault("capacity_available", bool(record.get("capacity_available", True)))
    record.setdefault("confidence", float(record.get("confidence", 0.75) or 0.75))
    return record

def _normalized_provider_quote(quote: Mapping[str, Any], *, quote_id: str, quote_hash: str, signed_quote_valid: bool = False) -> dict[str, Any]:
    now = utc_now_iso()
    estimated_total_cost = _positive_float(quote.get("estimated_total_cost"), "estimated_total_cost")
    return {
        "quote_id": quote_id,
        "provider_id": str(quote["provider_id"]),
        "route_id": str(quote["route_id"]),
        "provider_or_route": str(quote.get("provider_or_route", quote.get("route_id", ""))),
        "provider_type": str(quote.get("provider_type", "marketplace")),
        "provider_class": str(quote.get("provider_class", "")),
        "market_type": str(quote.get("market_type", "marketplace")),
        "network": str(quote.get("network", "offchain")),
        "payment_asset": str(quote.get("currency_or_asset", quote.get("payment_asset", "USD"))),
        "unit_type": str(quote["unit_type"]),
        "unit_price": float(quote["unit_price"]),
        "estimated_units": float(quote["estimated_units"]),
        "estimated_total_cost": estimated_total_cost,
        "capacity_available": bool(quote.get("capacity_available", True)),
        "settlement_mode": "generic_dry_run",
        "settlement_options": tuple(str(item) for item in quote.get("settlement_modes", ("generic_dry_run",))),
        "dry_run_only": True,
        "source": "live_provider",
        "status": "valid",
        "quote_ttl_seconds": int(quote.get("quote_ttl_seconds", 300) or 300),
        "expires_at": str(quote["expires_at"]),
        "assumptions": tuple(str(item) for item in quote.get("assumptions", ())),
        "raw_quote_hash": quote_hash,
        "signed_quote": str(quote.get("signature", "")),
        "signed_quote_valid": signed_quote_valid,
        "created_at": now,
        "updated_at": now,
    }


def _quote_drift(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    if not previous:
        return {}
    old_price = float(previous.get("estimated_total_cost", 0.0) or 0.0)
    new_price = float(current.get("estimated_total_cost", 0.0) or 0.0)
    if old_price <= 0:
        return {}
    drift_ratio = abs(new_price - old_price) / old_price
    if drift_ratio < 0.05:
        return {}
    return {
        "drift_id": deterministic_id("quote_drift", {"previous": previous.get("quote_id", ""), "current": current.get("quote_id", "")}),
        "provider_id": str(current.get("provider_id", "")),
        "route_id": str(current.get("route_id", "")),
        "tenant_id": str(current.get("tenant_id", "")),
        "workspace_id": str(current.get("workspace_id", "")),
        "previous_quote_id": str(previous.get("quote_id", "")),
        "current_quote_id": str(current.get("quote_id", "")),
        "previous_total_cost": old_price,
        "current_total_cost": new_price,
        "drift_ratio": round(drift_ratio, 6),
        "status": "review" if drift_ratio >= 0.25 else "observed",
        "created_at": utc_now_iso(),
    }


def _capacity_window(payload: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = str(payload.get("provider_id", "")).strip()
    route_id = str(payload.get("route_id", "")).strip()
    if not provider_id or not route_id:
        raise ValueError("provider_id and route_id are required for capacity listing")
    capacity_units = _positive_float(payload.get("available_units", payload.get("capacity_units")), "capacity_units")
    starts_at = str(payload.get("starts_at", utc_now_iso()))
    ends_at = str(payload.get("ends_at", ""))
    if not ends_at:
        raise ValueError("ends_at is required for capacity listing")
    return {
        "window_id": str(payload.get("window_id") or deterministic_id("capacity_window", {"provider_id": provider_id, "route_id": route_id, "starts_at": starts_at, "ends_at": ends_at})),
        "provider_id": provider_id,
        "route_id": route_id,
        "resource_type": str(payload.get("resource_type", "gpu_hour")),
        "gpu_type": str(payload.get("gpu_type", "any")),
        "region": str(payload.get("region", "")),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "capacity_available": True,
        "capacity_units": capacity_units,
        "available_units": capacity_units,
        "price_floor": float(payload.get("price_floor", 0.0) or 0.0),
        "reservation_required": bool(payload.get("reservation_required", True)),
        "status": "active",
        "tenant_id": str(payload.get("tenant_id", "")),
        "workspace_id": str(payload.get("workspace_id", "")),
        "created_at": utc_now_iso(),
    }


def _capacity_time_range(payload: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(payload.get("reserved_from", payload.get("starts_at", ""))).strip(),
        str(payload.get("reserved_until", payload.get("ends_at", ""))).strip(),
    )


def _capacity_has_time_range(payload: Mapping[str, Any]) -> bool:
    start, end = _capacity_time_range(payload)
    return bool(start or end)


def _time_ranges_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    if a_end and b_start and a_end <= b_start:
        return False
    if b_end and a_start and b_end <= a_start:
        return False
    return True


def _capacity_window_overlaps(window: Mapping[str, Any], start: str, end: str) -> bool:
    return _time_ranges_overlap(
        start,
        end,
        str(window.get("starts_at", "")),
        str(window.get("ends_at", "")),
    )


def _capacity_reservation_overlaps(reservation: Mapping[str, Any], start: str, end: str) -> bool:
    return _time_ranges_overlap(
        start,
        end,
        str(reservation.get("reserved_from", "")),
        str(reservation.get("reserved_until", "")),
    )


def _capacity_reservation_active(reservation: Mapping[str, Any], now: str) -> bool:
    status = str(reservation.get("status", ""))
    if status == "confirmed":
        reserved_until = str(reservation.get("reserved_until", ""))
        return not reserved_until or reserved_until > now
    if status != "held":
        return False
    hold_expires_at = str(reservation.get("hold_expires_at", reservation.get("expires_at", "")))
    return not hold_expires_at or hold_expires_at > now


def _capacity_hold_expired(reservation: Mapping[str, Any], now: str) -> bool:
    hold_expires_at = str(reservation.get("hold_expires_at", reservation.get("expires_at", "")))
    return str(reservation.get("status", "")) == "held" and bool(hold_expires_at) and hold_expires_at <= now


def _capacity_reservation(payload: Mapping[str, Any], windows: tuple[Mapping[str, Any], ...], reservations: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    if not windows:
        raise ValueError("no active capacity window found for provider_id and route_id")
    now = utc_now_iso()
    requested_start, requested_end = _capacity_time_range(payload)
    active_windows = tuple(
        window
        for window in windows
        if str(window.get("status", "active")) == "active"
        and str(window.get("ends_at", "")) > now
        and (not requested_start and not requested_end or _capacity_window_overlaps(window, requested_start, requested_end))
    )
    if not active_windows:
        if requested_start or requested_end:
            raise ValueError("no unexpired active capacity window overlaps requested reservation interval")
        raise ValueError("no unexpired active capacity window found for provider_id and route_id")
    window = active_windows[0]
    reservation_start = requested_start or str(window.get("starts_at", now))
    reservation_end = requested_end or str(window.get("ends_at", ""))
    requested_units = _positive_float(payload.get("capacity_units"), "capacity_units")
    active_reservations = tuple(
        item
        for item in reservations
        if _capacity_reservation_active(item, now)
        and _capacity_reservation_overlaps(item, reservation_start, reservation_end)
    )
    reserved = sum(float(item.get("capacity_units", item.get("units_reserved", 0.0)) or 0.0) for item in active_reservations)
    available = float(window.get("capacity_units", window.get("available_units", 0.0)) or 0.0) - reserved
    allow_partial = bool(payload.get("allow_partial", payload.get("partial_fill_allowed", False)))
    capacity_units = requested_units
    partial_fill = False
    if requested_units > available:
        if not allow_partial or available <= 0:
            raise ValueError("requested capacity exceeds available capacity")
        capacity_units = available
        partial_fill = True
    return {
        "reservation_id": str(payload.get("reservation_id") or deterministic_id("reservation", {"window_id": window.get("window_id", ""), "payload": payload})),
        "window_id": str(window.get("window_id", "")),
        "provider_id": str(payload.get("provider_id", "")),
        "route_id": str(payload.get("route_id", "")),
        "capacity_units": capacity_units,
        "requested_capacity_units": requested_units,
        "partial_fill": partial_fill,
        "partial_fill_reason": "capacity_shortfall" if partial_fill else "",
        "unit_type": str(payload.get("unit_type", window.get("resource_type", "gpu_hour"))),
        "reserved_from": reservation_start,
        "reserved_until": reservation_end,
        "status": "held",
        "hold_expires_at": str(payload.get("hold_expires_at", window.get("ends_at", ""))),
        "dry_run_only": True,
        "tenant_id": str(payload.get("tenant_id", window.get("tenant_id", ""))),
        "workspace_id": str(payload.get("workspace_id", window.get("workspace_id", ""))),
        "funds_moved": False,
        "created_at": now,
        "updated_at": now,
    }

def _capacity_auction_clearing(
    payload: Mapping[str, Any],
    windows: tuple[Mapping[str, Any], ...],
    reservations: tuple[Mapping[str, Any], ...],
    *,
    request_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    requested_start, requested_end = _capacity_time_range(payload)
    restrict_to_interval = bool(requested_start or requested_end)
    active_windows = tuple(
        window
        for window in windows
        if str(window.get("status", "active")) == "active"
        and str(window.get("ends_at", "")) > now
        and (not restrict_to_interval or _capacity_window_overlaps(window, requested_start, requested_end))
    )
    if not active_windows:
        if restrict_to_interval:
            raise ValueError("no unexpired active capacity window overlaps requested auction interval")
        raise ValueError("no unexpired active capacity window found for auction")
    auction_reservations = (
        tuple(
            reservation
            for reservation in reservations
            if _capacity_reservation_overlaps(reservation, requested_start, requested_end)
        )
        if restrict_to_interval
        else reservations
    )
    summary = _capacity_summary(active_windows, auction_reservations)
    available_units = float(summary.get("available_capacity_units", 0.0) or 0.0)
    if available_units <= 0:
        raise ValueError("no available capacity for auction")
    requested_units = _positive_float(
        payload.get("capacity_units", payload.get("requested_capacity_units", available_units)),
        "capacity_units",
    )
    allow_partial = bool(payload.get("allow_partial", True))
    if requested_units > available_units and not allow_partial:
        raise ValueError("requested auction capacity exceeds available capacity")
    auction_capacity_units = min(requested_units, available_units)
    raw_bids = payload.get("bids", ())
    if not isinstance(raw_bids, (list, tuple)):
        raise ValueError("bids must be a list")
    if not raw_bids:
        raise ValueError("at least one bid is required")
    window_floor = max(_safe_non_negative_float(window.get("price_floor", 0.0)) for window in active_windows)
    reserve_price = max(
        window_floor,
        _safe_non_negative_float(payload.get("reserve_price", payload.get("price_floor", 0.0))),
    )
    normalized_bids: list[dict[str, Any]] = []
    rejected_bids: list[dict[str, Any]] = []
    for index, raw_bid in enumerate(raw_bids):
        if not isinstance(raw_bid, Mapping):
            raise ValueError("each bid must be an object")
        bidder_id = str(raw_bid.get("bidder_id", raw_bid.get("account_id", ""))).strip()
        if not bidder_id:
            raise ValueError("bidder_id or account_id is required for each bid")
        bid_units = _positive_float(
            raw_bid.get("capacity_units", raw_bid.get("units", auction_capacity_units)),
            f"bids[{index}].capacity_units",
        )
        max_unit_price = _positive_float(
            raw_bid.get("max_unit_price", raw_bid.get("bid_price", raw_bid.get("unit_price"))),
            f"bids[{index}].max_unit_price",
        )
        bid = {
            "bid_id": str(
                raw_bid.get("bid_id")
                or deterministic_id("capacity_bid", {"request_id": request_id, "index": index, "bid": raw_bid})
            ),
            "bidder_id": bidder_id,
            "capacity_units": bid_units,
            "max_unit_price": max_unit_price,
            "submitted_at": str(raw_bid.get("submitted_at", now)),
        }
        if max_unit_price < reserve_price:
            rejected_bids.append({**bid, "rejection_reason": "below_reserve_price"})
            continue
        normalized_bids.append(bid)
    sorted_bids = sorted(
        normalized_bids,
        key=lambda bid: (-float(bid["max_unit_price"]), str(bid["submitted_at"]), str(bid["bid_id"])),
    )
    remaining_units = auction_capacity_units
    winning_bids: list[dict[str, Any]] = []
    for bid in sorted_bids:
        if remaining_units <= 0:
            rejected_bids.append({**bid, "rejection_reason": "capacity_exhausted"})
            continue
        bid_units = _positive_float(bid["capacity_units"], "bid.capacity_units")
        allocated_units = min(bid_units, remaining_units)
        if allocated_units < bid_units and not allow_partial:
            rejected_bids.append({**bid, "rejection_reason": "capacity_exhausted"})
            continue
        winning_bids.append(
            {
                **bid,
                "capacity_units": allocated_units,
                "requested_capacity_units": bid_units,
                "partial_fill": allocated_units < bid_units,
            }
        )
        remaining_units -= allocated_units
    total_units_cleared = sum(float(bid["capacity_units"]) for bid in winning_bids)
    clearing_unit_price = min((float(bid["max_unit_price"]) for bid in winning_bids), default=0.0)
    priced_winners = tuple(
        {
            **bid,
            "clearing_unit_price": clearing_unit_price,
            "estimated_total_cost": round(float(bid["capacity_units"]) * clearing_unit_price, 8),
        }
        for bid in winning_bids
    )
    status = "cleared" if priced_winners else "no_fill"
    auction_id = str(
        payload.get("auction_id")
        or deterministic_id(
            "capacity_auction",
            {
                "provider_id": payload.get("provider_id", ""),
                "route_id": payload.get("route_id", ""),
                "request_id": request_id,
                "bids": normalized_bids,
            },
        )
    )
    reason_codes = () if priced_winners else ("no_winning_bids",)
    return {
        "auction_id": auction_id,
        "provider_id": str(payload.get("provider_id", "")),
        "route_id": str(payload.get("route_id", "")),
        "status": status,
        "unit_type": str(payload.get("unit_type", active_windows[0].get("resource_type", "gpu_hour"))),
        "window_ids": tuple(str(window.get("window_id", "")) for window in active_windows),
        "available_capacity_units": available_units,
        "requested_capacity_units": requested_units,
        "auction_capacity_units": auction_capacity_units,
        "total_units_cleared": total_units_cleared,
        "reserve_price": reserve_price,
        "clearing_unit_price": clearing_unit_price,
        "winning_bids": priced_winners,
        "rejected_bids": tuple(rejected_bids),
        "reason_codes": reason_codes,
        "dry_run_only": True,
        "funds_moved": False,
        "reservations_created": False,
        "tenant_id": str(payload.get("tenant_id", "")),
        "workspace_id": str(payload.get("workspace_id", "")),
        "created_at": now,
        "request_id": request_id,
    }


def _capacity_summary(windows: tuple[Mapping[str, Any], ...], reservations: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    now = utc_now_iso()
    active_windows = tuple(window for window in windows if str(window.get("status", "active")) == "active" and str(window.get("ends_at", "")) > now)
    total_capacity = sum(float(item.get("capacity_units", 0.0) or 0.0) for item in active_windows)
    active_reservations = tuple(item for item in reservations if _capacity_reservation_active(item, now))
    expired_reservations = tuple(item for item in reservations if _capacity_hold_expired(item, now) or str(item.get("status", "")) == "expired")
    reserved_units = sum(float(item.get("capacity_units", item.get("units_reserved", 0.0)) or 0.0) for item in active_reservations)
    held_units = sum(float(item.get("capacity_units", item.get("units_reserved", 0.0)) or 0.0) for item in active_reservations if str(item.get("status", "")) == "held")
    confirmed_units = sum(float(item.get("capacity_units", item.get("units_reserved", 0.0)) or 0.0) for item in active_reservations if str(item.get("status", "")) == "confirmed")
    expired_units = sum(float(item.get("capacity_units", item.get("units_reserved", 0.0)) or 0.0) for item in expired_reservations)
    utilization_by_provider: dict[str, dict[str, float]] = {}
    for window in active_windows:
        provider_id = str(window.get("provider_id", ""))
        if not provider_id:
            continue
        provider = utilization_by_provider.setdefault(
            provider_id,
            {
                "total_capacity_units": 0.0,
                "reserved_capacity_units": 0.0,
                "held_capacity_units": 0.0,
                "confirmed_capacity_units": 0.0,
                "available_capacity_units": 0.0,
                "expired_capacity_units": 0.0,
                "utilization_ratio": 0.0,
            },
        )
        provider["total_capacity_units"] += float(window.get("capacity_units", 0.0) or 0.0)
    for reservation in active_reservations:
        provider_id = str(reservation.get("provider_id", ""))
        if not provider_id:
            continue
        provider = utilization_by_provider.setdefault(
            provider_id,
            {
                "total_capacity_units": 0.0,
                "reserved_capacity_units": 0.0,
                "held_capacity_units": 0.0,
                "confirmed_capacity_units": 0.0,
                "available_capacity_units": 0.0,
                "expired_capacity_units": 0.0,
                "utilization_ratio": 0.0,
            },
        )
        units = float(reservation.get("capacity_units", reservation.get("units_reserved", 0.0)) or 0.0)
        provider["reserved_capacity_units"] += units
        if str(reservation.get("status", "")) == "confirmed":
            provider["confirmed_capacity_units"] += units
        else:
            provider["held_capacity_units"] += units
    for reservation in expired_reservations:
        provider_id = str(reservation.get("provider_id", ""))
        if not provider_id:
            continue
        provider = utilization_by_provider.setdefault(
            provider_id,
            {
                "total_capacity_units": 0.0,
                "reserved_capacity_units": 0.0,
                "held_capacity_units": 0.0,
                "confirmed_capacity_units": 0.0,
                "available_capacity_units": 0.0,
                "expired_capacity_units": 0.0,
                "utilization_ratio": 0.0,
            },
        )
        provider["expired_capacity_units"] += float(
            reservation.get("capacity_units", reservation.get("units_reserved", 0.0)) or 0.0
        )
    for provider in utilization_by_provider.values():
        provider["available_capacity_units"] = max(
            0.0,
            provider["total_capacity_units"] - provider["reserved_capacity_units"],
        )
        provider["utilization_ratio"] = (
            round(provider["reserved_capacity_units"] / provider["total_capacity_units"], 6)
            if provider["total_capacity_units"]
            else 0.0
        )
    return {
        "window_count": len(active_windows),
        "reservation_count": len(reservations),
        "active_reservation_count": len(active_reservations),
        "expired_reservation_count": len(expired_reservations),
        "total_capacity_units": total_capacity,
        "reserved_capacity_units": reserved_units,
        "held_capacity_units": held_units,
        "confirmed_capacity_units": confirmed_units,
        "expired_capacity_units": expired_units,
        "available_capacity_units": max(0.0, total_capacity - reserved_units),
        "utilization_ratio": round(reserved_units / total_capacity, 6) if total_capacity else 0.0,
        "utilization_by_provider": utilization_by_provider,
    }


def _claim_candidates(
    store: ComputeMarketStoreProtocol,
    *,
    requested_job_id: str = "",
    tenant_id: str = "",
) -> tuple[Mapping[str, Any], ...]:
    tenant_filter = tenant_id.strip()
    if requested_job_id:
        job = store.get_record("compute_job", requested_job_id)
        if job is None or not _tenant_can_access_record({"tenant_id": tenant_filter}, job):
            return ()
        return (job,)
    now = utc_now_iso()
    queued_filters: dict[str, Any] = {"status": "queued"}
    dispatched_filters: dict[str, Any] = {"status": "dispatched"}
    if tenant_filter:
        queued_filters["tenant_id"] = tenant_filter
        dispatched_filters["tenant_id"] = tenant_filter
    queued = store.list_records("compute_job", filters=queued_filters, limit=100).records
    dispatched = tuple(
        job
        for job in store.list_records("compute_job", filters=dispatched_filters, limit=100).records
        if _job_lease_expired(job, now)
    )
    return tuple(
        sorted(
            (*queued, *dispatched),
            key=lambda item: (str(item.get("created_at", "")), str(item.get("job_id", item.get("record_id", "")))),
        )
    )


def _payload_tenant_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("tenant_id", "")).strip()


def _tenant_can_access_record(payload: Mapping[str, Any], record: Mapping[str, Any]) -> bool:
    tenant_id = _payload_tenant_id(payload)
    if not tenant_id:
        return True
    return str(record.get("tenant_id", "")).strip() == tenant_id


def _tenant_can_access_catalog_record(payload: Mapping[str, Any], record: Mapping[str, Any]) -> bool:
    tenant_id = _payload_tenant_id(payload)
    if not tenant_id:
        return True
    record_tenant_id = str(record.get("tenant_id", "")).strip()
    return not record_tenant_id or record_tenant_id == tenant_id

def _tenant_scoped_record_id(record_type: str, natural_id: str, tenant_id: str) -> str:
    tenant = tenant_id.strip()
    if not tenant:
        return natural_id
    return deterministic_id(record_type, {"tenant_id": tenant, "record_id": natural_id})


def _quote_record_id(quote_id: str, tenant_id: str) -> str:
    return _tenant_scoped_record_id("compute_quote", quote_id, tenant_id)


def _quote_replay_record_id(quote_id: str, tenant_id: str) -> str:
    return _tenant_scoped_record_id("quote_replay_guard", quote_id, tenant_id)


def _quote_cache_key(
    store: ComputeMarketStoreProtocol,
    provider_id: str,
    route_id: str,
    task_hash: str,
    policy_hash: str,
    tenant_id: str,
) -> str:
    if not tenant_id:
        return store.quote_cache_key(provider_id, route_id, task_hash, policy_hash)
    return deterministic_id(
        "quote_cache",
        {
            "provider_id": provider_id,
            "route_id": route_id,
            "task_hash": task_hash,
            "policy_hash": policy_hash,
            "tenant_id": tenant_id,
        },
    )


def _get_tenant_scoped_record(
    store: ComputeMarketStoreProtocol,
    record_type: str,
    natural_id: str,
    scoped_id: str,
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for record_id in (scoped_id, natural_id):
        record = store.get_record(record_type, record_id)
        if record is not None and _tenant_can_access_record(payload, record):
            return record
    return None


def _get_quote_record(
    store: ComputeMarketStoreProtocol,
    quote_id: str,
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    tenant_id = _payload_tenant_id(payload)
    record = _get_tenant_scoped_record(
        store,
        "compute_quote",
        quote_id,
        _quote_record_id(quote_id, tenant_id),
        payload,
    )
    if record is not None:
        return record
    if not tenant_id:
        return None
    for candidate in store.list_records("compute_quote", filters={"tenant_id": tenant_id}, limit=500).records:
        if str(candidate.get("quote_id", candidate.get("record_id", ""))) == quote_id:
            return candidate
    return None

def _assert_provider_catalog_access(
    store: ComputeMarketStoreProtocol,
    provider_id: str,
    payload: Mapping[str, Any],
) -> None:
    if not provider_id:
        return
    provider = store.get_record("compute_provider", provider_id)
    if provider is not None:
        if not _tenant_can_access_catalog_record(payload, provider):
            raise KeyError(f"Unknown compute provider: {provider_id}")
        return
    applications = store.list_records(
        "market_provider_application",
        filters={"provider_id": provider_id},
        limit=500,
    ).records
    if applications and not any(_tenant_can_access_catalog_record(payload, application) for application in applications):
        raise KeyError(f"Unknown compute provider: {provider_id}")


def _payload_worker_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("worker_id", "")).strip()


def _worker_id(payload: Mapping[str, Any]) -> str:
    worker_id = _payload_worker_id(payload)
    if not worker_id:
        raise ValueError("worker_id is required")
    return worker_id


def _assert_claim_owner(job: Mapping[str, Any], payload: Mapping[str, Any], action: str) -> str:
    claimed_by = str(job.get("claimed_by", "")).strip()
    worker_id = _payload_worker_id(payload)
    if claimed_by and worker_id != claimed_by:
        raise ValueError(f"worker_id does not own claim for compute job during {action}")
    return worker_id


def _lease_ttl_seconds(payload: Mapping[str, Any]) -> int:
    return min(3_600, max(30, int(_positive_float(payload.get("ttl_seconds", 300), "ttl_seconds"))))


def _positive_int(value: object, name: str, *, default: int) -> int:
    try:
        amount = int(str(value if value not in (None, "") else default))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer") from None
    if amount <= 0:
        raise ValueError(f"{name} must be positive")
    return amount


def _retry_policy_value(payload: Mapping[str, Any], key: str, default: int) -> object:
    retry_policy = payload.get("retry_policy", {})
    if isinstance(retry_policy, Mapping):
        return retry_policy.get(key, default)
    return default


def _job_max_retries(job: Mapping[str, Any]) -> int:
    return _positive_int(job.get("max_retries", 2), "max_retries", default=2)


def _job_max_dispatch_attempts(job: Mapping[str, Any]) -> int:
    return _positive_int(job.get("max_dispatch_attempts", 3), "max_dispatch_attempts", default=3)


def _future_utc_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _job_lease_expired(job: Mapping[str, Any], now: str) -> bool:
    lease_expires_at = str(job.get("lease_expires_at") or job.get("expires_at") or "")
    return bool(lease_expires_at and lease_expires_at <= now)


def _worker_capabilities(payload: Mapping[str, Any]) -> tuple[str, ...]:
    capabilities = payload.get("capabilities", ())
    if isinstance(capabilities, Mapping):
        return tuple(f"{key}:{capabilities[key]}" for key in sorted(capabilities))
    if isinstance(capabilities, str):
        return (capabilities,) if capabilities else ()
    if isinstance(capabilities, (list, tuple, set)):
        return tuple(str(item) for item in capabilities if str(item))
    return ()

def _compute_job(payload: Mapping[str, Any], *, request_id: str) -> dict[str, Any]:
    task_type = str(payload.get("task_type", "")).strip()
    input_ref = str(payload.get("input_ref", "")).strip()
    runtime = str(payload.get("model_or_runtime", "")).strip()
    provider_id = str(payload.get("provider_id", "")).strip()
    route_id = str(payload.get("route_id", "")).strip()
    if not all((task_type, input_ref, runtime, provider_id, route_id)):
        raise ValueError("task_type, input_ref, model_or_runtime, provider_id, and route_id are required")
    now = utc_now_iso()
    return {
        "job_id": str(payload.get("job_id") or deterministic_id("job", {"request_id": request_id, "payload": payload})),
        "task_type": task_type,
        "input_ref": input_ref,
        "model_or_runtime": runtime,
        "resource_request": dict(payload.get("resource_request", {})) if isinstance(payload.get("resource_request"), Mapping) else {},
        "budget_policy_id": str(payload.get("budget_policy_id", "")),
        "route_id": route_id,
        "provider_id": provider_id,
        "tenant_id": str(payload.get("tenant_id", "")).strip(),
        "workspace_id": str(payload.get("workspace_id", payload.get("tenant_id", ""))).strip(),
        "account_id": str(payload.get("account_id", payload.get("tenant_id", ""))).strip(),
        "estimated_units": _safe_non_negative_float(payload.get("estimated_units", 0.0)),
        "estimated_total_cost": _safe_non_negative_float(
            payload.get("estimated_total_cost", payload.get("estimated_cost", 0.0))
        ),
        "currency": str(payload.get("currency", payload.get("asset", "USD"))).upper(),
        "status": "queued",
        "lifecycle": ("planned", "quoted", "approved", "reserved", "queued"),
        "allowed_lifecycle": ("planned", "quoted", "approved", "reserved", "queued", "dispatched", "running", "succeeded", "failed", "cancelled", "expired", "settled", "reconciled"),
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "attempt": 0,
        "max_retries": _positive_int(
            payload.get("max_retries", _retry_policy_value(payload, "max_retries", 2)),
            "max_retries",
            default=2,
        ),
        "max_dispatch_attempts": _positive_int(
            payload.get("max_dispatch_attempts", _retry_policy_value(payload, "max_dispatch_attempts", 3)),
            "max_dispatch_attempts",
            default=3,
        ),
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _job_event(job_id: str, event_type: str, *, status: str, request_id: str, details: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": deterministic_id("job_event", {"job_id": job_id, "event_type": event_type, "request_id": request_id, "created_at": utc_now_iso()}),
        "job_id": job_id,
        "event_type": event_type,
        "status": status,
        "details": dict(details),
        "created_at": utc_now_iso(),
        "request_id": request_id,
    }


def _assert_job_status(job: Mapping[str, Any], allowed: tuple[str, ...], action: str) -> None:
    status = str(job.get("status", ""))
    if status not in allowed:
        allowed_text = ", ".join(allowed)
        raise ValueError(f"cannot {action} compute job from status {status}; expected one of: {allowed_text}")


def _append_lifecycle(job: Mapping[str, Any], status: str) -> tuple[str, ...]:
    lifecycle = tuple(str(item) for item in job.get("lifecycle", ()) if str(item))
    if status in lifecycle:
        return lifecycle
    return (*lifecycle, status)


def _job_cost(payload: Mapping[str, Any]) -> float:
    cost_data = payload.get("cost_data", {})
    if isinstance(cost_data, Mapping):
        value = cost_data.get("actual_total_cost", cost_data.get("estimated_total_cost", payload.get("actual_total_cost", 0.0)))
    else:
        value = payload.get("actual_total_cost", 0.0)
    return _non_negative_float(value, "actual_total_cost")


def _job_artifact(job: Mapping[str, Any], payload: Mapping[str, Any], *, request_id: str) -> dict[str, Any]:
    artifact = payload.get("artifact_data", payload.get("artifact", {}))
    artifact_ref = str(payload.get("artifact_ref", ""))
    if not artifact and not artifact_ref:
        return {}
    if artifact and not isinstance(artifact, Mapping):
        raise ValueError("artifact_data must be an object")
    now = utc_now_iso()
    artifact_payload = dict(artifact) if isinstance(artifact, Mapping) else {}
    artifact_id = str(payload.get("artifact_id") or deterministic_id("artifact", {"job_id": job.get("job_id", ""), "artifact_ref": artifact_ref, "artifact": artifact_payload}))
    return {
        "artifact_id": artifact_id,
        "job_id": str(job.get("job_id", "")),
        "provider_id": str(job.get("provider_id", "")),
        "route_id": str(job.get("route_id", "")),
        "artifact_ref": artifact_ref,
        "artifact_type": str(payload.get("artifact_type", artifact_payload.get("artifact_type", "result"))),
        "artifact_hash": content_hash({"artifact_ref": artifact_ref, "artifact": artifact_payload}),
        "metadata": artifact_payload,
        "status": "available",
        "dry_run_only": True,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _billing_account_id(payload: Mapping[str, Any], *, fallback_account_id: str = "", required: bool = True) -> str:
    account_id = str(payload.get("account_id", "")).strip()
    tenant_id = str(payload.get("tenant_id", "")).strip()
    fallback = str(fallback_account_id).strip()
    if account_id and tenant_id and account_id != tenant_id:
        raise ValueError("account_id must match tenant_id")
    if fallback:
        if account_id and account_id != fallback:
            raise ValueError("account_id must match billing record account_id")
        if tenant_id and tenant_id != fallback:
            raise ValueError("tenant_id must match billing record account_id")
    resolved = account_id or tenant_id or fallback
    if required and not resolved:
        raise ValueError("account_id or tenant_id is required")
    return resolved


def _usage_charge(job: Mapping[str, Any], payload: Mapping[str, Any], *, request_id: str, amount: float, units: float) -> dict[str, Any]:
    if amount <= 0:
        return {}
    account_id = _billing_account_id(payload, fallback_account_id=str(job.get("tenant_id", "")).strip(), required=False)
    currency = str(payload.get("currency", payload.get("asset", "USD"))).upper()
    now = utc_now_iso()
    usage_charge_id = str(payload.get("usage_charge_id") or deterministic_id("usage_charge", {"job_id": job.get("job_id", ""), "amount": amount, "request_id": request_id}))
    return {
        "usage_charge_id": usage_charge_id,
        "job_id": str(job.get("job_id", "")),
        "account_id": account_id,
        "provider_id": str(job.get("provider_id", "")),
        "route_id": str(job.get("route_id", "")),
        "task_type": str(job.get("task_type", "")),
        "unit_type": str(payload.get("unit_type", "compute_unit")),
        "units": units,
        "amount": amount,
        "currency": currency,
        "status": "dry_run_recorded",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _stripe_event_object(raw_event: Mapping[str, Any]) -> Mapping[str, Any]:
    data = raw_event.get("data", {})
    if isinstance(data, Mapping):
        obj = data.get("object", {})
        if isinstance(obj, Mapping):
            return obj
    return raw_event


def _stripe_account_id(raw_event: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    event_object = _stripe_event_object(raw_event)
    metadata = event_object.get("metadata", raw_event.get("metadata", {}))
    if not isinstance(metadata, Mapping):
        metadata = {}
    return str(
        payload.get("account_id")
        or payload.get("tenant_id")
        or metadata.get("account_id")
        or metadata.get("tenant_id")
        or event_object.get("client_reference_id")
        or raw_event.get("client_reference_id")
        or event_object.get("customer")
        or raw_event.get("customer")
        or ""
    )


def _provider_sla_refund_policy(provider: Mapping[str, Any]) -> str:
    metadata = provider.get("metadata", {})
    if isinstance(metadata, Mapping):
        sla = metadata.get("sla", {})
        if isinstance(sla, Mapping) and str(sla.get("refund_policy", "")).strip():
            return str(sla["refund_policy"])
    sla = provider.get("sla", {})
    if isinstance(sla, Mapping) and str(sla.get("refund_policy", "")).strip():
        return str(sla["refund_policy"])
    return "manual_review"


def _provider_sla_penalty(
    provider: Mapping[str, Any],
    job: Mapping[str, Any],
    usage_charge: Mapping[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    if not usage_charge or not bool(job.get("provider_sla_latency_breached", False)):
        return {}
    amount = _safe_non_negative_float(usage_charge.get("amount", 0.0))
    if amount <= 0:
        return {}
    usage_charge_id = str(usage_charge.get("usage_charge_id", ""))
    job_id = str(job.get("job_id", ""))
    penalty_id = deterministic_id(
        "provider_sla_penalty",
        {"provider_id": job.get("provider_id", ""), "job_id": job_id, "usage_charge_id": usage_charge_id},
    )
    now = utc_now_iso()
    return {
        "sla_penalty_id": penalty_id,
        "job_id": job_id,
        "usage_charge_id": usage_charge_id,
        "account_id": str(usage_charge.get("account_id", "")),
        "provider_id": str(job.get("provider_id", "")),
        "route_id": str(job.get("route_id", "")),
        "status": "pending_reconciliation",
        "sla_breach_type": "latency",
        "refund_policy": _provider_sla_refund_policy(provider),
        "provider_sla_max_latency_ms": _safe_non_negative_float(job.get("provider_sla_max_latency_ms", 0.0)),
        "actual_latency_ms": _safe_non_negative_float(job.get("actual_latency_ms", 0.0)),
        "recommended_credit_amount": amount,
        "provider_payout_adjustment_amount": amount,
        "currency": str(usage_charge.get("currency", "USD")),
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _stripe_credit(raw_event: Mapping[str, Any]) -> dict[str, object]:
    event_object = _stripe_event_object(raw_event)
    amount_source = event_object.get("amount_total", "")
    if amount_source in (None, ""):
        amount_source = event_object.get("amount_paid", "")
    if amount_source in (None, ""):
        amount_source = event_object.get("amount", "")
    if amount_source in (None, ""):
        amount_source = raw_event.get("amount_total", raw_event.get("amount_paid", raw_event.get("amount", 0)))
    amount = _non_negative_float(amount_source, "amount")
    if amount >= 100 and float(int(amount)) == amount:
        amount = amount / 100.0
    return {
        "amount": amount,
        "currency": str(event_object.get("currency", raw_event.get("currency", "USD"))).upper(),
    }


def _alert_delivery_record(alert: Mapping[str, Any], *, webhook_url: str, request_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    rule_name = str(alert.get("rule_name", ""))
    delivery_id = deterministic_id(
        "alert_delivery",
        {"rule_name": rule_name, "fired_at": alert.get("fired_at", ""), "request_id": request_id},
    )
    return {
        "delivery_id": delivery_id,
        "rule_name": rule_name,
        "metric_name": str(alert.get("metric_name", "")),
        "severity": str(alert.get("severity", "")),
        "status": "pending_delivery",
        "channel": "webhook",
        "target": _redacted_url(webhook_url),
        "delivery_attempted": False,
        "alert": dict(alert),
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _alert_delivery_envelope(alert: Mapping[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "type": "flow_memory.compute_market.alert",
        "request_id": request_id,
        "alert": dict(alert),
        "service": "flow-memory-compute-market",
        "created_at": utc_now_iso(),
    }


def _error_tracking_record(
    error_code: str,
    message: str,
    details: Mapping[str, Any],
    *,
    webhook_url: str,
    request_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    event_id = deterministic_id(
        "error_tracking_event",
        {"error_code": error_code, "message": message, "details": details, "request_id": request_id},
    )
    return {
        "event_id": event_id,
        "error_code": error_code,
        "message": message,
        "details": dict(details),
        "status": "pending_delivery",
        "channel": "webhook",
        "target": _redacted_url(webhook_url),
        "delivery_attempted": False,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _error_tracking_envelope(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "flow_memory.compute_market.error",
        "request_id": str(record.get("request_id", "")),
        "event_id": str(record.get("event_id", "")),
        "error_code": str(record.get("error_code", "")),
        "message": str(record.get("message", "")),
        "details": dict(record.get("details", {})) if isinstance(record.get("details", {}), Mapping) else {},
        "service": "flow-memory-compute-market",
        "created_at": str(record.get("created_at", utc_now_iso())),
    }


def _safe_error_details(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): _safe_error_value(str(key), value) for key, value in raw.items()}


def _safe_error_value(key: str, value: object) -> Any:
    if _is_sensitive_error_key(key):
        return "[redacted]"
    if isinstance(value, Mapping):
        return {str(child_key): _safe_error_value(str(child_key), child_value) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_safe_error_value("", item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_error_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _ERROR_DETAIL_KEY_FRAGMENTS)


def _otlp_export_record(
    export_id: str,
    *,
    endpoint_url: str,
    metric_count: int,
    trace_count: int,
    request_id: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "export_id": export_id,
        "endpoint": _redacted_url(endpoint_url),
        "status": "pending_delivery",
        "channel": "otlp_http_json",
        "metric_count": metric_count,
        "trace_count": trace_count,
        "delivery_attempted": False,
        "created_at": now,
        "updated_at": now,
        "request_id": request_id,
    }


def _otlp_export_body(snapshot: Mapping[str, Any], *, export_id: str, request_id: str) -> Mapping[str, Any]:
    metrics = tuple(item for item in snapshot.get("metrics", ()) if isinstance(item, Mapping))
    traces = tuple(item for item in snapshot.get("traces", ()) if isinstance(item, Mapping))
    resource = {
        "attributes": (
            {"key": "service.name", "value": {"stringValue": "flow-memory-compute-market"}},
            {"key": "deployment.environment", "value": {"stringValue": "production_planning"}},
            {"key": "flow_memory.export_id", "value": {"stringValue": export_id}},
            {"key": "flow_memory.request_id", "value": {"stringValue": request_id}},
        )
    }
    scope = {"name": "flow-memory.compute-market", "version": "1.0.0"}
    return {
        "resourceMetrics": (
            {
                "resource": resource,
                "scopeMetrics": (
                    {
                        "scope": scope,
                        "metrics": tuple(_otlp_metric(item) for item in metrics),
                    },
                ),
            },
        ),
        "resourceSpans": (
            {
                "resource": resource,
                "scopeSpans": (
                    {
                        "scope": scope,
                        "spans": tuple(_otlp_span(item) for item in traces),
                    },
                ),
            },
        ),
    }


def _otlp_metric(sample: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "name": str(sample.get("name", "")),
        "gauge": {
            "dataPoints": (
                {
                    "asDouble": _safe_non_negative_float(sample.get("value", 0.0)),
                    "attributes": _otlp_attributes(sample.get("labels", {})),
                },
            )
        },
    }


def _otlp_span(span: Mapping[str, Any]) -> Mapping[str, Any]:
    end_time = int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000_000)
    latency_ns = int(max(0.0, _safe_non_negative_float(span.get("latency_ms", 0.0))) * 1_000_000)
    return {
        "name": str(span.get("name", "")),
        "startTimeUnixNano": str(max(0, end_time - latency_ns)),
        "endTimeUnixNano": str(end_time),
        "attributes": _otlp_attributes(span.get("attributes", {})),
    }


def _otlp_attributes(raw: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(raw, Mapping):
        return ()
    return tuple(
        {"key": str(key), "value": {"stringValue": str(value)}}
        for key, value in sorted(raw.items())
    )


def _otlp_headers(raw: tuple[str, ...]) -> Mapping[str, str]:
    headers: dict[str, str] = {}
    for item in raw:
        key, separator, value = item.partition(":")
        if not separator:
            key, separator, value = item.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value or "\n" in key or "\r" in key or "\n" in value or "\r" in value:
            continue
        headers[key] = value
    return headers


def _post_json_with_transient_retry(
    endpoint_url: str,
    body: bytes,
    *,
    headers: Mapping[str, str],
    timeout_ms: int,
    delivery_failure_reason: str,
    non_2xx_reason: str,
) -> Mapping[str, Any]:
    timeout_seconds = max(0.001, timeout_ms / 1000.0)
    last_error = ""
    now = utc_now_iso()
    for attempt_index in range(2):
        request = urllib.request.Request(endpoint_url, data=body, headers=dict(headers), method="POST")
        now = utc_now_iso()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(getattr(response, "status", 0) or response.getcode())
                response.read(1024)
        except urllib.error.HTTPError as exc:
            return {
                "status": "failed",
                "http_status": int(getattr(exc, "code", 0) or 0),
                "error": type(exc).__name__,
                "reason_codes": (non_2xx_reason,),
                "updated_at": now,
            }
        except (OSError, urllib.error.URLError) as exc:
            last_error = type(exc).__name__
            if attempt_index == 0:
                continue
            return {
                "status": "failed",
                "http_status": 0,
                "error": last_error,
                "reason_codes": (delivery_failure_reason,),
                "updated_at": now,
            }
        if 200 <= status_code < 300:
            return {
                "status": "delivered",
                "http_status": status_code,
                "delivered_at": now,
                "reason_codes": (),
                "updated_at": now,
            }
        return {
            "status": "failed",
            "http_status": status_code,
            "reason_codes": (non_2xx_reason,),
            "updated_at": now,
        }
    return {
        "status": "failed",
        "http_status": 0,
        "error": last_error or "OSError",
        "reason_codes": (delivery_failure_reason,),
        "updated_at": now,
    }


def _post_otlp_collector(
    endpoint_url: str,
    envelope: Mapping[str, Any],
    *,
    headers: Mapping[str, str],
    timeout_ms: int,
) -> Mapping[str, Any]:
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    request_headers = {
        "content-type": "application/json",
        "user-agent": "flow-memory-compute-market-otlp/1",
        **dict(headers),
    }
    return _post_json_with_transient_retry(
        endpoint_url,
        body,
        headers=request_headers,
        timeout_ms=timeout_ms,
        delivery_failure_reason="otlp_collector_delivery_failed",
        non_2xx_reason="otlp_collector_non_2xx",
    )


def _post_alert_webhook(
    webhook_url: str,
    envelope: Mapping[str, Any],
    *,
    secret: str,
    timeout_ms: int,
) -> Mapping[str, Any]:
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    headers = {"content-type": "application/json", "user-agent": "flow-memory-compute-market-alerts/1"}
    if secret:
        headers["x-flow-memory-alert-signature"] = hmac.new(secret.encode("utf-8"), body, "sha256").hexdigest()
    return _post_json_with_transient_retry(
        webhook_url,
        body,
        headers=headers,
        timeout_ms=timeout_ms,
        delivery_failure_reason="alert_webhook_delivery_failed",
        non_2xx_reason="alert_webhook_non_2xx",
    )


def _alert_webhook_url_allowed(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme == "https" and bool(parsed.netloc):
        return True
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return True
    return False


def _redacted_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if not parsed.netloc:
        return value
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _stripe_event_posts_credit(raw_event: Mapping[str, Any]) -> bool:
    return str(raw_event.get("type", "")) in {"checkout.session.completed", "invoice.paid", "payment_intent.succeeded"}


def _stripe_event_is_payment_failure(event_type: str) -> bool:
    return event_type in {
        "checkout.session.expired",
        "invoice.payment_failed",
        "payment_intent.canceled",
        "payment_intent.payment_failed",
    }


def _stripe_payment_event_status(event_type: str, verified: bool) -> str:
    if not verified:
        return "rejected_unverified"
    if event_type == "checkout.session.expired":
        return "verified_checkout_expired"
    if event_type == "payment_intent.canceled":
        return "verified_payment_canceled"
    if _stripe_event_is_payment_failure(event_type):
        return "verified_payment_failed"
    return "verified"


def _stripe_failure(raw_event: Mapping[str, Any]) -> Mapping[str, str]:
    event_type = str(raw_event.get("type", ""))
    if not _stripe_event_is_payment_failure(event_type):
        return {}
    event_object = _stripe_event_object(raw_event)
    last_error = event_object.get("last_payment_error", raw_event.get("last_payment_error", {}))
    if not isinstance(last_error, Mapping):
        last_error = {}
    code = str(
        event_object.get("failure_code")
        or raw_event.get("failure_code")
        or last_error.get("code")
        or event_type
    )
    reason = str(
        event_object.get("failure_message")
        or raw_event.get("failure_message")
        or last_error.get("message")
        or event_type
    )
    return {"code": code, "reason": reason}


def _stripe_webhook_reason_codes(status: str, failure: Mapping[str, str]) -> tuple[str, ...]:
    if status == "rejected_unverified":
        return ("webhook_signature_invalid",)
    if status.startswith("verified_payment") or status == "verified_checkout_expired":
        return (str(failure.get("code") or status),)
    return ()


def _create_stripe_checkout_session(
    config: ComputeMarketConfig,
    checkout: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    request_id: str,
    idempotency_key: str,
) -> Mapping[str, str]:
    success_url = str(payload.get("success_url") or config.stripe_checkout_success_url).strip()
    cancel_url = str(payload.get("cancel_url") or config.stripe_checkout_cancel_url).strip()
    if not _is_https_url(success_url) or not _is_https_url(cancel_url):
        raise RuntimeError("stripe checkout redirect URLs must be https")
    amount_cents = _minor_currency_units(float(checkout.get("amount", 0.0)))
    account_id = str(checkout.get("account_id", ""))
    payment_event_id = str(checkout.get("payment_event_id", ""))
    fields = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": account_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": str(checkout.get("currency", "USD")).lower(),
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][price_data][product_data][name]": config.stripe_checkout_product_name,
        "metadata[account_id]": account_id,
        "metadata[request_id]": request_id,
        "metadata[payment_event_id]": payment_event_id,
    }
    body = urllib.parse.urlencode(fields).encode("utf-8")
    url = f"{config.stripe_api_base_url.rstrip('/')}/v1/checkout/sessions"
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "authorization": f"Bearer {config.stripe_secret_key}",
            "content-type": "application/x-www-form-urlencoded",
            "idempotency-key": idempotency_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.stripe_checkout_timeout_ms / 1000.0) as response:
            raw = response.read(65_537)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise RuntimeError("stripe checkout request failed") from exc
    if len(raw) > 65_536:
        raise RuntimeError("stripe checkout response too large")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("stripe checkout response was not valid JSON") from exc
    if not isinstance(decoded, Mapping):
        raise RuntimeError("stripe checkout response must be an object")
    session_id = str(decoded.get("id", "")).strip()
    session_url = str(decoded.get("url", "")).strip()
    if not session_id or not _is_https_url(session_url):
        raise RuntimeError("stripe checkout response missing hosted session")
    return {"id": session_id, "url": session_url}


def _minor_currency_units(amount: float) -> int:
    cents = (Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    value = int(cents)
    if value <= 0:
        raise RuntimeError("stripe checkout amount must be positive")
    return value


def _is_https_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _apply_credit(
    store: ComputeMarketStoreProtocol,
    account_id: str,
    *,
    amount: float,
    currency: str,
    request_id: str,
    source_event_id: str,
) -> Mapping[str, Any]:
    transaction_id = deterministic_id("credit_transaction", {"account_id": account_id, "source_event_id": source_event_id, "type": "credit"})
    existing = store.get_record("credit_transaction", transaction_id)
    if existing is not None:
        return existing
    now = utc_now_iso()
    current = store.get_record("credit_balance", account_id) or {
        "account_id": account_id,
        "available_credits": 0.0,
        "reserved_credits": 0.0,
        "currency": currency,
        "created_at": now,
    }
    available = float(current.get("available_credits", 0.0) or 0.0) + amount
    balance = {
        **dict(current),
        "account_id": account_id,
        "available_credits": round(available, 6),
        "reserved_credits": float(current.get("reserved_credits", 0.0) or 0.0),
        "currency": currency,
        "updated_at": now,
    }
    transaction = {
        "credit_transaction_id": transaction_id,
        "account_id": account_id,
        "transaction_type": "credit",
        "amount": amount,
        "currency": currency,
        "source_event_id": source_event_id,
        "status": "posted",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "request_id": request_id,
    }
    store.put_record("credit_balance", account_id, balance, tenant_id=account_id, status="active", request_id=request_id)
    store.put_record("credit_transaction", transaction_id, transaction, tenant_id=account_id, status="posted", request_id=request_id, idempotency_key=transaction_id)
    return transaction


def _job_estimated_total_cost(job: Mapping[str, Any], payload: Mapping[str, Any]) -> float:
    fallback = payload.get(
        "estimated_total_cost",
        payload.get("estimated_cost", job.get("estimated_total_cost", 0.0)),
    )
    cost_data = payload.get("cost_data", {})
    if isinstance(cost_data, Mapping):
        value = cost_data.get("estimated_total_cost", cost_data.get("amount", fallback))
    else:
        value = fallback
    return _safe_non_negative_float(value)


def _reserve_credit_for_job(
    store: ComputeMarketStoreProtocol,
    job: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    request_id: str,
) -> Mapping[str, Any]:
    amount = _job_estimated_total_cost(job, payload)
    account_id = _billing_account_id(
        payload,
        fallback_account_id=str(job.get("account_id", job.get("tenant_id", ""))).strip(),
        required=False,
    )
    if not account_id or amount <= 0:
        return {}
    currency = str(payload.get("currency", job.get("currency", "USD"))).upper()
    job_id = str(job.get("job_id", ""))
    attempt = int(job.get("attempt", 0) or 0)
    transaction_id = deterministic_id(
        "credit_transaction",
        {
            "account_id": account_id,
            "job_id": job_id,
            "attempt": attempt,
            "request_id": request_id,
            "type": "reserve",
        },
    )
    existing = store.get_record("credit_transaction", transaction_id)
    if existing is not None:
        return existing
    now = utc_now_iso()
    current = store.get_record("credit_balance", account_id) or {
        "account_id": account_id,
        "available_credits": 0.0,
        "reserved_credits": 0.0,
        "currency": currency,
        "created_at": now,
    }
    available = float(current.get("available_credits", 0.0) or 0.0)
    reserved = float(current.get("reserved_credits", 0.0) or 0.0)
    sufficient = available >= amount
    transaction = {
        "credit_transaction_id": transaction_id,
        "account_id": account_id,
        "transaction_type": "reserve",
        "amount": amount,
        "currency": currency,
        "job_id": job_id,
        "attempt": attempt,
        "status": "reserved" if sufficient else "insufficient_credit",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "request_id": request_id,
    }
    if sufficient:
        balance = {
            **dict(current),
            "account_id": account_id,
            "available_credits": round(available - amount, 6),
            "reserved_credits": round(reserved + amount, 6),
            "currency": currency,
            "updated_at": now,
        }
        store.put_record("credit_balance", account_id, balance, tenant_id=account_id, status="active", request_id=request_id)
    store.put_record(
        "credit_transaction",
        transaction_id,
        transaction,
        tenant_id=account_id,
        status=str(transaction["status"]),
        request_id=request_id,
        idempotency_key=transaction_id,
    )
    return transaction


def _release_credit_reservation(
    store: ComputeMarketStoreProtocol,
    job: Mapping[str, Any],
    *,
    request_id: str,
    reason: str,
) -> Mapping[str, Any]:
    reservation_id = str(job.get("credit_reservation_id", ""))
    if not reservation_id:
        return {}
    reservation = store.get_record("credit_transaction", reservation_id)
    if reservation is None or str(reservation.get("status", "")) != "reserved":
        return {}
    account_id = str(reservation.get("account_id", ""))
    amount = _safe_non_negative_float(reservation.get("amount", 0.0))
    if not account_id or amount <= 0:
        return {}
    release_id = deterministic_id(
        "credit_transaction",
        {"account_id": account_id, "reservation_transaction_id": reservation_id, "type": "reserve_release"},
    )
    existing = store.get_record("credit_transaction", release_id)
    if existing is not None:
        return existing
    now = utc_now_iso()
    currency = str(reservation.get("currency", "USD"))
    current = store.get_record("credit_balance", account_id) or {
        "account_id": account_id,
        "available_credits": 0.0,
        "reserved_credits": 0.0,
        "currency": currency,
        "created_at": now,
    }
    available = float(current.get("available_credits", 0.0) or 0.0)
    reserved = float(current.get("reserved_credits", 0.0) or 0.0)
    balance = {
        **dict(current),
        "account_id": account_id,
        "available_credits": round(available + amount, 6),
        "reserved_credits": round(max(0.0, reserved - amount), 6),
        "currency": currency,
        "updated_at": now,
    }
    released_reservation = {
        **dict(reservation),
        "status": "released",
        "released_at": now,
        "release_reason": reason,
        "updated_at": now,
    }
    release = {
        "credit_transaction_id": release_id,
        "account_id": account_id,
        "transaction_type": "reserve_release",
        "amount": amount,
        "currency": currency,
        "job_id": str(reservation.get("job_id", job.get("job_id", ""))),
        "reservation_transaction_id": reservation_id,
        "status": "posted",
        "reason": reason,
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "request_id": request_id,
    }
    store.put_record("credit_balance", account_id, balance, tenant_id=account_id, status="active", request_id=request_id)
    store.put_record(
        "credit_transaction",
        reservation_id,
        released_reservation,
        tenant_id=account_id,
        status="released",
        request_id=request_id,
        idempotency_key=reservation_id,
    )
    store.put_record(
        "credit_transaction",
        release_id,
        release,
        tenant_id=account_id,
        status="posted",
        request_id=request_id,
        idempotency_key=release_id,
    )
    return release

def _debit_credit(
    store: ComputeMarketStoreProtocol,
    account_id: str,
    *,
    amount: float,
    currency: str,
    request_id: str,
    usage_charge_id: str,
    reservation_transaction_id: str = "",
) -> Mapping[str, Any]:
    if not account_id or amount <= 0:
        return {}
    transaction_id = deterministic_id("credit_transaction", {"account_id": account_id, "usage_charge_id": usage_charge_id, "type": "debit"})
    existing = store.get_record("credit_transaction", transaction_id)
    if existing is not None:
        return existing
    now = utc_now_iso()
    current = store.get_record("credit_balance", account_id) or {
        "account_id": account_id,
        "available_credits": 0.0,
        "reserved_credits": 0.0,
        "currency": currency,
        "created_at": now,
    }
    reservation = store.get_record("credit_transaction", reservation_transaction_id) if reservation_transaction_id else None
    reservation_amount = (
        _safe_non_negative_float(reservation.get("amount", 0.0))
        if reservation is not None
        and str(reservation.get("status", "")) == "reserved"
        and str(reservation.get("account_id", "")) == account_id
        else 0.0
    )
    available = float(current.get("available_credits", 0.0) or 0.0)
    reserved = float(current.get("reserved_credits", 0.0) or 0.0)
    extra_due = max(0.0, amount - reservation_amount)
    unused_reservation = max(0.0, reservation_amount - amount)
    sufficient = available >= extra_due
    transaction = {
        "credit_transaction_id": transaction_id,
        "account_id": account_id,
        "transaction_type": "debit",
        "amount": amount,
        "currency": currency,
        "usage_charge_id": usage_charge_id,
        "reservation_transaction_id": reservation_transaction_id if reservation_amount else "",
        "status": "posted" if sufficient else "insufficient_credit",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "request_id": request_id,
    }
    if sufficient:
        balance = {
            **dict(current),
            "account_id": account_id,
            "available_credits": round(available - extra_due + unused_reservation, 6),
            "reserved_credits": round(max(0.0, reserved - reservation_amount), 6),
            "currency": currency,
            "updated_at": now,
        }
        store.put_record("credit_balance", account_id, balance, tenant_id=account_id, status="active", request_id=request_id)
        if reservation is not None and reservation_amount:
            settled_reservation = {
                **dict(reservation),
                "status": "settled",
                "settled_at": now,
                "settled_usage_charge_id": usage_charge_id,
                "settled_amount": amount,
                "unused_released_amount": unused_reservation,
                "updated_at": now,
            }
            store.put_record(
                "credit_transaction",
                reservation_transaction_id,
                settled_reservation,
                tenant_id=account_id,
                status="settled",
                request_id=request_id,
                idempotency_key=reservation_transaction_id,
            )
    store.put_record(
        "credit_transaction",
        transaction_id,
        transaction,
        tenant_id=account_id,
        status=str(transaction["status"]),
        request_id=request_id,
        idempotency_key=transaction_id,
    )
    return transaction


def _apply_refund_credit(
    store: ComputeMarketStoreProtocol,
    account_id: str,
    *,
    amount: float,
    currency: str,
    request_id: str,
    refund_id: str,
    usage_charge_id: str,
) -> Mapping[str, Any]:
    if not account_id or amount <= 0:
        return {}
    transaction_id = deterministic_id("credit_transaction", {"account_id": account_id, "refund_id": refund_id, "type": "refund_credit"})
    existing = store.get_record("credit_transaction", transaction_id)
    if existing is not None:
        return existing
    now = utc_now_iso()
    current = store.get_record("credit_balance", account_id) or {
        "account_id": account_id,
        "available_credits": 0.0,
        "reserved_credits": 0.0,
        "currency": currency,
        "created_at": now,
    }
    available = float(current.get("available_credits", 0.0) or 0.0) + amount
    balance = {
        **dict(current),
        "account_id": account_id,
        "available_credits": round(available, 6),
        "reserved_credits": float(current.get("reserved_credits", 0.0) or 0.0),
        "currency": currency,
        "updated_at": now,
    }
    transaction = {
        "credit_transaction_id": transaction_id,
        "account_id": account_id,
        "transaction_type": "refund_credit",
        "amount": amount,
        "currency": currency,
        "refund_id": refund_id,
        "usage_charge_id": usage_charge_id,
        "status": "posted",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": now,
        "request_id": request_id,
    }
    store.put_record("credit_balance", account_id, balance, tenant_id=account_id, status="active", request_id=request_id)
    store.put_record("credit_transaction", transaction_id, transaction, tenant_id=account_id, status="posted", request_id=request_id, idempotency_key=transaction_id)
    return transaction


def _refund_credit_transaction(store: ComputeMarketStoreProtocol, refund: Mapping[str, Any]) -> Mapping[str, Any]:
    account_id = str(refund.get("account_id", ""))
    refund_id = str(refund.get("refund_id", ""))
    usage_charge_id = str(refund.get("usage_charge_id", ""))
    if not account_id or not refund_id or not usage_charge_id:
        return {}
    transaction_id = deterministic_id("credit_transaction", {"account_id": account_id, "refund_id": refund_id, "type": "refund_credit"})
    existing = store.get_record("credit_transaction", transaction_id)
    if existing is not None:
        return existing
    debit_id = deterministic_id("credit_transaction", {"account_id": account_id, "usage_charge_id": usage_charge_id, "type": "debit"})
    debit = store.get_record("credit_transaction", debit_id)
    if debit is None or debit.get("status") != "posted":
        return {}
    return _apply_refund_credit(
        store,
        account_id,
        amount=_positive_float(refund.get("amount"), "refund.amount"),
        currency=str(refund.get("currency", "USD")),
        request_id=str(refund.get("request_id", "")),
        refund_id=refund_id,
        usage_charge_id=usage_charge_id,
    )


def _accrue_provider_payout(
    store: ComputeMarketStoreProtocol,
    *,
    provider_id: str,
    job_id: str,
    account_id: str,
    route_id: str,
    amount: float,
    currency: str,
    request_id: str,
    usage_charge_id: str,
) -> Mapping[str, Any]:
    if not provider_id or amount <= 0:
        return {}
    payout_id = deterministic_id("provider_payout", {"provider_id": provider_id, "job_id": job_id, "usage_charge_id": usage_charge_id})
    existing = store.get_record("provider_payout", payout_id)
    if existing is not None:
        return existing
    payout = {
        "provider_payout_id": payout_id,
        "provider_id": provider_id,
        "job_id": job_id,
        "account_id": account_id,
        "route_id": route_id,
        "usage_charge_id": usage_charge_id,
        "amount": amount,
        "currency": currency,
        "status": "accrued",
        "dry_run_only": True,
        "funds_moved": False,
        "created_at": utc_now_iso(),
        "request_id": request_id,
    }
    store.put_record("provider_payout", payout_id, payout, tenant_id=account_id, provider_id=provider_id, route_id=route_id, status="accrued", request_id=request_id, idempotency_key=payout_id)
    return payout


def _record_amount_total(records: tuple[Mapping[str, Any], ...]) -> float:
    return round(sum(float(record.get("amount", 0.0) or 0.0) for record in records), 6)


def _provider_payout_summary(records: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    accrued = tuple(record for record in records if str(record.get("status", "")) == "accrued")
    settled = tuple(record for record in records if str(record.get("status", "")) == "settled")
    return {
        "payout_count": len(records),
        "accrued_count": len(accrued),
        "settled_count": len(settled),
        "total_amount": _record_amount_total(records),
        "accrued_total": _record_amount_total(accrued),
        "settled_total": _record_amount_total(settled),
    }


def _billing_account(account_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "account_id": account_id,
        "tenant_id": str(payload.get("tenant_id", account_id)),
        "workspace_id": str(payload.get("workspace_id", "")),
        "status": "active",
        "billing_provider": str(payload.get("provider", "stripe")),
        "custody": "none",
        "created_at": now,
        "updated_at": now,
    }


def _verify_webhook_signature(
    raw_event: Mapping[str, Any],
    secret: str,
    signature: str,
    *,
    raw_event_body: str = "",
    tolerance_seconds: int = 300,
) -> bool:
    if not secret or not signature:
        return False
    secret_bytes = secret.encode("utf-8")
    if "v1=" in signature:
        timestamp = ""
        candidates: list[str] = []
        for item in signature.split(","):
            key, separator, value = item.partition("=")
            if not separator:
                continue
            if key == "t":
                timestamp = value
            elif key == "v1" and value:
                candidates.append(value)
        if not timestamp or not candidates or not raw_event_body:
            return False
        try:
            event_timestamp = int(timestamp)
        except ValueError:
            return False
        current_timestamp = int(datetime.now(timezone.utc).timestamp())
        if abs(current_timestamp - event_timestamp) > tolerance_seconds:
            return False
        expected = hmac.new(secret_bytes, f"{timestamp}.{raw_event_body}".encode("utf-8"), "sha256").hexdigest()
        return any(hmac.compare_digest(expected, candidate) for candidate in candidates)
    expected = hmac.new(secret_bytes, content_hash(raw_event).encode("utf-8"), "sha256").hexdigest()
    return hmac.compare_digest(expected, signature)


def _positive_float(value: object, name: str) -> float:
    try:
        amount = float(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if amount <= 0:
        raise ValueError(f"{name} must be positive")
    return amount


def _non_negative_float(value: object, name: str) -> float:
    try:
        amount = float(str(value if value not in (None, "") else 0.0))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric") from None
    if amount < 0:
        raise ValueError(f"{name} must be non-negative")
    return amount


def _assert_no_unsafe(payload: Mapping[str, Any]) -> None:
    for key, value in _walk(payload):
        if key == "settlement_mode" and str(value) in _SAFE_DRY_RUN_SETTLEMENT_MODES:
            continue
        if key in _UNSAFE_KEYS or (isinstance(value, str) and "seed phrase" in value.lower()):
            raise ValueError(f"Unsafe compute market payload rejected: {key}")
        if key in {"dry_run", "dry_run_required"} and value is False:
            raise ValueError("Flow Memory Compute Market requires dry-run payment and settlement planning by default")


def _walk(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, Mapping):
        pairs: list[tuple[str, object]] = []
        for key, child in value.items():
            pairs.append((str(key), child))
            pairs.extend(_walk(child))
        return tuple(pairs)
    if isinstance(value, (tuple, list)):
        pairs = []
        for child in value:
            pairs.extend(_walk(child))
        return tuple(pairs)
    return ()


def _tuple(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _recommended_intelligence_tier(payload: Mapping[str, Any], profile: Mapping[str, Any]) -> str:
    requested = str(payload.get("intelligence_tier") or profile.get("intelligence_tier") or "")
    if requested in {item.value for item in IntelligenceTier}:
        return requested
    estimated_value = _optional_price(payload.get("estimated_value"))
    max_latency_ms = int(float(payload.get("max_latency_ms", 0) or 0))
    if bool(payload.get("allow_background", False)):
        return IntelligenceTier.BACKGROUND_AGENT.value
    if bool(payload.get("allow_reserved_capacity", False)):
        return IntelligenceTier.RESERVED_CAPACITY.value
    if max_latency_ms and max_latency_ms <= 2_000:
        return IntelligenceTier.INSTANT.value
    if estimated_value is not None and estimated_value >= 100:
        return IntelligenceTier.PREMIUM.value
    task = str(payload.get("task") or payload.get("task_description") or "").lower()
    if "batch" in task:
        return IntelligenceTier.BATCH.value
    if any(marker in task for marker in ("research", "architecture", "competitor", "deep")):
        return IntelligenceTier.DEEP_REASONING.value
    return IntelligenceTier.STANDARD.value


def _recommended_reasoning_budget(payload: Mapping[str, Any], tier: str) -> Mapping[str, Any]:
    raw = payload.get("reasoning_budget", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    reasoning_level = str(source.get("reasoning_level") or payload.get("reasoning_level") or _default_reasoning_level(tier))
    default_steps = {
        IntelligenceTier.INSTANT.value: 2,
        IntelligenceTier.STANDARD.value: 8,
        IntelligenceTier.DEEP_REASONING.value: 32,
        IntelligenceTier.BACKGROUND_AGENT.value: 64,
        IntelligenceTier.BATCH.value: 16,
        IntelligenceTier.PREMIUM.value: 48,
        IntelligenceTier.RESERVED_CAPACITY.value: 96,
    }.get(tier, 8)
    background_runtime = int(source.get("max_background_runtime_seconds", payload.get("max_background_runtime_seconds", 3600 if tier == IntelligenceTier.BACKGROUND_AGENT.value else 0)) or 0)
    return {
        "reasoning_level": reasoning_level,
        "max_reasoning_steps": int(source.get("max_reasoning_steps", default_steps) or default_steps),
        "max_parallel_branches": int(source.get("max_parallel_branches", 4 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value, IntelligenceTier.PREMIUM.value, IntelligenceTier.RESERVED_CAPACITY.value} else 1) or 1),
        "max_reflection_passes": int(source.get("max_reflection_passes", 3 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.PREMIUM.value, IntelligenceTier.RESERVED_CAPACITY.value} else 1) or 1),
        "max_tool_calls": int(source.get("max_tool_calls", 16 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value, IntelligenceTier.RESERVED_CAPACITY.value} else 4) or 4),
        "max_wall_time_seconds": int(source.get("max_wall_time_seconds", payload.get("max_wall_time_seconds", 600 if tier != IntelligenceTier.INSTANT.value else 30)) or 60),
        "max_background_runtime_seconds": background_runtime,
        "checkpoint_interval_seconds": int(source.get("checkpoint_interval_seconds", payload.get("checkpoint_interval_seconds", 300 if background_runtime else 0)) or 0),
    }


def _default_reasoning_level(tier: str) -> str:
    if tier == IntelligenceTier.INSTANT.value:
        return "low"
    if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value, IntelligenceTier.PREMIUM.value}:
        return "high"
    if tier == IntelligenceTier.RESERVED_CAPACITY.value:
        return "extreme"
    return "medium"


def _intelligence_urgency(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = payload.get("urgency", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "run_now": bool(source.get("run_now", payload.get("run_now", True))),
        "defer_allowed": bool(source.get("defer_allowed", payload.get("defer_allowed", False))),
        "deadline": str(source.get("deadline", payload.get("deadline", ""))),
        "max_latency_ms": int(source.get("max_latency_ms", payload.get("max_latency_ms", 0)) or 0),
        "off_peak_allowed": bool(source.get("off_peak_allowed", payload.get("off_peak_allowed", False))),
    }


def _intelligence_quality_target(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = payload.get("quality_target", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "target": str(source.get("target", raw if isinstance(raw, str) else payload.get("quality_requirement", "standard"))),
        "min_confidence": float(source.get("min_confidence", 0.0) or 0.0),
        "require_audit_trail": bool(source.get("require_audit_trail", True)),
        "require_verified_provider": bool(source.get("require_verified_provider", payload.get("require_verified_provider", False))),
    }


def _intelligence_plan_payload(
    payload: Mapping[str, Any],
    tier: str,
    reasoning_budget: Mapping[str, Any],
    urgency: Mapping[str, Any],
    quality_target: Mapping[str, Any],
) -> Mapping[str, Any]:
    plan_payload = dict(payload)
    max_spend = _max_recommended_spend(payload, tier, _optional_price(payload.get("estimated_value")))
    policy = dict(plan_payload.get("policy", {})) if isinstance(plan_payload.get("policy"), Mapping) else {}
    policy.setdefault("max_total_cost", max_spend)
    policy.setdefault("max_latency_ms", int(urgency.get("max_latency_ms", 0) or payload.get("max_latency_ms", 0) or 0))
    policy.setdefault("dry_run_required", True)
    policy.setdefault("require_verified_provider", bool(quality_target.get("require_verified_provider", False)))
    if tier in {IntelligenceTier.RESERVED_CAPACITY.value, IntelligenceTier.BACKGROUND_AGENT.value}:
        policy.setdefault("require_capacity_confirmation", bool(payload.get("allow_reserved_capacity", tier == IntelligenceTier.RESERVED_CAPACITY.value)))
    plan_payload["policy"] = policy
    plan_payload["selection_strategy"] = str(payload.get("selection_strategy") or _selection_strategy_for_tier(tier))
    if not plan_payload.get("provider_constraints") and not plan_payload.get("provider_class") and not plan_payload.get("provider_class_constraints"):
        plan_payload["preferred_provider_classes"] = _recommended_provider_classes(tier)
    plan_payload["quality_requirement"] = str(quality_target.get("target", "standard"))
    plan_payload["reasoning_budget"] = reasoning_budget
    plan_payload["intelligence_tier"] = tier
    plan_payload["dry_run"] = True
    return plan_payload


def _selection_strategy_for_tier(tier: str) -> str:
    if tier == IntelligenceTier.INSTANT.value:
        return "best_latency"
    if tier == IntelligenceTier.BATCH.value:
        return "lowest_cost"
    if tier in {IntelligenceTier.RESERVED_CAPACITY.value, IntelligenceTier.BACKGROUND_AGENT.value}:
        return "capacity_guaranteed"
    if tier == IntelligenceTier.PREMIUM.value:
        return "reliability_weighted"
    if tier == IntelligenceTier.DEEP_REASONING.value:
        return "best_roi"
    return "balanced"


def _recommended_route_types(tier: str, payload: Mapping[str, Any]) -> tuple[str, ...]:
    if tier == IntelligenceTier.INSTANT.value:
        return ("direct", "token", "local")
    if tier == IntelligenceTier.BATCH.value:
        return ("batch_job", "gpu_minute", "marketplace")
    if tier == IntelligenceTier.DEEP_REASONING.value:
        return ("agent_runtime", "gpu_minute", "marketplace", "reserved_capacity")
    if tier == IntelligenceTier.BACKGROUND_AGENT.value:
        return ("background_agent", "reserved_capacity", "gpu_minute", "batch_job")
    if tier == IntelligenceTier.RESERVED_CAPACITY.value or bool(payload.get("allow_reserved_capacity", False)):
        return ("reserved_capacity", "gpu_hour", "reserved_capacity_slot")
    if tier == IntelligenceTier.PREMIUM.value:
        return ("reasoning_model", "marketplace", "reserved_capacity")
    return ("request", "token", "marketplace")


def _recommended_provider_classes(tier: str) -> tuple[str, ...]:
    if tier == IntelligenceTier.INSTANT.value:
        return (
            ProviderClass.SMALL_MODEL.value,
            ProviderClass.LOCAL_RUNTIME.value,
            ProviderClass.FOUNDATIONAL_MODEL.value,
        )
    if tier == IntelligenceTier.BATCH.value:
        return (
            ProviderClass.BATCH_INFERENCE.value,
            ProviderClass.GPU_CLUSTER.value,
            ProviderClass.MARKETPLACE_POOL.value,
        )
    if tier == IntelligenceTier.DEEP_REASONING.value:
        return (
            ProviderClass.REASONING_MODEL.value,
            ProviderClass.AGENT_RUNTIME.value,
            ProviderClass.GPU_CLUSTER.value,
            ProviderClass.RESERVED_CAPACITY_POOL.value,
            ProviderClass.MARKETPLACE_POOL.value,
        )
    if tier == IntelligenceTier.BACKGROUND_AGENT.value:
        return (
            ProviderClass.AGENT_RUNTIME.value,
            ProviderClass.GPU_CLUSTER.value,
            ProviderClass.RESERVED_CAPACITY_POOL.value,
            ProviderClass.BATCH_INFERENCE.value,
        )
    if tier == IntelligenceTier.RESERVED_CAPACITY.value:
        return (ProviderClass.RESERVED_CAPACITY_POOL.value,)
    if tier == IntelligenceTier.PREMIUM.value:
        return (
            ProviderClass.REASONING_MODEL.value,
            ProviderClass.AGENT_RUNTIME.value,
            ProviderClass.MARKETPLACE_POOL.value,
        )
    return (
        ProviderClass.FOUNDATIONAL_MODEL.value,
        ProviderClass.SMALL_MODEL.value,
        ProviderClass.MARKETPLACE_POOL.value,
        ProviderClass.LOCAL_RUNTIME.value,
    )

def _max_recommended_spend(payload: Mapping[str, Any], tier: str, estimated_value: float | None) -> float:
    explicit_budget = _optional_price(payload.get("budget", payload.get("max_total_cost", None)))
    if explicit_budget is not None and explicit_budget > 0:
        return round(explicit_budget, 6)
    value = float(estimated_value or 0.0)
    if value <= 0:
        return {
            IntelligenceTier.INSTANT.value: 0.05,
            IntelligenceTier.STANDARD.value: 0.5,
            IntelligenceTier.DEEP_REASONING.value: 5.0,
            IntelligenceTier.BACKGROUND_AGENT.value: 10.0,
            IntelligenceTier.BATCH.value: 2.0,
            IntelligenceTier.PREMIUM.value: 15.0,
            IntelligenceTier.RESERVED_CAPACITY.value: 25.0,
        }.get(tier, 1.0)
    multiplier = {
        IntelligenceTier.INSTANT.value: 0.01,
        IntelligenceTier.STANDARD.value: 0.05,
        IntelligenceTier.DEEP_REASONING.value: 0.2,
        IntelligenceTier.BACKGROUND_AGENT.value: 0.2,
        IntelligenceTier.BATCH.value: 0.08,
        IntelligenceTier.PREMIUM.value: 0.3,
        IntelligenceTier.RESERVED_CAPACITY.value: 0.35,
    }.get(tier, 0.05)
    return round(max(0.01, value * multiplier), 6)


def _intelligence_run_decision(
    payload: Mapping[str, Any],
    tier: str,
    reasoning_budget: Mapping[str, Any],
    urgency: Mapping[str, Any],
    compute_plan: Mapping[str, Any],
    price_context: Mapping[str, Any],
) -> str:
    fail_closed = tuple(str(item) for item in compute_plan.get("fail_closed_errors", ()) if str(item))
    if fail_closed:
        if any("capacity" in reason for reason in fail_closed) and bool(payload.get("allow_reserved_capacity", False)):
            return RunDecision.RESERVE_CAPACITY.value
        if any(reason in {"budget_exceeded", "unit_price_exceeded"} for reason in fail_closed):
            return RunDecision.DOWNGRADE_TIER.value
        return RunDecision.REJECT_NEGATIVE_ROI.value
    quote = compute_plan.get("normalized_quote", {}) if isinstance(compute_plan.get("normalized_quote"), Mapping) else {}
    estimated_cost = _optional_price(quote.get("estimated_total_cost")) or 0.0
    estimated_value = _optional_price(payload.get("estimated_value"))
    approval_threshold = float(payload.get("require_human_approval_above", 0.0) or 0.0)
    if approval_threshold > 0 and estimated_cost > approval_threshold and not bool(payload.get("human_approval_granted", False)):
        return RunDecision.REQUIRE_HUMAN_APPROVAL.value
    if estimated_value is not None and estimated_value >= 0 and estimated_cost > estimated_value:
        return RunDecision.REJECT_NEGATIVE_ROI.value
    max_spend = _max_recommended_spend(payload, tier, estimated_value)
    if estimated_cost > max_spend and tier not in {IntelligenceTier.INSTANT.value, IntelligenceTier.STANDARD.value}:
        return RunDecision.DOWNGRADE_TIER.value
    if bool(urgency.get("defer_allowed", False)) and bool(price_context.get("price_above_history", False)):
        return RunDecision.DEFER_UNTIL_CHEAPER.value
    if tier == IntelligenceTier.RESERVED_CAPACITY.value or (
        bool(payload.get("allow_reserved_capacity", False)) and str(quote.get("market_type", "")) == "reserved_capacity"
    ):
        return RunDecision.RESERVE_CAPACITY.value
    if str(reasoning_budget.get("reasoning_level", "")) == "extreme" and estimated_cost > 0 and not bool(payload.get("human_approval_granted", False)):
        return RunDecision.REQUIRE_HUMAN_APPROVAL.value
    return RunDecision.RUN_NOW.value


def _defer_until(payload: Mapping[str, Any], urgency: Mapping[str, Any], run_decision: str) -> str:
    if run_decision != RunDecision.DEFER_UNTIL_CHEAPER.value:
        return ""
    explicit = str(payload.get("defer_until") or payload.get("next_best_window") or "")
    if explicit:
        return explicit
    deadline = str(urgency.get("deadline", ""))
    if deadline:
        return deadline
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _downgrade_options(tier: str, compute_plan: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if tier in {IntelligenceTier.INSTANT.value, IntelligenceTier.STANDARD.value}:
        return ()
    quote = compute_plan.get("normalized_quote", {}) if isinstance(compute_plan.get("normalized_quote"), Mapping) else {}
    cost = _optional_price(quote.get("estimated_total_cost")) or 0.0
    return (
        {"intelligence_tier": IntelligenceTier.STANDARD.value, "reasoning_level": "medium", "estimated_cost_cap": round(max(0.01, cost * 0.5), 6)},
        {"intelligence_tier": IntelligenceTier.INSTANT.value, "reasoning_level": "low", "estimated_cost_cap": round(max(0.01, cost * 0.2), 6)},
    )


def _intelligence_rationale(tier: str, run_decision: str, compute_plan: Mapping[str, Any], price_context: Mapping[str, Any]) -> tuple[str, ...]:
    reasons = [f"tier={tier}", f"run_decision={run_decision}"]
    if bool(compute_plan.get("ok", False)):
        selected = compute_plan.get("selected_route", {}) if isinstance(compute_plan.get("selected_route"), Mapping) else {}
        reasons.append(f"selected_route={selected.get('route_id', '')}")
    else:
        reasons.append("planner_fail_closed")
    if price_context.get("median_unit_price") is not None:
        reasons.append(f"price_ratio={float(price_context.get('ratio_to_median', 0.0) or 0.0):.3f}")
    return tuple(reasons)


def _intelligence_next_safe_actions(run_decision: str, compute_plan: Mapping[str, Any]) -> tuple[str, ...]:
    base = tuple(str(item) for item in compute_plan.get("next_safe_actions", ()) if str(item))
    if run_decision == RunDecision.DEFER_UNTIL_CHEAPER.value:
        return ("wait for the next cheaper capacity window before dispatch", *base)
    if run_decision == RunDecision.DOWNGRADE_TIER.value:
        return ("retry with a lower intelligence tier or smaller reasoning budget", *base)
    if run_decision == RunDecision.REQUIRE_HUMAN_APPROVAL.value:
        return ("obtain explicit human approval before spending this reasoning budget", *base)
    if run_decision == RunDecision.RESERVE_CAPACITY.value:
        return ("hold or confirm reserved capacity before background execution", *base)
    if run_decision == RunDecision.REJECT_NEGATIVE_ROI.value:
        return ("do not run until expected task value exceeds estimated intelligence cost", *base)
    return ("run using dry-run compute planning; no funds moved", *base)


def _price_snapshot_from_quote(quote: Mapping[str, Any]) -> ComputePriceSnapshot:
    created_at = utc_now_iso()
    stable = {
        "quote_id": str(quote.get("quote_id", "")),
        "provider_id": str(quote.get("provider_id", "")),
        "route_id": str(quote.get("route_id", "")),
        "unit_type": str(quote.get("unit_type", "")),
        "unit_price": _optional_price(quote.get("unit_price")),
        "created_at": created_at,
    }
    return ComputePriceSnapshot(
        price_snapshot_id=deterministic_id("price_snapshot", stable),
        provider_id=str(quote.get("provider_id", "")),
        route_id=str(quote.get("route_id", "")),
        unit_type=str(quote.get("unit_type", "")),
        unit_price=_optional_price(quote.get("unit_price")),
        payment_asset=str(quote.get("payment_asset", quote.get("currency_or_asset", ""))),
        network=str(quote.get("network", "")),
        latency_ms=int(float(quote.get("estimated_latency_ms", 0) or 0)),
        reliability_score=float(quote.get("reliability_score", quote.get("confidence", 0.0)) or 0.0),
        capacity_available=bool(quote.get("capacity_available", True)),
        market_type=str(quote.get("market_type", "")),
        quote_source=str(quote.get("source", quote.get("quote_source", ""))),
        confidence=float(quote.get("confidence", 1.0) or 1.0),
        created_at=created_at,
        tenant_id=str(quote.get("tenant_id", "")),
        workspace_id=str(quote.get("workspace_id", "")),
        quote_id=str(quote.get("quote_id", "")),
        task_hash=str(quote.get("task_hash", "")),
    )


def _price_filters(payload: Mapping[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key in ("tenant_id", "workspace_id", "provider_id", "route_id", "task_hash"):
        value = payload.get(key)
        if value not in (None, ""):
            filters[key] = value
    unit_type = payload.get("unit_type", payload.get("task_type", ""))
    if unit_type not in (None, ""):
        filters["task_type"] = str(unit_type)
    return filters


def _quote_price_filter(quote: Mapping[str, Any]) -> Mapping[str, Any]:
    if not quote:
        return {}
    return {
        "provider_id": str(quote.get("provider_id", "")),
        "route_id": str(quote.get("route_id", "")),
        "unit_type": str(quote.get("unit_type", "")),
        "tenant_id": str(quote.get("tenant_id", "")),
        "workspace_id": str(quote.get("workspace_id", "")),
    }


def _price_groups(snapshots: tuple[Mapping[str, Any], ...], key: str) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for snapshot in snapshots:
        group_key = f"{snapshot.get(key, '')}:{snapshot.get('unit_type', '')}"
        groups.setdefault(group_key, []).append(snapshot)
    return tuple(tuple(group) for group in groups.values())


def _route_price_index(group: tuple[Mapping[str, Any], ...]) -> RoutePriceIndex:
    latest = group[-1]
    prices = _prices(group)
    return RoutePriceIndex(
        route_id=str(latest.get("route_id", "")),
        provider_id=str(latest.get("provider_id", "")),
        unit_type=str(latest.get("unit_type", "")),
        latest_unit_price=_optional_price(latest.get("unit_price")),
        median_unit_price=_median(prices),
        sample_count=len(prices),
        payment_asset=str(latest.get("payment_asset", "")),
        network=str(latest.get("network", "")),
        created_at=utc_now_iso(),
    )


def _provider_price_index(group: tuple[Mapping[str, Any], ...]) -> ProviderPriceIndex:
    latest = group[-1]
    prices = _prices(group)
    return ProviderPriceIndex(
        provider_id=str(latest.get("provider_id", "")),
        unit_type=str(latest.get("unit_type", "")),
        latest_unit_price=_optional_price(latest.get("unit_price")),
        median_unit_price=_median(prices),
        sample_count=len(prices),
        payment_asset=str(latest.get("payment_asset", "")),
        network=str(latest.get("network", "")),
        created_at=utc_now_iso(),
    )


def _prices(records: tuple[Mapping[str, Any], ...]) -> tuple[float, ...]:
    return tuple(price for price in (_optional_price(record.get("unit_price")) for record in records) if price is not None)


def _median(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _median_price_for_snapshot(snapshot: Mapping[str, Any], snapshots: tuple[Mapping[str, Any], ...]) -> float | None:
    comparable = tuple(
        item
        for item in snapshots
        if str(item.get("provider_id", "")) == str(snapshot.get("provider_id", ""))
        and str(item.get("route_id", "")) == str(snapshot.get("route_id", ""))
        and str(item.get("unit_type", "")) == str(snapshot.get("unit_type", ""))
    )
    return _median(_prices(comparable))


def _price_is_anomalous(snapshot: Mapping[str, Any], median: float | None) -> bool:
    price = _optional_price(snapshot.get("unit_price"))
    if price is None or median is None or median <= 0:
        return False
    ratio = price / median
    return ratio >= 2.5 or ratio <= 0.4


def _price_anomaly(snapshot: Mapping[str, Any], median: float | None) -> PriceAnomaly:
    price = _optional_price(snapshot.get("unit_price")) or 0.0
    baseline = median or price or 1.0
    ratio = price / baseline if baseline else 0.0
    return PriceAnomaly(
        anomaly_id=deterministic_id("price_anomaly", {"snapshot": snapshot.get("price_snapshot_id", ""), "ratio": ratio}),
        provider_id=str(snapshot.get("provider_id", "")),
        route_id=str(snapshot.get("route_id", "")),
        unit_type=str(snapshot.get("unit_type", "")),
        unit_price=price,
        median_unit_price=baseline,
        ratio_to_median=round(ratio, 6),
        direction="above_median" if ratio >= 1 else "below_median",
        severity="review" if 2.5 <= ratio < 5.0 or 0.2 < ratio <= 0.4 else "critical",
        created_at=utc_now_iso(),
    )


def _price_forecast(payload: Mapping[str, Any], snapshots: tuple[Mapping[str, Any], ...]) -> PriceForecast:
    prices = _prices(snapshots)
    forecast = _median(prices)
    return PriceForecast(
        forecast_id=deterministic_id("price_forecast", {"payload": payload, "count": len(prices), "median": forecast}),
        provider_id=str(payload.get("provider_id", "")),
        route_id=str(payload.get("route_id", "")),
        unit_type=str(payload.get("unit_type", payload.get("task_type", ""))),
        forecast_unit_price=forecast,
        confidence=min(1.0, len(prices) / 10.0) if prices else 0.0,
        sample_count=len(prices),
        horizon_seconds=int(payload.get("horizon_seconds", 3600) or 3600),
        created_at=utc_now_iso(),
    )


def _optional_price(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _ratio(value: float | None, baseline: float | None) -> float:
    if value is None or baseline is None or baseline == 0:
        return 1.0
    return round(value / baseline, 6)


def _intelligence_usage_record(intelligence_plan: Mapping[str, Any], compute_plan: Mapping[str, Any]) -> IntelligenceUsageRecord:
    quote = compute_plan.get("normalized_quote", {}) if isinstance(compute_plan.get("normalized_quote"), Mapping) else {}
    profile = compute_plan.get("profile", {}) if isinstance(compute_plan.get("profile"), Mapping) else {}
    metered_units = _metered_units(profile, intelligence_plan.get("recommended_reasoning_budget", {}))
    estimated_cost = _optional_price(quote.get("estimated_total_cost")) or 0.0
    estimated_value = _optional_price(profile.get("estimated_value"))
    roi = round(estimated_value / estimated_cost, 6) if estimated_value is not None and estimated_cost > 0 else 0.0
    return IntelligenceUsageRecord(
        usage_record_id=deterministic_id("intelligence_usage", {"plan": intelligence_plan.get("intelligence_plan_id", ""), "decision": compute_plan.get("decision_id", "")}),
        workspace_id=str(profile.get("workspace_id", intelligence_plan.get("workspace_id", ""))),
        tenant_id=str(profile.get("tenant_id", intelligence_plan.get("tenant_id", ""))),
        agent_id=str(profile.get("agent_id", intelligence_plan.get("agent_id", ""))),
        goal_id=str(profile.get("goal_id", intelligence_plan.get("goal_id", ""))),
        task_id=str(profile.get("task_id", intelligence_plan.get("task_id", ""))),
        intelligence_tier=str(intelligence_plan.get("recommended_intelligence_tier", "")),
        reasoning_level=str((intelligence_plan.get("recommended_reasoning_budget", {}) or {}).get("reasoning_level", "")) if isinstance(intelligence_plan.get("recommended_reasoning_budget", {}), Mapping) else "",
        metered_units=metered_units,
        estimated_cost=estimated_cost,
        actual_cost=None,
        estimated_value=estimated_value,
        task_roi=roi,
        selected_route=str(quote.get("route_id", "")),
        provider_id=str(quote.get("provider_id", "")),
        route_id=str(quote.get("route_id", "")),
        background_runtime_seconds=int(metered_units.get("background_runtime_seconds", 0.0)),
        created_at=utc_now_iso(),
        request_id=str(intelligence_plan.get("request_id", "")),
        decision_id=str(compute_plan.get("decision_id", "")),
    )


def _metered_units(profile: Mapping[str, Any], reasoning_budget: object) -> Mapping[str, float]:
    estimated_units = profile.get("estimated_units", {})
    units: dict[str, float] = {}
    if isinstance(estimated_units, Mapping):
        for key, value in estimated_units.items():
            price = _optional_price(value)
            if price is not None:
                units[str(key)] = price
    budget = reasoning_budget if isinstance(reasoning_budget, Mapping) else {}
    units.setdefault("agent_steps", float(budget.get("max_reasoning_steps", 0) or 0))
    units.setdefault("tool_calls", float(budget.get("max_tool_calls", 0) or 0))
    units.setdefault("parallel_branches", float(budget.get("max_parallel_branches", 0) or 0))
    units.setdefault("background_runtime_seconds", float(budget.get("max_background_runtime_seconds", 0) or 0))
    return units


def _usage_filters(payload: Mapping[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key in ("tenant_id", "workspace_id", "agent_id", "goal_id", "provider_id", "route_id", "task_hash"):
        value = payload.get(key)
        if value not in (None, ""):
            filters[key] = value
    return filters


def _usage_summary(records: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    estimated = sum(float(record.get("estimated_cost", 0.0) or 0.0) for record in records)
    actual = sum(float(record.get("actual_cost", record.get("estimated_cost", 0.0)) or 0.0) for record in records)
    return {
        "record_count": len(records),
        "total_estimated_cost": round(estimated, 6),
        "total_actual_cost": round(actual, 6),
        "highest_roi_agent": _highest_roi_agent(records),
        "waste_detected": _waste_detected(records),
    }


def _highest_roi_agent(records: tuple[Mapping[str, Any], ...]) -> str:
    best_agent = ""
    best_roi = float("-inf")
    for record in records:
        roi = float(record.get("task_roi", 0.0) or 0.0)
        if roi > best_roi:
            best_roi = roi
            best_agent = str(record.get("agent_id", ""))
    return best_agent


def _waste_detected(records: tuple[Mapping[str, Any], ...]) -> float:
    waste = 0.0
    for record in records:
        actual = float(record.get("actual_cost", record.get("estimated_cost", 0.0)) or 0.0)
        value = _optional_price(record.get("estimated_value"))
        if value is not None and actual > value:
            waste += actual - value
    return round(waste, 6)


def _compute_statement(records: tuple[Mapping[str, Any], ...], *, workspace_id: str, period: str) -> ComputeStatement:
    summary = _usage_summary(records)
    return ComputeStatement(
        statement_id=deterministic_id("compute_statement", {"workspace_id": workspace_id, "period": period}),
        workspace_id=workspace_id,
        period=period,
        total_estimated_cost=float(summary["total_estimated_cost"]),
        total_actual_cost=float(summary["total_actual_cost"]),
        record_count=int(summary["record_count"]),
        highest_roi_agent=str(summary["highest_roi_agent"]),
        waste_detected=float(summary["waste_detected"]),
        recommended_budget_changes=(),
        created_at=utc_now_iso(),
    )



def _redis_rate_limit_probe(limiter: RateLimiter, *, request_id: str, redis_prefix: str) -> Mapping[str, Any]:
    if not isinstance(limiter, RedisRateLimiter):
        return {"ok": False, "skipped": True, "reason": "redis_rate_limiter_not_configured"}
    probe = RedisRateLimiter(
        limiter.redis_url,
        prefix=f"{redis_prefix}:diagnostic:{request_id}",
        default_limit=1,
        window_seconds=30,
        fail_closed=limiter.fail_closed,
        client=limiter.client,
    )
    first = probe.check_limit("diagnostic-actor", "GET /admin/redis/diagnostics")
    second = probe.check_limit("diagnostic-actor", "GET /admin/redis/diagnostics")
    status = probe.get_status("diagnostics")
    return {
        "ok": bool(status.get("configured")) and first.ok is True and second.ok is False and second.reason_code == "rate_limited",
        "backend": "redis",
        "configured": bool(status.get("configured")),
        "first": first.as_record(),
        "second": second.as_record(),
        "fail_closed": limiter.fail_closed,
    }


def _redis_circuit_probe(breaker: CircuitBreaker, *, request_id: str, redis_prefix: str) -> Mapping[str, Any]:
    if not isinstance(breaker, RedisCircuitBreaker):
        return {"ok": False, "skipped": True, "reason": "redis_circuit_breaker_not_configured"}
    probe = RedisCircuitBreaker(
        breaker.redis_url,
        prefix=f"{redis_prefix}:diagnostic:{request_id}",
        failure_threshold=1,
        reset_after_seconds=30,
        fail_closed=breaker.fail_closed,
        client=breaker.client,
    )
    provider_id = "diagnostic-provider"
    before = probe.allow_request(provider_id, adapter_type="diagnostics")
    probe.record_failure(provider_id, adapter_type="diagnostics", error_class="diagnostic_failure")
    opened = probe.allow_request(provider_id, adapter_type="diagnostics")
    probe.reset(provider_id, adapter_type="diagnostics")
    recovered = probe.allow_request(provider_id, adapter_type="diagnostics")
    status = probe.get_state(provider_id, adapter_type="diagnostics")
    return {
        "ok": bool(status.get("configured")) and before.ok is True and opened.ok is False and opened.reason_code == "circuit_open" and recovered.ok is True,
        "backend": "redis",
        "configured": bool(status.get("configured")),
        "before": before.as_record(),
        "opened": opened.as_record(),
        "recovered": recovered.as_record(),
        "fail_closed": breaker.fail_closed,
    }

def _log_fields(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    selected = plan.get("selected_route", {}) if isinstance(plan.get("selected_route"), Mapping) else {}
    quote = plan.get("normalized_quote", {}) if isinstance(plan.get("normalized_quote"), Mapping) else {}
    return {
        "request_id": plan.get("request_id", ""),
        "decision_id": plan.get("decision_id", ""),
        "agent_id": (plan.get("profile", {}) or {}).get("agent_id", "") if isinstance(plan.get("profile"), Mapping) else "",
        "goal_id": (plan.get("profile", {}) or {}).get("goal_id", "") if isinstance(plan.get("profile"), Mapping) else "",
        "provider_id": selected.get("provider_id", ""),
        "route_id": selected.get("route_id", ""),
        "policy_id": (plan.get("policy_trace", {}) or {}).get("policy_id", "") if isinstance(plan.get("policy_trace"), Mapping) else "",
        "strategy": (plan.get("route_decision", {}) or {}).get("strategy", "") if isinstance(plan.get("route_decision"), Mapping) else "",
        "result": plan.get("policy_result", ""),
        "rejected_reason_codes": tuple(plan.get("fail_closed_errors", ())),
        "estimated_total_cost": quote.get("estimated_total_cost", 0.0),
        "dry_run_only": True,
    }
