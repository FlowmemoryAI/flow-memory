"""Policy engine."""

from __future__ import annotations

from dataclasses import dataclass

from flow_memory.core.types import Plan, PolicyDecision


@dataclass
class OPAPolicyEngine:
    """OPA/Rego-compatible policy boundary implemented in Python for the local kernel."""

    allowed_permissions: frozenset[str] = frozenset({"respond", "memory.read", "environment.observe", "tool.invoke"})
    human_review_permissions: frozenset[str] = frozenset(
        {"code.execute", "wallet.transfer", "browser.automation", "marketplace.bid", "filesystem.write"}
    )
    denied_actions: frozenset[str] = frozenset({"code.execute.raw", "wallet.transfer.raw"})
    max_economic_value_without_human: float = 0.0
    max_steps: int = 16

    def evaluate(self, plan: Plan) -> PolicyDecision:
        reasons: list[str] = []
        hard_denials: list[str] = []
        requires_human = False
        risk_level = "low"

        if len(plan.steps) > self.max_steps:
            hard_denials.append(f"Plan has {len(plan.steps)} steps; maximum is {self.max_steps}")
            requires_human = True
            risk_level = "high"

        for step in plan.steps:
            if step.action in self.denied_actions:
                hard_denials.append(f"Denied action: {step.action}")
                requires_human = True
                risk_level = "high"
            permission = step.required_permission
            if permission not in self.allowed_permissions:
                requires_human = True
                risk_level = "high" if permission in self.human_review_permissions else "medium"
                msg = f"Permission requires review: {permission}"
                reasons.append(msg)
                if permission not in self.human_review_permissions:
                    hard_denials.append(f"Permission not allowed by default policy: {permission}")
            if step.approval_required:
                requires_human = True
                risk_level = "high"
            if step.economic_value > self.max_economic_value_without_human:
                requires_human = True
                risk_level = "high"
                reasons.append(f"Economic value {step.economic_value} exceeds automatic limit {self.max_economic_value_without_human}")

        all_reasons = tuple(hard_denials + reasons)
        return PolicyDecision(approved=not hard_denials, reasons=all_reasons, requires_human=requires_human, risk_level=risk_level)
