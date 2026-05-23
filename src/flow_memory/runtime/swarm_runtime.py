"""Swarm runtime manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.runtime.manager import BaseRuntimeManager


@dataclass
class SwarmRuntimeManager(BaseRuntimeManager):
    """Tracks local agent discovery and delegation activity."""

    name: str = "swarm"
    discovered_agents: set[str] = field(default_factory=set)
    delegations: int = 0

    def discover(self, agent_did: str) -> None:
        self.discovered_agents.add(agent_did)

    def record_delegation(self) -> None:
        self.delegations += 1

    def summary(self) -> Mapping[str, object]:
        return {"agents": tuple(sorted(self.discovered_agents)), "delegations": self.delegations}
