"""Local agent card advertisements for swarm discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AgentCard:
    """Dependency-free agent advertisement.

    The card is intentionally small and serializable so it can be used by the
    local router, tests, and future protocol adapters without binding the core
    package to a web framework or DID library.
    """

    did: str
    name: str
    capabilities: Sequence[str]
    reputation: float = 0.0
    endpoints: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.did:
            raise ValueError("Agent DID is required")
        if not self.name:
            raise ValueError("Agent name is required")
        if not self.capabilities:
            raise ValueError("At least one capability is required")

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def as_manifest(self) -> Mapping[str, Any]:
        return {
            "did": self.did,
            "name": self.name,
            "capabilities": tuple(self.capabilities),
            "reputation": self.reputation,
            "endpoints": dict(self.endpoints),
            "metadata": dict(self.metadata),
        }
