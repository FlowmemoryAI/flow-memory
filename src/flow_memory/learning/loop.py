"""Concrete local learning loop for Flow Memory public alpha."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents import AgentProfile, AgentRunner
from flow_memory.learning.evaluation_history import EvaluationHistory
from flow_memory.learning.improvement_tracker import ImprovementTracker
from flow_memory.learning.memory_learning import MemoryLearningStore
from flow_memory.learning.neural_training import neural_training_status
from flow_memory.learning.reports import AgentLearningReport
from flow_memory.learning.rl_learning import run_safety_gate_learning
from flow_memory.learning.trace_collector import TraceCollector


@dataclass
class AgentLearningLoop:
    profile: AgentProfile
    collector: TraceCollector = field(default_factory=TraceCollector)
    memory: MemoryLearningStore = field(default_factory=MemoryLearningStore)
    history: EvaluationHistory = field(default_factory=EvaluationHistory)

    def run(self, goals: tuple[str, ...] = ("Explore and report", "Explore and report with memory")) -> AgentLearningReport:
        before_memory = len(self.memory.traces)
        rewards: list[float] = []
        safety_violations = 0
        disputes = 0
        for index, goal in enumerate(goals):
            result = AgentRunner(self.profile).run_cycle(goal)
            reward = 1.0 if result.accepted else -1.0
            rewards.append(reward)
            trace = self.collector.collect(agent_id=self.profile.agent_id, goal=goal, result_record=result.as_record(), rl_reward=reward)
            self.memory.add_trace(trace)
            self.history.add({"success": trace.success(), "goal": goal})
            if result.requires_approval:
                safety_violations += 0
            settlement = result.output.get("settlement")
            if isinstance(settlement, Mapping) and settlement.get("status") == "disputed":
                disputes += 1
        rl_report = run_safety_gate_learning(episodes=16)
        neural = neural_training_status()
        tracker = ImprovementTracker()
        tracker.add("memory_records", float(before_memory), float(len(self.memory.traces)))
        tracker.add("rl_reward", rl_report.before, rl_report.after)
        before_after = {"memory": self.memory.report(), "rl": rl_report.as_record(), "neural": neural.as_record(), "improvement": tracker.summary()}
        return AgentLearningReport(
            agent_id=self.profile.agent_id,
            episodes=len(goals),
            success_rate=self.history.success_rate(),
            average_reward=sum(rewards) / max(1, len(rewards)),
            safety_violations=safety_violations,
            disputes=disputes,
            memory_count=len(self.memory.traces),
            policy_changes=1 if rl_report.improved else 0,
            before_after=before_after,
            traces=self.collector.as_records(),
        )


def run_default_learning_loop() -> Mapping[str, Any]:
    profile = AgentProfile(
        name="Learning Loop Agent",
        identity="did:flow:learning-loop-agent",
        goals=("Explore and report",),
        capabilities=("local_reasoning", "memory_learning", "rl_advisory"),
        allowed_tools=("observe_environment", "respond"),
        allowed_skills=("research_brief",),
        autonomy_mode="autonomous_local",
        neural_config={"backend": "tiny_torch"},
        rl_config={"enabled": True, "backend": "local_tabular", "training_envs": ("safety_gate",)},
    )
    return AgentLearningLoop(profile).run().as_record()
