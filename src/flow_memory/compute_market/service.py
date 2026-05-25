"""Production-planning service layer for Flow Memory Compute Market."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from flow_memory.compute_market.config import ComputeMarketConfig, config_from_env
from flow_memory.compute_market.audit_export import LocalFileAuditExporter, build_checkpoint, verify_audit_export
from flow_memory.compute_market.controls import CircuitBreaker, RateLimiter, create_circuit_breaker, create_rate_limiter
from flow_memory.compute_market.errors import compute_error, policy_denial_error
from flow_memory.compute_market.memory import query_economic_memory_typed, query_request_from_payload
from flow_memory.compute_market.models import (
    AuditEvent,
    ComputeMarketHealth,
    ComputeMarketPolicy,
    ComputeProvider,
    ProviderHealthSnapshot,
)
from flow_memory.compute_market.observability import ComputeMarketTelemetry
from flow_memory.compute_market.planner import build_compute_plan, replay_decision
from flow_memory.compute_market.registry import default_compute_providers, default_compute_routes
from flow_memory.compute_market.storage import deterministic_id, migration_plan, utc_now_iso
from flow_memory.compute_market.storage_backends import ComputeMarketStoreProtocol, create_compute_market_store
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
        "broadcast",
        "broadcast_allowed",
        "sendTransaction",
        "signTransaction",
        "custody",
        "transfer",
        "withdraw",
        "deposit",
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
    ) -> None:
        self.config = config or config_from_env()
        errors = self.config.validate()
        if errors:
            raise ValueError("; ".join(errors))
        self.store = store or create_compute_market_store(self.config)
        self.telemetry = telemetry or ComputeMarketTelemetry()
        self.rate_limiter = rate_limiter or create_rate_limiter(self.config)
        self.circuit_breaker = circuit_breaker or create_circuit_breaker(self.config)
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

    def get_provider(self, provider_id: str) -> Mapping[str, Any]:
        provider = self.store.get_record("compute_provider", provider_id)
        if provider is None:
            raise KeyError(f"Unknown compute provider: {provider_id}")
        return {"ok": True, "provider": provider}

    def create_provider(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "POST /compute/providers", request_id=_request_id(payload), provider_id=str(payload.get("provider_id", "")))
        if limited is not None:
            return limited
        provider_id = str(payload.get("provider_id") or deterministic_id("provider", payload))
        provider = {**dict(payload), "provider_id": provider_id, "status": str(payload.get("status", "active"))}
        self.store.put_record("compute_provider", provider_id, provider, provider_id=provider_id, status=str(provider["status"]))
        self._audit("compute.provider.created", payload, result="created", provider_id=provider_id)
        return {"ok": True, "provider": provider}

    def update_provider(self, provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _assert_no_unsafe(payload)
        limited = self._rate_limit_response(payload, "PATCH /compute/providers/{provider_id}", request_id=_request_id(payload), provider_id=provider_id)
        if limited is not None:
            return limited
        current = dict(self.get_provider(provider_id)["provider"])
        updated = {**current, **dict(payload), "provider_id": provider_id}
        self.store.put_record("compute_provider", provider_id, updated, provider_id=provider_id, status=str(updated.get("status", "")))
        self._audit("compute.provider.updated", payload, result="updated", provider_id=provider_id)
        return {"ok": True, "provider": updated}

    def disable_provider(self, provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        payload = payload or {}
        limited = self._rate_limit_response(payload, "POST /compute/providers/{provider_id}/disable", request_id=_request_id(payload), provider_id=provider_id)
        if limited is not None:
            return limited
        current = dict(self.get_provider(provider_id)["provider"])
        current["status"] = "disabled"
        current["disabled_at"] = utc_now_iso()
        self.store.put_record("compute_provider", provider_id, current, provider_id=provider_id, status="disabled")
        self._audit("compute.provider.disabled", payload, result="disabled", provider_id=provider_id)
        return {"ok": True, "provider": current}

    def provider_health(self, provider_id: str) -> Mapping[str, Any]:
        limited = self._rate_limit_response({}, "POST /compute/providers/{provider_id}/health-check", request_id=new_id("request"), provider_id=provider_id)
        if limited is not None:
            return limited
        circuit = self.circuit_breaker.allow_request(provider_id, adapter_type="health_check")
        if not circuit.ok:
            self._audit("compute.provider.circuit_open", {"provider_id": provider_id}, request_id=new_id("request"), result="skipped", reason_codes=("circuit_open",), provider_id=provider_id)
            return {
                "ok": False,
                "provider_health": {
                    "provider_id": provider_id,
                    "status": "temporarily_disabled",
                    "error_code": "circuit_open",
                    "circuit": circuit.as_record(),
                },
            }
        provider = self.get_provider(provider_id)["provider"]
        routes = tuple(route for route in self.store.list_records("compute_route", filters={"provider_id": provider_id}).records)
        snapshot = ProviderHealthSnapshot(
            health_snapshot_id=deterministic_id("provider_health", {"provider_id": provider_id, "created_at": utc_now_iso()}),
            provider_id=provider_id,
            status="healthy" if provider.get("status") == "active" else "disabled",
            reliability_score=float(provider.get("reliability_score", 0.0) or 0.0),
            latency_ms=int(provider.get("average_latency_ms", 0) or 0),
            route_count=len(routes),
            rate_limits=provider.get("rate_limit_profile", {}) if isinstance(provider.get("rate_limit_profile"), Mapping) else {},
        )
        record = snapshot.as_record()
        self.store.put_record("provider_health_snapshot", snapshot.health_snapshot_id, record, provider_id=provider_id, status=snapshot.status)
        return {"ok": True, "provider_health": record}

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
        limited = self._rate_limit_response(payload, "POST /compute/routes/{route_id}/disable", request_id=_request_id(payload), route_id=route_id)
        if limited is not None:
            return limited
        current = dict(self.get_route(route_id)["route"])
        current["enabled"] = False
        current["disabled_at"] = utc_now_iso()
        self.store.put_record("compute_route", route_id, current, provider_id=str(current.get("provider_id", "")), route_id=route_id, status="disabled")
        self._audit("compute.route.disabled", payload, result="disabled", route_id=route_id)
        return {"ok": True, "route": current}

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
        self._audit(
            "compute.audit.verified",
            payload or {},
            result="completed" if ok else "failed",
            reason_codes=() if ok else (str(result.get("error_code", "audit_chain_invalid")),),
        )
        return {"ok": ok, "audit_chain": result}
    def audit_export(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        out = str(payload.get("out") or payload.get("path") or "")
        if not out:
            raise ValueError("audit export requires --out/path")
        exporter = LocalFileAuditExporter(Path(out))
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
        exporter.write_checkpoint(result.checkpoint)
        self._audit("compute.audit.exported", payload, result="completed", reason_codes=())
        return result.as_record()

    def audit_checkpoint(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        chain_id = str(payload.get("chain_id", "all") or "all")
        events = tuple(self.audit({"limit": 500}).get("audit_events", ()))
        if chain_id not in {"", "all"}:
            events = tuple(event for event in events if isinstance(event, Mapping) and str(event.get("chain_id", "")) == chain_id)
        checkpoint = build_checkpoint(
            tuple(event for event in events if isinstance(event, Mapping)),
            chain_id=chain_id,
            from_sequence=1,
            to_sequence=0,
            export_uri=str(payload.get("out", "")),
            exported_to="checkpoint_only",
        )
        self._audit("compute.audit.checkpointed", payload, result="completed", reason_codes=())
        return {"ok": True, "checkpoint": checkpoint.as_record()}

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
        if self.config.audit_export_required and not self.config.audit_export_uri:
            failures.append("audit_export_unavailable")
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
        ready = not failures and bool(health.get("compute_market_enabled"))
        health["ready"] = ready
        health["ok"] = ready
        health["readiness_failures"] = tuple(dict.fromkeys(failures))
        health["migration_status"] = migration_status
        health["migration_plan"] = migration_plan()
        health["audit_chain"] = audit_chain
        health["production_safety_defaults"] = self.config.as_record()
        return health

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
        self._audit(
            "compute.provider.circuit_open",
            payload,
            request_id=request_id,
            result="skipped",
            reason_codes=("circuit_open",),
        )
        return {**dict(payload), "policy": policy, "circuit_open_providers": open_providers}

    def _open_circuit_provider_ids(self) -> tuple[str, ...]:
        open_ids = getattr(self.circuit_breaker, "open_provider_ids", None)
        if callable(open_ids):
            return tuple(str(provider_id) for provider_id in open_ids())
        return ()

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


def _assert_no_unsafe(payload: Mapping[str, Any]) -> None:
    for key, value in _walk(payload):
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
