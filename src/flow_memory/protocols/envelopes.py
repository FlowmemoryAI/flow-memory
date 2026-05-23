"""Protocol message envelopes."""

from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class ProtocolEnvelope:
    protocol: str
    sender: str
    recipient: str
    payload: Mapping[str, object]
    message_id: str = field(default_factory=lambda: new_id("msg"))

    def as_record(self) -> Mapping[str, object]:
        return {"message_id": self.message_id, "protocol": self.protocol, "sender": self.sender, "recipient": self.recipient, "payload": dict(self.payload)}
