"""Local swarm discovery registry."""
from __future__ import annotations

from dataclasses import dataclass, field

from flow_memory.swarm.agent_card import AgentCard


@dataclass
class AgentDiscoveryRegistry:
    agents: dict[str, AgentCard] = field(default_factory=dict)

    def register(self, card: AgentCard) -> None:
        self.agents[card.did] = card

    def get(self, did: str) -> AgentCard:
        try:
            return self.agents[did]
        except KeyError as exc:
            raise KeyError(f"Unknown agent: {did}") from exc

    def discover(self, capability: str) -> tuple[AgentCard, ...]:
        return tuple(card for card in self.agents.values() if card.has_capability(capability))
