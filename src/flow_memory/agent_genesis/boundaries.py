"""Agent Genesis boundary registry and policy compilation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentBoundary:
    boundary_id: str
    display_name: str
    description: str
    policy_flags: Mapping[str, Any]
    approval_required: bool = True

    def as_record(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "display_name": self.display_name,
            "description": self.description,
            "policy_flags": dict(self.policy_flags),
            "approval_required": self.approval_required,
        }


BOUNDARIES: tuple[AgentBoundary, ...] = (
    AgentBoundary("ask_before_risky_action", "Ask before risky action", "Require approval for risky or irreversible actions.", {"approval_required_for_risk": True}),
    AgentBoundary("never_spend_money", "Never spend money", "Disallow real-funds movement and paid provider execution.", {"no_money_movement": True, "max_spend": 0.0}),
    AgentBoundary("never_delete_without_approval", "Never delete without approval", "Require explicit approval before destructive file operations.", {"destructive_action_requires_approval": True}),
    AgentBoundary("never_share_private_memory", "Never share private memory", "Exclude raw private memory from network contribution by default.", {"private_memory_allowed": False, "raw_payload_allowed": False}),
    AgentBoundary("local_only_by_default", "Local-only by default", "Prefer local/replay/dry-run paths unless explicitly configured otherwise.", {"local_only": True}),
    AgentBoundary("no_external_provider_calls", "No external provider calls", "Disable live provider calls in the public-alpha default profile.", {"no_live_provider_calls": True}),
    AgentBoundary("no_live_settlement", "No live settlement", "Allow dry-run settlement simulations only.", {"no_live_settlement": True}),
    AgentBoundary("no_private_keys", "No private keys", "Do not request, store, or use private keys.", {"no_private_keys": True}),
    AgentBoundary("no_unapproved_tool_use", "No unapproved tool use", "Restrict tools to policy-approved local actions.", {"approved_tools_only": True}),
)

BOUNDARY_BY_ID = {item.boundary_id: item for item in BOUNDARIES}


def list_boundaries() -> tuple[Mapping[str, Any], ...]:
    return tuple(item.as_record() for item in BOUNDARIES)


def get_boundary(boundary_id: str) -> AgentBoundary:
    try:
        return BOUNDARY_BY_ID[boundary_id]
    except KeyError as exc:
        raise KeyError(f"unknown agent boundary: {boundary_id}") from exc


def compile_boundaries(boundary_ids: tuple[str, ...]) -> Mapping[str, Any]:
    flags: dict[str, Any] = {"autonomy": "supervised", "approval_required": True}
    for boundary_id in boundary_ids:
        boundary = get_boundary(boundary_id)
        flags.update(boundary.policy_flags)
        flags["approval_required"] = bool(flags.get("approval_required", False) or boundary.approval_required)
    flags.setdefault("no_money_movement", True)
    flags.setdefault("private_memory_allowed", False)
    flags.setdefault("raw_payload_allowed", False)
    return flags
