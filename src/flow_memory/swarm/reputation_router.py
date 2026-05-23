"""Reputation-aware local routing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flow_memory.swarm.agent_card import AgentCard


@dataclass
class ReputationRouter:
    min_reputation: float = 0.0

    def rank(self, candidates: Sequence[AgentCard], capability: str) -> tuple[AgentCard, ...]:
        filtered = [card for card in candidates if card.has_capability(capability) and card.reputation >= self.min_reputation]
        return tuple(sorted(filtered, key=lambda card: (-card.reputation, card.did)))

    def choose(self, candidates: Sequence[AgentCard], capability: str) -> AgentCard:
        ranked = self.rank(candidates, capability)
        if not ranked:
            raise ValueError(f"No qualified agent for capability: {capability}")
        return ranked[0]
