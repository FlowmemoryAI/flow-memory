"""FlowIR policy adapters."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.ir.policy import PolicySpec


def policy_rule_from_ir(policy: PolicySpec) -> Mapping[str, Any]:
    return {
        "id": policy.id,
        "permissions": tuple(policy.permissions),
        "risk_level": policy.risk_level,
        "requires_approval": policy.requires_approval,
        "allow_unsafe": policy.allow_unsafe,
    }
