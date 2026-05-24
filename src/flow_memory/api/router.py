"""Dependency-free internal API router."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import unquote

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
    neural_live_checkpoint,
    neural_live_create,
    neural_live_learn,
    neural_live_session,
    neural_live_sessions,
    neural_live_step,
    neural_live_stop,
    neural_train_smoke,
    neural_validate_smoke,
)
from flow_memory.api.rl_endpoints import rl_benchmarks, rl_envs, rl_evaluate, rl_train_smoke
from flow_memory.api.release_endpoints import release_decision_status, release_evidence_status
from flow_memory.api.dashboard_endpoints import dashboard_snapshot
from flow_memory.api.visual_endpoints import current_visual_events, current_visual_state, network_state, start_visual_replay, visual_replay, visual_schema_endpoint
from flow_memory.api.compute_endpoints import (
    compute_capacity_windows,
    compute_economic_memory,
    compute_economic_memory_query,
    compute_marketplace_plan_endpoint,
    compute_payment_plan,
    compute_plan,
    compute_policies,
    compute_providers,
    compute_quote,
    compute_route,
    compute_routes,
    compute_simulate_settlement,
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
            neural_config=dict(payload.get("neural", {})) if isinstance(payload.get("neural", {}), Mapping) else {},
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
        neural_config = {
            "backend": backend,
            "perception": "dual_stream",
            "enabled": True,
            "live_mode": bool(payload.get("live_mode", payload.get("neural_live", False))),
            "learning_enabled": bool(payload.get("learning_enabled", False)),
            "policy_fallback": str(payload.get("policy_fallback", "allow_non_neural")),
            "telemetry_enabled": True,
        }
        profile = AgentProfile(
            name=str(payload.get("name", "API Neural Launch Agent")),
            identity=str(payload.get("identity", "did:flow:api-neural-agent")),
            goals=(goal,),
            capabilities=("local_reasoning", "neural_advisory"),
            allowed_tools=("observe_environment", "respond"),
            allowed_skills=("research_brief",),
            neural_config=neural_config,
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
        return compile_flowlang(source).as_record()

    def _flowlang_validate(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        return {"errors": validate_flowlang(source)}

    def _flowlang_run(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        source = str(payload.get("source", EXAMPLE_FLOWLANG))
        prompt = str(payload.get("prompt", "Run the declared agent"))
        result = compile_flowlang(source)
        if not result.ok:
            return result.as_record()
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile("w", suffix=".flow", delete=False, encoding="utf-8") as handle:
            handle.write(source)
            path = Path(handle.name)
        try:
            return run_flowlang_agent(path, prompt)
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

    def _neural_live_create(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_live_session_create_requested", "local_only": True})
        return neural_live_create(payload)

    def _neural_live_sessions(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_live_sessions()

    def _neural_live_session(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return neural_live_session(params["session_id"])

    def _neural_live_step(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_live_step_requested", "session_id": params["session_id"], "local_only": True})
        return neural_live_step(params["session_id"], payload)

    def _neural_live_learn(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_live_learn_requested", "session_id": params["session_id"], "local_only": True})
        return neural_live_learn(params["session_id"], payload)

    def _neural_live_checkpoint(self, params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_live_checkpoint_requested", "session_id": params["session_id"], "metadata_only": True})
        return neural_live_checkpoint(params["session_id"], payload)

    def _neural_live_stop(self, params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "neural_live_stop_requested", "session_id": params["session_id"], "local_only": True})
        return neural_live_stop(params["session_id"])


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
        return LocalNetworkOrchestrator().run(scenario, emit_visual_events=emit_visual).as_record()

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

    def _compute_providers(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_providers()

    def _compute_routes(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_routes()

    def _compute_policies(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_policies()

    def _compute_capacity(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_capacity_windows()

    def _compute_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_plan_requested", "dry_run_only": True})
        return compute_plan(payload)

    def _compute_marketplace_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_marketplace_plan_requested", "dry_run_only": True})
        return compute_marketplace_plan_endpoint(payload)

    def _compute_quote(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_quote_requested", "dry_run_only": True})
        return compute_quote(payload)

    def _compute_route(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_route_requested", "dry_run_only": True})
        return compute_route(payload)

    def _compute_payment_plan(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_payment_plan_requested", "dry_run_only": True})
        return compute_payment_plan(payload)

    def _compute_simulate_settlement(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.audit_events.append({"event": "compute_settlement_simulated", "dry_run_only": True})
        return compute_simulate_settlement(payload)

    def _compute_economic_memory(self, _params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory()

    def _compute_economic_memory_query(self, _params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return compute_economic_memory_query(payload)


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
    router.register("POST", "/neural/live/sessions", router._neural_live_create, "neural_live_create")
    router.register("GET", "/neural/live/sessions", router._neural_live_sessions, "neural_live_sessions")
    router.register("GET", "/neural/live/sessions/{session_id}", router._neural_live_session, "neural_live_session")
    router.register("POST", "/neural/live/sessions/{session_id}/step", router._neural_live_step, "neural_live_step")
    router.register("POST", "/neural/live/sessions/{session_id}/learn", router._neural_live_learn, "neural_live_learn")
    router.register("POST", "/neural/live/sessions/{session_id}/checkpoint", router._neural_live_checkpoint, "neural_live_checkpoint")
    router.register("POST", "/neural/live/sessions/{session_id}/stop", router._neural_live_stop, "neural_live_stop")
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
    router.register("POST", "/compute/plan", router._compute_plan, "compute_plan")
    router.register("POST", "/compute/marketplace-plan", router._compute_marketplace_plan, "compute_marketplace_plan")
    router.register("POST", "/compute/quote", router._compute_quote, "compute_quote")
    router.register("POST", "/compute/route", router._compute_route, "compute_route")
    router.register("POST", "/compute/payment-plan", router._compute_payment_plan, "compute_payment_plan")
    router.register("POST", "/compute/simulate-settlement", router._compute_simulate_settlement, "compute_simulate_settlement")
    router.register("GET", "/compute/providers", router._compute_providers, "compute_providers")
    router.register("GET", "/compute/routes", router._compute_routes, "compute_routes")
    router.register("GET", "/compute/policies", router._compute_policies, "compute_policies")
    router.register("GET", "/compute/capacity", router._compute_capacity, "compute_capacity")
    router.register("GET", "/compute/economic-memory", router._compute_economic_memory, "compute_economic_memory")
    router.register("POST", "/compute/economic-memory/query", router._compute_economic_memory_query, "compute_economic_memory_query")
    router.register("GET", "/release/evidence", router._release_evidence, "release_evidence")
    router.register("GET", "/release/decision/{target}", router._release_decision, "release_decision")
    router.register("GET", "/dashboard/snapshot", router._dashboard_snapshot, "dashboard_snapshot")
    router.register("GET", "/manifest", router._manifest, "manifest")
    return router


def manifest() -> Mapping[str, Any]:
    return endpoint_manifest()


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
