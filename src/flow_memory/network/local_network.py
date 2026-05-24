"""Local in-process Flow Memory network for public-alpha demos and tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents.runner import AgentRunner
from flow_memory.api.router import create_default_router
from flow_memory.economy.economy_v3 import EconomyV3
from flow_memory.network.receipts import NetworkReceipt
from flow_memory.network.reports import LocalNetworkReport, ScenarioReport
from flow_memory.network.topology import LocalNetworkTopology, default_topology
from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv
from flow_memory.rl.trainer import SimpleQLearningTrainer


@dataclass
class LocalFlowMemoryNetwork:
    topology: LocalNetworkTopology = field(default_factory=default_topology)
    economy: EconomyV3 = field(default_factory=EconomyV3)
    receipts: list[NetworkReceipt] = field(default_factory=list)
    audit_events: list[Mapping[str, Any]] = field(default_factory=list)

    def run_basic_economy(self) -> ScenarioReport:
        requester = self.topology.by_role("requester")
        worker = self.topology.by_role("worker")
        verifier = self.topology.by_role("verifier")
        result = self.economy.run_success_lifecycle(requester.profile.identity, worker.profile.identity, "Public-alpha launch readiness task", 3.0)
        self._receipt("basic_economy_completed", requester.profile.identity, {"task_id": result["task_id"], "worker": worker.profile.identity, "verifier": verifier.profile.identity})
        return ScenarioReport("basic-economy", result["status"] == "settled", "requester posted a task, worker completed it, verifier path settled locally", result)

    def run_neural_agent(self) -> ScenarioReport:
        worker = self.topology.by_role("worker")
        profile = worker.profile.__class__(**{**worker.profile.as_record(), "created_at": worker.profile.created_at, "risk_budget": worker.profile.risk_budget, "neural_config": {"backend": "tiny_torch", "perception": "dual_stream"}})
        result = AgentRunner(profile).run_cycle("Explore and report")
        neural = dict(result.output.get("neural", {}))
        ok = bool(result.accepted or result.requires_approval) and neural.get("backend") == "tiny_torch"
        data = {"accepted": result.accepted, "requires_approval": result.requires_approval, "neural": neural, "audit_events": tuple(result.audit_events)}
        self._receipt("neural_agent_cycle", profile.identity, data)
        return ScenarioReport("neural-agent", ok, "agent ran with neural advisory metadata; safety remains authoritative", data)

    def run_rl_training(self) -> ScenarioReport:
        env = SafetyGateEnv(seed=11, max_steps=3)
        trainer = SimpleQLearningTrainer(env)
        result = trainer.train(episodes=16)
        data = {**dict(result.as_record()), "advisory_only": True, "safety_authority": "policy_engine_and_approval_gate"}
        self._receipt("rl_training_completed", "did:flow:worker", data)
        return ScenarioReport("rl-training", bool(result.improved), "tabular policy improved or matched reward on SafetyGateEnv", data)

    def run_dispute_slashing(self) -> ScenarioReport:
        requester = self.topology.by_role("requester")
        worker = self.topology.by_role("worker")
        result = self.economy.run_failure_lifecycle(requester.profile.identity, worker.profile.identity, "Bad work dispute task", 2.0)
        ok = result["status"] == "slashed"
        self._receipt("dispute_slashing_completed", requester.profile.identity, {"task_id": result["task_id"], "worker": worker.profile.identity})
        return ScenarioReport("dispute-slashing", ok, "bad work produced a dispute and local reputation penalty", result)

    def register_router_agents(self) -> Mapping[str, Any]:
        router = create_default_router()
        for item in self.topology.participants:
            router.register_agent(item.card)
        health = router.dispatch("GET", "/health")
        agents = router.dispatch("GET", "/agents")
        self._receipt("api_router_checked", "did:flow:auditor", {"agent_count": len(agents.get("agents", ()))})
        return {"health": health, "agents": agents, "audit_events": tuple(router.audit_events)}

    def run(self, scenario: str = "all") -> LocalNetworkReport:
        scenario_key = scenario.replace("_", "-")
        if scenario_key == "all":
            reports = (
                self.run_basic_economy(),
                self.run_neural_agent(),
                self.run_rl_training(),
                self.run_dispute_slashing(),
            )
        elif scenario_key == "basic-economy":
            reports = (self.run_basic_economy(),)
        elif scenario_key == "neural-agent":
            reports = (self.run_neural_agent(),)
        elif scenario_key == "rl-training":
            reports = (self.run_rl_training(),)
        elif scenario_key == "dispute-slashing":
            reports = (self.run_dispute_slashing(),)
        else:
            raise ValueError(f"unknown local network scenario: {scenario}")
        return LocalNetworkReport(ok=all(report.ok for report in reports), scenarios=reports, topology=self.topology.as_record())

    def _receipt(self, receipt_type: str, actor: str, payload: Mapping[str, Any]) -> None:
        receipt = NetworkReceipt(receipt_type, actor, dict(payload))
        self.receipts.append(receipt)
        self.audit_events.append(receipt.as_record())
