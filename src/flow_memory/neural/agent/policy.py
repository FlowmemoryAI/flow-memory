"""Tiny advisory agent policy network."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.torch_optional import require_torch


@dataclass(frozen=True)
class AgentPolicyScores:
    next_action_score: float
    plan_ranking_score: float
    uncertainty: float

    def as_record(self) -> Mapping[str, float]:
        return {"next_action_score": self.next_action_score, "plan_ranking_score": self.plan_ranking_score, "uncertainty": self.uncertainty}


class TinyAgentPolicyNetwork:
    """Small CPU-safe torch scoring function; advisory only."""

    def __init__(self) -> None:
        self.torch = require_torch()

    def score(self, agent_state_embedding: Any, goal_embedding: Any, memory_context_embedding: Any, candidate_plan_embedding: Any) -> AgentPolicyScores:
        torch = self.torch
        stacked = torch.stack([
            agent_state_embedding.float().mean(),
            goal_embedding.float().mean(),
            memory_context_embedding.float().mean(),
            candidate_plan_embedding.float().mean(),
        ])
        plan_score = torch.sigmoid(stacked.mean()).item()
        next_action = torch.sigmoid(stacked[1] + stacked[2] - stacked[3].abs() * 0.1).item()
        uncertainty = torch.sigmoid(stacked.std()).item()
        return AgentPolicyScores(float(next_action), float(plan_score), float(uncertainty))
