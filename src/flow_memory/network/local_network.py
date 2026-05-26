"""Local in-process Flow Memory network for public-alpha demos and tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents.runner import AgentRunner

from flow_memory.economy.economy_v3 import EconomyV3
from flow_memory.network.receipts import NetworkReceipt
from flow_memory.network.reports import LocalNetworkReport, ScenarioReport
from flow_memory.network.topology import LocalNetworkTopology, default_topology
from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv
from flow_memory.rl.trainer import SimpleQLearningTrainer
from flow_memory.visualization import VisualEvent, reduce_visual_events, visual_event
from flow_memory.visualization.adapters import agent_participants_to_visual_events, economy_receipts_to_visual_events, neural_record_to_visual_events, rl_record_to_visual_events, safety_record_to_visual_events


@dataclass
class LocalFlowMemoryNetwork:
    topology: LocalNetworkTopology = field(default_factory=default_topology)
    economy: EconomyV3 = field(default_factory=EconomyV3)
    receipts: list[NetworkReceipt] = field(default_factory=list)
    audit_events: list[Mapping[str, Any]] = field(default_factory=list)
    visual_events: list[Mapping[str, Any]] = field(default_factory=list)
    visualized_receipt_ids: set[str] = field(default_factory=set)
    emit_visual: bool = False

    def run_basic_economy(self) -> ScenarioReport:
        requester = self.topology.by_role("requester")
        worker = self.topology.by_role("worker")
        verifier = self.topology.by_role("verifier")
        result = self.economy.run_success_lifecycle(requester.profile.identity, worker.profile.identity, "Public-alpha launch readiness task", 3.0)
        self._extend_visual(economy_receipts_to_visual_events(self._new_visual_receipts(tuple(result.get("receipts", ())), provenance="live")))
        self._extend_visual(safety_record_to_visual_events({"decision_id": f"policy-{result['task_id']}", "approved": True, "risk_level": "low", "reasons": ()}, agent_id=requester.profile.identity))
        self._receipt("basic_economy_completed", requester.profile.identity, {"task_id": result["task_id"], "worker": worker.profile.identity, "verifier": verifier.profile.identity})
        return ScenarioReport("basic-economy", result["status"] == "settled", "requester posted a task, worker completed it, verifier path settled locally", result)

    def run_neural_agent(self) -> ScenarioReport:
        worker = self.topology.by_role("worker")
        profile = worker.profile.__class__(**{**worker.profile.as_record(), "created_at": worker.profile.created_at, "risk_budget": worker.profile.risk_budget, "neural_config": {"backend": "tiny_torch", "perception": "dual_stream"}})
        result = AgentRunner(profile).run_cycle("Explore and report")
        neural = dict(result.output.get("neural", {}))
        ok = bool(result.accepted or result.requires_approval) and neural.get("backend") == "tiny_torch"
        data = {"accepted": result.accepted, "requires_approval": result.requires_approval, "neural": neural, "audit_events": tuple(result.audit_events)}
        self._extend_visual(neural_record_to_visual_events(neural, agent_id=profile.identity))
        self._extend_visual(safety_record_to_visual_events({"decision_id": f"neural-policy-{profile.agent_id}", "approved": result.accepted, "requires_human": result.requires_approval, "risk_level": "low"}, agent_id=profile.identity))
        self._receipt("neural_agent_cycle", profile.identity, data)
        return ScenarioReport("neural-agent", ok, "agent ran with neural advisory metadata; safety remains authoritative", data)

    def run_rl_training(self) -> ScenarioReport:
        env = SafetyGateEnv(seed=11, max_steps=3)
        trainer = SimpleQLearningTrainer(env)
        result = trainer.train(episodes=16)
        data = {**dict(result.as_record()), "advisory_only": True, "safety_authority": "policy_engine_and_approval_gate"}
        self._extend_visual(rl_record_to_visual_events({"episode_id": "rl-safety-gate", "env_id": "safety_gate", "metrics": data}, agent_id="did:flow:worker"))
        self._receipt("rl_training_completed", "did:flow:worker", data)
        return ScenarioReport("rl-training", bool(result.improved), "tabular policy improved or matched reward on SafetyGateEnv", data)

    def run_dispute_slashing(self) -> ScenarioReport:
        requester = self.topology.by_role("requester")
        worker = self.topology.by_role("worker")
        result = self.economy.run_failure_lifecycle(requester.profile.identity, worker.profile.identity, "Bad work dispute task", 2.0)
        ok = result["status"] == "slashed"
        self._extend_visual(economy_receipts_to_visual_events(self._new_visual_receipts(tuple(result.get("receipts", ())), provenance="live")))
        self._extend_visual(safety_record_to_visual_events({"decision_id": f"slash-{result['task_id']}", "approved": False, "requires_human": True, "risk_level": "high", "reason": "bad work dispute resolved with slashing"}, agent_id=worker.profile.identity))
        self._receipt("dispute_slashing_completed", requester.profile.identity, {"task_id": result["task_id"], "worker": worker.profile.identity})
        return ScenarioReport("dispute-slashing", ok, "bad work produced a dispute and local reputation penalty", result)

    def run_memory_learning(self) -> ScenarioReport:
        worker = self.topology.by_role("worker")
        first = AgentRunner(worker.profile).run_cycle("Remember that verified local work should cite evidence")
        second = AgentRunner(worker.profile).run_cycle("Use memory to report verified local work")
        memory_events = (
            {"memory_id": f"memory-{worker.profile.agent_id}-1", "agent_id": worker.profile.identity, "kind": "episodic", "summary": "verified local work should cite evidence", "importance": 0.8},
            {"memory_id": f"memory-{worker.profile.agent_id}-2", "agent_id": worker.profile.identity, "kind": "procedural", "summary": "use prior evidence when reporting work", "importance": 0.7},
        )
        for item in memory_events:
            self._emit_visual("memory", worker.profile.identity, item)
        data = {"first_accepted": first.accepted, "second_accepted": second.accepted, "memory_writes": memory_events, "audit_events": tuple(first.audit_events + second.audit_events)}
        self._receipt("memory_learning_completed", worker.profile.identity, data)
        return ScenarioReport("memory-learning", first.accepted and second.accepted, "agent wrote and reused local memory traces", data)

    def run_safety_approval(self) -> ScenarioReport:
        requester = self.topology.by_role("requester")
        decision = {"decision_id": "safety-approval-demo", "approved": False, "requires_human": True, "risk_level": "high", "reasons": ("external/economic action requires approval",)}
        self._extend_visual(safety_record_to_visual_events(decision, agent_id=requester.profile.identity))
        data = {"policy_decision": decision, "blocked": True, "safety_authority": "policy_engine_and_approval_gate"}
        self._receipt("safety_approval_required", requester.profile.identity, data)
        return ScenarioReport("safety-approval", True, "risky/economic action was routed to approval instead of executing", data)

    def register_router_agents(self) -> Mapping[str, Any]:
        from flow_memory.api.router import create_default_router
        router = create_default_router()
        for item in self.topology.participants:
            router.register_agent(item.card)
        health = router.dispatch("GET", "/health")
        agents = router.dispatch("GET", "/agents")
        self._receipt("api_router_checked", "did:flow:auditor", {"agent_count": len(agents.get("agents", ()))})
        return {"health": health, "agents": agents, "audit_events": tuple(router.audit_events)}

    def run(self, scenario: str = "all", *, emit_visual_events: bool = False) -> LocalNetworkReport:
        previous_emit = self.emit_visual
        self.emit_visual = emit_visual_events
        if emit_visual_events:
            self.visual_events.clear()
            self._extend_visual(agent_participants_to_visual_events((item.as_record() for item in self.topology.participants), provenance="live"))
        try:
            scenario_key = scenario.replace("_", "-")
            reports: tuple[ScenarioReport, ...]
            if scenario_key == "all":
                reports = (
                    self.run_basic_economy(),
                    self.run_neural_agent(),
                    self.run_rl_training(),
                    self.run_dispute_slashing(),
                    self.run_memory_learning(),
                    self.run_safety_approval(),
                )
            elif scenario_key == "basic-economy":
                reports = (self.run_basic_economy(),)
            elif scenario_key == "neural-agent":
                reports = (self.run_neural_agent(),)
            elif scenario_key == "rl-training":
                reports = (self.run_rl_training(),)
            elif scenario_key == "dispute-slashing":
                reports = (self.run_dispute_slashing(),)
            elif scenario_key == "memory-learning":
                reports = (self.run_memory_learning(),)
            elif scenario_key == "safety-approval":
                reports = (self.run_safety_approval(),)
            else:
                raise ValueError(f"unknown local network scenario: {scenario}")
            visual_state = reduce_visual_events(self.visual_events, provenance="live").as_record() if emit_visual_events else {}
            return LocalNetworkReport(ok=all(report.ok for report in reports), scenarios=reports, topology=self.topology.as_record(), visual_events=tuple(self.visual_events), visual_state=visual_state)
        finally:
            self.emit_visual = previous_emit

    def _receipt(self, receipt_type: str, actor: str, payload: Mapping[str, Any]) -> None:
        receipt = NetworkReceipt(receipt_type, actor, dict(payload))
        self.receipts.append(receipt)
        record = receipt.as_record()
        self.audit_events.append(record)
        self._emit_visual("audit", actor, {"audit_id": record.get("receipt_id", receipt_type), "event_type": receipt_type, "actor_id": actor, "summary": receipt_type, "ok": True}, source_event_id=str(record.get("receipt_id", "")))

    def _emit_visual(self, event_type: str, source: str, payload: Mapping[str, Any], *, source_event_id: str = "") -> None:
        if not self.emit_visual:
            return
        self.visual_events.append(visual_event(event_type, source, payload, provenance="live", source_event_id=source_event_id).as_record())

    def _extend_visual(self, events: tuple[VisualEvent, ...]) -> None:
        if not self.emit_visual:
            return
        self.visual_events.extend(event.as_record() for event in events)

    def _new_visual_receipts(self, receipts: tuple[Mapping[str, Any], ...], *, provenance: str = "live") -> tuple[Mapping[str, Any], ...]:
        if provenance != "live":
            return receipts
        fresh: list[Mapping[str, Any]] = []
        for receipt in receipts:
            receipt_id = str(receipt.get("receipt_id", ""))
            if receipt_id and receipt_id in self.visualized_receipt_ids:
                continue
            if receipt_id:
                self.visualized_receipt_ids.add(receipt_id)
            fresh.append(receipt)
        return tuple(fresh)
