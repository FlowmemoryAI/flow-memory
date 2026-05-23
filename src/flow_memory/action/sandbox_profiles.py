"""Sandbox execution profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class SandboxProfile:
    timeout_seconds: float = 5.0
    memory_limit_mb: int = 128
    cpu_limit: float = 1.0
    filesystem_allowlist: tuple[str, ...] = field(default_factory=tuple)
    network: str = "deny"
    env_allowlist: tuple[str, ...] = field(default_factory=tuple)
    output_size_limit: int = 65536
    requires_approval: bool = False

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.timeout_seconds <= 0:
            errors.append("timeout must be positive")
        if self.memory_limit_mb <= 0:
            errors.append("memory limit must be positive")
        if self.network not in {"allow", "deny"}:
            errors.append("network must be allow or deny")
        return tuple(errors)

    def as_record(self) -> Mapping[str, object]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit": self.cpu_limit,
            "filesystem_allowlist": tuple(self.filesystem_allowlist),
            "network": self.network,
            "env_allowlist": tuple(self.env_allowlist),
            "output_size_limit": self.output_size_limit,
            "requires_approval": self.requires_approval,
        }
