"""Sandbox policy checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.action.sandbox_profiles import SandboxProfile


@dataclass(frozen=True)
class SandboxPolicyDecision:
    allowed: bool
    requires_approval: bool
    reasons: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, object]:
        return {"allowed": self.allowed, "requires_approval": self.requires_approval, "reasons": self.reasons}


def sandbox_requires_approval(profile: SandboxProfile) -> bool:
    return profile.requires_approval or profile.network == "allow" or bool(profile.filesystem_allowlist)


def evaluate_sandbox_profile(profile: SandboxProfile) -> SandboxPolicyDecision:
    errors = profile.validate()
    if errors:
        return SandboxPolicyDecision(False, False, errors)
    requires = sandbox_requires_approval(profile)
    return SandboxPolicyDecision(not requires, requires, ("approval required",) if requires else ())
