"""Flow Memory Compute Market API endpoint handlers."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.compute_market import simulation_catalog
from flow_memory.compute_market.memory import economic_memory_schema
from flow_memory.compute_market.models import ComputeMarketPolicy, SelectionStrategy
from flow_memory.compute_market.registry import metadata_registry
from flow_memory.compute_market.service import default_service
from flow_memory.compute_market.storage import migration_plan


def compute_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().plan(payload)


def compute_marketplace_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().marketplace_plan(payload)


def compute_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().quote(payload)


def compute_route(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().route(payload)


def compute_payment_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().payment_plan(payload)


def compute_simulate_settlement(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().simulate_settlement(payload)


def compute_providers(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    result = default_service().list_providers(payload or {})
    return {**result, "registry": metadata_registry()}


def compute_provider(provider_id: str) -> Mapping[str, Any]:
    return default_service().get_provider(provider_id)


def compute_provider_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().create_provider(payload)


def compute_provider_update(provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().update_provider(provider_id, payload)


def compute_provider_disable(provider_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().disable_provider(provider_id, payload)


def compute_provider_health(provider_id: str) -> Mapping[str, Any]:
    return default_service().provider_health(provider_id)


def compute_routes(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().list_routes(payload or {})


def compute_route_get(route_id: str) -> Mapping[str, Any]:
    return default_service().get_route(route_id)


def compute_route_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().create_route(payload)


def compute_route_update(route_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().update_route(route_id, payload)


def compute_route_disable(route_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().disable_route(route_id, payload)


def compute_policies(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    service_result = default_service().list_policies(payload or {})
    return {
        **service_result,
        "selection_strategies": tuple(strategy.value for strategy in SelectionStrategy),
        "simulation_scenarios": simulation_catalog(),
    }


def compute_policy(policy_id: str) -> Mapping[str, Any]:
    return default_service().get_policy(policy_id)


def compute_policy_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().create_policy(payload)


def compute_policy_update(policy_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().update_policy(policy_id, payload)


def compute_policy_validate(policy_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().validate_policy(policy_id, payload)


def compute_economic_memory(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    result = default_service().economic_memory(payload or {})
    if not result.get("schema_fields"):
        result = {**result, "schema_fields": economic_memory_schema()}
    return result


def compute_economic_memory_query(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().economic_memory_query(payload)


def compute_economic_memory_summary(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().economic_memory_query({**dict(payload or {}), "query": "summary"})


def compute_economic_memory_anomalies(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().economic_memory_query({**dict(payload or {}), "query": "anomalies"})


def compute_economic_memory_provider(provider_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().economic_memory_query({**dict(payload or {}), "provider_id": provider_id})


def compute_economic_memory_route(route_id: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().economic_memory_query({**dict(payload or {}), "route_id": route_id})


def compute_economic_memory_task(task_type: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().economic_memory_query({**dict(payload or {}), "task_type": task_type})


def compute_decision(decision_id: str) -> Mapping[str, Any]:
    return default_service().decision(decision_id)


def compute_decision_replay(decision_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().replay_decision(decision_id, payload)


def compute_audit(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().audit(payload or {})


def compute_audit_event(audit_event_id: str) -> Mapping[str, Any]:
    return default_service().audit_event(audit_event_id)

def compute_audit_verify(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return default_service().audit_verify(payload or {})
def compute_audit_export(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().audit_export(payload)


def compute_audit_checkpoint(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().audit_checkpoint(payload)


def compute_audit_verify_export(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return default_service().audit_verify_export(payload)


def compute_health() -> Mapping[str, Any]:
    return default_service().health()


def compute_readiness() -> Mapping[str, Any]:
    return default_service().readiness()


def compute_migrations() -> Mapping[str, Any]:
    return {"ok": True, "migration_plan": migration_plan(), "default_market_policy": ComputeMarketPolicy().as_record()}
