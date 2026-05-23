"""Decentralized identity primitives."""

from __future__ import annotations

from dataclasses import dataclass, field

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class DID:
    """W3C DID-style identifier placeholder."""

    method: str = "key"
    identifier: str = field(default_factory=lambda: new_id("did").replace("did_", ""))

    def uri(self) -> str:
        return f"did:{self.method}:{self.identifier}"
