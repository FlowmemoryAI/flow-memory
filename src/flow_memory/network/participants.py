"""Local network participant records for Flow Memory public-alpha demos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile
from flow_memory.swarm.agent_card import AgentCard


@dataclass(frozen=True)
class LocalNetworkParticipant:
    role: str
    profile: AgentProfile
    card: AgentCard
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "role": self.role,
            "profile": self.profile.as_record(),
            "card": self.card.as_manifest(),
            "metadata": dict(self.metadata),
        }


def participant(role: str, *, did: str, name: str, capabilities: tuple[str, ...], reputation: float = 0.0) -> LocalNetworkParticipant:
    profile = AgentProfile(
        name=name,
        identity=did,
        goals=(f"Operate as {role}",),
        capabilities=capabilities,
        allowed_tools=("observe_environment", "respond"),
        allowed_skills=("research_brief", "economic_task"),
        autonomy_mode="autonomous_local" if role != "requester" else "supervised",
        reputation=reputation,
        metadata={"network_role": role},
    )
    card = AgentCard(did=did, name=name, capabilities=capabilities, reputation=reputation)
    return LocalNetworkParticipant(role=role, profile=profile, card=card)
