"""Human-in-the-loop approval adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from flow_memory.core.types import Plan, PolicyDecision


class ApprovalStatus(str, Enum):
    """Explicit outcome from a human approval gate."""

    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"


@dataclass
class HumanApprovalGate:
    """Human-in-the-loop approval adapter."""

    approval_fn: Callable[[Plan, PolicyDecision], bool | str | ApprovalStatus | None] | None = None
    critical_permissions: frozenset[str] = frozenset(
        {"code.execute", "wallet.transfer", "browser.automation", "marketplace.bid", "filesystem.write"}
    )

    def requires_approval(self, plan: Plan, decision: PolicyDecision) -> bool:
        if decision.requires_human:
            return True
        return any(permission in self.critical_permissions for permission in plan.required_permissions)

    def request_approval(self, plan: Plan, decision: PolicyDecision) -> ApprovalStatus:
        if not self.requires_approval(plan, decision):
            return ApprovalStatus.ALLOW
        if self.approval_fn is None:
            return ApprovalStatus.DEFER

        outcome = self.approval_fn(plan, decision)
        if isinstance(outcome, ApprovalStatus):
            return outcome
        if isinstance(outcome, str):
            try:
                return ApprovalStatus(outcome.lower())
            except ValueError:
                return ApprovalStatus.DENY
        if outcome is None:
            return ApprovalStatus.DEFER
        return ApprovalStatus.ALLOW if bool(outcome) else ApprovalStatus.DENY

    def approve(self, plan: Plan, decision: PolicyDecision) -> bool:
        return self.request_approval(plan, decision) is ApprovalStatus.ALLOW
