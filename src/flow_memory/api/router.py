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
    router.register("POST", "/marketplace/tasks", router._marketplace_task_create, "marketplace_task_create")
    router.register("POST", "/marketplace/bids", router._marketplace_bid_create, "marketplace_bid_create")
    router.register("POST", "/marketplace/settle", router._marketplace_settle, "marketplace_settle")
    router.register("GET", "/reputation/{did}", router._reputation_lookup, "reputation_lookup")
    router.register("POST", "/attestations", router._attestation_create, "attestation_create")
    router.register("GET", "/audit", router._audit, "audit_log")
    router.register("GET", "/swarm/agents", router._agents_list, "swarm_agents")
    router.register("POST", "/swarm/delegate", router._swarm_delegate, "swarm_delegate")
    router.register("POST", "/verification/submit", router._verification_submit, "verification_submit_alias")
    router.register("POST", "/verification/{contract_id}", router._verification_submit, "verification_submit")
    router.register("GET", "/verification/result", router._verification_result, "verification_result_alias")
    router.register("GET", "/verification/{contract_id}", router._verification_result, "verification_result")
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
