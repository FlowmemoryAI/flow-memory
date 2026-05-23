"""Coalition formation and delegation primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from flow_memory.core.types import new_id
from flow_memory.protocols.a2a import CapabilityManifest


@dataclass(frozen=True)
class DelegationContract:
    delegator_did: str
    delegate_did: str
    capability: str
    budget: float = 0.0
    constraints: Mapping[str, Any] = field(default_factory=dict)
    contract_id: str = field(default_factory=lambda: new_id("delegation"))


@dataclass(frozen=True)
class Coalition:
    goal: str
    members: Sequence[str]
    delegations: Sequence[DelegationContract]
    coalition_id: str = field(default_factory=lambda: new_id("coalition"))


@dataclass
class SwarmCoordinator:
    manifests: dict[str, CapabilityManifest] = field(default_factory=dict)

    def register(self, manifest: CapabilityManifest) -> None:
        self.manifests[manifest.agent_did] = manifest

    def discover(self, capability: str) -> tuple[CapabilityManifest, ...]:
        return tuple(
            manifest for manifest in self.manifests.values() if capability in set(manifest.capabilities)
        )

    def form_coalition(self, goal: str, required_capabilities: Sequence[str], budget: float = 0.0) -> Coalition:
        delegations: list[DelegationContract] = []
        members: list[str] = []
        for capability in required_capabilities:
            candidates = self.discover(capability)
            if not candidates:
                raise ValueError(f"No agent found for capability: {capability}")
            delegate = candidates[0]
            members.append(delegate.agent_did)
            delegations.append(
                DelegationContract(
                    delegator_did="swarm:coordinator",
                    delegate_did=delegate.agent_did,
                    capability=capability,
                    budget=budget / max(1, len(required_capabilities)),
                )
            )
        return Coalition(goal=goal, members=tuple(dict.fromkeys(members)), delegations=tuple(delegations))
