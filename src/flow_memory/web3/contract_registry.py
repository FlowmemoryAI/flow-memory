"""Contract registry JSON seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class ContractRegistry:
    chain: str = "base-sepolia"
    addresses: dict[str, str] = field(default_factory=dict)

    def register(self, name: str, address: str) -> None:
        self.addresses[name] = address

    def as_record(self) -> Mapping[str, object]:
        return {"chain": self.chain, "addresses": dict(self.addresses)}
