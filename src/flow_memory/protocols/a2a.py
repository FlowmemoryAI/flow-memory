"""Agent-to-agent messaging primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class CapabilityManifest:
    agent_did: str
    name: str
    capabilities: Sequence[str]
    permissions: Sequence[str]
    endpoints: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentMessage:
    sender_did: str
    recipient_did: str
    kind: str
    payload: Mapping[str, Any]
    message_id: str = field(default_factory=lambda: new_id("msg"))
    created_at: object = field(default_factory=utc_now)


@dataclass
class LocalA2ABus:
    """In-memory bus for tests and local swarm prototypes."""

    inboxes: dict[str, list[AgentMessage]] = field(default_factory=dict)
    manifests: dict[str, CapabilityManifest] = field(default_factory=dict)

    def register(self, agent_did: str, manifest: CapabilityManifest | None = None) -> None:
        self.inboxes.setdefault(agent_did, [])
        if manifest is not None:
            self.manifests[agent_did] = manifest

    def discover(self, capability: str) -> tuple[CapabilityManifest, ...]:
        return tuple(manifest for manifest in self.manifests.values() if capability in manifest.capabilities)

    def send(self, message: AgentMessage) -> None:
        self.register(message.recipient_did)
        self.inboxes[message.recipient_did].append(message)

    def receive(self, agent_did: str) -> tuple[AgentMessage, ...]:
        self.register(agent_did)
        messages = tuple(self.inboxes[agent_did])
        self.inboxes[agent_did].clear()
        return messages
