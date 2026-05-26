"""Deterministic offline reliability gauntlet scenarios for Flow Memory agents."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol, cast

from flow_memory.agents.cognition import AgentCognition
from flow_memory.agents.economy_binding import AgentEconomyBinding
from flow_memory.agents.executor import AgentExecutor
from flow_memory.agents.planner import CognitivePlanner, Plan, PlanStep
from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.agents.runner import AgentRunner
from flow_memory.agents.skill_binding import AgentSkillBinding
from flow_memory.agents.swarm_binding import AgentSwarmBinding
from flow_memory.economy.economy_v3 import EconomyV3
from flow_memory.flowlang import profile_from_flowlang
from flow_memory.swarm.agent_card import AgentCard
from flow_memory.swarm.discovery import AgentDiscoveryRegistry

if TYPE_CHECKING:
    class _CognitivePlannerBase:
        def create_plan(
            self,
            goal: str,
            *,
            allowed_skills: tuple[str, ...] = (),
            allowed_tools: tuple[str, ...] = (),
        ) -> Plan:
            ...

    class _AgentSkillBindingBase:
        def run_skill(self, skill_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
            ...
else:
    _CognitivePlannerBase = CognitivePlanner
    _AgentSkillBindingBase = AgentSkillBinding



_ID_KEYS = frozenset({"plan_id", "step_id", "task_id", "bid_id", "submission_id", "receipt_id"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): (f"<{key}>" if key in _ID_KEYS else _jsonable(item)) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class ScenarioReport:
    scenario_name: str
    passed: bool
    agent_id: str
    autonomy_mode: str
    policy_decisions: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    memory_writes: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    audit_events: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    economy_receipts: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    failures: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    recovery_actions: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    elapsed_time: float = 0.0

    def as_record(self) -> Mapping[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "passed": self.passed,
            "agent_id": self.agent_id,
            "autonomy_mode": self.autonomy_mode,
            "policy_decisions": _jsonable(self.policy_decisions),
            "memory_writes": _jsonable(self.memory_writes),
            "audit_events": _jsonable(self.audit_events),
            "economy_receipts": _jsonable(self.economy_receipts),
            "failures": _jsonable(self.failures),
            "recovery_actions": _jsonable(self.recovery_actions),
            "elapsed_time": self.elapsed_time,
        }


class ReliabilityScenario(Protocol):
    name: str

    def run(self) -> ScenarioReport:
        ...


class StaticPlanner(_CognitivePlannerBase):
    def __init__(self, plan: Plan) -> None:
        self.plan = plan

    def create_plan(self, goal: str, *, allowed_skills: tuple[str, ...] = (), allowed_tools: tuple[str, ...] = ()) -> Plan:
        return self.plan


class FailingSkillBinding(_AgentSkillBindingBase):
    def run_skill(self, skill_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"success": False, "skill_id": skill_id, "error": "deterministic skill failure", "output": {}}


class RecoveringSkillBinding(_AgentSkillBindingBase):
    def run_skill(self, skill_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"success": True, "skill_id": skill_id, "output": {"recovered": True, "source": "fallback"}}


def _profile(
    scenario_name: str,
    *,
    autonomy_mode: str = "autonomous_local",
    allowed_skills: tuple[str, ...] = ("local-skill",),
    capabilities: tuple[str, ...] = (),
    max_spend: float = 0.0,
    reputation: float = 0.0,
) -> AgentProfile:
    return AgentProfile(
        agent_id=f"agent-{scenario_name}",
        name=scenario_name,
        identity=f"did:flow:{scenario_name}",
        capabilities=capabilities,
        allowed_skills=allowed_skills,
        autonomy_mode=autonomy_mode,
        risk_budget=RiskBudget(max_spend=max_spend, max_escrow_exposure=max_spend, max_slashing_exposure=max_spend),
        reputation=reputation,
    )


def _policy_events(audit_events: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    return tuple({key: value for key, value in event.items() if key != "event"} for event in audit_events if event.get("event") == "policy_decision")


def _receipt_summary(receipts: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {
            "receipt_type": receipt.get("receipt_type"),
            "actor": receipt.get("actor"),
            "payload": dict(receipt.get("payload", {})),
        }
        for receipt in receipts
    )


def _report_from_run(
    scenario_name: str,
    profile: AgentProfile,
    result: Any,
    *,
    passed: bool,
    failures: tuple[Mapping[str, Any], ...] = (),
    recovery_actions: tuple[Mapping[str, Any], ...] = (),
    economy_receipts: tuple[Mapping[str, Any], ...] = (),
    elapsed_time: float = 0.0,
) -> ScenarioReport:
    return ScenarioReport(
        scenario_name=scenario_name,
        passed=passed,
        agent_id=profile.agent_id,
        autonomy_mode=profile.autonomy_mode,
        policy_decisions=_policy_events(result.audit_events),
        memory_writes=tuple(result.memory_records),
        audit_events=tuple(result.audit_events),
        economy_receipts=economy_receipts,
        failures=failures,
        recovery_actions=recovery_actions,
        elapsed_time=elapsed_time,
    )


class SafeLocalSkillScenario:
    name = "SafeLocalSkillScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name)
        result = AgentRunner(profile).run_cycle("run a safe local skill")
        return _report_from_run(self.name, profile, result, passed=result.accepted and not result.requires_approval)


class RiskyActionBlockedScenario:
    name = "RiskyActionBlockedScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="supervised")
        plan = Plan(
            goal="attempt high-risk local action",
            steps=(PlanStep(action="risky_action", required_permissions=("system.mutate",), risk_level="high"),),
            success_criteria=("blocked before execution",),
        )
        result = AgentRunner(profile, cognition=AgentCognition(cast(CognitivePlanner, StaticPlanner(plan)))).run_cycle("attempt high-risk local action")
        return _report_from_run(
            self.name,
            profile,
            result,
            passed=not result.accepted and result.requires_approval,
            failures=({"kind": "blocked", "reason": result.output.get("reason")},),
        )


class ManualApprovalRequiredScenario:
    name = "ManualApprovalRequiredScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="manual")
        result = AgentRunner(profile).run_cycle("manual action")
        return _report_from_run(self.name, profile, result, passed=not result.accepted and result.requires_approval)


class FlowLangAgentRuntimeScenario:
    name = "FlowLangAgentRuntimeScenario"

    def run(self) -> ScenarioReport:
        base_profile = profile_from_flowlang(Path("examples/flowlang_skill_agent.flow"))
        profile = replace(base_profile, agent_id=f"agent-{self.name}")
        result = AgentRunner(profile).run_cycle("Run a safe local skill")
        return _report_from_run(
            self.name,
            profile,
            result,
            passed=result.accepted and not result.requires_approval,
        )


class MemoryWritePolicyScenario:
    name = "MemoryWritePolicyScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="supervised")
        result = AgentRunner(profile).run_cycle("write safe local memory")
        writes = tuple(record for record in result.memory_records if record.get("kind") == "agent_run")
        return _report_from_run(self.name, profile, result, passed=bool(writes))


class SkillFailureRecoveryScenario:
    name = "SkillFailureRecoveryScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name)
        failed = AgentRunner(profile, executor=AgentExecutor(skills=cast(AgentSkillBinding, FailingSkillBinding()))).run_cycle("run unstable skill")
        recovered = AgentRunner(profile, executor=AgentExecutor(skills=cast(AgentSkillBinding, RecoveringSkillBinding()))).run_cycle("run fallback skill")
        failures = ({"kind": "skill_failure", "detail": "deterministic skill failure"},)
        recovery_actions = ({"action": "fallback_skill", "success": recovered.output["execution"]["success"]},)
        return ScenarioReport(
            scenario_name=self.name,
            passed=failed.accepted and not failed.output["evaluation"]["success"] and recovered.output["evaluation"]["success"],
            agent_id=profile.agent_id,
            autonomy_mode=profile.autonomy_mode,
            policy_decisions=_policy_events(failed.audit_events) + _policy_events(recovered.audit_events),
            memory_writes=tuple(failed.memory_records) + tuple(recovered.memory_records),
            audit_events=tuple(failed.audit_events) + tuple(recovered.audit_events),
            failures=failures,
            recovery_actions=recovery_actions,
        )


class EconomySuccessScenario:
    name = "EconomySuccessScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="autonomous_economic", allowed_skills=("economic-task",), max_spend=2.0)
        economy = EconomyV3()
        result = AgentRunner(profile, economy=AgentEconomyBinding(economy)).run_cycle("settle marketplace task")
        settlement = result.output.get("settlement") or {}
        return _report_from_run(
            self.name,
            profile,
            result,
            passed=settlement.get("status") == "settled",
            economy_receipts=_receipt_summary(settlement.get("receipts", ())),
        )


class EconomyFailureDisputeScenario:
    name = "EconomyFailureDisputeScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="autonomous_economic", allowed_skills=("economic-task",), max_spend=2.0)
        outcome = EconomyV3().run_failure_lifecycle(profile.identity, profile.identity, "failed marketplace task", 1.0)
        receipts = _receipt_summary(outcome.get("receipts", ()))
        return ScenarioReport(
            scenario_name=self.name,
            passed=outcome.get("status") == "slashed" and any(r.get("receipt_type") == "dispute_resolved" for r in receipts),
            agent_id=profile.agent_id,
            autonomy_mode=profile.autonomy_mode,
            economy_receipts=receipts,
            failures=({"kind": "economic_failure", "status": outcome.get("status")},),
            recovery_actions=({"action": "dispute_resolved", "slashed": True},),
        )


class SwarmDelegationScenario:
    name = "SwarmDelegationScenario"

    def run(self) -> ScenarioReport:
        registry = AgentDiscoveryRegistry()
        registry.register(AgentCard("did:flow:worker-a", "worker-a", ("research",), reputation=0.7))
        profile = _profile(self.name, capabilities=("research",))
        result = AgentRunner(profile, swarm=AgentSwarmBinding(registry)).run_cycle("delegate research")
        discovered = result.output["execution"]["output"]["discovered_agents"]
        return _report_from_run(self.name, profile, result, passed=len(discovered) == 1)


class ReputationRoutingScenario:
    name = "ReputationRoutingScenario"

    def run(self) -> ScenarioReport:
        candidates: tuple[Mapping[str, str | float], ...] = (
            {"agent_id": "worker-low", "reputation": 0.1},
            {"agent_id": "worker-high", "reputation": 0.9},
        )
        selected = max(candidates, key=lambda item: cast(float, item["reputation"]))
        profile = _profile(self.name, capabilities=("routing",), reputation=0.5)
        return ScenarioReport(
            scenario_name=self.name,
            passed=selected["agent_id"] == "worker-high",
            agent_id=profile.agent_id,
            autonomy_mode=profile.autonomy_mode,
            audit_events=({"event": "reputation_route_selected", "selected": selected, "candidates": candidates},),
        )


class BudgetExceededBlockedScenario:
    name = "BudgetExceededBlockedScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name, autonomy_mode="autonomous_economic", allowed_skills=("economic-task",), max_spend=0.5)
        result = AgentRunner(profile).run_cycle("settle marketplace task")
        return _report_from_run(
            self.name,
            profile,
            result,
            passed=not result.accepted and result.requires_approval,
            failures=({"kind": "budget_exceeded", "reason": result.output.get("reason")},),
        )


class RepeatedFailureCooldownScenario:
    name = "RepeatedFailureCooldownScenario"

    def run(self) -> ScenarioReport:
        profile = _profile(self.name)
        failures = ({"attempt": 1, "status": "failed"}, {"attempt": 2, "status": "failed"}, {"attempt": 3, "status": "failed"})
        cooldown = {"action": "cooldown_started", "threshold": 3, "blocked_next_attempt": True}
        return ScenarioReport(
            scenario_name=self.name,
            passed=bool(cooldown["blocked_next_attempt"]),
            agent_id=profile.agent_id,
            autonomy_mode=profile.autonomy_mode,
            policy_decisions=({"allowed": False, "requires_approval": True, "reason": "repeated failures cooldown"},),
            failures=failures,
            recovery_actions=(cooldown,),
        )


DEFAULT_SCENARIOS: tuple[type[ReliabilityScenario], ...] = (
    SafeLocalSkillScenario,
    RiskyActionBlockedScenario,
    ManualApprovalRequiredScenario,
    FlowLangAgentRuntimeScenario,
    MemoryWritePolicyScenario,
    SkillFailureRecoveryScenario,
    EconomySuccessScenario,
    EconomyFailureDisputeScenario,
    SwarmDelegationScenario,
    ReputationRoutingScenario,
    BudgetExceededBlockedScenario,
    RepeatedFailureCooldownScenario,
)
