"""Dependency-free internal API router."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import unquote

from flow_memory.api.auth import (
    create_membership_record,
    create_user_record,
    create_workspace_record,
    disable_api_key_record,
    disable_user_record,
    disable_workspace_record,
    issue_api_key_record,
    public_api_key_record,
    public_membership_record,
    public_user_record,
    public_workspace_record,
    rotate_api_key_record,
    update_user_record,
    update_workspace_record,
)
from flow_memory.api.errors import forbidden_error
from flow_memory.api.manifest import API_ENDPOINTS, endpoint_manifest
from flow_memory.core.types import new_id
from flow_memory.economy.attestations import Attestation
from flow_memory.economy.reputation import NonTransferableReputation
from flow_memory.swarm.agent_card import AgentCard
from flow_memory.swarm.delegation import DelegationContract
from flow_memory.flowlang import EXAMPLE_FLOWLANG, compile_flowlang, run_flowlang_agent, validate_flowlang
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.api.neural_endpoints import (
    neural_backends,
    neural_benchmarks,
    neural_checkpoints,
    neural_gpu_run,
    neural_gpu_runs,
    neural_status,
    neural_train_smoke,
    neural_validate_smoke,
)
from flow_memory.api.rl_endpoints import rl_benchmarks, rl_envs, rl_evaluate, rl_train_smoke
from flow_memory.api.release_endpoints import release_decision_status, release_evidence_status
from flow_memory.api.dashboard_endpoints import dashboard_snapshot
from flow_memory.api.visual_endpoints import current_visual_events, current_visual_state, network_state, start_visual_replay, visual_replay, visual_schema_endpoint
from flow_memory.api.compute_endpoints import (
    admin_reconciliation,
    admin_audit_export_status,
    admin_otlp_export,
    admin_policy_publish,
    admin_provider_approve,
    admin_provider_suspend,
    admin_redis_diagnostics,
    admin_route_disable,
    admin_storage_diagnostics,
    billing_balance,
    billing_checkout,
    billing_quota,
    billing_quota_set,
    billing_refund,
    billing_provider_payouts,
    billing_provider_payout_settle,
    billing_usage,
    billing_webhook_stripe,
    compute_audit,
    compute_audit_event,
    compute_audit_verify,
    compute_audit_checkpoint,
    compute_audit_chain_monitor,
    compute_audit_checkpoint_schedule,
    compute_audit_export,
    compute_audit_verify_export,
    compute_audit_replay,
    compute_alert_ack,
    compute_alerts,
    compute_alert_route,
    compute_track_error,
    compute_decision,
    compute_decision_replay,
    compute_economic_memory,
    compute_economic_memory_anomalies,
    compute_economic_memory_provider,
    compute_economic_memory_query,
    compute_economic_memory_route,
    compute_economic_memory_summary,
    compute_economic_memory_task,
    compute_health,
    compute_job,
    compute_job_artifacts,
    compute_job_cancel,
    compute_job_create,
    compute_jobs,
    compute_job_complete,
    compute_job_events,
    compute_job_receipt,
    compute_job_retry,
    compute_job_dispatch,
    compute_job_fail,
    compute_job_claim,
    compute_job_expire_leases,
    compute_job_heartbeat,
    compute_job_release_claim,
    compute_marketplace_plan,
    compute_intelligence_plan,
    compute_metrics,
    compute_payment_plan,
    compute_plan,
    compute_policies,
    compute_policy,
    compute_policy_create,
    compute_policy_update,
    compute_policy_validate,
    compute_provider,
    compute_provider_create,
    compute_provider_disable,
    compute_provider_health,
    compute_provider_external_quote,
    compute_provider_update,
    compute_providers,
    compute_quote,
    compute_readiness,
    compute_prices,
    compute_prices_anomalies,
    compute_prices_forecast,
    compute_prices_history,
    compute_telemetry,
    compute_route,
    compute_route_create,
    compute_route_disable,
    compute_route_get,
    compute_route_update,
    compute_routes,
    compute_simulate_settlement,
    compute_usage,
    compute_usage_by_agent,
    compute_usage_by_goal,
    compute_usage_statement,
    market_capacity_confirm,
    market_capacity_auction,
    market_capacity_expire,
    market_capacity_list,
    market_capacity_order_book,
    market_capacity_release,
    market_capacity_reserve,
    market_prices,
    market_prices_history,
    market_provider,
    market_provider_apply,
    market_provider_disable,
    market_provider_reject,
    market_provider_request_revision,
    market_provider_conformance,
    market_provider_reputation,
    market_provider_verify,
    market_quote_ingest,
    market_quote_cache_invalidate,
    market_quote_drift,
    market_quote_compare,
)

Handler = Callable[[Mapping[str, str], Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    handler: Handler
    name: str = ""

    @property
    def parts(self) -> tuple[str, ...]:
        return _split_path(self.path)


@dataclass
class LocalApiRouter:
    """Small in-process router with path parameters and local state."""

    routes: list[Route] = field(default_factory=list)
    agents: dict[str, AgentCard] = field(default_factory=dict)
    reputations: dict[str, NonTransferableReputation] = field(default_factory=dict)
    marketplace_tasks: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    marketplace_bids: dict[str, list[Mapping[str, Any]]] = field(default_factory=dict)
    delegations: dict[str, DelegationContract] = field(default_factory=dict)
    attestations: list[Attestation] = field(default_factory=list)
    audit_events: list[Mapping[str, Any]] = field(default_factory=list)
    api_key_records: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    user_records: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    workspace_records: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    workspace_memberships: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    runtime_ticks: int = 0
    latest_verification: Mapping[str, Any] = field(default_factory=dict)

    def register(self, method: str, path: str, handler: Handler, name: str = "") -> None:
        self.routes.append(Route(method=method.upper(), path=_normalize_path(path), handler=handler, name=name))

    def dispatch(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        method = method.upper()
        normalized = _normalize_path(path)
        for route in self.routes:
            if route.method != method:
                continue
            params = _match(route.parts, _split_path(normalized))
            if params is not None:
                result = route.handler(params, payload or {})
                self.audit_events.append({"method": method, "path": normalized, "route": route.name, "ok": True})
                return result
        raise LookupError(f"No route for {method} {normalized}")

    def register_agent(self, card: AgentCard) -> None:
        self.agents[card.did] = card
        reputation = self.reputations.setdefault(card.did, NonTransferableReputation())
        reputation.score = card.reputation

    def manifest(self) -> Mapping[str, Any]:
        registered = {(route.method, route.path) for route in self.routes}
        endpoints = [endpoint.as_record() for endpoint in API_ENDPOINTS if (endpoint.method, endpoint.path) in registered]
        return {"endpoints": tuple(endpoints)}

    def _health(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"ok": True, "service": "flow-memory", "mode": "local"}

    def _runtime_status(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"ok": True, "ticks": self.runtime_ticks, "agents": len(self.agents), "tasks": len(self.marketplace_tasks), "delegations": len(self.delegations)}

    def _runtime_tick(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.runtime_ticks += 1
        return {"ok": True, "ticks": self.runtime_ticks}

    def _agents_list(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"agents": tuple(card.as_manifest() for card in self.agents.values())}

    def _agents_get(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"agent": self._agent(params["did"]).as_manifest()}

    def _agent_memory(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self._agent(params["did"])
        return {"agent_id": params["did"], "memory": ()}

    def _agent_skills(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        card = self._agent(params["did"])
        return {"agent_id": card.did, "skills": tuple(card.capabilities)}

    def _agent_run(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        card = self._agent(params["did"])
        goal = str(payload.get("goal", "Explore and report"))
        return {"agent_id": card.did, "goal": goal, "status": "accepted_local_run"}

    def _agents_launch(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        goal = str(payload.get("goal", "Explore and report"))
        profile = AgentProfile(
            name=str(payload.get("name", "API Launch Agent")),
            identity=str(payload.get("identity", "did:flow:api-launch-agent")),
            goals=(goal,),
            capabilities=("local_reasoning", "safe_tool_use"),
            allowed_tools=("observe_environment", "respond"),
            allowed_skills=("research_brief",),
            autonomy_mode=str(payload.get("autonomy_mode", "autonomous_local")),
            metadata={"launch_path": "api"},
        )
        result = AgentRunner(profile).run_cycle(goal)
        return {"agent": profile.as_record(), "result": result.as_record(), "safety_authority": "policy_engine_and_approval_gate"}

    def _agents_launch_flowlang(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        prompt = str(payload.get("goal", payload.get("prompt", "Run the declared agent")))
        flow_result = self._flowlang_run({}, {"source": source, "prompt": prompt})
        return {"launch_mode": "flowlang", "result": flow_result, "safety_authority": "policy_engine_and_approval_gate"}

    def _agents_launch_neural(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        goal = str(payload.get("goal", "Explore and report"))
        backend = str(payload.get("backend", "tiny_torch"))
        profile = AgentProfile(
            name=str(payload.get("name", "API Neural Launch Agent")),
            identity=str(payload.get("identity", "did:flow:api-neural-agent")),
            goals=(goal,),
            capabilities=("local_reasoning", "neural_advisory"),
            allowed_tools=("observe_environment", "respond"),
            allowed_skills=("research_brief",),
            neural_config={"backend": backend, "perception": "dual_stream"},
            autonomy_mode="supervised",
            metadata={"launch_path": "api_neural"},
        )
        result = AgentRunner(profile).run_cycle(goal)
        return {"agent": profile.as_record(), "result": result.as_record(), "neural": result.output.get("neural", {}), "safety_authority": "policy_engine_and_approval_gate"}

    def _marketplace_task_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        title = str(payload.get("title", "")).strip()
        requester = str(payload.get("requester", "")).strip()
        reward = float(payload.get("reward", 0.0))
        if not title:
            raise ValueError("Task title is required")
        if not requester:
            raise ValueError("Requester is required")
        if reward < 0:
            raise ValueError("Reward must be non-negative")
        task_id = new_id("task")
        metadata = payload.get("metadata")
        task = {"task_id": task_id, "title": title, "requester": requester, "reward": reward, "status": "open", "metadata": dict(metadata) if isinstance(metadata, Mapping) else {}}
        self.marketplace_tasks[task_id] = task
        self.marketplace_bids[task_id] = []
        return {"task": dict(task)}

    def _marketplace_bid_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        if task_id not in self.marketplace_tasks:
            raise KeyError(f"Unknown task: {task_id}")
        bid = {"bid_id": new_id("bid"), "task_id": task_id, "agent_did": str(payload.get("agent_did", "")), "price": float(payload.get("price", 0.0)), "status": "open"}
        self.marketplace_bids.setdefault(task_id, []).append(bid)
        return {"bid": bid}

    def _marketplace_settle(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        task = dict(self.marketplace_tasks.get(task_id) or {})
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        if task.get("status") == "settled":
            raise ValueError(f"Task already settled: {task_id}")
        task["status"] = "settled"
        self.marketplace_tasks[task_id] = task
        return {"settlement": {"task_id": task_id, "status": "settled"}}

    def _marketplace_assign(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        task = dict(self.marketplace_tasks.get(task_id) or {})
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        task["status"] = "assigned"
        task["agent_did"] = str(payload.get("agent_did", ""))
        self.marketplace_tasks[task_id] = task
        return {"task": task}

    def _marketplace_submit(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        task = dict(self.marketplace_tasks.get(task_id) or {})
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        task["status"] = "submitted"
        task["artifact"] = payload.get("artifact", {})
        self.marketplace_tasks[task_id] = task
        return {"task": task}

    def _marketplace_verify(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        task = dict(self.marketplace_tasks.get(task_id) or {})
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        task["status"] = "verified" if bool(payload.get("accepted", True)) else "rejected"
        self.marketplace_tasks[task_id] = task
        return {"task": task}

    def _marketplace_dispute(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        task_id = str(payload.get("task_id", ""))
        task = dict(self.marketplace_tasks.get(task_id) or {})
        if not task:
            raise KeyError(f"Unknown task: {task_id}")
        task["status"] = "disputed"
        task["dispute_reason"] = str(payload.get("reason", ""))
        self.marketplace_tasks[task_id] = task
        return {"task": task}

    def _reputation_lookup(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        did = params["did"]
        reputation = self.reputations.get(did)
        if reputation is None:
            return {"did": did, "score": 0.0, "events": ()}
        return {"did": did, "score": reputation.score, "events": tuple(dict(event) for event in reputation.events)}

    def _attestation_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        attestation = Attestation(issuer=str(payload.get("issuer", "api")), subject=str(payload.get("subject", "")), claim=str(payload.get("claim", "")), evidence=dict(payload.get("evidence", {})) if isinstance(payload.get("evidence", {}), Mapping) else {})
        self.attestations.append(attestation)
        return {"attestation": attestation.as_record()}

    def _audit(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"events": tuple(dict(event) for event in self.audit_events)}

    def _swarm_delegate(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        delegate_did = str(payload.get("delegate_did", ""))
        capability = str(payload.get("capability", ""))
        card = self._agent(delegate_did)
        if not card.has_capability(capability):
            raise ValueError(f"Delegate lacks capability: {capability}")
        constraints = payload.get("constraints")
        contract = DelegationContract(delegator_did=str(payload.get("delegator_did", "")), delegate_did=delegate_did, capability=capability, objective=str(payload.get("objective", "")), budget=float(payload.get("budget", 0.0)), constraints=dict(constraints) if isinstance(constraints, Mapping) else {})
        assignment = payload.get("assignment")
        contract.assign(assignment if isinstance(assignment, Mapping) else {})
        self.delegations[contract.contract_id] = contract
        return {"delegation": contract.as_record()}

    def _verification_submit(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        contract_id = params.get("contract_id") or str(payload.get("contract_id", ""))
        contract = self._delegation(contract_id)
        result = payload.get("result")
        if contract.status == "assigned":
            contract.complete(result if isinstance(result, Mapping) else {"output": result})
        accepted = payload.get("accepted")
        if accepted is not None:
            evidence = payload.get("evidence")
            contract.verify(bool(accepted), evidence if isinstance(evidence, Mapping) else {})
            reputation = self.reputations.setdefault(contract.delegate_did, NonTransferableReputation())
            reputation.record({"contract_id": contract.contract_id, "capability": contract.capability}, 1.0 if accepted else -1.0)
        self.latest_verification = contract.as_record()
        return {"verification": contract.as_record()}

    def _verification_result(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        contract_id = params.get("contract_id")
        if contract_id:
            return {"verification": self._delegation(contract_id).as_record()}
        return {"verification": dict(self.latest_verification)}

    def _flowlang_compile(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        record: Mapping[str, Any] = compile_flowlang(source).as_record()
        return record

    def _flowlang_validate(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        return {"errors": validate_flowlang(source)}

    def _flowlang_run(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        prompt = str(payload.get("prompt", "Run the declared agent"))
        result = compile_flowlang(source)
        if not result.ok:
            record: Mapping[str, Any] = result.as_record()
            return record
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile("w", suffix=".flow", delete=False, encoding="utf-8") as handle:
            handle.write(source)
            path = Path(handle.name)
        try:
            run_result: Mapping[str, Any] = run_flowlang_agent(path, prompt)
            return run_result
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    def _flowlang_examples(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"examples": {"default": EXAMPLE_FLOWLANG}}

    def _neural_status(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_status()

    def _neural_backends(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_backends()

    def _neural_gpu_runs(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_gpu_runs()

    def _neural_gpu_run(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_gpu_run(params["run_id"])

    def _neural_benchmarks(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_benchmarks()

    def _neural_checkpoints(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_checkpoints()

    def _neural_validate_smoke(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_validate_smoke_requested"})
        return neural_validate_smoke()

    def _neural_train_smoke(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_train_smoke_requested", "local_only": True})
        return neural_train_smoke(str(payload.get("out", "artifacts/neural/api_smoke")))

    def _rl_envs(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return rl_envs()

    def _rl_benchmarks(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return rl_benchmarks()

    def _rl_evaluate(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "rl_evaluate_requested"})
        return rl_evaluate(payload)

    def _rl_train_smoke(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "rl_train_smoke_requested", "local_only": True})
        return rl_train_smoke(payload)

    def _network_run_scenario(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from flow_memory.network import LocalNetworkOrchestrator

        scenario = str(payload.get("scenario", "all"))
        emit_visual = bool(payload.get("emit_visual_events", payload.get("visual", False)))
        record: Mapping[str, Any] = LocalNetworkOrchestrator().run(scenario, emit_visual_events=emit_visual).as_record()
        return record

    def _network_state(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return network_state()

    def _visual_state(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return current_visual_state()

    def _visual_events(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return current_visual_events()

    def _visual_schema(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return visual_schema_endpoint()

    def _visual_replay(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return visual_replay(params["run_id"])

    def _visual_replay_start(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "visual_replay_start_requested", "scenario": str(payload.get("scenario", "all"))})
        return start_visual_replay(payload)

    def _release_evidence(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return release_evidence_status()

    def _release_decision(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return release_decision_status(params["target"])
    def _dashboard_snapshot(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return dashboard_snapshot()

    def _compute_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_plan_requested"})
        return compute_plan(payload)

    def _compute_marketplace_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_marketplace_plan_requested"})
        return compute_marketplace_plan(payload)

    def _compute_intelligence_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_intelligence_plan(payload)

    def _compute_quote(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_quote(payload)

    def _compute_route(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_route(payload)

    def _compute_payment_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_payment_plan(payload)

    def _compute_simulate_settlement(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_simulate_settlement(payload)

    def _compute_providers(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_providers(payload)

    def _compute_provider(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider(params["provider_id"], payload)

    def _compute_provider_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider_create(payload)

    def _compute_provider_update(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider_update(params["provider_id"], payload)

    def _compute_provider_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider_disable(params["provider_id"], payload)

    def _compute_provider_health(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider_health(params["provider_id"], payload)

    def _compute_provider_external_quote(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_provider_external_quote(payload)

    def _market_provider_apply(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_apply(payload)

    def _market_provider(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider(params["provider_id"], payload)

    def _market_provider_verify(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_verify(params["provider_id"], payload)


    def _market_provider_reject(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_reject(params["provider_id"], payload)


    def _market_provider_request_revision(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_request_revision(params["provider_id"], payload)

    def _market_provider_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_disable(params["provider_id"], payload)

    def _market_provider_reputation(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_reputation(params["provider_id"], payload)

    def _market_quote_ingest(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_quote_ingest(payload)

    def _market_quote_cache_invalidate(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_quote_cache_invalidate(payload)


    def _market_quote_drift(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_quote_drift(payload)

    def _market_quote_compare(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_quote_compare(payload)

    def _market_capacity_list(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_list(payload)

    def _market_capacity_reserve(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_reserve(payload)

    def _market_capacity_confirm(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_confirm(payload)

    def _market_capacity_auction(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_auction(payload)

    def _market_capacity_expire(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_expire(payload)

    def _market_capacity_release(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_release(payload)

    def _market_capacity_order_book(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_capacity_order_book(payload)

    def _market_prices(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_prices(payload)

    def _market_prices_history(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_prices_history(payload)

    def _compute_prices(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_prices(payload)

    def _compute_prices_history(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_prices_history(payload)

    def _compute_prices_anomalies(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_prices_anomalies(payload)

    def _compute_prices_forecast(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_prices_forecast(payload)

    def _compute_usage(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_usage(payload)

    def _compute_usage_by_agent(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_usage_by_agent(params["agent_id"], payload)

    def _compute_usage_by_goal(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_usage_by_goal(params["goal_id"], payload)

    def _compute_usage_statement(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_usage_statement(payload)

    def _compute_routes(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_routes(payload)

    def _compute_route_get(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_route_get(params["route_id"])

    def _compute_route_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_route_create(payload)

    def _compute_route_update(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_route_update(params["route_id"], payload)

    def _compute_route_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_route_disable(params["route_id"], payload)

    def _compute_policies(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policies(payload)

    def _compute_policy(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policy(params["policy_id"])

    def _compute_policy_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policy_create(payload)

    def _compute_policy_update(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policy_update(params["policy_id"], payload)

    def _compute_policy_validate(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policy_validate(params["policy_id"], payload)

    def _compute_economic_memory(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory(payload)

    def _compute_economic_memory_query(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_query(payload)

    def _compute_economic_memory_summary(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_summary(payload)

    def _compute_economic_memory_anomalies(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_anomalies(payload)

    def _compute_economic_memory_provider(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_provider(params["provider_id"], payload)

    def _compute_economic_memory_route(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_route(params["route_id"], payload)

    def _compute_economic_memory_task(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_task(params["task_type"], payload)

    def _compute_decision(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_decision(params["decision_id"])

    def _compute_decision_replay(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_decision_replay(params["decision_id"], payload)

    def _compute_audit(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit(payload)

    def _compute_audit_event(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_event(params["audit_event_id"])

    def _compute_audit_verify(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_verify(payload)
    def _compute_audit_export(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_export(payload)

    def _compute_audit_checkpoint(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_checkpoint(payload)

    def _compute_audit_verify_export(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_verify_export(payload)

    def _compute_audit_checkpoint_schedule(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_checkpoint_schedule(payload)

    def _compute_audit_chain_monitor(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_chain_monitor(payload)

    def _compute_audit_replay(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_audit_replay(payload)

    def _compute_job_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_create(payload)

    def _compute_jobs(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_jobs(payload)

    def _compute_job(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job(params["job_id"], payload)

    def _compute_job_cancel(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_cancel(params["job_id"], payload)

    def _compute_job_events(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_events(params["job_id"], payload)

    def _compute_job_artifacts(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_artifacts(params["job_id"], payload)

    def _compute_job_retry(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_retry(params["job_id"], payload)

    def _compute_job_dispatch(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_dispatch(params["job_id"], payload)

    def _compute_job_complete(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_complete(params["job_id"], payload)

    def _compute_job_receipt(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_receipt(params["job_id"], payload)

    def _compute_job_fail(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_fail(params["job_id"], payload)

    def _compute_job_claim(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_claim(payload)


    def _compute_job_expire_leases(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_expire_leases(payload)

    def _compute_job_heartbeat(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_heartbeat(params["job_id"], payload)

    def _compute_job_release_claim(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_job_release_claim(params["job_id"], payload)

    def _billing_checkout(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_checkout(payload)

    def _billing_webhook_stripe(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_webhook_stripe(payload)

    def _market_provider_conformance(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return market_provider_conformance(params["provider_id"], payload)

    def _billing_balance(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_balance(payload)

    def _billing_quota(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_quota(payload)

    def _billing_quota_set(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_quota_set(payload)

    def _billing_usage(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_usage(payload)

    def _billing_provider_payouts(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_provider_payouts(payload)

    def _billing_provider_payout_settle(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_provider_payout_settle(params["payout_id"], payload)

    def _billing_refund(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return billing_refund(payload)


    def _admin_reconciliation(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_reconciliation(payload)

    def _admin_provider_approve(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_provider_approve(params["provider_id"], payload)

    def _admin_provider_suspend(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_provider_suspend(params["provider_id"], payload)

    def _admin_route_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_route_disable(params["route_id"], payload)

    def _admin_policy_publish(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_policy_publish(params["policy_id"], payload)

    def _admin_storage_diagnostics(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_storage_diagnostics(payload)

    def _admin_redis_diagnostics(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_redis_diagnostics(payload)

    def _admin_audit_export_status(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_audit_export_status(payload)

    def _admin_otlp_export(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return admin_otlp_export(payload)


    def _compute_health(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_health()

    def _compute_readiness(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_readiness()

    def _compute_telemetry(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_telemetry(payload)

    def _compute_metrics(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_metrics(payload)

    def _compute_alerts(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_alerts(payload)

    def _compute_alert_route(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_alert_route(payload)

    def _compute_alert_ack(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_alert_ack(params["rule_name"], payload)

    def _compute_track_error(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_track_error(payload)


    def _auth_api_keys(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        tenant_id = _payload_tenant_id(_payload)
        workspace_id = _payload_workspace_id(_payload)
        records = tuple(
            public_api_key_record(record)
            for record in self.api_key_records.values()
            if _tenant_can_access_auth_record(tenant_id, workspace_id, record)
        )
        return {
            "ok": True,
            "api_keys": records,
        }

    def _auth_api_key_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        issued = issue_api_key_record(payload)
        record = issued["record"]
        if not isinstance(record, Mapping):
            raise ValueError("api key issuer returned invalid record")
        key_id = str(record["key_id"])
        self.api_key_records[key_id] = record
        return {"ok": True, "api_key": issued["api_key"], "record": public_api_key_record(record)}

    def _auth_api_key_rotate(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        key_id = params["key_id"]
        existing = self.api_key_records.get(key_id)
        if existing is None:
            raise KeyError(f"Unknown API key: {key_id}")
        _assert_auth_record_tenant_access(payload, existing, "rotate")
        rotated = rotate_api_key_record(existing, payload)
        previous_record = rotated["previous_record"]
        record = rotated["record"]
        if not isinstance(previous_record, Mapping) or not isinstance(record, Mapping):
            raise ValueError("api key rotation returned invalid record")
        previous_key_id = str(previous_record["key_id"])
        next_key_id = str(record["key_id"])
        self.api_key_records[previous_key_id] = previous_record
        self.api_key_records[next_key_id] = record
        return {
            "ok": True,
            "api_key": rotated["api_key"],
            "previous_record": public_api_key_record(previous_record),
            "record": public_api_key_record(record),
        }

    def _auth_api_key_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        key_id = params["key_id"]
        existing = self.api_key_records.get(key_id)
        if existing is None:
            raise KeyError(f"Unknown API key: {key_id}")
        _assert_auth_record_tenant_access(payload, existing, "disable")
        disabled = disable_api_key_record(existing, reason=str(payload.get("reason", "operator_requested")))
        self.api_key_records[key_id] = disabled
        return {"ok": True, "record": public_api_key_record(disabled)}

    def _auth_users(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        tenant_id = _payload_tenant_id(_payload)
        workspace_id = _payload_workspace_id(_payload)
        users = tuple(
            public_user_record(record)
            for record in self.user_records.values()
            if _tenant_can_access_auth_record(tenant_id, workspace_id, record)
        )
        return {"ok": True, "users": users}

    def _auth_user_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        record = create_user_record(payload)
        user_id = str(record["user_id"])
        self.user_records[user_id] = record
        return {"ok": True, "user": public_user_record(record), "management": "local_in_memory"}

    def _auth_user(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        record = self._auth_user_record(params["user_id"])
        _assert_user_access(payload, record, "read")
        return {"ok": True, "user": public_user_record(record)}

    def _auth_user_update(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        user_id = params["user_id"]
        current = self._auth_user_record(user_id)
        _assert_user_access(payload, current, "update")
        record = update_user_record(current, payload)
        self.user_records[user_id] = record
        return {"ok": True, "user": public_user_record(record)}

    def _auth_user_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        user_id = params["user_id"]
        current = self._auth_user_record(user_id)
        _assert_user_access(payload, current, "disable")
        record = disable_user_record(current, reason=str(payload.get("reason", "operator_requested")))
        self.user_records[user_id] = record
        return {"ok": True, "user": public_user_record(record)}

    def _auth_workspaces(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        tenant_id = _payload_tenant_id(_payload)
        workspace_id = _payload_workspace_id(_payload)
        workspaces = tuple(
            public_workspace_record(record)
            for record in self.workspace_records.values()
            if _tenant_can_access_auth_record(tenant_id, workspace_id, record)
        )
        return {"ok": True, "workspaces": workspaces}

    def _auth_workspace_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        record = create_workspace_record(payload)
        workspace_id = str(record["workspace_id"])
        self.workspace_records[workspace_id] = record
        return {"ok": True, "workspace": public_workspace_record(record), "management": "local_in_memory"}

    def _auth_workspace(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        record = self._auth_workspace_record(params["workspace_id"])
        _assert_workspace_access(payload, record, "read")
        return {"ok": True, "workspace": public_workspace_record(record)}

    def _auth_workspace_update(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = params["workspace_id"]
        current = self._auth_workspace_record(workspace_id)
        _assert_workspace_access(payload, current, "update")
        record = update_workspace_record(current, payload)
        self.workspace_records[workspace_id] = record
        return {"ok": True, "workspace": public_workspace_record(record)}

    def _auth_workspace_disable(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = params["workspace_id"]
        current = self._auth_workspace_record(workspace_id)
        _assert_workspace_access(payload, current, "disable")
        record = disable_workspace_record(current, reason=str(payload.get("reason", "operator_requested")))
        self.workspace_records[workspace_id] = record
        return {"ok": True, "workspace": public_workspace_record(record)}

    def _auth_workspace_members(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = params["workspace_id"]
        workspace = self._auth_workspace_record(workspace_id)
        _assert_workspace_access(payload, workspace, "list members")
        members = tuple(
            public_membership_record(record)
            for record in self.workspace_memberships.values()
            if str(record.get("workspace_id", "")) == workspace_id
            and bool(record.get("enabled", True))
            and _tenant_can_access_auth_record(_payload_tenant_id(payload), _payload_workspace_id(payload), record)
        )
        return {"ok": True, "members": members}

    def _auth_workspace_member_add(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = params["workspace_id"]
        user_id = str(payload.get("user_id", "")).strip()
        workspace = self._auth_workspace_record(workspace_id)
        _assert_workspace_access(payload, workspace, "add members to")
        user = self._auth_user_record(user_id)
        _assert_user_access(payload, user, "add to workspace")
        membership_payload = {**dict(payload), "tenant_id": str(workspace.get("tenant_id", ""))}
        record = create_membership_record(workspace_id, user_id, membership_payload)
        self.workspace_memberships[_membership_key(workspace_id, user_id)] = record
        return {"ok": True, "membership": public_membership_record(record)}

    def _auth_workspace_member_remove(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = params["workspace_id"]
        user_id = params["user_id"]
        workspace = self._auth_workspace_record(workspace_id)
        _assert_workspace_access(payload, workspace, "remove members from")
        key = _membership_key(workspace_id, user_id)
        record = self.workspace_memberships.get(key)
        if record is None or not bool(record.get("enabled", True)):
            raise KeyError(f"Unknown workspace member: {user_id}")
        _assert_workspace_access(payload, record, "remove")
        removed = {**dict(record), "enabled": False, "removed_reason": str(payload.get("reason", "operator_requested"))}
        self.workspace_memberships[key] = removed
        return {"ok": True, "membership": public_membership_record(removed)}

    def _auth_user_record(self, user_id: str) -> Mapping[str, Any]:
        record = self.user_records.get(user_id)
        if record is None:
            raise KeyError(f"Unknown user: {user_id}")
        return record

    def _auth_workspace_record(self, workspace_id: str) -> Mapping[str, Any]:
        record = self.workspace_records.get(workspace_id)
        if record is None:
            raise KeyError(f"Unknown workspace: {workspace_id}")
        return record
    def _manifest(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.manifest()

    def _agent(self, did: str) -> AgentCard:
        card = self.agents.get(did)
        if card is None:
            raise KeyError(f"Unknown agent: {did}")
        return card

    def _delegation(self, contract_id: str) -> DelegationContract:
        contract = self.delegations.get(contract_id)
        if contract is None:
            raise KeyError(f"Unknown delegation: {contract_id}")
        return contract


def create_default_router() -> LocalApiRouter:
    router = LocalApiRouter()
    router.register("GET", "/health", router._health, "health")
    router.register("GET", "/auth/api-keys", router._auth_api_keys, "auth_api_keys")
    router.register("POST", "/auth/api-keys", router._auth_api_key_create, "auth_api_key_create")
    router.register("POST", "/auth/api-keys/{key_id}/rotate", router._auth_api_key_rotate, "auth_api_key_rotate")
    router.register("POST", "/auth/api-keys/{key_id}/disable", router._auth_api_key_disable, "auth_api_key_disable")
    router.register("GET", "/auth/users", router._auth_users, "auth_users")
    router.register("POST", "/auth/users", router._auth_user_create, "auth_user_create")
    router.register("GET", "/auth/users/{user_id}", router._auth_user, "auth_user")
    router.register("PATCH", "/auth/users/{user_id}", router._auth_user_update, "auth_user_update")
    router.register("POST", "/auth/users/{user_id}/disable", router._auth_user_disable, "auth_user_disable")
    router.register("GET", "/auth/workspaces", router._auth_workspaces, "auth_workspaces")
    router.register("POST", "/auth/workspaces", router._auth_workspace_create, "auth_workspace_create")
    router.register("GET", "/auth/workspaces/{workspace_id}", router._auth_workspace, "auth_workspace")
    router.register("PATCH", "/auth/workspaces/{workspace_id}", router._auth_workspace_update, "auth_workspace_update")
    router.register("POST", "/auth/workspaces/{workspace_id}/disable", router._auth_workspace_disable, "auth_workspace_disable")
    router.register("GET", "/auth/workspaces/{workspace_id}/members", router._auth_workspace_members, "auth_workspace_members")
    router.register("POST", "/auth/workspaces/{workspace_id}/members", router._auth_workspace_member_add, "auth_workspace_member_add")
    router.register("POST", "/auth/workspaces/{workspace_id}/members/{user_id}/remove", router._auth_workspace_member_remove, "auth_workspace_member_remove")
    router.register("GET", "/runtime/status", router._runtime_status, "runtime_status")
    router.register("POST", "/runtime/tick", router._runtime_tick, "runtime_tick")
    router.register("GET", "/agents", router._agents_list, "agents_list")
    router.register("GET", "/agents/{did}", router._agents_get, "agents_get")
    router.register("GET", "/agents/{did}/memory", router._agent_memory, "agent_memory")
    router.register("GET", "/agents/{did}/skills", router._agent_skills, "agent_skills")
    router.register("POST", "/agents/{did}/run", router._agent_run, "agent_run")
    router.register("POST", "/agents/launch", router._agents_launch, "agents_launch")
    router.register("POST", "/agents/launch-flowlang", router._agents_launch_flowlang, "agents_launch_flowlang")
    router.register("POST", "/agents/launch-neural", router._agents_launch_neural, "agents_launch_neural")
    router.register("POST", "/marketplace/tasks", router._marketplace_task_create, "marketplace_task_create")
    router.register("POST", "/marketplace/bids", router._marketplace_bid_create, "marketplace_bid_create")
    router.register("POST", "/marketplace/settle", router._marketplace_settle, "marketplace_settle")
    router.register("POST", "/marketplace/assign", router._marketplace_assign, "marketplace_assign")
    router.register("POST", "/marketplace/submit", router._marketplace_submit, "marketplace_submit")
    router.register("POST", "/marketplace/verify", router._marketplace_verify, "marketplace_verify")
    router.register("POST", "/marketplace/dispute", router._marketplace_dispute, "marketplace_dispute")
    router.register("GET", "/reputation/{did}", router._reputation_lookup, "reputation_lookup")
    router.register("POST", "/attestations", router._attestation_create, "attestation_create")
    router.register("GET", "/audit", router._audit, "audit_log")
    router.register("GET", "/swarm/agents", router._agents_list, "swarm_agents")
    router.register("POST", "/swarm/delegate", router._swarm_delegate, "swarm_delegate")
    router.register("POST", "/verification/submit", router._verification_submit, "verification_submit_alias")
    router.register("POST", "/verification/{contract_id}", router._verification_submit, "verification_submit")
    router.register("GET", "/verification/result", router._verification_result, "verification_result_alias")
    router.register("GET", "/verification/{contract_id}", router._verification_result, "verification_result")
    router.register("POST", "/flowlang/compile", router._flowlang_compile, "flowlang_compile")
    router.register("POST", "/flowlang/validate", router._flowlang_validate, "flowlang_validate")
    router.register("POST", "/flowlang/run", router._flowlang_run, "flowlang_run")
    router.register("GET", "/flowlang/examples", router._flowlang_examples, "flowlang_examples")
    router.register("GET", "/neural/status", router._neural_status, "neural_status")
    router.register("GET", "/neural/backends", router._neural_backends, "neural_backends")
    router.register("GET", "/neural/gpu-runs", router._neural_gpu_runs, "neural_gpu_runs")
    router.register("GET", "/neural/gpu-runs/{run_id}", router._neural_gpu_run, "neural_gpu_run")
    router.register("GET", "/neural/benchmarks", router._neural_benchmarks, "neural_benchmarks")
    router.register("GET", "/neural/checkpoints", router._neural_checkpoints, "neural_checkpoints")
    router.register("POST", "/neural/validate-smoke", router._neural_validate_smoke, "neural_validate_smoke")
    router.register("POST", "/neural/train-smoke", router._neural_train_smoke, "neural_train_smoke")
    router.register("GET", "/rl/envs", router._rl_envs, "rl_envs")
    router.register("GET", "/rl/benchmarks", router._rl_benchmarks, "rl_benchmarks")
    router.register("POST", "/rl/evaluate", router._rl_evaluate, "rl_evaluate")
    router.register("POST", "/rl/train-smoke", router._rl_train_smoke, "rl_train_smoke")
    router.register("POST", "/network/run-scenario", router._network_run_scenario, "network_run_scenario")
    router.register("GET", "/network/state", router._network_state, "network_state")
    router.register("GET", "/visual/state", router._visual_state, "visual_state")
    router.register("GET", "/visual/events", router._visual_events, "visual_events")
    router.register("GET", "/visual/schema", router._visual_schema, "visual_schema")
    router.register("GET", "/visual/replay/{run_id}", router._visual_replay, "visual_replay")
    router.register("POST", "/visual/replay/start", router._visual_replay_start, "visual_replay_start")
    router.register("GET", "/release/evidence", router._release_evidence, "release_evidence")
    router.register("GET", "/release/decision/{target}", router._release_decision, "release_decision")
    router.register("GET", "/dashboard/snapshot", router._dashboard_snapshot, "dashboard_snapshot")
    router.register("POST", "/compute/plan", router._compute_plan, "compute_plan")
    router.register("POST", "/compute/marketplace-plan", router._compute_marketplace_plan, "compute_marketplace_plan")
    router.register("POST", "/compute/intelligence-plan", router._compute_intelligence_plan, "compute_intelligence_plan")
    router.register("POST", "/compute/quote", router._compute_quote, "compute_quote")
    router.register("POST", "/compute/route", router._compute_route, "compute_route")
    router.register("POST", "/compute/payment-plan", router._compute_payment_plan, "compute_payment_plan")
    router.register("POST", "/compute/simulate-settlement", router._compute_simulate_settlement, "compute_simulate_settlement")
    router.register("POST", "/compute/jobs", router._compute_job_create, "compute_job_create")
    router.register("GET", "/compute/jobs", router._compute_jobs, "compute_jobs")
    router.register("POST", "/compute/jobs/expire-leases", router._compute_job_expire_leases, "compute_job_expire_leases")
    router.register("GET", "/compute/jobs/{job_id}", router._compute_job, "compute_job")
    router.register("POST", "/compute/jobs/{job_id}/cancel", router._compute_job_cancel, "compute_job_cancel")
    router.register("GET", "/compute/jobs/{job_id}/events", router._compute_job_events, "compute_job_events")
    router.register("GET", "/compute/jobs/{job_id}/artifacts", router._compute_job_artifacts, "compute_job_artifacts")
    router.register("POST", "/compute/jobs/{job_id}/retry", router._compute_job_retry, "compute_job_retry")
    router.register("POST", "/compute/jobs/{job_id}/dispatch", router._compute_job_dispatch, "compute_job_dispatch")
    router.register("POST", "/compute/jobs/{job_id}/complete", router._compute_job_complete, "compute_job_complete")
    router.register("POST", "/compute/jobs/{job_id}/receipt", router._compute_job_receipt, "compute_job_receipt")
    router.register("POST", "/compute/jobs/{job_id}/fail", router._compute_job_fail, "compute_job_fail")
    router.register("POST", "/compute/jobs/claim", router._compute_job_claim, "compute_job_claim")
    router.register("POST", "/compute/jobs/{job_id}/heartbeat", router._compute_job_heartbeat, "compute_job_heartbeat")
    router.register("POST", "/compute/jobs/{job_id}/release-claim", router._compute_job_release_claim, "compute_job_release_claim")
    router.register("GET", "/compute/providers", router._compute_providers, "compute_providers")
    router.register("GET", "/compute/providers/{provider_id}", router._compute_provider, "compute_provider")
    router.register("POST", "/compute/providers", router._compute_provider_create, "compute_provider_create")
    router.register("PATCH", "/compute/providers/{provider_id}", router._compute_provider_update, "compute_provider_update")
    router.register("POST", "/compute/providers/{provider_id}/disable", router._compute_provider_disable, "compute_provider_disable")
    router.register("POST", "/compute/providers/{provider_id}/health-check", router._compute_provider_health, "compute_provider_health")
    router.register("POST", "/compute/providers/external/quote", router._compute_provider_external_quote, "compute_provider_external_quote")
    router.register("POST", "/market/providers/apply", router._market_provider_apply, "market_provider_apply")
    router.register("GET", "/market/providers/{provider_id}", router._market_provider, "market_provider")
    router.register("POST", "/market/providers/{provider_id}/verify", router._market_provider_verify, "market_provider_verify")
    router.register("POST", "/market/providers/{provider_id}/reject", router._market_provider_reject, "market_provider_reject")
    router.register("POST", "/market/providers/{provider_id}/request-revision", router._market_provider_request_revision, "market_provider_request_revision")
    router.register("POST", "/market/providers/{provider_id}/conformance", router._market_provider_conformance, "market_provider_conformance")
    router.register("POST", "/market/providers/{provider_id}/disable", router._market_provider_disable, "market_provider_disable")
    router.register("GET", "/market/providers/{provider_id}/reputation", router._market_provider_reputation, "market_provider_reputation")
    router.register("POST", "/market/quotes/ingest", router._market_quote_ingest, "market_quote_ingest")
    router.register("POST", "/market/quotes/compare", router._market_quote_compare, "market_quote_compare")
    router.register("POST", "/market/quotes/cache/invalidate", router._market_quote_cache_invalidate, "market_quote_cache_invalidate")
    router.register("GET", "/market/quotes/drift-observations", router._market_quote_drift, "market_quote_drift")
    router.register("POST", "/market/capacity/list", router._market_capacity_list, "market_capacity_list")
    router.register("POST", "/market/capacity/reserve", router._market_capacity_reserve, "market_capacity_reserve")
    router.register("POST", "/market/capacity/confirm", router._market_capacity_confirm, "market_capacity_confirm")
    router.register("POST", "/market/capacity/auction", router._market_capacity_auction, "market_capacity_auction")
    router.register("POST", "/market/capacity/expire", router._market_capacity_expire, "market_capacity_expire")
    router.register("POST", "/market/capacity/release", router._market_capacity_release, "market_capacity_release")
    router.register("GET", "/market/capacity/order-book", router._market_capacity_order_book, "market_capacity_order_book")
    router.register("GET", "/market/prices", router._market_prices, "market_prices")
    router.register("GET", "/market/prices/history", router._market_prices_history, "market_prices_history")
    router.register("GET", "/compute/prices", router._compute_prices, "compute_prices")
    router.register("GET", "/compute/prices/history", router._compute_prices_history, "compute_prices_history")
    router.register("GET", "/compute/prices/anomalies", router._compute_prices_anomalies, "compute_prices_anomalies")
    router.register("POST", "/compute/prices/forecast", router._compute_prices_forecast, "compute_prices_forecast")
    router.register("GET", "/compute/usage", router._compute_usage, "compute_usage")
    router.register("GET", "/compute/usage/by-agent/{agent_id}", router._compute_usage_by_agent, "compute_usage_by_agent")
    router.register("GET", "/compute/usage/by-goal/{goal_id}", router._compute_usage_by_goal, "compute_usage_by_goal")
    router.register("GET", "/compute/usage/statement", router._compute_usage_statement, "compute_usage_statement")
    router.register("GET", "/compute/routes", router._compute_routes, "compute_routes")
    router.register("GET", "/compute/routes/{route_id}", router._compute_route_get, "compute_route_get")
    router.register("POST", "/compute/routes", router._compute_route_create, "compute_route_create")
    router.register("PATCH", "/compute/routes/{route_id}", router._compute_route_update, "compute_route_update")
    router.register("POST", "/compute/routes/{route_id}/disable", router._compute_route_disable, "compute_route_disable")
    router.register("GET", "/compute/policies", router._compute_policies, "compute_policies")
    router.register("GET", "/compute/policies/{policy_id}", router._compute_policy, "compute_policy")
    router.register("POST", "/compute/policies", router._compute_policy_create, "compute_policy_create")
    router.register("PATCH", "/compute/policies/{policy_id}", router._compute_policy_update, "compute_policy_update")
    router.register("POST", "/compute/policies/{policy_id}/validate", router._compute_policy_validate, "compute_policy_validate")
    router.register("GET", "/compute/economic-memory", router._compute_economic_memory, "compute_economic_memory")
    router.register("GET", "/compute/economic-memory/summary", router._compute_economic_memory_summary, "compute_economic_memory_summary")
    router.register("GET", "/compute/economic-memory/anomalies", router._compute_economic_memory_anomalies, "compute_economic_memory_anomalies")
    router.register("GET", "/compute/economic-memory/providers/{provider_id}", router._compute_economic_memory_provider, "compute_economic_memory_provider")
    router.register("GET", "/compute/economic-memory/routes/{route_id}", router._compute_economic_memory_route, "compute_economic_memory_route")
    router.register("GET", "/compute/economic-memory/tasks/{task_type}", router._compute_economic_memory_task, "compute_economic_memory_task")
    router.register("POST", "/compute/economic-memory/query", router._compute_economic_memory_query, "compute_economic_memory_query")
    router.register("GET", "/compute/decisions/{decision_id}", router._compute_decision, "compute_decision")
    router.register("POST", "/compute/decisions/{decision_id}/replay", router._compute_decision_replay, "compute_decision_replay")
    router.register("GET", "/compute/audit", router._compute_audit, "compute_audit")
    router.register("GET", "/compute/audit/verify", router._compute_audit_verify, "compute_audit_verify")
    router.register("POST", "/compute/audit/export", router._compute_audit_export, "compute_audit_export")
    router.register("POST", "/compute/audit/checkpoint", router._compute_audit_checkpoint, "compute_audit_checkpoint")
    router.register("POST", "/compute/audit/verify-export", router._compute_audit_verify_export, "compute_audit_verify_export")
    router.register("POST", "/compute/audit/checkpoint-schedule", router._compute_audit_checkpoint_schedule, "compute_audit_checkpoint_schedule")
    router.register("GET", "/compute/audit/chain/monitor", router._compute_audit_chain_monitor, "compute_audit_chain_monitor")
    router.register("POST", "/compute/audit/replay", router._compute_audit_replay, "compute_audit_replay")
    router.register("GET", "/compute/audit/{audit_event_id}", router._compute_audit_event, "compute_audit_event")
    router.register("GET", "/compute/health", router._compute_health, "compute_health")
    router.register("GET", "/compute/readiness", router._compute_readiness, "compute_readiness")
    router.register("GET", "/compute/telemetry", router._compute_telemetry, "compute_telemetry")
    router.register("GET", "/compute/metrics", router._compute_metrics, "compute_metrics")
    router.register("GET", "/compute/alerts", router._compute_alerts, "compute_alerts")
    router.register("POST", "/compute/alerts/route", router._compute_alert_route, "compute_alert_route")
    router.register("POST", "/compute/alerts/{rule_name}/ack", router._compute_alert_ack, "compute_alert_ack")
    router.register("POST", "/compute/errors/track", router._compute_track_error, "compute_track_error")
    router.register("POST", "/billing/checkout", router._billing_checkout, "billing_checkout")
    router.register("POST", "/billing/webhooks/stripe", router._billing_webhook_stripe, "billing_webhook_stripe")
    router.register("GET", "/billing/balance", router._billing_balance, "billing_balance")
    router.register("GET", "/billing/quota", router._billing_quota, "billing_quota")
    router.register("POST", "/billing/quota", router._billing_quota_set, "billing_quota_set")
    router.register("GET", "/billing/usage", router._billing_usage, "billing_usage")
    router.register("GET", "/billing/provider-payouts", router._billing_provider_payouts, "billing_provider_payouts")
    router.register("POST", "/billing/provider-payouts/{payout_id}/settle", router._billing_provider_payout_settle, "billing_provider_payout_settle")
    router.register("POST", "/billing/refund", router._billing_refund, "billing_refund")
    router.register("GET", "/admin/reconciliation", router._admin_reconciliation, "admin_reconciliation")
    router.register("POST", "/admin/providers/{provider_id}/approve", router._admin_provider_approve, "admin_provider_approve")
    router.register("POST", "/admin/providers/{provider_id}/suspend", router._admin_provider_suspend, "admin_provider_suspend")
    router.register("POST", "/admin/routes/{route_id}/disable", router._admin_route_disable, "admin_route_disable")
    router.register("POST", "/admin/policies/{policy_id}/publish", router._admin_policy_publish, "admin_policy_publish")
    router.register("GET", "/admin/storage/diagnostics", router._admin_storage_diagnostics, "admin_storage_diagnostics")
    router.register("GET", "/admin/redis/diagnostics", router._admin_redis_diagnostics, "admin_redis_diagnostics")
    router.register("GET", "/admin/audit/export", router._admin_audit_export_status, "admin_audit_export_status")
    router.register("POST", "/admin/compute/otlp/export", router._admin_otlp_export, "admin_otlp_export")
    router.register("GET", "/manifest", router._manifest, "manifest")
    return router


def manifest() -> Mapping[str, Any]:
    return endpoint_manifest()


def _membership_key(workspace_id: str, user_id: str) -> str:
    return f"{workspace_id}:{user_id}"


def _payload_tenant_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("tenant_id", "")).strip()


def _payload_workspace_id(payload: Mapping[str, Any]) -> str:
    return str(payload.get("workspace_id", "")).strip()


def _tenant_can_access_auth_record(tenant_id: str, workspace_id: str, record: Mapping[str, Any]) -> bool:
    if tenant_id and str(record.get("tenant_id", "")).strip() != tenant_id:
        return False
    if workspace_id:
        record_workspace_id = str(record.get("workspace_id", "")).strip()
        if record_workspace_id and record_workspace_id != workspace_id:
            return False
    return True

def _assert_user_access(payload: Mapping[str, Any], record: Mapping[str, Any], action: str) -> None:
    tenant_id = _payload_tenant_id(payload)
    record_tenant_id = str(record.get("tenant_id", "")).strip()
    if tenant_id and record_tenant_id and record_tenant_id != tenant_id:
        raise forbidden_error(
            f"Tenant-scoped admin cannot {action} another tenant's user",
            details={"tenant_id": tenant_id, "requested_tenant_id": record_tenant_id},
        )
    workspace_id = _payload_workspace_id(payload)
    record_workspace_id = str(record.get("workspace_id", "")).strip()
    if workspace_id and record_workspace_id and record_workspace_id != workspace_id:
        raise forbidden_error(
            f"Workspace-scoped admin cannot {action} another workspace's user",
            details={"workspace_id": workspace_id, "requested_workspace_id": record_workspace_id},
        )

def _assert_workspace_access(payload: Mapping[str, Any], record: Mapping[str, Any], action: str) -> None:
    tenant_id = _payload_tenant_id(payload)
    record_tenant_id = str(record.get("tenant_id", "")).strip()
    if tenant_id and record_tenant_id and record_tenant_id != tenant_id:
        raise forbidden_error(
            f"Tenant-scoped admin cannot {action} another tenant's workspace",
            details={"tenant_id": tenant_id, "requested_tenant_id": record_tenant_id},
        )
    workspace_id = _payload_workspace_id(payload)
    record_workspace_id = str(record.get("workspace_id", "")).strip()
    if workspace_id and record_workspace_id and record_workspace_id != workspace_id:
        raise forbidden_error(
            f"Workspace-scoped admin cannot {action} another workspace",
            details={"workspace_id": workspace_id, "requested_workspace_id": record_workspace_id},
        )


def _assert_auth_record_tenant_access(payload: Mapping[str, Any], record: Mapping[str, Any], action: str) -> None:
    tenant_id = _payload_tenant_id(payload)
    record_tenant_id = str(record.get("tenant_id", "")).strip()
    if tenant_id and record_tenant_id != tenant_id:
        raise forbidden_error(
            f"Tenant-scoped admin cannot {action} another tenant's API key",
            details={"tenant_id": tenant_id, "requested_tenant_id": record_tenant_id},
        )
    workspace_id = _payload_workspace_id(payload)
    record_workspace_id = str(record.get("workspace_id", "")).strip()
    if workspace_id and record_workspace_id and record_workspace_id != workspace_id:
        raise forbidden_error(
            f"Workspace-scoped admin cannot {action} another workspace's API key",
            details={"workspace_id": workspace_id, "requested_workspace_id": record_workspace_id},
        )

def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path if path.startswith("/") else f"/{path}"
    return normalized.rstrip("/") or "/"


def _split_path(path: str) -> tuple[str, ...]:
    normalized = _normalize_path(path)
    if normalized == "/":
        return ()
    return tuple(part for part in normalized.strip("/").split("/") if part)


def _match(route_parts: tuple[str, ...], request_parts: tuple[str, ...]) -> dict[str, str] | None:
    if len(route_parts) != len(request_parts):
        return None
    params: dict[str, str] = {}
    for route_part, request_part in zip(route_parts, request_parts):
        if route_part.startswith("{") and route_part.endswith("}"):
            params[route_part[1:-1]] = unquote(request_part)
            continue
        if route_part != request_part:
            return None
    return params
