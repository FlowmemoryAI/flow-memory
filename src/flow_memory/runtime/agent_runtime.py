"""Agent runtime manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from flow_memory.runtime.events import RuntimeHealth
from flow_memory.runtime.manager import BaseRuntimeManager as _RuntimeBaseRuntimeManager


if TYPE_CHECKING:

    @dataclass
    class _AgentRuntimeBase:
        name: str

        def health(self) -> RuntimeHealth: ...
else:
    _AgentRuntimeBase = _RuntimeBaseRuntimeManager


@dataclass
class AgentRuntimeManager(_AgentRuntimeBase):
    """Tracks local agent runtime state without network dependencies."""

    name: str = "agent"
    active_agents: set[str] = field(default_factory=set)

    def register_agent(self, agent_id: str) -> None:
        if not agent_id:
            raise ValueError("agent_id is required")
        self.active_agents.add(agent_id)

    def health(self) -> RuntimeHealth:
        health = super().health()
        return type(health)(
            name=health.name,
            ok=health.ok,
            running=health.running,
            ticks=health.ticks,
            checks={**health.checks, "agent_count": len(self.active_agents) >= 0},
            messages=health.messages,
        )

    def summary(self) -> Mapping[str, object]:
        return {"active_agents": tuple(sorted(self.active_agents))}
