"""Resource limit helpers."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ResourceLimits:
    timeout_seconds: float
    memory_limit_mb: int
    cpu_limit: float

    def as_record(self) -> Mapping[str, object]:
        return {"timeout_seconds": self.timeout_seconds, "memory_limit_mb": self.memory_limit_mb, "cpu_limit": self.cpu_limit}
