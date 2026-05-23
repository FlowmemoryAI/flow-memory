"""Local agent trace dataset for neural policy, routing, and evaluation smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from flow_memory.neural.traces import AgentTrace, EconomyTrace, PlanTrace, SkillTrace


class AgentTraceDataset:
    def __init__(self, traces: tuple[AgentTrace, ...] | None = None) -> None:
        self.traces = traces or default_agent_traces()

    def __len__(self) -> int:
        return len(self.traces)

    def __getitem__(self, index: int) -> AgentTrace:
        return self.traces[index]

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "AgentTraceDataset":
        traces: list[AgentTrace] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            plan = PlanTrace(**item["plan"])
            skills = tuple(SkillTrace(**skill) for skill in item.get("skills", ()))
            economy = tuple(EconomyTrace(**receipt) for receipt in item.get("economy_receipts", ()))
            traces.append(
                AgentTrace(
                    agent_id=item["agent_id"],
                    state_summary=item["state_summary"],
                    goal=item["goal"],
                    plan=plan,
                    skills=skills,
                    policy_decisions=tuple(item.get("policy_decisions", ())),
                    economy_receipts=economy,
                    memory_writes=tuple(item.get("memory_writes", ())),
                    final_quality_score=float(item.get("final_quality_score", 0.0)),
                )
            )
        return cls(tuple(traces))

    def to_jsonl(self, path: str | Path) -> None:
        Path(path).write_text("\n".join(json.dumps(trace.as_record(), sort_keys=True) for trace in self.traces), encoding="utf-8")


def default_agent_traces() -> tuple[AgentTrace, ...]:
    return (
        AgentTrace(
            agent_id="agent_safe",
            state_summary="healthy supervised agent",
            goal="summarize safe local memory",
            plan=PlanTrace("summarize safe local memory", ("research-brief",), True, cost=0.1, risk=0.1),
            skills=(SkillTrace("research-brief", True, 0.92, 0.1),),
            policy_decisions=("allowed",),
            memory_writes=("summary",),
            final_quality_score=0.9,
        ),
        AgentTrace(
            agent_id="agent_economy",
            state_summary="economic agent settled verified work",
            goal="settle verified marketplace task",
            plan=PlanTrace("settle verified marketplace task", ("economic-task",), True, cost=1.0, risk=0.5),
            skills=(SkillTrace("economic-task", True, 0.82, 0.5),),
            policy_decisions=("approval_required", "approved"),
            economy_receipts=(EconomyTrace("task_1", "settled", 1.0),),
            memory_writes=("settlement_receipt",),
            final_quality_score=0.82,
        ),
        AgentTrace(
            agent_id="agent_failed",
            state_summary="skill failure generated repair plan",
            goal="run fragile external skill",
            plan=PlanTrace("run fragile external skill", ("fragile-skill",), False, cost=0.4, risk=0.8),
            skills=(SkillTrace("fragile-skill", False, 0.2, 0.8),),
            policy_decisions=("blocked",),
            memory_writes=("failure", "repair_recommendation"),
            final_quality_score=0.2,
        ),
    )
