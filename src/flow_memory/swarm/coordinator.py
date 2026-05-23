"""Local multi-agent coalition formation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from flow_memory.protocols.a2a import CapabilityManifest


@dataclass(frozen=True)
class Coalition:
    goal: str
    members: Sequence[CapabilityManifest]


@dataclass
class SwarmCoordinator:
    manifests: list[CapabilityManifest] = field(default_factory=list)

    def register(self, manifest: CapabilityManifest) -> None:
        self.manifests.append(manifest)

    def form_coalition(self, goal: str, required_capabilities: Sequence[str]) -> Coalition:
        required = set(required_capabilities)
        members = [
            manifest
            for manifest in self.manifests
            if required.intersection(set(manifest.capabilities))
        ]
        return Coalition(goal=goal, members=tuple(members))
