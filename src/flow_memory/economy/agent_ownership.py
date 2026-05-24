"""Agent ownership model for local/testnet Flow Memory deployments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentOwnership:
    agent_id: str
    owner_id: str
    operator_id: str = ""
    governance_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def can_request_payment(self, actor_id: str) -> bool:
        return actor_id in {self.owner_id, self.operator_id} - {""}

    def can_change_policy(self, actor_id: str) -> bool:
        return actor_id in {self.owner_id, self.governance_id} - {""}

    def as_record(self) -> Mapping[str, Any]:
        return {
            "agent_id": self.agent_id,
            "owner_id": self.owner_id,
            "operator_id": self.operator_id,
            "governance_id": self.governance_id,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentOwnershipRegistry:
    ownership: dict[str, AgentOwnership] = field(default_factory=dict)

    def register(self, ownership: AgentOwnership) -> None:
        if not ownership.agent_id:
            raise ValueError("agent_id is required")
        if not ownership.owner_id:
            raise ValueError("owner_id is required")
        self.ownership[ownership.agent_id] = ownership

    def owner_of(self, agent_id: str) -> str:
        item = self.ownership.get(agent_id)
        if item is None:
            raise KeyError(f"unknown agent ownership: {agent_id}")
        return item.owner_id

    def as_record(self) -> Mapping[str, Any]:
        return {"ownership": tuple(item.as_record() for item in self.ownership.values())}
