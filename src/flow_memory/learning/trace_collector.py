"""Collect structured traces from Flow Memory agent cycles."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class AgentLearningTrace:
    agent_id: str
    goal: str
    observation: Mapping[str, Any]
    plan: Mapping[str, Any]
    policy_decision: Mapping[str, Any]
    action_result: Mapping[str, Any]
    evaluation: Mapping[str, Any]
    memory_writes: tuple[Mapping[str, Any], ...]
    economic_outcome: Mapping[str, Any] | None = None
    rl_reward: float | None = None
    neural_metadata: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: new_id("learning_trace"))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def success(self) -> bool:
        if "success" in self.evaluation:
            return bool(self.evaluation.get("success"))
        if "metrics" in self.evaluation:
            return bool(dict(self.evaluation.get("metrics", {})).get("observed_success", 0.0))
        return bool(self.action_result.get("success", False))

    def as_record(self) -> Mapping[str, Any]:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "goal": self.goal,
            "observation": dict(self.observation),
            "plan": dict(self.plan),
            "policy_decision": dict(self.policy_decision),
            "action_result": dict(self.action_result),
            "evaluation": dict(self.evaluation),
            "memory_writes": tuple(dict(item) for item in self.memory_writes),
            "economic_outcome": dict(self.economic_outcome) if self.economic_outcome else None,
            "rl_reward": self.rl_reward,
            "neural_metadata": dict(self.neural_metadata),
            "success": self.success(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TraceCollector:
    traces: list[AgentLearningTrace] = field(default_factory=list)

    def collect(self, *, agent_id: str, goal: str, result_record: Mapping[str, Any], rl_reward: float | None = None) -> AgentLearningTrace:
        output = dict(result_record.get("output", {}))
        state = dict(result_record.get("state", {}))
        trace = AgentLearningTrace(
            agent_id=agent_id,
            goal=goal,
            observation={"goal": goal, "state_status": state.get("lifecycle_status", "")},
            plan=dict(state.get("current_plan", {})),
            policy_decision={"requires_approval": result_record.get("requires_approval", False), "accepted": result_record.get("accepted", False)},
            action_result=dict(output.get("execution", output)),
            evaluation=dict(output.get("evaluation", {})),
            memory_writes=tuple(dict(item) for item in result_record.get("memory_records", ())),
            economic_outcome=output.get("settlement"),
            rl_reward=rl_reward,
            neural_metadata=dict(output.get("neural", {})),
        )
        self.traces.append(trace)
        return trace

    def as_records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(trace.as_record() for trace in self.traces)
