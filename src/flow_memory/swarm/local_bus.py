"""In-process local A2A bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class LocalSwarmMessage:
    sender: str
    recipient: str
    kind: str
    payload: Mapping[str, object]
    message_id: str = field(default_factory=lambda: new_id("swarm_msg"))
    created_at: object = field(default_factory=utc_now)


@dataclass
class LocalSwarmBus:
    inboxes: dict[str, list[LocalSwarmMessage]] = field(default_factory=dict)

    def send(self, sender: str, recipient: str, kind: str, payload: Mapping[str, object] | None = None) -> LocalSwarmMessage:
        message = LocalSwarmMessage(sender=sender, recipient=recipient, kind=kind, payload=dict(payload or {}))
        self.inboxes.setdefault(recipient, []).append(message)
        return message

    def poll(self, recipient: str) -> tuple[LocalSwarmMessage, ...]:
        messages = tuple(self.inboxes.get(recipient, ()))
        self.inboxes[recipient] = []
        return messages
