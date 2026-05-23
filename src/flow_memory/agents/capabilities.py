"""Agent capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Capability:
    name: str
    description: str = ""

    def as_record(self) -> Mapping[str, str]:
        return {"name": self.name, "description": self.description}


def has_capability(capabilities: tuple[str, ...], required: str) -> bool:
    return required in capabilities or "*" in capabilities
