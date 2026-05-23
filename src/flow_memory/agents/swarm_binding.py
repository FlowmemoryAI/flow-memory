"""Agent swarm/delegation binding."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.swarm.discovery import AgentDiscoveryRegistry


class AgentSwarmBinding:
    def __init__(self, discovery: AgentDiscoveryRegistry | None = None) -> None:
        self.discovery = discovery or AgentDiscoveryRegistry()

    def discover(self, capability: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(card.as_manifest() for card in self.discovery.find_by_capability(capability))
