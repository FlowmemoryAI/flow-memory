"""Container sandbox seam.

This module intentionally does not launch Docker by default. It describes the
interface and fails clearly when a real container runtime is not configured.
"""

from __future__ import annotations

from flow_memory.action.sandbox_profiles import SandboxProfile
from flow_memory.action.sandbox_receipts import SandboxReceipt
from flow_memory.crypto.hashes import content_hash


class ContainerSandboxUnavailable(RuntimeError):
    pass


class ContainerSandbox:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def run(self, command: tuple[str, ...], profile: SandboxProfile) -> SandboxReceipt:
        if not self.enabled:
            raise ContainerSandboxUnavailable("Container sandbox is not enabled; local sandbox remains default")
        return SandboxReceipt(status="not_implemented", profile_hash=content_hash({"command": command, "profile": profile.as_record()}))
