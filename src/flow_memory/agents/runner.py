"""Runnable Flow Memory agent abstraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents.cognition import AgentCognition
from flow_memory.agents.compute_binding import AgentComputeBinding
from flow_memory.agents.economy_binding import AgentEconomyBinding
from flow_memory.agents.evaluator import AgentEvaluator
from flow_memory.agents.executor import AgentExecutor
from flow_memory.agents.memory_binding import AgentMemoryBinding
from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.rl_binding import AgentRlBinding
from flow_memory.agents.policy_binding import AgentPolicyBinding
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.reflection import AgentReflector
from flow_memory.agents.state import AgentState
from flow_memory.agents.swarm_binding import AgentSwarmBinding
from flow_memory.agents.task_graph import graph_from_steps


@dataclass(frozen=True)
class AgentRunResult:
    accepted: bool
    requires_approval: bool
    output: Mapping[str, Any]
    state: Mapping[str, Any]
    audit_events: tuple[Mapping[str, Any], ...]
    memory_records: tuple[Mapping[str, Any], ...]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "accepted": self.accepted,
            "requires_approval": self.requires_approval,
            "output": dict(self.output),
            "state": dict(self.state),
            "audit_events": tuple(dict(event) for event in self.audit_events),
            "memory_records": tuple(dict(record) for record in self.memory_records),
        }


@dataclass
class AgentRunner:
    profile: AgentProfile
    state: AgentState = field(default_factory=AgentState)
    cognition: AgentCognition = field(default_factory=AgentCognition)
    policy: AgentPolicyBinding = field(default_factory=AgentPolicyBinding)
    executor: AgentExecutor = field(default_factory=AgentExecutor)
    memory: AgentMemoryBinding = field(default_factory=AgentMemoryBinding)
    economy: AgentEconomyBinding = field(default_factory=AgentEconomyBinding)
    evaluator: AgentEvaluator = field(default_factory=AgentEvaluator)
    reflector: AgentReflector = field(default_factory=AgentReflector)
    swarm: AgentSwarmBinding = field(default_factory=AgentSwarmBinding)
    neural: AgentNeuralBinding = field(default_factory=AgentNeuralBinding)
    rl: AgentRlBinding = field(default_factory=AgentRlBinding)
    compute: AgentComputeBinding = field(default_factory=AgentComputeBinding)

    def run_cycle(self, user_input: str) -> AgentRunResult:
        self.state.lifecycle_status = "running"
        goal = user_input or (self.profile.goals[0] if self.profile.goals else "Explore and report")
        self.state.current_goal = goal
        context = self.memory.load_context(goal)
        discovered_agents = self.swarm.discover(self.profile.capabilities[0]) if self.profile.capabilities else ()
        plan = self.cognition.plan(self.profile, goal)
        graph = graph_from_steps(tuple(step.action for step in plan.steps))
        self.state.current_plan = plan.as_record()
        self.state.current_task_graph = graph.as_record()
        neural_metadata = self.neural.annotate_plan(self.profile, goal, plan, tuple(context))
        rl_metadata = self.rl.suggest(self.profile, goal)
        compute_metadata = self.compute.plan(self.profile, goal, plan)
        decision = self.policy.check_plan(self.profile, plan)
        audit_events: list[Mapping[str, Any]] = [
            {"event": "agent_cycle_started", "agent_id": self.profile.agent_id, "goal": goal},
            {"event": "plan_created", "plan_id": plan.plan_id, "risk_level": plan.risk_level},
            {"event": "neural_plan_annotated", "backend": neural_metadata.get("backend"), "status": neural_metadata.get("status", "available")},
            {"event": "rl_policy_suggested", "enabled": rl_metadata.get("enabled", False), "safety_authority": rl_metadata.get("safety_authority", "")},
            {"event": "compute_market_planned", "status": compute_metadata.get("status", "disabled"), "dry_run_only": compute_metadata.get("dry_run_only", True)},
            {"event": "policy_decision", **decision.as_record()},
        ]
        if compute_metadata.get("status") == "fail_closed":
            reason = str(compute_metadata.get("reason", "compute market policy failed closed"))
            self.state.add_event({"event": "compute_market_denied", "reason": reason})
            output = {"success": False, "blocked": True, "reason": reason}
            evaluation = self.evaluator.evaluate(output)
            reflection = self.reflector.reflect(evaluation)
            self.state.last_evaluation = evaluation.as_record()
            self.memory.write("compute_market_denied", {"goal": goal, "reason": reason, "compute": compute_metadata})
            audit_events.append({"event": "agent_cycle_blocked", "reason": reason, "blocked_by": "compute_market"})
            return AgentRunResult(False, True, {"evaluation": evaluation.as_record(), "reflection": reflection.as_record(), "neural": neural_metadata, "rl": rl_metadata, "compute": compute_metadata, **output}, self.state.as_record(), tuple(audit_events), tuple(self.memory.records))
        if decision.requires_approval and not decision.allowed:
            approval = {"plan_id": plan.plan_id, "reason": decision.reason, "permissions": plan.required_permissions}
            self.state.outstanding_approvals.append(approval)
            self.state.add_event({"event": "approval_required", **approval})
            output = {"success": False, "blocked": True, "reason": decision.reason}
            evaluation = self.evaluator.evaluate(output)
            reflection = self.reflector.reflect(evaluation)
            self.state.last_evaluation = evaluation.as_record()
            self.memory.write("blocked_plan", {"goal": goal, "reason": decision.reason})
            audit_events.append({"event": "agent_cycle_blocked", "reason": decision.reason})
            return AgentRunResult(False, True, {"evaluation": evaluation.as_record(), "reflection": reflection.as_record(), "neural": neural_metadata, "rl": rl_metadata, "compute": compute_metadata, **output}, self.state.as_record(), tuple(audit_events), tuple(self.memory.records))

        payload = {"goal": goal, "context": tuple(context), "agent_id": self.profile.agent_id, "discovered_agents": discovered_agents}
        execution = self.executor.execute(plan, payload)
        settlement = self.economy.maybe_settle(self.profile.identity or self.profile.agent_id, self.profile.identity or self.profile.agent_id, goal, plan.economic_value) if plan.economic_intent else None
        if compute_metadata.get("status") == "planned" and compute_metadata.get("economic_memory"):
            self.memory.write("compute_economic_memory", dict(compute_metadata.get("economic_memory", {})))
        evaluation = self.evaluator.evaluate(execution, expected=plan.success_criteria)
        reflection = self.reflector.reflect(evaluation)
        memory_record = self.memory.write("agent_run", {"goal": goal, "plan": plan.as_record(), "execution": execution, "settlement": settlement, "neural": neural_metadata, "rl": rl_metadata, "compute": compute_metadata})
        self.state.working_memory_snapshot = (memory_record,)
        self.state.last_evaluation = evaluation.as_record()
        self.state.lifecycle_status = "idle"
        self.state.add_event({"event": "agent_cycle_completed", "success": evaluation.success})
        audit_events.append({"event": "agent_cycle_completed", "success": evaluation.success})
        return AgentRunResult(True, False, {"execution": execution, "settlement": settlement, "evaluation": evaluation.as_record(), "reflection": reflection.as_record(), "neural": neural_metadata, "rl": rl_metadata, "compute": compute_metadata}, self.state.as_record(), tuple(audit_events), tuple(self.memory.records))


def run_agent_cycle(agent: AgentProfile, user_input: str) -> AgentRunResult:
    return AgentRunner(agent).run_cycle(user_input)
