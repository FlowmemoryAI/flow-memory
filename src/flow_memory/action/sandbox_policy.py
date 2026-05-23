"""Sandbox policy checks."""

from flow_memory.action.sandbox_profiles import SandboxProfile


def sandbox_requires_approval(profile: SandboxProfile) -> bool:
    return profile.requires_approval or profile.network == "allow" or bool(profile.filesystem_allowlist)
